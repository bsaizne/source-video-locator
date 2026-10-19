# STATE 迁移存档（2026-10-18 续63 补二十立档同批）

> `Current Task` 退休块**逐字**迁移。本批迁出：续63 补十七（B 方案导出异步化）。
> 现役块见 `.agent/STATE.md`。

> **▶ 2026-10-13（续63 补十七）— B 方案导出异步化：/api/tasks/export 带进度与可取消，UI 切任务通道【现读这条】**
> 口令「开始 B 方案导出异步化」。动手前先核四条承重前提（每条带可证伪检查）：
> **P1** 后端 hook 早已在位 = `locator_service.py:1590-1593`（`export_results`）与
> `:1610-1616`（`export_project`）本就收 `on_progress`+`cancel_token`，剪映腿 `:1731` 逐 clip 取消、
> `:1742` 逐 clip「准备素材 i/N」⇒ **`mvp/src` 零改动**（改的是任务层接线，不是算法）。
> **P2** `_STAGE_RANGES[EXPORT]=(EXPORTING,98,1.5)`（`worker.py:45`）是给 **analyze 收尾**用的，
> 导出任务复用 ⇒ 一提交就显示 98%、随后长时间不动（比现状更糟）⇒ 必须按 `task.kind` 分派。
> **P3** 隔离 payload 是白名单逐字段搬运 ⇒ 漏字段要当场可见。
> **P4** 同步 `POST /api/export` 不删（向后兼容 + 包侧既有 `jianying_http==200` 锁依赖它）。
> **改动面**：`api/tasks/models.py`（`TaskKind.EXPORT` + `export_params`/`export_batch`）·
> `manager.py`（`submit_export`，**批在提交时锁定**，`isolated` 与 analyze/render 同源传）·
> `worker.py`（`execute_task` EXPORT 分支；`run_render_worker`→`run_batch_task_worker` 两 kind 共用，
> 免得抄第二份终态处理必然漂移；`map_progress_stage(ev, kind)` 不传 kind 时老口径逐字不变）·
> `isolated.py`（payload 往返 + `_adopt_parent_batch` 不把 export 信封误当结果批还原）·
> `schemas.py`+`routes/tasks.py`（`POST /api/tasks/export`）· UI 六件（`ServiceAPI`/Http/Mock/
> `types.ts`/`index.ts` + 新 `useExportTask` + `ResultsPage.doExport` 切通道：进度行 + 取消按钮）。
> 两条通道的请求体**收成一个构造点**（`exportRequestBody()`）——同型下限/参数两处各写一份必漂移。
> **`warnings` 必须在产出它的进程里取**：隔离子进程的 service 与父进程是两个实例，
> 父进程读自己那份永远空 ⇒ 告警随信封（`task.result.warnings`）回传，否则包内看不到 LOC-2001/2002。
> **顺带接了一条既有未接能力（本批新发现的缺陷，不是本批引入）**：`ProgressDebouncer.flush()`
> 有实现、有单测，但**没有任何 worker 调用** ⇒ 任务收尾那一帧（导出「已导出 xxx」/渲染最后一段）
> 被防抖扣住后永不露出。已在 `run_worker` 与 `run_batch_task_worker` 两处 `mark_completed` 前补 flush。
> **门禁（数字逐字跑出来，`npm run ... > log; echo rc=$?`，不用 `| tail`——管道会把 rc 洗成假 0，
> 我这次就差点读到「APP_RC=0」而实际是 2）**：后端 **Ran 670 tests OK (skipped=2)**（改前改后各一轮，
> 同数）· API **Ran 150 OK**（130→150 = 新 `mvp/api/tests/test_export_task.py` 20 项：提交锁批 /
> JSON 通道参数集 / 无批 failed / LOC 话术 / 意外异常不逃逸 / 取消 / **首帧 <98 且单调且末帧 99** /
> analyze 老口径回归锁 / isolated 两条行为锁 / payload 往返 / 信封不回登记 / 路由 400 与回退 /
> 同步路由仍在）· UI vitest **161 passed**（150→161 = `exportTask.test.ts` 11 项，含**同源锁**：
> 任务通道与同步通道 body 逐字节相同）· 双 typecheck `rc=0`（app 与 desktop 各一次实测）。
> **端到端跑的是编译产物，不是桩**：`work/probe_export_task_e2e.cjs` =
> `out/electron/backend/bridge.js` → 真 uvicorn（`run_backend.py`，随机端口+会话令牌+release 通道）
> → `/api/results/load`（69 条真基线批）→ `POST /api/tasks/export` → 轮询 →
> **`PROBE PASS`**：`completed progress=100` · `waited_ms=4743` · 产物落盘且非空 ·
> 支持档两行 `isolated child started/booted pid=20828` = **`export_batch` 过了真跨进程 pickle**
> （假 service 的单测锁不到这条腿）。
> **包侧四条新硬断言打在现役 r23 包上首跑 = `FAILED=4`（`PASS=28`，预期红 = 锁真咬）**：
> ① 渲染层产物锁（`dist/assets/*.js` 里必须有 `/api/tasks/export` 串，13 个资产 0 命中）——判据打在**分发包
> 产物**上而不是源码树（教训 ⑧）；② 后端通道 `http=405`（r23 没这条路由，被 `/api/tasks/{id}` 的
> GET 规则吃掉）；③④ 任务 completed 与草稿 segment。其余 **28 项照绿**（DirectML wall=27.1s ·
> 剪映通道 http=200 · 隔离 `reaped exitcode=0` · 12 行腿埋点）。进度单调那条写成
> 「采到 ≥2 帧才判」，syn 导出快于轮询间隔 ⇒ **判 N/A 不判通过**（阈值别超测量精度）。
> ⚠️ **两处我自己的操作失误（如实留痕）**：① 首跑包内探针用了脚本默认 case=`test2`
> （23 分钟真素材，而 accept 读的是 `headless_syn.summary.json`）⇒ 停掉、确认无残留 `backend.exe`
> 后用 `syn` 重跑；② 新加的 info 行 `print(... ⇒ ...)` 在 GBK 控制台 `UnicodeEncodeError`，
> 把 accept 打崩在汇总行之前（教训 ⑮ 同族再犯）⇒ 除改掉我那两处，还顺手把既有两条同型 latent
> （`export_http`/`jianying_http` 缺字段分支的 info 行）一起改成 GBK 安全串——**那两条正是
> 拿旧包跑验收时最会走到的分支**。
> **覆盖边界（有意取舍，不是漏判）**：① **没有 >300s 的真长导出实测**（本机 syn 是秒级）⇒
> 「分钟级导出有进度、可取消、不被误报成连不上」= 单元 + 端到端 + 代码路径三级证据，
> **不是**真机长导出读数；真机读数要等他那边长素材再采。② UI 的 `exportResults`（同步）方法
> 保留但**页面已无调用方**；后端同步路由仍受支持并被包侧锁覆盖。③ **未提交、未出包** ⇒
> 收益还不在用户手上：要 **r24** 才进分发包，且这是跨平台 JS/TS 改动 ⇒ **mac 要另走一发 dispatch**，
> 否则默默留「Win 已改、mac 仍旧」的裂口。
> **真素材长导出实测（口令「先1再3再2」的第 1 条）**：lab 根 test2 批（54 条主 span，取材宽 132.2s）
> 走 `/api/tasks/export` 剪映通道跑到底 = **`wall=66.7s` · 84 帧 · 83 个不同进度值 · 81 条「准备素材 i/86」
> 逐 clip 帧 · 中位 0.84s/格 · 最大间隔 2.03s · 首帧 0.0（R1 在真跑里确认绕开）· 末帧 100 ·
> 收尾「已导出」帧 = True（flush 接线真链路生效）· 产物 82 clips/110.1MB/segments=86 ·
> `warnings=4` 随信封跨进程带回 · `isolated child booted` = 54 条批过了真跨进程 pickle**。
> 取消腿（第 4 格取消）：`cancel 请求 → 子进程 terminated = 0.36s`，驱动读到 `cancelled` 共 ≈1.0s；
> 残留 = 5 clips / 11.1MB 且 **`draft_content.json` 没写**（半成品不冒充可用草稿）；后端零未处理异常。
> **成本归因更正（我上一轮的口述错误，未进过档案，此处立准）**：曾据「374s ÷ 64 段」说真机单 clip
> 慢本机 7.4 倍 —— **分母用错**（64 段是成片渲染的段数，导出批是 `clips=681`）。按正确分母：
> 真机 571s/681=**0.84s**、474s/681=**0.70s** vs 本机 66.7s/86=**0.78s** ⇒ **两台机器逐 clip 成本一致，
> 没有性能异常**；墙钟差全部来自 **clip 条数**（真机 `material expand widened=620`，本机 7），
> 即补十五 已量过的「代价主体=取材扩宽」再确认。⇒ 要压那 6~13 分钟，杠杆在 `material_width`
> （scene 撑到完整镜头 vs core 仅核心窗），不在异步化、不在编码器；本条**无新缺陷要修**。
> **取消残留的裁决（第 3 条）= 不自动删，改为可见 + 复用提示**：按 ~1.3MB/clip 外推，真机那批取消
> 会留 ≈0.9GB —— 而那是下次重跑能直接复用的转码缓存（`clip_path.exists()` 跳过重抽是既有行为），
> 删掉的代价是下次多花几分钟重转。⇒ UI 取消后如实显示「已转好的素材留在 `<输出目录>`，重新导出同一批
> 会直接复用、不会重转」（`useExportTask` 新增 `cancelled`/`outDir` 两位 + 页面提示；vitest 162）。
> 探针（不入库）：`work/long_export_probe/{runA_full.log,runA_driver.log,runB_driver.log,runA_backend.log}`；
> ⚠️ 脚本日志名判断写错（`cancel_at=4` 不等于 `cancel_at`）⇒ **B 腿覆盖了 `runA_full.log`**，
> A 腿完整帧序列在 `runA_driver.log`（引数取自那里）；产物 `draftA`(110MB 真草稿) + `draftB`(11MB 残留样本) 暂留。
> 方案文档 `mvp/docs/PLAN_EXPORT_ASYNC_20261013.md`（含 R1~R5 风险与失败分支）。
> 产物：`mvp/api/tasks/{models,manager,worker,isolated}.py` · `mvp/api/{schemas,routes/tasks}.py` ·
> `mvp/api/tests/test_export_task.py`(新 20 项) · `mvp/ui/src/services/{ServiceAPI,HttpServiceAdapter,MockServiceAdapter,types,index}.ts` ·
> `mvp/ui/src/composables/useExportTask.ts`(新) · `mvp/ui/src/pages/ResultsPage.vue` ·
> `mvp/ui/src/services/__tests__/exportTask.test.ts`(新 11 项) ·
> `mvp/scripts/{attr_packaged_headless,accept_packaged_bundle}.py`；探针/日志在 `work/`（不入库）：
> `probe_export_task_e2e.cjs` · `pkg_attr_probe_r23_syn.log` · `accept_bundle_r23_exporttask.log` ·
> `backend_suite_r24_{b1,b2}.log`。
> **r24 已出（2026-10-14 00:0x，第 2 条）**：三笔已提交并推（`de930dc` 代码 / `dc15f86` 规则 /
> `811932e` 档案），构建时**工作树干净** ⇒ **r24 = 干净 commit `811932e` 构建**。
> `build-release.ps1` 四步走完（`work/build_r24.log`：[1/4] vite → [2/4] electron 主进程 →
> [3/4] PyInstaller `Build complete!` → [4/4] electron-builder，末尾出包成功行）。
> **包内四道全绿**：bundle **33 PASS / FAILED=0** —— 上一批在 r23 上预期红的 **4 条新锁全部转绿**
> （渲染层产物锁命中 `index--VHmdytl.js`、通道 `http=200`、任务 `completed`、草稿 ≥1 segment），
> 且「进度单调」这条这轮采到 ≥2 帧 ⇒ 由 N/A 变成真判 · render **FAILED=0**（R1 completed wall=60s）·
> 导出计划不变式 **FAILED=0**（4 片 × 4 通道）· 启动冒烟 **FAILED=0**（30s Electron 4 + backend 1，
> `AFTER_KILL=0`）。zip `Video-Locator-win-x64-20261013r24.zip` = **981,692,188B / 7,078 条目 /
> testzip=None / flat**（对 r23 +4,979B）；`zip 内 backend.exe 77,496,832B sha16=cf9c6ce003a47c66`
> **matches_disk_build=True**；`zip 内 bridge.js 8,882B sha16=7d3e0427e3d3a4db == 磁盘`。
> ⚠️ **一条我自己写错的核验当场订正**：先按「backend.exe 明文里搜路由串」判，得 `False` —— 那是
> **无效判据**（PyInstaller 把 .py 存成压缩 PYZ，明文搜不到是必然）。有效判据 = 行为（探针打的正是
> win-unpacked 里那个 backend.exe，回 `http=200 status=completed`）+ `matches_disk_build` +
> 渲染层 bundle 扫串。补做**代次区分核**：r24 的 13 个 dist/assets js 命中 1 个，
> **r23 同样 13 个命中 0 个** ⇒ 那条锁能区分代次，不是恒绿。
> **mac 已由他自己 dispatch（2026-10-14 口令「mac我跑工作流了」）**：我这边 `git credential fill`
> 两次非交互返回空（令牌需重登）⇒ 按纪律**不触发登录弹窗、不重试第三次**，交给他点。
> 读公开 API 实测：run **38429952068**（`workflow_dispatch`，**head=`c789670`** = 最新 master，
> 构建面含本批全部改动）状态 `in_progress`。**换包基线已取**（供事后核「包真的换了」，
> 不是只看 run 绿）：`mac-alpha` 的 `Video-Locator-mac-arm64.zip` =
> **916,828,395B @ updated_at 2026-10-12T16:56:33Z**（上一发 run 38277827813 的产物）
> ⇒ 本轮门槛绿则同名 `--clobber` 覆盖，**字节数与时间戳应双双变化**。
> **⑧ mac 换包核验已闭合（2026-10-16，公开 API 只读实测，未取令牌）**：run **38429952068** =
> `completed / success`，head_sha `c7896705b`（= 档案笔 `c789670`）；`mac-alpha` 的
> `Video-Locator-mac-arm64.zip` 现为 **916,840,558B @ 2026-10-13T17:01:02Z** ⇒ 对基线
> **+12,163B 且时间戳变化**（两项都变 = 真换了包，不是只看 run 绿）。构建面同一性另核：
> `git diff --name-only 811932e..c789670` = **仅 `.agent/{CHANGELOG,STATE,TODO}.md` 三份档案**
> ⇒ mac 那发的代码面与 **r24 构建点 `811932e` 逐字等同**（含导出任务通道代码笔 `de930dc`，
> `git merge-base --is-ancestor de930dc c789670` 通过）。⇒ 本块「状态 `in_progress`」与
> Current Problem 里「mac-alpha 仍是 r23 那一代」**均过期，已按实测订正**。
> 读数原文留 `work/mac_check/{rel,run}.json`（不入库）。

