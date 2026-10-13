# TODO

> **结构说明（2026-10-07 瘦身）**：本文件 = P0/P1/P2/Blocked 四容器 + 指针，目标 ≤100 行。
> 历史条目（原 43 个 ▶ 块 + 「历史记录」全节）已**逐字**迁往
> `.agent/archive/TODO_history_20261007.md`，一条未删。防复发纪律见 AGENTS.md「上下文更新约定」：
> P0 保持 ≤1 块，新增块时旧块即迁 archive。**续迁**：P1 里已结清/已被取代的历史条目（r15~r17 出包身份、
> 第十轮 mac 出包链、竞品 opcode 结案等 49 行）于 2026-10-13 逐字迁 `archive/TODO_history_20261013.md`。

## P0 — Current

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
> **未结两项**：① **mac 未更** —— `credential fill` 两次非交互返回空（要重登 GCM），不弹窗不重试，
> 需他自己 dispatch 或先重登；② **r21 待删**（三档规矩，等口令，r22 已验可作回滚档）。
> 真素材长导出已实测（test2 批 66.7s/86 clip：首帧 0.0、81 条逐 clip 帧、收尾帧可见、取消 0.36s 终止）；
> 成本归因更正 = 真机与本机逐 clip 成本一致（0.70~0.84s），墙钟差全在 clip 条数（取材扩宽 620 条）。
> 取消残留已裁决 = 不自动删（缓存可复用），UI 显示「素材留在 <目录>，重跑直接复用」，vitest 162。
> 仍存边界：**>300s 档**没在本机复现（本机最重素材只 66.7s）；包侧进度单调判据「采到 ≥2 帧才判」，syn 轮 N/A。
> 明细 = STATE Current Task 顶部「补十七」块 + 方案文档 `mvp/docs/PLAN_EXPORT_ASYNC_20261013.md`。

## P1 — Next

- [x] ~~r23 出包（等口令）~~ = ✅ **已出并四道全绿（2026-10-13 00:1x）**：
      `Video-Locator-win-x64-20261012r23.zip` 981,687,209B / 7,078 条目 / testzip=None /
      zip 内 backend.exe 77,493,384B sha16 `537bcca18760de77` == 磁盘（matches_disk_build=True）；
      **zip 内 `bridge.js` 与磁盘逐字节相同**（8,882B，含 node:http + httpRequester + data 透传）。
      bundle **28 PASS/0 FAIL**（两条新桥接锁由 r22 上的预期红转绿）· render **8 PASS/FAILED=0**
      （R1 wall=60s · 64 段无交叠 · h264_amf · 隔离在位）· 不变式 **FAILED=0** · 冒烟 AFTER_KILL=0。
      ⚠️ 订正：本条原写「预期 backend.exe sha16 与 r22 **逐字相同**」**被实测推翻** —— 实为同尺寸、
      仅 9 字节差（3 段各 3 字节，两处同值=归档长度字段）⇒ PyInstaller 非确定性构建；
      `git diff 36dec63..a84119d -- mvp/src mvp/api` 为空佐证没动 Python 运行面。
- [x] ~~待口令：release/ 四档删 r20~~ = ✅ **已删（2026-10-13 00:2x）**：删前 `zip_identity.py` 验回滚档
      r21 `testzip=None` / 7,078 条目 / backend.exe 77,493,043B / sha16 `fa3c394567cc17d2` 与档案逐字一致；
      r20 自身本批早先亦验过（`63987715436d5e31` 一致）。⇒ 现三档 r23/r22/r21。
- [x] ~~mac 包仍带同一缺陷，待用户定是否跟更~~ = ✅ **已 dispatch（2026-10-13 00:3x）**：run
      `38277827813`（ref=master，head `4fe0d96a5`，HTTP 204）。机制已读 workflow 本体验明：门槛绿 ⇒
      `gh release upload mac-alpha --clobber` **自动就地覆盖**，无需人工；门槛红 ⇒ publish 不跑、留旧包。
      用户明确「mac zip 不用你确认」⇒ **不再自行追读该 run**（watcher 日志留 `work/watch_mac_run.log`）。
- [x] ~~导出异步化（B 方案）~~ = ✅ **已落地（2026-10-13 续63 补十七）**：
      `POST /api/tasks/export` 进现有 tasks 框架（进度 0→99 + 可取消），UI 已切任务通道；
      同步 `/api/export` 保留未删。⚠️ 未提交、未出包 ⇒ 用户手上还没有；进包 = r24（mac 另 dispatch）。

