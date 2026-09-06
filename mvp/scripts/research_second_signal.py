"""Phase 24-0 非外观第二信号预研:音频判别力 + 时序非重叠先验(仅研究,不改 runtime)。

背景(STATE 2026-08-30 深夜交接):剩余失败族 = 同场景重复实例 / 同质场景互混,
特征升级预研(Phase 23-0)已证 ViT-B/14 无增益。本研究探两个非外观信号:

Part A 音频判别力(探针式,仿 research_feature_upgrade.py 口径):
  编辑段音频 vs 原片真值窗/干扰窗音频,log-mel 帧特征 + 最近邻帧投票
  (对快剪压缩稳健)+ 常速对角匹配(参考)。判别力 = 真值窗得票率 - 最大干扰窗得票率。
  含源↔源自对照(管线 sanity)。
  风险前置:编辑片可能压 BGM/解说盖原声 → 探针直接给经验答案。

Part B 时序非重叠先验(离线回放,零解码):
  主定位 span 在原片时间轴上互相重叠时,低置信段移入最近可容纳空隙(居中)。
  test3 用用户修正基线(Desktop/1,r10 实锤错位 447-449,真值≈444.5 在
  r9 442 / r11 447.5 空隙)对照全量裁决 verdicts 验收:目标 = 修 r10 且不动任何「对」。
  test1/2/4 用 _scene_v3 现行管线结果做普适性/扰动普查。

运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" \
      mvp/scripts/research_second_signal.py [--skip-audio]
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

BENCH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BENCH / "mvp" / "src"))

FFMPEG = BENCH / "tools" / "ffmpeg.exe"
FP = (BENCH.parent / "video-dedup-tool" / ".venv" / "Lib" / "site-packages"
      / "static_ffmpeg" / "bin" / "win32" / "ffprobe.exe")
IDX_DIR = Path("C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/index")
T3_BASELINE = Path("C:/Users/Bsaizne/Desktop/1/test3-ed__57a104a7.results.json")
CASES = BENCH / "mvp" / "benchmark" / "user_case" / "cases"

PAIRS = {
    "2mkv":  dict(orig="D:/video/2.mkv",  edit="D:/video/1.mp4",
                  idx="2__4c6d4ab2"),
    "test3": dict(orig="D:/ProjectXIXI/test3/test3-om.mp4",
                  edit="D:/ProjectXIXI/test3/test3-ed.mp4",
                  idx="test3-om__074e2dcc"),
    "test4": dict(orig="D:/ProjectXIXI/test4/test4-om.mkv",
                  edit="D:/ProjectXIXI/test4/test4-ed.mp4",
                  idx="test4-om__eb686e0c"),
}

# (pair, probe_id, query_t, true_win, note)  — 与 feature_upgrade 同一探针集
QUERIES = [
    ("2mkv", "p26_hard", 76.8, (2808, 2811), "夜读书:CLS 硬混淆(0.31真/0.87错)"),
    ("2mkv", "p08_brother", 13.5, (1108, 1110), "瞭望塔机位:兄弟 1048-1050"),
    ("2mkv", "p08b_brother", 13.9, (1048, 1050), "士兵特写:兄弟 1108-1110"),
    ("2mkv", "p27_sign", 85.5, (1808, 1815), "WHAT字牌:同场景相似绿牌"),
    ("2mkv", "p01_easy", 0.8, (2417, 2428), "金属球准备(sanity 易例)"),
    ("2mkv", "p04_easy", 4.6, (833, 845), "峡谷航拍(sanity 易例)"),
    ("test3", "t3r10_adj", 56.25, (441.5, 447.0), "逃亡奔跑:真值≈444.5,错位447-449"),
    ("test4", "t4r01_obs", 1.25, (3335, 3350), "同质滑梯(观察)"),
    ("test4", "t4r13_obs", 66.0, (3335, 3350), "同质滑梯(观察)"),
]
BROTHER = {"p08_brother": (1048, 1050), "p08b_brother": (1108, 1110)}
HALF_DIST = 10.0
TOPK_DISTRACT = 40

# ---------------- 音频特征 ----------------
SR = 16000
N_FFT = 1024
HOP = 512
N_MELS = 64


def mel_filterbank() -> np.ndarray:
    def hz2mel(f):
        return 2595.0 * np.log10(1.0 + f / 700.0)

    def mel2hz(m):
        return 700.0 * (10.0 ** (m / 2595.0) - 1.0)

    mels = np.linspace(hz2mel(50.0), hz2mel(8000.0), N_MELS + 2)
    bins = np.floor((N_FFT + 1) * mel2hz(mels) / SR).astype(int)
    fb = np.zeros((N_MELS, N_FFT // 2 + 1))
    for i in range(N_MELS):
        l, c, r = bins[i], bins[i + 1], bins[i + 2]
        c = max(c, l + 1)
        r = max(r, c + 1)
        fb[i, l:c] = (np.arange(l, c) - l) / (c - l)
        fb[i, c:r] = (r - np.arange(c, r)) / (r - c)
    return fb


FB = mel_filterbank()
WIN = np.hanning(N_FFT).astype(np.float32)


def extract_audio(video: str, t0: float, dur: float) -> np.ndarray:
    cmd = [str(FFMPEG), "-v", "error", "-ss", f"{max(0.0, t0):.3f}",
           "-t", f"{dur:.3f}", "-i", video, "-vn", "-ac", "1", "-ar", str(SR),
           "-f", "f32le", "-"]
    raw = subprocess.run(cmd, capture_output=True, timeout=120)
    if raw.returncode != 0:
        raise RuntimeError(f"ffmpeg audio failed: {raw.stderr[:200]!r}")
    x = np.frombuffer(raw.stdout, dtype=np.float32)
    return x if len(x) else np.zeros(SR, np.float32)


def logmel(x: np.ndarray) -> np.ndarray:
    if len(x) < N_FFT:
        x = np.pad(x, (0, N_FFT - len(x)))
    n = 1 + (len(x) - N_FFT) // HOP
    idx = np.arange(N_FFT)[None, :] + HOP * np.arange(n)[:, None]
    spec = np.abs(np.fft.rfft(x[idx] * WIN, axis=1))
    return np.log(spec @ FB.T + 1e-6)


def norm_frames(m: np.ndarray) -> np.ndarray:
    m = m - m.mean(axis=0, keepdims=True)
    n = np.linalg.norm(m, axis=1, keepdims=True)
    return m / np.maximum(n, 1e-8)


def frame_votes(q: np.ndarray, c: np.ndarray, smooth: int = 3) -> np.ndarray:
    """每查询帧的最近邻(候选轴 ±smooth 帧 max 平滑后 argmax)相似度与位置。"""
    s = q @ c.T
    if smooth > 1:
        pad = np.pad(s, ((0, 0), (smooth, smooth)), mode="edge")
        s = np.stack([pad[:, k:k + s.shape[1]]
                      for k in range(2 * smooth + 1)], axis=0).max(axis=0)
    j = s.argmax(axis=1)
    return s[np.arange(len(q)), j], j


def diag_score(q: np.ndarray, c: np.ndarray) -> tuple[float, int]:
    """常速对角匹配:最大平均对角余弦及其偏移(帧)。要求覆盖 ≥60% 查询长。"""
    s = q @ c.T
    tq, tc = s.shape
    best, best_o = -1.0, 0
    for o in range(-(tq - 1), tc):
        i0, i1 = max(0, -o), min(tq, tc - o)
        if i1 - i0 < max(4, int(0.6 * tq)):
            continue
        m = float(s[i0:i1, np.arange(i0, i1) + o].mean())
        if m > best:
            best, best_o = m, o
    return best, best_o


def window_feats(video: str, a: float, b: float) -> np.ndarray:
    return norm_frames(logmel(extract_audio(video, a, b - a)))


# ---------------- Part A ----------------
def run_audio() -> list[dict]:
    out = []
    for pair, pid, qt, true_win, note in QUERIES:
        cfg = PAIRS[pair]
        feats = np.load(IDX_DIR / (cfg["idx"] + ".idx") / "features.npy")
        times = np.load(IDX_DIR / (cfg["idx"] + ".idx") / "times.npy")

        # 干扰窗:优先文档化兄弟/错位区;否则以真值窗均值特征为伪查询,
        # 取全索引 top-K 非真值高相似区聚 run(CLS 最易混淆处=音频须分辨处)
        distract = []
        if pid in BROTHER:
            distract.append(BROTHER[pid])
        if pid == "t3r10_adj":
            distract.append((447.0, 449.0))
        if distract:
            distract_wins = [(max(0.0, a - HALF_DIST), b + HALF_DIST)
                             for a, b in distract]
        else:
            # 无文档化干扰的探针(p26/p27/easy/test4):取真值窗外
            # CLS 全局能量最高的两个连续区做干扰(用真值中心帧特征)
            ctr = float(np.mean(true_win))
            sel = np.where((times >= true_win[0] - 1) & (times <= true_win[1] + 1))[0]
            qv = feats[sel].mean(axis=0)
            qv /= max(np.linalg.norm(qv), 1e-8)
            sims = feats @ qv
            cand = [int(i) for i in np.argsort(-sims)[:TOPK_DISTRACT]
                    if not (true_win[0] - HALF_DIST <= times[i] <= true_win[1] + HALF_DIST)]
            runs = []
            for t in sorted(float(times[i]) for i in cand):
                if runs and t - runs[-1][1] <= 5.0:
                    runs[-1][1] = t
                else:
                    runs.append([t, t])
            distract_wins = [(max(0.0, a - HALF_DIST), b + HALF_DIST)
                             for a, b in runs[:2]]

        q_edit = window_feats(cfg["edit"], max(0.0, qt - 1.5), qt + 1.5)
        true_ctx = window_feats(cfg["orig"], max(0.0, true_win[0] - HALF_DIST),
                                true_win[1] + HALF_DIST)

        def votes_in(qf, ctx, win, ctx_a):
            sims, j = frame_votes(qf, ctx)
            t = ctx_a + j * HOP / SR
            inside = (t >= win[0]) & (t <= win[1])
            return float(sims.mean()), float(inside.mean())

        mean_sim, frac_true = votes_in(q_edit, true_ctx, true_win,
                                       max(0.0, true_win[0] - HALF_DIST))
        wrong_stats = []
        for a, b in distract_wins:
            ctx = window_feats(cfg["orig"], a, b)
            ms, fr = votes_in(q_edit, ctx, (a + HALF_DIST, b - HALF_DIST), a)
            wrong_stats.append({"win": [round(a, 1), round(b, 1)],
                                "mean_sim": round(ms, 4), "frac_inside": round(fr, 4)})

        # 对照:源↔源自匹配(真值段做查询,±15s 上下文)
        qa = max(0.0, true_win[0] - 1.5)
        q_src = window_feats(cfg["orig"], qa, true_win[1] + 1.5)
        ctrl_sim, ctrl_frac = votes_in(q_src, true_ctx, true_win,
                                       max(0.0, true_win[0] - HALF_DIST))
        d, doff = diag_score(q_src, true_ctx)
        ctrl_diag_located = max(0.0, true_win[0] - HALF_DIST) + doff * HOP / SR

        d, doff = diag_score(q_edit, true_ctx)
        diag_located = max(0.0, true_win[0] - HALF_DIST) + doff * HOP / SR
        diag_in = true_win[0] - 1 <= diag_located <= true_win[1] + 1

        fw = max((w["frac_inside"] for w in wrong_stats), default=0.0)
        entry = {
            "id": pid, "pair": pair, "query_t": qt, "true_win": list(true_win),
            "note": note,
            "distract_wins": [w["win"] for w in wrong_stats],
            "edit_audio": {"mean_sim_true": round(mean_sim, 4),
                           "frac_true": round(frac_true, 4),
                           "frac_wrong_max": round(fw, 4),
                           "margin": round(frac_true - fw, 4)},
            "diag": {"located": round(diag_located, 1), "in_true": bool(diag_in)},
            "control_src_to_src": {"frac_true": round(ctrl_frac, 4),
                                   "diag_located": round(ctrl_diag_located, 1)},
            "wrong": wrong_stats,
        }
        out.append(entry)
        print(f"[{pid}] true={true_win} distractors={entry['distract_wins']}\n"
              f"  edit-audio: frac_true={frac_true:.3f} wrong_max={fw:.3f} "
              f"margin={entry['edit_audio']['margin']:+.3f} | diag@{diag_located:.1f}s "
              f"in_true={diag_in} | 源↔源对照 frac={ctrl_frac:.3f} diag@{ctrl_diag_located:.1f}s",
              flush=True)
    return out


# ---------------- Part B ----------------
def load_results(path: Path) -> list[dict]:
    d = json.loads(path.read_text(encoding="utf-8"))
    items = []
    for i, r in enumerate(d["results"]):
        if r.get("not_in_source") or r.get("excluded"):
            continue
        e, o = r.get("edited_segment"), r.get("original")
        if not e or not o:
            continue
        w = (float(o["candidate_start"]), float(o["candidate_end"]))
        if w[1] - w[0] <= 0.01:
            continue
        items.append({"idx": i, "edited": (float(e["start"]), float(e["end"])),
                      "orig": w, "conf": r.get("confidence", "LOW"),
                      "score": float(r.get("confidence_score") or 0.0)})
    return items


def apply_nonoverlap_prior(items: list[dict], overlap_frac: float = 0.8,
                           max_gap_dist: float = 15.0,
                           max_mover_width: float = 8.0
                           ) -> tuple[list[dict], list[dict]]:
    """近重叠才触发:窄段 ≥overlap_frac 被更高分段覆盖时,移入 ±max_gap_dist
    内最近可容纳空隙(居中);宽复合段(蒙太奇)不作 mover;无近空隙则不动。"""
    out = [dict(it) for it in items]
    moves = []
    order = sorted(out, key=lambda r: r["score"], reverse=True)
    placed: list[tuple[float, float]] = []
    for r in order:
        a, b = r["orig"]
        width = b - a
        cov = 0.0
        if width <= max_mover_width:
            for pa, pb in placed:
                o = min(b, pb) - max(a, pa)
                if o > 0:
                    cov = max(cov, o / width)
        if cov >= overlap_frac:
            gaps = []
            prev = 0.0
            for pa, pb in sorted(placed):
                gaps.append((prev, pa))
                prev = pb
            gaps.append((prev, 1e9))
            cands = [g for g in gaps if g[1] - g[0] >= width
                     and min(abs(g[0] - a), abs(g[1] - b)) <= max_gap_dist]
            if cands:
                g = min(cands, key=lambda g: min(abs(g[0] - a), abs(g[1] - b)))
                new_a = (g[0] + g[1]) / 2 - width / 2
                moves.append({"idx": r["idx"], "from": [round(a, 2), round(b, 2)],
                              "to": [round(new_a, 2), round(new_a + width, 2)],
                              "score": r["score"], "cover": round(cov, 3)})
                r["orig"] = (round(new_a, 2), round(new_a + width, 2))
            else:
                moves.append({"idx": r["idx"], "from": [round(a, 2), round(b, 2)],
                              "to": None, "score": r["score"],
                              "cover": round(cov, 3), "no_near_gap": True})
        placed.append(r["orig"])
    return out, moves


VERDICT = json.loads(
    (CASES / "test3_gt_adjudication_full.json").read_text(encoding="utf-8"))["segments"]


def verdict_kind(rno: int) -> str:
    v = VERDICT.get(f"r{rno}", "")
    if v.startswith("对") or v.startswith("用户判错"):
        return "对"
    for k in ("错", "部分", "勉强"):
        if v.startswith(k):
            return k
    return "其他"


def run_temporal() -> dict:
    report = {}
    # test3 用户修正基线 + 全量裁决对照(阈值扫描:几何先验可分性)
    t3 = load_results(T3_BASELINE)
    sweep = {}
    for frac in (0.5, 0.6, 0.7, 0.8):
        _, mv = apply_nonoverlap_prior(t3, overlap_frac=frac)
        det = [{**m, "verdict": verdict_kind(m["idx"])} for m in mv]
        r10 = next((m for m in det if m["idx"] == 10), None)
        sweep[frac] = {
            "moves": len(mv),
            "moves_on_correct": sum(1 for m in det if m["verdict"] == "对"),
            "r10_fixed": bool(r10 and r10.get("to")
                              and abs((r10["to"][0] + r10["to"][1]) / 2 - 444.5) <= 2.0),
            "detail": [{k: m[k] for k in ("idx", "verdict", "from", "to", "cover")}
                       for m in det],
        }
    _, moves = apply_nonoverlap_prior(t3)
    moved_detail = [{**m, "verdict": verdict_kind(m["idx"])} for m in moves]
    r10 = next((m for m in moved_detail if m["idx"] == 10), None)
    r10_fix = bool(r10 and r10["to"] and abs((r10["to"][0] + r10["to"][1]) / 2 - 444.5) <= 2.0)
    report["test3"] = {
        "n_results": len(t3), "n_moves": len(moves),
        "moves_on_correct": sum(1 for m in moved_detail if m["verdict"] == "对"),
        "r10_move": r10, "r10_fixed": r10_fix,
        "threshold_sweep": sweep,
        "moves": moved_detail,
    }
    print(f"[test3 prior] strict moves={len(moves)} r10_fixed={r10_fix}; "
          f"sweep=" + ", ".join(f"{k}:{v['moves']}mv/{v['moves_on_correct']}correct/"
                                f"r10={v['r10_fixed']}" for k, v in sweep.items()),
          flush=True)

    # test1/2/4 普查(现行管线结果)
    for name in ("test1", "test2", "test4"):
        p = CASES / f"_scene_v3_{name}_results.json"
        items = load_results(p)
        n_overlap_src = 0
        its = sorted(items, key=lambda r: r["orig"][0])
        for i in range(len(its) - 1):
            if its[i]["orig"][1] > its[i + 1]["orig"][0] + 0.01:
                n_overlap_src += 1
        _, mv = apply_nonoverlap_prior(items)
        report[name] = {"n_results": len(items), "src_overlaps": n_overlap_src,
                        "n_moves": len(mv)}
        print(f"[{name} prior] n={len(items)} src_overlaps={n_overlap_src} "
              f"moves={len(mv)}", flush=True)
    return report


# ---------------- Part C:冲突段邻域内容证据可用性 ----------------
def run_neighborhood() -> dict:
    """对实锤错位段(t3r10):真值是否在索引里有被压制但存在的独立证据峰?
    方法 = 编辑段帧 CLS 均值查询 vs 原片索引 ±40s 每秒 max sim 曲线。"""
    from research_feature_upgrade import load_models, embed_batch
    from media.ffmpeg import FFmpegIO

    ff = FFmpegIO(FFMPEG, FP)
    ms, _ = load_models()
    cfg = PAIRS["test3"]
    feats = np.load(IDX_DIR / (cfg["idx"] + ".idx") / "features.npy")
    times = np.load(IDX_DIR / (cfg["idx"] + ".idx") / "times.npy")
    q = embed_batch(ms, ff, cfg["edit"], [55.75, 56.25, 56.75]).mean(axis=0)
    q /= max(np.linalg.norm(q), 1e-8)
    sims = feats @ q
    curve = {}
    sel = (times >= 430) & (times <= 470)
    ts, ss = times[sel], sims[sel]
    for sec in range(430, 470):
        m = ss[(ts >= sec) & (ts < sec + 1)]
        if len(m):
            curve[sec] = round(float(m.max()), 4)
    entry = {
        "probe": "t3r10_adj", "query_edit_span": [55.5, 57.0],
        "true_approx": 444.5, "wrong": [447.0, 449.0],
        "true_region_peak": max(curve[s] for s in range(441, 447)),
        "wrong_region_peak": max(curve[s] for s in range(447, 450)),
        "curve_430_470": curve,
    }
    print(f"[t3r10 neighborhood] true_region_peak={entry['true_region_peak']} "
          f"wrong_region_peak={entry['wrong_region_peak']}", flush=True)
    return entry


def main() -> int:
    t0 = time.time()
    report = {"started": time.strftime("%Y-%m-%d %H:%M:%S")}
    if "--skip-audio" not in sys.argv:
        report["audio"] = run_audio()
    report["temporal"] = run_temporal()
    report["neighborhood"] = run_neighborhood()
    out = BENCH / "work" / "second_signal_probe_results.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"\nsaved {out}  total {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
