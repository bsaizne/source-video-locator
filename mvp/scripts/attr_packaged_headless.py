# -*- coding: utf-8 -*-
"""attr_packaged_headless — 打包态性能归因第二步：包内 backend.exe headless 单变量复跑。

背景（续35 归因第一步）：实验环境（venv 直跑）test2 ON 臂 = 23.3 min，打包 E2E 同素材
= 62.6 min，环境罚约 2.69x；但 E2E 那一轮同时开着 Electron UI 并有计算机操控在截屏观察，
而「打包后端本体吞吐」只被 1.mp4 建索引微对照（13.7 vs 12.7 fps）排除过一次。

本脚本用与 Electron 主进程完全相同的 env（release 通道 + 会话令牌 + 随机端口 + 包内
ffmpeg/模型 + 同一 SVL_DATA_DIR 以复用索引）直接拉起包内 backend.exe，**无 Electron /
无预览流 / 无自动化观察**，轮询 /api/tasks/{id} 记录 (时刻, stage, message)、每次轮询的
往返延迟、以及后端进程累计 CPU 时间，从而把「打包后端本体」与「UI/观察侧」两层罚分开。

对照口径（三者同素材、同优化代码、同索引复用）：
  实验室 venv  = 1396.7s（续35 归因，work/spl_patch_arms/on_test2.results.json）
  打包 E2E     = 3756.7s（r3 包，日志阶段分解见本脚本 summary 的 reference 段）
  打包 headless = 本脚本产出

用法（必须 venv 绝对路径 python）：
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/attr_packaged_headless.py [case] [poll_s]
产物：work/pkg_attr/headless_<case>.{events.csv,summary.json,results.json}
      work/pkg_attr/headless_<case>.backend_stdout.log
"""
from __future__ import annotations

import ctypes
import csv
import json
import os
import queue
import re
import secrets
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BENCH = Path(r"D:\claudework\benchmark")
VENV_PY = Path(r"D:\claudework\video-dedup-tool\.venv\Scripts\python.exe")
OUT = BENCH / "work" / "pkg_attr"
EXE_DIR = BENCH / "mvp" / "ui" / "release" / "win-unpacked" / "resources" / "backend"
RES_DIR = BENCH / "mvp" / "ui" / "release" / "win-unpacked" / "resources"

CASES = {
    "2mkv": {"edited": r"D:\video\1.mp4", "original": r"D:\video\2.mkv"},
    "test1": {"edited": r"D:\ProjectXIXI\test1\test1-ed.mp4",
              "original": r"D:\ProjectXIXI\test1\test1-om.mkv"},
    "test2": {"edited": r"D:\ProjectXIXI\test2\tset2-ed.mp4",
              "original": r"D:\ProjectXIXI\test2\test2-om.mp4"},
    "test3": {"edited": r"D:\ProjectXIXI\test3\test3-ed.mp4",
              "original": r"D:\ProjectXIXI\test3\test3-om.mp4"},
    # 接线冒烟用（秒级索引 + 短定位），不用于性能读数
    "syn": {"edited": str(BENCH / "datasets" / "synthetic" / "edited" / "a1.mp4"),
            "original": str(BENCH / "datasets" / "synthetic" / "originals" / "source.mp4")},
}

# E2E（r3 包，2026-10-01 02:45:09 起）从打包日志读出的阶段边界，仅作对照常量。
E2E_REFERENCE = {
    "total_s": 3756.7,
    "segmentation_s": 121.5,        # twopass fps=30 起 -> final segments=54
    "per_segment_loop_s": 19 * 60 + 45,   # 02:47:14 -> 03:06:59（末条 patch v2 nearfield）
    "post_knob_s": 42 * 60 + 46,    # 03:06:59 -> 03:47:45（无日志，仅任务轮询）
    "task_polls_per_min": 74,
}

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
LISTEN_PREFIX = "BACKEND_LISTEN"


def appdata_dir() -> Path:
    base = Path(os.environ["APPDATA"])
    return base / "Video Locator AI" / "data"


