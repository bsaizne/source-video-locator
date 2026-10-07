"""导出**计划层**四通道不变式常态守卫（2026-10-07 续63；纯 json、不跑管线、不碰 ffmpeg）。

对象 = 现役四片真实结果批（默认 ``work/stable_sort_regress/{case}.results.json``）。
四个产物出口（成片 / EDL / FCP7 XML / 剪映卷轴）各跑一遍生产同一序列
``exporters.prepare_channel_plan``，读它自带的体检量断言五条：

  ① 贴接重叠裁到 0        ``audit["adjacent_overlap_pairs"] == 0``
  ② 裁重复不丢画面        ``audit["union_coverage_s"] == audit_pre_trim[...]``（Δ=0）
  ③ 真实复用只报数        非贴接重叠（连续场景内切多镜头，档案目检确证多数正确）的
                          对数/秒数在挖洞后会下降——外层与第三段的共享区间让给了内层，
                          画面仍被覆盖（②已锁），所以不断言持平，只报 ``reuse_*_delta``。
  ④ 卷轴清单符合拼接规则  逐 clip 一条素材，**减去**被去重的「紧邻且源区间逐字节相同」条
                          （续63 补二；按同一规则重算后逐条比对，能抓多删/漏删/顺序错）
  ⑤ 四通道同源            无取材扩宽时三时间线通道 plan 逐字段相同（差异只允许是参数）

另外报**抽取量**（剪映通道逐 clip 的代价，2026-10-07 立项时只定性说"抽取次数上升"）：
逐 clip 素材条数与 Σ 抽取宽度，对旧"重叠回并"腿同口径并报——宽度总量 = 解码秒的代理量。

Run:
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/check_export_plan_invariants.py
  # 只看计划层不取索引（扩宽腿自动跳过）：--no-index
  # 换结果批：--pattern "work/rerun_{case}.results.json"
退出码 0=五条全绿，1=有违反 ⇒ 可挂 accept / 出包前门槛。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

BENCH = Path(r"D:\claudework\benchmark")
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE", (r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages"
                                        r"\static_ffmpeg\bin\win32\ffprobe.exe"))
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from app.exporters import (prepare_channel_plan, plan_jianying_assets,  # noqa: E402
                           CHANNELS)
from infrastructure.config import load_config  # noqa: E402
from infrastructure.results_repo import load_results  # noqa: E402

CASES = ("2mkv", "test1", "test2", "test3")
DEFAULT_PATTERN = "work/stable_sort_regress/{case}.results.json"


def old_collapse_assets(plan):
    """逐字节复刻 2026-10-07 之前的剪映"重叠回并"（只看源区间，不问贴接）——
    留作代价与覆盖的对照臂，不是现役语义。"""
    clips = sorted((c for c in plan if c.kind in ("main", "low")),
                   key=lambda x: (x.edited_start, x.edited_end))
    assets, cur = [], None
    for c in clips:
        if cur is not None and c.orig_start < cur[1] - 1e-6:
            cur[1] = max(cur[1], c.orig_end)
            continue
        cur = [c.orig_start, c.orig_end]
        assets.append(cur)
    return assets


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pattern", default=DEFAULT_PATTERN)
    ap.add_argument("--cases", default=",".join(CASES))
    ap.add_argument("--no-index", action="store_true",
                    help="不取 scenes.npy（取材扩宽腿自动跳过，结论更保守）")
    ap.add_argument("--fps", type=float, default=25.0,
                    help="单帧守卫用名义帧长（成片通道生产口径=25）")
    ap.add_argument("--out", default="work/export_plan_invariants/report.json")
    args = ap.parse_args()

    cfg = load_config()
    xcfg = cfg.export
    store = None
    if not args.no_index:
        try:
            from engine.feature_store import FeatureStore
            from infrastructure import paths
            from media.ffmpeg import FFmpegIO
            store = FeatureStore(FFmpegIO(), paths.index_root(),
                                 sampling_fps=float(cfg.pipeline.index_sampling_fps))
        except Exception as e:                              # noqa: BLE001
            print(f"[warn] 索引层构造失败，退化为无索引腿：{type(e).__name__}: {e}")
            store = None

    rows, violations = [], []
    for case in [c for c in args.cases.split(",") if c]:
        res_p = BENCH / args.pattern.format(case=case)
        if not res_p.exists():
            print(f"[skip] {case}: 结果批不存在 {res_p}")
            continue
        batch = load_results(res_p)
        scenes, orig_duration, have_index = None, None, False
        if store is not None and batch.original_video:
            try:
                bundle = store.load_index(Path(batch.original_video))
                scenes = bundle.scenes
                orig_duration = float(bundle.meta.duration or 0.0) or None
                have_index = scenes is not None
            except Exception as e:                          # noqa: BLE001
                print(f"[warn] {case}: 索引不可用（{type(e).__name__}: {e}），"
                      f"扩宽腿跳过——覆盖结论按保守口径读")
        row = {"case": case, "results": str(res_p.relative_to(BENCH)).replace("\\", "/"),
               "index": have_index, "channels": {}}
        plans = {}
        for ch in CHANNELS:
            plan, st = prepare_channel_plan(
                batch, channel=ch, min_confidence=xcfg.min_confidence,
                low_policy=xcfg.low_policy, scenes=scenes, orig_duration=orig_duration,
                fps=args.fps, snap_scenes=bool(xcfg.snap_scenes),
                snap_tolerance_s=float(xcfg.snap_tolerance_s),
                boundary_split_enabled=bool(xcfg.boundary_split_enabled),
                boundary_min_piece_s=float(xcfg.boundary_min_piece_s),
                material_expand=(ch == "jianying" and bool(xcfg.material_expand)),
                min_clip_s=float(xcfg.min_clip_s))
            plans[ch] = plan
            pre, post = st["audit_pre_trim"], st["audit"]
            checks = {
                "adjacent_overlap_zero": post["adjacent_overlap_pairs"] == 0,
                "coverage_delta_zero": abs(post["union_coverage_s"]
                                           - pre["union_coverage_s"]) < 0.005,
            }
            # 「真实复用不动」**不做硬断言**（只报数）：外层被挖洞时，它与第三段的共享区间
            # 让给内层clip——复用对数会下降，但那段画面仍被内层覆盖（②已锁覆盖不变）。
            # 断言它持平会把正确的去重判成违反（2026-10-07 有索引腿实测 2mkv/test3 触发）。
            row["channels"][ch] = {
                "n_trim": st["n_trim"], "n_split": st["n_split"],
                "n_expanded": st["n_expanded"], "warnings": len(st["warnings"]),
                "pre": pre, "post": post, "checks": checks,
                "reuse_pairs_delta": post["reuse_pairs"] - pre["reuse_pairs"],
                "reuse_dup_delta": round(post["reuse_dup_s"] - pre["reuse_dup_s"], 3),
            }
            if ch == "jianying":
                assets = plan_jianying_assets(plan)
                collapsed = old_collapse_assets(plan)
                # ④ 卷轴清单必须等于「逐 clip 一条素材，减去被去重的紧邻同素材」——
                # 直接按同一规则重算一遍逐条比对（比数个数强：能抓到多删/漏删/顺序错）。
                expected: list[tuple[float, float]] = []
                for c in sorted((x for x in plan if x.kind in ("main", "low")),
                                key=lambda x: (x.edited_start, x.edited_end)):
                    if expected and expected[-1] == (c.orig_start, c.orig_end):
                        continue   # 紧邻同素材连放 = 纯重复（续63 补二去重）
                    expected.append((c.orig_start, c.orig_end))
                checks["assets_match_scroll_rule"] = (
                    [(a.orig_start, a.orig_end) for a in assets] == expected)
                # 真实抽取代价 = **去重后的区间**：抽取循环按 ``clips/<stem>.mp4`` 是否存在
                # 复用文件，而 stem 由秒级取整的源区间决定 ⇒ 逐 clip 条数不等于抽取次数。
                uniq: dict[tuple[int, int], float] = {}
                for a in assets:
                    key = (int(round(a.orig_start)), int(round(a.orig_end)))
                    uniq[key] = max(uniq.get(key, 0.0), a.orig_width)
                row["jianying_cost"] = {
                    "new_assets": len(assets),
                    "new_extract_calls": len(uniq),
                    "new_extract_s": round(sum(uniq.values()), 2),
                    "new_asset_width_s": round(sum(a.orig_width for a in assets), 2),
                    "old_collapse_assets": len(collapsed),
                    "old_collapse_extract_s": round(sum(e - s for s, e in collapsed), 2),
                    "old_collapse_coverage_s": round(sum(e - s for s, e in collapsed), 2),
                }
            for name, ok in checks.items():
                if not ok:
                    violations.append(f"{case}/{ch}:{name}")
        # ⑤ 同源：无扩宽的三通道 plan 必须逐字段一致（剪映扩宽则单独比 core 腿）
        sig = {ch: [(c.kind, c.edited_start, c.edited_end, c.orig_start, c.orig_end)
                    for c in plans[ch]] for ch in ("movie", "edl", "fcp7_xml")}
        same = len({tuple(v) for v in sig.values()}) == 1
        row["timeline_channels_identical"] = same
        if not same:
            violations.append(f"{case}:timeline_channels_differ")

        edl_pre = row["channels"]["edl"]["pre"]
        jy = row["channels"]["jianying"]
        print(f"\n[{case}] 索引={'有' if have_index else '无'}  "
              f"clip={row['channels']['edl']['post']['n_clips']}  "
              f"贴接对={edl_pre['adjacent_pairs']}  "
              f"裁前重复={edl_pre['adjacent_overlap_pairs']}对/{edl_pre['adjacent_dup_s']}s "
              f"→ 裁后={row['channels']['edl']['post']['adjacent_overlap_pairs']}对 "
              f"覆盖 {edl_pre['union_coverage_s']}→{row['channels']['edl']['post']['union_coverage_s']}s "
              f"真实复用={row['channels']['edl']['post']['reuse_pairs']}对 "
              f"三通道同plan={'是' if same else '否'}")
        cost = row.get("jianying_cost") or {}
        print(f"        剪映：扩宽={jy['n_expanded']} 素材={cost.get('new_assets')}条 "
              f"卷轴覆盖={jy['post']['union_coverage_s']}s | 抽取={cost.get('new_extract_calls')}"
              f"次/{cost.get('new_extract_s')}s（素材宽度合计 {cost.get('new_asset_width_s')}s）"
              f"| 旧回并腿={cost.get('old_collapse_assets')}条/"
              f"{cost.get('old_collapse_extract_s')}s（覆盖仅这些，其余被吞）")
        rows.append(row)

    out = BENCH / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"pattern": args.pattern, "fps": args.fps,
                               "violations": violations, "rows": rows},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n留证 = {out.relative_to(BENCH)}")
    if violations:
        print(f"FAILED={len(violations)} 违反项：{violations}")
        return 1
    print(f"FAILED=0（{len(rows)} 片 × {len(CHANNELS)} 通道五条不变式全绿）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
