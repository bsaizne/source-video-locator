"""GT 重建专会话: 9 条目标候选窗对照图 VLM 判定(找正确位置)。

对 gt_rebuild/<pid>_candidates.jpg(行1=ED 3帧, 行2..=W0..W5 候选窗各 3 帧)
判定每个候选窗是否与 ED 内容匹配, 给出推荐正确窗口。
结果写 work/gt_rebuild_candidates_vlm.json。
"""
import base64, json, sys, time, urllib.request
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]
WORK = BENCH / "work"
REBUILD = BENCH / "mvp" / "benchmark" / "user_case" / "gt_rebuild"
CFG = json.loads(Path(r"D:/deepseek harnees/vision-subagent/vision-mcp-config.json").read_text(encoding="utf-8"))

TARGETS = ["p04", "p10", "p16", "p18", "p34", "p35", "p36", "p37", "p40"]

PROMPT = """You are a film-footage verification judge. This comparison sheet helps locate an EDITED (解说) video shot inside ORIGINAL (原片) footage.
Layout:
- Row 1 (top): ED — 3 frames from the EDITED video (the query shot we are trying to locate). The edited shot may contain a quick montage of several sub-shots.
- Rows 2+ : W0, W1, ... — each is a candidate window from the ORIGINAL (3 frames each), found by a matcher.

Judge which candidate window(s) contain the SAME content/event/subject as ED (same scene/actors/story moment, even if different camera angle/shot size).
For EACH candidate row W0..W5 reply Wn_MATCH: YES or NO. If a row is partially matching, reply PARTIAL with a note.
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
    cand = json.loads((REBUILD / "gt_rebuild_candidates.json").read_text(encoding="utf-8"))
    by_id = {c["id"]: c for c in cand["cases"]}
    report = {"cases": []}
    for pid in TARGETS:
        c = by_id[pid]
        path = REBUILD / f"{pid}_candidates.jpg"
        print(f"=== {pid} (GT {c['gt'][0]}-{c['gt'][1]}) ===", flush=True)
        t0 = time.time()
        try:
            text = vlm_call(CFG, PROMPT, str(path))
        except Exception as exc:
            print(f"  VLM FAIL: {exc}", flush=True)
            text = "VLM_FAIL: " + str(exc)
        dt = time.time() - t0
        print(text, flush=True)
        print(f"  ({dt:.1f}s)", flush=True)
        report["cases"].append({"id": pid, "gt": c["gt"], "candidates": c["candidates"],
                                "vlm": text, "elapsed_s": round(dt, 1)})
        (WORK / "gt_rebuild_candidates_vlm.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    out = WORK / "gt_rebuild_candidates_vlm.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved", out, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
