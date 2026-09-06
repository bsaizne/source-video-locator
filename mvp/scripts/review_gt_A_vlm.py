"""A 段对照图 VLM 多模态审查——逐张判定 TRUE/DIST/候选窗是否匹配编辑段。

用 M1-M3 已验证的 VLM 通道(Volcengine Ark), 对 5 张失败族对照图做语义审查。
每张输出: 编辑行内容 / TRUE 行匹配? / DIST 行是干扰? / 候选窗哪个对 / 人眼可否分 TRUE-DIST。
"""
import base64
import json
import sys
import time
import urllib.request
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]
WORK = BENCH / "work"
GT_A = BENCH / "mvp" / "benchmark" / "user_case" / "gt_A"
CFG = json.loads(Path(r"D:/deepseek harnees/vision-subagent/vision-mcp-config.json").read_text(encoding="utf-8"))

SHEETS = ["p08_sheet.jpg", "p38_sheet.jpg", "p26_sheet.jpg", "t3r12_sheet.jpg", "t4r01_sheet.jpg"]

PROMPT = """You are a film-footage verification judge. This is a comparison sheet for matching an EDITED (解说) video shot to ORIGINAL (原片) footage. The sheet layout:
- Row 1 (top): 3 frames from the EDITED video (the query shot) — the thing we are trying to locate.
- Row 2: labeled TRUE — 3 frames from the ORIGINAL at the claimed correct position.
- Row 3: labeled DIST — 3 frames from the ORIGINAL at a claimed distractor/兄弟机位 position (if present).
- Remaining rows: labeled c0/c1/c2 with sim= — top candidate windows found by the matcher.

Please judge each row carefully (the frames are from movies; ignore burned-in subtitles/watermarks):
1. Describe briefly what the EDITED row (row 1) shows.
2. TRUE row: does it show the SAME content/event/subject as the EDITED row (same scene, same actors, same story moment, even if different camera angle/shot size)? Reply TRUE_MATCH: YES or NO.
3. DIST row (if present): does it show the SAME content as EDITED, or a DIFFERENT/confusable shot? Reply DIST_SAME_AS_EDITED: YES or NO.
4. For each candidate row c0/c1/c2 (if present): does it match the EDITED content? Reply as C0_MATCH: YES/NO, C1_MATCH: YES/NO, C2_MATCH: YES/NO.
5. CAN_HUMAN_DISTINGUISH: can a human reliably tell the TRUE position from the DIST (brother) position based on these frames? YES/NO + one-line reason.
Keep it compact, one answer per line."""


def vlm_call(cfg, prompt, img_paths):
    images = []
    for p in img_paths:
        data = Path(p).read_bytes()
        images.append("data:image/jpeg;base64," + base64.b64encode(data).decode())
    body = {"model": cfg["model"],
            "messages": [{"role": "user", "content":
                          [{"type": "text", "text": prompt}]
                          + [{"type": "image_url", "image_url": {"url": u}} for u in images]}],
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
        pid = name.split("_")[0]
        path = GT_A / name
        print(f"=== {pid} ===", flush=True)
        t0 = time.time()
        try:
            text = vlm_call(CFG, PROMPT, [str(path)])
        except Exception as exc:
            print(f"  VLM FAIL: {exc}", flush=True)
            text = "VLM_FAIL: " + str(exc)
        dt = time.time() - t0
        print(text, flush=True)
        print(f"  ({dt:.1f}s)", flush=True)
        report["cases"].append({"id": pid, "sheet": name, "elapsed_s": round(dt, 1), "vlm": text})
        (WORK / "gt_A_vlm_review.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    out = WORK / "gt_A_vlm_review.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved", out, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
