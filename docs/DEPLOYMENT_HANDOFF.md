# 部署交接文档（DEPLOYMENT HANDOFF）

> 阶段定位：**桌面部署完成，安装器（NSIS）已按用户拍板移除（2026-08-27）**。当前只交付**可直接运行的免安装 exe**
> （`win-unpacked`），**不生成安装器**。本文写清：交付物在哪、怎么用、关键修复（GPU/CPU 真切换 + 拖拽 +
> 蒙太奇多段定位 + 原始 span 宽度兜底 + 召回优化）、如何重新打包、暂停项与下一步。

## 1. 当前交付物（可直接用）

| 交付物 | 路径 | 状态 |
| --- | --- | --- |
| **可运行 exe（本阶段唯一交付物）** | `mvp/ui/release/win-unpacked/Video Locator.exe` | 免安装，双击即用 |
| NSIS 安装器 | ~~`Video Locator Setup 0.1.0.exe`~~ | **已移除（用户拍板 2026-08-27）**；electron-builder 改 `--dir` 不再生成；产物已删 |

> **交付形态（用户拍板 2026-08-27）**：安装器从项目移除，本阶段只交付**直接打包好的可运行 exe**。
> 构建以 `electron-builder --dir` 产出的 `win-unpacked/` 为准，不再跑 NSIS 打包。

`win-unpacked/` 自包含：Electron 主进程 + `resources/app/`（明文，`asar: false`）+ `resources/backend/backend.exe`
（Python 引擎）+ `resources/models/dinov2_cls_384/`（DirectML ONNX）+ `resources/models/dinov2_vits14/`
（CPU torch 权重 `.pth`）+ `resources/backend/ffmpeg.exe|ffprobe.exe`。**运行 exe 即自动拉起后端，无需手动
启动 uvicorn。**

## 2. 怎么用

