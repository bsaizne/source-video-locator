# Video Locator AI — UI 架构设计（阶段一）

> 本文件是 Vue3 + TS 桌面前端的架构性文档（Stage 1）。它描述页面结构、信息层级、
> 用户流程与前端 ↔ 后端 Service API 契约。组件级设计见 `03-components.md`，
> 视觉规范见 `02-design.md`。

## 1. 定位

Video Locator AI 是一个**本地运行**的 AI 视频定位工作台：给定一段剪辑视频
（Edited）与一段原始长视频（Source），自动在 Source 中定位每个剪辑片段对应的
原始区间，给出置信度，支持人工修正与批量导出。

它不是聊天机器人 / 自动化内容工具，而是 **Codex Workspace + Windows Fluent +
Premiere-Pro 式专业工具台**：机器给候选，人来做确认与修正。因此界面强调
**可信度（置信三档 + 依据）、可修正性（手动区间 / 备选候选）、批量导出**。

## 2. 技术边界

- 前端 = Vue 3 + TypeScript + Vite，桌面壳 = **Electron**（已拍板）。
- 前端**不直接接触** torch / numpy / FFmpeg subprocess / 特征缓存 / 模型文件。
  一切算法经 Python `Application Service` → `SourceLocatorService`。
- 前端只依赖一个 `ServiceAPI` 接口（见 §4）。默认注入 `MockServiceAdapter`
  （零后端跑通）；`HttpServiceAdapter` 在提供 `VITE_API_BASE` 时接管。
- 视觉组件**全部自研**（学习 Fluent 语言，不引入 winitonweb 源码、不依赖 GPL），
  商业闭源发布安全。

## 3. 页面结构与信息层级

三栏工作台（`.app-shell`）：

| 栏 | 宽度 | 内容 | 层级职责 |
|---|---|---|---|
| Sidebar | 240px | Logo、导航（Home/Projects/Media Library/Analysis/Results/Settings）、底部 BackendStatusIndicator（Model/Backend/Index） | 全局导航 + 系统状态 |
| Main | 1fr | 当前页面（`<router-view>`） | 页面主体 |
| Inspector | 320px | 选中项详情 / 参数 / 日志 / 置信度依据 | 上下文细节 + 动作 |

信息层级约定：**导航 → 列表/任务 → 细节 → 动作**。细节与动作尽可能放在右侧
Inspector，避免主区堆叠。

### 3.1 页面路由

| 路由 | 页面 | 职责 |
|---|---|---|
| `/` | Home | 概览统计 + Recent Projects 网格 + New Project |
| `/projects` | Projects | 项目列表 + 新建 |
| `/projects/:id` | Project Detail | 单项目：Source 信息（duration/index/backend）、Source Library、Edited Videos（拖拽导入）、Build Index、Run Analysis |
| `/media` | Media Library | 所有 Source/Edited 资产 |
| `/analysis` | Analysis | 任务执行中心：Source/Edited 选择、Run/Cancel、6 步 Pipeline 进度 |
| `/results` | Results | 结果审查：左 ResultTable + 右视频对比 + Inspector 详情 |
| `/settings` | Settings | 后端/采样/置信度展示 + 已知限制 |

## 4. Service API 契约

前端 `ServiceAPI` 接口（`src/services/ServiceAPI.ts`）划分三组，方法一一映射后端
`SourceLocatorService`：

### 4.1 Index Service
- `getIndexStatus(originalPath) → IndexStatus`：`{ indexMeta: IndexMetaJson | null; validation: IndexValidationJson; backend: BackendInfoJson }`
- `buildIndex(originalPath, {cancelToken}) → IndexStatus`：Streams `INDEX_BUILD` 进度
- `getIndexMeta(originalPath) → IndexMetaJson | null`

### 4.2 Analysis Service
- `analyzeEdited(editedPath, {cancelToken}) → { segments: ShotSegmentJson[] }`
- `locate(editedPath, originalPath, {cancelToken}) → ResultBatchJson`：一步编排
  （索引复用/构建 → 编辑侧抽帧+切分 → 逐段检索/定位/置信 → 汇总）

### 4.3 Result Service
- `exportResults(batch, {outDir?, filename?, cancelToken?}) → { path }`
- `loadResults(path) → ResultBatchJson`

### 4.4 进度 / 取消
- `onProgress(listener) → unsubscribe`：订阅 `ProgressEventJson`（7 阶段
  `ProgressStage`：`INDEX_BUILD / EDITED_FEATURE_EXTRACTION / SEGMENT_DETECTION /
  CANDIDATE_RETRIEVAL / LOCALIZATION / CONFIDENCE / EXPORT`）。
- `cancel()`：取消当前任务（后端为 `CancellationToken`）。

### 4.5 数据契约红线（与 `domain/models.py` 的 `to_dict()` 严格一致）

- `ResultJson` 顶层含 `edited_segment{start,end}` 与
  `original{candidate_start,candidate_end}`（**键名不对称**，须照抄）。
- `confidence` / `confidence_score` / `reasons` **拍平在 `Result` 顶层**（非嵌套
  Confidence 对象）。
- `manual_override == true` 时才出现 `manual_timestamp` 与 `auto_result`（手工修正
  双轨：自动值保留在 `auto_result`）。
- `confidence_score` 是**工程分，非概率**：UI 用 HIGH/MEDIUM/LOW 文案 + reasons
  依据，**禁止显示成百分比**。
- `IndexValidation` 三态：`VALID / INVALID / MISSING`；`IndexMeta.backend` 取自
  `device_name()` 合法值集合，**仅展示/日志，不作 UI 分支逻辑**。

## 5. 用户流程

```
新建项目 → 导入 Source → Build Index（streams 进度）→ 导入 Edited →
Run Analysis（6 步 Pipeline）→ Results（机器给候选 + 置信 + 依据 + 备选）
   → 人工播放对比 → 手动修正起点/终点 → 确认/跳到备选 → 批量导出
```

单段失败会被**失败隔离**：该段标记为 `Unresolved`（LOW + `failure_reason` +
日志 exception），后续段继续，不中断整任务。取消操作抛 `ApplicationError`，
不落入段级隔离。

## 6. 诚实限制（UI 显著处传达，不隐藏）

- 连续镜头是主能力；**蒙太奇是低置信场景**（显示候选区间 + 多备选 + 明确标识）。
- **暗场景语义特征可能混淆**（置信可能虚高）——Inspector 显示对应 reason。
- `s4` 为已知困难边界。
- **AMD GPU / Apple Silicon 需实机验证**；**macOS Intel 不支持**。
- 置信度权重/阈值为**未标定占位**（标定后会调整）。
