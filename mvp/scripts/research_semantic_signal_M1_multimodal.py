"""Phase 24-2 · 多模态判定探针 M1 —— 字幕语义召回层 + VLM 事件级判定层。

用户 2026-09-01 拍板:分层检索方向「结合多模态进行判定」,两层都测(A)。
  M1a 召回层: 编辑片解说字幕 OCR -> 语义文本, 与原片候选窗帧做 VLM 语义匹配,
              验证「字幕语义能否把正确事件捞回候选池 / 能否区分兄弟-干扰」。
  M1b 判定层: 查询帧 vs 候选帧(正确/兄弟/干扰) 的 VLM「事件级」判定
              (是否同一事件/同一场景, 容忍不同机位——区别于 Phase 24-1 的帧级判定)。

仅研究侧, 零 runtime。VLM 调用 <= 18 次(成本控制)。

数据事实(已侦察):
  - 编辑段解说字幕 OCR 全部可读: p08="And this mission is even more top secret",
    p26="She used binoculars to watch what Levi was doing",
    t3r12="But the Elven King just stands there and watches",
    p04="Preventing horrible monsters from escaping"。
  - 注意 p26 字幕讲"望远镜女看 Levi 在做什么", 而画面是"夜读男"——字幕与画面可能异步,
    这正是要验证的点。

输出: work/semantic_signal_M1_results.json
运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/research_semantic_signal_M1_multimodal.py
"""
from __future__ import annotations

import base64
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

BENCH = Path(__file__).resolve().parents[2]
FFMPEG = BENCH / "tools" / "ffmpeg.exe"
VLM_CFG = Path("D:/deepseek harnees/vision-subagent/vision-mcp-config.json")

PAIRS = {
    "2mkv":  dict(orig="D:/video/2.mkv",  edit="D:/video/1.mp4"),
    "test3": dict(orig="D:/ProjectXIXI/test3/test3-om.mp4",
                  edit="D:/ProjectXIXI/test3/test3-ed.mp4"),
}

# (pair, pid, 查询编辑时间, 字幕参考时间, 正确窗, 兄弟窗|None, 干扰窗|None, 说明)
CASES = [
    ("2mkv", "p08", 13.5, 13.5, (1108, 1110), (1048, 1050), None,
     "兄弟机位: 瞭望塔机位(真值) vs 士兵特写(兄弟)"),
    ("2mkv", "p26", 77.0, 77.0, (2808, 2811), None, (1766, 1770),
     "夜读(真值) vs 编辑上下文区域(干扰, 高 sim 误配)"),
    ("test3", "t3r12", 64.75, 64.75, (454, 480), None, (481, 488),
     "精灵王重复镜头(真值 454-480) vs 另一重复实例场景46(干扰, 481-488)"),
]

MATCH_PROMPT = (
    "You are matching a movie narration subtitle to film footage. "
    "Given a narration text and a movie frame, decide whether the narration text "
    "describes the content / event / subject shown in this frame. "
    "Ignore burned-in TikTok watermarks and subtitles. "
    "Reply with EXACTLY one line starting with 'MATCH: YES' or 'MATCH: NO', "
    "then a short reason."
)

EVENT_PROMPT = (
    "You are a film-story event judge. Given two movie frames, decide whether they "
    "show the SAME EVENT or SCENE of the story (same subjects at the same story moment, "
    "even if from a different camera angle / different shot size), or DIFFERENT events "
    "(different scene / different story moment / different subjects). "
    "Ignore burned-in subtitles, watermarks and logo text. "
    "Reply with EXACTLY one line starting with 'VERDICT: SAME' or 'VERDICT: DIFFERENT', "
    "then a short reason."
)