def process_cpu_seconds(pid: int) -> float | None:
    """后端进程累计 CPU 秒（kernel+user）。拿不到就返回 None，不影响主测量。"""
    try:
        k32 = ctypes.windll.kernel32
        handle = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return None
        Creation = ctypes.c_ulonglong
        ct = Creation(); et = Creation(); kt = Creation(); ut = Creation()
        ok = k32.GetProcessTimes(handle, ctypes.byref(ct), ctypes.byref(et),
                                 ctypes.byref(kt), ctypes.byref(ut))
        k32.CloseHandle(handle)
        if not ok:
            return None
        return (kt.value + ut.value) / 1e7
    except Exception:  # noqa: BLE001 - 观测用，失败不阻断
        return None


def running_named_images() -> list[str]:
    try:
        out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True,
                             text=True, encoding="utf-8", errors="replace", check=False).stdout
    except OSError:
        return []
    return [ln.split(",")[0].strip('"') for ln in out.splitlines() if ln.strip()]


def http(base: str, token: str, method: str, path: str, body: dict | None = None,
         timeout: float = 60.0):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(base + path, data=data, method=method)
    req.add_header("X-Locator-Session", token)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def spawn_stdout_drain(proc, logf, listen_q: "queue.Queue"):
    """后台线程持续排空 backend.exe 的 stdout/stderr。

    必须排空：uvicorn 每个请求都往 stderr 打一行，几 KB 的管道缓冲写满后会**阻塞后端**，
    那样测出来的就不是性能而是阻塞节奏。"""

    def _run():
        for line in proc.stdout:
            try:
                logf.write(line)
                logf.flush()
            except ValueError:      # 文件已关（进程结束时）
                pass
            if line.startswith(LISTEN_PREFIX):
                listen_q.put(line.strip())

    threading.Thread(target=_run, daemon=True).start()


