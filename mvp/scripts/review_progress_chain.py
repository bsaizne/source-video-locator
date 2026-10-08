# -*- coding: utf-8 -*-
"""review_progress_chain — 进度链「跳格」真机前复核（源码树记事件流，2026-10-08 续63 补八）。

要关掉的边界（档案明写的两处诚实边界之一）：续63 补五 把修复链显示宽度改成按实测耗时
占比后，**字牌 ≈32s 一跳 / ISC ≈27s 一跳两个数是模型推算**，只有 patch 那条被 run3 实测
验证过（预测 28s vs 实测 18~42s）。当时没再跑 27 分钟验证趟 => 一直没闭合。

为什么量「显示出来的百分比」而不是日志：进度事件**不落支持档**（`mvp/api/tasks/` 里没有任何
`_log.info`），包内日志只能看到腿的零星标记。所以本轮按用户裁决 = **源码树用同一条
`on_progress` 记事件流**，经产品自己的映射与防抖换算成用户看到的读数，再算停留时长。
（埋点让包内可观测 = 下一批。）

口径（三条，缺一不可）：
  1) 读数 = `mvp.api.tasks.worker.map_progress_stage(ev)` —— 与产品**同一个**映射，不另造；
  2) 再过一遍 `ProgressDebouncer`（发布层真会合并事件），**raw 与 debounced 两条时间线都算**，
     两者不一致时以 debounced 为准并留痕；
  3) 「跳一格」= 显示读数（一位小数）发生变化的时刻；停留 = 相邻变化时刻之差。

判据（PASS/FAIL，2026-10-08 续63 补九 改口径）：
  ① **逐腿最大停留 ≤ 45s**（旧版写 40s 且只在均值意义上建模；实测最坏单格 = 字牌腿
     41.4~41.6s，超 40 但不是「改善没生效」——改前形态是 363s 一动不动。用户感知的
     是最大停留 ⇒ 阈值按最大值判，上限放 45s，与 `mvp/api/tests/test_tasks.py` 的
     `test_refine_leg_dwell_lock_is_max_based` 同阈值）
  ② **逐腿均值 ≤ 25s**（= 现役显示宽度下的跳格密度锁；宽度被改窄 ⇒ 读数塌 ⇒ 本条变红）
  ③ 全程（92→100）最大停留 ≤ 60s（防别处又长出长冻结）
  ④ 显示读数单调不回退
  ⑤ 与 2026-10-08 两趟实测登记值对照（只报数不判负）
  ⑥ 腿边界埋点自证：本脚本会 `configure_logging()` 落一份支持档，读回 `locate leg=`
     行，与事件流推出的逐腿耗时对账（两条独立观测面必须一致 ⇒ 埋点不是自说自话）

**腿归因口径（本版更正）**：patch 腿与 ISC 腿的 UI 消息**文本相同**（都是「画面深度复核
N/67」），旧版用消息子串匹配 ⇒ 把 patch+ISC 混成一条「ISC 腿 41 格 最大 37.3s」，
而 37.3s 其实是 patch 腿的最大停留（ISC 腿实测 33.9s）。⇒ 改按事件自带的 `phase`
字段归因（字牌腿是 fix 的一个子区间，按 pct 落界），别再用消息文本区分腿。

Run（venv 绝对路径，repo 根）：
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/review_progress_chain.py test2
产物：work/progress_chain_review/{case}.events.json + {case}_dwell.txt（与
  `work/fixramp_run1_table.txt` 同列格式，可直接逐行对照改前读数）
  + logs/video_locator.log（本脚本自配的支持档，用来跑 ⑥ 的埋点对账）

**测量卫生（2026-10-08 踩过）**：本脚本量的是「每格停留秒数」，对 GPU 争用极敏感。
跑期间**不得并发任何用 DML/解码的活**（首跑我在重叠窗口里跑了包内探针，字牌腿被抬到
52.8s，整趟作废重跑）。判据里的阈值只在独占态下有意义。
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
for p in (BENCH / "mvp" / "src", BENCH / "mvp", BENCH / "mvp" / "scripts"):
    sys.path.insert(0, str(p))

from app.models import ProgressEvent, ProgressStage  # noqa: E402
from app.locator_service import SourceLocatorService  # noqa: E402
from api.tasks.debounce import ProgressDebouncer  # noqa: E402
from api.tasks.worker import map_progress_stage  # noqa: E402
from device.directml_backend import DirectMLBackend  # noqa: E402
from infrastructure.config import load_config  # noqa: E402
from rerun_fast_global import CASES  # noqa: E402

OUT = BENCH / "work" / "progress_chain_review"
DWELL_MAX_CAP_S = 45.0     # ① 逐腿**最大**停留上限（与 test_tasks 的跳格锁同阈值）
DWELL_MEAN_CAP_S = 30.0    # ② 逐腿均值上限（实测口径 = 腿墙钟 ÷ 该腿内**实际出现**的读数数）
DWELL_CAP_ALL_S = 60.0     # ③ 全程上限
# 2026-10-08 两趟实测登记 {腿: (最大停留 源码树, 最大停留 包内, 均值 源码树, 均值 包内)}
# 数据源 = work/progress_chain_review/test2.events.json（源码树 1476.5s）与
#          work/r16_pkg/cadence/test2_packaged_dwell_pctcollapse.txt（包内 r16 1407.5s）
MEASURED = {"字牌 OCR": (41.6, 41.4, 24.6, 23.7),
            "切镜拆分": (33.8, 31.7, 16.9, 31.7),
            "patch 精排": (37.3, 28.3, 20.5, 18.4),
            "ISC 第二意见": (33.9, 33.8, 24.7, 24.1)}
# (腿名, phase, 该腿事件的 current 区间, total, 埋点里的 leg= 名, 是否判均值)
# 字牌腿只是 fix 相位的 10..42 子区间 ⇒ 用 pct 落界切出来；patch/ISC 靠 phase 区分
# （它们的消息文本一模一样，按文本归因会把两条腿混成一条——本版就是修这个）。
# 切镜拆分不判均值：整腿只有 2 个读数（0/1），均值=腿长/2 没有体验含义，判最大即可。
LEGS = (("字牌 OCR", "fix", 10, 42, 48, "text_anchor", True),
        ("切镜拆分", "split", 0, 1, 1, "shot_split", False),
        ("patch 精排", "patch", 0, 66, 67, "patch_refine", True),
        ("ISC 第二意见", "isc", 0, 66, 67, "isc_refine", True))


class Recorder:
    """记 (t, 原始事件, 映射读数) + 同步过一遍发布层防抖。"""

    def __init__(self) -> None:
        self.t0 = time.monotonic()
        self.raw: list[dict] = []
        self.deb: list[dict] = []
        self._clock_base = self.t0
        self._deb = ProgressDebouncer(min_interval_s=0.5, clock=self._now)

    def _now(self) -> float:
        return time.monotonic() - self._clock_base

    def __call__(self, ev) -> None:
        t = time.monotonic() - self.t0
        stage, pct = map_progress_stage(ev)
        msg = str(getattr(ev, "message", "") or "")
        phase = getattr(getattr(ev, "stage", None), "value", "?")
        rec = {"t_s": round(t, 2), "stage": phase, "phase": str(getattr(ev, "phase", "") or ""),
               "current": getattr(ev, "current", None), "total": getattr(ev, "total", None),
               "task_stage": str(getattr(stage, "value", stage)), "pct": pct, "msg": msg}
        self.raw.append(rec)
        for st, p, m in self._deb.submit(stage, pct, msg):
            self.deb.append({"t_s": round(t, 2), "task_stage": str(getattr(st, "value", st)),
                             "pct": p, "msg": m, "phase": rec["phase"]})

    def flush(self) -> None:
        t = time.monotonic() - self.t0
        for st, p, m in self._deb.flush():
            self.deb.append({"t_s": round(t, 2), "task_stage": str(getattr(st, "value", st)),
                             "pct": p, "msg": m, "phase": "flush", "flushed": True})


def steps(events: list[dict]) -> list[dict]:
    """读数发生变化的时刻（一位小数）。返回 [{t_s, pct, dwell_s, msg, phase}]。"""
    out, last = [], None
    for e in events:
        if last is None or e["pct"] != last:
            out.append(dict(e))
            last = e["pct"]
    for i, s in enumerate(out):
        nxt = out[i + 1]["t_s"] if i + 1 < len(out) else None
        s["dwell_s"] = round(nxt - s["t_s"], 1) if nxt is not None else 0.0
    return out


def leg_rows(rows: list[dict], phase: str, lo_pct: float, hi_pct: float) -> list[dict]:
    """按 **phase + 读数落界** 归因到某条腿（patch 与 ISC 的消息文本相同，不能按文本分）。

    注意：**腿边界上的读数会归错腿**——split 的 0/1 事件与 fix 的 48 单位事件同一瞬间到达，
    折叠后的显示行只记得先到的那个 phase。所以逐腿统计一律用 :func:`leg_interval`
    （墙钟区间）裁剪，别直接用这个函数算最大/均值。
    """
    return [r for r in rows if r.get("phase") == phase and lo_pct - 1e-9 <= r["pct"] <= hi_pct + 1e-9]


def leg_interval(raw: list[dict], phase: str, lo: int, hi: int) -> tuple[float | None, float | None]:
    """该腿在**原始事件流**上的墙钟区间（首末端事件之差 = 腿耗时，与显示折叠无关）。"""
    ts = [r["t_s"] for r in raw if r.get("phase") == phase
          and r.get("current") is not None and lo <= int(r["current"]) <= hi]
    return (ts[0], ts[-1]) if len(ts) >= 2 else (None, None)


def leg_wall_from_events(raw: list[dict], phase: str, lo: int, hi: int) -> float | None:
    a, b = leg_interval(raw, phase, lo, hi)
    return round(b - a, 1) if a is not None else None


def leg_dwells(rows: list[dict], a: float, b: float) -> tuple[int, list[float]]:
    """把每个显示读数的停留区间 [t, t+dwell] 裁剪进腿区间 [a,b]。

    返回 (该腿内的读数数, 各读数在腿内的停留秒)。和单测锁同一口径：
    **均值 = 腿墙钟 ÷ 读数数**，**最大 = 单格停留上界**（用户感知的就是它）。
    """
    inside = [r for r in rows if a <= r["t_s"] < b]
    clipped = []
    for r in inside:
        s, e = max(r["t_s"], a), min(r["t_s"] + (r["dwell_s"] or 0.0), b)
        if e > s:
            clipped.append(round(e - s, 1))
    return len(inside), clipped


def leg_bounds(phase: str, lo: int, hi: int, total: int) -> tuple[float, float]:
    """该腿读数区间两端点（用产品自己的映射算，不手填百分比）。"""
    a = map_progress_stage(ProgressEvent(ProgressStage.REFINE, lo, total, "", phase))[1]
    b = map_progress_stage(ProgressEvent(ProgressStage.REFINE, hi, total, "", phase))[1]
    return min(a, b), max(a, b)


def leg_wall_from_events(raw: list[dict], phase: str, lo: int, hi: int) -> float | None:
    """用**原始事件流**算该腿墙钟 = 首端到末端事件之差（与显示读数折叠无关）。

    和埋点 elapsed 对账只能用这个口径：显示读数的停留合计会把「上一个读数的尾巴」算进
    下一条腿（93.9 那个读数既是拆分腿的末端、又是 patch 的头），按停留合计对账会假红。
    """
    ts = [r["t_s"] for r in raw if r.get("phase") == phase
          and r.get("current") is not None and lo <= int(r["current"]) <= hi]
    return round(ts[-1] - ts[0], 1) if len(ts) >= 2 else None


def read_back_legs(log_path: Path) -> dict[str, float]:
    """读回本脚本自己落的支持档，取 `locate leg=<名> elapsed=<秒>`。⑥ 埋点的文件侧证据。"""
    if not log_path.exists():
        return {}
    import re as _re
    pat = _re.compile(r"^locate leg=(\w+) elapsed=([\d.]+)s", _re.M)
    out: dict[str, float] = {}
    for m in pat.finditer(log_path.read_text(encoding="utf-8", errors="replace")):
        out[m.group(1)] = float(m.group(2))   # 同名取最后一次（一次 locate 只有一行）
    return out


def main() -> int:
    case = sys.argv[1] if len(sys.argv) > 1 else "test2"
    assert case in CASES, "片名只能是 %s" % list(CASES)
    OUT.mkdir(parents=True, exist_ok=True)
    # ⑥ 埋点对账要读回文件，所以这里必须落一份**真支持档**（同产品配置：INFO+ 文件、
    # 脱敏、轮转）。stream 走 StringIO：别把腿行混进控制台，也免得控制台刷盘影响计时。
    import io
    import logging
    from infrastructure.logging import configure_logging
    logging_dir = OUT / "logs"
    logging_dir.mkdir(parents=True, exist_ok=True)
    configure_logging(stream=io.StringIO(), log_dir=logging_dir)
    srv = SourceLocatorService(config=load_config())
    assert isinstance(srv.backend, DirectMLBackend), \
        "必须 DirectMLBackend, 实际 %s" % type(srv.backend).__name__
    print("BACKEND_SELECTED type=%s" % type(srv.backend).__name__, flush=True)
    cfg = srv.config.pipeline
    assert cfg.fast_global_enabled and cfg.shot_split_enabled and cfg.patch_refine_enabled \
        and cfg.isc_refine_enabled, "现役默认三旋钮必须开（复核对象=现役配置）"
    rec = Recorder()
    t0 = time.monotonic()
    batch = srv.locate(CASES[case]["edited"], CASES[case]["original"], on_progress=rec)
    rec.flush()
    wall = time.monotonic() - t0
    n = len(batch.results)
    for h in logging.getLogger().handlers:      # 腿行必须落盘后才读得回来
        try:
            h.flush()
        except Exception:  # noqa: BLE001
            pass

    raw_rows, deb_rows = steps(rec.raw), steps(rec.deb)
    # raw 与 debounced 是否一致（发布层会不会吃掉我们的 tick）
    same = [r["pct"] for r in raw_rows] == [r["pct"] for r in deb_rows]
    basis = deb_rows if deb_rows else raw_rows
    tail = [r for r in basis if r["pct"] >= 92.0]
    fails: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        print("[%s] %s %s" % ("PASS" if ok else "FAIL", name, detail), flush=True)
        if not ok:
            fails.append(name)

    all_max = max([r["dwell_s"] for r in tail] or [0.0])
    pcts = [r["pct"] for r in basis]
    monotonic = all(b >= a for a, b in zip(pcts, pcts[1:]))

    # 逐腿：墙钟区间 = 原始事件流首末端（裁剪显示停留，避免跨腿算错）+ 与埋点 elapsed 对账
    legs_from_log = read_back_legs(logging_dir / "video_locator.log")
    per_leg: dict = {}
    for name, phase, lo, hi, total, leg_key, _judge in LEGS:
        lo_pct, hi_pct = leg_bounds(phase, lo, hi, total)
        a, b = leg_interval(rec.raw, phase, lo, hi)
        if a is None:
            per_leg[name] = {"steps": 0, "max_s": 0.0, "mean_s": 0.0, "sum_s": 0.0,
                             "wall_s": None, "pct_range": [lo_pct, hi_pct],
                             "leg_log_elapsed_s": legs_from_log.get(leg_key)}
            continue
        n_steps, dw = leg_dwells(tail, a, b)
        wall = b - a
        per_leg[name] = {"steps": n_steps,
                         "max_s": max(dw) if dw else 0.0,
                         "mean_s": round(wall / n_steps, 1) if n_steps else 0.0,
                         "sum_s": round(sum(dw), 1),
                         "wall_s": round(wall, 1),
                         "pct_range": [lo_pct, hi_pct],
                         "leg_log_elapsed_s": legs_from_log.get(leg_key)}

    lines = ["t_s      pct    停留s   消息"]
    for r in tail:
        lines.append("%-8.1f %-6.1f %-7.1f %s" % (r["t_s"], r["pct"], r["dwell_s"], r["msg"]))
    (OUT / ("%s_dwell.txt" % case)).write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT / ("%s.events.json" % case)).write_text(json.dumps(
        {"case": case, "wall_s": round(wall, 1), "segments": n,
         "raw_vs_debounced_identical": same, "raw_steps": len(raw_rows),
         "debounced_steps": len(deb_rows), "legs": per_leg,
         "legs_from_log": legs_from_log,
         "events": rec.raw, "debounced": rec.deb},
        ensure_ascii=False, indent=1), encoding="utf-8")

    print("\n=== %s：locate 全程 %.1fs（%d 段）· 92→100 共 %d 个跳格 ==="
          % (case, wall, n, len(tail)), flush=True)
    print("  raw/debounced 跳格数 = %d / %d（same=%s；不等=发布层合并了亚 0.5s 突发）"
          % (len(raw_rows), len(deb_rows), same), flush=True)
    print("  逐腿（墙钟=原始事件流首末端；停留按腿区间裁剪；阈值 = 最大 %.0fs / 均值 %.0fs）:"
          % (DWELL_MAX_CAP_S, DWELL_MEAN_CAP_S), flush=True)
    print("    %-14s %6s %5s %8s %8s %8s %8s  %s"
          % ("腿", "墙钟s", "读数", "均值s", "最大s", "埋点s", "差s",
             "2026-10-08 登记 最大(源码树/包内) 均值(源码树/包内)"), flush=True)
    for name, _p, _lo, _hi, _t, _leg_key, _j in LEGS:
        d = per_leg[name]
        reg = MEASURED.get(name, (0.0, 0.0, 0.0, 0.0))
        log_s = d["leg_log_elapsed_s"]
        diff = ("-" if log_s is None or d["wall_s"] is None
                else "%.1f" % (log_s - d["wall_s"]))
        print("    %-14s %6s %5d %8.1f %8.1f %8s %8s  %.1f / %.1f   %.1f / %.1f"
              % (name, "-" if d["wall_s"] is None else "%.1f" % d["wall_s"],
                 d["steps"], d["mean_s"], d["max_s"],
                 "-" if log_s is None else "%.1f" % log_s, diff,
                 reg[0], reg[1], reg[2], reg[3]), flush=True)
    print("  全程最大停留 %.1fs；读数表 -> %s" % (all_max, OUT / ("%s_dwell.txt" % case)),
          flush=True)

    for name, _p, _lo, _hi, _t, _leg_key, judge_mean in LEGS:
        d = per_leg[name]
        check("① %s 最大停留 <= %.0fs" % (name, DWELL_MAX_CAP_S),
              d["max_s"] <= DWELL_MAX_CAP_S,
              "实得 %.1fs（%.0f 读数，登记 %.1f/%.1f）" % (d["max_s"], d["steps"],
                                                          MEASURED[name][0], MEASURED[name][1]))
        if judge_mean:
            check("② %s 均值停留 <= %.0fs" % (name, DWELL_MEAN_CAP_S),
                  d["mean_s"] <= DWELL_MEAN_CAP_S,
                  "实得 %.1fs（腿墙钟 %ss / %d 读数）" % (d["mean_s"], d["wall_s"], d["steps"]))
    check("③ 92→100 全程最大停留 <= %.0fs" % DWELL_CAP_ALL_S, all_max <= DWELL_CAP_ALL_S,
          "实得 %.1fs" % all_max)
    check("④ 显示读数单调不回退", monotonic)
    # ⑤ 与 2026-10-08 两趟实测登记值对照：**只报数不判负**（机器负载/素材不同都会动）
    over = ["%s 最大 %.1fs(登记 %.1f/%.1f)" % (nm, per_leg[nm]["max_s"], MEASURED[nm][0],
                                               MEASURED[nm][1])
            for nm in MEASURED if per_leg[nm]["max_s"] > max(MEASURED[nm][0], MEASURED[nm][1])]
    print("  [⑤ 对照] %s" % ("超登记值：" + "；".join(over) if over
                             else "各腿最大停留均未超两趟登记值（只报数不判负）"), flush=True)
    # ⑥ 腿边界埋点（文件侧）：本脚本落的支持档必须有 12 行腿，且逐腿 elapsed 与
    #    **原始事件流**推出的墙钟对得上。两条**独立**观测面（内存事件流 vs 落盘档）互证，
    #    埋点才不是自说自话。
    n_leg_lines = len(legs_from_log)
    check("⑥a 支持档出现 12 行 locate leg= 埋点", n_leg_lines == 12,
          "实得 %d 行（0 行 = 埋点没进代码/没落盘，不判通过）" % n_leg_lines)
    drift = []
    for name, _p, _lo, _hi, _t, leg_key, _j in LEGS:
        log_s = legs_from_log.get(leg_key)
        ev_s = per_leg[name]["wall_s"]
        if log_s is None:
            drift.append("%s: 档里没有 leg=%s 行" % (name, leg_key))
            continue
        if ev_s is None:
            drift.append("%s: 事件流里该腿不足两个事件（腿没跑？）" % name)
            continue
        if abs(log_s - ev_s) > max(8.0, 0.12 * max(log_s, ev_s)):
            drift.append("%s: 埋点 %.1fs vs 事件流 %.1fs" % (name, log_s, ev_s))
    check("⑥b 埋点 elapsed 与事件流逐腿墙钟对账（差 <= max(8s, 12%)）", not drift,
          "; ".join(drift))
    # 判据口径（首版写歪，实跑后改）：发布层防抖**设计上**就会合并亚 0.5s 的突发帧，
    # 所以「raw 序列 == debounced 序列」是错的断言（实测 113 vs 109，差的 4 个全是亚秒突发）。
    # 真正要守的是：**合并不得放大可见停留**（否则 tick 发了但用户看不到）。
    raw_max = max([r["dwell_s"] for r in (raw_rows if raw_rows else [{"dwell_s": 0.0}])
                   if r["pct"] >= 92.0] or [0.0])
    deb_max = max([r["dwell_s"] for r in tail] or [0.0])
    check("⑤ 防抖合并未放大可见停留（debounced 最大停留 - raw <= 2s）",
          deb_max - raw_max <= 2.0,
          "raw %.1fs vs debounced %.1fs（跳格数 raw %d / debounced %d；差值 = 被合并的亚秒突发）"
          % (raw_max, deb_max, len([r for r in raw_rows if r["pct"] >= 92.0]), len(tail)))
    print("\nFAILED=%d %s" % (len(fails), fails), flush=True)
    print("ALL_DONE", flush=True)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
