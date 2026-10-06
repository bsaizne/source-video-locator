# -*- coding: utf-8 -*-
"""accept_packaged_bundle_mac — macOS(arm64) 包体内容验收，CI 内跑，**发布前门槛**。

为什么需要它：Windows 侧从 r5 起就有 `accept_packaged_bundle.py`（资产 sha256 + 包内 backend
冒烟 + 三条 GPU 判据），而 mac 包过去只验到「构建成功 + 静态库依赖 + ad-hoc 签名可验」，
**没做过一次包体实测**（我们自己的纪律：源码全绿 ≠ 包能用）。本脚本 = mac 版同口径验收，
判据按 mac 事实改写：DML 在 macOS 恒不可用，所以 GPU 断言换成 **MPS 是否真被选中**，
并把 patch/ISC 精排资产是否在位做成硬判据（当年 Windows 上"静默回退 CPU 慢 2.6~3.9×"
瞒了两周，同一形态在 mac 上目前**就是缺资产**，不能再让它静默）。

只在 macOS runner 上运行（GitHub Actions `macos-package` job，publish 之前一步）。

用法:
  python mvp/scripts/accept_packaged_bundle_mac.py ["<path to Video Locator.app>"]

退出码 0 = 全过；非 0 = 有失败项（最后一行 `FAILED=<n>`）。
豁免开关: SVL_MAC_ALLOW_MISSING_REFINE_ASSETS=1 ⇒ patch/ISC 资产缺失降级为 WARN
（只用于临时放行，档案里必须留痕是谁在哪次放的）。
"""
from __future__ import annotations

import hashlib
import json
import os
import queue
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

APP_DEFAULT = "mvp/ui/release/mac-arm64/Video Locator.app"
SMOKE_TIMEOUT_S = 900.0
INDEX_TIMEOUT_S = 900.0


def check(name: str, ok: bool, detail: str = "") -> bool:
    print("[%s] %s %s" % ("PASS" if ok else "FAIL", name, detail), flush=True)
    return ok


def warn(name: str, detail: str = "") -> None:
    print("[WARN] %s %s" % (name, detail), flush=True)


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def http(base: str, token: str | None, method: str, path: str,
         body: dict | None = None, timeout: float = 60.0):
    """带会话令牌的请求；token=None = 故意不带令牌（门禁负例）。"""
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(base + path, data=data, method=method)
    if token:
        req.add_header("X-Locator-Session", token)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def drain(proc: subprocess.Popen, logf, listen_q: "queue.Queue") -> None:
    """持续排空 stdout/stderr。管道写满会**阻塞后端**（Windows 侧同样的教训）。"""
    def _pump(stream, to_console):
        for line in iter(stream.readline, ""):
            if not line:
                break
            logf.write(line if isinstance(line, str) else str(line))
            logf.flush()
            if to_console:
                print("  " + line.rstrip()[:200], flush=True)
            if "BACKEND_LISTEN" in line:
                listen_q.put(line.strip())
        stream.close()

    threading.Thread(target=_pump, args=(proc.stdout, True), daemon=True).start()
    threading.Thread(target=_pump, args=(proc.stderr, False), daemon=True).start()


