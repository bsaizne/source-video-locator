"""GT 重建专会话: PARTIAL 13 条 GT 行逐帧对齐判定(供收窄窗口)。

目标: p04 p07 p08 p11 p12 p14 p15 p16 p18 p21 p27 p33 p34
判定 GT 行 3 帧(左/中/右)中哪些与 ED 行对应, 以收窄正确窗口。
结果写 work/gt_review_partial_vlm.json。
"""
import base64, json, sys, time, urllib.request
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]
WORK = BENCH / "work"
REV = BENCH / "mvp" / "benchmark" / "user_case" / "gt_review"
CFG = json.loads(Path(r"D:/deepseek harnees/vision-subagent/vision-mcp-config.json").read_text(encoding="utf-8"))

TARGETS = ["p04", "p07", "p08", "p11", "p12", "p14", "p15", "p16", "p18", "p21", "p27", "p33", "p34"]

PROMPT = """You are a film-footage verification judge. This sheet has 3 rows from matching an EDITED (解说) video shot to ORIGINAL (原片) footage:
- Row 1 (top): ED — 3 frames from the EDITED video (the query shot to locate).
- Row 2: GT — 3 frames (left/middle/right) from the ORIGINAL at the ground-truth window.
- Row 3: C1 — 3 frames from the ORIGINAL at the matcher's top-1 candidate window.

The ground-truth window is suspected to be PARTLY correct (too wide / only part matches). Judge frame by frame:
1. ED: one line describing what the edited row shows (subjects/actions/props/setting).
2. GT_FRAMES: for each of the 3 GT frames (left, middle, right) say whether it shows the SAME content/event/subject as ED. Format exactly:
   GT_LEFT: MATCH or NO
   GT_MIDDLE: MATCH or NO
   GT_RIGHT: MATCH or NO
3. C1_MATCH: does the C1 row match ED? Reply C1_MATCH: YES or NO.
4. If a GT frame is NO, one line on what it actually shows.
Keep compact, one answer per line."""


def vlm_call(cfg, prompt, img_path):
    data = Path(img_path).read_bytes()
    url = "data:image/jpeg;base64," + base64.b64encode(data).decode()
    body = {"model": cfg["model"],
            "messages": [{"role": "user", "content":
                          [{"type": "text", "text": prompt},
                           {"type": "image_url", "image_url": {"url": url}}]}],
            "max_tokens": 800}
    req = urllib.request.Request(
        f"{cfg['base']}/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + cfg["apiKey"]})
    with urllib.request.urlopen(req, timeout=cfg.get("timeoutMs", 120000) / 1000) as r:
        data = json.loads(r.read())
    return data["choices"][0]["message"]["content"]


def main() -> int:
    manifest = json.loads((REV / "gt_review_manifest.json").read_text(encoding="utf-8"))
    by_id = {c["id"]: c for c in manifest["cases"]}
    report = {"cases": []}
    for pid in TARGETS:
        c = by_id[pid]
        path = REV / f"{pid}_sheet.jpg"
        print(f"=== {pid} (GT {c['gt'][0]}-{c['gt'][1]} C1 {c['c1'][0]}-{c['c1'][1]}) ===", flush=True)
        t0 = time.time()
        try:
            text = vlm_call(CFG, PROMPT, str(path))
        except Exception as exc:
            print(f"  VLM FAIL: {exc}", flush=True)
            text = "VLM_FAIL: " + str(exc)
        dt = time.time() - t0
        print(text, flush=True)
        print(f"  ({dt:.1f}s)", flush=True)
        report["cases"].append({"id": pid, "gt": c["gt"], "c1": c["c1"],
                                "vlm": text, "elapsed_s": round(dt, 1)})
        (WORK / "gt_review_partial_vlm.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    out = WORK / "gt_review_partial_vlm.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved", out, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
