# STATE 历史块归档（2026-10-08 瘦身）

> 按 AGENTS.md「档案防复发纪律」逐字迁移，一条未改未删。
> 来源：`.agent/STATE.md` Current Task 退休块（迁出时 Current Task 保持 ≤3 块）。


> **▶ 2026-10-07（续62）— 成片相邻段重复画面已修（导出/渲染层去重叠）**
> 用户报「剪出的片里两个相邻片段有重合，完整视频同一画面出现两次」。根因 = **定位段源窗有
> `min_span_s=2.0` 地板**（`config.py:138`，`locator_service.py:1795-1801` 夹紧居中），而剪辑段常
> 0.7~1.5s ⇒ 贴接相邻两段各被撑到 2s 宽**必然交叠**（数学上 ≈ 2s − 编辑时长），逐段取材再拼接的
> 产物就重复那段画面。放大项 = 导出层把段扩成完整镜头（实测有 ed=2.48s 拿 9.94s 源窗）。
> **不是最近几批引入的回归**（10-02 老结果同样有），之前在指标口径下不可见（严格指标只看 span 覆盖）。
> **既有边界**：剪映卷轴 `plan_jianying_assets` 早就有"重叠回并"去重，成片/EDL/XML 三处没有。
> 修 = 新增纯函数 `exporters.trim_adjacent_source_overlaps()`：编辑轴贴接（gap≤0.05s）的相邻主 clip
> 源区间交叠**按中点切开**（用户裁决）；**包含形态改为外层挖洞**成头/尾两条（同属该编辑段、记录槽按源宽比例分），
> 内层完整保留 —— 首版写成中点裁尾，真实四片回放暴露会丢外层独占右尾（2mkv 少 6.58s / test3 少 0.83s），
> **丢画面比重复更糟所以不采用**。单帧守卫：切完任一侧不足 1 帧 ⇒ 跳过该对；**非贴接重叠 = 真实复用不裁**
> （档案既有目检结论：连续场景内切多镜头的重叠多数正确）。接线 = `render_movie`（split 之后）+
> `export_project` 的 edl/fcp7_xml 分支；剪映卷轴不动。
> **证据**：后端 **565 OK**（+16 纯函数单测含包含/倒挂/链叠/守卫/幂等，+3 渲染接线锁含"非贴接不裁"）·
> API **105 OK** · 真实四片计划层回放 = 贴接重叠 7/2/4/16 → **0**，重复秒 8.99/0.53/3.73/10.22 → **0**，
> **并集覆盖 Δ=0.00**（一块不丢）。零语义为构造性：只改导出计划层不回写 `Result`，
> `measure_four_results` 读 Result 字段 ⇒ 三指标不可能变（已核）。
> **~~未闭合~~ → 已闭合（续62 补一）**：打包态真机渲染/导出一次 = 已由双臂 A/B 包内实测闭合（见下）。**已提交**（本批源码+测试+档案）。
> **r14 已出包（2026-10-07 00:21，口令「推ci并打包，删旧包只留 r13+r14」）**：
> `mvp/ui/release/Video-Locator-win-x64-20261007r14.zip` = 981,639,927 B / **7,078 条目** /
> `testzip()=None`；包内 `backend.exe` **77,448,544 B `sha16=4f5631af9e4ea51f`**
> （r13 = 77,445,580 / `52ca8c225bbc3683` ⇒ 新代码入包的尺寸+摘要硬证）；
> `Video Locator.exe` 与 ISC 图与 r13 逐字节同（未改动层，符合预期）。
> 验收：**accept FAILED=0**（冒烟 26.4s · DirectML 生效 · 精排与 ISC 未回退 CPU · 段数 1）·
> 三防 **FAILED=0**（`three_defense_smoke_r7.py`）· 启动冒烟 Electron 4 + backend 1 存活 25s，
> 用完即清 AFTER_KILL=0。构建日志 `work/build_r14.log`，验收日志 `work/accept_r14.log` /
> `work/three_defense_r14.log` / `work/zip_r14.log`。
> **✅ 剪映卷轴去重语义已统一（2026-10-07 续62 补二，用户拍板「先统一」）**：
> 剪映分支在取材扩展**之后**施加同一 `trim_adjacent_source_overlaps`（挂错在扩展前会失效），
> `plan_jianying_assets` 删除"重叠回并"改逐 clip 一素材（+撞名守卫）。四通道一套语义：
> 贴接对裁开、非贴接=真实复用保留。**顺带发现旧回并真缺陷**：条件只看源区间 ⇒ 源序回跳
> clip 被静默吞掉——四片回放旧卷轴 84/55/67/103 段只剩 5/49/22/3 条素材，
> 并集覆盖 4.28/123.01/37.05/14.61s（真实 152/129/97/167s，2mkv 丢 ~97%）。
> 门禁：后端 **569 OK**（+4 锁）· API **105 OK** · 四片回放 + 2mkv 真代码端到端 PASS
> （`work/jianying_unify_{replay,e2e}_20261007.py`）。代价：素材逐 clip ⇒ 抽取次数上升。
> **r14 不含本批**（进包需下次出包授权）；明细 CHANGELOG 续62 补二。
> **✅ 包体级判别已闭合（2026-10-07 续62 补一，双臂 A/B）**：不再等用户真项目——
> `work/r14_trim_pkg/r14_trim_pkg_probe.py` 打包态 headless 起 r13 与 r14 两臂
> （唯一变量 = backend.exe；ffmpeg/ffprobe/模型/env/数据目录/输入/导出参数逐字相同，
> r13 臂用 zip 抽出的完整 onedir 树），`/api/results/load` 灌真实四片结果批 →
> `/api/export`（edl+fcp7_xml，LOW+backup 全量门槛）→ 2mkv 渲染。判读：
> **r13 臂 EDL 贴接重叠 4/2/4/16 对、重复 4.98/1.32/3.73/11.06s（症状在修复前包内复现）；
> r14 臂四片 EDL+XML 全部 0 对 / 0 重复秒；并集覆盖两臂逐 case Δ=0.00（不丢画面）**；
> 渲染腿 r13 成片 166.020s（84 clips）vs r14 **160.974s**（86 clips，+2 = 挖洞头/尾条），
> 时长差 5.046s ≈ EDL 重复秒 4.98s ⇒ 重复画面确实从成片消失。两臂均 DirectML/h264_amf。
> 产物 `work/r14_trim_pkg/report.json`。明细 CHANGELOG 续62 补一。
> **分发包现状**（口令执行）：r10/r11 已删（释放 ~1.9GB），留 **r13（回滚）+ r14（现役）**。

