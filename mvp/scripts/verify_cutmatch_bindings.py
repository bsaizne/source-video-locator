"""独立复核 cutmatch-analysis/FINDINGS/09 的 26 项常量绑定 (2026-09-26, benchmark 侧只读).

动机: 09 的表格由对方脚本产出, benchmark 侧**从未自己碰过字节**。本轮不采信文字, 只做三件事:
  1. 直接从 09_CONSTANT_BINDING.md 的表格正则抽 (name, value, name_off, val_off), 避免转录误差;
  2. 在 cutmatch-sidecar.exe 上**逐项读字节**: 名字串是否真在该偏移、其后是否零间隔紧跟数值、数值是否等于表里写的值;
  3. 布局判别(决定"相邻=配对"是否可信): 解出 [名字前一个元素] / [名字后一个元素] / [数值后一个元素],
     看是否为 name→value→name 交替(强) 还是 name→value→value(弱=可能只是名字表+数值表硬排);
     并在同一区段统计 "s(attr) 后紧跟数值" 的**基线比例**(若接近 100%, 相邻本身不构成证据)。

输出: 控制台表格 + work/verify_cutmatch_bindings.json
不修改对方项目任何文件; 不修改我方 runtime.
"""
from __future__ import annotations

import json
import re
import struct
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]
DOC = Path(r"D:\claudework\cutmatch-analysis\FINDINGS\09_CONSTANT_BINDING.md")
BIN = Path(r"D:\claudework\cutmatch-analysis\extracted\app\PFiles\CutMatch\cutmatch-sidecar.exe")
JSON_BIND = Path(r"D:\claudework\cutmatch-analysis\data\dict_bindings.json")
SINGLE = {0x74: "True", 0x46: "False", 0x4e: "None", 0x70: "p"}
ROW = re.compile(r"^\|\s*\`([^\`]+)\`\s*\|\s*\*\*([^*|]+?)\*\*(?:（[^|]*）)?\s*\|\s*(0x[0-9a-fA-F]+)\s*\|\s*(0x[0-9a-fA-F]+)\s*\|")


def rd(data: bytes, off: int):
    """按 09 §1 的容器文法解一个元素, 返回 (kind, value, next_off)."""
    if off >= len(data):
        return None, None, off
    b = data[off]
    if b == 0x66 and off + 9 <= len(data):
        v, = struct.unpack_from("<d", data, off + 1)
        return "f", v, off + 9
    if b == 0x6c:
        j, sh, val = off + 1, 0, 0
        while j < len(data) and j - off < 12:
            c = data[j]
            val |= (c & 0x7F) << sh
            sh += 7
            j += 1
            if not (c & 0x80):
                break
        return "i", val, j
    if b in SINGLE:
        return "v", SINGLE[b], off + 1
    if b == 0x54:
        n = data[off + 1]
        q, items = off + 2, []
        for _ in range(n):
            k, v, q2 = rd(data, q)
            if k is None:
                return None, None, off
            items.append(v)
            q = q2
        return "T", items, q
    z = data.find(b"\x00", off + 1)
    if z < 0 or z - off > 400:
        return None, None, off
    return "s", (chr(b), data[off + 1:z].decode("latin1")), z + 1