def vlm_call(cfg: dict, prompt: str, images: list[bytes]) -> str:
    import urllib.request

    def dataurl(img: bytes) -> str:
        return "data:image/png;base64," + base64.b64encode(img).decode()

    body = {
        "model": cfg["model"],
        "messages": [{
            "role": "user",
            "content": [{"type": "text", "text": prompt}]
                       + [{"type": "image_url", "image_url": {"url": dataurl(img)}}
                          for img in images],
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


def grab(video: str, t: float) -> bytes:
    out = BENCH / "work" / "_m1_frame.png"
    subprocess.run([str(FFMPEG), "-y", "-v", "error", "-ss", f"{t:.3f}",
                    "-i", video, "-vf", "scale=512:-2", "-frames:v", "1",
                    str(out)], check=True, capture_output=True)
    return out.read_bytes()


def first_line(text: str) -> str:
    t = (text or "").strip()
    return t.splitlines()[0] if t else ""


def verdict(text: str, key: str) -> str | None:
    t = (text or "").upper()
    return "YES" if f"{key}: YES" in t else (
        "NO" if f"{key}: NO" in t else None)


def event_verdict(text: str) -> str | None:
    t = (text or "").upper()
    if "VERDICT: SAME" in t:
        return "SAME"
    if "VERDICT: DIFFERENT" in t:
        return "DIFFERENT"
    return None


def run_case(cfg, pair, pid, qt, sub_t, true_win, brother_win, dist_win, note) -> dict:
    p = PAIRS[pair]
    out = {"id": pid, "pair": pair, "note": note,
           "true_win": list(true_win), "brother_win": list(brother_win) if brother_win else None,
           "dist_win": list(dist_win) if dist_win else None}

    # 查询帧(编辑段)
    qb = grab(p["edit"], qt)

    # 候选窗抽帧(正确/兄弟/干扰各 1 帧, 取窗中心)
    def mid_frames(win):
        a, b = win
        ts = np.linspace(a + 0.2, b - 0.2, 3) if (b - a) > 0.6 else [a]
        return ts, [grab(p["orig"], float(t)) for t in ts]

    candidates = [("true", true_win)]
    if brother_win:
        candidates.append(("brother", brother_win))
    if dist_win:
        candidates.append(("dist", dist_win))

    # ===== M1a 字幕语义召回: 字幕文本 -> 候选帧 =====
    # 字幕文本: 由本探针脚本外部提供(已侦察 OCR, 写死在常量里避免重复 OCR)
    SUBTITLES = {
        "p08": "And this mission is even more top secret",
        "p26": "She used binoculars to watch what Levi was doing",
        "t3r12": "But the Elven King just stands there and watches",
    }
    sub_txt = SUBTITLES.get(pid)
    m1a = {"subtitle": sub_txt, "hits": {}}
    if sub_txt:
        for kind, win in candidates:
            ts, frames = mid_frames(win)
            votes = []
            for t, fb in zip(ts, frames):
                txt = vlm_call(cfg, MATCH_PROMPT.format(narration=sub_txt)
                               if "{narration}" in MATCH_PROMPT
                               else f"{MATCH_PROMPT}\nNarration: \"{sub_txt}\"",
                               [fb])
                v = verdict(txt, "MATCH")
                votes.append({"t": round(float(t), 2), "verdict": v,
                              "raw": first_line(txt)[:100]})
                print(f"[{pid}][M1a] {kind} t={t:.1f} match={v}", flush=True)
            m1a["hits"][kind] = {"votes": votes,
                                 "yes": sum(1 for x in votes if x["verdict"] == "YES")}
    out["M1a_subtitle_recall"] = m1a

    # ===== M1b VLM 事件级判定: 查询帧 vs 候选帧 =====
    m1b = {"hits": {}}
    for kind, win in candidates:
        ts, frames = mid_frames(win)
        votes = []
        for t, fb in zip(ts, frames):
            txt = vlm_call(cfg, EVENT_PROMPT, [qb, fb])
            v = event_verdict(txt)
            votes.append({"t": round(float(t), 2), "verdict": v,
                          "raw": first_line(txt)[:100]})
            print(f"[{pid}][M1b] {kind} t={t:.1f} event={v}", flush=True)
        m1b["hits"][kind] = {"votes": votes,
                             "same": sum(1 for x in votes if x["verdict"] == "SAME")}
    out["M1b_event_judge"] = m1b

    print(f"== [{pid}] M1a(subtitle) true_yes="
          f"{m1a['hits'].get('true', {}).get('yes')} M1b(event) true_same="
          f"{m1b['hits'].get('true', {}).get('same')}", flush=True)
    return out


def main() -> int:
    t0 = time.time()
    cfg = json.loads(VLM_CFG.read_text(encoding="utf-8"))
    report = {"started": time.strftime("%Y-%m-%d %H:%M:%S"),
              "model": cfg["model"], "cases": []}
    for case in CASES:
        report["cases"].append(run_case(cfg, *case))
    out = BENCH / "work" / "semantic_signal_M1_results.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nsaved {out}  total {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