> **▶ 2026-10-07（续63）— 导出计划层常态守卫 + 逐 clip 代价实测 + r15 出包（三件按用户「按你的想法来」自主推进）**

> **判断**：续62 两批真缺陷的共同根因不是函数写错，而是**同一套五步计划序列在

> `locator_service` 里抄了三遍**（成片 / EDL+XML / 剪映）——重复编排代码本身就是漏接的载体。

> **收口** = 新纯函数 `exporters.prepare_channel_plan(batch, channel=…, …)`：

> `build_export_plan → fragment_warnings → snap → boundary split →〔取材扩宽〕→ trim`

> 顺序硬固定，通道差异只允许是参数差异；stats 自带 `audit_pre_trim`/`audit` 两份体检。

> 新只读 `audit_source_overlaps()`：贴接重叠（违规）/真实复用（不动）/并集覆盖/零宽，

> **必须扫全对**（真实复用常隔着中间段，只看紧邻对会漏计——自己的新锁逼出来的）。

> 硬约束：`material_expand` 只允许 `channel='jianying'`，时间线通道误传直接 `ValueError`

> （本批收口时我就把它误透给三通道，EDL 并集覆盖 134s→531s=画面被整镜头撑大，

> 由 r15 **包体探针**抓回 ⇒ 教训：包内产物级判据不能只靠源码树）。

> **常态守卫**（入库）`mvp/scripts/check_export_plan_invariants.py`：真实四片 × 四通道，

> 贴接重叠 2/0/3/7 对 → **0**、并集覆盖 Δ=**0.00**（134.094/84.346/74.037/119.963s）、