---

> 本文件累计存放 2026-10-18 立档批次从 `Current Task` 逐字迁出的退休块（补十七 = 补二十 立档同批；补十八 = 补廿一 立档同批）。

> **▶ 2026-10-17（续63 补十八）— 上一会话三批未提交改动收口：音轨布局回退 + 竞品黑盒对照 + 取材扩宽护栏 1.5【现读这条】**
> 口令「开始」。接手时工作树 = 上一会话留下的 **三批改动、全部未提交未出包**（交接件
> `.agent/archive/HANDOFF_20261017_rea_competitor_blackbox.md`，自包含）。先验 mtime 无孤儿写入者
> （源码停在 10-16 23:2x / 10-17 02:31），再**自己重跑门禁逐条取 rc**，不引用上一会话的数字。
> **① 音轨回退（代码笔 `2afcec7`）**：源声轨为「N 声道 + **未指定布局**」时 ffmpeg 原生 aac 拒收
> （`Unsupported channel layout "6 channels"` rc=-22、产物 0 字节）⇒ 抽素材/预览整腿当场失败。
> **触发面不是人造源**：`5.1(side)`/hexagonal 编进 MP4 后布局信息就丢 ⇒ **本产品自抽的 `og*.mp4`
> 天然是这种源**（把它当原片再抽一次即复现）。次生陷阱：失败留 0 字节文件 + 剪映腿裸 `exists()`
> ⇒ 第二次导出**不再报错**却静默把坏素材写进草稿。修 = 首跑参数**逐字不变**、仅失败后按
> 48k/stereo 重试一次；失败清半成品；可用性判据收成唯一来源 `app.exporters.clip_present`
> （剪映腿 + 草稿写入端共用，教训 ⑲）。改前 A 臂 `MediaError`(rc=4294967274)/C 臂 rc=-22 0 字节，
> 改后 A 臂 OK 447,853B 且 **C 臂仍 rc=-22（判据真咬）**；新锁 4 项。
> **同族调用点本轮已枚举完（不是"修一处宣称其余安全"）**：另两处「存在即复用」形态**本身带有效性判据、
> 无潜伏 0 字节复用** —— `timeline_render.py:594` 要 `st_size>0`、`source_merge.py::_valid_output`
> 走 probe+视频流+时长吻合。**同族未改（登记，需单独立批）**：`source_merge.py::_transcode_args`
> 也是 `concat → -c:a aac` 无布局归一（同形源失败更早：`Cannot select channel layout for the link
> between filters auto_aresample_0 and Parsed_concat_6`）；但那是**硬失败非静默坏产物**，修法 = concat
> 前插 `aformat=channel_layouts=stereo`。
> **② 竞品（CutMatch）黑盒对照 —— 首次用同一把目检尺子量出「竞品 vs 我方」**（尺子 =
> `mvp/scripts/shot_detect/boundary_gt_v1.json` 44 窗/125 条 conf=high；竞品数据 =
> `D:\claudework\cutmatch-analysis\sandbox\out\` 只读）。切点质量（共同覆盖 2mkv+test1，±1.0s）：
> **竞品 t0.50 = P/R/F1 0.885/0.958/0.920（test1 F1 1.000）** vs **我方 scn2 = 0.550/0.917/0.687
> （test1 F1 0.200）**。后处理规则**已可逐帧复现**（其 probs + 自记参数重放：2mkv 1874/1874、
> test1-om 491/491 全等）⇒ **`sensitivity=18` 对切点集合无可观测作用**（判据 = 不含它的规则即可复现）。
> **导出层双臂**（只把竞品切点接进导出计划层）：A 我方 scn2 导出实得 **131/139**、严格 135 ·
> B 竞品 TN 切点 **130/139**、严格 135 ⇒ **换更准的切点在导出实得上不涨（−1，噪声级）**，与档案旧结论
> 同向（`FINDINGS_TN_CUT_QUALITY_VS_METRIC.md`）。**结论：竞品优势在信号源（TN 逐帧概率），不在后处理
> 三条（阈值/组中点/min_gap）。** 附带量级事实：其 sidecar `.text` = 373MB（整包 87%），常量是
> RVA 表而**无任何 RIP 相对引用**（8 modrm×5 opcode×8 REX 全扫 = 0）⇒ 字符串 xref→函数体这条路不存在。
> **③ 取材扩宽护栏 `material_expand_rel_cap` 2.5 → 1.5（代码笔 `beedb91`，产品口径用户拍板）**：
> 四片导出层扫描（`work/expand_sweep.py`，**同口径自证** 严格 135/139、导出实得 131/139 逐位吻合）
> cap 2.5/2.0/**1.5**/1.2/core 不扩宽 ⇒ Σ素材宽 499.1/452.1/**421.7**/419.9/419.9s，
> 而**导出实得与严格四档全不变** ⇒ 2.5 以上的扩宽在该口径下是纯代价（多转码 + 多无关画面）。
> ⚠️ **口径必须读准**：cap 1.5 在这批数据上 **≈ 关闭扩宽**（不是"温和收紧 −15%"）—— 导出计划不变式里
> 扩宽条数四片 = **0/0/0/1**（cap 2.5 时 11/7/9/12，本会话重跑独立印证），Σ 421.7s ≈ core 419.9s。
> 语义 = **卷轴只给解说实际引用的核心窗，不再撑成完整原片镜头**；2026-10-11 的 K=2.5 是当时拍的口径。
> 若要"保留部分整镜头扩宽"的温和档 = **2.0**（−9.4%），一条数值 + 一条锁 + 重跑门禁即可切。
> **门禁（本会话逐字跑，`work/verify_20261017/`，rc 逐条取不用 `| tail`）**：后端全套
> **`Ran 675 tests in 199.786s` OK (skipped=2) / BACKEND_RC=0**（DirectML 生效
> `BACKEND_DEVICE directml amd`）· API **`Ran 150 tests` OK / API_RC=0** · 导出计划不变式
> **FAILED=0（4 片 × 4 通道）/ INV_RC=0**。**代码已提交（两笔）但本批未重跑 UI**（无前端改动面）。
> **静态逆向线两次判死、已收线（别再重开）**：① REA 的 Windows Ghidra P0 **只收原生 PE**
> （原文 `accepts native PE and explicitly selected raw 6502 targets only`）⇒ 373MB 切片喂 Ghidra 被
> 平台策略封死，rizin 能反汇编切片但 `axt` 只覆盖已分析范围（8MB=2%）；② 全量 PE 分析
> 默认 `GHIDRA_HEADLESS_MAXMEM=2G` → 1h50m 后 `OutOfMemoryError: Java heap space`，抬到 10G 重跑
> 30 分钟无产出（日志冻结/RSS 3.9GB）主动掐掉；③ 剩下唯一静态未知 = `commentary_boundary_refine_*`
> 的"存在性"角色，而其**位置**角色 2026-09-26 已实测（施加在我方 227 条边界上 97.4% 位移 ≤4 帧）。
> **环境（本轮新装，全在 D 盘）**：`D:\claudework\rea`（master，`npm ci`+`compile`）、`D:\npm-global`
> （npm 前缀从 `%APPDATA%\npm` 迁来，`rea.cmd` 6.5.0）、`D:\tools\ghidra\ghidra_12.1.4_PUBLIC`
> （sha256 = 官方 `ddac49f9…`）、`D:\tools\rizin` 0.9.1、`D:\tools\kuna`（REA 在 Windows 拒
> `unsupported_host`）；User 级环境变量 `GHIDRA_INSTALL_DIR`/`REA_KUNA_COMMAND`，JDK 23 = `D:\java`；
> REA+Ghidra `doctor` **10/10 全绿**（源码构建需从 npm 包拷 `native/windows/build/{manifest.json,
> rea-windows-x64.node}` 回位才绿）。网络事实复确认：`github.com:443` 阻断、`api.github.com` 通。
> **覆盖边界（有意取舍，不是漏判）**：① **观感面未测** —— cap 1.5 的成片接缝/硬切位置**没有读图验收**，
> 本批只有只读数据面；② 黑盒对照只覆盖**共同可测的 2mkv+test1**（竞品未交付 test2/test3 的 probs）；
> ③ **未出包** ⇒ 用户手上仍是 r24；本轮 `mvp/ui` 零改动 ⇒ **mac 不必另走 dispatch**（跨平台 JS/TS 未动）；
> ④ 竞品侧一律**只读交付物**，未运行竞品。
> **主线「导出过渡不流畅」仍未结**（`.agent/archive/HANDOFF_20261016_export_smoothness.md`）：缺三样
> 外部输入 = 他指认的**具体秒数** / 未经微信转码的原始 `movie_*.mp4` / `<解说片名>__<hash8>.results.json`
> （`%APPDATA%\Video Locator AI\data\exports\` 只有 2026-08-27 三份旧 results，不含本案 ⇒「主 span 本身就宽」
> 与「snap 撑宽」占比拆不开）；机械层六项已排除、armB 帧级切点判负、armC 段宽上限有效且不撞 align 护栏；
> 另一条挂账 = `og720-720` 相似度自相矛盾（0.08 vs 0.97，两数打架未查谁错）。
> **产物**：代码 `mvp/src/{media/ffmpeg/ffmpeg_io.py, app/exporters.py, app/locator_service.py,
> infrastructure/config.py}` + `mvp/tests/{test_ffmpeg_io.py, test_exporters.py,
> test_locator_service.py}`；档案 `.agent/{STATE,TODO,CHANGELOG}.md` +
> `.agent/archive/{HANDOFF_20261016_export_smoothness.md, HANDOFF_20261017_rea_competitor_blackbox.md}`
> （本批首次入库）+ 旧块迁 `archive/{STATE_history_20261017.md, TODO_history_20261017.md}`；
> 探针与日志（不入库）`work/{verify_20261017/, audio_51_20261017/, cap15_*.log, expand_sweep.py,
> export_arm_bb.py, export_arm_gt.py, trans_smooth_20261016/}` 及
> `D:\claudework\cutmatch-analysis\sandbox\{compare_bb_vs_ours,bb_final,rule_search,diag_timebase}.py`。

---

> **▶ 2026-10-17（续63 补十九）— 竞品三刀（只写文档）+ r25 出包【现读这条】**
> 口令：「先不用（上午那三批的下一批），先拿 rea 完整逆向竞品」→「按你的计划来」→「继续下一刀」→
> 「跑一下竞品项目的采集脚本」→「修复采集器缺陷并重新运行自检」→「推远端 / 出 r25」。
> **动手前追问了四轮**（用户点名要求「挖之前先反复追问问清楚」），定下的口径全部落档：
> 目标 = 语义规格+参数清单+定点通道+模型层；手段 = 运行+动态插桩；载体 = 本机直启行政解包树（不安装）；
> **使用边界 = 结论只写文档，一行不进产品代码**；优先链 = 模型特征→主链参数→解说边界→导出 schema。
> **一、竞品侧（正文一律在 `D:\claudework\cutmatch-analysis`，本仓 `Next Actions` 第 4 条只留指针）**
> 四条承重前提被实测打掉，于是没按原选项执行：①「只拉模块」不成立（全树 0 个 app `.py`、无 app 级
> `.pyd`；`*_mypyc.pyd` 是 charset_normalizer 的 ⇒ 旧「sidecar=mypyc」归因要改）；
> ② 常量块内 **C(code object) 记录 = 0** ⇒ 函数行号/posonly/kwonly 静态永不可得（旧 `codes` 出 0 行的真因）；
> ③ 其 IPC **不是命名管道 JSON-RPC，是本地 Flask HTTP/WS**（`cutmatch.web.*` + `flask` 串 504 次 +
> 真实路由字面串）；④「只支持 NVIDIA」**在代码层不成立**（docstring 明写 CUDA/**MPS**/CPU 三档 +
> `device_keys/macos.py`）⇒ 战略差异重述为「其 Windows 包押 CUDA vs 我方 DirectML」。
> **产出**：`FINDINGS/13`（137 模块 / 11,213 名字 / 1,891 参数名表 / **3,202 条他们自写中文 docstring**）、
> `FINDINGS/14`（22 个 `/api/*` + **16 键阶段词表**（快 8 / 精 11 子集，强推断）+ batch 状态 12 键 +
> 授权 18 码 + 导出格式四元组 + `source/commentary/output` 三角色）、`FINDINGS/15`（话术 341 条 +
> model lease 357 条）。三处对我方决策直接有用：**他们原片侧 1fps 索引且不切镜头**（独立印证 cap 1.5
> ≈ 关闭扩宽是同侧口径）／**时长守恒靠变速补齐（90–110%）而非 0.1s 下限撑宽**（我方第十/十二轮
> 越界那一族在其结构里不存在）／**渲染失败仍交付 XML**（档案挂着未决的口径当场闭合）。
> **动态腿判死（确证，不再追）**：`licensing.client.legacy` 原文「**每次启动都向授权服务器校验**」+
> D4「`content_key` 由服务器下发」+ `protected_assets`「租约配置只在进程间内存传递、加载完即清理」
> ⇒ 用户要的「本机直启 + 先断网」下推理与解密链不可达；且静态三条永久边界（函数体控制流 /
> HTTP 方法与请求体 / 权重明文）已写死。**本轮未执行竞品任何代码、未改其任何文件。**
> **二、采集器（`runtime_evidence` 那条链）修了 7 处**：README 被当证据（造假符号 `host/name/port`）／
> **我自己上轮修法引入的回归**（白名单收窄到 `.log/.txt` ⇒ `01_exports` 的 `draft_content.json`/CSV/XML
> 被一起跳过）／CSV-TSV 整族无行判据／XML 属性名抢匹配吞掉内层键值（真 FCPXML 上必然复发）／
> UTF-16 日志按 utf-8 硬解 = 静默零命中（教训 ⑮ 同族）／防自喂只有文件名规则 + **我的排除件在报表里
> 凭空消失**（自造静默丢弃）／压缩包混进「扩展名不符」静默丢。
> 新增硬断言自检 `scripts/selftest_parse_runtime_log.py` = **17/17 PASS**。夹具首版我手写了两个
> **不在符号表里的键** ⇒ 表现为假失败，已改成从 `load_symbols() ∩ WANTED` 动态取键、每通道唯一键。
> **前提核查**：`runtime_evidence/` 从未投放证据、竞品日志路径在本机全部不存在 ⇒
> `data/runtime_params_observed.json` 现 = **{}（本机没有任何竞品观测）**；自检只证「链路可用」。
> **三、r25 已出（构建点 = 干净 commit `c3a17e5`，已推 `cf71641..c3a17e5` 4 笔）**
> 推之前远端多出一笔**用户自己在 GitHub 网页的改动**（10-16 11:41 删 README 一行）⇒ 不覆盖，
> 把本地 4 笔 **rebase** 到它之上（我的提交不碰 README，无冲突面）。`mvp/ui` 本轮零改动
> ⇒ **mac 不需另走 dispatch**。四道包内验收对 `win-unpacked` 取，**逐条 rc=0**：
> bundle **33 PASS / FAILED=0**（含上一批 4 条导出通道锁仍真绿：渲染层产物锁命中 `index--VHmdytl.js`、
> 后端通道 `http=200`；12 行 `locate leg=` 齐）· render **FAILED=0**（R1/R3 子进程未误判硬崩）·
> 导出计划不变式 **FAILED=0**（4 片 × 4 通道，扩宽条数 0/0/0/1 = cap 1.5 语义再确认）·
> 启动冒烟 **FAILED=0**（Electron 4 + backend 1 / 30s 存活 / `AFTER_KILL=0`）。
> **zip 身份** = `Video-Locator-win-x64-20261017r25.zip` **981,693,605B**（对 r24 **+1,417B**）/
> 条目 **7,079**（文件 6,993 + 空目录 86；r24 是 85，差的那 1 个 = 本代 `resources/` 确实无直属文件）/
> `testzip=None` / `zip 内 backend.exe 77,498,025B sha16 ae04274989342708 == 磁盘` /
> `zip 内 bridge.js 8,882B sha16 7d3e0427e3d3a4db == 磁盘` /
> **与 r24 的文件名集合差集 = 0/0（逐名等同）**。
> ⚠️ **两处我自己的错，立准在此**：① 打包脚本的目录条目规则我先按「每个目录都写」造出 1,374 条
> ⇒ 与历代 7,078 不可比，实测出 r24 规则 = 只给无直属文件的目录写显式条目后重打；
> ② 更严重的一次是清死代码时删掉 `pre = ` 却留 `if pre:` ⇒ 脚本在**写包前** NameError，
> **而我下一条消息里已经报了「7,079 条目 / 981,703,678B」这组没有读数支撑的数** ⇒ 已当场更正、
> 核磁盘确认 `ABSENT` 才重跑。判据教训：包体身份核验原先只比嵌套件（backend.exe/bridge.js），
> **缺「条目数 == 磁盘文件数」+「顶层关键件在位」+「与上一代文件名差集」三道 ⇒ 坏包能全绿出门**，
> 现已写进 `work/r25_pkg/make_zip_r25.py` 并在不过时就 `exit 1` 不写包。
> **覆盖边界（有意取舍）**：① **cap 1.5 的观感面仍未测**（成片接缝/硬切无读图，四档指标不变只是数据面）；
> ② 动态面只剩「HTTP 方法与请求体字段」拿不到，要他那边**已激活真机**按 5 类产物投放；
> ③ ~~删 r22~~ = **已删（2026-10-17 口令）**，用 `work/r25_pkg/precheck_delete_r22.py` 双验：
>    回滚档 r23/r24 均 `testzip=None` / 7,078 条目 / backend.exe 尺寸+sha16 与档案逐字一致；
>    r22 自身身份留痕 = 981,686,020B / 7,078 条目 / backend.exe 77,493,384B sha16 `f0d00f10c4123813`。
>    ⚠️ 这条闸第一版**只查 STATE.md** ⇒ r23 的 sha16 判「找不到」（它记在 `archive/checkpoint-2026-10-13-0040.md:127,662`，
>    STATE 里那段读数已随立档迁入 `STATE_history_20261017.md` 且只留 zip 级读数）⇒ **期望值没错，是判据搜索面写窄**；
>    现扩到整个 `.agent/`（实搜 173 份，`.agent/versions/` 下是目录、按文件读会 PermissionError，已跳过不可读者）。
> ④ `source_merge.py::_transcode_args` 声道布局同族缺陷**仍未改**（硬失败非静默，需单独立批）。
> **产物**：代码笔 `e79d4ee`（音轨回退 + `clip_present`）/ `36acc50`（cap 1.5）/ 档案笔 `4783594`·`c3a17e5`；
> 本仓 `work/{r25_pkg/make_zip_r25.py, r25_pkg/diag_zip_dir_rule.py, verify_20261017/,
> accept_{bundle,render}_r25.log, invariants_r25.log, startup_r25.log, build_r25.log}`；
> 竞品仓 `scripts/{mine_module_semantics,extract_http_contract,extract_messages_and_lease,
> selftest_parse_runtime_log,parse_runtime_log}.py` + `data/module_semantics_20261017.*` 等。

---

> **▶ 2026-10-18（续63 补二十）— cap 1.5 观感面读图收口（2mkv 单片）+ 「双档各出一张成片」验收设计判空【现读这条】**
> 口令：接上一会话，在三个开放项里点选 **cap 1.5 观感读图**。**零产品代码改动**（只读探针 + 逐张读图），
> `git diff HEAD -- mvp src` 为空 ⇒ 树与 r25 构建点 `c3a17e5` 相同。
> **一、动手前打掉两条前提（各是我自己的错）**
> ① 交接件写的验收法「包内 accept + 双档（2.5 vs 1.5）各出一片再读图」= **空实验**：`material_expand`
> 只允许 `channel="jianying"`（`exporters.py:433` 硬守卫 raise），成片通道调用 `prepare_channel_plan`
> 时**根本不传**这两个参数（`locator_service.py:992-998`）⇒ **cap 对成片/EDL/XML 惰性，两档成片逐字节相同**；
> 观感面唯一载体 = **剪映卷轴素材**。
> ② 我开工第一条消息报「四片原片在 UNC `\\ProjectXIXI`、`net use` 空 ⇒ 缺素材做不了」**是错的**：
> r25 包内 render 验收用的 `work/stable_sort_regress/2mkv.results.json` 记的是本地路径
> **`D:\video\2.mkv`（1,020,168,298B，在位）**。⇒ 教训：**路径要核到当前这批用的那份 results 文件**，
> 别拿另一批（`work/fastglobal_default_*`）里的 UNC 字段当事实。（test1/2/3 确实只有 UNC 记录、本机无副本 ⇒ 那三片仍不可渲染。）
> ⚠️ **同日补廿四订正：这条也是错的**——四片原片全在本地 D（`D:\ProjectXIXI\test*\*-om.*`），错因是我的 `sed 's/.*: *//'` 把盘符 `D:` 吃掉；四片扩测见 STATE 补廿四 块。
> **二、计划层读数（2mkv，索引 `2__4c6d4ab2` = scn2+evt1 @1fps，逐 clip 只读）**
> - **cap1.5 逐 clip == 关闭扩宽**（`cap15_identical_to_core_per_clip=true`），且
>   **1.5 档卷轴区间 == 成片通道区间**（`scroll_15_equals_movie_spans=true`，2.5 档 false）
>   ⇒ 现役包里**剪映素材相对成片零余量（零 handle）**。
> - 两档差异 = **12/72 条**（11 条 2.5 扩宽 + clip34 被去重叠连带裁短），2.5 档多出 **26.4s**
>   （Σ素材宽 161.2 vs 135.4s，`n_expanded` 11 vs 0）；本轮在本地路径上复现了 10-17 02:32 那轮的
>   161.2/135.4 ⇒ 两把尺子对同一件事，索引等价、跨臂可比。
> - 「至少一边不在索引切点上」的 clip：**1.5 档 47 / 2.5 档 37**，其中**两档都算镜头中间的 37 条
>   ⇒ cap 只归因 10 条**；1.5 档越界深度 中位 1.81s、最大 8.0s，>1.0s 的边界 47/144。
> **三、真剪点偏差（把「2.5 = 整镜头」削掉一半）**
> 13 个扩宽边界逐个在 ±1.0s 窗内**逐帧解码自算像素差**（v1 用 ffmpeg `metadata=print` 的读数不合法：
> 出现窗口外时间戳 + 跨窗复读 ⇒ 判废重做，`edge_offsets.py` 只留作判废证据）：
> **11/13 有显著真剪点，中位偏 0.209s、最大 0.917s，8/13 偏 >0.12s、3/13 偏 >0.30s**；
> 2 条边界附近根本没有剪点（clip46@1766.0 / clip54@2008.0）。按符号拆开：**5 条正向 ⇒ 2.5 素材把
> 邻镜头 ≤0.25s 带进卷轴（闪切）**；6 条负向 ⇒ 少带 0.2~0.9s 本镜头内容
> ⇒ 「换 2.0/2.5 买到的是**近似**镜头完整度 + 闪切风险，不是干净的整镜头」。
> **四、逐张读图（12 张接触表全读，每张 8 帧 @300px，标 S15/S25/E15/E25）**
> 1.5 档一致形态 = 入/出点落在**动作中途**：clip13 入点时士兵已举绳／clip35 丢掉 2.4s 举杯动作／
> clip46 直接从坐定阅读开始／clip54 入点时步枪已举起／clip61 丢掉 2s 走向三脚架／clip62·68·69 出点时
> 手势未完；clip70 尾那条 10s「镜头」实测含 **≥2 条真剪点**（scenes.npy 漏切并成一条）。
> 2.5 档读到的反面与第三节符号**同向对上**：clip38 素材头 0.3s 是上一条镜头（机头特写）、
> clip68/69 素材尾把下一镜头开头带进来、clip70 头带 0.35s 道具特写。
> **五、结论（分级）**
> - **硬证据**：cap 不进成片通道；1.5 档卷轴 = 成片区间（零 handle）；cap 归因的边界变化只有 10/72 条。
> - **方向性**：1.5 的观感代价 = 入/出点在动作中途 + 零余量；2.5 的代价 = 串镜头闪切 + 卷轴比解说引用长 19%。
>   **cap 既不是「过渡不流畅」的成因、也不是解药**（与 10-16 armC 反证「段宽不改像素静止占比」同向）。
> - **未知（覆盖边界，如实登记）**：① ~~单片（2mkv）结论，test1/2/3 原片不在本地~~ = **同日补廿四已订正并扩到四片**（原片全在 D；且 test3 有 1 条 1.5 档仍扩宽 ⇒ 口径改为 ≈）；② 读图对象是**原片帧**
>   （素材 = 该区间转码，构造等同），**未在剪映里真机回放**两档卷轴；③ 未测其它置信档/低策略下的形态。
> **产物**：`work/cap15_film_20261018/{plan_diff.py,plan_diff.json,changed12.json,frames.py,sheets/×12png,
> sheets_index.json,edge_offsets_v2.py,edge_offsets_v2.json}`（`work/` 不入库）。
> **现役未结项**：`source_merge::_transcode_args` 同族批 · 主线「过渡不流畅」三样外部输入 · `og720-720` 挂账 ·
> 下次出 r26 时删 r23。

