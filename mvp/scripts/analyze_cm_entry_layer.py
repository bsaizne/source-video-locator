"""竞品入口/资源层整值转储（2026-10-06 竞品侧下一刀 ①）。

范围 = cutmatch.processing.{video.processor,video.concat,jobs.batch,progress.tracker,
resources.device_events,resources.memory_safety} + cutmatch.web.processing_api.* +
cutmatch.runtime.{resources,tools}。只读静态常量，不运行竞品、不碰授权/受保护模型。

输出：
- work/cm_redig/entry/<module>.txt      每模块逐值全文（供 drill-down）
- work/cm_redig/entry_view_20261006.md  可读视图：长文本(docstring/话术) + 数值 + 结构化对象

Run: D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/analyze_cm_entry_layer.py
FINDINGS_CUTMATCH_ENTRY_LAYER_20261006.md 里的 `view:行号` 指本脚本产出的
`entry_view_20261006.md`；输入与输出均在仓库外/gitignore，本脚本是复现入口。
"""
import json
import sys
from pathlib import Path

DATA = Path(r"D:\claudework\cutmatch-analysis\data")
OUT_DIR = Path(r"D:\claudework\benchmark\work\cm_redig\entry")
OUT_VIEW = Path(r"D:\claudework\benchmark\work\cm_redig\entry_view_20261006.md")

TARGETS = (
    "cutmatch.processing.video.processor",
    "cutmatch.processing.video.concat",
    "cutmatch.processing.jobs.batch",
    "cutmatch.processing.progress.tracker",
    "cutmatch.processing.resources.device_events",
    "cutmatch.processing.resources.memory_safety",
    "cutmatch.web.processing_api.single",
    "cutmatch.web.processing_api.batch",
    "cutmatch.web.processing_api.state",
    "cutmatch.web.processing_api.routes",
    "cutmatch.web.processing_api.diagnostics",
    "cutmatch.runtime.resources",
    "cutmatch.runtime.tools",
    "cutmatch.processing.jobs",
    "cutmatch.processing.progress",
    "cutmatch.processing.resources",
    "cutmatch.processing.video",
)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def fmt(v):
    if isinstance(v, str):
        return "S " + v.replace("\n", " / ")
    if isinstance(v, bool) or v is None:
        return "K " + repr(v)
    if isinstance(v, (int, float)):
        return "N " + repr(v)
    return "X " + json.dumps(v, ensure_ascii=False)


def main():
    blobs = json.loads((DATA / "nuitka_blobs.json").read_text(encoding="utf-8"))
    mods = {}
    for l in (DATA / "nuitka_blob_index.txt").read_text(encoding="utf-8-sig").splitlines():
        m = __import__("re").match(r"@0x([0-9a-f]+) count=\s*(\d+) module=(\S+)", l.strip())
        if m:
            mods[int(m.group(1), 16)] = m.group(3)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    per_mod = {}
    for b in blobs:
        mod = mods.get(b["start"])
        if not mod or mod not in TARGETS:
            continue
        per_mod.setdefault(mod, []).extend(b.get("values", []))

    long_text, numbers, structs, ident = [], [], [], []
    for mod, vals in sorted(per_mod.items()):
        (OUT_DIR / (mod + ".txt")).write_text(
            "\n".join(f"{i:4d} {fmt(v)}" for i, v in enumerate(vals)), encoding="utf-8")
        for v in vals:
            if isinstance(v, str):
                if len(v) >= 60:
                    long_text.append((mod, v))
                elif 4 <= len(v) < 60 and (" " not in v.strip()):
                    ident.append((mod, v))
            elif isinstance(v, (int, float)) and not isinstance(v, bool):
                numbers.append((mod, v))
            elif isinstance(v, (list, dict)):
                structs.append((mod, v))

    lines = ["# 竞品入口/资源层可读视图（2026-10-06）", ""]
    lines.append(f"范围 {len(per_mod)} 个模块 / {sum(len(v) for v in per_mod.values()):,} 值；"
                 f"逐值全文在 `entry/<module>.txt`")
    lines.append("")
    lines.append("| 模块 | 值数 |")
    lines.append("|---|---|")
    for m, v in sorted(per_mod.items(), key=lambda x: -len(x[1])):
        lines.append(f"| `{m}` | {len(v)} |")
    lines.append("")

    lines.append("## A. 数值常量（全部，按值排）")
    lines.append("")
    for mod, v in sorted(numbers, key=lambda x: x[1]):
        lines.append(f"- {v!r}  <- `{mod}`")
    lines.append("")

    lines.append("## B. 结构化对象（dict/list，原样）")
    lines.append("")
    seen = set()
    for mod, v in structs:
        key = json.dumps(v, ensure_ascii=False, sort_keys=True)[:200]
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"- `{mod}`: {json.dumps(v, ensure_ascii=False)[:600]}")
    lines.append("")

    lines.append("## C. 长文本（>=60 字符 = docstring / 话术 / 键串）")
    lines.append("")
    seen_s = set()
    for mod, v in long_text:
        if v in seen_s:
            continue
        seen_s.add(v)
        lines.append(f"- `{mod}`: {v[:900]}")
    lines.append("")

    OUT_VIEW.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("modules=%d values=%d numbers=%d structs=%d longtext=%d idents=%d"
          % (len(per_mod), sum(len(v) for v in per_mod.values()),
             len(numbers), len(structs), len(long_text), len(ident)))
    print("view lines=%d size=%d bytes" % (len(lines), OUT_VIEW.stat().st_size))
    return 0


if __name__ == "__main__":
    sys.exit(main())
