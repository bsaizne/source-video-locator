# Release 测试（RELEASE_TEST）

本文件汇总 Video Locator AI 桌面版的发布前验证：免安装运行、启动、后端生命周期、完整管线、
性能、打包体积与已知限制。**后端/打包层已实测**（本机 Windows + RX 6750 GRE + DirectML）；
安装器（NSIS）已按用户拍板移除（2026-08-27），只交付免安装 `win-unpacked/Video Locator.exe`。

## 1. 免安装运行测试

> 产物 `mvp/ui/release/win-unpacked/Video Locator.exe`（免安装，双击即用）。无需安装器。

## 2. 启动测试

- dev：`npm run dev`（vite 5173）+ 开发者自跑 `uvicorn mvp.api.main:app --port 8765`；
  Electron 健康检查 `GET /api/health` → `{"status":"ok","version":"0.1"}`。离线弹「后端离线」。
- prod：`app.isPackaged` 时 spawn `resources/backend/backend.exe`（PyInstaller onedir），
  `MEDIA_FFMPEG/MEDIA_FFPROBE` 指向打包内二进制，`waitForHealth` 30s 内轮询通过。

## 3. Backend 生命周期

**已实测**（打包后端 `backend.exe`）：

| 检查 | 结果 |
| --- | --- |
| `GET /api/health` | `200 {"status":"ok","version":"0.1"}` |
| 启动日志 | `module=api session=<sid> GET /api/health` |
| 进程自动退出 | `kill` 后无残留（应用用 `before-quit→stopBackend()`） |

## 4. 完整管线冒烟

**后端/服务层实测**（`mvp/benchmark/release/`，合成 `testsrc` 源 + 编辑片段，directml）：

[`result/release_smoke_result.json`](../mvp/benchmark/release/result/release_smoke_result.json) —
index / analysis / preview / export 四段，均 success。管线：原片索引 → 编辑侧抽帧 → 切分 →
候选检索 → 精定位 → 置信 → 结果 → 预览 → 导出。

**WebSocket 进度**：`/ws/progress/{task_id}` 已实现并测（后端 `test_progress` 4 项；前端
`subscribeProgress` WS 一次重连）。真实任务推送阶段级帧 + `{cancel}`。

> 注：合成测试片 shot 结构简单（常 1 个低置信段），用于验证**管线可跑通**，不代表真实影片
> 的定位精度。

## 5. 性能基准

[`result/benchmark_result.json`](../mvp/benchmark/release/result/benchmark_result.json)，
由 `mvp/benchmark/release/benchmark_release.py --durations 600 3600 7200` 生成（本机 directml）。

| 项目 | 结果 |
| --- | --- |
| 索引 10min（300 帧） | **23.96s**（~12.5 fps） |
| 索引 60min（1800 帧） | **135.22s**（~13.3 fps） |
| 索引 120min（3600 帧） | **270.68s**（~13.3 fps） |
| 分析（10min 源，1 段） | total_time≈3.35s，embedding≈3.22s（ONNX 冷启动），检索/定位/置信<0.01s |
| 预览（抽 20s） | ffmpeg_time≈0.4s，输出≈100KB |

> 索引跨时长**近线性扩展**（~13 fps 稳定），良好。内存/CPU 未插桩（venv 无 psutil）；源为
> 合成片（代表性见 README）；embedding 冷启动占分析耗时大头。

## 6. Bundle 体积

`resources/backend` = **845 MiB**（初始 946 MiB，剪枝省 ~101 MiB）。详见
[`bundle_optimization_report.md`](bundle_optimization_report.md) 与
[`bundle_report.md`](bundle_report.md)。推断：torch 374M + opencv 112M + onnxruntime 63M +
numpy 27M 为必需；scipy/pandas/PIL/onnx 已剔除（运行时未 import）。

## 7. 已知限制

- 进度为**阶段级**（非 DINOv2 逐帧百分比）。
- 模型权重运行时解析到用户数据目录（首次可能下载/导出）；**不入 bundle**。
- bundle 偏大（本地 DL 引擎固有成本）；单 exe 冷启动含 ONNX 会话加载（~3s）。
- macOS Intel 不支持；AMD/Apple 需本机验证。
- 剪枝已在打包后端做真实索引/预览验证；CPU/torch 回退路径预期安全（torch 不 import scipy）。

## 8. 相关命令

```bash
# 后端单元测试
../video-dedup-tool/.venv/Scripts/python.exe -m unittest mvp.api.tests.test_api mvp.api.tests.test_tasks mvp.api.tests.test_progress mvp.api.tests.test_preview mvp.api.tests.test_preview_service
# 前端
cd mvp/ui && npm run test && npm run build && npm run typecheck && npm run typecheck:desktop && npm run compile:electron
# 基准
../video-dedup-tool/.venv/Scripts/python.exe mvp/benchmark/release/benchmark_release.py --durations 600 3600 7200
```