---

> **▶ 2026-10-18（续63 补廿一）— source_merge 音频布局归一：全 unknown 硬失败 + 混合形态「顺序决定产物」两族一并修掉【现读这条】**
> 口令：「先处理 source_merge 声道布局批次」（补二十 之后三件候选里的第一件）。**本批改了产品代码，未出包**
> ⇒ 用户手上仍是 r25、**还没有这个修复**；纯后端 Python ⇒ **mac 包要另走 dispatch 才带上**。
> **一、归因（改前双臂，读数在 `work/merge_layout_20261018/`）**：档案原话只写了"失败更早、硬失败非静默"，
> 实测是**两族**，第二族比第一族更坏。
> ① **硬失败（确证）**：所有输入都是「6 声道 + 容器未写布局」⇒ 每条编码器尝试都在**滤镜图协商阶段**抛
>   `Cannot select channel layout for the link between filters auto_aresample_0 and Parsed_concat_{8,12,28}`
>   （n=2/3/7 全复现）⇒ `MediaError`；`tmp` 有清理 + `_valid_output` 有拦 ⇒ **不留坏缓存**（这条档案说对了）。
> ② **静默改写（档案没记，本轮新查）**：混合形态**不报错**，但**产物声道结构 = 第一路的布局**
>   （实测 `[5.1,stereo]→6/5.1`、`[stereo,5.1]→2/stereo`、`[unknown6,stereo]→2/stereo`）
>   ⇒ 用户多段原片合并后的声道数由**输入顺序**决定，且**零留痕**。
> 真形源不是手造的：`C:\Users\Bsaizne\Downloads\clips\clips\og*.mp4`（用户从本产品导出）**35 个文件逐个探过 = 6ch/unknown**；
> 成因链 = `5.1(side)` 编进 MP4 后布局信息丢失（与 `e79d4ee` 同一条）。测试夹具用 `pan=5.1(side)|…` 复现该形制，
> 并有一条 `test_fixture_is_actually_unnamed` 锁住"夹具真的是 unknown"。
> **二、修法**（`mvp/src/media/ffmpeg/source_merge.py`：纯函数 + 一处接线 + 一处日志）
> `resolve_audio_layouts()` 给每路算"要依次施加的布局链"：① 都写明且全等 ⇒ **空链 = 命令逐字不变**；
> ② 未写布局但按声道数可补名（1/2/6/8 → mono/stereo/5.1/7.1）⇒ 只补名（**声道数不变**）；
> ③ 补名后仍不一致或存在表外声道数 ⇒ 统一到**声道数最多**的可解析布局（否则退 `stereo`），
> 未写布局的路**先补名再归一**（补名后 ffmpeg 才拿到正确上/下混系数——实测 5.1→stereo 是**真下混**：
> 200/350/500/650/800/950Hz 六条单音在产物两声道里都在，不是丢声道）。
> 顺带把 `plan.reason` 落进日志：此前 `reason` 既不回传也不打日志，连原有的"音频有无不一致，降级纯视频"也一直隐身。
> **三、验收**
> - 同脚本双臂：改后 `allunknown2/3/7` **RAISE → OK 且产物 6/5.1**、`real_unk_pair`（真 og 派生）转绿、
>   `unk_then_st` 与 `st_then_unk` 产物布局**相同**（顺序不再决定）；基线 `stereo_base` 仍 2/stereo 且命令逐字未变。
> - 新锁 **13 项**（纯函数 6 + `_transcode_args` 结构 3 + 真 ffmpeg E2E 4，含一条**日志留痕锁**）；
>   后端全套 **Ran 688 OK (skipped=2)**（改前 675）· API **Ran 150 OK** · 导出计划不变式 **FAILED=0**，三条 rc 均 0。
> - 预期红实测：`source_merge.py` 退回 HEAD 版跑新测试文件 ⇒ `ImportError: cannot import name 'resolve_audio_layouts'`；
>   行为级红由 `pre_fix_report3.json`（RAISE + 2/stereo）承载。
> **四、两条新登记（本批不做，只记）→ ✅ 两项均已于同日续63 补廿二 收口**（①的修法换了方向：不是探测提速，是不再报假故障）
> ① `available_hevc_encoders()` 只看 ffmpeg 编码器列表、不看能否真开 ⇒ 本机每次合并**白跑 nvenc + qsv 两回**
>   （各一次完整滤镜图初始化，stderr 分别 `Cannot load nvcuda.dll` / `Error creating a MFX session: -9`）；
> ② **copy 腿**签名 = `(codec, sample_rate, channels)` **不含布局** ⇒ 6ch/unknown 与 6ch/5.1 判为"可流复制"，
>   产物布局同样由第一段决定；本批只改转码腿（动签名会收紧 copy 命中率，需单独判据与回归）。
> **产物**：代码笔 `mvp/src/media/ffmpeg/source_merge.py` + `mvp/tests/test_source_merge.py`（待提）；
> 探针/日志（不入库）`work/merge_layout_20261018/{attribute_pre.py, attribute_pre2.py(自身缺陷判废),
> attribute_pre3.py, pre_fix_report3.json, post_fix_report3.json, measure_collapse.py(余弦法因未对齐不作证据),
> spectral_semantics.py, test_source_merge*.log, backend_suite*.log, api_suite.log, invariants.log}`。

