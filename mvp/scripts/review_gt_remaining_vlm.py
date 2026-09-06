"""GT 重建专会话: 补审 NOT_REVIEWED + WRONG 共 14 条对照图 VLM 预筛。

目标案例:
  NOT_REVIEWED: p36 p37 p38 p39 p40 p41
  WRONG:        p01 p02 p03 p10 p19 p31 p32 p35

对每张 sheet 输出: ED 内容 / GT 行实际内容 / ED<->GT 是否对应 / ED<->C1 是否对应 /
C1 内容是否为正确位置的线索 / 建议正确窗口(若有把握)。

布局(gt_review/<pid>_sheet.jpg): row1=编辑3帧 ED, row2=GT 原片窗3帧 GT, row3=top-1候选 C1 3帧。
结果写 work/gt_review_remaining_vlm.json。
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

TARGETS = ["p01", "p02", "p03", "p10", "p19", "p31", "p32", "p35",
           "p36", "p37", "p38", "p39", "p40", "p41"]

PROMPT = """You are a film-footage verification judge. This sheet has 3 rows from matching an EDITED (解说) video shot to ORIGINAL (原片) footage:
- Row 1 (top): ED — 3 frames from the EDITED video (the query shot we are trying to locate).
- Row 2: GT — 3 frames from the ORIGINAL at the claimed correct position in the ground truth.
- Row 3: C1 — 3 frames from the ORIGINAL at the matcher's top-1 candidate window.

Judge carefully (ignore burned-in subtitles/watermarks; frames are from a movie):
1. ED: one line describing exactly what the edited row shows (subjects, actions, props, shot size, setting).
2. GT_CONTENT: one line describing what the GT row actually shows (subjects/actions/setting).
3. GT_MATCH: does the GT row show the SAME content/event/subject as ED (same scene/actors/story moment, even if different camera angle or shot size)? Reply GT_MATCH: YES or NO.
4. C1_CONTENT: one line describing what the C1 row shows.
5. C1_MATCH: does the C1 row match ED? Reply C1_MATCH: YES or NO.
6. If GT_MATCH=NO and C1_MATCH=YES, the C1 window is likely the correct position — say C1_IS_CORRECT: YES.
7. If both are NO, say BOTH_WRONG: YES and state what distinctive visual cues a human should look for to find the real position (character, clothing, prop, setting, light).
Keep it compact, one answer per line."""


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
        (WORK / "gt_review_remaining_vlm.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    out = WORK / "gt_review_remaining_vlm.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved", out, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
