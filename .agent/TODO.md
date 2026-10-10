# TODO

> **结构说明（2026-10-07 瘦身）**：本文件 = P0/P1/P2/Blocked 四容器 + 指针，目标 ≤100 行。
> 历史条目（原 43 个 ▶ 块 + 「历史记录」全节）已**逐字**迁往
> `.agent/archive/TODO_history_20261007.md`，一条未删。防复发纪律见 AGENTS.md「上下文更新约定」：
> P0 保持 ≤1 块，新增块时旧块即迁 archive。

## P0 — Current

> **▶ 2026-10-11（续63 补十一·第十四轮）— 成片"重合"定性 + B 落地（取材扩宽相对护栏 K=2.5）【现读这条】**
> 多模态读图定性 = `scenes.npy` 漏切（3285-3323 一段 38s 实为 4 镜头）+「完整镜头」扩宽把 1s 短切撑进
> 假大镜头 → 卷轴重放。跨 4 片探针：现役 scene 重叠 Σ=1432.59s；护栏 `expanded≤K×core` K≤2.8 压回 core
> 底噪 8.00s、K=3 起漏 ⇒ **用户拍板 K=2.5**。已落地：`ExportConfig.material_expand_rel_cap=2.5` +
> `expand_material_spans(rel_cap=)` + `prepare_channel_plan`/`export_project`/镜像脚本三处透传。
> 门禁 后端 **630** / API **128** / invariants **FAILED=0**（扩宽 2mkv 62→4、覆盖 531→147s，三通道覆盖不变）。
> **状态：本批待 push（下一步）；push 后开 A 立项。**
> **A 立项（镜头检测漏切）** = 治本，动 `scenes.npy` 生成 → 需 `feature_version` bump + 全量重建索引 +
> 三指标重验；先写立项文档评审、不自动开码。B 只是绕开放大器，没修检测本身。
> 明细见 `CHANGELOG.md` 第十四轮 与 `STATE.md` Current Task 顶部同名块。

> **▶（历史·已完成）2026-10-10（续63 补十一·第十二轮）— 剪映导出崩修复：极短素材撑越 material.duration**
> 真机支持档 `POST /api/export` 抛未处理 `ValueError`（target 被 0.1s 下限撑到 100000µs > 素材 64000µs）
> ⇒ ASGI 掐连接 ⇒ UI 误报「无法连接后端服务 (fetch failed)」。修 = 抽 `_jianying_segment_speed`
> （锁原速仅在 `target_us≤mat_us`；末尾按素材时长回压 speed），正常素材行为不变。
> 门禁 = 后端 **626 OK(skipped=2)** · API **128 OK** · 新锁 `JianyingSegmentSpeedTest` 4 条（含结构锁）。
> **状态：已出包 r20**（未提交工作树构建；zip 内 backend.exe 与磁盘逐字节相等 sha16 `63987715436d5e31`，对 r19
> +635B）；包内 bundle/render/export-plan 三门 FAILED=0。**未提交**（等口令）。
> ✅ 剪映路径包内锁已补（选项 B）：accept 现另发 `format=jianying` 导出并断言 http=200 + 草稿 ≥1 segment；
> 对 r20 重跑 bundle FAILED=0（实测 1 段 speed=1.0 + og0-45.mp4）。只改 `mvp/scripts` 两脚本、不进 backend.exe
> ⇒ r20 zip 不变。边界：syn 只 1 条常规 clip ⇒ 不专门覆盖 <0.1s 回压分支（靠单测）。
> 未做的第二层（等裁决，别自己扩面）：`/api/export` 只 `except ApplicationError`，其它意外异常仍显示成误导性 fetch failed。
> release/ 现三档 r20/r19/r18，删 r18 等口令。明细见 `CHANGELOG.md` 第十二轮 与 `STATE.md` Current Task 顶部同名块。

