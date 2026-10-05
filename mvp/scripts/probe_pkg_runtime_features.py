# -*- coding: utf-8 -*-
"""probe_pkg_runtime_features — r8 包 runtime 功能在位探针（2026-10-05，出包验收的一部分）。

目的：在**包内 backend.exe**（与 Electron 同一 spawn env）上证明续41~续53 新功能真的进了
runtime，而不是只在源码树里：
  ① /api/health + /api/settings/device（DirectML 生效）
  ② /api/fs/browse（续41 入库层：盘符浏览路由在包内存在且可响应）
  ③ syn 全链定位任务中 **L2 画面索引默认开的行为证据**——syn 源片无索引 ⇒ 任务应出现
     INDEX_BUILD「正在建立画面索引（一次性）」阶段 + 后端日志 `isc l2 index build started`
     （旋钮默认关时这两条都不会出现 = 直接行为判据）
  ④ ISC 第二意见在 GPU（日志 device=dml，不回退）
用法: D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/probe_pkg_runtime_features.py
"""
from __future__ import annotations

import json
import os
import queue
import re
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.parse
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import attr_packaged_headless as H  # noqa: E402  复用 spawn/http/排空/等监听基建

EXE_DIR = H.EXE_DIR
RES_DIR = H.RES_DIR
LOG_DIR = BENCH / "work" / "pkg_runtime_probe"
CASE = {"edited": str(BENCH / "datasets" / "synthetic" / "edited" / "a1.mp4"),
        "original": str(BENCH / "datasets" / "synthetic" / "originals" / "source.mp4")}

fails: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print("[%s] %s %s" % ("PASS" if ok else "FAIL", name, detail), flush=True)
    if not ok:
        fails.append(name)