> 三时间线通道同 plan=是；`reuse_pairs` **只报不断言**（外层挖洞会把与第三段的共享区间

> 让给内层，对数下降而画面不丢——断言它持平会把正确去重判成违反）。

> 新 `mvp/tests/test_export_plan_guard.py`（22 项）含 AST 结构锁：产品树里

> `build_export_plan`/`trim_adjacent_source_overlaps` 的调用点只允许在 helper 内 ⇒ 第五个出口漏接=红。

> **逐 clip 代价（补二欠账）**：计划层 2mkv 卷轴 64 条 / 宽度 815.75s / 去重后抽取 **56 次 701s**；

> 源码树三臂 `work/jianying_cost_20261007.py`：2mkv A(扩宽)=**81.1s** vs B(core)=33.0s（2.46×）、

> test2 89.2s vs 29.5s（3.02×）⇒ 代价主体是**取材扩宽**不是逐 clip，分钟级 ⇒ r15 可出。

> **r15 出包**（backend.exe `sha16` 逐代递增，`d45656f585826f4a` / 77,467,467B）：

> accept **FAILED=0**（含本批新加的 4 条隔离硬断言）· 三防 **FAILED=0** ·

> 启动冒烟 Electron 4 + backend 1 / AFTER_KILL=0 · 包体剪映探针

> `work/r15_jianying_pkg/probe.py` **FAILED=0**（EDL 134.12s、卷轴 64 条/56 文件/815.75s/531.0s

> 与计划层逐字对齐，包内墙钟 80.7s ≈ 源码树 81.1s）。

> **accept 首跑抓到的 ④ 包内缺陷**（已修）：隔离子进程不走 ASGI lifespan ⇒

> `configure_logging()` 无人调用，root logger 无 handler，INFO 被 lastResort 丢弃 ⇒

> 包内 stdout 与支持档 `video_locator.log` **一起缺整段分析记录**（三级日志=售后能力）；

> 加上父进程拿到终态信封就 terminate 又吞尾巴。修 = 子进程自配日志+行缓冲+flush、

> 正常终态先 `join(CHILD_GRACE_S=10s)`、payload 带父 `task_id` 让父子日志可串联。

> **更正登记**：续62 补五/补六 自报「双 typecheck 干净」**不实**——当时只过

> `typecheck:desktop`，渲染层 `vue-tsc` 有 5 个错（Mock 适配器 3 处缺 `last_event_at` +

> 徽标单测夹具用了契约外 `status`），r15 构建阶段 1 打回后已修。

> 新门禁基线 = 后端 **599** · API **120** · vitest **144** · app+desktop typecheck 双绿。

> **续63 补二（同日跟进）**：① 成片通道包内实测补上（`clip_ranges` 与源码树 movie 计划 64 段

> 逐字段相同、时长 136.366 vs Σ 136.344s、h264_amf、成片顺序紧邻交叠 0 对），并升为常设验收

> `mvp/scripts/accept_packaged_render.py`；② 那趟实测抓到 `submit_render` 漏传 `isolated`

> ⇒ **渲染从未进隔离子进程**（档案"analyze/render 子进程化"对成片不实，已更正 + AST 调用点锁）；

> ③ 卷轴「紧邻同素材连放」按收窄方案实现 = `plan_jianying_assets(drop_adjacent_duplicates)`

> 默认开（config `jianying_drop_adjacent_duplicates`），2mkv 64→63 条、宽度 815.75→791.75s、

> **并集覆盖 531.0s 不变**；机制更正：紧邻重复只在剪映卷轴出现（成片/EDL/XML 都是 0 对），

> 根因 = 取材扩宽 × 紧凑拼接，不是重排本身；④ ①③ 的 UI 接线完成（侧栏低内存徽标行 +

> 运行中 ≥120s 无新事件才提示"没有新进展"）。门禁 = 后端 **602** · API **122** · vitest **146** ·

> 双 typecheck + renderer build 绿。**r15 包不含 ②③④**（源码树 only ⇒ 进包要 r16 授权）。

> **续63 补三/补四**：两处新 UI 先做了真机目检（注入造态逐档读回，顺带抓到一个失效 CSS