- **直接运行**：进入 `win-unpacked\`，双击 `Video Locator.exe`。（SmartScreen 可能提示「未知发布者」
  →「更多信息 → 仍要运行」；未签名。）
- 首次启动显示「正在初始化 AI 引擎 N%」→ 检查后端 → READY → 进入首页。
- **导入视频（源片必须用完整绝对路径）**：项目详情页「源片库 / 剪辑视频」区可**拖入本地视频**（取绝对路径），或点「选择源片文件 / 选择文件」用系统对话框选真实视频（返回绝对路径）。源片区若显示**相对路径（只有文件名）**会**警告**并提示重新选择——裸名会导致后端找不到文件、构建索引失败。
- **索引状态**：点「构建索引」后徽章显示「构建中」→ 成功「有效」/ 失败显示后端具体原因（如「源片路径无效或不存在」）。后端有真实状态查询（`/api/index/status`），重启 app 后也能看到真实索引状态。
- **后端切换（GPU/CPU）**：设置页「设备」卡片——**真正的三档下拉**：智能（自动选 GPU/CPU）/ AMD GPU (DirectML) /
  CPU。选「AMD GPU」→ 保存 → 回源片页重新构建索引即用 DirectML 推理（本机 RX 6750 GRE 实测 `device_type: amd`）；
  选「CPU」→ 用内置 torch 权重；「智能」在 GPU 可用时自动选它。当前实际后端按真实运行结果展示，若请求 GPU
  但回退 CPU 会显示「已回退」提示（不静默）。

## 3. 关键修复（本阶段）

### 3.1 GPU / CPU 真正可切换（本次新增，替代旧“只读显示”）
**根因**：旧 Settings 页「设备」是**只读展示**（无真的切换控件），且 `HttpServiceAdapter` 的
`DEVICE_NAMES` 白名单**缺 `'directml'`**——后端 `IndexMeta.backend` 真实返回 `"directml"`，被
`normDeviceName` 强制 clamp 成 `'cpu'`，**即使 GPU 真在工作 UI 也显示 CPU**。
**修复**（端到端，后端 + 前端 + 持久化）：
- **后端**：新增 `infrastructure/settings_repo.py`（持久化 `device.preferred` 到 `<data_dir>/settings.json`）；
  `SourceLocatorService` 加 `device_preference`/`set_device_preference()`/`device_settings()`（切换后重置 backend、
  立即生效并持久化）；新路由 `routes/settings.py` `GET|POST /api/settings/device`（POST 校验 auto/cpu/directml，
  非法 → 400）。
- **前端**：`types.ts` `DeviceName` 补 `'directml'` + `DevicePreference`/`DeviceSettingsJson`；
  `HttpServiceAdapter` `DEVICE_NAMES` 加 `'directml'` + `getDeviceSettings/setDeviceSettings`；`ServiceAPI`/`Mock`/
  session store 同步；`SettingsPage.vue` 由只读改为**真三档下拉** + 保存生效 + 显示「期望 vs 实际/回退」。
- **验证**：`GET /api/settings/device`（auto→`directml/amd`）、POST `cpu`→`cpu`、POST `directml`→`amd`、
  非法 `gpu`→400；后端日志 `backend requested=auto → backend selected=directml type=amd` 全过。

### 3.2 GPU 会切回 CPU（模型内置，已装），并补 CPU 权重
- 模型内置 `resources/models/dinov2_cls_384/`，main.ts 设 `SVL_DML_MODEL=<resourcesPath>/models/...onnx`。
- **CPU 同修**：CPU 走 torch 原生需要权重 `.pth`，此前 bundle 只带 ONNX → 打包 exe 里切 CPU 会崩
  （`DINOv2 weights not found`）。**修复**：把 `dinov2_vits14_pretrain.pth` 内置 `resources/models/dinov2_vits14/`，
  main.ts 设 `SVL_DINOV2_WEIGHTS=<resourcesPath>/models/dinov2_vits14/...pth`。实测打包 exe 切 CPU 正常
  （`actual_device_type: cpu`，不再 500）。

### 3.3 无法拖入视频（preload 未生效，已修）
**根因**：`window.desktop` / `window.backend` 在渲染进程均为 `undefined`——Electron **sandboxed preload
不能 `require` 相对路径模块**，而 `preload.js` 保留 `require("./backend/bridge")` → 整个 preload 加载失败 →
`contextBridge.exposeInMainWorld` 永不执行 → 拖拽 `getPathForFile` 与 renderer→后端桥全失效（CDP 实测
旧版 `desktop:false`）。
**修复**：`scripts/build-preload.cjs` 用 `esbuild` 把 `preload.ts + backend/bridge.ts` **bundle 成单个自包含
文件**（仅外留 `require("electron")`，sandbox 允许）；`compile:electron` 在 tsc 后追加该步。实测新版
`window.desktop:true`、`getPathForFile:function`、`backend.request:function`；拖拽恢复。
安全姿态不变（`sandbox:true` + `contextIsolation:true` + `nodeIntegration:false`）。

### 3.4 构建索引后仍显示「缺失」（已修）
**根因**：项目页源片存的是**裸文件名**（如 `Dune.mkv`，无目录——旧 exe 拖拽未生效且项目页无「打开文件」入口）。后端按工作目录解析不到 → `ffprobe` 找不到 → `/api/index` 失败 → 前端因**无真实索引状态查询端点**而一直显示「缺失」。
**修复**：
- 前端源片库/剪辑区新增「选择源片文件/选择文件」（Electron `dialog.showOpenDialog` → 绝对路径，`window.desktop.openFile`）；拖拽保留。源片区对**非绝对/裸名**路径显示警告「源片是相对路径，请点『选择源片文件』」。
- 后端 `build_original_index` **前置校验**：路径非绝对或文件不存在 → 提前抛**明确可读错误**「源片路径无效或不存在：\<path\>。请点『选择源片文件』选择真实视频文件」，不再走到 ffprobe/embed 才笼统失败。
- 后端新增 **`GET /api/index/status?video_path=…`**（透传 `FeatureStore.validate_index`：VALID/INVALID/MISSING + reason）；前端 `getIndexStatus` 改为真实查询，不再用内存占位 → 构建成功后显示「有效」、重启后也能查真实状态。
- 索引徽章支持「构建中」态；失败时前端显示**后端具体原因**（而非一直「缺失」）。
- 异常逃逸加固：`build_original_index` 的 `except` 扩为含 `DeviceError`/`OSError`/兜底 `Exception`，保证日志始终有 `index failed` 前缀。
**验证**：打包 exe CDP——裸名 `Dune.mkv` status→`INVALID/source video missing`、裸名构建→`500 + 明确中文错误`（不再 ffprobe 崩）、`window.desktop.openFile:function`；后端 `unittest` 51（+`test_index_status` 4）、前端 `test` 67、`test:mock`、`typecheck`/`compile:electron` 全绿。

### 3.5 点「开始分析」一直转圈 + 取消无效 + 异步分析后导出报错（已修）
**根因**（三个关联问题）：
1. **一直转圈**：打包 exe 里 Electron 主进程 `globalThis.WebSocket` 不可用（Electron 34 的 Node 20 无全局 WebSocket），进度 WS 代理被禁用（日志 `global WebSocket unavailable`）。前端 `subscribeProgress` 走 WS 收不到任何帧 → `runLocate` 的 Promise 永不 settle → 界面一直「分析中」。
2. **取消无效**：同一原因，取消走 HTTP 能取消后端，但前端因收不到 WS 终态帧界面无反馈；且编辑片 `embed_frames` 是一次性调用，长剪辑取消无效。
3. **导出 no_results**：`/api/export` 用 `ctx.current_batch`（仅同步 `/api/results` 设置）；异步 `/api/tasks/analyze` 的 worker 不写它 → 异步分析完成后导出报 `400 no_results`。
**修复**：
- 前端 `analysis.runLocate` 改为 **HTTP 轮询 `GET /api/tasks/{id}` 直到终态**（`pollTaskUntilDone`），不依赖 WS；取消走既有 `cancelTask`。任何环境都可靠。
- 后端 `analyze_edited_video` 的编辑片 embed 改为**分批 + 每批 `_check_cancel`**，长剪辑也能及时中断。
- 后端新增 `SourceLocatorService.last_result_batch()`；`/api/export` 改为 `ctx.current_batch or ctx.service.last_result_batch()`，异步任务完成也可导出。
**验证**（源码 TestClient + 打包 exe HTTP 全链路）：`POST /api/index` → `completed / directml / 帧数`；`GET /api/index/status` → `VALID`；`POST /api/tasks/analyze` → 轮询至 `completed`，结果 `[HIGH, LOW]`；`POST /api/export` → `200`（落盘 results.json）；再次分析后 `POST /api/tasks/{id}/cancel` → `cancelled / cancel_requested=True`；前端 `test` 67、`test:mock`、后端 `unittest` 51 全绿。

### 3.6 特征提取「一直转圈」（其实是慢 + 无进度显示，已修）
**根因**：特征提取（编辑片 embed）阶段 progress 固定 30%（阶段级粗进度）+ 无「已处理 N/M 帧」显示 → 编辑片越长（如 2h 解说 @2fps 约 1.4 万帧）embed 越久，进度条停在 30% 不动、看着像卡死。实测 100s 剪辑 embed 实际 14s 就 completed（不是真卡）。
**修复**：
- 后端 `analyze_edited_video` 编辑片 embed **分批**，每批上报真实帧进度 `EDITED_FEATURE_EXTRACTION current=N total=M message="特征提取 N/M 帧"`。
- worker 把 `ev.message` 透传到 task；`Task.to_dict()` 返回 `message`；前端 `TaskJson` 加 `message`，轮询时显示「特征提取 N/M 帧」。
- worker 对 embedding 阶段用真实帧数把 progress **从 10% 平滑到 30%**（INDEXING→EMBEDDING 区间），进度条不再停在 30。
**验证**（打包 exe）：特征提取阶段 progress `13→16→18→21→24→28`、msg「特征提取 32/200→…→176/200 帧」→ completed。
**踩坑记录**：重建后端必须 **cwd 在 benchmark 根** 跑（`cd D:\claudework\benchmark && python mvp/scripts/build_backend.py`）。`backend.spec` 用**相对 pathex**（`mvp`/`mvp/src`），若 cwd 在 `mvp/ui` 则 PyInstaller 打包的 `backend.exe` 缺 `mvp` 包（`run_backend: ModuleNotFoundError: No module named 'mvp'`）→ exe 启动 health 超时。

### 3.7 构建索引报「cannot reach backend: fetch failed」（已修）
**根因**：后端 PyInstaller 冷启动慢（加载 torch/onnx），实测约 20s，更慢的机器可能 >30s；而 Electron `waitForHealth` 只等 **30s**。后端未 ready 时用户点「构建索引」→ 渲染层连不上 → `cannot reach backend: fetch failed`。间接依据：后端本身能正常建索引（300s 源片 150 帧 14.8s 完成、directml），**不是构建时崩溃**。
**修复**：`electron/backend/config.ts` `HEALTH_TIMEOUT_MS` 30_000 → **90_000**，给后端充足冷启动时间；`waitForHealth` 成功后才 `createWindow`，用户进入主界面时后端已 running。
**验证**：启动打包 exe，后端 health 200；经 renderer→后端桥 `POST /api/index` → `200 completed / 150帧 / directml·amd`（fetch 通路正常，不再 fetch failed）。

### 3.8 结果页剪辑黑屏 / 进度条不能滑 / 预览要手动生成（已修）
**根因**：
1. **剪辑黑屏**：`GET /api/preview/edited` 把用户原始编辑视频「原样」`FileResponse` 返回（**无转码**）；原片预览走 `extract_clip` 重编码 libx264 MP4（能播）。用户编辑视频是 MKV/HEVC，Chromium `<video>` 不支持 → 黑屏。这是「原片有画面、剪辑黑屏」的差异根源。
2. **进度条纯摆设**：`VideoPlayer.vue` 视频下方进度条无 seek 事件（样式 `cursor:pointer` 却不可拖），且 `VideoComparisonPlayer` 的剪辑播放器只绑了 `@tick`、没绑 `@seek`。
3. **预览要手动**：`generatePreview()` 只在 InspectorPanel「生成预览」按钮被调；`setBatch`/`select` 都不自动，原片预览初始为 null（占位）。
**修复**：
- **编辑预览改「抽 edited_segment 区间转码 H.264 MP4」**：复用自己的 `POST /api/preview`（对任意视频抽区间重编码 libx264 MP4，`PreviewService.extract_segment`），并弃用 `/api/preview/edited`（原样返回）。`stores/results.ts` 新增 `generateEditedPreview()`（`previewResult(edited_video, edited_segment.start, end)`）。
- **默认自动生成**：`setBatch()` / `select()` / `markManualOverride()` 自动生成**编辑 + 原片**预览；InspectorPanel 按钮改「重新生成」（手动刷新）。
- **进度条可拖 + 时间轴对称**：`VideoPlayer` 的 `.vp__bar` 加 `@pointerdown/move/up` seek（emit `seek`）；`VideoComparisonPlayer` 两侧播放器都绑 `@seek`；两侧时间轴统一为**区间 local 0..width**（1:1 按比例同步），`onOriginalSeek` 把原片位置映射回编辑侧。
- **导出后清理预览**：`PreviewService.cleanup()` 清空 `<app-data>/previews/`；`/api/export`（`routes/results.py`）导出成功后调用，避免自动生成的预览片段长期占用磁盘。
**验证**（打包 exe）：`POST /api/preview {HEVC/MKV 编辑视频,±区间}` → `200 {path,duration}`；`GET /api/preview/media/<name>` → `200 video/mp4`、`ffprobe= h264`（浏览器可播，非黑屏）；`/api/export` 后 `previews` 目录清空（`Before:[3文件] After:[]`）；前端 `test` 67、后端 `unittest` 51 全绿。

### 3.9 算法改进：蒙太奇多段定位 + 原始 span 宽度兜底 + 召回优化（2026-08-27~28）

用户反馈「编辑片有、定位结果没有」「短镜头被定位成 30s 原片」「很多镜头没识别到」，三波修复：

- **蒙太奇多段定位**：`domain.Result` 新增 `original_segments`（+`OriginalSegment`，向后兼容 `original` 主 span）+ 运行时模块 `engine/localization/montage_localize.py`（`MontageLocalizer`，query-axis 聚类+门控+每簇 merged span）+ `app._apply_montage`（**蒙太奇段 → 多个子镜头原片区 + `montage_flag` + 诚实降 LOW**）。前端 `InspectorPanel` 显示「多段定位」列表。→ 修「编辑片有、定位结果没有」（[0] 救回持枪子镜头等）。
- **原始 span 宽度兜底**：`finloc_window` 新增 **`tight_span`**（cs 覆盖峰值为中心、宽度≤`max_orig_span_s`(15s)）+ `app._bound_span` 按编辑支持比例夹紧。→ 修「1s 镜头→30s 原片」（[8] 22s→4s、[11] 30s→9.5s；**全部原片区 ≤15s**）。蒙太奇子 span **不夹紧**（保住 GT recall 6/7，夹紧会退化）。
- **召回优化**：`config.py` 接入 `montage_*` 参数 + PipelineConfig 驱动 `MontageLocalizer` + `detect_shots z_thresh 2.0→1.7/cut_abs 0.30→0.26` + `MIN_HITS 2→1`/`SIM_FLOOR 0.45→0.38` + `retrieval_top_k 20→28` + **`index_sampling_fps 0.5→1.0`**（密度，7667 帧）。→ 修「很多镜头没识别到」（12→14 段、18→25 子 span，GT recall 6/7 保持）。**参数扫描平衡点**：激进（z=1.4/mf=1/gap=8）碎片化致 GT 4/7 已弃；中间设置保 6/7。
- **多模态核验**（`mvp/scripts/verify_recall_sample.py`，recall_s*.jpg）：新子 span 内容相关（士兵/荒漠/铁丝网/平台上人），非随机噪声；但**暗色/崎岖内容匹配松散**（cover 0.38-0.66）——特征层上限（CLS 难精判别暗色同类内容），需第二信号/更好特征=独立研究。
- **说明**：以上均**不改相似度/检索/排序语义**；`_apply_montage` 用 query-axis 蒙太奇检测（比 pipeline `multi_island` 更准）诚实降 LOW。

### 3.10 研究期多模态诊断（2026-08-27，`mvp/benchmark/user_case/montage_research/`）

- 真实用户案例定位「对不上」诊断：**算法限制非 bug**（蒙太奇丢子镜头 + 相似外观误配 + 置信占位未标定）；时间基 `start_time=0` 排除、预览=Result.original 无二次换算、device=directml/索引复用正确。
- 蒙太奇多段定位方向验证（query-axis 簇数 = 干净 1 簇/蒙太奇多簇并对齐 GT），GT recall 2/7→86%，硬化成可测模块 `montage_localize.py`（8 单测）。
- 多模态 contact sheet 工具：`src/diagnostics/`（frame_sampler/contact_sheet/case_builder）、`src/vision_qa/`（case 子命令）。

### 3.8 方向 A 事件表（场景实例身份建模, 2026-09-05 立项完整阶段）
**变更**：索引 schema bump `feature_version` 从 `+scn1` → `+scn1+evt1`（含事件表）。
- 落盘新增 `events.npy`（[E,2] 事件单元起止秒）+ `event_feats.npy`（[E,384] L2 事件代表指纹），
  由场景表经 `FeatureStore._build_event_table` 确定性派生（归并参数 60s/0.60 固化）。
- **部署影响**：旧索引 feature_version 不匹配 → 首次启动自动 INVALID 重建（GPU DirectML 四片约 1-2h，
  或用 `mvp/scripts/backfill_scene_tables.py` 免重 embed 回填场景+事件表）。
- 查询侧新增事件单元扩池（`event_recall_enabled` 默认开）：查询均值 vs 事件指纹 top-3 →
  事件窗内帧扩池，独立精化+门控；**不改**相似度/检索/排序/置信语义（帧级为主，事件级只扩池；
  帧级+场景均零证据才救回）。兄弟机位（p08/p38 同事件）歧义经事件身份聚合消解。
- 结果契约：`OriginalSegmentJson` 新增可选 `from_event_pool`（仅展示候选，不参与主定位改写/
  text_anchor 重排/导出主轨；EDL/XML 注释 event-pool candidate）。
- 回退开关：`pipeline.event_recall_enabled=false` 恢复旧行为（事件表缺失自动降级不崩）。
- 验收：后端 246 单测（+6 事件）+ 前端 vitest 67 + API 58 全绿；四片三指标零回退（112/139 · 136/139 · 4/9）；
  p08 兄弟机位若被事件扩池救回 → 2.mkv 严格 +1。

## 4. 如何重新打包

```powershell
cd D:\claudework\benchmark\mvp\ui
# 渲染层 + Electron 主进程 + preload bundle
npm run build && npm run compile:electron
# 后端 PyInstaller —— 必须 CD 到 benchmark 根再跑（backend.spec 用相对 pathex mvpm/…，
# cwd 在 mvp/ui 会缺 mvp 包 → exe 启动 ModuleNotFoundError / health 超时）
cd D:\claudework\benchmark
D:\claudework\video-dedup-tool\.venv\Scripts\python.exe mvp\scripts\build_backend.py
# 只产 win-unpacked 免安装 exe（不生成安装器）
npx electron-builder --dir
```

要点：
- electron 二进制用 `ELECTRON_MIRROR` / `ELECTRON_BUILDER_BINARIES_MIRROR`（npmmirror）绕开 GitHub 443。
- **`asar: false`**（electron-builder.json）：`addWinAsarIntegrity` 会**无条件**改写 exe（`--dir` 下
  `signAndEditExecutable:false` 不生效），在 Windows Defender 扫新 exe 时锁文件报 `UNKNOWN`。`asar:false`
  让 `asarOptions==null` → 跳过该步。代价：app 明文放 `resources/app/`（未签名 MVP 可接受，不碰模型/后端）。
- 模型资产须就位：`resources/models/dinov2_cls_384/`（ONNX）、`resources/models/dinov2_vits14/`（CPU .pth）。
- 后端若改了 `mvp/src`/`mvp/api`，**必须**重跑 `build_backend.py`，否则 exe 里 `backend.exe` 仍是旧代码
  （本轮曾因此 `/api/settings/device` 404）。

## 5. 暂停项 / 下一步

- **已移除（用户拍板 2026-08-27）**：NSIS 安装器（electron-builder 改 `--dir`，产物已删）。不恢复。
- **下一步（如需要）**：代码签名、自定义应用图标、商业保护层（License / Device Binding / 激活 / 云鉴权——均不在本期）。
- **算法上限（诚实）**：暗色/崎岖同类子镜头的定位精度受 CLS 特征判别力限制（多模态核验 cover 0.38-0.66 松散）。若要「对这类也准」→ 需第二信号/更好特征（场景身份/时序一致性，**独立研究阶段**，研究护栏允许：真实数据证明该失败类影响产品价值）。
- **H4 Windows NVIDIA / CUDA**：仍 PENDING（`H4_GPU_RUNNER_UNAVAILABLE`，需 NVIDIA 环境）。CUDA 不进当前实施。
- **已知限制**：未签名；win-unpacked 用默认 Electron 图标；bundle ~190MB exe（含后端 815MB + 模型，本地 DL 引擎固有成本）；`asar:false` 明文 app（无 DRM/IP 混淆）；进度为阶段级（非 DINOv2 逐帧）；`index_sampling_fps=1.0` 使首次建索引 ~700s（1fps，7667 帧，一次性缓存后快）。

## 6. 验证记录（本机，2026-08-27~28）

- 后端 `unittest`（mvp/tests 82 + api 51 = 133）+ 前端 `test` 67 + `test:mock` + `typecheck`/`typecheck:desktop` + `compile:electron` 全绿。
- **打包 `backend.exe`（PyInstaller，含算法改进）E2E**（真实 1.mp4→2.mkv，`/api/health` 200 → `/api/tasks/analyze` completed）：
  - **12 段 → 14 段、25 子 span**（召回优化），HIGH3/LOW11，宽度全 ≤15s（宽度兜底）；GT recall 6/7 保持。
  - 蒙太奇段 `original_segments`（多个子镜头原片区）+ 诚实 LOW；干净段单 span HIGH。
  - `index_sampling_fps=1.0`（7667 帧，复用 @1_l2 索引，构建一次后快）。
- **多模态核验**（recall_s*.jpg 逐帧读图）：新子 span 内容相关（士兵/荒漠/铁丝网/平台上人），非随机噪声；暗色崎岖内容匹配松散（cover 0.38-0.66）= 特征上限。
- 打包 `Video Locator.exe`（win-unpacked，`asar:false`）CDP 端到端：`/api/settings/device` auto→directml/amd、CPU/DirectML 可切换、`window.desktop`/`getPathForFile`/`backend.request` 桥恢复、Settings 三档下拉；关闭后 8765 释放、0 残留。索引缺失修复（裸名 → 明确中文错误 + `/api/index/status` 真实状态）。