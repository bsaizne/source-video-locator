"""Phase 24-2 · 多模态召回探针 M2 —— 字幕事件语义召回(方向 C 的正确用法)。

用户 2026-09-01 拍板:分层检索「结合多模态进行判定」后,进一步拍板测
「字幕语义召回索引」——即方向 C(字幕语义→原片事件召回)第一次被完整验证,
此前只列远期、从未建过字幕→原片场景的召回通道。

M1(判定层)已证:VLM 事件级判定无判别力(失败族语义同貌),字幕语义仅弱方向性。
M2 换一个视角 = **召回层**:字幕描述的具体事件(如 test4「二十多人被困滑梯管道」)
能否把视觉漏检/视觉同质无解的正确事件**捞回候选池**——这是方向 C 的正确用法
(召回,不是判定),也是「早期纯视觉决策是否错过多模态红利」的直接裁决。

环境事实(已侦察):
  - 无文本嵌入模型(sentence-transformers/transformers/fastembed 全 MISS)
    → 无法做向量双塔检索,只能 VLM 事件语义匹配(受限但诚实的最小版)。
  - 字幕 OCR 全部可读: test4(法语)=
      "Deux petites filles ont été témoins..." / "a volontairement surchargé un toboggan aquatique" /
      "Plus de vingt personnes sont restées coincées dans le tube du toboggan" /
      "Ils ne pouvaient pas l'atteindre";
    p26 = "She used binoculars to watch what Levi was doing";
    t3r12 = "But the Elven King just stands there and watches"(64.75 与 66.0 均出现,同步性好)。

探针结构:
  M2a 字幕事件语义 → 正确事件窗 vs 干扰窗(VLM EVENT-MATCH, 事件级而非画面级):
      字幕描述的故事事件是否发生在候选窗画面中。
  M2b 对照: 正确窗命中率 vs 干扰窗命中率 → 字幕事件语义能否区分正确/干扰
      (重点 test4: 同质滑梯中「被困管道」事件若只在 353-355 命中 → 字幕召回有效)。

判据: 正确窗 EVENT-YES ≥2/3 且干扰窗显著更低 = 字幕事件召回有效;
      否则 = 字幕事件语义同样无判别力(与 M1 事件级证伪一致)。

输出: work/semantic_signal_M2_results.json
运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/research_semantic_signal_M2_subtitle_recall.py
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
    "test4": dict(orig="D:/ProjectXIXI/test4/test4-om.mkv",
                  edit="D:/ProjectXIXI/test4/test4-ed.mp4"),
    "test3": dict(orig="D:/ProjectXIXI/test3/test3-om.mp4",
                  edit="D:/ProjectXIXI/test3/test3-ed.mp4"),
}

# 字幕来自编辑段附近 OCR(已侦察,写死避免重复 OCR)
CASES = [
    ("test4", "t4r01", "Plus de vingt personnes sont restées coincées "
                       "dans le tube du toboggan",
     (3335, 3350), [(3319, 3329), (3355, 3359), (3359, 3377)],
     "同质滑梯: 正确事件[353,354,355]=[3329-3355] vs 干扰[352,356,357]=同质邻窗"),
    ("2mkv", "p26", "She used binoculars to watch what Levi was doing",
     (2808, 2811), [(1766, 1770)],
     "夜读(真值) vs 夜阳台(干扰, 编辑上下文区域)"),
    ("test3", "t3r12", "But the Elven King just stands there and watches",
     (454, 480), [(481, 488)],
     "精灵王重复镜头: 真值 vs 另一重复实例场景46"),
]

EVENT_MATCH_PROMPT = (
    "You are a film-event retrieval judge. Given a narration text (transcribed "
    "subtitles describing a story event) and a movie frame, decide whether the "
    "EVENT described in the narration is happening / visible in this frame — "
    "the same story event, even if filmed from a different camera angle or at a "
    "slightly different moment. If the frame shows people stuck in a water slide "
    "tube, that IS the 'people stuck in slide tube' event. "
    "Ignore burned-in TikTok watermarks and subtitles. "
    "Reply with EXACTLY one line starting with 'EVENT: YES' or 'EVENT: NO', "
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
    out = BENCH / "work" / "_m2_frame.png"
    subprocess.run([str(FFMPEG), "-y", "-v", "error", "-ss", f"{t:.3f}",
                    "-i", video, "-vf", "scale=512:-2", "-frames:v", "1",
                    str(out)], check=True, capture_output=True)
    return out.read_bytes()


def first_line(text: str) -> str:
    t = (text or "").strip()
    return t.splitlines()[0] if t else ""


def event_verdict(text: str) -> str | None:
    t = (text or "").upper()
    return "YES" if "EVENT: YES" in t else (
        "NO" if "EVENT: NO" in t else None)


def run_case(cfg, pair, pid, subtitle, true_win, dist_wins, note) -> dict:
    p = PAIRS[pair]
    out = {"id": pid, "pair": pair, "note": note, "subtitle": subtitle,
           "true_win": list(true_win), "dist_wins": [list(w) for w in dist_wins]}

    def eval_win(win):
        a, b = win
        ts = np.linspace(a + 0.2, b - 0.2, 3) if (b - a) > 0.6 else [a]
        votes = []
        for t in ts:
            fb = grab(p["orig"], float(t))
            txt = vlm_call(cfg, f"{EVENT_MATCH_PROMPT}\nNarration: \"{subtitle}\"",
                           [fb])
            v = event_verdict(txt)
            votes.append({"t": round(float(t), 2), "verdict": v,
                          "raw": first_line(txt)[:110]})
            print(f"[{pid}] t={t:.1f} event={v}", flush=True)
        return votes, sum(1 for x in votes if x["verdict"] == "YES")

    true_votes, true_yes = eval_win(true_win)
    out["true"] = {"votes": true_votes, "event_yes": true_yes,
                   "yes_ratio": round(true_yes / max(len(true_votes), 1), 2)}
    out["dist"] = []
    for w in dist_wins:
        dv, dy = eval_win(w)
        out["dist"].append({"win": list(w), "votes": dv, "event_yes": dy,
                            "yes_ratio": round(dy / max(len(dv), 1), 2)})
    print(f"== [{pid}] true_event_yes={true_yes}/3 dist_event_yes="
          f"{[d['event_yes'] for d in out['dist']]}", flush=True)
    return out


def main() -> int:
    t0 = time.time()
    cfg = json.loads(VLM_CFG.read_text(encoding="utf-8"))
    report = {"started": time.strftime("%Y-%m-%d %H:%M:%S"),
              "model": cfg["model"],
              "note": "M2 字幕事件语义召回: 字幕描述事件 -> 原片候选窗 VLM EVENT-MATCH",
              "cases": []}
    for case in CASES:
        report["cases"].append(run_case(cfg, *case))
    out = BENCH / "work" / "semantic_signal_M2_results.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nsaved {out}  total {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