> **▶ 2026-10-18（续63 补廿二）— 两项遗留收口：开不了的编码器不再白试/不再报假故障 + copy 判据补布局 + 一条会让补廿一静默失效的加固【现读这条】**
> 口令「接着修那两项遗留问题」。**改了产品代码，未出包** ⇒ 用户手上仍是 r25，补廿一 + 本批两条修复他都没有。
> **① 编码器白跑（前提被实测改写了两次，别照档案原话做）**
> - **时间不是主项**：微型探测本身同价（本机每条死编码器 ≈0.57s、探测 7 条 = 2.82s）⇒ **没有引入任何探测子进程**。
> - 真正的缺陷是**用户可见的假故障**：改前每次合并向进度流播报
>   `硬件编码器 hevc_nvenc 执行失败，已回退到 hevc_qsv` + `…hevc_qsv 执行失败，已回退到 hevc_amf`
>   （本机无 NVIDIA/Intel 属正常态）。实测两臂各 6 条消息、其中 **2 条是假故障**。
> - 实装 = **结构性判据**「一帧都没编出来」（不匹配 stderr 文案）⇒ 开场即败者进**进程内黑名单**
>   （按 ffmpeg 路径分键；`libx265` CPU 兜底**永不拉黑**），下次直接跳过并留一条日志；
>   **编到一半死**（参数/素材问题）仍照常播报，两种失败不混。
> - 双臂读数：改后 run1 假故障 **0 条**（仍付一次发现成本，wall 5.06s）、run2 **1.77s**（改前同臂 4.98s
>   ⇒ 同进程内后续每次省 ≈3.3s）。
> **② copy 腿布局**
> - 签名加**补名后**的布局：`6ch/unknown` 与 `6ch/5.1` 同序 ⇒ **仍判可流复制**（不把分集原片从秒级 copy
>   拖进几十分钟转码）；`5.1(side)` 别名归一到 `5.1` 同理（FFmpeg ≥7.1 区分二者，只差下混系数不差声道顺序）。
> - ⚠️ **收紧面在 MP4 上实测不可观测**：`hexagonal` 编进 MP4 后 ffprobe 也只报 `6/unknown`
>   ⇒ 造不出"两路都写明且顺序不同"的 MP4 对照（`leftover_arms.json` 四对全 copy）。
>   真实收益 = 容器**确实声明了**不同布局的情况（MKV `5.1` vs `hexagonal`、`stereo` vs `dual_mono`）不再误判可流复制。
> - copy 腿另加 `copy_layout_note()` 留痕：实测 `-c copy` 配 `-channel_layout 5.1 -ac 6` **仍写 unknown**
>   ⇒ 改不了元数据，只能如实记「产物音轨按第一段声明解释其余段」。
> **③ 顺带堵掉一个会让补廿一整套归因静默失效的洞**
> `declared_layout` 原先把字面 `"unknown"` 当"已写明"——ffprobe 的 **csv 视图给 `unknown`、json 视图缺字段**，
> 现役恰好靠 json 才没出事（换个取数方式就整条链路静默退回旧行为）。现在两种都算未解析，
> 并有锁 `test_literal_unknown_from_ffprobe_is_still_unnamed`。
> **验收**：新锁 **6 项**（`LeftoverFixTest` 5 + `DeadEncoderSkipE2ETest` 1）；
> 后端 **Ran 694 OK (skipped=2)**（补廿一 688）· API **Ran 150 OK** · 导出计划不变式 **FAILED=0**，三条 rc 均 0。
> **产物**：代码笔 `mvp/src/media/ffmpeg/source_merge.py` + `mvp/tests/test_source_merge.py`；
> 探针/日志（不入库）`work/merge_layout_20261018/{leftover_probe.py,leftover_probe.json,leftover_arms.py,
> leftover_arms_pre.json,leftover_arms_post.json,test_leftover*.log,backend_suite3.log,api_suite3.log,invariants3.log}`。
> **现役未结项**：主线「过渡不流畅」三样外部输入 · `og720-720` 挂账 · 下次出 r26 时删 r23 ·
> ⚠️ 出包时 **mac 要另走 dispatch**（补廿一 + 本批都是纯后端 Python 改动）。