> token `--c-warn`→`--warn`），随后**用户裁决把显示删掉** = 侧栏「内存」行与进度条黄字

> 心跳提示全部撤除（含 store computed 与对应 vitest 用例）。**保留**后端字段与 `types.ts`

> 契约镜像 ⇒ ①③ 定性为「能力在后端、界面不呈现」，是裁决不是欠账，别再当缺口登记。

## 续63 补六 — ⑥b 两级采样探针判负（2026-10-08 迁出）

> 来源：`.agent/STATE.md` Current Task 退休块，逐字未改。

> **▶ 2026-10-08（续63 补六）— ⑥b「两级采样」探针 = 判负关闭（成本实测成立 / 精度硬门崩）**
> 用户口令「3」= 六项立项唯一剩余项 ⑥，按 STATE 建议**只跑 b 且换判据**（主 = 建索引**实测**耗时；
> 硬门 = 三指标零回退）。沙盒纪律：`mvp/src` 一行未动 ⇒ 不接线、不 bump 生产 `feature_version`。
> **成本侧成立**：四片**同脚本双臂**实测 1fps 41.3min → 0.5fps 21.8min（比值 **0.529**，
> 区间 0.481~0.609），体积 ÷2；前案 13.6 帧/秒折算模型低估 2.3%~17.1%。
> **精度侧崩**：两片 59 条 = 严格 58→52、**导出实得 56→44**、场景 58→56、口袋 p30 回退 ⇒ 判负。
> **两片损害形态不同**（本批最有价值的发现）：test2 损在**证据层**（`no_evidence` 1→9、
> 切分并段 67→65 行）⇒ 严格直接掉 5；2mkv 损在**导出层**（严格只掉 1，但主 span 变宽/位移、
> 命中改由子 span 兜住 ⇒ 导出实得掉 6）。⇒ 10-03「grid2 零代价」包络**不足以支撑决策**：
> 它只扰动最终 span，看不见这两层（正是它 §6 边界 1 自己写明「不覆盖」的那一类）。
> **密验腿（⑥b 换形态本体）**：C05D 在 test2 上 **0 翻转、三指标与对照臂逐格相同、失败分布逐字
> 相同** ⇒ 精度救得回；但命中窗并集 = 源片 **33.4%**，补帧后 5055 帧 ≈ 1fps 的 5051 帧，墙钟
> 265+395=660s > 435s（**1.52×**）⇒ **「密验救回精度」的本质就是把网格补回 1fps，精度与成本
> 不可兼得**（盈亏线：帧数 cov≤33.3%、墙钟 cov≲12%，因密帧 seek 0.156s/帧 vs 顺序解码 0.105）。
> **逐图复核（用户点名）**：test2 3 张 9 行 + 2mkv 4 张 10 行全读；**第一版出图取格缺陷已修**
> （原用「重叠最大行的主 span」会取错格 ⇒ 改复刻评估器规则取「判档证据」span）。读图：test2 的
> 5 条翻转里 **3 条画面级真丢/错位**；C05D 的救回 2 条逐字同 span、2 条跨切点覆盖、1 条靠信封
> ⇒「零翻转」成立而**「逐帧等价」不成立**。
> **登记两条口径（未改判卷代码）**：① 1 秒级超短 GT 行的 `within` 通道可由**完全不与 GT 重叠**、
> 只落在 ±2s 信封内的 span 满足 ⇒ 引用「零回退」须带这句；② A10 与 10-03 基线批**逐行 mark 相同
> 但 strip 后逐字节不等**（`isc_l2_index_enabled` 10-05 才翻默认）⇒ 跨批引用 v2_* 只可用于三指标层。
> **⑥a/⑥c/⑥d 未跑**（本轮按口令只跑 b），保持「未跑」而非「已证否」，不得外推为探针族结案。
> 明细 `FINDINGS_TWO_STAGE_SAMPLING_20261008.md` + CHANGELOG 续63 补六（含 ISC 双数据根实况）。

## 续63 补七 — r16 出包（2026-10-08 迁出）

> 来源：`.agent/STATE.md` Current Task 退休块，逐字未改。

