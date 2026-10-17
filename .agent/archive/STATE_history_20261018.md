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
