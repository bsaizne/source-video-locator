# PLAN：导出异步化（B 方案）

状态：**提案，未开工**。2026-10-13 提出（补十六 收口后唯一有产品收益的未拍板项）。
判据来源 = 现役代码实读（下列行号本批已核）。

## 1. 背景与真实代价

- 导出是**分钟级同步** HTTP 请求：真机实测 **374s / 783s** 崩、**475s / 571s** 成功
  （STATE 补十六 ①）。补十六 把 Electron 桥接层的等待上限从 undici 默认 300s 抬到
  `BRIDGE_REQUEST_TIMEOUT_MS=30min` —— 那只消掉了**误报**（草稿写完却弹「无法连接后端」），
  等待体验没动：用户干等 6~13 分钟，**无进度、无取消、超 30min 仍会被切断**。
- 成片渲染（`kind=render`）早就走异步任务通道（进度 + 取消 + 轮询），导出没有。
  两者代价同量级，缺的是接线，不是能力。

## 2. 关键前提：后端 hook 已经齐了（本批核实）

`SourceLocatorService` 的两个导出方法**本来就收 `on_progress` + `cancel_token`**，
只是同步路由没传：

- `export_results`：`mvp/src/app/locator_service.py:1590-1593`（签名）· `:1595` 取消检查 ·
  `:1596/:1598` 两条 `ProgressStage.EXPORT` 事件。
- `export_project`：`:1610-1616`（签名）· `:1630` 入口取消 · `:1646` 起跑事件
  「正在导出 {fmt}」· **剪映腿已有逐 clip 进度与取消**：`:1731` 每 clip
  `_check_cancel` + `:1742-1744` 「准备素材 i/N」· `:1757` 收尾「已导出 {name}」。

⇒ **本批 `mvp/src` 零改动**，只动 `mvp/api/tasks` + `mvp/api/routes` + `mvp/ui`。
这是 B 方案最省的一刀：不需要新造进度语义。

tasks 框架现成件：`TaskKind`（现 ANALYZE/RENDER，`models.py:43-49`）·
`TaskStage.EXPORTING`（`models.py:39`，已存在）· `TaskManager.submit_analyze/submit_render`
（`manager.py:35-71`）· `GET /api/tasks/{id}` + `/cancel`（`routes/tasks.py:76-106`）·
UI 轮询模板 `useRenderMovie.ts`（800ms；打包态 Electron 主进程无 WS，只能轮询）·
**桥接层零改动**（`electron/backend/bridge.ts` 是路径通用的，render 任务已验证同通道）。

## 3. 改动面（6 处，按依赖顺序）

1. **`mvp/api/tasks/models.py`**：`TaskKind` 加 `EXPORT`；`Task` 加
   `export_params: dict` + `export_batch`（**提交时锁批**，与 `render_batch` 同理由——
   排队期间用户又跑一次 locate 会导出错批）。
2. **`mvp/api/tasks/manager.py`**：`submit_export(batch, *, fmt, out_dir, min_confidence,
   low_policy, snap_scenes, material_width)`。⚠️ `isolated=self._isolated` 必须同源传
   （`submit_render` 当年漏过一次 ⇒ 隔离分支永远不进，见 `manager.py:66-68` 注释）。
3. **`mvp/api/tasks/worker.py`**：
   - `execute_task` 加 EXPORT 分支（调 `export_project` / `export_results`，
     返回 `{"kind": "export", "path": str(p), "warnings": [...]}`）。
   - **进度区间必须按 `task.kind` 分派** —— 见 §5 风险 R1，这是本批唯一会做错的地方。
   - 取消/失败话术沿用 render 腿（`public_error` → 「话术（LOC 码）」进 `task.error`）。
4. **`mvp/api/routes/tasks.py`**：`POST /api/tasks/export` → `{task_id}`。
   结果批口径与 `/api/export` 逐字一致（`routes/results.py:135`：
   `ctx.current_batch or ctx.service.last_result_batch()`），无批 → 400 `no_results`。
5. **`mvp/ui`**：`ServiceAPI` 加 `startExportTask`；`HttpServiceAdapter` +
   `MockServiceAdapter` 双实现；新增 `useExportTask`（照抄 `useRenderMovie` 的
   轮询/取消/`error` 直显后端话术）；`ResultsPage.vue doExport()`（现 `:164-186` 的
   `await service.exportResults(...)`）切任务通道 —— 按钮 loading 换成进度条 + 取消，
   完成后的 `path` 与 `warnings` 展示形态**保持现有**（告警滚动列表已在 r21 修过）。
6. **保留 `POST /api/export` 同步路由不删**：向后兼容 + 包侧既有锁
   `accept_packaged_bundle.py` 的 `jianying_http==200` 依赖它。

顺手项（改注释不改行为）：`routes/results.py:160-164` 的第二层边界注释仍写
「逃到 ASGI ⇒ uvicorn 掐连接」—— 该定性已被补十六 实测推翻（真因 = 客户端 300s 头超时），
本批把注释订正为「全局 handler 会回结构化 500，这层负责把意外异常变成 400 + 人话」。

## 4. 取消语义（如实边界）

- 剪映腿：逐 clip 协作式 `_check_cancel`（`locator_service.py:1731`）⇒ 取消粒度 = 一个素材。
- 隔离态：取消 = 父进程 `terminate` 子进程（强于协作检查，`isolated.py` 模块docstring 已声明）。
- **边界**：中途取消后 `clips/*.mp4` 已产出的半截素材**不自动清理**，`draft_content.json`
  未写 ⇒ 草稿不可用但目录残留在磁盘上。幂等保护已有（`clip_path.exists()` 跳过重抽，
  `:1734-1737`），重导同一批不会重复转码。本批**不做**残留回收（要做须单独裁决删什么）。