- [x] ~~导出对话框 UI 修复（2026-10-10 第十三轮）~~ = ✅ **已提交并两代进包**（2026-10-12 复核）：
      `ResultsPage.vue` 告警列表加滚动 + 输出目录「浏览…」= 代码笔 `aacfaa9`（2026-10-10 23:50，实测在 master），
      `git merge-base --is-ancestor aacfaa9 09714ab` 通过 ⇒ 已在 **r21**，r22 同链继承。本条无遗留。
- [ ] **六项立项已拍板（2026-10-07），先入文档后动码**——计划 =
      `mvp/docs/PLAN_HARDENING_SIX_ITEMS_20261007.md`，执行顺序建议：②设备回报 → ①低内存
      收缩 → ③防抖+心跳（小三件一批）→ ④独立进程监督（单独批）→ ⑤导出实得口径（与性能
      口径对齐联动）→ ⑥换形态探针族（研究线，沙盒纪律）。逐项完成打勾：
      - [x] ② 子进程设备回报标记 = ✅（2026-10-07：backend stdout 一次性 `BACKEND_DEVICE <name> <type>` 标记行（懒构建点=真实解析点）；UI 首启 READY 前拉 actual 三元组、buildIndex 不再用索引历史标签覆盖徽标）
      - [x] ① 低内存收缩 batch+预取 = ✅（2026-10-07：`media/resource_budget.py` 纯函数三档（unknown→全默认零语义；tight/critical 收缩），接 `_grab_frames_parallel` 线程与 `build_tp_index` 簇上限（切簇只改批次不改帧），`/api/settings/device` 补 low_memory_mode/memory_tier/grab_workers/max_cluster_frames）
      - [x] ③ 阶段进度防抖+心跳 = ✅（2026-10-07：`api/tasks/debounce.py` ProgressDebouncer（同阶段最小间隔合并、阶段切换/终态直通、held 先补发）接 analyze/render worker；Task 补 `last_event_at` 心跳并暴露 to_dict/UI 契约；进度条 0.2s 过渡既有）
      - [x] ④ 独立 GPU 工作进程监督 = ✅ 第一步任务级隔离（2026-10-07：`api/tasks/isolated.py`，analyze/render 子进程化，硬崩无信封退出 → failed(带 exitcode)，服务与其它任务存活；取消 = terminate；spawn 不可用回落线程内；`run_backend` 补 freeze_support；故障注入钩子 + 6 单测含真实 spawn。打包态 spawn 验证挂 r15 accept。监督重启（崩溃计数+冷却）暂不需要——任务全为用户显式发起，无自动重试消费方）
      - [ ] ~~⑤ 指标 HIT ≠ 导出实得~~ → **2026-10-07 用户裁决不做，丢回搁置区**（重启需用户再提；与「性能口径三处对齐」同批处理最合适）
      - [x] ⑥ 换形态探针族：**b 已实跑并判负关闭**（2026-10-08 续63 补六，`FINDINGS_TWO_STAGE_SAMPLING_20261008.md`）；a 置信非饱和 / c E3 换载体 / d 退化门换判据 **未跑**（本轮按口令只跑 b；是「未跑」不是「已证否」）。
            续63 复核建议（**待拍板，不自动开跑**）：先只跑 **b**，且判据换掉——档案已有
            「2fps vs 1fps 密度探针：生产严格净 0、建索引 ×2 耗时」，密度↑不改落点 ⇒ b 的
            精度上限有限，可兑现收益在**建索引耗时/首屏延迟**（现役 22~31min/片）。
            a 撞护栏（Confidence 公式冻结+不标定），d 的退化门默认关无生产影响 ⇒ 优先级最低。

## P2 — Later

- [x] TODO 瘦身 = ✅（2026-10-07：历史迁 `.agent/archive/TODO_history_20261007.md`，
      防复发纪律写入 AGENTS.md）。

## Blocked

- [ ] H4（Windows NVIDIA / CUDA）= `H4_GPU_RUNNER_UNAVAILABLE` —— 无可用 Windows GPU runner，
      需用户提供 NVIDIA 环境与计费权限（见 `.agent/STATE.md` H4-0 记录）。
