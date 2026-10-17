# TODO 迁移存档（2026-10-17 续63 补十八立档同批）

> `P0 — Current` 退休块**逐字**迁移。本批迁出：续63 补十七（B 方案导出异步化）。现役块见 `.agent/TODO.md`。

> **▶ 2026-10-13（续63 补十七）— B 方案导出异步化：/api/tasks/export 带进度与可取消【现读这条】**
> 后端 hook 本就在位（`export_project`/`export_results` 收 `on_progress`+`cancel_token`）⇒
> **`mvp/src` 零改动**，只接任务层 + UI：`TaskKind.EXPORT` · `submit_export`（提交时锁批，
> 防排队期间新定位换批）· `POST /api/tasks/export` · 进度按 `task.kind` 分派
> （analyze 收尾的 98→99.5 老口径逐字不变）· UI `useExportTask` + `ResultsPage` 切通道（进度行+取消）。
> 两条通道请求体收成一个构造点；`warnings` 随信封回传（隔离子进程与父进程是两个 service 实例）。
> 顺带接了 `ProgressDebouncer.flush()`：有实现有单测却**没有任何 worker 调用** ⇒ 收尾帧永不露出。
> 门禁：后端 **Ran 670 OK (skipped=2)** · API **Ran 150 OK**（130→150，+20）·
> UI vitest **161 passed**（150→161，+11）· 双 typecheck rc=0（逐字取码；`| tail` 会把 rc 洗成假 0）。
> 端到端 `work/probe_export_task_e2e.cjs` = 编译产物 `bridge.js` → 真 uvicorn（随机端口+令牌+release）
> → 完成 `progress=100` + 产物落盘 + `isolated child booted`（批过了真跨进程 pickle）⇒ **PROBE PASS**。
> 包侧 4 条新锁打在现役 **r23** 上首跑 = **FAILED=4 / PASS=28（预期红 = 锁真咬：含 1 条渲染层产物锁 +
> 3 条后端通道锁；r23 没这条路由 ⇒ 405）**，
> 其余 28 项照绿（DirectML wall=27.1s · 剪映 http=200 · reaped exitcode=0 · 12 行腿埋点）。
> **已出包 r24**（干净 commit `811932e`，包内四道全绿：bundle 33/0 · render 0 · 不变式 0 · 冒烟 0；
> zip 981,692,188B / backend.exe sha16 `cf9c6ce003a47c66` == 磁盘；r24 bundle 命中 1 / r23 命中 0）。
> ① **r21 已删**（2026-10-14 口令；删前双验逐字一致）⇒ release/ 三档 r24/r23/r22；
> ② **mac 由他 dispatch**：run `38429952068`（head `c789670`）→ **已闭合（2026-10-16 实测）**：
> `completed/success`；换包基线 `916,828,395B @ 2026-10-12T16:56:33Z` 现为
> **`916,840,558B @ 2026-10-13T17:01:02Z`**（字节+时间戳双变 = 包真换了）；
> `git diff --name-only 811932e..c789670` 仅 `.agent` 三份档案 ⇒ mac 代码面等同 r24。
> 探针草稿已清（draftA 他删 / draftB 我删），
> 日志留 `work/long_export_probe/`。
> 真素材长导出已实测（test2 批 66.7s/86 clip：首帧 0.0、81 条逐 clip 帧、收尾帧可见、取消 0.36s 终止）；
> 成本归因更正 = 真机与本机逐 clip 成本一致（0.70~0.84s），墙钟差全在 clip 条数（取材扩宽 620 条）。
> 取消残留已裁决 = 不自动删（缓存可复用），UI 显示「素材留在 <目录>，重跑直接复用」，vitest 162。
> 仍存边界：**>300s 档**没在本机复现（本机最重素材只 66.7s）；包侧进度单调判据「采到 ≥2 帧才判」，syn 轮 N/A。
> 明细 = STATE Current Task 顶部「补十七」块 + 方案文档 `mvp/docs/PLAN_EXPORT_ASYNC_20261013.md`。