## 5. 风险与失败分支（按回退代价升序）

- **R1（最可能发生，且会静默）进度映射族**。`_STAGE_RANGES[EXPORT] = (EXPORTING, 98, 1.5)`
  （`worker.py:45`）是给 **analyze 收尾**用的；RENDER 靠 `(EXPORTING, 0, 99)`（`:47`）独占全区间。
  导出任务若直接复用 EXPORT 阶段映射 ⇒ **一提交就显示 98%、随后长时间不动**，看着像卡死。
  ⇒ 判据必须是按 `kind` 分派（kind=export 时 EXPORT 阶段事件走 0→99）。
  失败形态「首帧 98」→ 只回退 `worker.py` 映射一处，代价最小。
  另注 `worker.py:87-92` 的插值分支：`RENDER_MOVIE` 用 `current/total`（已完成数），
  剪映腿 `:1742` 发的也是 `current=i+1, total=n_clips` ⇒ 同口径，新增阶段别再混 `+1`。
- **R2 隔离 pickle**。`_payload_of` / `_task_from_payload`（`isolated.py:45-75`）是白名单式逐字段
  搬运；忘加 `export_params`/`export_batch` ⇒ 子进程拿到空批 → 任务 failed（**红得看得见**，
  不会静默跑错）。⇒ 加一条单测：payload 往返后 export 字段不丢。
- **R3 Mock 适配器不产 `warnings`**（`Known Issues` 已登记 dev/Mock 看不到 LOC-2001/2002）。
  UI 切任务通道后告警只从 `task.result.warnings` 读 ⇒ Mock 若不同步补，dev 态告警条恒空。
  处置：Mock 的 export 任务结果里给固定 `warnings`（或明确 dev 态不呈现，二选一，写进测试）。
- **R4 出包与 mac**。改动面 = Python(API 层) + UI JS ⇒ **必须重出包（r24）** 才对用户生效；
  且 **mac 要另走一发 `h3-macos-mps.yml` dispatch**（同一份 UI 代码，跨平台改动不主动
  dispatch 就留「Win 已改、mac 仍旧」的裂口）。门槛红则 `mac-alpha` 留旧包（自动 publish 只在
  门槛绿时跑）。
- **R5 收益无法在本机证明**。>300s 的长导出需要真机长材料；本机 accept 夹具是分钟级以内。
  ⇒ 验收里这条只能登记为**覆盖边界**：「异步化后进度/取消在包内实测通」可证，
  「长导出不再触发客户端超时」由 §6 的超时上限逻辑 + 真机日志背书，不靠本机复现。

## 6. 门禁与验收（每项写判据，不写「跑一下」）

1. 后端全套 `python -m unittest discover -s mvp/tests -p "test_*.py"`（PYTHONPATH 双根）+
   API `mvp/api/tests`。**新增锁**（命名可改）：
   - `POST /api/tasks/export` 无批 → 400 `no_results`；有批 → `{task_id}` 且轮询到
     `completed` 时 `result.path` 存在、`result.kind == "export"`。
   - **进度单调不回退**，且首帧不得 ≥98（直接抓 R1）。
   - `ApplicationError` → `failed` 带 LOC 话术；意外异常 → `failed` 不逃逸。
   - 取消：running 中 cancel → `cancelled`；隔离态另测「terminate 生效且服务存活」。
   - `isolated._payload_of` 往返含 export 字段（抓 R2）。
   - `submit_export` 传了 `isolated`（结构锁，防 `submit_render` 那次回归重演）。
2. UI vitest（现役 150 项）+ 双 typecheck（app + desktop）。新增 adapter 契约测 +
   `useExportTask` 终态/取消/warnings 三测。
3. 端到端（dev 态真跑一次 jianying 导出）：读数 = 进度 0→100 单调、逐 clip「准备素材 i/N」
   可见、中途取消后端与其它任务存活。
4. 包侧：`accept_packaged_bundle.py` **加一条任务通道硬断言**
   （`POST /api/tasks/export` → 轮询 completed → `draft_content.json` 在位且含 ≥1 segment），
   保留原同步 `jianying_http==200` 锁。⚠️ 包侧锁按**编译产物**排版写（教训：本批前的假红）。
   首跑预期红 ⇒ 红才是锁真咬的证据。
5. r24 出包后按规矩：zip 身份（条目数/testzip/`bridge.js` 与磁盘逐字节）+ 四道包内验收 +
   release/ 三档（出 r24 时删 r21，删前先验 r22 回滚档 sha16 逐字一致）。

## 7. 明确不做

- 不改 `/api/export` 的同步语义、不改 `mvp/src` 导出算法与 `export_project` 签名。
- 不做导出队列 / 并发上限 / 断点续导 / 残留素材回收。
- 不动 Confidence、GT、索引层。

## 8. 工作量与拍板点

- 工作量：API 层约 4 文件小改 + UI 1 composable + 2 adapter + 页面接线；测试为大头。
  单批可完成，无需分腿。
- 需你拍的三处：**(a)** Mock 的 warnings 取向（R3 二选一）；**(b)** 取消后残留素材是否回收
  （§4，默认不回收）；**(c)** 是否与 r24 同批、以及 mac dispatch 时机（默认随包同批发）。
