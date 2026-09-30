"""独立复核 cutmatch-analysis/data/competitor_profile_v1.json (v2) 的「键↔值」指针 —— benchmark 侧只读字节 (2026-09-26).

不采信文字, 只做三件事:
  1. 名字自证: 对每条 value/level/source, 在 source.key_off 处读字节, 必须解出标签 + 该条自身的键名(逐字符);
  2. 值自证: 在 source.val_off 处读 9 字节, 与 source.raw 逐字节比对, 再按容器文法解码, 与 value 比对;
  3. 配对序自证: 同一 blob 内, 按 key_off 升序的名次 与 按 val_off 升序的名次必须逐条一致
     (名表/值表同序 ⇒ 顺序映射成立), 否则列出所有序颠倒项。

另: 顺带解码 FINDINGS/09 早期「相邻配对」给出的 0x174e04c1(声称 0.1), 用于判定
    offset_refine_dtw_min_score 的 0.1/0.55 分歧是「值不同」还是「取到了邻键的值位」。

输出: work/verify_cutmatch_profile_pairing.json
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BENCH = Path(r"D:\claudework\benchmark")
PROFILE = Path(r"D:\claudework\cutmatch-analysis\data\competitor_profile_v1.json")
BIN = Path(r"D:\claudework\cutmatch-analysis\extracted\app\PFiles\CutMatch\cutmatch-sidecar.exe")

spec = importlib.util.spec_from_file_location("v2", str(BENCH / "mvp" / "scripts" / "verify_cutmatch_bindings_v2.py"))
v2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v2)
rd = v2.rd


def entries(o, path=""):
    if isinstance(o, dict):
        if "value" in o and "source" in o and isinstance(o["source"], dict):
            yield path, o
        for k, val in o.items():
            yield from entries(val, path + "/" + str(k))
    elif isinstance(o, list):
        for i, val in enumerate(o):
            yield from entries(val, path + "[%d]" % i)


def num_eq(a, b) -> bool:
    try:
        return abs(float(a) - float(b)) < 1e-9
    except (TypeError, ValueError):
        return str(a) == str(b)


def main() -> int:
    data = BIN.read_bytes()
    prof = json.loads(PROFILE.read_text(encoding="utf-8"))
    rows, bad_name, bad_raw, bad_val = [], [], [], []
    for path, e in entries(prof):
        src = e["source"]
        if "key_off" not in src or "val_off" not in src:
            continue
        key = path.rsplit("/", 1)[-1]
        ko, vo = int(src["key_off"], 16), int(src["val_off"], 16)
        k, kv, nxt = rd(data, ko)
        name_ok = (k == "s" and isinstance(kv, tuple) and kv[1] == key)
        raw = data[vo:vo + 9].hex(" ")
        raw_ok = ("raw" not in src) or (raw == src["raw"].strip())
        vk, vv, _ = rd(data, vo)
        # profile 的三类特殊编码(不是错误, 需按其自身约定判定):
        #   <<PREV>>              = 容器 0x70(p) 复用前一常量
        #   {'floatspecial': n}   = 0x5a(Z) 特殊浮点(nan/inf 类)
        #   字符串值               = 名表串, 解码为 (标签, 文本); 只比文本
        val = e["value"]
        if isinstance(val, dict) and "floatspecial" in val:
            val_ok = (vk == "s" and isinstance(vv, tuple) and vv[0] in ("Z", "z"))
        elif val == "<<PREV>>":
            val_ok = (vk == "v" and vv == "p")
        elif vk == "s" and isinstance(vv, tuple):
            val_ok = (vv[1] == str(val))
        else:
            val_ok = num_eq(val, vv) if vk in ("f", "i") else (str(val) == str(vv))
        row = {"path": path, "key": key, "blob": src.get("blob"), "key_off": src["key_off"],
               "val_off": src["val_off"], "value": e["value"], "level": e.get("level"),
               "name_at_key_off": (kv[1] if isinstance(kv, tuple) else str(kv)),
               "name_ok": bool(name_ok), "raw": raw, "raw_ok": bool(raw_ok),
               "decoded_kind": vk, "decoded": vv if isinstance(vv, (int, float, str)) else str(vv),
               "value_ok": bool(val_ok)}
        rows.append(row)
        if not name_ok:
            bad_name.append(row)
        if not raw_ok:
            bad_raw.append(row)
        if not val_ok:
            bad_val.append(row)

    inversion, per_blob = [], {}
    for blob in sorted({r["blob"] for r in rows}):
        sub = [r for r in rows if r["blob"] == blob]
        by_k = sorted(sub, key=lambda r: int(r["key_off"], 16))
        by_v = sorted(sub, key=lambda r: int(r["val_off"], 16))
        krank = {r["key"]: i for i, r in enumerate(by_k)}
        vrank = {r["key"]: i for i, r in enumerate(by_v)}
        inv = [r["key"] for r in by_k if krank[r["key"]] != vrank[r["key"]]]
        per_blob[blob] = {"n": len(sub), "inversions": len(inv), "examples": inv[:10],
                          "key_span": [by_k[0]["key_off"], by_k[-1]["key_off"]],
                          "val_span": [by_v[0]["val_off"], by_v[-1]["val_off"]]}
        inversion += [{"blob": blob, "key": k} for k in inv]

    print("profile 条目(带 key_off/val_off): %d" % len(rows))
    print("名字自证失败: %d | raw 字节不符: %d | 数值不符: %d" % (len(bad_name), len(bad_raw), len(bad_val)))
    print()
    print("| blob | 条目 | 名表区间 | 值表区间 | 序颠倒 |")
    print("|---|---|---|---|---|")
    for blob, s in per_blob.items():
        print("| %s | %d | %s..%s | %s..%s | %d |" % (blob, s["n"], s["key_span"][0], s["key_span"][1],
                                                       s["val_span"][0], s["val_span"][1], s["inversions"]))
    if inversion:
        print()
        print("序颠倒示例:", json.dumps(inversion[:20], ensure_ascii=False))

    print()
    print("=== 争议常量 ===")
    for r in rows:
        if r["key"] in ("offset_refine_dtw_min_score", "offset_refine_min_score",
                        "offset_refine_dtw_sample_interval_seconds", "offset_refine_dtw_max_samples"):
            print("  %-42s value=%-6s val_off=%s raw=%s 解出=%s(%s) 名字自证=%s 值自证=%s" % (
                r["key"], r["value"], r["val_off"], r["raw"], r["decoded"], r["decoded_kind"],
                r["name_ok"], r["value_ok"]))

    stale = 0x174E04C1
    sk, sv, _ = rd(data, stale)
    print()
    print("=== FINDINGS/09 早期相邻配对位 0x174e04c1 (声称 0.1) ===")
    print("  解出: kind=%s value=%r | 该位起 40 字节: %s" % (sk, sv, data[stale:stale + 40]))

    Path(BENCH / "work" / "verify_cutmatch_profile_pairing.json").write_text(json.dumps({
        "profile": str(PROFILE), "n_entries": len(rows),
        "bad_name": len(bad_name), "bad_raw": len(bad_raw), "bad_value": len(bad_val),
        "per_blob": per_blob, "inversions": inversion,
        "offset_refine_dtw_min_score_stale_0x174e04c1": {"kind": sk, "value": str(sv)},
        "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print()
    print("saved work/verify_cutmatch_profile_pairing.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())