> **▶ 2026-10-18（续63 补廿三）— r26 出包（构建点 = 干净 commit `ad7cec4`）+ 包内新增第五道「合并腿」实测；mac dispatch 卡在令牌【现读这条】**
> 口令「打包 r26 并在 mac 跑 dispatch」。**推远端已完成 = `e5b5d90..ad7cec4`（6 笔，fast-forward，无 force）**。
> ⚠️ **mac dispatch 没做成（等他一步）**：非交互取令牌两条路都堵——`git credential fill` 返空；
> `git credential-manager get` 首跑**挂死 60s**，加 `GCM_INTERACTIVE=never` 后明确报
> `Cannot prompt because user interactivity has been disabled`（rc=255）⇒ 按规矩**停手不重试、不弹窗**。
> 入口：仓库 `bsaizne/source-video-locator` → Actions → **H3 macOS MPS POC + MVP tests** → Run workflow
> （ref=master，head 应为 `ad7cec4`）；或他本机交互跑一次 `git credential-manager get` 让令牌可用，我再 dispatch。
> ⚠️ **顺带订正一条档案判据**（就在他要决定的这件事上）：补十九 块写的「`mvp/ui` 零改动 ⇒ mac 不需另走
> dispatch」**只对了一半**——mac 包的 backend 由 CI 从检出 ref **现编**（workflow 有
> `Build backend bundle (PyInstaller onedir…)`）⇒ **凡 `mvp/src` 改动 mac 就得重出**。
> 所以现役 mac 包（10-16 dispatch，head `c789670` ≈ r24 代）**不含** r25 两笔（`e79d4ee` 音轨布局回退、
> `36acc50` cap 1.5）也**不含**补廿一/补廿二。判据改为：**`mvp/src` 或 `mvp/ui` 任一改动 ⇒ mac 需 dispatch**。
> **构建** = `mvp/ui/scripts/build-release.ps1` 四步 rc=0（`work/r26_pkg/build_r26.log`，[3/4] `Build complete!`）。
> **五道包内验收串行、逐条取 rc（全 0）**：
> · bundle **33 PASS / FAILED=0**（12 行 `locate leg=` 齐、跳格 48 分位口径对得上）
> · render **FAILED=0**（64 段 / 136.344 vs 136.366s / h264_amf / wall 60.1s，与 r25 **逐字同**）
> · 导出计划不变式 **FAILED=0**（4 片 × 4 通道）· 启动冒烟 **FAILED=0 / AFTER_KILL=0**
> · **新增第五道 `work/r26_pkg/accept_packaged_merge.py` FAILED=0** = 真起包内 `backend.exe` + 包内 ffmpeg/ffprobe
>   打 `POST /api/source/merge`：M1 两个「6ch+未写布局」输入合并 `mode=transcode` 且产物 **`6/5.1`**、
>   夹具锁确为 `6/unknown`、M2 两种先后顺序产物布局**相同**（改前是 `6/5.1` vs `2/stereo`）、
>   M3 包内支持档出现 `source merge plan:` 留痕 ⇒ **补廿一 + 补廿二 的修复确认在分发包里生效**。
> **zip 身份**（两把尺子读数逐字相同：`make_zip_r26.py` 与独立的 `work/r17_pkg/zip_identity.py`）
> = `Video-Locator-win-x64-20261018r26.zip` **981,697,844B**（对 r25 **+4,239B**）/ 条目 **7,079**
> （文件 6,993 + 空目录 86，与 r25 同）/ `testzip=None` / `root_form=flat` /
> `backend.exe 77,502,636B sha16 9410f2e7baa948d6` **zip 内 == 磁盘**（对 r25 的 77,498,025B **+4,611B**，
> 与本批源码改动面相容）/ `bridge.js 8,882B sha16 7d3e0427e3d3a4db` **与 r25 逐字相同**（本批零 JS 改动）/
> **与 r25 文件名集合差集 = 0/0** / 渲染层含 `/api/tasks/export` 的资产仍命中 `index--VHmdytl.js`。
> **覆盖边界（如实）**：① M1 那句"改前会 500"来自**源码树实测**（`pre_fix_report3.json` 的 RAISE），
> **包内改前臂没跑**——r25 的 `win-unpacked` 已被本批构建覆盖，为补一条对照重解 981MB 包不值；
> ② 第五道目前住在 `work/r26_pkg/`，**升不升为常设（`mvp/scripts/`）待他拍板**；
> ③ 分发包现有**四档**（r26/r25/r24/r23）。
> **待口令**：ⓐ mac dispatch（见上）；ⓑ 按「每出一代删最老」应删 **r23**——删前照例双验 r25/r24 逐字一致
> （脚本 `work/r25_pkg/precheck_delete_r22.py` 改 EXPECT 即可复用）。
> **产物**：`work/r26_pkg/{build_r26.log, accept_{bundle,render}_r26.log, invariants_r26.log, startup_r26.log,
> accept_packaged_merge.py, accept_merge_r26.log, make_zip_r26.py, make_zip_r26.log, dispatch_mac.py}`。