> **▶ 2026-10-08（续63 补七）— r16 出包：三件修复进包 + 全链包内验收绿**
> 口令「推ci然后打包吧」。已推 `aba3a21..654dd32`（6 笔，含 ⑥b 判负批）；macOS workflow 是
> dispatch-only，按既有搁置裁决**未**手动触发。
> 门禁（命令输出留证 `work/r16_gates.log`）= 后端 **606 OK(skipped=2)** · API **122 OK** ·
> vitest **144** · app/desktop **两个 config 分别** typecheck `rc=0`
> （首轮我误取 `tail` 的退出码 ⇒ 已重跑成 Python 硬取 returncode，不接受自报）。
> 包 = `mvp/ui/release/Video-Locator-win-x64-20261008r16.zip` = 981,659,900B / **7,078 条目** /
> `testzip()=None`；**zip 内** backend.exe 实测 77,469,132B `sha16=7c9533750776a79a`
> （r15 = 77,467,467B / `d45656f585826f4a` ⇒ 尺寸+摘要硬证，且与磁盘构建产物逐字节同）。
> 三件进包的**行为级**证据：① `accept_packaged_render.py` **R2「渲染走了隔离子进程」PASS**
> （这条对 r15 如实报红）+ R2b 未静默回落线程内；② 卷轴 **63 条**（r15 包 64）且包内日志出现
> `adjacent dedup (jianying)`；③ 进度链宽度属包日志侧观测，本轮未单独彩排。
> 验收全绿：bundle **FAILED=0**（冒烟 29.1s ≤75s · DirectML · 精排/ISC 未回退 CPU · 隔离子进程在跑 ·
> 子进程 INFO 进得到包内 · 未误判硬崩）· render **FAILED=0**（R1 completed 63s · R4 136.366 vs
> Σ136.344s · R5a 64 段紧邻 0 交叠 · R6 h264_amf）· 三防 **FAILED=0** ·
> `check_export_plan_invariants.py` **FAILED=0**（4 片 × 4 通道；2mkv 贴接 2 对→0、覆盖 Δ=0.00）·
> 启动冒烟 Electron 4 + backend 1 存活 30s、用完即清 `AFTER_KILL=0`。
> **r16 的包体靶子不抄档案**：新 `work/r16_pkg/expect_from_source.py` 用同一份 results 在源码树跑
> `export_project` 现算，并先断言「源码树数据根 vs 包内数据根」的 2.mkv 场景表基线全等
> （fv/preprocess_sha/帧数/scenes 行数/scenes 求和）⇒ 包体探针 `work/r16_pkg/probe.py` 只与它比：
> EDL 134.12s/64 事件/贴接 0 对、卷轴 63 条/56 文件/791.75s/531.0s、紧邻重复 1 对 13.0s
> ≤ 计划层认定的真实复用 487.25s、全原速、包内墙钟 97.4s ≤140s ⇒ **FAILED=0**。
> 分发包现状 = **r15（回滚）+ r16（现役）两份**（口令「只留r15和16」，2026-10-08 已删
> r13+r14，释放 ~1.96GB；删前两份留档均 `testzip=None` / 7,078 条目 / backend.exe 身份逐代核对）。

### 迁自 STATE.md `Current Task`（2026-10-08，续63 补十一 同批瘦身）

