# -*- coding: utf-8 -*-
"""独立复核 精修/展示层新确证键 (FINDINGS_DOCSTRING_BREAKTHROUGH) —— 只读 sidecar exe 字节 (2026-09-26 续10f).

按 DECISIONS 2026-09-26 纪律: 禁用「键名相邻字节」, 统一走 val_off 值解码 + 名表/值表排序一致性.
四类检查:
  A. 键名在 key_off 处 (Nuitka 字符串 = 首字节为首字符, NUL 结尾);
  B. val_off 处按容器文法解码 == profile 声称值 (0x66=f64, 0x6c=varint, 0x74=T, 0x46=F, 0x4e=None);
  C. 名表/值表排序一致性: 同 blob 内按 key_off 排序与按 val_off 排序的键序必须一致 (防错位配对);
  D. docstring 原文直接在 exe 二进制 grep (UTF-8, 绕开执行方 JSON).
输出 work/verify_refine_bindings.json
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BENCH = Path(__file__).resolve().parents[2]
PROFILE = Path(r"D:\claudework\cutmatch-analysis\data\competitor_profile_v1.json")
ADJ = Path(r"D:\claudework\cutmatch-analysis\data\adjacent_pairs.json")
BIN = Path(r"D:\claudework\cutmatch-analysis\extracted\app\PFiles\CutMatch\cutmatch-sidecar.exe")
OUT = BENCH / "work" / "verify_refine_bindings.json"

NEW_KEYS = [
    # P1 路径 DP / 连续偏移 (fast_timeline.options + pipeline.options + adjacent)
    "path_local_weight", "path_consistency_weight", "path_coarse_weight", "path_support_weight",
    "path_transition_grace_seconds", "path_transition_max_penalty", "path_backward_max_penalty",
    "recovery_neighbor_disagreement_seconds", "recovery_local_score_threshold",
    "continuity_tiebreak_bonus", "timeline_strictness",
    "local_window_margin_seconds", "propagated_local_window_margin_seconds",
    # P0 密集起点 / 精排半径 (fast)
    "frame_refine_radius_seconds", "path_refine_radius_seconds", "frame_refine_query_count",
    "actual_refine_query_count", "initial_refine_candidate_count", "actual_refine_min_score_gain",
    "actual_refine_score_threshold", "min_candidate_margin", "offset_bucket_seconds",
    "dense_sample_fps", "balanced_coarse_sample_fps",
    # ED 切分精修 / 边界守卫
    "boundary_backshift_enabled", "boundary_backshift_max_seconds",
    "source_boundary_guard_frames", "source_boundary_refine_max_shift",
    "commentary_scene_refine_enabled", "commentary_scene_candidate_snap_radius_frames",
    "commentary_scene_move_radius_frames", "commentary_scene_min_side_frames",
    "commentary_scene_max_additions_per_segment", "commentary_scene_prediction_support_radius",
    "commentary_scene_visual_score_min", "commentary_scene_visual_strong_score_min",
    "commentary_scene_visual_peak_ratio_min", "commentary_scene_structure_distance_min",
    "commentary_scene_structure_strong_distance", "commentary_scene_motion_ecc_similarity_max",
    "commentary_scene_motion_histogram_distance_max", "commentary_scene_flash_luminance_min",
    "commentary_scene_flash_luminance_jump_min", "commentary_scene_descriptor_width",
    "commentary_scene_descriptor_height", "commentary_scene_dual_single_min",
    "commentary_scene_dual_many_min", "commentary_scene_dual_combined_min",
    "offset_refine_dtw_start_window_max_points",
]

DOCSTRINGS = [
    "时间线镜头选路：使用动态规划按原候选顺序选择弱惩罚倒退的路径。",
    "时间线连续偏移：修正连续命中同一源镜头时重复使用起始帧的问题。",
    "时间线镜头转移评分：对源镜头索引或起点发生倒退施加固定惩罚。",
    "时间线逐帧转移评分：按实际帧差与期望帧差的偏离扣除连续性分数。",
    "修正快速模式开头串镜，并在尾部跨镜时优先使用同镜头画面。",
    "记录需要在剪映和 Premiere 时间线展开的真实转场切点。",
    "使用候选附近 10fps 网格和多帧首段证据寻找最佳源起点。",
    "把上一段最强候选按解说时间差平移，补入全局召回可能漏掉的位置。",
    "为每段解说联合全局与 patch top-k 召回原片候选，并应用长镜头局部提升后排序。",
    "只在源片段开头明显还是上一镜头尾帧时，才把入点向后校正。",
    "按内点三倍权重计算局部特征分数。",
    "按采样、偏移支持、局部一致性和候选差距给出稳定置信度结论。",
]


def decode_val(d: bytes, off: int):
    """Nuitka 常量文法(0x66=f64 / 0x6c=varint / 0x74=T / 0x46=F / 0x4e=None), 仿 verify_cutmatch_bindings_v2.rd."""
    if off >= len(d):
        return None, "oob"
    b = d[off]
    if b == 0x66 and off + 9 <= len(d):
        return struct.unpack_from("<d", d, off + 1)[0], "f"
    if b == 0x6C:
        j, sh, val = off + 1, 0, 0
        while j < len(d) and j - off < 12:
            c = d[j]
            val |= (c & 0x7F) << sh
            sh += 7
            j += 1
            if not (c & 0x80):
                break
        return val, "i"
    if b == 0x74:
        return True, "T"
    if b == 0x46:
        return False, "F"
    if b == 0x4E:
        return None, "N"
    return None, "unk:0x%02x" % b


def main() -> int:
    d = BIN.read_bytes()
    prof = json.loads(PROFILE.read_text(encoding="utf-8"))
    entries = {}  # key -> (section, rec)
    for section, node in prof.items():
        if not isinstance(node, dict):
            continue
        for k, v in node.items():
            if isinstance(v, dict) and "value" in v and "source" in v:
                entries[k] = (section, v)
    adj = json.loads(ADJ.read_text(encoding="utf-8"))

    results = {}
    for k in NEW_KEYS:
        rec = {}

        def name_at(off: int) -> str:
            """Nuitka 短 ASCII 串: 可能带 0x61('a')/0x75('u') 前缀标记字节, 名字其后至 NUL。"""
            for skip in (0, 1, 2):
                s = d[off + skip:].split(b"\x00", 1)[0].decode("latin1", "replace")
                if s == k:
                    return s
            return d[off:].split(b"\x00", 1)[0].decode("latin1", "replace")

        if k in entries:
            section, v = entries[k]
            src = v["source"]
            ko = int(src["key_off"], 16)
            vo = int(src["val_off"], 16)
            raw_ok = name_at(ko)
            name_ok = raw_ok == k
            val, kind = decode_val(d, vo)
            claimed = v["value"]
            if isinstance(claimed, dict) and "floatspecial" in claimed:
                claimed = claimed["floatspecial"]
            val_ok = (val == claimed) if kind in ("f", "i", "T", "F", "N") else False
            rec = {"section": section, "key_off": src["key_off"], "val_off": src["val_off"],
                   "name_at_offset": raw_ok, "name_ok": name_ok, "decoded": val, "kind": kind,
                   "claimed": claimed, "val_ok": bool(val_ok), "level": v.get("level")}
        elif k in adj:  # adjacent_pairs 键(无 profile 记录): name_off/val_off 成对
            pairs = adj[k]
            p0 = pairs[0]
            no = int(p0["name_off"], 16)
            vo = int(p0["val_off"], 16)
            name_at_ = name_at(no)
            val, kind = decode_val(d, vo)
            rec = {"section": "adjacent_pairs", "key_off": p0["name_off"], "val_off": p0["val_off"],
                   "name_at_offset": name_at_, "name_ok": name_at_ == k, "decoded": val, "kind": kind,
                   "claimed": p0.get("value"), "val_ok": str(val) == str(p0.get("value")),
                   "n_occurrences": len(pairs)}
        rec["verified"] = bool(rec.get("name_ok") and rec.get("val_ok"))
        results[k] = rec

    # C. 名表/值表排序一致性: 按 key_off 与 val_off 排序的键序须一致(同 blob 内)
    keyed = [(k, int(v["key_off"], 16), int(v["val_off"], 16))
             for k, v in results.items() if "key_off" in v and v.get("section") != "adjacent_pairs"]
    by_key = sorted(keyed, key=lambda x: x[1])
    by_val = sorted(keyed, key=lambda x: x[2])
    order_consistent = [k for k, _, _ in by_key] == [k for k, _, _ in by_val]
    # adjacent 键单独做同样的序检查
    adjk = [(k, int(json.loads(ADJ.read_text(encoding='utf-8'))[k][0]["name_off"], 16),
             int(json.loads(ADJ.read_text(encoding='utf-8'))[k][0]["val_off"], 16))
            for k in NEW_KEYS if k in adj]
    if adjk:
        order_consistent_adj = ([k for k, _, _ in sorted(adjk, key=lambda x: x[1])] ==
                                [k for k, _, _ in sorted(adjk, key=lambda x: x[2])])
    else:
        order_consistent_adj = None

    # D. docstring 二进制 grep (UTF-8)
    doc_hits = {}
    for s in DOCSTRINGS:
        doc_hits[s] = d.find(s.encode("utf-8"))

    out = {"binary": str(BIN), "size": len(d), "n_keys": len(results),
           "n_verified": sum(1 for v in results.values() if v.get("verified")),
           "failed": [k for k, v in results.items() if not v.get("verified")],
           "order_consistent_profile": order_consistent,
           "order_consistent_adjacent": order_consistent_adj,
           "docstring_hits": {s: ("FOUND@0x%x" % o if o >= 0 else "MISSING") for s, o in doc_hits.items()},
           "keys": results}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("键复核: %d/%d 通过; 失败=%s" % (out["n_verified"], out["n_keys"], out["failed"]))
    print("名表/值表排序一致 (profile 区): %s | (adjacent 区): %s" % (order_consistent, order_consistent_adj))
    print("docstring 二进制命中: %d/%d" % (sum(1 for v in doc_hits.values() if v >= 0), len(DOCSTRINGS)))
    for s, o in doc_hits.items():
        print("  %s %s" % ("OK " if o >= 0 else "MISS", s[:44]))
    print("saved %s" % OUT)
    return 0 if out["n_verified"] == out["n_keys"] and all(v >= 0 for v in doc_hits.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
