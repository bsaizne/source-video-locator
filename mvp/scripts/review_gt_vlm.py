"""41 条 GT 对照图 VLM 批量预筛——逐张判定 GT 行是否匹配编辑行(校准阶段数据层)。

布局(gt_review/<pid>_sheet.jpg): row1=编辑3帧 ED, row2=GT 原片窗3帧 GT, row3=top-1候选 C1 3帧。
输出每条: ED内容 / GT_MATCH(YES/NO) / C1_MATCH(YES/NO) / 判定(OK 或 SUSPECT)。
供用户聚焦人工审核: 只重点复核 SUSPECT, OK 条可抽验。
"""
import base64
import json
import sys
import time
import urllib.request
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]
WORK = BENCH / "work"
REV = BENCH / "mvp" / "benchmark" / "user_case" / "gt_review"
CFG = json.loads(Path(r"D:/deepseek harnees/vision-subagent/vision-mcp-config.json").read_text(encoding="utf-8"))

PROMPT = """You are a film-footage verification judge. This sheet has 3 rows from matching an EDITED (解说) video shot to ORIGINAL (原片) footage:
- Row 1 (top): ED — 3 frames from the EDITED video (the query shot we are trying to locate).
- Row 2: GT — 3 frames from the ORIGINAL at the claimed correct position in the ground truth.
- Row 3: C1 — 3 frames from the ORIGINAL at the matcher's top-1 candidate window.

Judge carefully (ignore burned-in subtitles/watermarks; frames are from movies):
1. ED: one line describing what the edited row shows.
2. GT_MATCH: does the GT row show the SAME content/event/subject as ED (same scene/actors/story moment, even different camera angle or shot size)? Reply GT_MATCH: YES or NO.
3. C1_MATCH: does the C1 row match ED? Reply C1_MATCH: YES or NO.
4. If GT_MATCH=NO, say in one line what the GT row actually shows (to help judge whether it's a mislabeled GT or an ambiguous case).
Keep compact, one answer per line."""


def vlm_call(cfg, prompt, img_path):
    data = Path(img_path).read_bytes()
    url = "data:image/jpeg;base64," + base64.b64encode(data).decode()
    body = {"model": cfg["model"],
            "messages": [{"role": "user", "content":
                          [{"type": "text", "text": prompt},
                           {"type": "image_url", "image_url": {"url": url}}]}],
            "max_tokens": 500}
    req = urllib.request.Request(
        f"{cfg['base']}/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + cfg["apiKey"]})
    with urllib.request.urlopen(req, timeout=cfg.get("timeoutMs", 120000) / 1000) as r:
        data = json.loads(r.read())
    return data["choices"][0]["message"]["content"]


def main() -> int:
    manifest = json.loads((REV / "gt_review_manifest.json").read_text(encoding="utf-8"))
    cases = manifest["cases"]
    report = {"cases": []}
    for c in cases:
        pid = c["id"]
        path = REV / f"{pid}_sheet.jpg"
        print(f"=== {pid} (GT {c['gt'][0]}-{c['gt'][1]} C1 {c['c1'][0]}-{c['c1'][1] if c['c1'] else '-'}) ===", flush=True)
        t0 = time.time()
        try:
            text = vlm_call(CFG, PROMPT, str(path))
        except Exception as exc:
            print(f"  VLM FAIL: {exc}", flush=True)
            text = "VLM_FAIL: " + str(exc)
        dt = time.time() - t0
        print(text, flush=True)
        print(f"  ({dt:.1f}s)", flush=True)
        gt_match = "GT_MATCH: YES" in text
        c1_match = "C1_MATCH: YES" in text
        report["cases"].append({"id": pid, "gt": c["gt"], "c1": c["c1"],
                                "vlm": text, "gt_match": gt_match, "c1_match": c1_match,
                                "elapsed_s": round(dt, 1)})
        (WORK / "gt_review_vlm.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    out = WORK / "gt_review_vlm.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved", out, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
