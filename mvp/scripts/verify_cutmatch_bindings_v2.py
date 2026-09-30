"""独立复核 cutmatch-analysis/FINDINGS/09 §8/§9 (增量部分) —— benchmark 侧只读字节 (2026-09-26).

09 在 02:14 更新: 新增 §8 (N10/N3 绑定 + 伪绑定陷阱) 与 §9 (接受我方质疑并重分级; 文法修订到 0x6e=隐式1元组).
本脚本**不采信文字**, 只做四件事:
  1. §8.1 / §8.2 表格逐项读字节 (名字在偏移处 + 零间隔 + 数值一致);
  2. §8.3 的"伪绑定陷阱"验证: 0x174bcbbb 附近是否真是 93 名表/值块交界;
  3. §9.3 的 _scene_range_fps: 枚举全部出现, 检查紧随元素是否**一律不是**数值;
  4. §9.4 的代码对象记录: 用修订文法(0x6e=隐式1元组)解 0x174db053, 看能否复现
     (qualname, [co_consts..., filename], co_varnames) 形状与 retrieval.py 的 0.45/0.55.
输出 work/verify_cutmatch_v2.json
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
SINGLE = {0x74: "True", 0x46: "False", 0x4e: "None", 0x70: "p"}
ROW = re.compile(r"^\|\s*\`([^\`]+)\`\s*\|\s*\*\*([^*|]+?)\*\*\s*\|\s*(0x[0-9a-fA-F]+)\s*\|")


def rd(d: bytes, off: int, implicit_tuple: bool = True):
    """容器文法(含 09 §9.4 修订: 0x6e = 隐式 1 元组). 返回 (kind, value, next_off)."""
    if off >= len(d):
        return None, None, off
    b = d[off]
    if b == 0x66 and off + 9 <= len(d):
        v, = struct.unpack_from("<d", d, off + 1)
        return "f", v, off + 9
    if b == 0x6c:
        j, sh, val = off + 1, 0, 0
        while j < len(d) and j - off < 12:
            c = d[j]
            val |= (c & 0x7F) << sh
            sh += 7
            j += 1
            if not (c & 0x80):
                break
        return "i", val, j
    if b in SINGLE:
        return "v", SINGLE[b], off + 1
    if b in (0x54, 0x6E) and implicit_tuple:      # T=n 元, n=隐式 1 元
        n = d[off + 1] if b == 0x54 else 1
        q, items = off + (2 if b == 0x54 else 1), []
        for _ in range(n):
            k, v, q2 = rd(d, q, implicit_tuple)
            if k is None:
                return None, None, off
            items.append(v)
            q = q2
        return ("T" if b == 0x54 else "n"), items, q
    z = d.find(b"\x00", off + 1)
    if z < 0 or z - off > 400:
        return None, None, off
    return "s", (chr(b), d[off + 1:z].decode("latin1")), z + 1


def main() -> int:
    doc = DOC.read_text(encoding="utf-8")
    data = BIN.read_bytes()
    out = {"sections": {}}

    # ---- 1) §8.1 / §8.2 表格 ----
    for sec, tag in (("8.1", "N10 边界精修 7 项"), ("8.2", "N3 部分完成")):
        blk = doc.split("### %s" % sec, 1)[1].split("###", 1)[0]
        rows = []
        for line in blk.splitlines():
            m = ROW.match(line.strip())
            if not m:
                continue
            name, claimed, off = m.group(1), m.group(2).strip(), int(m.group(3), 16)
            k, v, nxt = rd(data, off)
            name_ok = k == "s" and isinstance(v, tuple) and v[0] == "a" and v[1] == name
            gap0 = (nxt == off + 1 + len(name) + 1) if name_ok else None
            vk, vv, _ = rd(data, nxt) if name_ok else (None, None, None)
            val_ok = False
            if vk == "f":
                val_ok = abs(float(claimed) - vv) < 1e-9
            elif vk == "i":
                val_ok = int(float(claimed)) == vv
            rows.append({"name": name, "claimed": claimed, "off": hex(off), "name_ok": name_ok,
                         "next_kind": vk, "next_value": vv if isinstance(vv, (int, float)) else str(vv),
                         "value_ok": val_ok})
            print("[%s] %-58s 声称值=%-8s 名字=%s 紧随=%s %s %s" % (
                sec, name, claimed, name_ok, vk, vv, "OK" if val_ok else "!!"))
        out["sections"][tag] = rows

    # ---- 2) §8.3 伪绑定陷阱 ----
    trap = 0x174BCBBB
    chain = []
    p = trap - 0x120
    for _ in range(40):
        k, v, nxt = rd(data, p)
        if k is None or nxt <= p:
            p += 1
            continue
        chain.append((hex(p), k, v if isinstance(v, (int, float, str)) else "T"))
        p = nxt
    out["sections"]["trap_0x174bcbbb"] = chain
    print("\n#### 0x174bcbbb 邻域 40 元素(检查是否 93 名表→值块交界)")
    for c in chain:
        print("   %s %s %s" % c)

    # ---- 3) §9.3 _scene_range_fps ----
    occ, start = [], 0
    while True:
        i = data.find(b"_scene_range_fps", start)
        if i < 0:
            break
        s = i - 1
        tail = data[i + len("_scene_range_fps")]
        nxt = None
        if tail == 0:
            k, v, _ = rd(data, i + len("_scene_range_fps") + 1)
            nxt = (k, v if isinstance(v, (int, float, str)) else "T")
        occ.append({"off": hex(s), "kind": chr(data[s]), "next": str(nxt)})
        start = i + 1
    out["sections"]["_scene_range_fps"] = occ
    print("\n#### _scene_range_fps 出现 %d 次: %s" % (len(occ), occ))

    # ---- 4) §9.4 代码对象记录 ----
    recs = []
    p = 0x174DB053
    k, v, nxt = rd(data, p)
    recs.append({"off": hex(p), "kind": k, "value": str(v)[:400]})
    print("\n#### 0x174db053 解出: %s %s" % (k, str(v)[:300]))
    out["sections"]["code_object_0x174db053"] = recs

    # ---- 5) 三个"歧义"名字的连续数值串 ----
    amb = {}
    for nm in ("source_global_fps", "feature_image_size", "runtime_vision_vits14"):
        sites = []
        start = 0
        while True:
            i = data.find(nm.encode(), start)
            if i < 0:
                break
            if data[i + len(nm)] == 0:
                q = i + len(nm) + 1
                run = []
                while True:
                    k2, v2, q2 = rd(data, q)
                    if k2 in ("f", "i") and len(run) < 6:
                        run.append(v2)
                        q = q2
                        continue
                    break
                if run:
                    sites.append({"off": hex(i - 1), "numbers": run})
            start = i + 1
        amb[nm] = sites
    out["sections"]["ambiguous_runs"] = amb
    print("\n#### 连续数值串: %s" % json.dumps(amb, ensure_ascii=False))

    Path(BENCH / "work" / "verify_cutmatch_v2.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nsaved work/verify_cutmatch_v2.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
