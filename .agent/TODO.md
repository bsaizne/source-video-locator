# TODO

> **结构说明（2026-10-07 瘦身）**：本文件 = P0/P1/P2/Blocked 四容器 + 指针，目标 ≤100 行。
> 历史条目（原 43 个 ▶ 块 + 「历史记录」全节）已**逐字**迁往
> `.agent/archive/TODO_history_20261007.md`，一条未删。防复发纪律见 AGENTS.md「上下文更新约定」：
> P0 保持 ≤1 块，新增块时旧块即迁 archive。

## P0 — Current

> **▶ 2026-10-07（续63）— 导出计划层常态守卫 + 逐 clip 代价实测 + r15 出包【现读这条】**
> 根因判断：续62 两批真缺陷都不是函数写错，是**同一套五步计划序列在 service 里抄了三遍**
> ⇒ 出口会漏接。收口 = `exporters.prepare_channel_plan`（四通道唯一入口，顺序硬固定，
> stats 自带 `audit_pre_trim`/`audit` 两份体检）+ `audit_source_overlaps`（只读；**必须扫全对**，
> 真实复用常隔着中间段）。新 `mvp/tests/test_export_plan_guard.py` 19+3 项含 AST 结构锁
> （`build_export_plan`/`trim_adjacent_source_overlaps` 产品调用点只允许在 helper 内）。
> 常态脚本入库 `mvp/scripts/check_export_plan_invariants.py`（真实四片 × 四通道，退出码可挂门槛）：
> 贴接重叠 2/0/3/7 对 → **0**，并集覆盖 Δ=**0.00**，三通道同 plan=是。
> 代价（补二欠账）：2mkv 卷轴 64 条/宽度 815.75s/去重后抽取 **56 次 701s**；源码树双臂墙钟
> A(扩宽)=81.1s vs B(core)=33.0s（A/B 2.46，test2 3.02）⇒ 代价主体是**取材扩宽**不是逐 clip，
> 分钟级，r15 可出。
> **本批抓到并修的三处**：① 渲染层 `vue-tsc` 5 错（Mock 缺 `last_event_at`+徽标夹具越契约）
> ⇒ **更正**续62 补五/补六「双 typecheck 干净」自报不实；② 打包态隔离子进程不走 ASGI
> lifespan ⇒ `configure_logging()` 没人调，INFO 被 lastResort 丢弃（包内 stdout 与支持档
> 一起缺分析记录）+ 父进程拿到终态就 terminate 吞尾 ⇒ 修 = 子进程自配日志/行缓冲/flush +
> 正常终态先 `join(CHILD_GRACE_S)`，父子日志同 `task_id`；③ **我自己引入的回归**：扩宽参数
> 误透给时间线三通道（EDL 覆盖 134s→531s），由 r15 包体探针抓到 ⇒ 改硬约束（非剪映通道传
> `material_expand` 直接 ValueError）。
> 门禁 = 后端 **599** · API **120** · vitest **144** · app+desktop typecheck 双绿。
> **续63 补二**：成片通道包内实测补上（64 段 `clip_ranges` 与源码树逐字段相同、136.366 vs
> Σ136.344s、h264_amf、成片顺序紧邻交叠 0 对）⇒ 升为常设 `mvp/scripts/accept_packaged_render.py`；
> 该实测抓到 `submit_render` **漏传 `isolated`**（渲染从未进隔离子进程，档案口径不实已更正）；
> 卷轴去「紧邻同素材连放」默认开（2mkv 64→63 条、宽度 815.75→791.75s、**覆盖 531.0s 不变**），
> 机制更正 = 紧邻重复只在剪映卷轴（根因 取材扩宽 × 紧凑拼接，非重排）；①③ 的 UI 接线完成
> （侧栏低内存行 + ≥120s 无新事件提示）。门禁 = 后端 **602** · API **122** · vitest **146** ·
> 双 typecheck + renderer build 绿。**r15 不含这三件**。
> 明细 CHANGELOG 续63 / 续63 补一 / 续63 补二。

## P1 — Next

- [x] 待用户口令：git 推送 = ✅（2026-10-07 续63 口令「按你的想法来」→ 推 `6a0ef88..aba3a21`
      实测 11 笔；档案原写 12 笔为计数过期）。
