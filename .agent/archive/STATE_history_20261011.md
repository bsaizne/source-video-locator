# STATE 归档（2026-10-11）— Current Task 超限块逐字迁移

> 按 AGENTS.md「档案防复发纪律」从 `.agent/STATE.md` `Current Task` 迁出的整块，**一字未改**。
> 迁出原因：新增「续63 补十二（A1 离线扫参 + 边界尺子 + A2 预演）」块后 `Current Task` 会超 3 块。
> 迁移时的回滚点 = 本地 HEAD `4b44a47`（远端 origin/master 在 `c873e18`）。
> 该块内容（腿边界埋点 + 支持档降噪 + 跳格锁口径）已提交 `ba5bedd` 并已随 **r17** 进包，全部结清。

> **▶ 2026-10-08（续63 补九）— 腿边界埋点 + 支持档 proactor 降噪 + 跳格锁改按最大值口径【下个对话从这里读起】**
> 用户口令「2」= 上一批实测捞出的候选三件**全做**。动 `mvp/src` 两处 + `mvp/api/tests` + `mvp/tests`
> + 两个常设复核脚本。**现已提交 `ba5bedd` 并出包 r17**（见下面 补十 块）。
> 门禁 = 后端 **617** OK(skipped=2) · API **124** OK · vitest **144** · app/desktop 两个 config
> **分别** typecheck `RC=0`（留证 `work/r17_gates/gates_final2.log` + `gates.json`——final2 是
> **档案与注释全部落定之后**重跑的那一轮，final.log 是同批早一轮；退出码由
> `subprocess.returncode` 硬取；门禁 runner 自己先崩在两处：Windows 上 `npx` 要走 `shutil.which`，
> vitest 输出里的 U+2713 会把 cp936 控制台的 print 打断——RC 已拿到却挂在打印尾巴）。
> **① 腿边界埋点**（`app/locator_service.locate`）：一次 locate 落 **12 行**
> `locate leg=<名> elapsed=<秒> units=<a>-><b>/48 chain=<自链入口累计>` + 链首一行
> `locate refine start units=0/48 legs=<12 个开关 on/off>`。**每腿一行（完成时）而不是进/出各一行**：
> 腿 k 的「进入」就是腿 k-1 的「完成」，链首开关行交代「这条腿跑没跑」⇒ 同样可复核、行数减半；
> **腿内 tick 一律不落日志**（一次真实 locate 的 tick 上百条，会把同批刚做完的支持档降噪直接抵消）。
> 三条旋钮判定 `_split_on/_patch_on/_isc_on` 整体上移到链入口 = 埋点行与腿执行**同一真源**。
> 边界放在**腿与腿的切换处**而非刻度表原位置：旧 42 边界排在序列腿之后 ⇒ 序列腿耗时算进字牌腿；
> 把 42 的 ramp 推送提到序列腿之前（tick 上限 = 10+int(32*0.9)=38 够不到 42 ⇒ 显示逐点与事件序列
> **逐字不变**）。验收 = `mvp/tests/test_locator_service.py::LocateLegLoggingTest` 5 项：行数恰 12 且
> 顺序=执行顺序 · 刻度/累计单调 · elapsed 求和=累计(±0.3s) · 开关行 12 项 · tick 不污染 ·
> **ramp 行为不变**（终点仍 48、不回退）· **文件侧**（走 `configure_logging` = 打包态同一套 handler
> 栈，跑完读回 `video_locator.log` 逐条核，不是只在 logger 上挂 assertLogs handler）。
> **② 支持档降噪**（`infrastructure/logging.py`）：`BenignConnectionNoiseFilter` 挂 **asyncio logger**
> （logger 级 filter 才对传播记录生效；挂 root 等于没挂）。判据三条**同时**成立才算噪声：名字 asyncio
> + 回调 `_call_connection_lost` + `ConnectionReset/BrokenPipe` 且 winerror（缺省退 errno）∈
> {10053,10054,10058} ⇒ **降级为 DEBUG 而不是丢**：支持档（INFO+）与 stdout 不再收录，调试档
> （`SVL_LOG_DEBUG=1`）逐条保留；新增 `SVL_LOG_NOISE_FILTER=off` 开关（支持人员临时看全量 + 双臂
> 对照的对照臂）；stream handler 门槛显式 INFO（原 level=0 ⇒ 降级记录仍会刷 stderr）。
> **主证据 = 真实历史支持档逐条判据回归**（`work/r17_noise/classify_real_log.py`）：现役真档 19,877
> 条记录 / **492 条 ERROR**，噪声族 **485/485** 判可降、其它 **7 条真故障 0 误杀**
> （`app.locator_service` 2 + `api` 5）；另单测 6 项（含「我方模块同名异常照旧 ERROR」等三类反例 +
> filter 幂等）。
> **真机臂：客户端强关在本机复现不出，改用「真进程注入双臂」闭合**（追加轮，见本节末「追加」）——
> `work/r17_noise/probe.py` 的 uvicorn 三臂（r16 包内 / 源码树 / 源码树+调试档）跑了**四轮**
> （发完即 RST → 先 recv 64KB 再 RST 并在 preview_dir 放 40MB 文件走 FileResponse → 补
> `MEDIA_FFPROBE`（第二轮那 18 条"真故障"其实是探针自己缺 ffprobe 的 500）→ 各臂档目录先清空重跑），
> `probe_proactor.py` 的裸 asyncio 三臂跑一轮（含按 stdlib 源码反出来的「关闭时仍挂着读」打法，
> `proactor_events.py:165` 的 `sock.shutdown()` 就是历史那条 traceback 的行号），
> `probe_keepalive.py` 的真服务栈 + keep-alive 超时当扳机再跑一轮（客户端只收响应头就 RST、
> 晾服务端 6.5s 让它自己回收）——**七轮全部 0 条**，连降噪之前的 r16 对照臂也 0 条
> ⇒ 「修复臂看起来干净」= **空跑**，不能当验收。三个探针脚本都已改成
> 「对照臂 0 条 ⇒ 下游一律 N/A 不判通过」并加仪表自证行（`module=probe.*`）证明落盘链路是通的。
> **闭合办法**（`work/r17_noise/probe_inject.py`，VERDICT=CLOSED / FAILED=0）：不再赌 OS 时序，
> 而是在**跑着真实产品服务栈的进程里**走 asyncio 自己的记录路径 —— 真 `create_app()` +
> 真 `uvicorn.Server(Config(..., access_log=False))`（与 `launcher.build_server` 同参）+
> 真 ProactorEventLoop + lifespan 里产品的 `configure_logging()` + `loop.call_exception_handler()`
> 交给 **asyncio 默认异常处理器** 落 logger "asyncio"，异常是真 `ConnectionResetError(10054,…)`
> 带真 traceback；唯一代打的是"抛它的回调不是 `_call_connection_lost` 本尊"。三臂七判据全 PASS：
> J1 off 臂 10/10 条该形态进支持档（含 WinError 10054）= 不过滤就会淹档 ·
> J2 on 臂同一注入 **0 条** · J3 on_debug 支持档仍 0 条而 debug.log 以 DEBUG 留满 10 条
> （降噪≠丢信息）· J4 不误杀：同批注入的 ValueError 形态 + 产品自己的真故障在三臂**都**照旧进档 ·
> J0 装配锁（off 未装 / on 已装）· J5 仪表自证行 · J6 确认跑在 ProactorEventLoop 上。
> ⇒ ② 的证据链 = 历史真档 485 条逐条判据回归（判据对不对）
> + 真进程注入三臂双臂对照（链路生不生效）+ 单测 6 项（不误杀的反例齐全）。
> **仍然没有的**只有一件：本机一次"内核真报错"的直接观察（登记为已知局限，不影响上面三条）。
> 同批实测通过的半边：真故障 ERROR（POST /api/index 指向不存在文件）在修复臂支持档里照常可见。
> **③ 跳格锁改按最大值口径**（`mvp/api/tests/test_tasks.py`）：旧锁
> `round(0.1/(1.7*32/48/67)*(363/67)) = 32 ≤ 40` 算的是**均匀假设下的均值**，输入 363s 还是修复前的
> 腿耗时。改两条：**锁 A** 可见读数数由现役宽度表**现算**（`map_progress_stage` 上取值，宽度一改
> 就红）+ 均值 ≤30s；**锁 B** 实测最大停留 ≤45s（两趟最坏）。另加 `test_width_collapse_would_trip_the_lock`
> **反向验证**锁 A 真能抓到 run3 那种「按腿数量平分」回归（0.2 点 ⇒ 读数 12→3 ⇒ 均值超阈值）。
> **顺带更正 续63 补八 的腿归因**：patch 与 ISC 两条腿的 UI 消息文本**一模一样**（都是
> 「画面深度复核 N/67」），旧 `review_progress_chain.py` 按消息子串归因 ⇒ 两条腿混成一条
> （档案那句「ISC 腿 41 格 最大 37.3s」里的 41 格 = patch+ISC 合算）。按事件 `phase` + **墙钟区间
> 裁剪**重算两趟原始数据：
> `腿 / 腿墙钟(源码树·包内) / 最大停留(源码树·包内) / 代码读数数` =
> 字牌 OCR `245.9·236.6 / 41.6·41.4 / 12`；切镜拆分 `33.8·31.7 / 33.8·31.7 / 2`；
> patch 精排 `470.9·423.1 / 37.3·28.3 / 24`；ISC 第二意见 `419.7·408.9 / 33.9·33.8 / 19`。
> ⇒ **37.3s 属 patch 腿**，ISC 腿最大 = 33.9s；全程最坏单格仍是字牌腿 41.6/41.4s，
> 「改善 8.7x、按最大值口径超旧阈值 1.4~1.6s」的结论不受影响。不加宽字牌腿显示宽度（挤占 patch/ISC）。
> **④ 两个常设复核脚本同批改口径**：`review_progress_chain.py` 判据换成 ①逐腿最大 ≤45 ②逐腿均值 ≤30
> ③全程 ≤60 ④读数单调 ⑤与登记值对照（只报数）⑥**埋点自证**（档内腿行数=12 + 逐腿 elapsed 与事件流
> 墙钟对账，差 ≤max(8s,12%)；0 行判 **N/A** 不判通过）——归因函数已用已录
> `work/progress_chain_review/test2.events.json` 回放校验，与上表逐腿一致。
> `review_packaged_support_log.py` 新增 **C2 腿行面**（行数/顺序/刻度单调/腿耗时合计 ≤ 会话 elapsed）
> + D 面写明降噪已上线（现役 r16 与更早档里的 10054 = 历史，非回归）；对真实档跑通 FAILED=0。
> **⑤ 附带更正**：`locate()` 里 ISC 那条「默认关」注释已过期——`config.py:350
> isc_refine_enabled = True`（随「ISC L2 画面索引宽扫」在提交 7c6e485 一起翻的默认）⇒ 就地改注释，
> 未动行为。

