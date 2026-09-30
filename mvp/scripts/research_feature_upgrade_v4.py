"""Phase 23 特征升级预研(三):用修正 GT 重跑 ViT-S vs ViT-B 对照。

起因(2026-09-22 用户质疑 -> FINDINGS_GT_CONTAMINATION_AUDIT.md):
预研(一)(二) 的 9 个探针中 3 个建立在已证伪数据上 ——
  * p26 旧真值窗 2808-2811 = GT 标错(正确 1768.2-1770.05, 用户画面精修);
  * p08b "真值窗" 1048-1050 = p38 旧错误 GT 区(已作废; p08b 正确 = p08 的 1108.15-1109.1);
  * t4r01/t4r13 = test4 数据无效(test4-ed.mp4 与 test4-om.mkv 是两部不同电影)。
而"ViT-B 更差"的最强证据(p08b margin -0.138 -> -0.281)恰来自 p08b 污染案例。
=> "该不该换更大基座(ViT-S -> ViT-B)"目前无可靠证据支撑任一方, 本脚本用修正 GT 重跑。

方法(与原协议一致, 见 research_feature_upgrade.py / _upgrade2.py):
- 查询帧 = 编辑片 qt±0.4s 三帧均值(ViT-S / ViT-B 各自嵌入, L2);
- 干扰窗 = ViT-S 全片索引 top-40 相似帧(排除真值窗 ±10s)聚区(gap 5s)取前 2 区, ±10s 扩边,
  再插入人工"兄弟机位/已知错位"窗;
- ViT-S 侧用全片索引缓存(1fps L2 CLS), ViT-B 侧对"真值窗 ±1s ∪ 干扰窗"局部嵌入;
- 指标 = true_max - wrong_max(= margin) + argmax 是否落真值窗。

本脚本相对原脚本新增:
- 同一批嵌入帧上同时计算"v3 旧口径"与"v4 修正口径"两套标签 => 区分"数据修正"与"协议差异";
- 一次 forward 同时取 CLS + patch(原预研一/二分两次跑);
- 记录 ViT-S 全片索引中真值帧 rank(产品相关: 正确区是否进池);
- 索引基线自检(当前 .idx 与 .idx.stale 的 features 是否一致 => ViT-S 基线未变)。

设备:CPU。ViT-B 无 DirectML/ONNX 资产、本机 torch 为 +cpu 构建 => 与原 2026-08-30 口径一致
(GPU 优先约定见 .agent/DECISIONS.md; 本探针无 GPU 路径, 已在 FINDINGS 留痕)。

运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" \
      mvp/scripts/research_feature_upgrade_v4.py
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

BENCH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BENCH / "mvp" / "src"))

from device.dinov2_model import DinoV2Small, _imagenet_preprocess  # noqa: E402
from media.ffmpeg import FFmpegIO  # noqa: E402

FFMPEG = BENCH / "tools" / "ffmpeg.exe"
FFPROBE = (BENCH.parent / "video-dedup-tool" / ".venv" / "Lib" / "site-packages"
           / "static_ffmpeg" / "bin" / "win32" / "ffprobe.exe")
W_S = BENCH / "work" / "dinov2_weights" / "dinov2_vits14_pretrain.pth"
W_B = BENCH / "work" / "dinov2_weights" / "dinov2_vitb14_pretrain.pth"
IDX_DIR = Path("C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/index")
GT_V4 = BENCH / "datasets" / "real" / "ground_truth_v4.json"
GT_T3 = BENCH / "datasets" / "real" / "ground_truth_test3.json"
ARCH1 = BENCH / "work" / "feature_upgrade_probe_results.json"
ARCH2 = BENCH / "work" / "feature_upgrade_probe2_results.json"
OUT = BENCH / "work" / "feature_upgrade_v4_results.json"

PAIRS = {
    "2mkv": dict(orig="D:/video/2.mkv", edit="D:/video/1.mp4",
                 idx="2__4c6d4ab2"),
    "test3": dict(orig="D:/ProjectXIXI/test3/test3-om.mp4",
                  edit="D:/ProjectXIXI/test3/test3-ed.mp4",
                  idx="test3-om__074e2dcc"),
}

# 探针集: 原 9 探针 - test4 两个(数据无效) + t3r12(失败族硬例, 新增)
PROBES = [
    dict(id="p26_hard", pair="2mkv", qt=76.8, gt=("v4", "p26"),
         note="夜读书+手: 原探针真值窗 2808-2811 = GT 标错"),
    dict(id="p08_brother", pair="2mkv", qt=13.5, gt=("v4", "p08"),
         brother=(1048.0, 1050.0), note="瞭望塔机位: 兄弟机位 1048-1050 为干扰"),
    dict(id="p08b_brother", pair="2mkv", qt=13.9, gt=("v4", "p08"),
         brother=(1048.0, 1050.0),
         note="士兵特写: 原探针把 p38 旧错误 GT 区 1048-1050 当真值窗(已作废)"),
    dict(id="p27_sign", pair="2mkv", qt=85.5, gt=("v4", "p27"), note="WHAT 字牌"),
    dict(id="p01_easy", pair="2mkv", qt=0.8, gt=("v4", "p01"), note="金属球准备(易例)"),
    dict(id="p04_easy", pair="2mkv", qt=4.6, gt=("v4", "p04"), note="峡谷航拍(易例)"),
    dict(id="p17_easy", pair="2mkv", qt=38.0, gt=("v4", "p17"),
         legacy_skip="原探针 query 36.0 落在 p16 编辑段, 不可比",
         note="武器站枪塔(易例)"),
    dict(id="t3r10_adj", pair="test3", qt=56.25, gt=("t3", "t3r10"), note="逃亡奔跑边界"),
    dict(id="t3r12_hard", pair="test3", qt=64.75, gt=("t3", "t3r12"),
         brother=(481.0, 488.0), extra=True, note="精灵王重复镜头(失败族, 本脚本新增)"),
]

HALF_DIST = 10.0     # 干扰窗半径(与原脚本一致)
TOPK_DISTRACT = 40   # ViT-S 全索引取前 K 帧聚干扰区
PATCH_TOPK = 100     # V3: query-patch 最大余弦的 top100 均值
PATCH_THIN = 12      # 每窗候选帧上限(与原 probe2 一致)


def load_gt():
    out = {}
    for key, path in (("v4", GT_V4), ("t3", GT_T3)):
        data = json.loads(path.read_text(encoding="utf-8"))
        for seg in data.get("positives", []):
            out[(key, seg["id"])] = dict(
                original=[float(x) for x in seg["original"]],
                edited=[float(x) for x in seg["edited"]],
                tier=seg.get("tier"), note=seg.get("note", ""))
    return out


def load_archive():
    """原预研存档: id -> 旧口径(true_win, distract_wins, 源文件)。"""
    out = {}
    for tag, path in (("probe1", ARCH1), ("probe2", ARCH2)):
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for e in data.get("probes", []):
            if e["id"] not in out:
                out[e["id"]] = dict(
                    tag=tag, true_win=[float(x) for x in e["true_win"]],
                    distract_wins=[[float(a), float(b)] for a, b in e["distract_wins"]],
                    metrics_cls=(e.get("vit_s"), e.get("vit_b")),
                    metrics_patch=(e.get("patch_vits"), e.get("patch_vitb")))
    return out


def load_models():
    ms = DinoV2Small()
    ms.load_state_dict(torch.load(str(W_S), map_location="cpu", weights_only=True),
                       strict=False)
    ms.eval()
    mb = DinoV2Small(embed_dim=768, num_heads=12)
    missing, unexpected = mb.load_state_dict(
        torch.load(str(W_B), map_location="cpu", weights_only=True), strict=False)
    print("ViT-B load: missing=%s unexpected=%s" % (list(missing), list(unexpected)),
          flush=True)
    mb.eval()
    return ms, mb


def runs_from_frames(ts_sorted, gap=5.0):
    if not len(ts_sorted):
        return []
    out = [[ts_sorted[0], ts_sorted[0]]]
    for t in ts_sorted[1:]:
        if t - out[-1][1] <= gap:
            out[-1][1] = t
        else:
            out.append([t, t])
    return out


def merge_windows(wins):
    ws = sorted([list(w) for w in wins], key=lambda w: w[0])
    out = []
    for a, b in ws:
        if out and a <= out[-1][1] + 0.5:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [tuple(w) for w in out]


def win_idx(times, win, pad=0.0):
    a, b = win
    return np.where((times >= a - pad) & (times <= b + pad))[0]


def local_wins(feats, times, q_s, true_win, brother=None):
    """ViT-S 全索引 top-K 聚干扰区(与原脚本同一口径)。"""
    sims = feats @ q_s
    conf = [int(i) for i in np.argsort(-sims)[:TOPK_DISTRACT]
            if not (true_win[0] - HALF_DIST <= times[i] <= true_win[1] + HALF_DIST)]
    runs = runs_from_frames(sorted(float(times[i]) for i in conf))
    wins = [(max(0.0, a - HALF_DIST), b + HALF_DIST) for a, b in runs[:2]]
    if brother:
        wins.insert(0, (float(brother[0]) - HALF_DIST, float(brother[1]) + HALF_DIST))
    wins = [w for w in wins if not (w[0] < true_win[1] and w[1] > true_win[0])]
    return merge_windows(wins)


def thin(ts_list, cap=PATCH_THIN):
    if len(ts_list) <= cap:
        return list(ts_list)
    idx = np.linspace(0, len(ts_list) - 1, cap).round().astype(int)
    return [ts_list[i] for i in idx]


def patch_score(q_flat, cand):
    """V3 定义: query patch 对候选帧 patch 的最大余弦 -> top100 均值。"""
    m = np.asarray(q_flat @ cand.T).max(axis=0)   # [P,P]
    k = min(PATCH_TOPK, m.size)
    return float(np.sort(m.ravel())[-k:].mean())


@torch.no_grad()
def embed_query(models, ff, video, ts):
    x = torch.cat([_imagenet_preprocess(ff.grab_frame(video, float(t))) for t in ts])
    out = {}
    for tag, m in models.items():
        cls, pat = m.forward_features(x)
        # 与原脚本一致: 先逐帧 L2 归一化, 再对查询帧取均值, 再归一化
        c = cls.numpy().astype(np.float32)
        c /= np.maximum(np.linalg.norm(c, axis=1, keepdims=True), 1e-8)
        c = c.mean(axis=0)
        c /= max(float(np.linalg.norm(c)), 1e-8)
        p = pat.numpy().astype(np.float32)
        p /= np.maximum(np.linalg.norm(p, axis=2, keepdims=True), 1e-8)
        out[tag] = (c, np.concatenate(p, axis=0))
    return out


@torch.no_grad()
def embed_candidates(models, ff, video, ts, q_pat, batch=4):
    """返回 cls[tag] -> [N,D] 与 pat[tag] -> [N] (V3 patch 得分)。"""
    cls_out = {t: [] for t in models}
    pat_out = {t: [] for t in models}
    for i in range(0, len(ts), batch):
        chunk = ts[i:i + batch]
        x = torch.cat([_imagenet_preprocess(ff.grab_frame(video, float(t)))
                       for t in chunk])
        for tag, m in models.items():
            c, p = m.forward_features(x)
            c = c.numpy().astype(np.float32)
            c /= np.maximum(np.linalg.norm(c, axis=1, keepdims=True), 1e-8)
            cls_out[tag].append(c)
            p = p.numpy().astype(np.float32)
            p /= np.maximum(np.linalg.norm(p, axis=2, keepdims=True), 1e-8)
            pat_out[tag].extend(patch_score(q_pat[tag], p[k]) for k in range(len(chunk)))
    return ({t: np.concatenate(v, axis=0) for t, v in cls_out.items()},
            {t: np.asarray(v, np.float32) for t, v in pat_out.items()})


def score_block(sims, times, true_win, dist_wins, pad=1.0, idx_map=None):
    """sims 为与 times 对齐的分数; idx_map=全片索引下标(用于 ViT-S 全片口径)。"""
    ti = win_idx(times, true_win, pad)
    tm = float(max(sims[i] for i in ti)) if len(ti) else float("nan")
    dm, dw = float("nan"), None
    for w in dist_wins:
        wi = win_idx(times, w)
        if not len(wi):
            continue
        m = float(max(sims[i] for i in wi))
        if dw is None or m > dm:
            dm, dw = m, list(w)
    return dict(true_max=round(tm, 4), wrong_max=round(dm, 4),
                margin=round(tm - dm, 4), wrong_win=[round(x, 1) for x in dw] if dw else None,
                n_true=int(len(ti)))


def full_index_rank(sims, times, true_win, pad=1.0):
    order = np.argsort(-sims)
    rank_of = {int(i): r + 1 for r, i in enumerate(order)}
    ti = win_idx(times, true_win, pad)
    if not len(ti):
        return None, None
    best = int(ti[int(np.argmax(sims[ti]))])
    return rank_of[best], float(times[best])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="逗号分隔的探针 id(默认全部)")
    ap.add_argument("--out", default=str(OUT), help="结果 JSON 输出路径")
    args = ap.parse_args()
    out_path = Path(args.out)
    probes = ([p for p in PROBES if p["id"] in args.only.split(",")]
              if args.only else PROBES)
    t0 = time.time()
    print("torch=%s cuda=%s" % (torch.__version__, torch.cuda.is_available()),
          flush=True)
    gt, arch = load_gt(), load_archive()
    ff = FFmpegIO(FFMPEG, FFPROBE)
    models = {"vit_s": None, "vit_b": None}
    ms, mb = load_models()
    models = {"vit_s": ms, "vit_b": mb}

    # --- 索引基线自检: 当前 .idx 与 .idx.stale 是否同一批特征 ---
    base = {}
    cur_d = IDX_DIR / (PAIRS["2mkv"]["idx"] + ".idx")
    old_d = IDX_DIR / (PAIRS["2mkv"]["idx"] + ".idx.stale")
    fa = np.load(cur_d / "features.npy")
    base["features_shape"] = list(fa.shape)
    base["features_dtype"] = str(fa.dtype)
    try:
        base["index_json"] = json.loads((cur_d / "index.json").read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover
        base["index_json"] = "ERR %s" % exc
    if (old_d / "features.npy").exists():
        fb = np.load(old_d / "features.npy")
        base["stale_same_shape"] = (fa.shape == fb.shape)
        if fa.shape == fb.shape:
            base["stale_max_abs_diff"] = float(np.max(np.abs(fa - fb)))
    print("baseline:", json.dumps(base, ensure_ascii=False)[:400], flush=True)

    report = {"started": time.strftime("%Y-%m-%d %H:%M:%S"),
              "purpose": "feature_upgrade 重跑(v4/verified 修正 GT)",
              "device": {"torch": torch.__version__,
                         "cuda": bool(torch.cuda.is_available()),
                         "note": "CPU 前向(ViT-B 无 DML/ONNX 资产; 与原口径一致)"},
              "baseline_check": base, "probes": [], "summary": []}

    for spec in probes:
        pid, pair = spec["id"], spec["pair"]
        cfg = PAIRS[pair]
        g = gt[spec["gt"]]
        true_win = tuple(g["original"])
        feats = np.load(IDX_DIR / (cfg["idx"] + ".idx") / "features.npy").astype(np.float32)
        times = np.load(IDX_DIR / (cfg["idx"] + ".idx") / "times.npy").astype(np.float64)
        qt = spec["qt"]
        q_ts = [qt - 0.4, qt, qt + 0.4]
        q = embed_query(models, ff, cfg["edit"], q_ts)
        q_s = q["vit_s"][0]
        q_b = q["vit_b"][0]
        q_pat = {"vit_s": q["vit_s"][1], "vit_b": q["vit_b"][1]}
        sims_full = feats @ q_s

        # --- 标签口径 ---
        lab_v4 = dict(label="v4", true_win=list(true_win),
                      source="%s:%s" % (spec["gt"][0], spec["gt"][1]),
                      distract_wins=local_wins(feats, times, q_s, true_win, spec.get("brother")))
        labelings = [lab_v4]
        if pid == "p26_hard":   # 09-01 粗修正窗敏感性对照
            labelings.append(dict(label="v4_coarse", true_win=[1766.0, 1770.0],
                                  source="STATE.md 2026-09-01 粗修正",
                                  distract_wins=local_wins(feats, times, q_s, (1766.0, 1770.0))))
        a = arch.get(pid)
        if a and not spec.get("legacy_skip"):
            labelings.append(dict(label="v3_legacy", true_win=list(a["true_win"]),
                                  source="work/feature_upgrade_%s_results.json" % a["tag"],
                                  distract_wins=[tuple(w) for w in a["distract_wins"]]))

        # --- 联合帧集合(各口径真值窗 ±1s ∪ 各口径干扰窗) ---
        u_ts = set()
        for L in labelings:
            u_ts |= {float(times[i]) for i in win_idx(times, tuple(L["true_win"]), 1.0)}
            for w in L["distract_wins"]:
                u_ts |= {float(times[i]) for i in win_idx(times, tuple(w))}
        all_ts = sorted(u_ts)
        cls_b, pat = embed_candidates(models, ff, cfg["orig"], all_ts, q_pat)
        loc_times = np.asarray(all_ts, np.float64)
        sims_s_loc = sims_full[np.array([int(np.argmin(np.abs(times - t))) for t in all_ts])]
        sims = {"vit_s": sims_s_loc.astype(np.float32),
                "vit_b": (cls_b["vit_b"] @ q_b).astype(np.float32)}
        pat_scores = {"vit_s": pat["vit_s"], "vit_b": pat["vit_b"]}

        entry = dict(id=pid, pair=pair, query_t=qt, gt_note=g["note"][:120],
                     probe_note=spec["note"], extra=bool(spec.get("extra")),
                     frames_embedded=len(all_ts), labelings=[])
        for L in labelings:
            tw = tuple(L["true_win"])
            dws = [tuple(w) for w in L["distract_wins"]]
            true_ts = [float(times[i]) for i in win_idx(times, tw, 1.0)]
            dist_ts = sorted({float(times[i]) for w in dws for i in win_idx(times, w)})
            row = dict(label=L["label"], true_win=[round(x, 2) for x in tw],
                       source=L["source"],
                       distract_wins=[[round(a, 1), round(b, 1)] for a, b in dws],
                       n_frames_true=len(true_ts), n_frames_distract=len(dist_ts))
            for tag in ("vit_s", "vit_b"):
                r = score_block(sims[tag], loc_times, tw, dws)
                r["argmax_t"] = round(float(loc_times[int(np.argmax(sims[tag]))]), 1)
                row["cls_" + tag] = r
            # ViT-S 全片索引口径(产品相关: 正确区是否进池)
            r_full = score_block(sims_full, times, tw, dws)
            rank, rank_t = full_index_rank(sims_full, times, tw)
            r_full.update(argmax_t=round(float(times[int(np.argmax(sims_full))]), 1),
                          true_best_rank=rank, true_best_t=rank_t)
            row["cls_vit_s_fullindex"] = r_full
            # patch 口径(原 probe2: 每窗 thin 到 12 帧)
            t_t, d_t = thin(true_ts), thin(dist_ts)
            tmap = {t: k for k, t in enumerate(loc_times)}
            for tag in ("vit_s", "vit_b"):
                sc = pat_scores[tag]
                tv = [float(sc[tmap[t]]) for t in t_t if t in tmap]
                dv, dwin = [], None
                for w in dws:
                    vv = [float(sc[tmap[t]]) for t in d_t if t in tmap and w[0] <= t <= w[1]]
                    if vv and (dwin is None or max(vv) > (max(dv) if dv else -9)):
                        dv, dwin = vv, w
                tm = max(tv) if tv else float("nan")
                dm = max(dv) if dv else float("nan")
                row["patch_" + tag] = dict(true_max=round(tm, 4), wrong_max=round(dm, 4),
                                           margin=round(tm - dm, 4),
                                           n_scored=len(t_t) + len(d_t))
            entry["labelings"].append(row)
            report["summary"].append(dict(
                probe=pid, extra=bool(spec.get("extra")), labeling=L["label"],
                true_win=row["true_win"],
                s_margin=row["cls_vit_s"]["margin"], b_margin=row["cls_vit_b"]["margin"],
                s_arg=row["cls_vit_s"]["argmax_t"], b_arg=row["cls_vit_b"]["argmax_t"],
                ps_margin=row["patch_vit_s"]["margin"], pb_margin=row["patch_vit_b"]["margin"],
                s_rank_full=row["cls_vit_s_fullindex"]["true_best_rank"]))
        report["probes"].append(entry)
        # 增量落盘: 单探针失败也不丢已完成结果
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        print("\n[%s] qt=%.2f true(v4)=%s frames=%d" %
              (pid, qt, list(true_win), len(all_ts)), flush=True)
        for row in entry["labelings"]:
            print("  %-10s true=%s dist=%s\n"
                  "      CLS S %+.4f / B %+.4f | patch S %+.4f / B %+.4f | S_full_rank=%s"
                  % (row["label"], row["true_win"], row["distract_wins"],
                     row["cls_vit_s"]["margin"], row["cls_vit_b"]["margin"],
                     row["patch_vit_s"]["margin"], row["patch_vit_b"]["margin"],
                     row["cls_vit_s_fullindex"]["true_best_rank"]), flush=True)

    report["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    report["elapsed_s"] = round(time.time() - t0, 1)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print("\nsaved %s  total %.0fs" % (out_path, report["elapsed_s"]), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