> **▶（历史·已完成）2026-10-08（续63 补九）— 腿边界埋点 + 支持档降噪 + 跳格锁改按最大值口径**
> 口令「2」= 补七/补八 捞出的候选三件全做。动 `mvp/src` 两处（`app/locator_service.py` 埋点 ·
> `infrastructure/logging.py` 降噪）+ 后端/API 测试 + 两个常设复核脚本。**已提交 `ba5bedd`、已出包 r17**
> （r16 不含这三件 ⇒ 进包等 r17 授权）。门禁 = 后端 **617** · API **124** · vitest **144** ·
> app/desktop 双 typecheck `RC=0`（`work/r17_gates/gates_final.log`，rc 由 returncode 硬取）。
> 明细见 `CHANGELOG.md` 续63 补九 与 `STATE.md` Current Task 顶部同名的块。
> **① 埋点**：一次 locate 落 12 行 `locate leg=<名> elapsed=… units=a->b/48 chain=…` + 链首一行
> `legs=<12 个开关>`；每腿**一行**（不是进/出各一行，理由与 tick 不落日志都写在代码注释里）；
> 三条旋钮判定上移到链入口=同一真源；42 的 ramp 推送提到序列腿之前（序列耗时不再算进字牌腿，
> tick 上限 38 够不到 42 ⇒ 事件序列逐字不变）。后端 `LocateLegLoggingTest` 5 项，含**文件侧**
> 走 `configure_logging` 读回 `video_locator.log` 逐条核 + ramp 行为不变。
> **② 降噪**：`BenignConnectionNoiseFilter` 挂 asyncio logger，三条判据同时成立（asyncio +
> `_call_connection_lost` + ConnectionReset/BrokenPipe + winerror∈{10053,10054,10058}）⇒
> **降级 DEBUG 而非丢**（调试档 `SVL_LOG_DEBUG=1` 仍逐条留）；新增 `SVL_LOG_NOISE_FILTER=off`；
> stream handler 门槛显式 INFO。主证据 = **真实历史档 485 条逐条判据回归**
> （`work/r17_noise/classify_real_log.py`：485/485 判可降、其它 7 条真故障 0 误杀）+ 单测 6 项。
> **② 的复现臂七轮全 0，改换证据面闭合**：七种客户端强关打法（uvicorn 三臂四轮 / 裸 asyncio
> 三臂一轮 / 真服务栈 + keep-alive 超时当扳机一轮）在本机**一条都没造出**该形态，
> 连降噪之前的 r16 对照臂也 0 条 ⇒ 三个脚本一律「对照臂 0 条 ⇒ 下游判 N/A 不判通过」+
> 仪表自证行（证明落盘链路是通的）。**闭合办法 = `work/r17_noise/probe_inject.py`**：在真实
> 服务栈进程里走 asyncio **自己的** `call_exception_handler` → 默认处理器 → logger "asyncio"
> （真 ProactorEventLoop + 真 lifespan 的 `configure_logging()` + 真 `ConnectionResetError(10054)`
> + 真 traceback），剩下唯一变量就是 filter 在不在。三臂七判据 **J0-J6 全 PASS / VERDICT=CLOSED**：
> 不过滤 10/10 淹档 · 过滤臂 0 条 · 过滤+调试档 debug.log 以 DEBUG 留满 10 条 · 不误杀（同批注入的
> ValueError 形态 + 产品真故障在三臂都照旧进档）· 装配锁 · 仪表自证 · 确认在 ProactorEventLoop。
> **残留只一项**：「OS 会不会真报这个错」不由它证明，由历史真档 485 条逐条判据回归背书。
> **③ 跳格锁**：旧锁按均值建模（32≤40，输入 363s 还是修复前的）⇒ 改两条：锁 A 可见读数数由现役
> 宽度表**现算** + 均值 ≤30s；锁 B 实测最大停留 ≤45s；再加 `test_width_collapse_would_trip_the_lock`
> 反向验证（宽度压回 0.2 点 ⇒ 读数 12→3 ⇒ 锁 A 会红）。**更正 续63 补八 的腿归因**：patch 与 ISC
> 两条腿的 UI 消息文本一模一样，旧脚本按消息子串归因 ⇒ 混成一条；按 `phase` + 墙钟区间裁剪重算
> 两趟原始数据 ⇒ **37.3s 属 patch 腿**，ISC 腿最大 = 33.9s（源码树）/33.8s（包内）；
> 字牌腿 41.6/41.4s 仍是全程最坏单格 ⇒ 补八 的结论不受影响。逐腿表（腿墙钟/最大停留/读数数）：
> 字牌 `245.9·236.6 / 41.6·41.4 / 12`、拆分 `33.8·31.7 / 33.8·31.7 / 2`、
> patch `470.9·423.1 / 37.3·28.3 / 24`、ISC `419.7·408.9 / 33.9·33.8 / 19`。
> **④ 常设脚本**：`review_progress_chain.py` 判据改 ①逐腿最大 ≤45 ②逐腿均值 ≤30 ③全程 ≤60
> ④单调 ⑤对照登记只报数 ⑥埋点自证（腿行数=12 + 埋点 elapsed 与事件流墙钟对账 ≤max(8s,12%)；
> 0 行判 N/A）——归因函数已用已录 `test2.events.json` 离线回放校验；
> `review_packaged_support_log.py` 新增 C2 腿行面 + D 面写明降噪已上线（对真实档重跑 FAILED=0）。
> **⑤ 附带**：`locate()` 里 ISC「默认关」注释过期（`config.py:350 =True`，提交 7c6e485 翻的）
> ⇒ 就地更正，未动行为。教训入 `Known Issues`：**⑫ 按 UI 文本标签分组统计会串腿**、
> **⑬ 复现类探针必须自带仪表自证行 + 对照臂 0 条 ⇒ 下游 N/A**。
>
> **历史（同批 P0 块的前身，逐字见 archive/CHANGELOG）**：续63 导出计划层常态守卫 + 逐 clip 代价
> 实测 + r15 出包；补二~补五 成片包内实测 / 渲染隔离 / 卷轴去重 / 进度链三轮修正；补六 ⑥b 判负；
> 补七 r16 出包；补八 进度链独占实测 + 支持档文件侧闭合。
## P1 — Next