def gen_fixtures(ffmpeg: Path, work: Path) -> tuple[Path, Path, Path]:
    """包内 ffmpeg 造合成素材：20s 原片 + 其 6-12s 剪辑 + 同内容的中文名副本。

    顺带就是「包内 ffmpeg 可用」的实测。只判"任务跑完不崩"，不判定位精度。
    """
    src = work / "smoke_src.mp4"
    ed = work / "smoke_ed.mp4"
    ed_cjk = work / "中文 素材 测试.mp4"
    subprocess.run([str(ffmpeg), "-y", "-v", "error", "-f", "lavfi",
                    "-i", "testsrc2=size=320x240:rate=25:duration=20",
                    "-pix_fmt", "yuv420p", "-an", str(src)], check=True, timeout=300)
    subprocess.run([str(ffmpeg), "-y", "-v", "error", "-ss", "6", "-t", "6", "-i", str(src),
                    "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                    "-an", str(ed)], check=True, timeout=300)
    shutil.copyfile(ed, ed_cjk)
    return src, ed, ed_cjk


def wait_task(base: str, token: str, task_id: str, log_prefix: str) -> tuple[bool, dict]:
    t0 = time.monotonic()
    seen: set = set()
    while time.monotonic() - t0 < SMOKE_TIMEOUT_S:
        _, st = http(base, token, "GET", "/api/tasks/%s" % task_id, timeout=120.0)
        key = (st.get("stage"), st.get("progress"))
        if key not in seen:
            seen.add(key)
            print("  [%s] %s %s %s" % (log_prefix, st.get("status"), st.get("stage"),
                                       st.get("progress")), flush=True)
        if st.get("status") == "completed":
            return True, st
        if st.get("status") in ("failed", "cancelled"):
            print("  [%s] 终态 %s error=%s" % (log_prefix, st.get("status"),
                                               st.get("error")), flush=True)
            return False, st
        time.sleep(2.0)
    return False, {"error": "wait_task 超时 %ss" % SMOKE_TIMEOUT_S}


def main() -> int:
    if sys.platform != "darwin":
        print("本脚本只在 macOS runner 上跑（当前 %s）" % sys.platform, flush=True)
        return 2
    app = Path(sys.argv[1] if len(sys.argv) > 1 else APP_DEFAULT).expanduser().resolve()
    # 必须绝对路径：下面 Popen 带 cwd=backend_dir，POSIX 会先切 cwd 再解析 argv[0]，
    # 相对路径会指向不存在的位置（CI 首跑实测：is_file() 判 True 却在 Popen 抛 ENOENT）。
    res = app / "Contents" / "Resources"
    backend_dir = res / "backend"
    backend_bin = backend_dir / "backend"
    ffmpeg = backend_dir / "ffmpeg"
    ffprobe = backend_dir / "ffprobe"
    weights = res / "models" / "dinov2_vits14" / "dinov2_vits14_pretrain.pth"
    patch_onnx = res / "models" / "dinov2_cls_patch" / "dinov2_cls_patch.onnx"
    isc_onnx = res / "models" / "isc_ft_v107" / "isc_ft_v107.onnx"

    fails = 0

    def ck(name: str, ok: bool, detail: str = "") -> None:
        nonlocal fails
        if not check(name, ok, detail):
            fails += 1

    # ---- A 结构 ----
    ck("app bundle 存在", app.is_dir(), str(app))
    ck("包内 backend 在位", backend_bin.is_file(), str(backend_bin))
    ck("包内 ffmpeg 在位", ffmpeg.is_file(), str(ffmpeg))
    ck("包内 ffprobe 在位", ffprobe.is_file(), str(ffprobe))
    ck("DINOv2 权重随包", weights.is_file(),
       "size=%s sha256[:16]=%s" % (weights.stat().st_size if weights.is_file() else "-",
                                   sha256_of(weights) if weights.is_file() else "-"))
    if fails:
        print("结构缺项，后面跑不起来。FAILED=%d" % fails, flush=True)
        return 1

    # ---- B 精排资产（静默回退教训；mac 目前确实缺）----
    allow_missing = os.environ.get("SVL_MAC_ALLOW_MISSING_REFINE_ASSETS", "").strip() == "1"
    for label, files in (
            ("patch 双输出 ONNX（精排）", [patch_onnx, Path(str(patch_onnx) + ".data")]),
            ("ISC 第二意见 ONNX", [isc_onnx, Path(str(isc_onnx) + ".data")])):
        missing = [p.name for p in files if not p.is_file()]
        if not missing:
            detail = ", ".join("%s sha256[:16]=%s" % (p.name, sha256_of(p)) for p in files)
            check("%s 图+外部权重齐" % label, True, detail)
        elif allow_missing:
            warn("%s 缺 %s（已豁免）" % (label, missing),
                 "后果：精排静默回退 CPU torch / isc_refine 整体跳过")
        else:
            ck("%s 缺 %s" % (label, missing), False,
               "后果 = 精排静默回退 CPU（Windows 实测整条慢 2.6~3.9x）/ ISC 第二意见缺席；"
               "临时放行请设 SVL_MAC_ALLOW_MISSING_REFINE_ASSETS=1 并在档案留痕")

    data_dir = Path(tempfile.mkdtemp(prefix="svl-mac-accept-"))
    log_dir = data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(24)          # 只进 env，不落任何日志
    listen_q: "queue.Queue" = queue.Queue()

    env = dict(os.environ)
    env.update({
        "SVL_DATA_DIR": str(data_dir),
        "SVL_LOG_DIR": str(log_dir),
        "SVL_SESSION_TOKEN": token,
        "SVL_BUILD_CHANNEL": "release",
        "SVL_BACKEND_PORT": "0",
        "SVL_DINOV2_WEIGHTS": str(weights),
        "MEDIA_FFMPEG": str(ffmpeg),
        "MEDIA_FFPROBE": str(ffprobe),
        "PYTHONUNBUFFERED": "1",
    })
    if patch_onnx.is_file():
        env["SVL_PATCH_ONNX"] = str(patch_onnx)
    if isc_onnx.is_file():
        env["SVL_ISC_ONNX"] = str(isc_onnx)

    out_log = data_dir / "backend_stdout.log"
    proc = None
    try:
        with out_log.open("w", encoding="utf-8") as logf:
            try:
                proc = subprocess.Popen([str(backend_bin)], stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, text=True, encoding="utf-8",
                                        errors="replace", env=env, cwd=str(backend_dir))
            except OSError as exc:
                ck("包内 backend 可启动", False, "%r" % (exc,))
                print("FAILED=%d" % fails, flush=True)
                return 1
            drain(proc, logf, listen_q)
            try:
                line = listen_q.get(timeout=90.0)
                host, port = line.split()[1], line.split()[2]
                base = "http://%s:%s" % (host, port)
                ck("BACKEND_LISTEN 公告", True, base)
            except queue.Empty:
                ck("BACKEND_LISTEN 公告", False, "90s 内没等到，后端可能起不来")
                print("FAILED=%d" % fails, flush=True)
                return 1

            # ---- C/D 门禁 ----
            try:
                status, body = http(base, token, "GET", "/api/health", timeout=30.0)
                ck("health 200", status == 200, json.dumps(body)[:80])
            except Exception as exc:                          # noqa: BLE001
                ck("health 200", False, repr(exc))

            # /api/health 属放行路径，不能当无令牌负例 ⇒ 用 settings/device
            try:
                http(base, None, "GET", "/api/settings/device", timeout=20.0)
                ck("无令牌请求被拒", False, "居然返回 200")
            except urllib.error.HTTPError as exc:
                ck("无令牌请求被拒", exc.code == 401, "rc=%s" % exc.code)

            # ---- E 端到端 locate（合成素材，判"跑完不崩"）----
            src, ed, ed_cjk = gen_fixtures(ffmpeg, data_dir)
            try:
                _, built = http(base, token, "POST", "/api/index",
                                {"video_path": str(src)}, timeout=INDEX_TIMEOUT_S)
                ck("包内 backend 建索引", True, "resp=%s" % json.dumps(built)[:120])
            except Exception as exc:                          # noqa: BLE001
                ck("包内 backend 建索引", False, repr(exc))
                src = ed = ed_cjk = None

            if src is not None:
                for tag, edited in (("locate", ed), ("locate 中文路径", ed_cjk)):
                    try:
                        _, task = http(base, token, "POST", "/api/tasks/analyze",
                                       {"edited_path": str(edited), "original_path": str(src)},
                                       timeout=60.0)
                        ok, st = wait_task(base, token, task["task_id"], tag)
                        segs = len(((st.get("result") or {}).get("results") or []))
                        ck("%s 任务完成" % tag, ok, "结果段=%d" % segs)
                    except Exception as exc:                  # noqa: BLE001
                        ck("%s 任务完成" % tag, False, repr(exc))

            # ---- F 设备判据：MPS 真被选中（不是 DML、也不是静默 CPU）----
            proc.terminate()
            time.sleep(2.0)
            text = ""
            # 设备行既可能进 SVL_LOG_DIR 的文件日志，也可能只在 stdout（Windows 侧验收
            # 当初读的就是 stdout 那份）⇒ 两处都扫，避免判据因"读错地方"而假红。
            for lf in [out_log] + sorted(log_dir.glob("*.log")):
                if lf.is_file():
                    text += lf.read_text(encoding="utf-8", errors="replace")
            ck("日志出现 backend selected=mps", "backend selected=mps" in text,
               "" if "backend selected=mps" in text else
               "未见 MPS 选中行；fallback 线索=%s" % (
                   [l for l in text.splitlines() if "fallback" in l or "unavailable" in l][-3:]))
            for kw in ("UnicodeDecodeError", "ASCII", "codec can't decode"):
                if kw in text and "中文" in text:
                    warn("日志含解码告警", kw)
            if fails:
                # 失败必须把包内后端日志尾部打到 job console：run #26/#27 实测只有
                # 通用话术 LOC-1107 时，CI 侧完全看不到真因（本地是靠 traceback 才定位到
                # isc_refine 的片尾越界）。
                tail = [l for l in text.splitlines() if l.strip()][-60:]
                print("---- 包内后端日志尾部（供定位真因）----", flush=True)
                for l in tail:
                    print("  " + l[:240], flush=True)
    finally:
        if proc is not None and proc.poll() is None:
            proc.kill()
        shutil.rmtree(data_dir, ignore_errors=True)

    print("FAILED=%d" % fails, flush=True)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
