# mvp/api — Python Service Bridge（FastAPI）

前端不直接调 `SourceLocatorService`；通过本桥（HTTP）暴露为统一的本地 API。
桥是 **Adapter Layer**：只做转发，不实现任何算法。前端下一阶段设
`VITE_API_BASE=http://127.0.0.1:8765` 即可从 Mock 切到真实后端（不改 UI 页）。

> 本阶段**不实现 WebSocket**（`/ws/progress` 仅留接口说明）；不接 Electron、不改 Vue、
> 不改 `mvp/src`（domain/engine/FeatureStore/DeviceBackend/SourceLocatorService 全冻结）。
> 桥只 import `app`(SourceLocatorService)、`domain`、`infrastructure.errors`、`infrastructure.logging`。

## 端点

| 方法 | 路径 | 请求体 | 返回 |
|---|---|---|---|
| GET | `/api/health` | — | `{ status, version }` |
| POST | `/api/index` | `{ video_path }` | `{ status, frames, backend:{device_name,device_type} }` |
| POST | `/api/analyze` | `{ edited_path }` | `{ segments: [{id,label,span{start,end},nq}] }` |
| POST | `/api/results` | `{ edited_path, original_path? }` | `ResultBatchJson`（拍平 confidence） |
| POST | `/api/export` | `{ output_dir }` | `{ path }` |
| POST | `/api/tasks/analyze` | `{ edited_path, original_path }` | `{ task_id }` |
| GET | `/api/tasks/{task_id}` | — | TaskJson（status/stage/progress/result/error） |
| POST | `/api/tasks/{task_id}/cancel` | — | `{ status: "cancel_requested" }` |
| WS | `/ws/progress/{task_id}` | — | 实时进度帧（见「异步任务」） |
| POST | `/api/preview` | `{ original_path, start, end }` | `{ path, duration }` |
| GET | `/api/preview/media/{filename}` | — | 抽取出的预览片段（video/mp4，支持 Range） |
| GET | `/api/preview/edited` | — | 当前会话编辑视频（video/mp4，支持 Range） |

- `POST /api/results`：`original_path` 缺省时使用最近一次 `/api/index`（或 `/api/results`）记录的原片；
  两者皆无 → `400 {error:"no_original"}`。
- `POST /api/export`：导出最近一次 `/api/results` 得到的结果批；无批 → `400 {error:"no_results"}`。

## 异步任务（本阶段：生命周期，非真实进度）

`/api/tasks/*` 是把长分析（可能数分钟）**异步化**的入口：`POST /api/tasks/analyze` 立即返回
`task_id`，TaskManager 在**后台 worker 线程**里调 `SourceLocatorService.locate(edited, original)`
并更新任务状态；客户端轮询 `GET /api/tasks/{task_id}` 或用 `POST /cancel` 请求取消。

- 状态机：`pending → running → completed | failed | cancelled`。
- 阶段级 progress（**不是**真实 DINO 逐帧进度，需后续 service hook）：
  `idle → indexing → embedding → segmenting → retrieval → exporting → finished`，`progress` 为
  0–100 的阶段百分比。
- Worker 调 service（复用同一实例），把 progress 回调 `ProgressEvent` 映射为 TaskStage；捕获
  异常 → `failed`（`error` 存原因）；`CancellationToken` 取消 → `cancelled`。**不复制/实现算法**。
- **实时进度（WS）已实现**：`GET /ws/progress/{task_id}` 订阅该任务的实时进度帧。服务端在每次
  状态变更时向订阅者推送 `progress`（`{type, task_id, status, stage, progress, message}`）与
  终态 `completed`/`failed`/`cancelled`；客户端可发 `{"type":"cancel"}` 请求取消
  （`TaskManager.cancel` → `CancellationToken`，**不强制杀线程**）。任务不存在 →
  `{type:"error", error:"unknown_task"}` 并关闭。
- 进度仍为**阶段级**（非真实 DINO 逐帧百分比；需后续 service hook 提供逐帧进度）。

## 视频预览（独立能力，不改 locate / 置信度 / Result schema）

`POST /api/preview` 从 ``original_path`` 抽取 ``[start, end]``（秒）为独立 mp4，落盘到
预览缓存目录（默认 ``<app-data>/previews``），返回 ``{path, duration}``。前端把 ``path``
映射到 ``GET /api/preview/media/{filename}``（Starlette ``FileResponse`` 支持 HTTP Range，
HTML5 video 可拖动），作为 Original 预览播放源；`GET /api/preview/edited` 用
``FileResponse`` 服务当前会话编辑视频，作为 Edited 预览播放源。

- 复用 ``SourceLocatorService`` 的 ``FFmpegIO.extract_clip``（精确重编码）；**不复制/实现算法**，
  不改 ``mvp/src``。
- 错误统一 ``PreviewError``（``LocatorError`` 子类）→ 500 ``{error, detail}`` 并 ``logger.exception``。
- 安全性：media 路由只取 ``path.name``（basename）且限制在 ``preview_dir`` 内，杜绝目录穿越；
  `edited` 路由只服务会话记录过的那份编辑视频，不接受客户端传入路径。

## 到 `SourceLocatorService` 的映射

- `build_original_index(video_path)` → `POST /api/index`；`frames`/`backend` 取自返回 `IndexBundle.meta`（冻结 IndexMeta）。
- `analyze_edited_video(edited_path)` → `POST /api/analyze`；把 `ShotSegment[]` 映射 `{id,label,span,nq}`（numpy 留后端不出 JSON）。
- `locate(edited, original)` → `POST /api/results`（同步）；经 `TaskManager` 在后台线程 → `POST /api/tasks/analyze`（异步轮询）。
- `export_results(batch, out_dir=...)` → `POST /api/export`。

## 约定

- 线格式：结果用冻结 `ResultBatch.to_dict()`；`confidence` 顶层拍平为 `confidence`/`confidence_score`/`reasons`，
  **不是**嵌套对象；不转百分比、不加 probability、不改 score 语义。
- `backend.device_type` 是**纯展示层分类**（来自冻结 `IndexMeta.backend` 的静态标签映射），只进响应 payload，
  桥内任何逻辑/分支/判错都不使用它；不据此做 fallback / 选后端 / 判错。
- 错误：服务层 `LocatorError` → `500 {error, detail}`（`logger.exception`）；缺原片/结果批 → `400 {error, detail}`。

## 进度 / 取消（本阶段仅文档，未实现）

- `WS /ws/progress`：服务端每步推送 `{ stage, current, total, message }`（`ProgressStage` 7 阶段）；
  客户端可发 `{ "cancel": true }` 取消当前任务（`CancellationToken`）。当前 Vue 用 Mock Progress。

## 运行 / 测试

```bash
cd D:\claudework\benchmark
# 启动（py/pip 不在 PATH，用 venv 绝对路径）
../video-dedup-tool/.venv/Scripts/python.exe -m uvicorn mvp.api.main:app --host 127.0.0.1 --port 8765
# 测试（unittest，与仓库一致）
../video-dedup-tool/.venv/Scripts/python.exe -m unittest mvp.api.tests.test_api -v
```

依赖：`fastapi`、`uvicorn[standard]`、`websockets`（见 `requirements.txt`；pydantic/starlette 随之安装）。