- [ ] **导出对话框 UI 修复（2026-10-10 第十三轮）— 代码已改、双 typecheck+vitest 绿，未提交未出包**：
      `ResultsPage.vue` 告警列表撑爆窗口（加滚动）+ 输出目录选不了（加「浏览…」复用 openDirectory IPC）。
      ⚠️ 前端改动要重建 r21 才在应用里可见。待口令：提交 + 是否随下次出包进 r21。
- [x] **mac 出包链 = ✅ 真机结清（2026-10-10 续63 补十一 第十一轮，读 live CI）**：run
      `37955484860`（head `31974f2`）三 job 全绿；`macos-package` step 11 走通道 A 直链+sha256
      三份 try=1 即中 ⇒ step 15 门槛绿 ⇒ step 16 publish 绿 ⇒ release `mac-alpha` 新增
      `Video-Locator-mac-arm64.zip` 916,769,503B（2026-10-09T16:27:38Z）。第五/六轮担心的
      「等值校验首次生效就在 CI 上」已验通。H3 正式化项（按平台裁 `extraResources` 的 ≈88MB 死资产）另计。
- [x] ~~待口令：Windows release/ 三档删 r17~~ = ✅ 已删（2026-10-10）：现两档 r19 现役 + r18 回滚；
      删前 `zip_identity.py` 验回滚档 r18 `testzip=None` / 7,078 条目 / backend.exe sha16
      `2eb651d38003d433` 与档案一致，释放 ≈940MB。与 mac 线无关。
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
- [x] **r16 出包 = ✅（2026-10-08 续63 补七，口令「推ci然后打包吧」）**：
      `Video-Locator-win-x64-20261008r16.zip` 981,659,900B / 7,078 条目 / `testzip=None` /
      **zip 内** backend.exe `sha16=7c9533750776a79a`。bundle · render（**R2 转绿**）· 三防 ·
      导出计划守卫 · 启动冒烟 · 包体产物探针（靶子由源码树现算）= **全部 FAILED=0**。
- [x] ~~两处新 UI 目检~~ = ✅（续63 补三，顺带修掉失效 token `--c-warn`→`--warn`）
      → **续63 补四：用户裁决删掉这两处显示**（侧栏内存行 + 黄字心跳提示），
      后端字段与 types 契约镜像保留。**别再把它当 UI 欠账重新提。**
- [x] ~~分发包保留~~ = ✅ 口令「只留r15和16」（2026-10-08）：删 r13 + r14（~1.96GB），
      留 r16 现役 + r15 回滚；删前两份均 `testzip=None` / 7,078 条目 / backend.exe 身份逐代核对。
- [ ] **续63 补十（2026-10-08）= r17 已出包并全链验收绿**：`Video-Locator-win-x64-20261008r17.zip`
      981,665,352B / 7,078 条目 / `testzip=None` / **zip 内** backend.exe 77,472,765B
      `sha16=7e3fe311bdf62b36`（== 磁盘构建；r16 = 77,469,132 / `7c9533750776a79a`）。
      bundle（含两条新包侧锁）· render · 三防 · 导出计划守卫 · 启动冒烟 AFTER_KILL=0 ·
      包体产物探针 = 全部 FAILED=0。出包时未提交，**随后同一内容已提交 `ba5bedd`**
      （构建后没再动 `mvp/src`）=> 包与该 commit 的产品源码逐字对应。
      r15 是否按「最新+上一档」保留规矩删除，等口令。
- [x] ~~待口令：本批（续63 补六~补九）git 提交~~ = ✅ 已提交 `ba5bedd`（代码/测试/脚本 8 文件）
      + 档案笔，推 origin/master。
      archive 两份 + 两个常设脚本（清单见 STATE `Next Actions` 第 1 条）。
- [ ] **r17 出包时（等授权）待办两件**：① accept 加包侧硬断言「真实 analyze 后支持档必须出现
      12 行 `locate leg=`」= 埋点进包的锁；② 出包后让用户自然跑一段（历史那 485 条就是这么攒的），
      再按 `review_packaged_support_log.py` C2/D 面读新档（自然攒一份真档）。
      注：降噪本身**已用真进程注入三臂闭合**（`work/r17_noise/probe_inject.py` J0-J6 全 PASS），
      这两条只是把它升级成「每次出包自动核」+ 补上「OS 真触发」那一项残留观察。
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