> **▶ 2026-10-18（续64）— 边界误差分型 + 索引网格损失（scn3 预演）+ B 线判负；一处判据订正与一条疑似缺陷【现读这条】**
> 口令「以你自己的理解说边界问题还要怎么进步」→「开」→「先 a 试试」→「再试试 b」→「交接」。
> **全程只读**（mvp/src 零改动、索引未重建、无新依赖）；明细 archive/HANDOFF_20261018_boundary_precision.md。
> **一、分型（先有分母）**：先复现 0.732/0.832/0.779，再拆 = 漏检 **21/125** · 漂移 **104**（le0.12s **26** /
> 0.12~0.50s **63** / >0.50s **15**）· 假阳 **38** · 有符号中位 **0.000**（早 38 / 晚 40 ⇒ **无系统偏置**）。
> **二、网格损失（本轮核心）**：同批候选、唯一变量 = 是否吸到 1fps 网格：abs_med **0.250 → 0.050**、
> le0.12s **27.6% → 77.9%**；现役漂移 p90 恰 **0.520s** = 1fps 吸附上限；与导出侧「真剪点偏差中位
> **0.249s**」同量级 ⇒ **端点漂移主因疑为网格而非扩宽规则**（与 cap 判负自洽；⚠️ 归因假设，未接线实测）。
> **三、scn3 预演（探针已入库）** mvp/scripts/shot_detect/probe_scn3_precision.py：尺子 ±0.5s →
> A 现役 n=93 **0.250 / le0.12 27** · B 像素10fps n=103 **0.050 / 82** · **C 融合(scn3) n=105 0.100 / 80**；
> 窗内条数 **142 → 134（不碎）**。导出侧 11 条真剪点：A **0.249**（le0.12 4/11）· B/C **0.000**（⚠️ **同源**）。
> **四、B 线判负**（语义分格 CLS：整帧+左中右三竖条，零新依赖；cv2 在位但 haar/YuNet 模型为空）：
> 两窗口（±2s / [-4,0]）A 族最好 **0.555**、B 族最好 **0.553**，判死线 0.70 ⇒ **不接线、不加依赖**。
> 旁证：GT 处整帧语义距离 **0.0869** vs 随机 **0.0857**（若真是两人对切，语义不可能不动）。
> **五、⚠️ 判据订正（我错，原话留档）**：第一版用 **±0.5s** 窗口，但这批样本精度是 **±2~4s**
> （t1_long_sheets.py:33 FPS=0.25；t1_missed_attr.py:54 WIN=2.0）⇒ 那组「AUC 0.42~0.53 判负」**作废**，
> 已按两窗口重算（见四）。教训：**判据窗口必须与样本时间精度匹配**。
> **六、新发现（未决）**：52 条漏切拆 verdict = **P2 45 条(87%，pix 中位 0.040)** /
> **P3 5 条（有峰被「3×邻域中位」杀；读图确认 2 条真切点：t=1831 屋顶→火焰 @t+1.2s、
> t=6861 双人全景→遮挡近景 @t+0.4s）** / P1 1 条 / **?CLS腿应命中 1 条（cls_max 0.718 远高于门 0.30 却漏
> ⇒ **疑似真缺陷，优先级最高**）**。
> **▶ 2026-10-18（续65）— 结案「CLS 0.718 疑似缺陷」：是假缺陷；但挖出真漏检 + verdict 链结构缺陷 + 门扫参零和【现读这条】**
> 口令「继续」。**全程只读**（`mvp/src` 零改动、索引未重建、无新依赖、未出包）。
> **一、结论翻转**：t=3782 那条 **CLS 腿命中了、边界也产出了**（3780.0）——不是缺陷。
> 探针 `work/boundary_20261018/cls718_probe.py` 逐环复刻生产链：CLS 峰 **0.7185 @t=3780.0**（local_peak、
> ≥0.30、**gate 通过 dist=0.2531/dev=0.2527**）· 像素腿候选 **3780.3**（gate 通过）· 融合后两者同位置被 NMS
> 合成一条 ⇒ `scenes.npy` 确有 **3780.0**。
> **二、错在哪（两处都是我的，原话留档）**：① `t1_missed_attr.py` **判定窗 ±1.5s 窄于取峰窗 WIN=2.0s** ——
> 边界落在 1.5~2.0s 之间时，脚本一边拿它当证据一边判它不存在；本案 3780 距 3782 = **恰 2.00s** ⇒ 被判 has_bound=False。
> ② 该脚本 verdict 是 **if-elif 链，CLS 腿排最后** ⇒ 被像素腿否掉的条目**永远走不到 CLS 分支**，
> 于是「52 条只 1 条标 CLS」被误读成「CLS 腿只对 1 条有信号」。独立复算（`cls_arm_coverage.py`）=
> **局部极大且 ≥0.30 共 11 条**（非 1 条），过 gate 后 2 条**全部落在已有边界上** ⇒ 真实净漏 = **0**。
> **三、目检坐标自己偏了 ~1.7s**：0.25fps 接触表（4s 一格取中点）在 5fps 细采样下显示真切点在 **3780.3**
> （`fine_429_3782.png`：3777~3780.0 同一暗场景 → **3780.2~3780.4 切**；10fps 像素 `3780.3=0.1865` 为全窗第一，
> 是第二名 2.3 倍）⇒ 生产边界 3780.0 误差 0.3s = **命中**，是**目检坐标偏晚**不是引擎漏。
> **四、同批确有真漏检（兄弟条）**：`idx=429 t=3814` → 像素腿 ±2s **空集**（窗内最大 0.0838 < 绝对门 0.12）；
> CLS 腿 **0.4411 @3816.0 通过**；**持续性门 dist=0.0973 < 0.10 差 0.0027 被否** ⇒ 不出边界。
> 5fps 细采样确认真切点 **3815.6**（人物灰衣背影 → 暗处火焰）⇒ **信号对、是门杀的**。
> **五、但放宽门是零和（可证伪检查已做）**：`gate_sweep.py` 生产同款判据扫参 —— 现役 0.842；
> best **dist=0.06 → 0.845（+0.003 噪声级）**，且 ±0.5s 口径变差、边界数 +4%；**gate 全关 0.781（崩）**。
> ⇒ **调门不是解**；要救这类只能给 CLS 腿**独立门**（判据改动，需单独立项拍板）。
> **已落档**：`mvp/docs/FINDINGS_BOUNDARY_PRECISION_20261018.md` **§9**（自包含，含 6 条复跑命令）。
> **立项（2026-10-18「开始立项吧」）**：`mvp/docs/PLAN_BOUNDARY_ALIGNMENT_20261018.md` ——
> ① scn3 网格精度（**可直接动码**）② CLS 腿独立门（⚠️**动码前须先裁产品口径**：同场景正反打算不算一个镜头；
> 我从 `evidence_localize.py:154-158` 查到场景表在代码里的作用是**扩池单元不是镜头身份** ⇒ 建议口径 C 折中标注）
> ③ 弱信号段低置信标注（侧车文件，向后兼容硬断言）。已同步登记到 TODO P1。
> **未结项**：① 接 scn3（bump scn2→scn3 + 出包 r27 + mac 另走 dispatch）
> ② ~~改相对门（P3 那 5 条，上限 4%）~~ = **已结案 = 不做**（见 §10：可达只有 3 条、尺子对这 5 条无话可说、
> 放宽使 R 恒 0.872 不变而 P 单调下滑、全片 +68~150 条边界）⇒ **`pixel_rel_mult=3.0` 改为实测最优档，不再列为待改项**
> ③ ~~查 CLS 0.718 异常~~ = **已结案（假缺陷）**，剩余「CLS 腿独立门」属新立项待拍板
> ④ 主线「过渡不流畅」三样外部输入 ⑤ 下次出包删 r24。
> **新教训（写进 §9.6 第 4 条）**：0.25fps 接触表成的坐标单条不确定度是 **±2s 级**，不能用它论证「精确到秒的漏检」；
> §8.1 那条「判据窗口必须匹配样本精度」在**数据源侧**同样成立。

