"""竞品常量库前缀穷举清点（2026-10-06）：模块族 x 常量数矩阵 + 已挖/未挖对账 + 未挖族里的算法相关键摘录。

只读 D:/claudework/cutmatch-analysis/data（Nuitka 常量 blob 静态转储），不运行竞品、不碰授权/受保护模型。
输出：work/cm_redig/inventory_20261006.md + inventory_20261006.json

Run: D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/analyze_cm_blob_inventory.py
输入（竞品静态转储 `D:/claudework/cutmatch-analysis/data`）与输出（`work/`）都在仓库外或被
gitignore —— 本脚本是复现入口；结论档 =
`mvp/benchmark/user_case/competitor_cutmatch/FINDINGS_CUTMATCH_ENTRY_LAYER_20261006.md`。
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

DATA = Path(r"D:\claudework\cutmatch-analysis\data")
REDIG = Path(r"D:\claudework\benchmark\work\cm_redig")
OUT_MD = REDIG / "inventory_20261006.md"
OUT_JSON = REDIG / "inventory_20261006.json"

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 续37 已挖范围（dump_blobs.py 的 KEEP 前缀）
MINED_PREFIXES = ("cutmatch.matching", "cutmatch.exporting.segments", "cutmatch.exporting.timing")

# 算法相关性关键词（时间对位 / 打分 / 门控 / 采样 / 合并 / 边界）
ALGO_KEYS = (
    "score", "match", "align", "offset", "window", "thresh", "confid", "dedup",
    "coverage", "merge", "boundar", "scene", "sampl", "frame", "feature", "embed",
    "cosine", "sim", "rank", "candidate", "anchor", "cluster", "dtw", "path",
    "refine", "vote", "penalt", "toler", "duration", "fps", "patch", "grid",
    "query", "peak", "gap", "split", "snap", "dup", "ambig",
)

IDENT = re.compile(r"^[a-z][a-z0-9_]{3,}$")


def classify(v):
    if isinstance(v, bool) or v is None:
        return "const"
    if isinstance(v, (int, float)):
        return "number"
    if isinstance(v, str):
        return "string"
    if isinstance(v, list):
        return "array"
    if isinstance(v, dict):
        return "object"
    return "other"


def main():
    blobs = json.loads((DATA / "nuitka_blobs.json").read_text(encoding="utf-8"))
    idx_lines = [l.strip() for l in (DATA / "nuitka_blob_index.txt").read_text(
        encoding="utf-8-sig").splitlines() if l.startswith("@")]
    mods = {}
    for l in idx_lines:
        m = re.match(r"@0x([0-9a-f]+) count=\s*(\d+) module=(\S+)", l)
        if m:
            mods[int(m.group(1), 16)] = m.group(3)

    per_mod = defaultdict(lambda: {"blobs": 0, "values": 0, "types": defaultdict(int),
                                   "strings": []})
    unmatched_blobs = 0
    for b in blobs:
        mod = mods.get(b["start"])
        if mod is None:
            unmatched_blobs += 1
            mod = "?unmapped"
        e = per_mod[mod]
        e["blobs"] += 1
        for v in b.get("values", []):
            e["values"] += 1
            t = classify(v)
            e["types"][t] += 1
            if t == "string":
                e["strings"].append(v)

    mined = {m: e for m, e in per_mod.items() if m.startswith(MINED_PREFIXES)}
    unmined_fc = {m: e for m, e in per_mod.items()
                  if not m.startswith(MINED_PREFIXES) and m.startswith("cutmatch.")}
    thirdparty = {m: e for m, e in per_mod.items()
                  if not m.startswith("cutmatch.") and m != "?unmapped"}

    def total(d):
        return sum(e["values"] for e in d.values())

    fam = defaultdict(lambda: {"modules": 0, "values": 0, "mined": False})
    for m, e in per_mod.items():
        f = ".".join(m.split(".")[:2])
        fam[f]["modules"] += 1
        fam[f]["values"] += e["values"]
        if m.startswith(MINED_PREFIXES):
            fam[f]["mined"] = True

    # 未挖第一方族里的算法相关标识符摘录
    cand = defaultdict(lambda: {"n": 0, "mods": set()})
    for m, e in unmined_fc.items():
        for s in e["strings"]:
            s2 = s.strip()
            low = s2.lower()
            if not (IDENT.match(s2) or ("_" in s2 and len(s2) < 48)):
                continue
            if any(k in low for k in ALGO_KEYS) and len(s2) >= 5:
                cand[s2]["n"] += 1
                cand[s2]["mods"].add(m)

    lines = []
    lines.append("# 竞品常量库前缀穷举清点（2026-10-06）")
    lines.append("")
    lines.append(f"- 数据源 = `nuitka_blobs.json` {len(blobs)} blob / "
                 f"{sum(len(b.get('values', [])) for b in blobs):,} 值；"
                 f"index 侧 {len(idx_lines)} 行 / {len(mods)} 个已归属模块；"
                 f"blob 未归属 index = {unmatched_blobs}")
    lines.append(f"- 续37 已挖范围 = `{MINED_PREFIXES[0]}` / "
                 f"`{MINED_PREFIXES[1]}` / `{MINED_PREFIXES[2]}`")
    lines.append("")
    lines.append("## 1. 总账：已挖 vs 未挖 vs 三方")
    lines.append("")
    lines.append("| 桶 | 模块数 | 常量数 | 占比 |")
    lines.append("|---|---|---|---|")
    allv = total(per_mod) or 1
    unmapped = {m: e for m, e in per_mod.items() if m == "?unmapped"}
    for name, d in (("续37 已挖", mined), ("未挖的第一方 cutmatch.*", unmined_fc),
                    ("三方库（噪声面）", thirdparty), ("blob 未归属 index", unmapped)):
        pct = 100.0 * total(d) / allv
        lines.append(f"| {name} | {len(d)} | {total(d):,} | {pct:.1f}% |")
    lines.append(f"| 合计 | {len(per_mod)} | {total(per_mod):,} | 100% |")
    lines.append("")
    lines.append("## 2. 模块族矩阵（前两段）")
    lines.append("")
    lines.append("| 族 | 模块数 | 常量数 | 续37 是否触及 |")
    lines.append("|---|---|---|---|")
    for f, e in sorted(fam.items(), key=lambda x: -x[1]["values"]):
        if e["values"] < 40:
            continue
        lines.append(f"| `{f}` | {e['modules']} | {e['values']:,} | "
                     f"{'部分/全部' if e['mined'] else 'NO'} |")
    lines.append("")
    lines.append("## 3. 未挖的第一方模块（按常量数排）")
    lines.append("")
    lines.append("| 模块 | 常量 | string | number | array | object |")
    lines.append("|---|---|---|---|---|---|")
    for m, e in sorted(unmined_fc.items(), key=lambda x: -x[1]["values"]):
        t = e["types"]
        lines.append(f"| `{m}` | {e['values']:,} | {t.get('string', 0):,} | "
                     f"{t.get('number', 0):,} | {t.get('array', 0):,} | {t.get('object', 0):,} |")
    lines.append("")
    lines.append("## 4. 未挖族里的算法相关标识符（候选新键）")
    lines.append("")
    lines.append("| 标识符 | 出现 | 所在模块（截 3 个） |")
    lines.append("|---|---|---|")
    ranked = sorted(cand.items(), key=lambda x: (-len(x[1]["mods"]), -x[1]["n"]))
    for k, v in ranked[:120]:
        ms = ", ".join(sorted(v["mods"])[:3])
        lines.append(f"| `{k}` | {v['n']} | {ms} |")
    lines.append("")
    lines.append(f"（命中候选键 {len(cand)} 个，仅列前 120；完整在 "
                 f"`inventory_20261006.json`）")

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    OUT_JSON.write_text(json.dumps({
        "totals": {"mined": total(mined), "unmined_first_party": total(unmined_fc),
                    "third_party": total(thirdparty), "all": total(per_mod)},
        "modules": {m: {"values": e["values"], "blobs": e["blobs"], "types": dict(e["types"])}
                    for m, e in sorted(per_mod.items())},
        "candidate_keys": {k: {"n": v["n"], "mods": sorted(v["mods"])}
                           for k, v in sorted(cand.items(), key=lambda x: -x[1]["n"])}},
        ensure_ascii=False, indent=1), encoding="utf-8")

    print("mined_values=%d unmined_first_party=%d third_party=%d candidate_keys=%d"
          % (total(mined), total(unmined_fc), total(thirdparty), len(cand)))
    print("wrote:", OUT_MD)
    return 0


if __name__ == "__main__":
    sys.exit(main())
