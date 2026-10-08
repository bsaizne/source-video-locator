# -*- coding: utf-8 -*-
"""review_packaged_support_log — 包内**支持档**（video_locator.log）事后复核（2026-10-08 续63 补八）。

为什么要这条：续63 补二 修掉「隔离子进程不走 ASGI lifespan => `configure_logging()` 没人调 =>
包内 stdout 与支持档一起缺整段分析记录」，验收是在 **stdout** 上断言的
（`accept_packaged_bundle.py` 那条「子进程 INFO 进得到包内」）。但售后真正拿到的是
**落盘的支持档**（`/api/logs/download` 打 zip 发客服），文件侧此前没被机器核过。
本脚本 = 拿一份真实支持档（用户自然运行后下载/自查的那份）做文件侧复核，随时可跑。

复核六面：
  A 隔离配对：每个 `isolated child started` 是否有同 task_id 的 `isolated child booted`
    （缺 = 子进程 INFO 没进支持档 = 售后档缺整段分析过程，正是续63 抓的那个缺陷形态）；
    `reaped exitcode` 分布（0 = 正常收割；-15 = 被 terminate 吞尾；其它 = 子进程崩）。
  B 会话账：`locate started/finished`、`analysis started`、`index started/finished` 配对与时长。
  C 腿标记：`patch_refine:` / `isc_refine:` / `text anchor promoted` / `consecutive offsets`
    / `degradation gate` 计数（= 埋点进包之前支持档能看到的修复链痕迹）。
  C2 腿边界埋点（2026-10-08 续63 补九 ①）：`locate refine start` 开关行 + 每 locate 12 行
    `locate leg=<名> elapsed=… units=a->b/48 chain=…`。0 行只判 **N/A**（早于埋点的档、
    或现役 r16 包都没有），不判通过；有行则查行数/顺序/刻度单调 + 「腿耗时合计
    不超过会话 elapsed」。=> 售后按档就能回答「进度停在哪条腿、吃了多少秒」。
  D ERROR 信噪比：按异常类型聚类，单列 asyncio proactor 连接重置（`WinError 10054`）——
    它在真实档里是**噪声不是故障**（485/492 条），同批已降级为 DEBUG（续63 补九 ②）；
    新档若还出现 = 跑的仍是降噪之前的包。
  E 基本盘：行数、时间跨度、轮转备份清单。

Run（venv 绝对路径）：
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/review_packaged_support_log.py
  ... review_packaged_support_log.py --log "C:\\Users\\<u>\\AppData\\Roaming\\Video Locator AI\\logs\\video_locator.log"
  ... review_packaged_support_log.py --out work/support_log_review/report.json
退出码：A 面任一不成立 => 1；其余只报数。
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

DEFAULT_LOG = Path(r"C:\Users\Bsaizne\AppData\Roaming\Video Locator AI\logs\video_locator.log")
LINE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) (\w+)\s+module=(\S+) "
                     r"session=(\S+) (.*)$")
TS = "%Y-%m-%d %H:%M:%S,%f"
fails: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print("[%s] %s %s" % ("PASS" if ok else "FAIL", name, detail), flush=True)
    if not ok:
        fails.append(name)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default=str(DEFAULT_LOG))
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[2]
                                         / "work" / "support_log_review" / "report.json"))
    args = ap.parse_args()
    p = Path(args.log)
    if not p.exists():
        print("支持档不存在：%s（用户还没在包内跑过，或路径被 SVL_LOG_DIR 覆盖）" % p)
        return 2
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    parsed, unparsed = [], 0
    for l in lines:
        m = LINE_RE.match(l)
        if not m:
            unparsed += 1
            continue
        ts, lvl, mod, sid, msg = m.groups()
        parsed.append({"t": datetime.strptime(ts, TS), "lvl": lvl, "mod": mod,
                       "sid": sid, "msg": msg})
    print("支持档 %s\n  行数=%d 可解析=%d 续行/未匹配=%d" % (p, len(lines), len(parsed), unparsed))
    if parsed:
        print("  跨度 %s -> %s" % (parsed[0]["t"], parsed[-1]["t"]))
    backups = sorted(x.name for x in p.parent.glob(p.name + "*") if x != p)
    print("  同目录其它日志/轮转备份：%s" % (backups or "无"))

    # ---- A 隔离配对 ----
    started = dict()      # task_id -> pid
    booted = set()
    reaped: Counter = Counter()
    tracebacks = []
    for e in parsed:
        m = re.search(r"task (\S+) isolated child started pid=(\d+)", e["msg"])
        if m:
            started[m.group(1)] = int(m.group(2))
            continue
        m = re.search(r"task (\S+) isolated child booted pid=(\d+)", e["msg"])
        if m:
            booted.add(m.group(1))
            continue
        m = re.search(r"task (\S+) isolated child reaped exitcode=(-?\d+)", e["msg"])
        if m:
            reaped[m.group(2)] += 1
            continue
        if "child traceback" in e["msg"]:
            tracebacks.append(e["msg"][:160])
    print("\n=== A 隔离子进程（文件侧）===")
    print("  started=%d booted=%d reaped=%s traceback 行=%d"
          % (len(started), len(booted), dict(reaped), len(tracebacks)))
    missing = sorted(set(started) - booted)
    # 空跑不算通过：任务隔离 2026-10-07（续63）才上线，早于它的支持档**必然**一条隔离行都没有；
    # 把「0 started / 0 缺」报成 PASS 就是自报门禁（同 续63 补五 双 typecheck 那类错）。
    if not started:
        print("[N/A] A1/A2 不判：本档里**没有任何隔离行**（该档早于任务隔离上线，"
              "或这些运行没走包内任务路径）=> 文件侧子进程日志这条仍未实测，别当已验收")
    else:
        check("A1 每个 started 都有同 task_id 的 booted（子进程 INFO 进得到支持档）",
              not missing, "缺 %d 个：%s" % (len(missing), missing[:5]))
        check("A2 收割退出码只有 0（-15 = 被 terminate 吞尾；其它 = 崩）",
              set(reaped) <= {"0"}, "分布 %s" % dict(reaped))

    # ---- B 会话账 ----
    ev: dict = {}
    locate_rows = []
    for e in parsed:
        m = re.search(r"locate started edited=(\S+) refine=(\S+)", e["msg"])
        if m:
            ev[e["sid"]] = {"edited": m.group(1), "refine": m.group(2), "t0": e["t"]}
            continue
        if "locate finished" in e["msg"]:
            r = ev.pop(e["sid"], None)
            m2 = re.search(r"elapsed=([\d.]+)s", e["msg"])
            locate_rows.append({"edited": (r or {}).get("edited", "?"),
                                "refine": (r or {}).get("refine", "?"),
                                "elapsed_s": float(m2.group(1)) if m2 else None})
    idx_pairs = [e["msg"] for e in parsed if "index finished" in e["msg"]]
    print("\n=== B 会话账 ===")
    print("  locate 完成配对 %d 次；index finished %d 次；未闭合 locate（崩/取消）%d 个"
          % (len(locate_rows), len(idx_pairs), len(ev)))
    for r in locate_rows[-6:]:
        print("    %s refine=%s elapsed=%ss" % (r["edited"], r["refine"], r["elapsed_s"]))

    # ---- C 腿标记 ----
    marks = ("patch_refine:", "isc_refine:", "text anchor promoted", "consecutive offsets",
             "degradation gate", "patch v2 nearfield", "isc refine device",
             "patch reranker device")
    print("\n=== C 修复链可观测标记 ===")
    cnt = {k: sum(1 for e in parsed if k in e["msg"]) for k in marks}
    for k, v in cnt.items():
        print("  %-26s %d" % (k, v))

    # ---- C2 腿边界埋点（2026-10-08 续63 补九 ①）----
    # 埋点之前进度事件**完全不落日志**，售后问「进度卡住」只能靠 C 面这些腿内自带行猜。
    # 现每腿完成时落一行 `locate leg=<名> elapsed=<秒> units=<a>-><b>/48 chain=<累计秒>`，
    # 链首另有 `locate refine start … legs=<12 个开关>` 一行。⇒ 按档即可复现「哪条腿吃了
    # 多少墙钟」，与 UI 读数是同一份刻度。
    LEG_NAMES = ("global_anchor", "dense_recheck", "text_anchor", "seq_rerank",
                 "temporal_repair", "conflict_rerank", "temporal_ambiguity",
                 "consecutive_resolve", "degradation_gate",
                 "shot_split", "patch_refine", "isc_refine")
    leg_pat = re.compile(r"^locate leg=(\w+) elapsed=([\d.]+)s units=(\d+)->(\d+)/(\d+) "
                         r"chain=([\d.]+)s$")
    by_sid: dict = {}
    chain_starts = 0
    for e in parsed:
        if e["msg"].startswith("locate refine start"):
            chain_starts += 1
        m = leg_pat.match(e["msg"])
        if m:
            by_sid.setdefault(e["sid"], []).append(
                {"leg": m.group(1), "elapsed": float(m.group(2)),
                 "units": (int(m.group(3)), int(m.group(4))), "chain": float(m.group(6))})
    print("\n=== C2 腿边界埋点（一次 locate 应 12 行腿 + 1 行开关汇总）===")
    print("  腿行数合计=%d，涉及会话=%d，refine start 行=%d"
          % (sum(len(v) for v in by_sid.values()), len(by_sid), chain_starts))
    if not by_sid:
        # 0 行不判通过，也不判失败：早于埋点上线的档（含**现役 r16**）本来就没有这些行。
        print("[N/A] 本档没有任何腿边界行 => 该档早于埋点上线（埋点本批进源码树，"
              "下一次出包才进包）。别把它当「埋点已实测」。")
    else:
        bad_n = {s: len(v) for s, v in by_sid.items() if len(v) != len(LEG_NAMES)}
        check("C2a 每个有埋点的会话都落满 %d 行腿" % len(LEG_NAMES), not bad_n,
              "行数异常会话 %s" % list(bad_n)[:5])
        bad_seq = []
        for s, v in by_sid.items():
            if [x["leg"] for x in v] != [n for n in LEG_NAMES if n in {y["leg"] for y in v}]:
                bad_seq.append(s)
            units = [x["units"][1] for x in v]
            if units != sorted(units):
                bad_seq.append(s + "(units 回退)")
            chain = [x["chain"] for x in v]
            if chain != sorted(chain):
                bad_seq.append(s + "(chain 回退)")
        check("C2b 腿顺序/刻度/累计耗时单调", not bad_seq, "异常 %s" % bad_seq[:5])
        top = sorted(((max((x["elapsed"] for x in v), default=0.0), s)
                      for s, v in by_sid.items()), reverse=True)[:3]
        print("  各会话最慢单腿耗时 top3（秒）：%s" % [(round(t, 1), s) for t, s in top])
        # 埋点的 elapsed 合计应≈该会话 locate finished 的 elapsed（差 = 段循环/索引等链外时间，
        # 所以只做「合计 <= elapsed + 1s」的单向体检，超过即埋点计时写错）。
        fin: dict = {}
        for e in parsed:
            m = re.search(r"elapsed=([\d.]+)s", e["msg"]) if "locate finished" in e["msg"] else None
            if m:
                fin[e["sid"]] = float(m.group(1))
        over = [(s, round(sum(x["elapsed"] for x in v), 1), fin[s])
                for s, v in by_sid.items() if s in fin
                and sum(x["elapsed"] for x in v) > fin[s] + 1.0]
        check("C2c 腿耗时合计不超过会话 locate elapsed", not over, "超出 %s" % over[:5])

    # ---- D ERROR 信噪比 ----
    errs = [e for e in parsed if e["lvl"] in ("ERROR", "CRITICAL")]
    kinds: Counter = Counter()
    for e in errs:
        m = re.search(r"(\w+Error|Exception|Warning)(?::|$)", e["msg"])
        kinds[(m.group(1) if m else e["msg"][:40])] += 1
    proactor = sum(1 for e in errs if "Exception in callback _Proactor" in e["msg"])
    print("\n=== D ERROR 面 ===")
    print("  ERROR/CRITICAL 行 %d；其中 asyncio proactor 连接重置 %d 行" % (len(errs), proactor))
    print("  分类 top8：%s" % json.dumps(dict(kinds.most_common(8)), ensure_ascii=False))
    if proactor and errs and proactor == len(errs):
        print("  [info] 支持档里的 ERROR **全部**是 proactor 噪声（客户端强关连接），"
              "无真实故障行 —— 但它会淹没支持人员判断，属降噪欠账")
    if proactor:
        # 降噪（2026-10-08 续63 补九 ②）：这类记录在 configure_logging 里降级为 DEBUG，
        # 支持档不再收录。⇒ **新档**里还能看到就说明跑的仍是旧包（<= r16），
        # 而老档（本档跨度自 2026-08-27）留着历史噪声是正常现象，不是回归。
        print("  [info] 已上线降噪：ConnectionReset/BrokenPipe + _call_connection_lost + "
              "WinError 10053/10054/10058 降级 DEBUG（调试档 SVL_LOG_DEBUG=1 仍保留）。"
              "本档这些行 = 降噪进包之前的历史。")


    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "log": str(p), "lines": len(lines), "parsed": len(parsed),
        "span": [str(parsed[0]["t"]) if parsed else None, str(parsed[-1]["t"]) if parsed else None],
        "isolated": {"started": len(started), "booted": len(booted),
                     "missing_boot": missing, "reaped": dict(reaped),
                     "tracebacks": tracebacks[:5],
                     "verdict": ("NOT_EXERCISED（档内无隔离行，文件侧未实测）"
                                 if not started else "EXERCISED")},
        "locate": locate_rows, "index_finished": len(idx_pairs),
        "markers": cnt,
        "leg_instrumentation": {"sessions": len(by_sid),
                                "leg_lines": sum(len(v) for v in by_sid.values()),
                                "refine_start_lines": chain_starts,
                                "expected_legs_per_locate": len(LEG_NAMES),
                                "verdict": ("ABSENT（档早于埋点/跑的是 <=r16 包）"
                                            if not by_sid else "PRESENT")},
        "errors_total": len(errs), "errors_proactor": proactor,
        "error_kinds": dict(kinds), "fails": fails}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print("\n留证 -> %s" % out)
    print("FAILED=%d %s" % (len(fails), fails))
    print("ALL_DONE")
    return 1 if fails else 0


if __name__ == "__main__":
    sys_exit = main()
    raise SystemExit(sys_exit)