> **▶ 2026-10-18（续63 补廿四）— r23 已删 + cap 1.5 结论从单片扩到四片（含两条对我自己上一轮的订正）+ C 盘占用查清【现读这条】**
> 口令「删旧包吧，然后继续，然后查查为什么做你这个项目我的 C 盘老被占用空间，不是都在 D 盘吗」。
> **一、删旧包**：按「每出一代删最老」删 **r23**（释放 981,687,209B ≈ 936MB）。删前
> `work/r26_pkg/precheck_delete_r23.py` 双验（期望值从 197 份 `.agent` 文本里抓、读数从 zip 里取）：
> **r26 现役 / r25 / r24 三档与档案逐字一致、`testzip=None`**，r23 自身身份留痕
> = 981,687,209B / 7,078 条目 / backend.exe 77,493,384B sha16 `537bcca18760de77`。⇒ 磁盘三档 = **r26/r25/r24**。
> **二、⚠️ 订正我上一轮写的两条（都是我的错，原话留在档案里不悄悄改，只加订正）**
> ① **「test1/2/3 原片不在本地 ⇒ 单片结论」= 错**。四片原片**全在本地 D 盘**：
>   `D:\video\2.mkv` + `D:\ProjectXIXI\test{1,2,3}\test{n}-om.*`（逐个 `os.path.exists` 已验）。
>   错因 = 我自己那条 grep 管道里的 `sed 's/.*: *//'` **把盘符 `D:` 一起吃掉了**，
>   于是 `D:\ProjectXIXI\...` 显示成 `\ProjectXIXI\...`，我据此判成"UNC 不可达"。
>   ⇒ 教训同族但形态新：**shell 文本处理能造出"看起来像证据"的假读数**；路径存在性一律用
>   `os.path.exists` 逐条判，不要用 sed/grep 的输出反推。
> ② **「cap1.5 逐 clip == 关闭扩宽」+「1.5 档卷轴区间 == 成片通道区间」= 只在 3/4 片成立**。
>   test3 有 **1 条 clip 在 1.5 档仍被扩宽**（`clip62` core=[2939.000, 2943.167] 4.17s → 1.5 档
>   [2939.000, 2945.000] 6.0s = **1.44×，正好在 1.5 阈内**），⇒ 该片的"卷轴 == 成片"不成立。
>   口径改为：**cap 1.5 ≈ 关闭扩宽**（四片 234 条 clip 里 1 条仍扩宽），不是"等于关闭"。
> **三、四片实测（`work/cap15_film_20261018/{four_cases.py,four_case_report.json,sheets_four.py,sheets4/}`）**
> | 片 | clips | 两档不同 | cap 归因 | 至少一边不在切点 1.5/2.5 | Σ素材宽 2.5/1.5/core | 1.5==core | 1.5 卷轴==成片 |
> |---|---|---|---|---|---|---|---|
> | 2mkv | 72 | 12 | 10 | 47 / 37 | 161.2 / 135.4 / 135.4 | ✓ | ✓ |
> | test1 | 45 | 7 | 7 | 42 / 35 | 103.0 / 84.6 / 84.6 | ✓ | ✓ |
> | test2 | 47 | 9 | 8 | 25 / 17 | 92.2 / 76.7 / 76.7 | ✓ | ✓ |
> | test3 | 70 | 11 | 9 | 37 / 28 | 142.7 / 125.0 / **123.2** | **✗ 1 条** | **✗** |
> | **合计** | **234** | **39** | **34** | 151 / 117 | 499.1 / 421.7 / 419.9 | 3/4 片 | 3/4 片 |
> 真剪点偏差（四片合并，44 个扩宽边界、±1.0s 窗逐帧自算像素差）：**32/44 有显著剪点，
> 中位 |Δ| 0.249s、最大 0.917s，26/32 偏 >0.12s、11/32 >0.30s**；按符号 **18 正向 = 2.5 素材把邻镜头
> ≤0.9s 带进卷轴（闪切）**、14 负向 = 少带 0.2~0.9s 本镜头内容。
> 读图 **7/7 张**（新增三片各取头/尾最长两条 + test3 那条 1.5 仍扩宽的）：
> test1 出点时两人扭打未完（丢 4.0s 收尾）／test2 出点丢掉守卫转身收尾 2.0s／test3 入点从精灵特写中段开始
> （丢 2.0s）；2.5 侧 test3_clip33 素材头 **带进上一条镜头 ~0.4-0.8s**（与 18 条正向偏差同向对上）；
> test3_clip62 的 1.5 档出点 2944.72 距真剪点 ~2944.9 只差一两帧 ⇒ **1.5 不是"砍掉收尾"，是"只允许到 1.44×"**。
> **⇒ 补二十 的结论在四片上全部成立且更强**：cap **既不是「过渡不流畅」的成因、也不是解药**
> （cap 归因 34/234 条，而"切口落在镜头中间"两档都有 117~151 条）；单片覆盖边界**已关闭**。
> **四、C 盘占用查清（`work/cdisk_20261018/measure_c.py`，只量不删）**
> | 写入点 | 量 | 谁写的 |
> |---|---|---|
> | `%TEMP%\rea-ghidra-*`（两个目录） | **6.39 GB** | **竞品逆向那条线**（Ghidra headless 工作区，10-17 00:12 / 02:14，内含 428MB 目标 exe 副本 + 分析缓存）⇒ 不是本项目 |
> | `%APPDATA%\Video Locator AI` | 488 MB（`data` 377 + `Cache` 95） | **分发包数据根** + 包内验收（`attr_packaged_headless.appdata_dir()` 就指这里：index 116 + edited_cache 126 + models 88 + isc 30 + merged 11） |
> | `~\.qoder-cn` | 735 MB | CLI 自身（会话/记忆/快照） |
> | `%LOCALAPPDATA%\SourceVideoLocator` | 448 MB（edited_cache 228 + index 102 + models 88） | **源码树/探针态数据根**（`paths.app_data_dir()` = LOCALAPPDATA） |
> | 工具链缓存 | ~1.1 GB | uv 406 + pip 386 + npm 191 + electron 116（venv 在 D，**缓存目录默认在 C**） |
> | `%TEMP%\_MEI000022f02` | 90 MB | PyInstaller 解包残留（10-11，非正常退出留下的） |
> | 我的探针/单测残留 | **仅 14.8 MB**（163 项） | `svl_*`/`tmp.*`；`tempfile.mkdtemp` 在单测 `setUpClass` 里**没有配平清理** ⇒ 每跑一次全套留 ~10 个目录（量小但在长） |
> ⇒ **结论：代码与产物确实在 D，吃 C 的是"数据根按设计落 AppData"+"一次性逆向工作区 6.39GB"+"工具链缓存"**。
> **处置 = 用户裁决（2026-10-18）：三项都不做、不入待办、以后勿再提议。**
> **五、现役未结项**：ⓐ ~~mac dispatch 待他一步~~ = **已闭合**（run `39060341032` 全程 22.5min，
>   三 job 全 success；`macos-package` 11.5min、21 步全绿，含
>   **`Accept packaged mac bundle (gate publish)` success** 与 **`Publish to mac-alpha` success**；
>   回读资产 = `Video-Locator-mac-arm64.zip` **917,013,005B @ 2026-10-17T19:19:39Z**，
>   对旧值 916,840,558B @ 10-13 **+172,447B 且时间戳变** ⇒ 包确实换了，**mac 侧已含 r25+r26 全部后端修复**）；
>   ⓑ 第五道包内合并验收**升不升为常设**；ⓒ 主线「过渡不流畅」三样外部输入；
>   ⓓ `og720-720` 相似度自相矛盾挂账。
> **产物**：`work/r26_pkg/precheck_delete_r23.py`、`work/cap15_film_20261018/{four_cases.py,four_case_report.json,four_cases.log,sheets_four.py,sheets4/×7,sheets4_index.json}`、`work/cdisk_20261018/measure_c.py`。

## 续63 补廿四 块（逐字迁入，2026-10-18 出包 r27 时）