> **▶ 2026-10-08（续63 补八）— 进度链跳格独占实测 + 包内支持档文件侧闭合【下个对话从这里读起】**
> 用户裁决「先 1（真机自然运行复核）+ 埋点下一批」。三条产物：
> `mvp/scripts/review_progress_chain.py`（源码树记 on_progress 事件流，读数经产品自己的
> `map_progress_stage` + `ProgressDebouncer` 换算，与 `work/fixramp_run1_table.txt` 同列可比）、
> `mvp/scripts/review_packaged_support_log.py`（事后核真实支持档）、
> `work/name_probe/packaged_index_probe.py`（包内特殊文件名 + 隔离任务文件侧）。
>
> **进度链 test2 独占实测（locate 全程 1476.5s=24.6min，67 段）**：字牌腿 302.6→551.5s 共
> **249s / 10 个跳格 ⇒ 均值 24.9s、最大停留 41.6s**；ISC 腿 41 格最大 37.3s；全程最大 41.6s；
> 读数单调不回退；防抖合并 113→109 格（全是亚 0.5s 突发）且**未放大可见停留**（raw 41.6 =
> debounced 41.6）。对照：改前实测「字牌 363s 一动不动 / ISC 40~58s」⇒ **改善成立且量级 8.7×**。
> **但模型预测口径要更正**：`test_tasks.py:220` 那条 `step_s = 0.1/(1.7*32/48/67)*(363/67) = 32s`
> 算的是**均匀假设下的均值**，实测均值 24.9s 优于它，而用户感知的是**最大值 41.6s**（段间成本
> 不均，最坏单格 1.67× 均值）⇒ 超阈值 1.6s 不是"改善没生效"，是**锁的口径选错了**。
> 建议（待拍板，未动代码）：把该锁改成按实测最大值口径 + 登记 41.6s，**不**加宽字牌腿显示宽度
> （会挤占 patch/ISC，且 1.6s 不构成体验问题）。
> **测量卫生（本批踩过两次，已写进脚本 docstring）**：① 首跑我在重叠窗口里跑了包内探针（同块
> DML），字牌腿被抬到 52.8s ⇒ 整趟作废重跑，污染趟产物已删以防被误引；② 探针首版在任务
> completed 后 1s 就 terminate，把父进程 `isolated child reaped` 行自己切掉 = 假红，
> 改成等收割行出现（≤25s 宽限）再收。
>
> **支持档「文件侧」两条老欠账今天首次实测闭合**：① 打包态子进程 INFO 真进
> `video_locator.log`——完整链 `started(父) -> booted(子, 同 pid 同 task_id) -> 子进程 locate
> 内部 INFO -> reaped exitcode=0`（此前只在 stdout 断言过）；② 特殊文件名：支持档里
> 2026-08-27 两条 `index failed: Dune (2021).mkv / Interstellar (2014).mkv` 真因挖出 =
> 当年 ffprobe 命令被**手工加单引号**（Windows 不认单引号 => 收到带引号字面名），
> 现包内对 `Dune (2021) 沙丘 test.mp4` 建索引/回读 VALID/目录名 `...__dcadb7f3.idx` 全过
> （FAILED=0）=> 历史缺陷，已闭。
> **顺带捞出的产品级欠账（未动）**：真实支持档 492 条 ERROR 里 **485 条 = asyncio proactor
> `WinError 10054` 连接重置噪声**（客户端强关，非故障）=> 支持档信噪比 1.4%，客服看档会被
> 淹没；降噪（过滤该 callback 或降级）与「修复链腿边界埋点」同批做最合适。

> **包内真机复核已闭合（同批追加，`work/r16_pkg/packaged_cadence_probe.py`）**：轮询 UI 同一个读数源
> （`GET /api/tasks/{id}` 的 `progress`，服务端已过 `map_progress_stage`+防抖）量 test2 打包态跳格，
> **不需要等埋点**（埋点只影响售后事后能否查）。结果与源码树同口径几乎逐格对齐：
> 墙钟 **1407.5s vs 源码树 1476.5s（0.95x，无包体劣化）**、92→100 跳格 **54 vs 55**、
> 全程最大停留 **41.4s vs 41.6s**、字牌腿最大 41.4s / 均值 23.7s（源码树 41.6 / 24.9）、
> ISC 腿最大 **33.8s vs 37.3s**、结果段数 67 = 源码树一致、读数单调不回退。
> **C5 支持档文件侧隔离链在真实 25 分钟任务上完整**：父 `started` / 子 `booted`（同 task_id）/
> 子进程 `locate finished` INFO / `reaped exitcode=0` 全在 `video_locator.log` 里。FAILED=0（C1-C6）。
> 自纠一处：探针首版按 `(pct,stage,message)` 变化折叠采样，**消息换了而读数没换会被当成"动了"**
> => 低估可见冻结（首跑报 145 格）；已改成与源码树同的 **pct 变化**折叠并重出读数表。
> 分发包：已按口令删 r13+r14，留 **r16 现役 + r15 回滚**。本批未提交（等口令）。
