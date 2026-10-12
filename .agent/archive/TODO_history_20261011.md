# TODO 归档（2026-10-11）— P0 超限块逐字迁移

> 按 AGENTS.md「档案防复发纪律」：TODO.md 的 P0 保持 ≤1 块。本次新增「续63 补十二」块，
> 同批把下面 3 个已退休的 P0 块**一字未改**迁出（迁移时回滚点 = 本地 HEAD `4b44a47`）。

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

<!-- 以下 = TODO.md P0 退休块「续63 补十二」，2026-10-11 逐字迁入 -->

> **▶ 2026-10-11（续63 补十二）— A1 离线扫参 + 边界尺子 + A2 预演【现读这条】**
> 口令「3」= 开 A 第一步。**`mvp/src` 零改动**（只加尺子 + harness + 发现文档）。
> 尺子 = 4 片 44 窗 × 12s（540s / 全片 31124s 的 1.7%）4fps 接触表逐格目检 ⇒ 150 条边界（125 conf=high），
> 入库 `mvp/scripts/shot_detect/boundary_gt_v1.json`；复现
> `PYTHONPATH=mvp/src;mvp python mvp/scripts/shot_detect/eval_shot_detector.py --mode ablation|arms|ceiling|holdout|region`。
> **读数**：现役 `scenes.npy` P 0.707 / **R 0.232** / F1 0.349（±1.0s；主容差只能 ±1.0s，因为现役索引是 **1fps**，
> 立项文档写的 0.5fps 是错的）；定向区 test2 3285-3333 目检 21 边界 vs 现役 2 段（38s+47s 假镜头）。
> 分腿消融：`z_thresh` 1.5→关 单腿 R 0.232→0.504；`min_shot_s` 3.0→1.0 单腿 +0.008 但与关 z **强交互**（合 0.664）
> ⇒ 教训 ⑰「单旋钮消融会互相掩蔽」。天花板：test2 **44% 真边界在 CLS 序列上无局部极大** ⇒ 阈值救不了。
> 留出窗对照：调参臂 F1 0.727(选参)→**0.653(留出)**，现役 0.341→0.359 ⇒ 增益不是过拟合。
> A2 预演：像素通道（160×90/10fps，直方图 L1 与 mean-abs-diff 各半 + NMS）同尺 **P 0.706 / R 0.864 / F1 0.777**；
> ⚠️ 朴素并集 R 0.944 但 **P 0.461** ⇒ 融合不能 OR。成本：300s 片段解码 17~18s 且**与输出帧数几乎无关**
> ⇒ A2 边际 ≈ +5min/5000s 片（现役 22~31min），纯 CPU 可与 GPU 推理并发。
> **下一步 = 等用户拍板**：(a) A2 开码（推荐）/ (b) A1 调参批（R 0.23→0.63，代价=全片边界数翻倍，属 runtime）/
> (c) A3 当第三方尺子核偏置。B 护栏 K=2.5 保留。
> ⚠️ 未证面：尺子 1.7% 抽样、test1 仅 3 条高置信 ⇒ 不外推；目检与像素同源 ⇒ 像素 R 是偏乐观上界；
> 只做了「窗」的二分没做「片」的二分；P 在两半窗间抖动大 ⇒ P 差 <0.1 不可读；本批未测「场景表变好后下游是否变好」。
> **未提交**（等口令）：`mvp/scripts/shot_detect/*` + `mvp/docs/FINDINGS_SHOT_DETECTION_A1_20261011.md`
> + `PLAN_SHOT_DETECTION_20261011.md` 的提交指针更正（B 代码笔 `098021b`，原写 `c873e18` 是档案笔）。
> 明细 `mvp/docs/FINDINGS_SHOT_DETECTION_A1_20261011.md` 与 `STATE.md` Current Task 顶部同名块。

### 迁移（2026-10-12 补十五立档时逐字迁入）：TODO P0「续63 补十三」块

> **▶ 2026-10-11（续63 补十三）— A2 落地：scn2 = 像素通道 + CLS 证据 + 持续性门【现读这条】**
> 已落地并通过验收：尺子（生产落盘表）P/R/F1 0.732/0.832/0.779、四片回归严格 130→135、
> **导出实得 112→131（+19）**、后端 668 / API 128 / 不变式 / 成套体检全绿；成片渲染门槛曾红，查明是**判据自身两处缺陷**
> （取帧约定 + 绝对偏移判据超出测量精度），已改判离散度并转绿（`VERDICT PASS`，新增 7 项锁）。
> 本批两处真缺陷：持续性门 v1「后块≠前块」在真数据上无效（v2 改判「后块内部要落定」）、
> 像素→网格吸附一律向上取整（同批候选 0.785→0.832）。
> ~~**未提交、未出包（等口令）**~~ → **✅ 已提交 + 已出包 r21（2026-10-11 续63 补十四，
> 口令「push吧，然后出包」）**：代码笔 `9481f39` + 档案笔 `09714ab` 推 `c873e18..09714ab`；
> **r21 = 干净 commit `09714ab` 构建**（出包前同树重跑后端 668 OK / API 128 OK / 工作树干净）。
> 包内三道验收全绿：bundle **26 PASS/0 FAIL**（DirectML wall=33.1s · 剪映 http=200 · 隔离 reaped 0 ·
> 腿埋点在位）· render **FAILED=0**（64 段无交叠 · h264_amf · wall 60.1s）· 不变式 **FAILED=0**。
> zip `Video-Locator-win-x64-20261011r21.zip` 981,685,359B / 7,078 条目 / testzip=None /
> **zip 内 backend.exe 77,493,043B sha16 `fa3c394567cc17d2` == 磁盘构建**（对 r20 +18,145B，
> 与「r20 后 src 只有 A2」相容）。⚠️ 包内未实测：老用户 derived_stale 首触重刷（accept 夹具=全新索引态）。
> (iii) test1 长镜头专项**已定性闭合**（门 v2 判负不放宽，主因=同场景切换两通道皆无信号，
> 见 STATE `Current Problem` 首条附注）；(ii) 老用户升级路径**已拍板 = 维持现状、文案不加预计耗时**
> （口令「不用加」）。**本批无遗留**；release/ 现三档 r21/r20/r19（**r18 已按口令删除，2026-10-11**，
> 删前验 r19 可读与档案逐字一致，释放 ≈940MB）。
> 明细 = `.agent/STATE.md` Current Task 顶部「补十三」块 + `work/v2_accept/` 验收日志。
