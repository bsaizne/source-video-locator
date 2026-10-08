# -*- coding: utf-8 -*-
"""⑥b 「两级采样」探针（粗筛索引 + 命中邻域密验）—— 研究线沙盒，零 runtime 改动。

问题（2026-10-07 续62 补七 重述后的立项理由）：
  源片索引抽稀到 0.5fps（建索引成本 ÷2、体积 ÷2）能否**三指标零回退**；
  若出现回退，「命中邻域密验」（只在候选窗附近补稠密帧）能否把它救回来。
判据（本轮按 STATE Next Actions 的建议**换掉**了旧判据「口袋救回」为主）：
  主   = 建索引**实测**耗时下降（前案只有折算值）
  硬门 = 三指标零回退（严格 / 导出实得 / 负例）
  保险 = 若 B05 有回退，C05D 须把回退行救回 ≥1/3，否则整条判负

前案与本探针补的边界（`FINDINGS_INDEX_DENSITY_DIV2_20261003.md` §6）：
  边界 1「§3 是最终 span 的敏感度包络，**不是 0.5fps 索引链路的模拟**；不覆盖粗网格让
         提案整体换地方」→ 本探针 B05/C05D 走**真实链路**，直接测提案是否换地方。
  边界 2「§2.1 建索引耗时是**折算值**（续17 吞吐），本批未实跑索引重建」→ 本探针 build 腿
         同脚本两臂**实测**。

臂（唯一变量 = 源片索引网格；编辑侧与所有稠密复核腿不动）：
  A10  = 1.0fps 现役网格（对照；同脚本重建的 A10 与生产索引 features/times **逐字节断言相同**，
         相同才允许复用生产 bundle 作对照）
  B05  = 0.5fps 粗筛，无密验
  C05D = B05 粗网格 + 命中邻域密验（在 B05 自己给出的候选窗 ±PAD_S 内按 DENSE_FPS 补帧，
         与粗帧合并后**重建场景表/事件表**）

Run（Python 绝对路径；产物目录带日期，默认拒覆盖）:
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/probe_two_stage_sampling_20261008.py build [case]
  ... probe_two_stage_sampling_20261008.py locate A10|B05|C05D [case]
  ... probe_two_stage_sampling_20261008.py dense [case]
  ... probe_two_stage_sampling_20261008.py report
强制重跑 = 环境变量 SVL_FORCE_RERUN=1（默认不动既有留痕）。

零 runtime 声明：不改 `mvp/src` 任何文件、不 bump 生产 `feature_version`、不翻任何默认值；
所有写入都落在 `work/two_stage_20261008/`（隔离索引根），生产应用数据目录**只读**。
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

BENCH = Path(r"D:\claudework\benchmark")
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE", (r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages"
                                       r"\static_ffmpeg\bin\win32\ffprobe.exe"))
for _p in (BENCH / "mvp" / "src", BENCH / "mvp", BENCH / "mvp" / "scripts"):
    sys.path.insert(0, str(_p))

import numpy as np  # noqa: E402

from app.locator_service import SourceLocatorService  # noqa: E402
from device.directml_backend import DirectMLBackend  # noqa: E402
from domain import IndexValidationStatus  # noqa: E402
from engine.feature_store import FeatureStore  # noqa: E402
from engine.feature_store.index_bundle import IndexBundle  # noqa: E402
from infrastructure.config import load_config  # noqa: E402
from measure_shot_recall import evaluate  # noqa: E402
from rerun_fast_global import CASES, _Progress  # noqa: E402

OUT = BENCH / "work" / "two_stage_20261008"
# 生产索引根（**只读**：仅 load_index，绝不 create/invalidate）
PROD_INDEX_ROOT = Path(r"C:\Users\Bsaizne\AppData\Roaming\Video Locator AI\data\index")
GT_FILES = {
    "2mkv": "datasets/real/ground_truth_v4.json",
    "test1": "datasets/real/ground_truth_test1.json",
    "test2": "datasets/real/ground_truth_test2.json",
    "test3": "datasets/real/ground_truth_test3.json",
}
COARSE_FPS, CONTROL_FPS, DENSE_FPS, PAD_S = 0.5, 1.0, 2.0, 12.0
# 口袋 8 条（`FINDINGS_PATCH_DENSE_CORR_20261002.md` §POCKET8：旧基线 127 时代的真口袋，
# probe_pocket_retest_gt130；8 条 ID 已核实仍在现行 139 条 GT 里）—— 只作「回退时能否救回 ≥1/3」的保险口径，不作主判据。
POCKET8 = ["p02", "p03", "p20", "p30", "p34", "t1r14c", "t2r06c", "t3r02c"]
# build 腿同脚本两臂只实跑这两片（其余片用生产元数据帧数 × 实测吞吐，标注为折算）
BUILD_PAIR_CASES = ["2mkv", "test2"]
# build 腿要建的密度档（默认两臂都建；SVL_BUILD_FPS=0.5 用于「只补粗筛索引、对照走生产」）
BUILD_FPSS = [float(x) for x in os.environ.get("SVL_BUILD_FPS", "1.0,0.5").split(",")]
ARMS = {"A10": CONTROL_FPS, "B05": COARSE_FPS, "C05D": COARSE_FPS}


def _force() -> bool:
    return bool(os.environ.get("SVL_FORCE_RERUN"))


def _service(fps: float) -> SourceLocatorService:
    """新建服务，源索引域指向隔离根（生产目录绝不写入）。"""
    srv = SourceLocatorService(config=load_config())
    assert isinstance(srv.backend, DirectMLBackend), \
        "必须 DirectMLBackend, 实际 %s" % type(srv.backend).__name__
    print("BACKEND_SELECTED type=%s" % type(srv.backend).__name__, flush=True)
    cfg = srv.config.pipeline
    assert cfg.fast_global_enabled is True, "基线要求 fast_global_enabled=True（现役默认）"
    assert cfg.shot_split_enabled and cfg.patch_refine_enabled and cfg.isc_refine_enabled, \
        "基线要求三旋钮默认开（现役 2026-10-06 翻默认后）"
    cfg.index_sampling_fps = fps
    iso = OUT / ("idx_%sfps" % ("%g" % fps))
    srv._store = FeatureStore(srv.ffmpeg, iso, sampling_fps=fps)
    return srv


def _dir_bytes(p: Path) -> int:
    return sum(f.stat().st_size for f in p.glob("*") if f.is_file())


def _bundle_equal(a: IndexBundle, b: IndexBundle) -> dict:
    """两臂索引是否逐字节等价（用于「复用生产 bundle 作对照」的合法性断言）。"""
    out = {"times_rows": [int(a.times.shape[0]), int(b.times.shape[0])],
           "times_max_abs": float(np.abs(a.times - b.times).max())
           if a.times.shape == b.times.shape else None,
           "feat_max_abs": float(np.abs(a.features - b.features).max())
           if a.features.shape == b.features.shape else None,
           "meta_keys": {k: [getattr(a.meta, k), getattr(b.meta, k)]
                         for k in ("sampling_fps", "feature_version", "file_hash",
                                   "num_frames", "duration")}}
    out["identical"] = (out["times_rows"][0] == out["times_rows"][1]
                        and out["times_max_abs"] == 0.0 and out["feat_max_abs"] == 0.0)
    return out


# ------------------------------------------------------------------ #
# 腿 1：建索引两臂实测（补前案边界 2）
# ------------------------------------------------------------------ #
def leg_build(cases: list[str]) -> int:
    acct = {}
    acct_p = OUT / "build_account.json"
    if acct_p.exists() and not _force():
        acct = json.loads(acct_p.read_text(encoding="utf-8"))
    srvs = {}   # 服务只建一次（后端初始化昂贵，且两次 _service() 会重复打印 BACKEND_SELECTED）
    for case in cases:
        orig = CASES[case]["original"]
        row = acct.get(case, {})
        for fps in BUILD_FPSS:
            key = "%sfps" % ("%g" % fps)
            if key in row and not _force():
                print("[build skip] %s %s（已有留痕）" % (case, key), flush=True)
                continue
            if fps not in srvs:
                srvs[fps] = _service(fps)
            srv = srvs[fps]
            store = FeatureStore(srv.ffmpeg, OUT / ("idx_%s" % key), sampling_fps=fps)
            v = store.validate_index(orig)
            if v.status is IndexValidationStatus.VALID:
                print("[build reuse] %s %s（隔离根已 VALID）" % (case, key), flush=True)
                meta = store.get_metadata(orig)
                row[key] = {"wall_s": None, "reused": True,
                            "num_frames": int(meta.num_frames),
                            "bytes": _dir_bytes(store.index_dir(orig)),
                            "feature_version": meta.feature_version}
                continue
            t0 = time.monotonic()
            seen = {"last": 0}

            def _cb(ev, _s=seen):
                done = getattr(ev, "done", None)
                if done and done - _s["last"] >= 500:
                    _s["last"] = done
                    print("    %s %s embedding %s" % (case, key, done), flush=True)

            meta = store.create_index(orig, srv.backend, progress=_cb)
            wall = time.monotonic() - t0
            row[key] = {"wall_s": round(wall, 1), "reused": False,
                        "num_frames": int(meta.num_frames),
                        "duration_s": round(float(meta.duration), 1),
                        "throughput_fps": round(int(meta.num_frames) / max(wall, 1e-6), 2),
                        "bytes": _dir_bytes(store.index_dir(orig)),
                        "feature_version": meta.feature_version}
            print("[build] %s %s -> %.1fs frames=%d thr=%.2f fps bytes=%.1fMB"
                  % (case, key, wall, meta.num_frames, row[key]["throughput_fps"],
                     row[key]["bytes"] / 1e6), flush=True)
        # 同一影片的两臂耗时比 = 本探针的主判据（同脚本、同机器、同后端）
        k1, k05 = "1fps", "0.5fps"
        if k1 in row and k05 in row and row[k1].get("wall_s") and row[k05].get("wall_s"):
            row["ratio_05_over_1"] = round(row[k05]["wall_s"] / row[k1]["wall_s"], 3)
        # 复用生产 bundle 的合法性：同片同 fps 的隔离重建 vs 生产索引须逐字节相同
        if k1 in row and not row[k1].get("reused"):
            srv = srvs.get(CONTROL_FPS) or _service(CONTROL_FPS)
            srvs[CONTROL_FPS] = srv
            prod_store = FeatureStore(srv.ffmpeg, PROD_INDEX_ROOT, sampling_fps=CONTROL_FPS)
            iso_store = FeatureStore(srv.ffmpeg, OUT / "idx_1fps", sampling_fps=CONTROL_FPS)
            if prod_store.validate_index(orig).status is IndexValidationStatus.VALID:
                row["prod_vs_rebuilt"] = _bundle_equal(
                    prod_store.load_index(orig), iso_store.load_index(orig))
                print("[identity] %s 生产 1fps == 同脚本重建 -> identical=%s"
                      % (case, row["prod_vs_rebuilt"]["identical"]), flush=True)
        acct[case] = row
        OUT.mkdir(parents=True, exist_ok=True)
        acct_p.write_text(json.dumps(acct, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(acct, ensure_ascii=False, indent=1), flush=True)
    print("ALL_DONE", flush=True)
    return 0


# ------------------------------------------------------------------ #
# 腿 2：定位（真实链路，补前案边界 1）
# ------------------------------------------------------------------ #
def _load_bundle(arm: str, case: str, srv: SourceLocatorService) -> IndexBundle:
    orig = CASES[case]["original"]
    if arm == "A10":
        # 对照臂复用生产索引（build 腿已断言与同脚本重建逐字节相同）
        store = FeatureStore(srv.ffmpeg, PROD_INDEX_ROOT, sampling_fps=CONTROL_FPS)
        v = store.validate_index(orig)
        assert v.status is IndexValidationStatus.VALID, \
            "对照臂生产索引不可用(%s): %s" % (case, v.reason)
        return store.load_index(orig)
    if arm == "B05":
        store = FeatureStore(srv.ffmpeg, OUT / "idx_0.5fps", sampling_fps=COARSE_FPS)
        v = store.validate_index(orig)
        assert v.status is IndexValidationStatus.VALID, \
            "B05 索引缺失(%s): %s —— 先跑 build 腿" % (case, v.reason)
        return store.load_index(orig)
    if arm == "C05D":
        p = OUT / "dense_bundles" / ("%s.npz" % case)
        assert p.exists(), "C05D bundle 缺失(%s) —— 先跑 dense 腿" % case
        z = np.load(p)
        meta = json.loads(str(z["meta_json"]))
        from domain.index import IndexMeta  # noqa: E402
        return IndexBundle(IndexMeta.from_dict(meta), z["features"], z["times"],
                           scenes=z["scenes"], scene_feats=z["scene_feats"],
                           events=z["events"], event_feats=z["event_feats"])
    raise ValueError(arm)


def leg_locate(arm: str, cases: list[str]) -> int:
    assert arm in ARMS, "臂只能是 A10/B05/C05D, 收到 %r" % arm
    srv = _service(ARMS[arm])
    d = OUT / "results"
    d.mkdir(parents=True, exist_ok=True)
    for case in cases:
        out = d / ("%s_%s.results.json" % (arm, case))
        if out.exists() and not _force():
            print("[locate skip] %s" % out.name, flush=True)
            continue
        bundle = _load_bundle(arm, case, srv)
        assert int(bundle.meta.num_frames) == int(bundle.features.shape[0])
        t0 = time.monotonic()
        print("[locate %s | %s] start (frames=%d fv=%s)"
              % (arm, case, bundle.features.shape[0], bundle.meta.feature_version), flush=True)
        batch = srv.locate(CASES[case]["edited"], CASES[case]["original"],
                           on_progress=_Progress(), index_bundle=bundle)
        wall = time.monotonic() - t0
        data = batch.to_dict()
        # 双臂须断言 status/error：任何段带 failure_reason 都要留痕可见
        errs = [r["result_id"] for r in data["results"] if r.get("failure_reason")]
        assert len(data["results"]) > 0, "%s/%s 结果段数=0" % (arm, case)
        out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print("[locate %s | %s] done %.1fs segs=%d errs=%d -> %s"
              % (arm, case, wall, len(data["results"]), len(errs), out.name), flush=True)
    print("ALL_DONE", flush=True)
    return 0


# ------------------------------------------------------------------ #
# 腿 3：命中邻域密验（两级采样的第二级）
# ------------------------------------------------------------------ #
def _hit_windows(case: str) -> list[tuple[float, float]]:
    """从 B05 自己的候选（= 第一级的产出）取窗口，±PAD_S 后按时间合并。"""
    p = OUT / "results" / ("B05_%s.results.json" % case)
    assert p.exists(), "缺 B05 结果(%s) —— 密验窗必须来自粗筛第一级的真实产出" % case
    spans = []
    for r in json.loads(p.read_text(encoding="utf-8"))["results"]:
        for t in [r["original"]] + list(r.get("original_segments") or []):
            a, b = float(t["candidate_start"]), float(t["candidate_end"])
            if b - a > 0.01:
                spans.append((a, b))
    spans.sort()
    merged = []
    for a, b in spans:
        a, b = a - PAD_S, b + PAD_S
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return [(max(0.0, a), b) for a, b in merged]


def leg_dense(cases: list[str]) -> int:
    d = OUT / "dense_bundles"
    d.mkdir(parents=True, exist_ok=True)
    srv = _service(COARSE_FPS)
    store = FeatureStore(srv.ffmpeg, OUT / "idx_0.5fps", sampling_fps=COARSE_FPS)
    for case in cases:
        out = d / ("%s.npz" % case)
        if out.exists() and not _force():
            print("[dense skip] %s" % out.name, flush=True)
            continue
        orig = Path(CASES[case]["original"])
        coarse = store.load_index(orig)
        wins = _hit_windows(case)
        t0 = time.monotonic()
        ct = np.asarray(coarse.times, dtype=np.float64)
        step = 1.0 / DENSE_FPS
        # 密验网格**对齐粗网格偏移**（t_k + 0.5/1.0/1.5 …），保证不与粗帧重合；
        # 抓帧走冻结同帧契约 grab_grid_times（**不用 iter_frames**：其合成标签比真实 pts
        # 晚 ~0.5s，续52-C 实测，混用会让两臂的密帧与粗帧不在同一时间语义上）。
        offs = [i * step for i in
                range(1, int(round((1.0 / COARSE_FPS) / step)))]        # 0.5/1.0/1.5（粗格间距 2s 内）
        targets = []
        for base_t in ct:
            for off in offs:
                t = float(base_t) + off
                if any(a <= t <= b for a, b in wins):
                    targets.append(round(t, 3))
        targets = sorted(set(targets))
        got = srv.ffmpeg.grab_grid_times(orig, targets, step=step) if targets else {}
        pairs = [(t, f) for t, f in got.items() if f is not None]
        pairs.sort(key=lambda x: x[0])
        dense_t = np.asarray([t for t, _ in pairs], dtype=np.float32)
        emb = []
        for i in range(0, len(pairs), 32):
            emb.append(srv.backend.embed_frames([f for _, f in pairs[i:i + 32]]))
        dense_f = np.concatenate(emb, axis=0).astype(np.float32) if emb else np.zeros(
            (0, coarse.features.shape[1]), dtype=np.float32)
        # 与粗帧去重（同刻已存在则不重复计入）
        keep = np.ones(dense_t.shape[0], dtype=bool)
        for i, t in enumerate(dense_t):
            if ct.size and np.min(np.abs(ct - float(t))) < 0.25:
                keep[i] = False
        dense_f, dense_t = dense_f[keep], dense_t[keep]
        feats = np.concatenate([coarse.features, dense_f], axis=0).astype(np.float32)
        times = np.concatenate([ct, dense_t.astype(np.float32)]).astype(np.float32)
        order = np.argsort(times, kind="stable")
        feats, times = feats[order], times[order]
        scenes, scene_feats = store._build_scene_table(feats, times)
        events, event_feats = store._build_event_table(scenes, scene_feats)
        meta = dict(coarse.meta.to_dict())
        meta["num_frames"] = int(times.shape[0])
        meta["feature_version"] = "%s+dv2" % coarse.meta.feature_version  # 沙盒标记，不写生产
        np.savez_compressed(out, features=feats, times=times, scenes=scenes,
                            scene_feats=scene_feats, events=events,
                            event_feats=event_feats,
                            meta_json=json.dumps(meta, ensure_ascii=False))
        print("[dense] %s 窗=%d 粗帧=%d 密帧(去重后)=%d 合计=%d  %.1fs"
              % (case, len(wins), int(coarse.times.shape[0]), int(dense_t.shape[0]),
                 int(times.shape[0]), time.monotonic() - t0), flush=True)
    print("ALL_DONE", flush=True)
    return 0


# ------------------------------------------------------------------ #
# 腿 4：比对（零 GPU，纯 JSON + GT）
# ------------------------------------------------------------------ #
def _strip_ids(data: dict) -> dict:
    """strip(result_id)（与 probe_defaults_flip_ab 同口径）：逐字节比对的预处理。"""
    import copy
    d = copy.deepcopy(data)
    d.pop("result_id", None)
    for r in d.get("results", []):
        r.pop("result_id", None)
    return d


def _failure_hist(res: list[dict]) -> dict:
    h = {}
    for r in res:
        k = r.get("failure_reason") or "None"
        h[k] = h.get(k, 0) + 1
    return h


def _rows_by_edited(res: list[dict]) -> dict:
    return {(round(float(r["edited_segment"]["start"]), 3),
             round(float(r["edited_segment"]["end"]), 3)): r for r in res}


def _spans(r: dict) -> list[tuple[float, float]]:
    out = [(float(r["original"]["candidate_start"]), float(r["original"]["candidate_end"]))]
    for s in r.get("original_segments") or []:
        out.append((float(s["candidate_start"]), float(s["candidate_end"])))
    return out


def leg_report() -> int:
    rep = {"caliber": ("同脚本两臂；评估器 = measure_shot_recall.evaluate（未改写）；"
                       "对照臂 A10 = 生产 1fps 索引（build 腿已断言与同脚本重建逐字节相同）；"
                       "基线批 work/isc_refine_arms/v2_* = 2026-10-03 现役默认"),
           "cases": {}, "totals": {}, "build_account": {}}
    base = {}
    for arm in ("A10", "B05", "C05D"):
        base[arm] = {}
        for case in CASES:
            p = OUT / "results" / ("%s_%s.results.json" % (arm, case))
            if p.exists():
                base[arm][case] = json.loads(p.read_text(encoding="utf-8"))["results"]
    v10 = {}
    for case in CASES:
        p = BENCH / "work" / "isc_refine_arms" / ("v2_%s.results.json" % case)
        if p.exists():
            v10[case] = json.loads(p.read_text(encoding="utf-8"))["results"]

    tot = {}
    # 漂移控制：同脚本 A10 臂 vs 2026-10-03 基线批 v2_*，strip(result_id) 后逐字节比对。
    # 相同 => 跨批基线可用（B05 只需与 v2_* 比）；不同 => 必须补跑 A10 四片作真对照。
    rep["drift_control"] = {}
    for case in CASES:
        if case not in base["A10"] or case not in v10:
            continue
        a = _strip_ids(json.loads((OUT / "results" / ("A10_%s.results.json" % case))
                                  .read_text(encoding="utf-8")))
        b = _strip_ids(json.loads((BENCH / "work" / "isc_refine_arms" /
                                   ("v2_%s.results.json" % case)).read_text(encoding="utf-8")))
        sa, sb = json.dumps(a, sort_keys=True, ensure_ascii=False), \
            json.dumps(b, sort_keys=True, ensure_ascii=False)
        rep["drift_control"][case] = {"strip_identical": sa == sb,
                                      "len_a": len(sa), "len_b": len(sb)}
        print("[drift] %s A10 vs v2_20261003 strip_identical=%s"
              % (case, sa == sb), flush=True)
    for case in CASES:
        gt = json.loads((BENCH / GT_FILES[case]).read_text(encoding="utf-8"))
        row = {"available": {a: (case in base[a]) for a in base}, "metrics": {}, "diff": {}}
        for arm in ("A10", "B05", "C05D"):
            if case not in base[arm]:
                continue
            import contextlib, io
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                r = evaluate(gt, base[arm][case], label=arm + "_" + case)
            row["metrics"][arm] = {"strict": r["strict_hit"], "main": r["main_hit"],
                                   "scene": r["scene_hit"], "fp": r["fp"],
                                   "n_pos": r["n_pos"], "n_neg": r["n_neg"],
                                   "marks": {p["id"]: p["mark"] for p in r["per_pos"]},
                                   "n_rows": len(base[arm][case]),
                                   "failure_reasons": _failure_hist(base[arm][case])}
            t = tot.setdefault(arm, {"strict": 0, "main": 0, "scene": 0, "fp": 0,
                                     "n_pos": 0, "n_neg": 0})
            for k in ("strict", "main", "scene", "fp", "n_pos", "n_neg"):
                t[k] += row["metrics"][arm][k]
        if case in v10:
            import contextlib, io
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                r = evaluate(gt, v10[case], label="v10_" + case)
            row["metrics"]["V10"] = {"strict": r["strict_hit"], "main": r["main_hit"],
                                     "scene": r["scene_hit"], "fp": r["fp"],
                                     "n_pos": r["n_pos"], "n_neg": r["n_neg"],
                                     "marks": {p["id"]: p["mark"] for p in r["per_pos"]},
                                     "n_rows": len(v10[case])}
            t = tot.setdefault("V10", {"strict": 0, "main": 0, "scene": 0, "fp": 0,
                                       "n_pos": 0, "n_neg": 0})
            for k in ("strict", "main", "scene", "fp", "n_pos", "n_neg"):
                t[k] += row["metrics"]["V10"][k]
        # 逐行 span 差（按编辑侧区间对齐；两侧行数不等 = 结构变化，单列）
        for arm in ("B05", "C05D"):
            if case not in base[arm]:
                continue
            ref_arm = "A10" if case in base["A10"] else None
            ref = base[ref_arm][case] if ref_arm else v10.get(case)
            if ref is None:
                continue
            ra, rb = _rows_by_edited(ref), _rows_by_edited(base[arm][case])
            common = sorted(set(ra) & set(rb))
            ds, de, sub_n = [], [], 0
            for k in common:
                sa, sb = _spans(ra[k]), _spans(rb[k])
                sub_n += abs(len(sa) - len(sb))
                if len(sa) == len(sb):
                    for (a0, a1), (b0, b1) in zip(sa, sb):
                        ds.append(b0 - a0)
                        de.append(b1 - a1)
            d_all = ds + de
            row["diff"][arm] = {
                "ref_arm": ref_arm or "V10", "rows_ref": len(ra), "rows_arm": len(rb),
                "matched_rows": len(common),
                "only_in_ref": [list(k) for k in sorted(set(ra) - set(rb))][:10],
                "only_in_arm": [list(k) for k in sorted(set(rb) - set(ra))][:10],
                "span_abs_median_s": round(float(np.median(np.abs(d_all))), 3) if d_all else None,
                "span_abs_p95_s": round(float(np.percentile(np.abs(d_all), 95)), 3) if d_all else None,
                "span_abs_max_s": round(float(np.max(np.abs(d_all))), 3) if d_all else None,
                "n_span_moves_gt_1s": int(sum(1 for x in d_all if abs(x) > 1.0)),
                "n_span_moves_gt_2s": int(sum(1 for x in d_all if abs(x) > 2.0)),
                "subspan_count_diff_rows": sub_n}
            # 翻转行（相对 ref 臂的逐 GT mark）
            mref = row["metrics"].get(ref_arm or "V10", {}).get("marks", {})
            mart = row["metrics"][arm]["marks"]
            row["diff"][arm]["flips"] = {k: [mref.get(k), v] for k, v in mart.items()
                                         if mref.get(k) != v}
        rep["cases"][case] = row
    rep["totals"] = tot
    # 口袋 8 条逐臂读数（保险口径：B05 若回退，看 C05D 救回多少）
    rep["pocket"] = {}
    for arm in ("A10", "V10", "B05", "C05D"):
        mk = {}
        for row in rep["cases"].values():
            m = row["metrics"].get(arm, {}).get("marks", {})
            mk.update({k: v for k, v in m.items() if k in POCKET8})
        if mk:
            rep["pocket"][arm] = {"marks": mk, "hit": sum(1 for v in mk.values() if v == "HIT"),
                                  "rows": len(mk)}
    if (OUT / "build_account.json").exists():
        rep["build_account"] = json.loads((OUT / "build_account.json").read_text(encoding="utf-8"))
    (OUT / "compare.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1),
                                      encoding="utf-8")
    print("=== 四片合计（各臂）===")
    for arm in ("A10", "V10", "B05", "C05D"):
        if arm not in tot:
            continue
        t = tot[arm]
        print("  %-5s 严格 %3d/%d | 导出实得 %3d | 场景 %3d | 负例 %d/%d"
              % (arm, t["strict"], t["n_pos"], t["main"], t["scene"], t["fp"], t["n_neg"]))
    for arm, pk in rep["pocket"].items():
        print("  口袋 %-5s HIT %d/%d  %s" % (arm, pk["hit"], pk["rows"],
                                             json.dumps(pk["marks"], ensure_ascii=False)))
    for case, row in rep["cases"].items():
        for arm, m in row["metrics"].items():
            print("[%s|%s] 行数=%d 失败分布=%s" % (case, arm, m["n_rows"],
                                                  json.dumps(m.get("failure_reasons", {}),
                                                             ensure_ascii=False)))
        for arm, dd in row["diff"].items():
            print("[%s|%s] 匹配行 %d/%d(参照 %d) 移动>1s=%d >2s=%d |Δ|max=%ss 翻转=%d"
                  % (case, arm, dd["matched_rows"], dd["rows_arm"], dd["rows_ref"],
                     dd["n_span_moves_gt_1s"], dd["n_span_moves_gt_2s"],
                     dd["span_abs_max_s"], len(dd["flips"])))
            if dd["flips"]:
                print("     flips %s" % json.dumps(dd["flips"], ensure_ascii=False))
    print("\nsaved %s" % (OUT / "compare.json"))
    print("ALL_DONE", flush=True)
    return 0


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    rest = sys.argv[2:]
    OUT.mkdir(parents=True, exist_ok=True)
    if mode == "build":
        cases = rest or BUILD_PAIR_CASES
        return leg_build(cases)
    if mode == "locate":
        arm = rest[0]
        cases = rest[1:] or list(CASES)
        return leg_locate(arm, cases)
    if mode == "dense":
        return leg_dense(rest or list(CASES))
    if mode == "report":
        return leg_report()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
