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

---

> **同批（续63 补十九立档）再迁出**：TODO P0 的续63 补十八块（三批未提交改动收口）。

> **▶ 2026-10-17（续63 补十八）— 上一会话三批未提交改动收口：音轨布局回退 + 竞品黑盒对照 + 取材扩宽 1.5【现读这条】**
> 接手时工作树 = 三批**未提交未出包**改动（交接件 `.agent/archive/HANDOFF_20261017_rea_competitor_blackbox.md`）。
> 先验 mtime 无孤儿写入者，再自己重跑门禁（不引用上一会话数字）。
> **① 音轨回退（`2afcec7`）**：「N 声道 + 未指定布局」源被原生 aac 拒收（rc=-22、0 字节）⇒ 抽素材整腿失败；
> 触发面 = **本产品自抽的 clip 天然是这种源**（5.1(side) 编进 MP4 后布局丢失）。次生陷阱 = 失败留 0 字节 +
> 剪映腿裸 `exists()` ⇒ 第二次导出静默写坏草稿。修 = 首跑参数逐字不变、失败后按 48k/stereo 重试一次 +
> 清半成品 + 判据收一 `app.exporters.clip_present`（教训 ⑲）。改前 A 臂 MediaError / 改后 A 臂 OK 447,853B
> 且 C 臂仍 rc=-22（判据真咬）。**同族已枚举**：另两处「存在即复用」自带有效性判据、无潜伏问题；
> `source_merge.py::_transcode_args` 同形缺陷**未改**（硬失败非静默，需单独立批）。
> **② 竞品黑盒对照**（同尺 `boundary_gt_v1.json`，竞品侧只读）：切点 ±1.0s P/R/F1 = 竞品 t0.50
> **0.885/0.958/0.920**（test1 F1 1.000）vs 我方 scn2 **0.550/0.917/0.687**（test1 0.200）；
> 后处理规则可用其 probs **逐帧复现**（1874/1874、491/491 全等）⇒ `sensitivity=18` 对切点集合无可观测作用。
> **导出层双臂**：我方切点 131/139 vs 竞品切点 130/139（严格同 135）⇒ **换更准切点在导出实得不涨**；
> 竞品优势在**信号源（TN 逐帧概率）**不在后处理三条。
> **③ `material_expand_rel_cap` 2.5 → 1.5（`beedb91`，口径用户拍板）**：四档（2.5/2.0/1.5/1.2）导出实得
> 131/139、严格 135/139 **逐位不变**，Σ素材宽 499.1→421.7s ⇒ 高 cap 扩宽是纯代价。
> ⚠️ **cap 1.5 ≈ 关闭扩宽**（不变式扩宽条数 0/0/0/1，本会话重跑独立印证；Σ421.7 ≈ core 419.9）=
> 卷轴只给解说引用窗、不再撑成完整镜头；温和档 = **2.0**（−9.4%）一句话可切。
> **门禁（本会话逐字跑，`work/verify_20261017/`）**：后端 **Ran 675 OK (skipped=2) / rc=0**（199.8s，
> `BACKEND_DEVICE directml amd`）· API **Ran 150 OK / rc=0** · 导出计划不变式 **FAILED=0 / rc=0**。UI 无改动面。
> **静态线两次判死已收线**（REA Win Ghidra P0 只收原生 PE；全量 PE 2G→OOM、10G 30min 无产出）⇒ 别再重开。
> **边界（如实）**：**观感面未测**（cap 1.5 成片接缝/硬切无读图，本批只数据面）· 黑盒只覆盖共同可测的
> 2mkv+test1 · **未出包** ⇒ 用户手上仍是 r24 · `mvp/ui` 零改动 ⇒ **mac 不必另 dispatch** · 未推远端。
> **主线「过渡不流畅」仍未结**：缺他指认的秒数 / 未转码原始 `movie_*.mp4` / `*.results.json`；
> `og720-720` 相似度 0.08 vs 0.97 自相矛盾仍挂账。
> 明细 = STATE Current Task 顶部「补十八」块 + `mvp/docs/` 无新增（本轮未写方案文档）。
