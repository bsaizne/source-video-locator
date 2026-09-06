"""Phase 24-1 VLM 多模态判读 v2 —— 换新视觉模型后的严谨重跑。

改进(相对 6.5 单帧判读):
  1. 每候选窗抽 3 帧(起/中/末),逐帧对查询帧判 SAME/DIFFERENT,多数表决;
  2. 查询帧也抽 3 帧(ed±0.4),分别判,汇总;
  3. 输出每对(查询帧, 候选帧)的 VLM 判定 + 理由,生成多数票结论;
  4. 判定 prompt 固定、强制二选一开头,减少自由发挥。

用法:
  python mvp/scripts/research_phase24_1_vlm.py [--probes p08,p08b,p26]
配置: 读 vision-mcp-config.json(base/key/model,火山方舟视觉模型)。
"""
from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

BENCH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BENCH / "mvp" / "src"))

from media.ffmpeg import FFmpegIO

FFMPEG = BENCH / "tools" / "ffmpeg.exe"
FP = (BENCH.parent / "video-dedup-tool" / ".venv" / "Lib" / "site-packages"
      / "static_ffmpeg" / "bin" / "win32" / "ffprobe.exe")
VLM_CFG = Path("D:/deepseek harnees/vision-subagent/vision-mcp-config.json")

PAIRS = {
    "2mkv":  dict(orig="D:/video/2.mkv",  edit="D:/video/1.mp4"),
    "test3": dict(orig="D:/ProjectXIXI/test3/test3-om.mp4",
                  edit="D:/ProjectXIXI/test3/test3-ed.mp4"),
}
PROBES = [
    ("2mkv", "p08",  13.5, (1108, 1110), "瞭望塔+同桌机位(真值)", (1048, 1050)),
    ("2mkv", "p08b", 13.9, (1048, 1050), "士兵特写(真值)", (1108, 1110)),
    ("2mkv", "p26",  76.8, (2808, 2811), "夜读书(真值)", None),
    ("2mkv", "p01",   0.8, (2417, 2428), "金属球准备(sanity)", None),
    ("test3", "t3r12", 64.75, (454, 480), "精灵王重复镜头", None),
]

JUDGE_PROMPT = (
    "You are a careful film-footage forensics judge. "
    "Given two movie frames, decide whether they show the SAME source footage "
    "(same camera shot, same scene, same framing of the same subjects at the same moment) "
    "or DIFFERENT footage (different shot/scene/subjects, or same scene from a different "
    "camera angle). Note: ignore burned-in subtitles/watermarks/logo text when judging content. "
    "Reply with EXACTLY one line starting with 'VERDICT: SAME' or 'VERDICT: DIFFERENT', "
    "then a short 1-2 sentence reason."
)


def vlm_judge(cfg: dict, img_a: bytes, img_b: bytes, prompt: str) -> str:
    """调用视觉模型判两帧。返回模型文本。"""
    import urllib.request

    def dataurl(img: bytes) -> str:
        return "data:image/png;base64," + base64.b64encode(img).decode()

    body = {
        "model": cfg["model"],
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": dataurl(img_a)}},
                {"type": "image_url", "image_url": {"url": dataurl(img_b)}},
            ],
        }],
        "max_tokens": 500,
    }
    req = urllib.request.Request(
        f"{cfg['base']}/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {cfg['apiKey']}"},
    )
    with urllib.request.urlopen(req, timeout=cfg.get("timeoutMs", 120000) / 1000) as r:
        data = json.loads(r.read())
    return data["choices"][0]["message"]["content"]


def verdict_of(text: str) -> str | None:
    t = (text or "").strip().upper()
    if t.startswith("VERDICT: SAME") or "VERDICT: SAME" in t:
        return "SAME"
    if t.startswith("VERDICT: DIFFERENT") or "VERDICT: DIFFERENT" in t:
        return "DIFFERENT"
    return None


def grab(ff: FFmpegIO, video: str, t: float) -> bytes:
    """抽帧返回 PNG bytes(缩放短边 512 控制体积)。"""
    out = BENCH / "work" / "_vlm_frame.png"
    subprocess.run([str(FFMPEG), "-y", "-v", "error", "-ss", f"{t:.3f}",
                    "-i", video, "-vf", "scale=512:-2", "-frames:v", "1",
                    str(out)], check=True, capture_output=True)
    return out.read_bytes()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probes", default=None)
    args = ap.parse_args()

    cfg = json.loads(VLM_CFG.read_text(encoding="utf-8"))
    ff = FFmpegIO(FFMPEG, FP)
    report = {"started": time.strftime("%Y-%m-%d %H:%M:%S"),
              "model": cfg["model"], "base": cfg["base"], "probes": []}

    want = set(args.probes.split(",")) if args.probes else None
    for pair, pid, qt, true_win, note, brother in PROBES:
        if want and pid not in want:
            continue
        p = PAIRS[pair]
        q_ts = [qt - 0.4, qt, qt + 0.4]
        # 候选窗内抽帧: 真值窗(3) + 兄弟窗(3, 若有)
        spans = [("true", true_win)] + ([("brother", brother)] if brother else [])
        rows = []
        for q_t in q_ts:
            qb = grab(ff, p["edit"], q_t)
            for kind, (a, b) in spans:
                c_ts = np.linspace(a + 0.2, b - 0.2, 3) if (b - a) > 0.6 \
                    else [a]
                votes = []
                for c_t in c_ts:
                    cb = grab(ff, p["orig"], float(c_t))
                    txt = vlm_judge(cfg, qb, cb, JUDGE_PROMPT)
                    v = verdict_of(txt)
                    votes.append({"c_t": round(float(c_t), 2), "verdict": v,
                                  "raw": txt.strip().splitlines()[0][:120]
                                  if txt else ""})
                rows.append({"q_t": round(q_t, 2), "kind": kind, "span": [a, b],
                             "votes": votes,
                             "sames": sum(1 for x in votes if x["verdict"] == "SAME")})
            print(f"[{pid}] q={q_t:.1f} true_same="
                  f"{sum(1 for r in rows if r['kind']=='true' and abs(r['q_t']-q_t)<0.01 and r['sames']>1)}"
                  f"/3 bro_same="
                  f"{sum(1 for r in rows if r['kind']=='brother' and abs(r['q_t']-q_t)<0.01 and r['sames']>1)}"
                  f"/3", flush=True)

        # 汇总: 真值窗命中(≥2 SAME)/兄弟窗命中
        true_hit = sum(1 for r in rows if r["kind"] == "true" and r["sames"] >= 2)
        bro_rows = [r for r in rows if r["kind"] == "brother"]
        bro_hit = sum(1 for r in bro_rows if r["sames"] >= 2) if bro_rows else None
        report["probes"].append({
            "id": pid, "pair": pair, "note": note, "query_t": qt,
            "true_win": list(true_win), "brother": list(brother) if brother else None,
            "true_frames_same3": true_hit, "brother_frames_same3": bro_hit,
            "detail": rows,
        })
        print(f"== [{pid}] true_hit(≥2SAME/3q)={true_hit} "
              f"bro_hit={bro_hit} | note={note}", flush=True)

    out = BENCH / "work" / "phase24_1_vlm2_results.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nsaved {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