def wait_backendListen(proc, listen_q: "queue.Queue", timeout: float) -> tuple[str, int]:
    """等 BACKEND_LISTEN 公告（后端绑定成功才会打印，宁缺毋假）。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError("backend.exe 启动即退出 rc=%s" % proc.returncode)
        try:
            line = listen_q.get(timeout=0.5)
        except queue.Empty:
            continue
        m = re.match(r"%s (\S+) (\d+)" % LISTEN_PREFIX, line)
        if m:
            return m.group(1), int(m.group(2))
    raise RuntimeError("backend.exe 未公告 BACKEND_LISTEN（启动失败或超时）")


def main() -> int:
    def arg(i: int, default: str) -> str:
        # 位置参数：case / poll_s / data_dir / mode。data_dir 传空串 = 用整包默认目录
        # （曾被 Path("") -> "." 误解析，把索引建进包体目录，故显式容错 + 落点断言）。
        return sys.argv[i] if len(sys.argv) > i else default

    case = arg(1, "test2")
    poll_s = float(arg(2, "2.0"))
    data_dir = Path(arg(3, "").strip()) if arg(3, "").strip() else appdata_dir()
    mode = arg(4, "packaged")
    assert mode in ("packaged", "venv"), "mode 只能是 packaged/venv"
    # mode=venv 时不启 backend.exe，而用同一套 env 起源码树后端（同数据目录、同 ffmpeg、
    # 同 HTTP 服务），用来分离「PyInstaller 冻结包」与「HTTP 服务进程形态」两种罚。
    mode = sys.argv[4] if len(sys.argv) > 4 else "packaged"
    assert mode in ("packaged", "venv"), "mode 只能是 packaged/venv"
    assert not str(data_dir.resolve()).startswith(str(RES_DIR.resolve())), \
        "SVL_DATA_DIR 不得落在包体资源目录内（派生产物会写进 win-unpacked）：%s" % data_dir
    assert case in CASES, "case 只能是 %s" % ",".join(CASES)
    paths = CASES[case]
    for p in (paths["edited"], paths["original"]):
        assert Path(p).exists(), "素材不存在: %s" % p

    OUT.mkdir(parents=True, exist_ok=True)
    tag = "headless" if mode == "packaged" else "venvhttp"
    events_csv = OUT / ("%s_%s.events.csv" % (tag, case))
    summary_json = OUT / ("%s_%s.summary.json" % (tag, case))
    results_json = OUT / ("%s_%s.results.json" % (tag, case))
    stdout_log = OUT / ("%s_%s.backend_stdout.log" % (tag, case))
    for f in (events_csv, summary_json, results_json, stdout_log):
        if f.exists():
            ts = time.strftime("%Y%m%d-%H%M%S")
            f.rename(f.with_name(f.name + ".%s.bak" % ts))  # 禁覆盖留痕

    # --- 干扰排除断言：不得有整包实例/别的后端在跑 -----------------------------
    imgs = running_named_images()
    blockers = [n for n in ("Video Locator.exe",) if n in imgs]
    other_backend = sum(1 for n in imgs if n == "backend.exe")
    assert not blockers and other_backend == 0, \
        "打包态归因要求无 UI/无别的后端：发现 %s / backend.exe x%d" % (blockers, other_backend)

    exe = EXE_DIR / "backend.exe"
    if mode == "packaged":
        assert exe.exists(), "包内后端不存在: %s" % exe
        cmd = [str(exe)]
    else:
        cmd = [str(VENV_PY), str(BENCH / "mvp" / "scripts" / "run_backend.py")]
    token = secrets.token_urlsafe(24)          # 只进 env，不落任何日志
    log_dir = OUT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    env = {
        **os.environ,
        "MEDIA_FFMPEG": str(EXE_DIR / "ffmpeg.exe"),
        "MEDIA_FFPROBE": str(EXE_DIR / "ffprobe.exe"),
        "SVL_DATA_DIR": str(data_dir),          # 与整包同一数据目录 => 复用已建索引
        "SVL_LOG_DIR": str(log_dir),
        "SVL_SESSION_TOKEN": token,
        "SVL_BUILD_CHANNEL": "release",
        "SVL_BACKEND_PORT": "0",
        "SVL_DML_MODEL": str(RES_DIR / "models" / "dinov2_cls_384" / "dinov2_cls_384.onnx"),
        "SVL_DINOV2_WEIGHTS": str(RES_DIR / "models" / "dinov2_vits14" / "dinov2_vits14_pretrain.pth"),
        # r5+ 打包态 main.ts 注入（2026-10-06 补齐）：缺 patch = 精排静默回退 CPU torch
        # 慢 2.6~3.9x；缺 ISC = 第二意见整体跳过。headless 必须与 Electron env 逐字对齐。
        "SVL_PATCH_ONNX": str(RES_DIR / "models" / "dinov2_cls_patch" / "dinov2_cls_patch.onnx"),
        "SVL_ISC_ONNX": str(RES_DIR / "models" / "isc_ft_v107" / "isc_ft_v107.onnx"),
    }
    if mode == "venv":
        # 源码树形态的导入路径：mvp.api（顶层 mvp 包）+ mvp/src 里的 app/domain/... 绝对导入
        env["PYTHONPATH"] = os.pathsep.join(
            [str(BENCH), str(BENCH / "mvp" / "src"), str(BENCH / "mvp")])
    for k in ("SVL_DML_MODEL", "SVL_DINOV2_WEIGHTS", "SVL_PATCH_ONNX", "SVL_ISC_ONNX"):
        assert Path(env[k]).exists(), "%s 缺失: %s" % (k, env[k])

    proc = subprocess.Popen(cmd, cwd=str(EXE_DIR), env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace", bufsize=1)
    listen_q: "queue.Queue" = queue.Queue()
    phases: list[dict] = []
    try:
        with stdout_log.open("w", encoding="utf-8") as logf:
            spawn_stdout_drain(proc, logf, listen_q)
            host, port = wait_backendListen(proc, listen_q, timeout=180.0)
            base = "http://%s:%d" % (host, port)
            print("[listen] %s:%d pid=%d" % (host, port, proc.pid), flush=True)

            health = None
            for _ in range(60):
                try:
                    health = http(base, token, "GET", "/api/health")
                    break
                except (urllib.error.URLError, TimeoutError):
                    time.sleep(1.0)
            assert health, "健康检查失败"

            device = http(base, token, "GET", "/api/settings/device")
            print("[device] %s" % json.dumps(device, ensure_ascii=False), flush=True)
            # device_name=directml / device_type=amd（DirectML 生效）。此调用会惰性构建
            # backend，构建成本因此落在计时窗口之外（E2E 那一轮约 3s 在窗口内）。
            assert (device["actual_device_name"] == "directml"
                    and device["actual_device_type"] == "amd"
                    and device["is_accelerator"] and not device["fallback"]), \
                "必须 DirectML 生效（测量前硬断言后端）：实际 %s" % device

            idx = http(base, token, "GET",
                       "/api/index/status?video_path=%s" % urllib.parse.quote(paths["original"]))
            print("[index] %s" % idx, flush=True)
            index_warm = idx.get("status")
            if index_warm != "VALID":
                t = time.monotonic()
                built = http(base, token, "POST", "/api/index",
                             {"video_path": paths["original"]}, timeout=3600.0)
                index_warm = "BUILT %.1fs frames=%s" % (time.monotonic() - t, built.get("frames"))
                print("[index] built %s" % index_warm, flush=True)

            # --- 计时窗口：只包住 analyze 任务（与两个参照臂同口径）-----------
            t0 = time.monotonic()
            cpu0 = process_cpu_seconds(proc.pid)
            task = http(base, token, "POST", "/api/tasks/analyze",
                        {"edited_path": paths["edited"], "original_path": paths["original"]})
            task_id = task["task_id"]
            print("[task] %s submitted at %.1f" % (task_id, t0), flush=True)

            rows: list[list] = []
            last_key = None
            latencies: list[float] = []
            status: dict = {}
            while True:
                tp = time.monotonic()
                st = http(base, token, "GET", "/api/tasks/%s" % task_id, timeout=120.0)
                lat_ms = (time.monotonic() - tp) * 1000.0
                latencies.append(lat_ms)
                el = time.monotonic() - t0
                cpu = process_cpu_seconds(proc.pid)
                key = (st.get("stage"), st.get("message"))
                if key != last_key:
                    phases.append({"t_s": round(el, 1), "stage": st.get("stage"),
                                   "progress": st.get("progress"),
                                   "message": st.get("message")})
                    print("[%.1fs] %s %s%% %s (lat %.0fms)"
                          % (el, st.get("stage"), st.get("progress"),
                             st.get("message"), lat_ms), flush=True)
                    last_key = key
                rows.append([round(el, 2), st.get("status"), st.get("stage"),
                             st.get("progress"), st.get("message"), round(lat_ms, 1),
                             None if cpu is None else round(cpu, 1)])
                status = st
                if st.get("status") in ("completed", "failed", "cancelled"):
                    break
                if proc.poll() is not None:
                    raise RuntimeError("backend.exe 中途退出 rc=%s" % proc.returncode)
                time.sleep(poll_s)

            wall = time.monotonic() - t0
            cpu1 = process_cpu_seconds(proc.pid)
            with events_csv.open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["t_s", "status", "stage", "progress", "message",
                            "poll_latency_ms", "backend_cpu_s"])
                w.writerows(rows)

            result = status.get("result") or {}
            if result:
                results_json.write_text(json.dumps(result, ensure_ascii=False, indent=1),
                                        encoding="utf-8")

            lat_sorted = sorted(latencies)
            n = len(lat_sorted)
            summary = {
                "arm": "packaged_headless" if mode == "packaged" else "venv_http_headless",
                "case": case,
                "backend_cmd": cmd[0],
                "package": ("Video-Locator-win-x64-20261001r4（backend.exe 2026-10-01 04:22 构建）"
                            if mode == "packaged" else "源码树 run_backend.py（同 env/同数据目录）"),
                "started_utc": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(t0)),
                "wall_s": round(wall, 1),
                "backend_cpu_s": None if None in (cpu0, cpu1) else round(cpu1 - cpu0, 1),
                "backend_cpu_ratio": None if None in (cpu0, cpu1, wall) else round((cpu1 - cpu0) / wall, 2),
                "poll_s": poll_s,
                "polls": n,
                "poll_latency_ms": {"p50": round(lat_sorted[n // 2], 1) if n else None,
                                    "p95": round(lat_sorted[int(n * 0.95)], 1) if n else None,
                                    "max": round(lat_sorted[-1], 1) if n else None},
                "index_state_before_run": index_warm,
                "device": device,
                "segments": len(result.get("results", [])),
                "task_status": status.get("status"),
                "task_error": status.get("error"),
                "phases": phases,
                "reference": {
                    "lab_venv_test2_on_s": 1396.7,
                    "packaged_e2e_r3": E2E_REFERENCE,
                },
            }
            summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=1),
                                    encoding="utf-8")
            print("[done] wall=%.1fs segments=%s cpu_ratio=%s -> %s"
                  % (wall, summary["segments"], summary["backend_cpu_ratio"],
                     summary_json.name), flush=True)
        return 0
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    sys.exit(main())