<!-- 以下 = STATE.md Current Task 退休块「续63 补十」，2026-10-11 逐字迁入 -->

> **▶ 2026-10-08（续63 补十）— r17 出包：补九 三件进包 + 包侧两条新锁（腿埋点已实测进档）【下个对话从这里读起】**
> 口令「先出包吧」。构建 = `mvp/ui/scripts/build-release.ps1` 一条链（vite → compile:electron →
> PyInstaller → electron-builder dir），`PS_EXIT=0`；zip = `Compress-Archive win-unpacked\*` Optimal
> （与 r15/r16 同形态：根=散装内容）。**r17 = 未提交工作树构建**（本批三件都没提交，git 时机由用户掌握）
> ⇒ 「包 == 源码树」只对得上工作树，不对得上任何一次 commit，登记在此以防日后误判。
> **代次性质（构建后补记）**：构建当时本批未提交 ⇒ 出包记录先按「工作树构建」登记；随后同一内容
> 已提交为 `ba5bedd`，且构建后**未再改 `mvp/src`**（只改了 `.agent` 档案与 `accept_packaged_bundle.py`
> 这条判据自身的 bug）⇒ 包内 backend.exe 与该 commit 的产品源码逐字对应。
> 包 = `mvp/ui/release/Video-Locator-win-x64-20261008r17.zip` = **981,665,352B / 7,078 条目 /
> `testzip()=None`**；**zip 内** `resources/backend/backend.exe` = 77,472,765B
> `sha16=7e3fe311bdf62b36`，与磁盘构建产物逐字节一致（r16 = 77,469,132 / `7c9533750776a79a`
> ⇒ 尺寸 +3,633B，正是埋点+降噪那点代码量；r15 = 77,467,467 / `d45656f585826f4a` 未变）。
> 身份核验用新写的 `work/r17_pkg/zip_identity.py`（从 zip 里读，不读磁盘；同时把 r15/r16 三份一起列）。
> **包内验收全绿**：bundle **FAILED=0**（冒烟 30.2s ≤75s · DirectML · patch/ISC 未回退 CPU ·
> 隔离子进程 started+booted · 无 DIED without envelope）· render **FAILED=0** ·
> 三防 **FAILED=0**（含 release 无令牌拒启）· `check_export_plan_invariants.py` **FAILED=0**
> （4 片 × 4 通道五条不变式）· 启动冒烟 Electron 4+backend 1 存活 30s、用完即清 `AFTER_KILL=0` ·
> 包体产物探针 **FAILED=0**（靶子仍由 `work/r17_pkg/expect_from_source.py` 在源码树现算：
> 卷轴 63 条 / 56 文件 / 791.75s / 531.0s、EDL 134.12s、贴接 0 对、包内墙钟 99.7s ≤140s）。
> **本批新增两条包侧锁（`accept_packaged_bundle.py`，r17 起常设）**：
> ① 「腿边界埋点进包并落支持档」= 读 `work/pkg_attr/logs/video_locator.log` **最后一次 locate 的窗口**
> （该档追加式，全文计数会假绿），断言 `locate leg=` 顺序 == `EXPECT_LEGS` 12 条 · 刻度只增不减 ·
> 链首 `locate refine start legs=…` 在位。包内实测原文（合成素材 a1.mp4，1 段）：
> `text_anchor 0.4s units=9->42/48` · `shot_split 2.0s` · `patch_refine 10.1s` · `isc_refine 7.5s`
> · `chain=20.0s` ⇒ 售后从此能按档回答「进度停在哪条腿」。
> ② `EXPECT_LEGS` 与单测 `LocateLegLoggingTest.LEGS` 同源，两处必须同改（注释已写）。
> **首跑一条假红（我自己的 bug，不是包的）**：`legs == EXPECT_LEGS` 是 list 比 tuple ⇒ 恒 False，
> 而明细里 12 个名字逐字正确 ⇒ 改成 `list(EXPECT_LEGS)` 后重跑 FAILED=0。教训同
> 「验收脚本首跑要预期红」：红要先判是包的问题还是判据的问题，别改包也别放宽阈值。
> 分发包现状 = **r17 现役 + r16 回滚 + r15**（r15 是否按保留规矩删除，等口令）。
> macOS workflow 仍是 dispatch-only，按既有搁置裁决**未**手动触发。