> **▶ 2026-10-18（续63 补廿四）— r23 已删 + cap 1.5 结论从单片扩到四片（含两条对我自己上一轮的订正）+ C 盘占用查清【现读这条】**
> 口令「删旧包吧，然后继续，然后查查为什么做你这个项目我的 C 盘老被占用空间，不是都在 D 盘吗」。
> **一、删旧包**：按「每出一代删最老」删 **r23**（释放 981,687,209B ≈ 936MB）。删前
> `work/r26_pkg/precheck_delete_r23.py` 双验（期望值从 197 份 `.agent` 文本里抓、读数从 zip 里取）：
> **r26 现役 / r25 / r24 三档与档案逐字一致、`testzip=None`**，r23 自身身份留痕
> = 981,687,209B / 7,078 条目 / backend.exe 77,493,384B sha16 `537bcca18760de77`。⇒ 磁盘三档 = **r26/r25/r24**。
> **二、⚠️ 订正我上一轮写的两条（都是我的错，原话留在档案里不悄悄改，只加订正）**
> ① **「test1/2/3 原片不在本地 ⇒ 单片结论」= 错**。四片原片**全在本地 D 盘**：
>   `D:\video\2.mkv` + `D:\ProjectXIXI\test{1,2,3}\test{n}-om.*`（逐个 `os.path.exists` 已验）。
>   错因 = 我自己那条 grep 管道里的 `sed 's/.*: *//'` **把盘符 `D:` 一起吃掉了**，
>   于是 `D:\ProjectXIXI\...` 显示成 `\ProjectXIXI\...`，我据此判成"UNC 不可达"。
>   ⇒ 教训同族但形态新：**shell 文本处理能造出"看起来像证据"的假读数**；路径存在性一律用
>   `os.path.exists` 逐条判，不要用 sed/grep 的输出反推。
> ② **「cap1.5 逐 clip == 关闭扩宽」+「1.5 档卷轴区间 == 成片通道区间」= 只在 3/4 片成立**。
>   test3 有 **1 条 clip 在 1.5 档仍被扩宽**（`clip62` core=[2939.000, 2943.167] 4.17s → 1.5 档
>   [2939.000, 2945.000] 6.0s = **1.44×，正好在 1.5 阈内**），⇒ 该片的"卷轴 == 成片"不成立。
>   口径改为：**cap 1.5 ≈ 关闭扩宽**（四片 234 条 clip 里 1 条仍扩宽），不是"等于关闭"。
> **三、四片实测（`work/cap15_film_20261018/{four_cases.py,four_case_report.json,sheets_four.py,sheets4/}`）**
> | 片 | clips | 两档不同 | cap 归因 | 至少一边不在切点 1.5/2.5 | Σ素材宽 2.5/1.5/core | 1.5==core | 1.5 卷轴==成片 |
> |---|---|---|---|---|---|---|---|
> | 2mkv | 72 | 12 | 10 | 47 / 37 | 161.2 / 135.4 / 135.4 | ✓ | ✓ |
> | test1 | 45 | 7 | 7 | 42 / 35 | 103.0 / 84.6 / 84.6 | ✓ | ✓ |
> | test2 | 47 | 9 | 8 | 25 / 17 | 92.2 / 76.7 / 76.7 | ✓ | ✓ |
> | test3 | 70 | 11 | 9 | 37 / 28 | 142.7 / 125.0 / **123.2** | **✗ 1 条** | **✗** |
> | **合计** | **234** | **39** | **34** | 151 / 117 | 499.1 / 421.7 / 419.9 | 3/4 片 | 3/4 片 |
> 真剪点偏差（四片合并，44 个扩宽边界、±1.0s 窗逐帧自算像素差）：**32/44 有显著剪点，
> 中位 |Δ| 0.249s、最大 0.917s，26/32 偏 >0.12s、11/32 >0.30s**；按符号 **18 正向 = 2.5 素材把邻镜头
> ≤0.9s 带进卷轴（闪切）**、14 负向 = 少带 0.2~0.9s 本镜头内容。
> 读图 **7/7 张**（新增三片各取头/尾最长两条 + test3 那条 1.5 仍扩宽的）：
> test1 出点时两人扭打未完（丢 4.0s 收尾）／test2 出点丢掉守卫转身收尾 2.0s／test3 入点从精灵特写中段开始
> （丢 2.0s）；2.5 侧 test3_clip33 素材头 **带进上一条镜头 ~0.4-0.8s**（与 18 条正向偏差同向对上）；
> test3_clip62 的 1.5 档出点 2944.72 距真剪点 ~2944.9 只差一两帧 ⇒ **1.5 不是"砍掉收尾"，是"只允许到 1.44×"**。
> **⇒ 补二十 的结论在四片上全部成立且更强**：cap **既不是「过渡不流畅」的成因、也不是解药**
> （cap 归因 34/234 条，而"切口落在镜头中间"两档都有 117~151 条）；单片覆盖边界**已关闭**。
> **四、C 盘占用查清（`work/cdisk_20261018/measure_c.py`，只量不删）**
> | 写入点 | 量 | 谁写的 |
> |---|---|---|
> | `%TEMP%\rea-ghidra-*`（两个目录） | **6.39 GB** | **竞品逆向那条线**（Ghidra headless 工作区，10-17 00:12 / 02:14，内含 428MB 目标 exe 副本 + 分析缓存）⇒ 不是本项目 |
> | `%APPDATA%\Video Locator AI` | 488 MB（`data` 377 + `Cache` 95） | **分发包数据根** + 包内验收（`attr_packaged_headless.appdata_dir()` 就指这里：index 116 + edited_cache 126 + models 88 + isc 30 + merged 11） |
> | `~\.qoder-cn` | 735 MB | CLI 自身（会话/记忆/快照） |
> | `%LOCALAPPDATA%\SourceVideoLocator` | 448 MB（edited_cache 228 + index 102 + models 88） | **源码树/探针态数据根**（`paths.app_data_dir()` = LOCALAPPDATA） |
> | 工具链缓存 | ~1.1 GB | uv 406 + pip 386 + npm 191 + electron 116（venv 在 D，**缓存目录默认在 C**） |
> | `%TEMP%\_MEI000022f02` | 90 MB | PyInstaller 解包残留（10-11，非正常退出留下的） |
> | 我的探针/单测残留 | **仅 14.8 MB**（163 项） | `svl_*`/`tmp.*`；`tempfile.mkdtemp` 在单测 `setUpClass` 里**没有配平清理** ⇒ 每跑一次全套留 ~10 个目录（量小但在长） |
> ⇒ **结论：代码与产物确实在 D，吃 C 的是"数据根按设计落 AppData"+"一次性逆向工作区 6.39GB"+"工具链缓存"**。
> **处置 = 用户裁决（2026-10-18）：三项都不做、不入待办、以后勿再提议。**
> **五、现役未结项**：ⓐ ~~mac dispatch 待他一步~~ = **已闭合**（run `39060341032` 全程 22.5min，
>   三 job 全 success；`macos-package` 11.5min、21 步全绿，含
>   **`Accept packaged mac bundle (gate publish)` success** 与 **`Publish to mac-alpha` success**；
>   回读资产 = `Video-Locator-mac-arm64.zip` **917,013,005B @ 2026-10-17T19:19:39Z**，
>   对旧值 916,840,558B @ 10-13 **+172,447B 且时间戳变** ⇒ 包确实换了，**mac 侧已含 r25+r26 全部后端修复**）；
>   ⓑ 第五道包内合并验收**升不升为常设**；ⓒ 主线「过渡不流畅」三样外部输入；
>   ⓓ `og720-720` 相似度自相矛盾挂账。
> **产物**：`work/r26_pkg/precheck_delete_r23.py`、`work/cap15_film_20261018/{four_cases.py,four_case_report.json,four_cases.log,sheets_four.py,sheets4/×7,sheets4_index.json}`、`work/cdisk_20261018/measure_c.py`。

> **▶ 2026-10-18（续66）— 立项①+③ 同批落地：scn3 网格精度接线 + scene_strength 侧车（代码已提交 `5bb8089`）【现读这条】**
> 口令「① 先做 → ②-0 裁口径 → ③ 与 ① 同批最省事」。**本批动了 `mvp/src`**（4 源文件 + 2 测试）。
> **一、scn3 是什么**：判据**一格未动**，只把场景边界时刻从 **1fps 索引网格**换成像素腿的 **10fps 原始候选时刻**。
> 现役把边界吸到 1fps 网格（`_snap_index`，实测有符号位移中位 **+0.215s**、绝对中位 0.28s）；
> 下游 `exporters.snap_clips_to_scenes` 直接吃这张表吸附 clip 端点 ⇒ 精度提升**会落到成片端点**。
> **二、验收（全绿）**：等价性 = 默认路径与 scn2 **逐字节相同**（scn2 sha `e6b0946c3129bc61` 不变）·
> `scene_feats` sha `e1cfe6ca7bdea10a` **不变**（指纹零漂移）· **943 场景不变** ·
> **373/943 条边界真的离开网格**（`|Δ|` 最大 **0.500s** = 1fps 半格，正是吸附上限）· 不变式 `gap=0`。
> **尺子三档复跑与档案逐字一致**：A n=93 `0.250 / le0.12 27` · B n=103 `0.050 / 82` · C n=105 `0.100 / 80`，
> 窗内条数 **142 / 128 / 134**。**后端 699 OK（skipped=2）· API 150 OK**；合成端到端 13 项全绿。
> **三、侧车 `scene_strength.npy`（立项③）**：`[S] float32` 场景**起始边界**融合强度，第 0 个恒 1.0（文件起点非切分）。
> **不动 `scenes.npy` schema**（仍 `[S,2]`，测试有硬断言）⇒ 旧索引照常可读、不因侧车全量重建。
> 长度必须严格等于场景数，否则 `_load_scene_strength` 返回 **None**（**宁可丢也不修**：错位强度比没强度更危险）。
> `IndexBundle.scene_strength` 新字段，`None`=旧索引 ⇒ 下游行为与引入前逐字相同。
> **四、⚠️ 我踩的三个实现坑（全留在 IMPL §4）**：
> ① **改错位置**：第一版在 NMS 之后记原始时刻，但 `items` 里早就是 `float(times[j])` ⇒ `raw_out` 全空、边界一条没动，
>    被「至少有一部分边界真的动了」断言当场抓住。
> ② **修错方式**：改对位置后直接 `items.append((float(t), 1.0))` ⇒ **场景数 943→930**，因为 **NMS 按时间去重**，
>    items 时刻一变 NMS 结果就变 ⇒ 等于顺手改了 scn2 判定。最终 = `items` 保持 `times[j]`，原始时刻走**并行字典**
>    `raw_by_snap`，**完全不参与判据**。
> ③ **测试自己写错**：拿 scn3 结果当 baseline 去比 scn2。教训：**「默认路径不变」只能靠「同一输入跑两次默认调用」证**。
> **五、如实交代两处偏差**：① 立项写「另返回通道」，实现用**关键字出参**（改返回值要破 5 调用点 + 3 测试）；
> ② 真索引上的 `refresh_derived` 端到端**本轮没跑完**——重扫 8221s@10fps 实测 >6min 无进度输出，我停掉了；
> 链路证明改用合成片，真索引侧用 `verify_equiv.py` 单独证等价性与精度（两件事没互相替代）。
> **六、⚠️ 立档时我自己造的两次事故（已全部用 git 恢复，留档防复发）**：迁块时用「块首 → 章节尾」切片，
> 把后续块一起覆盖，块数 3→1；两次都靠 `git checkout -- .agent/STATE.md` 恢复。
> 教训：**迁块必须按「本块首 → 下一块首」切片，禁止用「本块首 → 章节尾」**；改完必须断言块数与残留。
> **七、未结**：① 4 片导出实得 + 导出计划不变式（**出包前硬验收**）② **出包 r27 + mac 另走 dispatch**
> ③ ②-0 产品口径仍待裁 ④ 立项③ 的「下游按阈值标注」未做（要等口径）⑤ 下次出包删 r24。
> 明细：`mvp/docs/IMPL_SCN3_20261018.md`（含踩坑与偏差）；计划 `mvp/docs/PLAN_BOUNDARY_ALIGNMENT_20261018.md`。