- [x] **r15 出包 = ✅（2026-10-07 12:33）**：`Video-Locator-win-x64-20261007r15.zip`
      981,659,630B / 7,078 条目 / `testzip=None` / backend.exe `sha16=d45656f585826f4a`。
      accept **FAILED=0**（新增 4 条隔离硬断言全过）· 三防 **FAILED=0** ·
      启动冒烟 Electron 4+backend 1 / AFTER_KILL=0 · 包体剪映探针
      `work/r15_jianying_pkg/probe.py` **FAILED=0**（EDL 134.12s、卷轴 64 条/56 文件/
      815.75s/531.0s 与计划层逐字对齐、包内墙钟 80.7s）。
      ⚠️ 该探针同时抓回我本批引入的回归：取材扩宽参数误透给时间线三通道（EDL 覆盖被撑到 531s）
      ⇒ 已改硬约束 + 单测锁。
- [x] ~~待裁：卷轴紧邻同素材连放~~ = ✅ 已按收窄方案实现（续63 补二，默认开 + config 旋钮 +
      3 条单测 + 守卫脚本逐条比对）。
- [ ] **待授权：r16 出包** —— 渲染隔离修复 + 卷轴去重两件在源码树，r15 不含；
      出包后跑 accept + `accept_packaged_render.py`（对 r15 现况如实报 R2 红）+ 三防 + 启动冒烟。
- [x] ~~两处新 UI 目检~~ = ✅（续63 补三，顺带修掉失效 token `--c-warn`→`--warn`）
      → **续63 补四：用户裁决删掉这两处显示**（侧栏内存行 + 黄字心跳提示），
      后端字段与 types 契约镜像保留。**别再把它当 UI 欠账重新提。**
- [ ] 待口令：本批 git 提交；`release/` 现有 r13+r14+r15，按「最新+上一档」可删 r13（~0.98GB）。
- [x] 竞品 opcode 通道可行性 = ✅ 已试采结案（2026-10-07 续62 补三）：字面通道判死（0 pyc，
      Nuitka AOT）；机器码绑定通道判死（LEA→blob / MOV→平铺数组两形态不成立，全量反汇编
      路径未立项）；**blob 序通道打开**（blob 序=源码书写序，进度 pct 互证；tracker 阶段词表
      「特征→候选→召回→定位」与 V2 流程注册序已产出）。
      明细 `competitor_cutmatch/FINDINGS_OPCODE_CHANNEL_20261007.md`。
- [ ] **六项立项已拍板（2026-10-07），先入文档后动码**——计划 =
      `mvp/docs/PLAN_HARDENING_SIX_ITEMS_20261007.md`，执行顺序建议：②设备回报 → ①低内存
      收缩 → ③防抖+心跳（小三件一批）→ ④独立进程监督（单独批）→ ⑤导出实得口径（与性能
      口径对齐联动）→ ⑥换形态探针族（研究线，沙盒纪律）。逐项完成打勾：
      - [x] ② 子进程设备回报标记 = ✅（2026-10-07：backend stdout 一次性 `BACKEND_DEVICE <name> <type>` 标记行（懒构建点=真实解析点）；UI 首启 READY 前拉 actual 三元组、buildIndex 不再用索引历史标签覆盖徽标）
      - [x] ① 低内存收缩 batch+预取 = ✅（2026-10-07：`media/resource_budget.py` 纯函数三档（unknown→全默认零语义；tight/critical 收缩），接 `_grab_frames_parallel` 线程与 `build_tp_index` 簇上限（切簇只改批次不改帧），`/api/settings/device` 补 low_memory_mode/memory_tier/grab_workers/max_cluster_frames）
      - [x] ③ 阶段进度防抖+心跳 = ✅（2026-10-07：`api/tasks/debounce.py` ProgressDebouncer（同阶段最小间隔合并、阶段切换/终态直通、held 先补发）接 analyze/render worker；Task 补 `last_event_at` 心跳并暴露 to_dict/UI 契约；进度条 0.2s 过渡既有）
      - [x] ④ 独立 GPU 工作进程监督 = ✅ 第一步任务级隔离（2026-10-07：`api/tasks/isolated.py`，analyze/render 子进程化，硬崩无信封退出 → failed(带 exitcode)，服务与其它任务存活；取消 = terminate；spawn 不可用回落线程内；`run_backend` 补 freeze_support；故障注入钩子 + 6 单测含真实 spawn。打包态 spawn 验证挂 r15 accept。监督重启（崩溃计数+冷却）暂不需要——任务全为用户显式发起，无自动重试消费方）
      - [ ] ~~⑤ 指标 HIT ≠ 导出实得~~ → **2026-10-07 用户裁决不做，丢回搁置区**（重启需用户再提；与「性能口径三处对齐」同批处理最合适）
      - [ ] ⑥ 换形态探针族 4 条（a 置信非饱和 / b 两级采样 / c E3 换载体 / d 退化门换判据）。
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
