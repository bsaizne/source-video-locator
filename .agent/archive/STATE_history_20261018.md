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
