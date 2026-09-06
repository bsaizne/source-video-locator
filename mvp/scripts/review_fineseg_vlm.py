"""test 域细切分候选(t2r02b/t2r03a) VLM 多模态复审（2026-09-04）。
复用 review_p36_vlm.py 通道。输出: work/fineseg_review/fineseg_vlm.json
"""
import base64
import json
import sys
import time
import urllib.request
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]
CFG = json.loads(Path(r"D:/deepseek harnees/vision-subagent/vision-mcp-config.json").read_text(encoding="utf-8"))
OUT_DIR = BENCH / "work" / "fineseg_review"
OUT = OUT_DIR / "fineseg_vlm.json"

SHEETS = ["t2r02b_candidates.jpg", "t2r03a_candidates.jpg"]

PROMPT = """You are a film-footage verification judge. This comparison sheet helps locate an EDITED (解说) video shot inside ORIGINAL (原片) footage.
Layout:
- Row 1 (top): ED — 3 frames from the EDITED video (the query shot we are trying to locate).
- Row 2: W_HIT — 3 frames from the ORIGINAL at a window found by a fine-grained single-frame matcher (candidate correct position).
- Row 3: W_WHOLE — 3 frames from the ORIGINAL at the window found by whole-segment matching (current runtime main).

Judge: does W_HIT contain the SAME content/event/subject as ED (same scene/actors/story moment, even if different camera angle/shot size)?
And does W_WHOLE match ED?
Reply exactly:
ED_CONTENT: <one-line description of what ED shows>
W_HIT_MATCH: YES or NO (or PARTIAL with note)
W_WHOLE_MATCH: YES or NO (or PARTIAL with note)
BEST_WINDOW: W_HIT or W_WHOLE or NONE
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
    report = {"cases": []}
    for name in SHEETS:
        path = OUT_DIR / name
        print(f"=== {name} ===", flush=True)
        t0 = time.time()
        try:
            text = vlm_call(CFG, PROMPT, str(path))
        except Exception as exc:
            print(f"  VLM FAIL: {exc}", flush=True)
            text = "VLM_FAIL: " + str(exc)
        dt = time.time() - t0
        print(text, flush=True)
        print(f"  ({dt:.1f}s)", flush=True)
        report["cases"].append({"id": name, "vlm": text, "elapsed_s": round(dt, 1)})
        OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved", OUT, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())