def main() -> int:
    doc = DOC.read_text(encoding="utf-8")
    rows = []
    for line in doc.splitlines():
        m = ROW.match(line.strip())
        if m:
            name, val, noff, voff = m.group(1), m.group(2).strip(), int(m.group(3), 16), int(m.group(4), 16)
            if not name.startswith(("local_sample_fps",)):  # 保留全部, 下面再分级
                rows.append({"name": name, "claimed": val, "name_off": noff, "val_off": voff})
    print("从 09 文档表格抽到 %d 行绑定" % len(rows))

    data = BIN.read_bytes()
    print("sidecar 尺寸 %d 字节" % len(data))

    # 对照对方的结构化产物
    jb = json.loads(JSON_BIND.read_text(encoding="utf-8")) if JSON_BIND.exists() else {}
    jb_map = {}
    for k, v in jb.items():
        if isinstance(v, list) and v:
            e = v[0]
            jb_map[k] = (str(e.get("name_off")), str(e.get("val_off")), str(e.get("value")))

    out, n_name_ok, n_gap0, n_val_ok, layout = [], 0, 0, 0, {}
    for r in rows:
        k, v, nxt = rd(data, r["name_off"])
        name_ok = (k == "s" and isinstance(v, tuple) and v[0] == "a" and v[1] == r["name"])
        # 名字串结束后的下一个元素偏移
        after_name = nxt if name_ok else None
        gap0 = (after_name == r["val_off"])
        vk, vv, vnext = rd(data, r["val_off"])
        val_ok = False
        if vk == "f":
            try:
                val_ok = abs(float(r["claimed"]) - vv) < 1e-9
            except ValueError:
                val_ok = False
        elif vk == "i":
            try:
                val_ok = (int(float(r["claimed"])) == vv)
            except ValueError:
                val_ok = False
        # 布局: 数值后的下一个元素
        nk, nv, _ = rd(data, vnext) if vk else (None, None, None)
        pat = "%s->%s->%s" % (k or "?", vk or "?", nk or "?")
        if nk == "s" and isinstance(nv, tuple) and nv[0] == "a":
            layout_pat = "name->value->name(交替)"
        elif nk in ("f", "i"):
            layout_pat = "name->value->value(弱: 可能是名字表+数值表)"
        else:
            layout_pat = "name->value->%s" % (nk,)
        layout[layout_pat] = layout.get(layout_pat, 0) + 1
        n_name_ok += name_ok
        n_gap0 += bool(gap0)
        n_val_ok += val_ok
        jk = jb_map.get(r["name"])
        it = {"name": r["name"], "claimed": r["claimed"], "name_off": r["name_off"], "val_off": r["val_off"],
              "name_found": name_ok, "zero_gap": gap0, "value_matches": val_ok,
              "decoded_kind": vk, "decoded": (vv if isinstance(vv, (int, float, str)) else "list"),
              "pattern": pat, "layout": layout_pat,
              "in_dict_bindings_json": (jk[0] == hex(r["name_off"]) and jk[1] == hex(r["val_off"])) if jk else None}
        out.append(it)
        flag = "OK " if (name_ok and gap0 and val_ok) else "!! "
        print("%s%-46s 表值=%-8s 名字=%s 零间隔=%s 数值符=%s  %s" % (
            flag, r["name"], r["claimed"], name_ok, gap0, val_ok, layout_pat))

    print("\n汇总: 名字命中 %d/%d, 零间隔 %d/%d, 数值匹配 %d/%d" % (
        n_name_ok, len(rows), n_gap0, len(rows), n_val_ok, len(rows)))
    print("布局分布: %s" % layout)

    # 基线比例: 在同一区段(选项名常量流)里, 属性名字符串后紧跟数值的比例
    lo, hi = 0x174b0000, 0x17500000
    p, pairs, attrs = lo, 0, 0
    while p < hi:
        k, v, nxt = rd(data, p)
        if k is None or nxt <= p:
            p += 1
            continue
        if k == "s" and isinstance(v, tuple) and v[0] == "a":
            attrs += 1
            nk, _, _ = rd(data, nxt)
            if nk in ("f", "i"):
                pairs += 1
        p = nxt
    print("区段 [%#x,%#x): 属性名 %d 个, 其中后紧跟数值 %d (%.1f%%)" % (
        lo, hi, attrs, pairs, 100.0 * pairs / max(1, attrs)))

    # ---- 第二相: 绑定签名统计(区分"选项默认值"与"校验器字面量") ----
    sites = {}
    p = lo
    while p < hi:
        k, v, nxt = rd(data, p)
        if k is None or nxt <= p:
            p += 1
            continue
        if k == "s" and isinstance(v, tuple) and v[0] == "a":
            nk, _, _ = rd(data, nxt)
            sites.setdefault(v[1], []).append((p, nk))
        p = nxt
    multi, num_only_1, num_any = 0, 0, 0
    sig = {"schema+default(>=1 数值落点 且 出现>=2 次)": 0,
           "仅数值落点(出现 1 次)": 0, "无数值落点": 0, "多个数值落点": 0}
    for nm, lst in sites.items():
        nums = [s for s in lst if s[1] in ("f", "i")]
        if not nums:
            sig["无数值落点"] += 1
            continue
        num_any += 1
        if len(nums) > 1:
            sig["多个数值落点"] += 1
        elif len(lst) >= 2:
            sig["schema+default(>=1 数值落点 且 出现>=2 次)"] += 1
        else:
            sig["仅数值落点(出现 1 次)"] += 1
    print("\n绑定签名统计(区段内 %d 个不同属性名):" % len(sites))
    for k2, v2 in sig.items():
        print("   %-44s %d" % (k2, v2))
    print("   -> 有数值落点的名字 %d 个; 其中 %d 个同时出现在别处(定义位)" % (
        num_any, sig["schema+default(>=1 数值落点 且 出现>=2 次)"]))
    # 09 表里的 26 项各自属于哪一类
    for it in out:
        lst = sites.get(it["name"], [])
        nums = [s for s in lst if s[1] in ("f", "i")]
        it["total_sites"] = len(lst)
        it["numeric_sites"] = [(hex(x), k2) for x, k2 in nums]
        it["signature"] = ("多个数值落点" if len(nums) > 1 else
                           ("schema+default" if len(lst) >= 2 else "仅数值落点"))

    Path(BENCH / "work" / "verify_cutmatch_bindings.json").write_text(
        json.dumps({"doc_rows": len(rows), "name_ok": n_name_ok, "zero_gap": n_gap0, "value_ok": n_val_ok,
                    "layout": layout, "region_attr_names": attrs, "region_name_num_pairs": pairs,
                    "signature": sig, "signature_counts": {"attr_names": len(sites), "with_numeric": num_any},
                    "bindings": out}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved work/verify_cutmatch_bindings.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