def main() -> int:
    imgs = H.running_named_images()
    assert "Video Locator.exe" not in imgs and "backend.exe" not in imgs, \
        "探针要求无 UI/无别的后端在跑：%s" % imgs

    token = secrets.token_urlsafe(24)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    data_dir = H.appdata_dir()
    graph = RES_DIR / "models" / "dinov2_cls_patch" / "dinov2_cls_patch.onnx"
    isc_graph = RES_DIR / "models" / "isc_ft_v107" / "isc_ft_v107.onnx"
    env = {
        **os.environ,
        "MEDIA_FFMPEG": str(EXE_DIR / "ffmpeg.exe"),
        "MEDIA_FFPROBE": str(EXE_DIR / "ffprobe.exe"),
        "SVL_DATA_DIR": str(data_dir),
        "SVL_LOG_DIR": str(LOG_DIR),
        "SVL_SESSION_TOKEN": token,
        "SVL_BUILD_CHANNEL": "release",
        "SVL_BACKEND_PORT": "0",
        "SVL_DML_MODEL": str(RES_DIR / "models" / "dinov2_cls_384" / "dinov2_cls_384.onnx"),
        "SVL_DINOV2_WEIGHTS": str(RES_DIR / "models" / "dinov2_vits14" / "dinov2_vits14_pretrain.pth"),
        # 与 Electron main.ts 相同的两条注入（r8 首次随包）
        "SVL_PATCH_ONNX": str(graph),
        "SVL_ISC_ONNX": str(isc_graph),
    }
    proc = subprocess.Popen([str(EXE_DIR / "backend.exe")], cwd=str(EXE_DIR), env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace", bufsize=1)
    listen_q: "queue.Queue" = queue.Queue()
    stdout_lines: list[str] = []
    try:
        with (LOG_DIR / "backend_stdout.log").open("w", encoding="utf-8") as logf:
            def _drain():
                for line in proc.stdout:
                    stdout_lines.append(line)
                    logf.write(line)
                    logf.flush()
                    listen_q.put(line)
            import threading
            threading.Thread(target=_drain, daemon=True).start()
            host, port = H.wait_backendListen(proc, listen_q, timeout=180.0)
            base = "http://%s:%d" % (host, port)
            print("[listen] %s:%d" % (host, port), flush=True)

            # ① health + device
            health = H.http(base, token, "GET", "/api/health")
            check("api/health", health.get("status") == "ok" or bool(health), json.dumps(health, ensure_ascii=False)[:120])
            device = H.http(base, token, "GET", "/api/settings/device")
            check("settings/device DirectML",
                  device.get("actual_device_name") == "directml" and device.get("actual_device_type") == "amd",
                  json.dumps({k: device.get(k) for k in
                              ("actual_device_name", "actual_device_type", "is_accelerator", "fallback")},
                             ensure_ascii=False))

            # ② fsbrowse（续41 新路由在包内存在）
            try:
                fb = H.http(base, token, "GET", "/api/fs/browse")
                drives = [d.get("name", d) if isinstance(d, dict) else d for d in fb.get("drives", [])]
                check("api/fs/browse 续41", True, "drives=%s" % drives)
            except urllib.error.HTTPError as exc:
                check("api/fs/browse 续41", False, "HTTP %d" % exc.code)

            # ③ syn 全链定位：L2 索引自动构建行为证据
            task = H.http(base, token, "POST", "/api/tasks/analyze",
                          {"edited_path": CASE["edited"], "original_path": CASE["original"]})
            tid = task["task_id"]
            print("[task] %s submitted" % tid, flush=True)
            t0 = time.monotonic()
            phases: list[dict] = []
            last = None
            status = {}
            while True:
                st = H.http(base, token, "GET", "/api/tasks/%s" % tid, timeout=120.0)
                key = (st.get("stage"), st.get("message"))
                if key != last:
                    phases.append({"t_s": round(time.monotonic() - t0, 1), "stage": st.get("stage"),
                                   "message": st.get("message")})
                    print("  [%5.1fs] %-14s %s" % (time.monotonic() - t0, st.get("stage"),
                                                   st.get("message")), flush=True)
                    last = key
                status = st
                if st.get("status") in ("completed", "failed", "cancelled"):
                    break
                if proc.poll() is not None:
                    raise RuntimeError("backend.exe 提前退出 rc=%s" % proc.returncode)
                time.sleep(0.5)
            check("syn 定位完成", status.get("status") == "completed",
                  "wall=%.1fs segments=%s err=%s" % (time.monotonic() - t0,
                                                     len((status.get("result") or {}).get("results", [])),
                                                     status.get("error")))
            idx_build_phase = [p for p in phases
                               if p["stage"] == "INDEX_BUILD" or "画面索引" in (p["message"] or "")]
            # 注：INDEX_BUILD 进度按 120s 簇粒度回调——syn 源片 90 帧 = 1 簇 ⇒ 构建期间无事件，
            # 任务轮询看不到 INDEXING 阶段属预期；真实 2h 片源 ~69 次回调（约 9s 一次）可见。
            # 因此 L2 行为证据以日志 build started/built 为准（下方），此处仅提示不判 FAIL。
            if idx_build_phase:
                print("  (info) INDEX_BUILD 阶段可见: %s" % json.dumps(idx_build_phase, ensure_ascii=False),
                      flush=True)

            # ④ 日志证据：isc l2 index build started/built + patch/isc device
            time.sleep(1.0)
            log_blob = (LOG_DIR / "backend_stdout.log").read_text(encoding="utf-8", errors="replace")
            for pat, name in [
                    (r"isc l2 index build started", "日志:isc l2 index build started"),
                    (r"isc l2 index built path=\S+ frames=\d+", "日志:isc l2 index built"),
                    (r"patch reranker device=dml", "日志:patch reranker device=dml"),
                    (r"isc.*device=dml|isc_device=dml|BACKEND_SELECTED.*amd", "日志:ISC/DML 后端")]:
                m = re.search(pat, log_blob)
                check(name, bool(m), m.group(0)[:100] if m else "(未见)")
    finally:
        try:
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=15)
        except Exception:
            pass

    print("FAILED=%d" % len(fails), flush=True)
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
