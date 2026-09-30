# -*- coding: utf-8 -*-
"""把我方历史上所有「相邻配对」绑定(values from adjacency)与对方 profile v2 的 val_off 值逐条对账。

背景: ordered_search_max_seconds 我方旧绑定 7200(相邻读法) vs profile/字节 1800 —— 已知第 3 例相邻陷阱。
本脚本系统排查是否还有其它错误绑定。输出 work/binding_reconciliation.json
"""
import json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
B = Path(r"D:\claudework\benchmark")
PROF = json.load(open(r"D:\claudework\cutmatch-analysis\data\competitor_profile_v1.json", encoding="utf-8"))

def entries(o, path=""):
    if isinstance(o, dict):
        if "value" in o and "source" in o and isinstance(o["source"], dict):
            yield path, o
        for k, v in o.items():
            yield from entries(v, path + "/" + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from entries(v, path + "[%d]" % i)

prof = {}
_raw = []
for path, e in entries(PROF):
    nm = path.rsplit("/", 1)[-1]
    rec = {"path": path, "value": e["value"], "level": e.get("level"), "source": e.get("source")}
    prof.setdefault(nm, []).append(rec)
    if isinstance(e.get("source"), dict) and "val_off" in e["source"]:
        _raw.append({"name": nm, "path": path, "blob": e["source"].get("blob"),
                     "val_off": int(e["source"]["val_off"], 16), "value": e["value"]})

# 解析 <<PREV>> 哨兵: 取同 blob 内 val_off 排序上的前一条的值(容器复用语义)
for r in _raw:
    if r["value"] == "<<PREV>>":
        prev = [x for x in _raw if x["blob"] == r["blob"] and x["val_off"] < r["val_off"]]
        prev.sort(key=lambda x: x["val_off"])
        src = prev[-1] if prev else None
        r["value"] = src["value"] if src else "<<UNRESOLVED>>"
        r["prev_of"] = src["name"] if src else None
        for c in prof.get(r["name"], []):
            if c["path"] == r["path"]:
                c["value"] = r["value"]
                c["resolved_prev_of"] = r.get("prev_of")

ours = []
for fn, key in (("verify_cutmatch_v2.json", "sections"), ("verify_cutmatch_bindings.json", "sections")):
    p = B / "work" / fn
    if not p.exists():
        continue
    d = json.loads(p.read_text(encoding="utf-8"))
    for sec, rows in d.get(key, {}).items():
        if not isinstance(rows, list):
            continue
        for r in rows:
            if isinstance(r, dict) and "name" in r and "claimed" in r:
                ours.append({"src": fn, "section": sec, "name": r["name"], "claimed": str(r["claimed"]).strip(),
                             "off": r.get("off") or r.get("name_off")})

def num(s):
    try:
        return float(str(s).split()[0].replace(",", ""))
    except Exception:
        return None

print("我方历史绑定行数:", len(ours), "| profile 条目名数:", len(prof))
print()
print("| 名字 | 我方(相邻读法) | profile v2(值表配对) | 判定 |")
print("|---|---|---|---|")
mismatch, unknown, agree = [], [], 0
for r in ours:
    cands = prof.get(r["name"])
    if not cands:
        unknown.append(r)
        continue
    pv = cands[0]["value"]
    a, b = num(r["claimed"]), num(pv)
    ok = (a is not None and b is not None and abs(a - b) < 1e-9) or (str(r["claimed"]) == str(pv))
    if ok:
        agree += 1
    else:
        mismatch.append((r, cands[0]))
        print("| %s | %s | %s | **不一致** |" % (r["name"], r["claimed"], pv))
print()
print("一致 %d 条 | 不一致 %d 条 | profile 中查无此名 %d 条" % (agree, len(mismatch), len(unknown)))
if unknown:
    print("查无此名(多为函数/局部名, 非选项键):", [u["name"] for u in unknown][:20])
out = {"agree": agree, "mismatch": len(mismatch), "unknown": len(unknown),
       "mismatches": [{"name": r["name"], "ours_adjacency": r["claimed"], "profile_value": c["value"],
                       "section": r["section"], "src": r["src"], "profile_path": c["path"]} for r, c in mismatch]}
(B / "work" / "binding_reconciliation.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("saved work/binding_reconciliation.json")