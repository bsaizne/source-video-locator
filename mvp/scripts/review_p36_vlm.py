"""p36 细切分取证 · 多模态复审（2026-09-04）——VLM 判定 ED vs 候选窗内容匹配。
复用 review_gt_rebuild_vlm.py 的 Volcengine Ark 通道。
输入: work/p36_review/p36_candidates.jpg | 输出: work/p36_review/p36_vlm.json
"""
import base64
import json
import sys
import time
import urllib.request
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]
CFG = json.loads(Path(r"D:/deepseek harnees/vision-subagent/vision-mcp-config.json").read_text(encoding="utf-8"))
SHEET = BENCH / "work" / "p36_review" / "p36_candidates.jpg"
OUT = BENCH / "work" / "p36_review" / "p36_vlm.json"

PROMPT = """You are a film-footage verification judge. This comparison sheet helps locate an EDITED (解说) video shot inside ORIGINAL (原片) footage.
Layout:
- Row 1 (top): ED — 3 frames from the EDITED video (the query shot, edited time ~110-111.5s). The edited shot may contain a quick montage of several sub-shots.
- Rows 2+ : W0, W1, W2, W3 — each is a candidate window from the ORIGINAL (3 frames each) found by a matcher.

Judge which candidate window(s) contain the SAME content/event/subject as ED (same scene/actors/story moment, even if different camera angle/shot size).
For EACH candidate row reply Wn_MATCH: YES or NO (or PARTIAL with a note).
Then one line: BEST_WINDOW: <the best matching window id, or NONE if none matches>.
Keep compact, one answer per line."""


def vlm_call(cfg, prompt, img_path):
    data = Path(img_path).read_bytes()
    url = "data:image/jpeg;base64," + base64.b64encode(data).decode()
    body = {"model": cfg["model"],
            "messages": [{"role": "user", "content":
                          [{"type": "text", "text": prompt},
                           {"type": "image_url", "image_url": {"url": url}}]}],
            "max_tokens": 900}
    req = urllib.request.Request(
        f"{cfg['base']}/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + cfg["apiKey"]})
    with urllib.request.urlopen(req, timeout=cfg.get("timeoutMs", 120000) / 1000) as r:
        data = json.loads(r.read())
    return data["choices"][0]["message"]["content"]


def main() -> int:
    print("sheet:", SHEET, "exists:", SHEET.exists(), flush=True)
    t0 = time.time()
    try:
        text = vlm_call(CFG, PROMPT, str(SHEET))
    except Exception as exc:
        print(f"VLM FAIL: {exc}", flush=True)
        text = "VLM_FAIL: " + str(exc)
    dt = time.time() - t0
    print(text, flush=True)
    print(f"({dt:.1f}s)", flush=True)
    OUT.write_text(json.dumps({"model": CFG["model"], "prompt": PROMPT, "vlm": text,
                              "elapsed_s": round(dt, 1), "sheet": str(SHEET)},
                             ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved", OUT, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())