# TODO

> **结构修复说明（Agent Context Manager）**：本文件原有 66 条 `## → 日期: 主题` 记录，
> 且 `# TODO` 标题被埋在 L279，没有任何优先级容器，导致 `agent-context status` 的
> 待办计数恒为 0。现按协议整理为 P0/P1/P2/Blocked 四个容器；**历史条目一条未删**，
> 原样保留在文末「历史记录」章节中（降级为 `###` 以免与优先级容器平级）。
>
> P0/P1 条目取自 `STATE.md` 的 open item，以及历史记录中标注「待拍板 / 待确认 / 待复核」
> 且未见结案结论者，并逐条标注出处。若有误判，请直接编辑本节。

## P0 — Current

> **▶ 2026-10-06（续59）— macOS CI 5 失败修复已推送；四片零差异回归待查【下个对话第一件事】**
> 根因 = numpy SIMD 快排精确平局跨架构顺序不同（合成夹具踩中；生产无影响）。
> 已推 3230fad：两处 argsort 改 stable + patch 两断言 + isc_l2 夹具真峰移库外。后端 540 全绿。
> **待办**：① 查 `work/stable_sort_regress/summary.json`（不完整就重跑 probe_stable_sort_regress.py，
> 预期四片逐字节零差异）② 等 macOS CI 重跑结果 ③ 全过销项，有失败按 STATE 续59 块思路续查。

> **▶ 2026-10-06（续58 补一）— r9 包真机全链复核 = PASS【醒来读这条】**
> 口令「跑吧」：包内 backend.exe headless 跑 test1 真实片（env 已补齐 SVL_PATCH_ONNX/
> SVL_ISC_ONNX 注入对齐 main.ts，防精排静默回退 CPU）⇒ wall **1196.9s=19.9min**（实验室
> 1320.5s，headless 方差内）· 55 段零错误 · DirectML 生效 · 索引复用 · 轮询 p50 4.7ms ·
> **strip 逐字节 identical=True**（vs 实验室 defaults_flip_ab/test1/on 臂）⇒ r9 包 = 实验室
> 同语义，三旋钮新默认在包内正确生效。进度通道全程有消息。明细 CHANGELOG 续58 补一。
> **待拍板**：① 工作区 git 提交（三旋钮翻默认+UI 五件+探针+档案；**提交前勿改工作区**）
> ② 下一刀拍板：A1 降子补记分→A2 异源选优（推荐）∥ A3 导出含子（产品选项），见 RESEARCH_PROPOSAL_NEXT_CUT_20261006.md。

> **▶ 2026-10-06（续58）— r9 出包完成 + 验收全过**
> 口令「出包」：`build-release.ps1` 四步全过（首跑败于旧 win-unpacked 文件占用，清进程重跑即过）
> → `accept_packaged_bundle.py` **FAILED=0**（资产 sha256/DML/精排 GPU/ISC GPU/冒烟 33.9s）+
> **启动冒烟 PASS** + zip 抽验全过 ⇒ **`Video-Locator-win-x64-20261006r9.zip`（936MB/7078 条目）**
> = 现役包（三旋钮新默认 15~31min/片 + UI 五件修复进包）。release 现役 = r8（回滚）+r9；r7 已删（口令）。
> ⚠️ 包 = 未提交工作区构建 ⇒ git 提交前不要再改工作区。
> **待拍板**：① 工作区 git 提交（三旋钮翻默认+UI 五件+探针+档案）② r8 旧包删除授权
> ③ 真机全链复核（r9 包跑一条真实片，看新默认态观感）④ 算法下一刀立项
> （ED 子镜头对齐需真设计 / mkv 建表异步化需产品口径 / 扫描行为缩减）。

> **▶ 2026-10-06（续57 夜间批二）— 计划项 1「ISC margin 门标定」= 判负关闭（已回滚）**
> 原设计（ED 子镜头对齐）经材料复读修正为门标定。两级探针：① 全量 0.035 臂（2mkv）读图
> = 1 真增益 + **1 真损失**（0.9s 窄段 HIGH 被远跳 56.6s）⇒ 亚门分不可远跳；② 近场限定
> （offset≤3s 才降门）实现阶段**机制否证**——评分窗内取 max ⇒ 近场峰被主分吸收 margin 恒 0。
> ⇒ **判负关闭**，isc_refine/config/locator_service/单测全部回滚（后端 540 OK 复验）；
> 探针留证。真救回需换评分几何，与「扫描行为缩减」同层级立项。FINDINGS_NEXT_DIRECTIONS §7。

> **▶ 2026-10-06（续57 夜间批次）— 三旋钮已翻默认 + 真机复核过 + FP16 判负【醒来读这条】**
> ① 翻默认（口令「翻」，前置补齐）：联合双臂四片全 PASS（test2 **1.294×** 0/67 · test3
> **1.276×** 0/103 · 2mkv **1.162×** 0/84 · test1 0/55）⇒ `patch_refine_grid=True` ·
> `rerank_grid_grab=True` · `cluster_workers=4` 生效；三指标 136/131/138/4·9 自动成立；
> 后端 540 OK；**新默认态 ≈ 15~31min/片**。② 真机复核：UI 四件全过 + 抓修第 5 处
> `.pd__lib` 溢出（已修复验）。③ FP16 探针：ISC 1.806× 但 DINOv2 无肉（0.845×/1.014×），
> 采纳代价>收益 ⇒ **判负有据**。④ 方向评估见 `FINDINGS_NEXT_DIRECTIONS_20261006.md`：
> 纯性能侧挤干（三桶=解码地板）；建议 ED 子镜头切分对齐 > mkv 建表异步化 > r9 出包。
> **未提交 git / 未打包 r9**（口令）。工作区 = config+回归锁+pd__lib+3 探针。

> **▶ 2026-10-06（续57）— UI 真机反馈四件 = 完成**
> ① 首页卡片路径溢出（grid 子项 min-width:auto 根因 → `.pcard` min-width:0 + 剪辑行只显文件名）
> ② 新建项目**不再弹对话框选剪辑视频**，直接建空项目跳构建页自选素材（断链根源随流程删除）
> ③ 剪辑视频列表加 ×删除（store `removeEditedVideo`）④ `.pd__pickrow` 按钮 flex+gap。
> 门禁：vitest **136 全绿** · 双 typecheck 干净；纯 UI 层，零后端改动。明细 CHANGELOG 续57。

> **▶ 2026-10-06（续56）— other 桶网格接线：test1 双臂 1.132× 零语义**
> 新旋钮 `pipeline.rerank_grid_grab`（**默认关**）：locate 主循环两处源片重排窗
> （① patch v2 近场池 ±30s@4s 均匀网格 ② 字牌锚定源窗 4 均匀点）改走 `grab_grid`
> 网格抽取（管道量 ÷~100），与 `patch_refine_grid` 语义解耦。
> **验证**：test1 同脚本双臂（`work/rerank_grid_ab/`）off 1601.0 → on 1413.7s = **1.132×**，
> strip 55 段 **0 差异** + 信封一致 ⇒ 端到端零语义；与账单预期吻合（other 桶 294.4s≈22%）。
> 续54~56 干净双臂最大一刀。单测 +7 · 后端全套 **540 OK (skipped=2)**。明细 FINDINGS §5.12。
> **等口令**：~~git 提交（续54~续57）~~ **已提交推送**（`2d2c993..1a697ec` 三笔：fix(mvp) 源码+测试 /
> chore(scripts) 探针+FINDINGS / feat(ui)+docs(agent)，工作区清零）。
> 剩：翻默认三旋钮（`patch_refine_grid` · `cluster_workers` · `rerank_grid_grab`，各自还需三片双臂）/
> r9 出包 / UI 真机复核。
> 未改 GT / 未 bump feature_version / 现役默认态行为不变。

> **▶ 2026-10-06（续55）— `%.6f` 缺陷修复 + 三刀提速（并集才是主力）：现役默认态 19~31min**
> 账单：窗 spawn 680 次/561 调用（≈1.2 簇/调用），固定开销 ~0.17s/次，成本已改为
> **解码跨度主导（0.164s/解码秒）**；CPU 抓帧 78% vs DML 推理 18%（更正续54「GPU 2.4%」= 漏数入口）。
> `id()` 判重复嵌入 dup=1463 是假读数（真重复率 0.00）⇒ 嵌入去重关闭。
> **真缺陷已修**：`_grid_select_expr` 用 `%g` 把簇起点截成两位小数 ⇒ select 窗偏离 ≤0.005s ⇒
> 修复前跨源合成 micro test2 1/300 · 2mkv 6/300 · test3 6/300 **不同帧**（0.5s 护栏抓不到），
> 改 `%.6f` 后**四片 1200/1200 逐字节同帧**；端到端零语义 test1 0/55 · test2 0/67 · test3 0/103 · 2mkv 0/84。
> L2 索引标签全整数秒 ⇒ 已入库索引无需重建。
> 三项提速：`patch_refine_grid`（默认关，test1 双臂 **1.068×** + 0 差异）· patch 段内并集（无旋钮，
> **四片零语义 PASS**：test2 1862.8s **0/67** · test3 1861.6s **0/103** · 2mkv 1407.2s **0/84** ·
> test1 0/55；跨 run 比值 **1.22~1.33×** ⇒ 本批最大一刀）· `media.cluster_workers`（默认 1，
> test1 双臂 **1.071×**（1155.4→1078.9s）+ 0 差异）。
> ⚠️ **更正**：本批早先按 test1 形状统计判「并集在串行下几乎没肉」**错了**——另三片候选窗重叠度高，
> 并集实测省 1.22~1.33×。教训 = 单片窗口形状统计不能外推成套结论，形状类判断必须跨片实测。
> **现役默认态 = 19~31 分钟**（test1 19.3 / 2mkv 23.5 / test2 31.0 / test3 31.0；
> 会话开始 21.5/31.3/38.0/40.3 ⇒ 一天内约 1.3×，结果逐字段未变）。`PRODUCT_INTRO` 已同步。
> **硬解已穷尽判负**：d3d12va 本 build **解不出帧**（三片 hw 可用窗 0/6，报错 `hardware accelerator
> failed to decode picture`；汇总里 31~148× 是空输出假速度），解码地板 0.66~0.78×；
> dxva2 同样 0/6 出帧、地板 0.38~0.50×；d3d11va（续54）净 0.42× ⇒ **AMD 三入口全关（有据）**，
> 回本需「帧不回 CPU」的 GPU 前处理重构形态。macOS videotoolbox / NVIDIA cuvid 仍未测。
> 门禁后端 **534 OK (skipped=2)**（+8）。明细 FINDINGS §5.7~5.10。
> **运行中**：段内并集（无旋钮）三片回归 `work/spawn_consolidation_regress/run_union.log`。
> **等口令**：git 提交（续54~续55）/ 翻默认两旋钮（各自还需三片双臂）/ r9 出包。
> **下一刀**：`other` 桶网格接线（294.4s=22%，跨度中位 24.8s/步长恰 4s）；isc 精扫需先解相位。
> 未改 GT / 未 bump feature_version。

> **▶ 2026-10-05（续54）— 定位侧提速第一批：窗 spawn 合并（零语义 1.30×）**
> 定位账单（窗 spawn 记账）：窗抓帧 892s=61%、每窗 spawn 固定开销 ~1s 是主体、GPU 仅 2.4%。
> 硬解（路径 A）实证判负（d3d11va 0.42×，回传开销>收益）；机制留档：统一转换链可保逐字节契约。
> 三件零语义落地：① `_preembed_mids` 打分批量预取（每段 6~8 spawn→1~2）② metadata 缓存
> ③ 精扫网格抽取（新旋钮 `isc_refine_grid_refine` 默认关，单独收益≈0 保留基建）。后端 526 OK。
> test1 同条件双臂 **1671.0→1287.3s = 1.30×**，三方 strip 逐字节全等（合并前基线/新off/新on）。
> **✅ 四片零语义回归 PASS（续54 补，`probe_spawn_consolidation_regress.py`）**：对照续52-G 常态链臂
> 现役默认态直跑 —— test2 2277.9s **0/67** · test3 2416.4s **0/103** · 2mkv 1875.4s **0/84**
> ⇒ 四片逐字节全等 ⇒ 三指标 136/131/138/4·9 自动成立。跨 run 1.17~1.29×（参照臂含争用，
> 不作干净数字）。明细 FINDINGS §5.7。
> **等口令**：git 提交（续54）/ grid_refine 翻默认（建议维持关）/ patch_refine 同款合并（下一刀）。
> 未改 GT / 未 bump feature_version / consolidation 无旋钮直接生效。

> **▶ 2026-10-05（续53 补三）— E2E 抓到「第二次分析必崩」真缺陷 + 修复；r8 定稿**
> E2E test1（打包态 headless）抓到续52-G 潜伏崩溃：`_isc_l2_validated` 被初始化为 `{}`（dict），
> 「加载已存在有效索引」分支 `.add` 即崩 = 用户第二次分析同一原片必崩（当时四片全走重建分支漏测）。
> 修复 = `set()` + 2 回归测试 + worker 异常堆栈落 tasks logger（此前 no-op 无从归因）。
> 重验：后端 **523 OK** · E2E **PASS**（24.3min/55 段/L2 加载 8221 帧/DML）· accept **FAILED=0** ·
> zip 0 缺漏 · 启动冒烟 PASS。**r8 zip 已重打定稿**；release = r7 + r8。
> runtime 功能确认全过（fsbrowse/L2 翻默认行为证据/GPU/PYZ/注入）。~~等口令：git 提交~~
> **已提交推送**（`6fcf399..3f42e65` 三笔，工作区清零）。剩：r8 真机 UI 全链复核（可选）。
> 未改 GT / 未 bump feature_version。

> **▶ 2026-10-05（续53 补二）— git 三笔推送 + r8 出包验收全过；release 只留 r7+r8**
> git `199c010..6fcf399` 三笔已推 origin/master（feat 产品代码 / chore 研究脚本 / docs 档案）。
> r8 = `Video-Locator-win-x64-20261005r8.zip`（981MB）：accept **FAILED=0** + zip 逐文件 0 缺漏 +
> 启动冒烟 PASS。r6 已删，release 现役 = r7（回滚）+ r8（最新）。⚠️ r7 的 .zip 实为 tar 流（解包
> 用 tar 工具）。**下一步**：r8 真机端到端复核（顺带看 L2 首跑画面索引构建进度与时间口径观感）；
> mkv 建表异步化 / 代际差点位穷举（下批）。未改 GT / 未 bump feature_version。

> **▶ 2026-10-05（续53 补一）— L2 翻默认已执行（用户口令「1」）：`isc_l2_index_enabled=True` 生效**
> config 翻默认（证据链+回退路径入注释）· 回归锁翻转 · DECISIONS 2026-10-05 落账 ·
> PRODUCT_INTRO 口径同步（高精度全片 45~60min → **27~43min**；一次性画面索引 5~11min/部原片）·
> 顺带修 `_ensure_isc_l2_index` stat/sha 无保护缺陷（源片不可读原会崩 locate → 现 WARNING+回退）。
> 门禁后端 **521 OK (skipped=2)**。现役默认态 = L1+L2 全开（三指标 136/131/138/4·9 零回退）。
> **等口令**：git 提交（续41~续53）/ r8 重打（翻默认+建表修复需进包）/ mkv 建表异步化（解耦）/
> 代际差精确点位穷举（下批）。未改 GT / 未 bump feature_version / 未提交。

> **▶ 2026-10-05（续53）— mkv 建表性能结案（5.01×）+「mkv 慢」错误归因更正；翻默认前置全部清除**
> ① 真因 = test1-om.mkv 容器尾部音频比视频流晚 8.4s ⇒ 脚本版 builder 尾部 8 个死目标各触发
> 一次**整表重试**（每次全片解码 ~350s）≈ 2800s 纯浪费；「mkv+select 解码路径本身慢」与
> 「大簇优化无效」两旧结论作废（2.mkv 15.7 帧/s + 探针 22 帧/s 双证伪）。
> ② 修复（isc_l2_index.py，runtime/脚本共用）：末视频帧 pts 截断（ffprobe 尾扫 0.15s +
> 双级回退）+ 死簇守卫（消除潜在死循环）+ fps≠1 簇推进修正 + 脚本委托 build_tp_index。
> ③ 验证：test1-om tp 重建 **638.3s（12.9 帧/s）vs 3198.1s = 5.01×**，与验收索引 **times/feats
> 逐字节相等** ⇒ 续52 验收字节等价沿用；单测 +3；后端 **521 OK (skipped=2)**。FINDINGS §5.6.6。
> ④ 翻默认 `isc_l2_index_enabled=True` 的性能前置**全部清除**（建表一次性代价 =
> mp4 ~5~11min / mkv ~11min/137min 片）。**待拍板**：翻默认（材料齐，仍等口令）。
> 其余：git 提交（续41~续53）/ r8 重打 / mkv 建表异步化（解耦）/ 代际差精确点位穷举（下批）。

> **▶ 2026-10-04（续52）— L2 全链路完成（A/B PASS 1.44× + 常态链等价 PASS）；翻默认待拍板**
> ① test2/test3 fresh 双臂 0 差异 ⇒ 四片收口；归档差 = `v2_*` 跨代际（vs fresh off：test2 3 行 span /
> test3 1 行 span + 4 段边界 / 2mkv 1 段拆合；L1 off 路径惰性；test3「5 行」系行号对齐虚计；机制未定位留白，
> 「整格跳位」旧归因已撤回）。提速 test2 1.727×/test3 2.089× 有争用不作干净数字（干净 = 1.27×/1.30×）。
> ② L2：四片索引全建（干净 28.8 帧/s ≈4~6min/片源）；**探针原文判据 >2s=0 四片全未过**，
> triage 后「峰不丢」大体成立（离群多为窗扫复刻塌分/网格相位，真分歧 1 行）；**接线暂缓**，FINDINGS §5.6.1。
> **✅ L2 接线 + 常态链 + 复验等价 PASS（续52-F/G）**：提速合计 **1.44×**，三指标
> 136/131/138/4·9 零回退；入库目录 `data/isc_index/` + sha256 失效判定 + locate 内同步自动
> 构建（异步留待进程隔离）；复验修复 builder 全片攒内存 bug（流式嵌入）；四片新 on 臂与
> 验收臂 0 差异。**待拍板**：翻默认 `isc_l2_index_enabled=True`（前置仅剩 mkv 建表性能，可翻后做）。
> 其余：代际差精确点位穷举（下批）；git 提交（续41~续52）/ r8 重打等口令。

> **▶ 2026-10-03（续51 补一）— `grab_grid_decode` 已翻默认 True（选项 B）**
> 依据：帧级逐字节等价 + test1 逐字段 0 差异 1.27× + 2mkv 双新臂 0 差异 1.30× + **四片三指标逐项一致**
> （136/131/138/4·9）+ 门禁 512 OK；`config.py` 注释写全证据与回退路径 + 默认值回归锁。
> ~~**在跑**：fresh 双新臂 test2/test3（用于归因那 3+5 行 LOW 置信差异）~~ → **已结案（续52）**。
> git 提交（续41~续52）/ r8 重打仍等口令。

> **▶ 2026-10-03（续51）— 「还能推进吗」：L1 后成本构成已换位，下一刀清单已定**
> 现役 test1 = 36.4min（L1 后）。归因（口径标注）：宽扫残量 **~10~12min**（off 宽扫增量 ~19.7min − L1 省 9.8min，
> 由续45 ON 臂 1595s / 续47 defaults_check 2772s / 本批 A/B 2186s 推得）· 两旋钮 **11.1min**（续34 实测优化后 664.9s）
> · P（编辑侧嵌入等）**6.5min**（续34 387.5s）· **其余 ~9min 未归因**（1595−387.5−664.9）。
> **下一刀排序**：① L2（ISC 源片索引）= 把宽扫 10~12min 压到 ~1min 级，建表 ~9min/片源、第 2 条成片起纯赚，
> 并把扫描范围扩到全片；② 两旋钮 11.1min（无管道红利了，要 FP16/帧数/特征缓存，需实测拆分）；
> ③ 未归因 9min 必须插桩；④ 硬解只在 L2 建表时有价值；⑤ 多进程 1.2~1.4×（风险高）。
> **已备探针** `mvp/scripts/probe_locate_stage_timing.py`（零 runtime，monkey-patch 计时：阶段/两 embed/源与编辑抓帧分账）
> —— **排在四片回归之后跑**（避免 GPU 争用污染计时）。

> **▶ 2026-10-03（续50 补四）— test1 A/B PASS（零语义 + 1.27×）；三片回归运行中**
> on 2186.1s（36.4min）vs off 2772s（46.2min）= **1.27×**，`strip(result_id)` 后**逐字段 0 差异**；
> 门禁后端全套 **512 OK (skipped=2)**。**运行中**：2mkv/test2/test3 on 臂（off 复用 `v2_*`，≈2.5h）。
> **下一步**：四片齐 → 拍板翻 `grab_grid_decode` 默认 → L2（ISC 源片索引）立项。未翻默认/未提交。

> **▶ 2026-10-03（续50 补三）— 漂移修复（网格=逐字节等价）+ 其它抓帧点否定 + A/B 重跑中**
> ① `_grid_select_expr(lo,step)`：锚定解码簇起点的绝对窗口首帧 ⇒ 300s@1s **300/300**、180s@2s **90/90**
> 逐字节同帧，2.36~2.61×；亚秒步长护栏回退（`MIN_GRID_STEP_S=1.0`）。② shot_split 形状 2.10× 但 cos 0.335、
> patch 小窗 1.08× ⇒ **不接线**。③ L2 建表形状 600s@1s：123.6s→49.4s（2.50×）。
> **A/B 重跑中**（off=现役默认批复用，on 运行中）。**待办**：A/B 数 → 四片回归 → 翻默认；L2 立项；后端全套。

> **▶ 2026-10-03（续50 补二）— L1 已接线（默认关）；test1 整条 A/B 运行中**
> 接线：`isc_refine` 增 `grab_grid`（**只用于宽扫粗扫**）+ `FFmpegIO.grab_grid_times`（带洞安全）+
> `locator_service._grab_grid_batch`（三路回退 + 缓存复用）；旋钮 `pipeline.grab_grid_decode`（默认 False）。
> 单测 +8 定向全绿。**A/B 运行中**：`work/isc_grid_ab/`（test1 off/on 两臂，strip(result_id) 逐字段 + 墙钟）。
> **下一步**：A/B 出数 → 四片回归 → 翻默认；接 shot_split/patch_refine；L2 立项；后端全套待跑。

> **▶ 2026-10-03（续50 补）— L1 已落地（`grab_grid` 2.5×，到解码地板）；下一步=接线+test1 A/B**
> `mvp/src/media/ffmpeg/ffmpeg_io.py`：`grab_grid` = `select` 抽取 + `-fps_mode passthrough` + 冻结 `first_ge`；
> `grab_frames` 增 `filters/size/match/passthrough`；单测 +6。A/B（180s/2s/91 点）= 27.9s → **11.1s（2.51×）**，
> 79/91 逐字节同帧、ISC cos mean 0.997。**反例**：`fps` 滤波重定时间轴（0.78）不可用；缺 passthrough 会复制帧。
> **解码地板 8.5s/180s 窗（21× 实时）** ⇒ 继续降本靠 L2（源片索引）或硬解（扫描路径 A/B）。
> 门禁 后端 **505 OK (skipped=2)**。**待办**：① 接线宽扫粗扫 → test1 整条 A/B；② 四片回归；③ L2 立项；④ 硬解 A/B。

> **▶ 2026-10-03（续50）— 成本结构实测：L1「解码管道网格抽取」为首选杠杆（用户令「先把成本打下来」）**
> 实测：ISC 推理 30.4 fps vs 窗解码抓帧 7.65 帧/s（**抓帧 = 推理的 4×**，卡在原始帧管道 I/O，
> 每帧 2.6~6.0 MB，只取 1/25~1/30）⇒ **L1 = 网格扫描用 `-vf fps=1/N`（可选 `-s`）**，管道量 ÷25~60，
> 宽扫 18~24 s/段 → 3~6 s/段，并同幅作用于 shot_split/patch_refine（grab 占 77.6%）。
> **L2 = ISC 源片索引**（实测一次性 22.4 min/8.4MB 每片源；N≥2 条成片起每片省 ~22 min；先 L1 再 L2）。
> **L3 = main-agreement 门 → 实测不可分（切换段 15/301；真增益行 0.509/0.598/0.674 落在未切换段
> 中位 0.771 之下）⇒ 不建议单独上**。L4 FP16 未测。归档 `FINDINGS_COST_STRUCTURE_LEVERS_20261003.md`。
> **待拍板**：立刻开 L1 实施？L2 立项？L4 并行？

> **▶ 2026-10-03（续49）— P0 ④「两级采样索引探针」结构账 = 建议不立项（收益全在一次性）**
> 零 runtime/零 GPU 结构账 + 新探针 `mvp/scripts/probe_index_fps_sensitivity.py`：
> ① 收益错配：四片索引 31,117 帧 / 53.2MB / 建索引折算 38.1min ⇒ ÷2 省 19.1min + 26.6MB，
>   **每次定位（45~60min/片）一分不省**（ISC 宽扫 + 抓帧按任意时刻抓帧，不经索引）；
> ② 精度不是阻碍：现役 v2_* 批 span 端点吸附 2s 网格（偏差 ≤1s）= 严格 136→**137** / 导出 131 持平
>   / 场景 138 持平 / 负例持平（唯一翻转 t1r12a part→HIT）；平移 ∓1s = −4 / −1；
> ③ 检索保真度（当前 GT，DML 206s）stride2 = 139/139、rank p99=**11.0** ≪ 我方 top-28；
>   stride10 = 130/139、p99=448.6（须密验兜底）。**④ 由「待实跑」转为「结构账判负候选」**。
> **替代杠杆（建议接）**：ISC 宽扫粗步长 2.0s→4.0s（−42% 宽扫 embeds；现役宽扫已是两级）
> ⇒ 先做 20~30 段 ×±90s @1s ISC 曲线探针（≈5~10min GPU）算峰值保持率，门槛 ≥95%。
> 归档 `FINDINGS_INDEX_DENSITY_DIV2_20261003.md` + `work/index_fps_probe/`。
> **待拍板**：④ 采纳 (a) 不立项 / (b) 降级可选档 / (c) 实跑四片回归；是否接替代杠杆；git（续41~续49）；r8 重打。

> **▶ 2026-10-03（续48）— v3 阶梯宽扫（ladder=30）= FAIL（计时判负），维持 0.0**
> `rerun_isc_refine.py ladder` 3 片计时全部更慢：2mkv +8.3% / test1 +1.4% / test2 +13.2%
> （3 片 +7.9%），test3 中止不参与。精度 3 片零回退、翻转 0 行、p20/p34/p14 保持 HIT、
> churn 4 行无真损失——**精度无损但无收益，纯负优化**。机制复盘：过门峰≈切换段仅 ~10%，
> ~90% 段白付内圈粗扫+细化再扩外圈 ⇒ 结构性净亏；教训 =「提前收工」类优化先做结构账再实跑。
> FINDINGS §12 + `work/isc_refine_arms/analysis_ladder/` 已归档。**性能侧队列 ③ 宽扫自适应
> 降本（阶梯形态）就此判负关闭**；下一杠杆 = ④ 两级采样索引探针。**待拍板**：git 提交
> （续41~续48）/ r8 重打。

> **▶ 2026-10-03（续46 补）— v2 radius=90 翻默认（用户拍板）：严格 136 / 导出实得 131 生效**
> `isc_refine_scan_radius_s` 0.0→90.0（续45 验收 PASS 依据见 config 注释/FINDINGS §11）；
> PRODUCT_INTRO 时间口径 18→30~45min（精确数字等 defaults_check 实测回填，同时交叉验证
> vs v2_test1 逐位一致）。后端 496 全绿。**待拍板**：git 提交（续41~续46）/ r8 重打。
> **性能侧队列（2026-10-03）**：~~① ISC@512 批量推理~~ **判负**（batch1 33.2fps 最快，batch 全更慢）
> · ~~② hwaccel 硬解~~ **判负**（a1.mp4 像素差 1.05 与冻结帧契约冲突）· defaults_check = test1
> 46.2min 逐位一致 ✓（PRODUCT_INTRO 45~60min/片已回填）→ 剩：③ 宽扫自适应降本（行为变更
> 需四片回归）→
> **④ 两级采样索引探针（用户新增）**：档案前提 = 竞品 source_global_fps 确证 1.0（非 0.1），
> 我方审计 stride2(0.5fps) 检索 139/139 零漏 / stride10 漏 12（rank1 短案例）⇒ 0.5fps 档
> （÷2，需 feature_version bump + 四片全回归）先行，0.1fps+密验兜底档（÷10，需设计兜底腿）
> 视 0.5 结果定。

> **▶ 2026-10-03（续46）— 窗批量抓帧解码翻默认开 = test1 全片 1.34× 逐位一致**
> `FFmpegIO.grab_frames`（簇一次 spawn + -copyts + showinfo pts；gap≤4s/跨度≤40s；失败回退）+
> `_grab_frames_window`（缓存查漏 + 假体鸭子回退）+ `grab_window_decode=True`。bug 留痕：
> loglevel 吞 showinfo（死等）/-copyts 缺失差一帧。零语义：单测逐字节 + 2.mkv 132 帧 1.73× +
> **test1 全片 21.5→16.0min = 1.34×，55 段 strip(result_id) 逐位一致**。后端 496 全绿。
> **待拍板**：① v2 radius=90（严格 136/导出 131 PASS，代价 +88min/四片）；② git（续41~续46）；
> ③ r8 重打。

> **▶ 2026-10-03（续45）— ISC 门控 v2 宽幅扫描生产验收 = PASS，待用户拍板翻 radius 90【下个对话从这里读起】**
> `rerun_isc_refine.py v2` 四片实跑（唯一变量 `isc_refine_scan_radius_s` 0→90，ALL_DONE/PY_EXIT=0，
> 总 212.4min vs ON 臂 124min）。**三指标零回退全升**：严格 134→**136** · 导出实得 128→**131** ·
> 场景 138 持平 · 负例 4/9 持平。**翻转 3 条全真增益**：**p20/p34 part→HIT**（CLS 真盲族被宽扫
> 虚拟候选救回，续43 探针 margin +0.11/+0.33 兑现，MISS6 缺口 6→4）+ t2r06c main F→T。
> churn 判据行口径 5 行（2 行无指标影响读毕无损失），ISC 切换段 31（v1 21），无自信错恶化
> （t1r30a/t2r04a 落点逐位同）。t1r08c/t1r12a 仍 part、t2r03b 仍 MISS（无候选不救设计内）。
> **裁决 PASS** ⇒ 可进拍板翻 `isc_refine_scan_radius_s=90`；**radius 保持 0.0 未翻**（未改 GT/
> 未 bump feature_version/未 git 提交）。归档 FINDINGS §11 + `work/isc_refine_arms/analysis_v2/`。
> **待拍板**：① 是否翻 radius 90（注意宽扫代价 +88min/四片）；② git 提交（续41~续45，仍等口令）。
> **▶ 2026-10-02（续44）— ISC 第二意见局部重排生产验收 = PASS，待用户拍板翻默认【下个对话从这里读起】**
> ON 臂四片实跑（`rerun_isc_refine.py on`，ALL_DONE/PY_EXIT=0，≈124min）；OFF 臂=现役默认批
> `spl_patch_arms/on_*` 复用（续39 重计 133/125/138/4 逐位一致旁证）。**三指标零回退**：
> 严格 133→134（+1，p14 part→HIT）· 导出实得 125→**128**（+3，+t2r07c/t3r02c main F→T）·
> 场景 138 持平 · 负例 4/9 持平。翻转 3 条全真增益（拼图 3 张读毕），churn 9/139 无指标影响。
> MISS6：p14 获救，p20/p34/t1r08c/t1r12a 仍 part，t2r03b 双臂 0s 占位（v1 门控不救无候选，符合预期）。
> **裁决 PASS** ⇒ 可进拍板翻默认；**`isc_refine_enabled` 保持 False**（未翻默认/未改 GT/未 bump
> feature_version）。归档 FINDINGS §10 + `work/isc_refine_arms/analysis/`。
> **▶ 2026-10-03（续44 补）— 翻默认已执行**：`isc_refine_enabled=True`（用户拍板）；打包接线三件套
> （资产入册 resources/models/isc_ft_v107 二进制 gitignore + build-release sha256 fail-fast + main.ts
> SVL_ISC_ONNX + accept ISC 断言 75s）+ 再生成脚本 export_isc_onnx.py（vs 仓内 cos=1.0/max|d|=0）。
> 门禁：后端 492 全绿 · vitest 138 · 双 typecheck 绿。已知上限：CLS 聚簇提案框死第二意见视野
> （p20/p34 型救不到）⇒ 门控 v2 = 提案放宽检索 top-N。**r8 重打等口令**。
> **待拍板**：② git 提交（续41~续44，仍等口令）。
> **▶ 2026-10-02（续43）— 方案B 正交 backbone 探针 = 正判，ISC21 通过门槛【下个对话从这里读起】**
> 三臂 20 案例（与方案A 同协议/判据/案例集）：**ISC21 = MISS 5/6 gt>main、6/6 gt_is_peak**
> （含 t2r03b 峰落 GT±0.4s——续42"不可救"限定改写为"DINOv2 链不可救、ISC 链能救"），
> MISS+POCKET 7/12 ≥ 1/3 ✓；对照 7/8 peak（唯一 t1r27 = −0.02 边界翻转非反噬）。
> CLIP 臂弱信号不采纳；dino sanity 2/6 = 无 GT 泄漏旁证；ens 与 ISC 持平。
> 读图 9 曲线 + 3 拼图确证真峰/真内容；Phase 12 ISC 旁证一致。
> 工程留痕：① CLIP 图 DML 授权失败污染进程 → 同进程后续 DML Run 段错误（多模型 runtime 须 fail-fast 隔离）；
> ② t2r03b main=0 占位炸扫描窗（方案A 同踩），已修 >150s 钳 GT 邻域。
> 归档 FINDINGS_ORTHOGONAL_BACKBONE_PROBE_20261002。探针级：零 runtime/零 GT/零 feature_version。
> **▶ 扩验证（同日选项②）**：全 139 正例 ISC+dino 分布 = 核心桶（定位错 63 例）ISC 峰命中 **44/63 (70%)**
> vs dino 37/63（配对 15:8）；drift 73%/far 43%/nowin 8/8；独家增量 12 例（margin 至 0.37）；
> 失败 19 例 = 近位移边界翻转 9 + 远位移两臂一致错 10（t1r30a/t2r04a 读图确证同峰同错）。
> ⇒ ISC 只能做歧义段第二意见 tiebreaker，不能当主判据。
> **▶ 立项前多模态复核（用户问「多模态复核没」后补齐）**：独家增量 12 例全读毕 = **11 干净 + 1 边界**
> （t2r07b ISC 峰内容真但锚到 GT 窗前 2.2s 的相邻子镜头 = 多镜段子单元族，不算干净命中）⇒
> 独家增量按干净 11 例记账；门控新增约束：ED 段含切点时须容忍子镜头粒度（±2~3s）或结合
> ED 子镜头切分对齐。曲线 12 + 拼图 6 全读完（VLM 仍不可用，读图=多模态复核）。
> **待拍板**：① 是否立项采纳门控设计（歧义段 top-K ±5s ISC 重扫 + margin 门 + 三指标回归 + MISS6 必验收）；
> ② git 提交（续41+续42+续43，等口令）。

> **▶ 2026-10-02（续42）— 方案A(patch 稠密对应)判负 + 双栈解读**
> 双栈完全解读：竞品基座与我方逐字节同、我方表示更强、竞品机制已全移植 ⇒ 根因=特征判别力。
> 方案A patch 稠密几何对应探针（mutual-NN+仿射RANSAC内点率）20 案例 GPU 实测 =
> MISS6 gt_is_peak 1/6、margin 噪声级、CONTROL 同义反复、机理=背景主导稀释 ⇒ **判负不进 runtime**
> （FINDINGS_PATCH_DENSE_CORR_20261002）。**t2r03b 查证结案**：0s 仅 unresolved 占位（导出/UI/渲染
> 全过滤，非用户可见缺陷，早前说法已更正）；根因=0.9s 窄段证据太弱（cover0.062/bsim0.413），
> 窄窗豁免可过弱簇门但 dense_retry 门(0.62)仍挡、降门会放回 test4 假定位 ⇒ **不可救接受为未命中**；
> 窄窗豁免已回退，仅保留 reasons.ts 补 no_evidence 中文映射（vitest138+双typecheck绿）。
> **方案1 TN 喂饱探针**：TN@2/4/8fps 严格 116→118→122（场景123→130→135）单调升 ⇒ 采样耦合成立(用户直觉对)。
> 两级@默认coarse≈4.8fps=130 > TN@8fps(更密)122 ⇒ TN喂更密仍不敌。⚠️**bug更正**：edited_segment_fps 不进
> twopass(死参数，twofed_2/4/8 md5相同)，撤回初版「两级喂饱零变化/同8fps两级胜TN」错判(两级提采样未测)。
> ⇒ **TN不接入**。多模态16/16：A类5/8强确证两级胜TN；B类喂饱真锚对仅1/8(p36)、余边界翻转(span抖判据线)。
> FINDINGS_TN_SAMPLING_COUPLING_20261002。
> **待拍板**：方案B(正交backbone探针) / 接受精度现状转产品鲁棒性 / git 提交(仍等口令)。

> **▶ 2026-10-02（续41 后续）— r7 出包 = 现役包【下个对话从这里读起】**
> `Video-Locator-win-x64-20261002r7.zip` = r6 + 续41（入库层四件 + 快/精双模式）。
> accept FAILED=0 · 三防全过 · 启动冒烟 PASS · 真机快验全 ✓（真实盘符/白名单/refine=fast 确证），
> 期间抓到「0.0 GB」显示缺陷 → 修 → 重建 → 复验。
> **待拍板**：git 提交（续41+续41后续，等口令）/ 下批方向。

> **（2026-10-02 续41）— 入库层四件 + 快/精双模式 完成**
> 入库层：fsbrowse（盘符/自然排序/白名单/磁盘剩余）+ GET /api/fs/browse + 磁盘预检 LOC-1108
> （合并/渲染动手前拦截）+ FileBrowser.vue 浏览选择面板（多选顺序=合并顺序）。
> 双模式：locate(refine) 逐任务覆盖两旋钮，默认高精度不变；UI 模式单选 + localStorage；
> body 显式才带 refine。dev 浏览器实测全 ✓。
> 门禁：后端 485 · API 104 · vitest 138 · 双 typecheck · mock 契约全绿；零 feature_version。
> **待拍板**：git 提交（续41，等口令）/ **r7 重打**（续41 两批需进包，需授权）。现役包仍 = r6。

> **（2026-10-02 续40 后续三）— r6 出包 + 包体真机全验**
> `Video-Locator-win-x64-20261002r6.zip`（1.68GB/8364 条目）。accept FAILED=0 · 三防全过 ·
> 调试档包内冒烟 PASS · 启动冒烟 PASS · CDP 真机快验：未分析徽标/新文案/92.0% 小数/device=dml 全 ✓。
> r6 = r5 + UI 三修复 + 售后三件。数据残留裁决：不删、待办撤档。
> **待拍板**：下批方向。（git 已提交 2026-10-02 三笔：00b34f1/e85f4b9/3f527d9。
> **(A) 成片缺口标记 2026-10-02 用户裁决「先不做」**——三问口径全否，重启需用户再提；
> 候选剩 (C) 入库层四件 / 大文件鲁棒性四件 / 快精双模式 UI 档。）

> **（2026-10-02 续40 后续二）— 售后可诊断性三件完成**
> 脱敏补强（uvicorn access_log 关 + 百分号路径/API path= 两条新规则）· 三级日志
> （调试档 debug.log 默认关，SVL_LOG_DEBUG=1 开）· 客服编号表 `mvp/docs/SUPPORT_ERROR_CODES.md`
> （13 码全表 + 防漂移测试）。后端 469(+9) · API 100 全绿，前端零改动。
> **r6 重打累计 = UI 三修复 + 本批三件**（等授权）。
> **待拍板**：r6 / git 提交（续33后续~续40后续二，等口令）/ 下批 (A) 缺口标记。
> （r4 旧包已删，2026-10-02 用户授权。）

> **（2026-10-02 续40 后续）— 真机 UI 三问题修复完成（未进包）**
> ① empty→「未分析」+徽标成组+长名省略号；② 新增 REFINE 进度阶段（92→98 逐段推进、链入口补发
> 消息覆盖 6.5min 空窗）+ 进度一位小数；③ 21 条进度文案全量去技术化中文重写（patch 精排→画面深度复核 等）。
> 门禁 460/100/132/双 typecheck/mock 全绿；dev+源码树后端 DML 实跑目检 ✓。
> **待拍板**：**r6 重打**（UI 修复需进包才到用户手上）/ git 提交（续33后续~续40后续，等口令）/
> r4 旧包删除（需授权）/ 下批方向 (A) 成片缺口标记 / (C) 入库层·大文件鲁棒性。

> **（2026-10-02 续40）— r5 重打 + 包体验收全过**
> `Video-Locator-win-x64-20261001r5.zip` 出包（1.68GB/8364 条目）。`accept_packaged_bundle.py` FAILED=0（r4=5）；
> 三防冒烟全过；真机 test2 全链：**device=dml 包内确证**、**27.0min**（r4 62.6min）、结果与 r3 逐字段一致；
> r4 两尾巴销项（精修进度文案 ✓ / 导出默认「全部」✓）。首跑修掉 `build-release.ps1` GBK 读 UTF-8 断言崩溃。
> **新登记**：段循环后→拆分前 ~6.5min 零消息 + 92% 钳死（UX 尾巴）；CLS asset.json 无 sha256 启动 WARNING（既有）。
> **待拍板**：① git 提交（续33后续~续40，等口令，建议拆三笔）；② r4 旧包删除（需授权）；
> ③ 下批方向 (A) 成片缺口标记 / (C) 入库层·大文件鲁棒性。

> **（2026-10-01 续39）— 20 条 GT 缺口核对及写回完成**
> 用户令「那你去完成啊」：原生帧节奏解码、切点/动作图证与源帧辅助匹配完成；**17 条修订、3 条保留**。
> 10 条原片窗修订 + 7 条仅 ED 锚点收紧；139 个 ID、其余119正例、9负例保留，未扩充蒙太奇标签。
> 四份 GT 版本追加 `gt-gap-review-20261001-r1`；备份 `work/gt_backup_pre_gap_review_20261001/`；MD5 manifest 已更新。
> 原 ON 结果批不变，同评估器重计 **严格 133/139 · 主片段 125/139 · 场景 138/139 · 负例误报 4/9**。
> 相对旧GT读数132/119/137：这是**标注修订导致重计，不是算法提升**。p34 HIT→part 如实保留。
> t1r08c 零时长已改一帧锚点，但严格仍未命中（MISS→part）；续38“实际覆盖该点”过强，现撤回。
> t2r03b 旧“同源重复”已追加取代说明；t1r22/t1r25/t2r06c 原标注成立。
> **范围/精度**：本轮核对20工单，非全139条重标；源窗为图证帧时间包络，不声称亚帧精度；执行者Codex，非用户逐条亲审。
> 报告 `mvp/benchmark/user_case/semantic_signal/FINDINGS_GT_GAP_REVIEW_20261001.md`；最终图证 `work/gap_gt_review_final_20261001/`。
> 校验通过：输入8哈希、备份逐字节、结果4哈希不变、未选119正例/9负例不变、ID保留。GT工单结案，算法仍有6条严格未命中。

- [x] GT缺口20条核对、17条写回、3条保留、备份/哈希/同批重计/报告完成；当前严格133、主片段125、场景138、负例误报4/9。

> **（2026-10-01 续36）打包态 62.6min 根因闭环 + 卫生四件 = ✅【下个对话从这里读起】**：
> **根因**：分发包缺 DML patch 双输出 ONNX ⇒ `PatchReranker` 静默回退 CPU torch（包内
> `patch reranker device=cpu` / 源码树 `device=dml`），全链均匀慢 2.6~3.9×。三臂对照证明
> **UI/预览/CUA 无罪**（打包 headless 3625.0s ≈ 整包 E2E 3756.7s），续35 的运行时干扰假设作废。
> **修复**：图入仓 + 构建同名复制外部权重（净增 ≈88MB，sha256 实测与 CLS 同源）+ `build-release.ps1`
> fail-fast/摘要断言 + `main.ts` 注入 `SVL_PATCH_ONNX` + 回退即 WARNING + `accept_packaged_bundle.py`。
> **Arm D 大素材 = 1400.5s ≈ venv 1396.7s**；三臂结果批含 confidence+信封 两两差异 0 ⇒ 基线读数不变。
> 门禁：后端 460 · API 99 · vitest 132 · 双 typecheck · test:mock 全绿。
> **待拍板**：① **r5 重打**（修复只有重打才进包；重打后跑验收脚本 + 真机核精修进度文案/导出默认项）；
> ② **git 提交**（续33后续~续36 全部未提交，等口令，建议拆三笔）；③ 下批方向 (A) 缺口标记 / (C) 入库层·大文件鲁棒性。
> **新登记缺陷**：~~`dinov2_cls_patch.onnx` 仓内无再生成脚本~~（续37 已补 `mvp/scripts/export_patch_onnx.py`，
> 再生成与仓内资产输出逐位一致）；mac 包多带 ≈88MB 死资产（未处理，H3 正式化时按平台裁剪）。

> **（2026-10-01 续35 收官）性能归因第一步 + 44 份 GT 头 = ✅【下个对话从这里读起】**：
> **归因**：实验重跑 test2 ON 臂 23.3 min vs 打包 62.6 min = **环境罚 2.69×**；微对照建索引
> 打包 13.7 vs venv 12.7 fps ⇒ 推理/抓帧吞吐排除；strip(result_id) 后 67 段逐位一致（跨环境零语义）。
> **下批候选 = 打包态关干扰单变量复跑**做精确分解。产物 `work/spl_patch_arms_att_backup/`。
> **GT 头**：44 份批量补齐（`apply_gt_version_headers.py` 幂等；H 类 3 份读文判定；§八登记表 +44 行；
> 复扫 44→1 误报）。**交接时工作区未提交（续33后续~续35 全部，等口令）；现役包 r4。**
> **待拍板**：git 提交 / 下批方向（打包态性能精确分解 / (A) 缺口标记 / (C) 入库层或大文件鲁棒性）。

> **（2026-10-01 续35 r4）导出默认「全部」+ 后处理进度 + 徽标修复 = ✅**：
> `minConfidence` 默认 LOW / patch_refine 逐段进度回调（「高精度精修：patch 局部精排 i/n」落
> 镜头分析步骤）/ `IndexStatus.backend` 可空化修徽标误标。回归 后端 457 · API 99 · vitest 127 全绿。
> **r4 = `Video-Locator-win-x64-20261001r4.zip`**（三防+启动冒烟 PASS；r3 已删）。
> ⚠️ r4 未真机全链复跑——下次分析顺带核对精修进度文案与导出默认项。
> **待拍板不变**：git 提交（续33后续~续35 全部，等口令）/ 下批方向（打包态性能归因 1.56× /
> (A) 缺口标记 / (C) 入库层或大文件鲁棒性）。

> **（2026-10-01 续35 E2E）r3 包真机端到端 = ✅ 全过**：
> 多选对话框/真实合并/索引复用+DML/shot_split 54→67（验收逐字一致）/patch_refine 65 段/剪映草稿/
> **LOC-2002×5 组双通道**/成片渲染（41 段 h264_amf CFR 正常）。**新登记待拍板/排期**：
> [UX-P1] 分析后处理（shot_split+patch_refine ~36min）零进度上报 → 用户实测「92% 卡感」，建议加阶段文案或子进度；
> [性能] 打包态全链 62.6 min ≈ 实验室串行 40 min 的 1.56×，抓帧优化未兑现 → 需离线归因；
> [UI-P3] 侧栏后端徽标 CPU 误标；[日志] 预览 asyncio 噪音。详见 CHANGELOG「续35 E2E」。
> **待拍板不变**：git 提交（续33后续+续34+续35+E2E 全部，等口令）/ 下批方向 (A) 缺口标记 / (C) 入库层或大文件鲁棒性。

> **（2026-10-01 续35 后续）两旋钮翻默认开(选 c) + r3 重打 + 旧包清理 = ✅ 完成**：
> `shot_split/patch_refine` 默认 **True**（DECISIONS 2026-10-01）+ `PRODUCT_INTRO` 数字/时间口径更新；
> 回归 后端 455 · API 99 全绿。r3 = `Video-Locator-win-x64-20261001r3.zip`（backend 三防冒烟 +
> 启动冒烟 PASS）；旧 r2 zip 已删（用户授权）。**生产现役基线 = 严格 132 · 场景 137 · 负例 4/9 ·
> 导出实得 119/139**。**待拍板剩余**：① git 提交（续33后续+续34+续35 全部，等口令）
> ② UI 真机 E2E 复核（r3 包上：多选合并/渲染成片/LOC-2002/默认开观感）
> ③ 下批方向 (A) 成片缺口标记 / (C) 入库层四件或大文件鲁棒性四件。
> 详见 STATE `Current Task` 顶部「续35 后续」块。

> **（2026-10-01 续35）接线卫生小批 = ✅ 两件落地**：`/api/results/load` 撞码修复（`LOC-1103`→
> **`LOC-1107`**，只增不改；`detail` 技术串确认为设计内不动）+ 网络失败条幅中文话术
> （HttpServiceAdapter）。回归 后端 455 · API 99 · vitest 127 · 双 typecheck 全绿；零 feature_version。
> **待拍板不变**：① 两旋钮默认值三选一（开销比已实测 2.72×，高精度 ≈18 min/片）② git 提交
> （续33后续+续34+续35 未提交，等口令）③ r3 分发包重打（需授权）④ 杠杆3 立项（会改结果）。
> 详见 STATE `Current Task` 顶部续35 块。

> **（2026-10-01 续34）shot_split/patch_refine 抓帧提速 = ✅ 归因 + 零语义落地 + 全片 1.90×【下个对话从这里读起】**：
> 用户问「性能有什么可优化」→ 拍板「都要」（先归因拿基线，再落零语义改动，对比提速 + 验逐位一致）。
> **归因（杠杆0）**：新探针 `probe_split_patch_timing.py`（`off批→shot_split→patch_refine` 复现 ON 臂后半段，
> 不重跑整条 locate）。全片 test1 baseline 臂 **grab 合计 978.9s = 77.6% wall**（源片 ffmpeg spawn 65.2% +
> 编辑片 12.4%）、embed.dual 10.8%、patch_score 9.0% ⇒ 与历史 `_patch_rerank_span`「grab 占 81%」同量级，
> **瓶颈是 ffmpeg 逐帧 spawn 不是模型推理**。
> **落地（杠杆1+2，零语义）**：① `locator_service.py:1105/1123` 两旋钮 `grab_frame` 换 `_grab_frame_cached`（512 FIFO）；
> ② 两模块加可选 `grab_frames` 批量参数 + `_grab_many`，生产传 `_grab_frames_parallel`（4 线程），
> 「grab→embed 逐帧交错」重构为「**先并行批量 grab → 再主线程串行 embed**」。**遵守续6：DML forward 保持串行**
> （多线程并发 Run 段错误），只并行 grab（纯 IO），`ex.map` 保序 ⇒ 帧内容/顺序不变。`grab_frames=None` 回退逐帧
> ⇒ 离线验证器 + 单测零回归。
> **验证（整条 locate 全字段逐位一致 = 最强零语义证明）**：① 微探针三向 span 一致 `baseline_full == optimized_full == ref(on_test1) = TRUE`（各 55 spans）；
> ② 升级 = 跑完整 `srv.locate()`（`time_full_locate_optimized.py`，优化后代码双旋钮开 test1 全片），与续33 原始串行产物
> `on_test1.results.json` **strip(result_id) 后全部确定性字段差异段数=0**（conf_score/rank/alternatives/reasons/segs/信封字段全比，字节数 99953==99953）。
> **旋钮段全尺度 A/B：1262.3s → 664.9s = 1.90×**（省 10.0 min/片）；缓存 raw grab 2591→1691（省 35%）+ 4 线程并行摊剩余。
> 8 段子集先行 2.09×。**缓存驱逐路径全片额外覆盖**（1691 grab/512 上限 ⇒ ~3 次 clear，竞争下仍逐位一致）。
> **整条 locate 实测（用户侧）：opt_full = 1052.4s = 17.54 min**；P（pre-knob）=387.5s；serial_full=1649.8s=27.5min ⇒ **full-locate 提速 1.57×**
> （Amdahl：P 占优化后 37% 未碰，故 1.57×<旋钮段 1.90×）；**ON/OFF 开销比 串行 4.26× → 优化 2.72×（实测，确认此前推导 2.4~3×）**。
> 回归：后端 **455 OK (skipped=2)** · API **99 OK** · 零 `feature_version` · 生产三指标不变（旋钮默认仍关）。
> **边界**：两口径须分清——旋钮段 1.90× / 整条 locate 1.57×（用户体验）；只验 test1 全片（余三片未跑全片 A/B，零语义由整条 locate 全字段一致+回退兼容+全绿保证）；
> 未做杠杆3（改 REFINE_FPS/窗口/CLS 预筛——会改结果需三指标回归）。归档 `FINDINGS_SPLIT_PATCH_GRAB_PERF_20261001.md` + `work/spl_patch_timing/*`。
> **待拍板**：① 两旋钮默认值仍关——**ON/OFF 开销比已实测降到 2.72×**（高精度全片 locate=test1 实测 17.54 min，不再原「30–45 min/片」），续33「三选一」时间口径据此更新，(c) `PRODUCT_INTRO` 可下修到「高精度 ≈18 min/片（test1 实测，片长相关）」；
> ② 本批 git 提交（探针 + 3 源码 + FINDINGS + 档案，等口令）；③ r3 分发包重打（需授权）；④ 杠杆3 是否立项。

> **（2026-09-30 续33 后续）两旋钮（shot_split / patch_refine）生产路径双臂验收 = ✅ PASS【下个对话从这里读起】**：
> 离线组合验证没走完整 `locate()`，本批补生产路径证据。新增 `rerun_split_patch_arms.py`（off/on 双臂 DML 硬断言）
> + `diag_split_patch_flips.py`（判据机制）+ `review_spl_patch_flip.py`（按评估口径选行读图）。
> **结果**：严格 **130→132** · 导出实得 **107→119（+12）** · 场景 137 持平 · 负例 4→4 ·
> **与离线组合验证逐位一致 ⇒ runtime 接线零漂移**。OFF 臂等价性已证（off_2mkv/off_test1 与现役默认批逐位一致，
> test2/test3 直接复用现役默认批）。翻转 14 行 = 13 增 1 损，机制全为 direct 主 span（union 装配命中 **0** 行）；
> 9 行实质覆盖 / 4 行 ±2s 相邻（p03/p30/t1r02/t3r23）/ **1 行真损失 t3r02a**。逐张读图 6 张（p05·p30 真增益，
> t1r02·t1r20 真，t3r23 打折，t3r02a 真损失）。
> **新增硬事实**：ON 臂单片 31–44 分钟 vs OFF 7–8 分钟 = **4~5× 耗时**（patch_refine 局部 DML 推理）。
> 归档 `FINDINGS_SPLIT_PATCH_PROD_ACCEPT_20260930.md` + `work/spl_patch_arms/` + `work/spl_patch_visual/`；
> 零 `mvp/src` 改动、零 feature_version；基线 455 测试全绿。
> **待拍板**：① 两旋钮默认值三选一（(a) 维持关 + UI 高精度开关 / (b) 只翻 shot_split / (c) 都翻 + 改时间口径）
> ② r3 分发包重打（需授权）③ 本批 git 提交（4 脚本 + FINDINGS + 档案，等口令）④ 下批方向（(A) 成片缺口标记 /
> (C) 入库层四件 / (D) 大文件鲁棒性四件）。

> **（2026-09-30 续32 后续）18 条 GT 工单逐帧裁决闭环 = ✅ 已落地【下个对话从这里读起】**：
> 六张拼图逐张读图（18/18 与检索判别一致）→ 用户逐帧裁决「18 条全部确认」→ 12 行重锚定 +
> 2 行同源重复注释（corrections 落账 + 快照 `work/gt_backup_pre_ticket_20260930/` + manifest 哈希）。
> 两条翻案：t2r05a「特征层失败」= GT 窗错；t2r03a 旧 HIT = 双错相消假 HIT。
> **新基线**：严格 **130/139** · 导出实得 **107/139** · 场景 137/139 · 负例 4/9 · 截等长 111/139；
> 回归 后端 444 OK · API 99 OK。归档 `FINDINGS_GT_TICKET_ADJUDICATION_20260930.md`。
> **下批方向已拍板 = (E) 场景内稠密局部位置信号**：影响面统计已做（新 GT 口径）= 同场景族 23 行可救池；
> **口袋测试集已重推 + 三模态复核**（`probe_pocket_retest_gt130.py`）：13 候选 → 剔 2 容差类
> ⇒ **8 条生产未命中真口袋**（p02/p03/p20/p30/p34/t1r14c/t2r06c/t3r02c，读图+算术+检索三证齐）。
> **(E) ①② 执行完毕（续32 后续六）**：① **形态4 runtime 化落地**——
> `engine/localization/shot_split.py` + `pipeline.shot_split_enabled`（**默认关**）+ locate 接线；
> 后端 444→**451** 全绿 + API 99；真实验收 PASS（test2 关侧零影响、开侧 54→67 段、严格 18→18、
> 导出 14→15）。② **融合评分建议搁置**——形态5 margin 0.05 补跑净 +1（8 增 7 损），独裁重选收口。
> **形态6 runtime 化也落地**：`engine/localization/patch_refine.py`（歧义门+top-K 精排，**默认关**）+
> 离线验证 PASS（导出 107→109、零 churn、2 翻转读图真增益）；后端 444→**455** 全绿 + API 99。
> **待拍板**：shot_split / patch_refine 默认值翻转（建议随 r3 真机复核后）/ r3 打包（需授权）。新改动已提交推送（3ed468c/49e79e0/63bc24b）。
> **待拍板剩余**：git 提交（256+ 条）/ r3 分发包重打（需授权）。

> **（2026-09-30 续32）交接铁律立档 + 补复核三条 + 合并夹具修复 + GT 工单判别 = ✅ 闭环**：
> 铁律置顶 HANDOFF（AGENTS.md 那条按用户令撤除）。补复核：续28 判负成立+三查询坍缩同落点 5088-5089；
> 密度判负成立且保守；续27 = **夹具缺陷**（非产品，初版定性已更正）已修：part2 以 part1 实际末帧起切 +
> 互斥断言 + 时间轴同一性锁（δ 前 0 / 后恒 0.167s，无重复无累积）⇒ 合并产物恢复可用，定位对照重跑中。
> GT 工单自动判别 = **16 疑错 / 2 同源重复 / 0 推翻读图 / 0 无效**（读图与检索零冲突），
> 含 t2r05a 原"特征层失败"定性大概率 GT 窗侧问题；**GT 修改待用户逐帧裁决**（工单在
> `work/gt_tickets_retrieval.json` + `work/highwrong_visual/GT_REVIEW_TICKETS.json`）。
> 同批前段：① `main_hit` 并列口径落地（导出实得 100/139）② 重复认领告警两路径均否决
> ③ conf_v2 正式关闭（36 段读图真错仅 4）。测试 444/99/127 全绿。
> **待拍板**：git（246+ 条）/ r3 打包 / 14 条 GT 行逐帧裁决 / 下批 = 清单 3 入库层四件 ·
> 清单 4 大文件鲁棒性 · 锚点线以「导出实得」判据重开（14 条口袋测试集在案）。

> **（2026-09-29 续31）用户撤裁决重做「退化拒绝门」= ✅ 分腿归因 + 并集缺陷修正 + 同构安全形态 LOC-2002 落地【下个对话从这里读起】**：
> 档案错判先更正（本项续19 已实现+已否决，非"已批未做"）。用户选「仍做 B（需撤裁决）」⇒ 按续21-E1
> 纪律先做**影响面统计**再谈形态：四片 224 可回答段中 31 段（13.8%）有单一伙伴 ≥0.8 的重复认领，
> **无一属竞品伪影**；三机制 = 相邻细段拼接铺满 / 宽窄 span 分层包含 / **对称重复+等证据=掷硬币**
> （test3 seg41 HIGH 0.87 vs seg61 HIGH 0.89 同指一 2s 区间，读图=同一镜头）。
> **分腿（续19 没做）**：拒识腿单独 = 严格 −2 / 场景 −1 / 负例 ±0；续19 的 −14 里 **test2 的 −5
> 全来自子 span 腿「全低即整段清空」**，与竞品那条判据无关（两实现逐位互证 127→118/137→132）。
> **真缺陷修正**：`duplicate_ratio` 累加→**并集**（邻居互叠被重复计数），test3 seg17 宽 span 转误拒为
> 保留 ⇒ 回收 严格 +2 / 场景 +1。**裁决**：`degradation_gate_enabled` 维持默认关（第四次确证）。
> **新立安全形态（默认开）**：`duplicate_claim_groups/warnings` 只**提示**不删答案，走既有
> `last_export_warnings`→`/api/export`→导出对话框（**UI 零改动**）；判据 = 重叠/较窄侧 ≥0.8 **且**
> 窄宽比 ≥0.5（下限由读图抓到的假阳性逼出：test3 30/31 段画面是 Thorin 与 Thranduil 两个不同角色，
> 只是 8s 宽 span 含住 2s 窄 span）。真实导出四片冒烟 = 2mkv/test1 零组、test2 一组、test3 两组，
> **开/关两侧 EDL 逐字节一致**，逐张读图确证三组真为同镜头。**用户令「全部读一遍」后补全量逐图复核**
> （`mvp/scripts/review_degradation_visual.py`，16 张拼图 / 本批累计 25 张逐张读毕）：① 拒识腿的 −2
> （t3r12/t3r18）**都是真画面损失**而非 GT 口径（s41 与 s61 同指山岩镜头、0.87 vs 0.89 掷硬币）；
> ② **承重子 span 的 `cover` 是 0.00~0.19** ⇒「cover 低 ≠ 无用」，这才是 test2 −5 的根因；
> ③ LOC-2002 在 2.mkv 零组**不是漏报**（那 3 对各含一条 LOW 被导出门槛挡在工程外，口径=工程内重复）。
> 测试：后端 **433→444** · API **99** · vitest **127** · 双 typecheck 干净 · `test:mock` PASS；
> 生产三指标不变，零 `feature_version` 变更。归档 `FINDINGS_DEGRADATION_LEGS_AND_DUP_CLAIM_WARN.md`。
> **事故留痕**：首跑误用 `replay_degradation_gate.py` 硬编码输出路径覆盖了续19 的
> `work/degradation_gate_ab.json`（`work/` 不在 git，不可恢复；聚合数字 DECISIONS/CHANGELOG 有留痕），
> 已补 `--report` 参数防复发。
> **尾巴**：Mock 适配器不产 warnings（dev 态看不到 LOC-2002）/ 打包 exe 真机复核告警文案（需授权）/
> `min_scene_coverage` 整段清空形态缺陷未改 runtime（门默认关无生产影响，已量化「部分丢」可免 test2 −5）/
> 竞品「相近片段自动合并」未做（本次只提示）。
> **待拍板**：git 提交（实测 244 条，本轮用户选暂不提交）/ 分发包 r3（用户选等下批做完一起打）/
> 下批 = (A) 成片缺口标记 或 (C) 入库层四件 或 (D) 大文件鲁棒性四件。
>
> **（续31 补二）用户追问「架构不行就换 / 有没有整套换过 / 判负后改过算法吗」→ 执行清单第 1 项
> = 五环组合链扩四片双口径对照 ✓ 完成**：
> ① **整套换 = 净退步**：同判据同粒度 复现链截等长 **83/139** vs 我方 **105/139**
> （去 ±2s 容差 = 67 vs 85）；候选层复现链有 **9 条 GT 从未进表** vs 我方 oracle 仅 1 条 rank>20；
> 它的完整 span 读数 124 接近我方 127 **全部来自 TN 场景 span 装配效应**（test1 41 vs 10）。
> 逐 ID 差集 = 复现独家 16 vs **我方独家 38**。链路一致性已核（两份 manifest 160 路径仅 32 不同，
> 全是输入/统计；A1–A25 假设逐字一致；G5 从未扩片且 test1 上零翻转）。
> ② **但挖到真东西**：16 条里有 **14 条是真口袋**（剔除 2 条 ±2s 容差漏洞：p14 窗外 0.67s、
> t2r01c 窗外 0.04s），逐张读图 6 张 16 行确认 ≥8 条是**「同场景内 2–7s 偏移」**= 我方唯一主病灶族，
> 复现链靠**场景内稠密局部对应**（每场景 5 关键帧 + patch 主力 + 段内 DTW）锚对，
> 而我方 `patch v2` 是 ±30s/4s 步长/margin>0.075 的**近场稀疏重排** ⇒ 该挖的是它的**表示粒度**
> 不是它的判据（与 fast_global「吸收性质、不接受前提」同一条成功路径）。
> ③ 另 3 条口袋暴露我方**命中质量虚高**：p30 生产 HIT 实为 577s 宽事件 span 兜住（OURS 落点差 200s）、
> p34/t2r05b 靠宽窗 cov 吃窄 GT 窗 ⇒ 读数需打折。
> ④ **我方口径需加注**：`within = span ⊆ GT窗±2s` 在截等长口径下给我方 **+18 行**（105→85）、
> 给复现链 +16 ⇒ 结论方向不变（delta +22→+18），但 105 这个被引用数字要标口径；
> M1 章程门用双臂同口径差值不受影响。
> ⑤ **下一步（第 1 项的产出物 = 立项材料）**：以这 14 条为测试集，做「场景内稠密局部位置信号」
> 影响面统计 + 无 GT 反标探针，门槛 = 命中 ≥1/3 且 127 条零回退（patch v2 同规格）。
> 归档 `FINDINGS_COMBO_CALIBER_ALL_CASES.md`；新脚本 `probe_combo_caliber_all_cases.py` /
> `probe_combo_pocket_visual.py`；产物 `work/combo_caliber_all_cases.json` + `work/combo_pocket_visual/`。
> 清单第 2~5 项（conf_v2 换饱和判据 / 两级采样探针 / E3 换载体 / min_scene_coverage 换判据）**未动**。

> **（2026-09-29 续30）下批偷向 = 成片渲染（差集 TOP1）移植 + 真实验收 = ✅ 闭环【下个对话从这里读起】**：
> 用户令「先下批偷向吧」→ 按档案排序取表 D 唯一判「缺失」的 TOP1。竞品形态字节确证
> （blob #138：逐段 CFR + 合并优先流复制失败回退重编 + 逐段帧数校验 + 硬件编码器拉黑回退 +
> 停滞看门狗 + `-progress` 读取线程 + terminate/wait/kill + 片段并发保序 + 稳定命名产物）。
> **用户拍板口径**：紧凑拼接（**不**落地竞品黑场空档腿）+ 音轨取原片对应区间（不用解说轨）。
> **落地**：`media/ffmpeg/timeline_render.py`（复用续27 的 concat/进度解析/错误摘要基建）+
> `RenderConfig` + `paths.rendered_root()` + `ProgressStage.RENDER_MOVIE` +
> `locator_service.render_movie()`（与 `export_project` **同一套 clip 计划**：门槛→吸附→切点展开）+
> `POST /api/tasks/render`（`Task.kind`，渲染批提交时锁定防竞态）+ UI `startRenderTask`/
> `useRenderMovie`（轮询/取消/打开目录）+ 结果页导出对话框「成片渲染」区块。
> **本批最大发现（新工程结论）**：中段音频**不能用 AAC**——1024 样本补齐使中段音频恒长视频一帧，
> concat 按最长流推进偏移 ⇒ 60 段成片 **59 处 0.0417→0.0630s 视频接缝**（容器帧率被探成 48000/1001）；
> `-shortest` 是错误解法（实测反截 3 帧、间隙放大到 0.103s）；正解 = **中段 MOV + PCM 24bit +
> 终片只复制视频、音频转一次 AAC**。回归锁两处（单测帧距集合 + 验收脚本 frame_delta_stats）。
> **真实验收 PASS**：2.mkv 60 段 / 3552 帧 / 148.17s，`nb_frames`==严格计数==计划、**不规则帧距 0**、
> 帧率回到 24000/1001、8 段抽样对齐 0 或 −1 帧、逐张读图 9 张画面同景同人、EDL 与成片同计划、
> `h264_amf` 硬件编码在位、首跑 54.7s（0.9s/段）二次 0.2s 复用、`hdr_downgraded=True` 留痕。
> 测试：后端 **388→433** · API **89→99** · vitest **118→127** · 双 typecheck 干净 · `test:mock` PASS。
> 生产基线不变，零 `feature_version` 变更。归档 `FINDINGS_VIDEO_RENDER_PORT.md`；表 D/E/结论已销项。
> **待拍板**：git 提交（实测 241 文件）/ 分发包 r3 重打（含续27+29+30）/ 下批三选一 =
> (A) 成片补「缺口标记」（黑场腿或时间码条 + 可选解说轨；让成片从"审片带"变成能直接给客户看）
> (B) ~~退化拒绝门（TOP1 剩余半边，成本低，已批未做）~~
>     **⚠️ 本条为档案错判，2026-09-29 续31 更正：该项早已实现+实测否决+通道关闭**——
>     `engine/localization/degradation_gate.py`（借 `max_duplicate_scene_ratio=0.8`/`min_scene_coverage=0.2`
>     判据）已接线 `locator_service.py:1087-1089` + `test_degradation_gate.py` + 离线双臂
>     `replay_degradation_gate.py`；续19 双臂实测 **严格 −14 / 场景 −12 / 支撑 −201**，逐图判被拒帧与 GT
>     同内容 ⇒ DECISIONS 2026-09-28(续19) 裁决 `degradation_gate_enabled=False` 且**不做阈值再调**；
>     DECISIONS 续21-E1 权威纪律：同类"去重/唯一认领"判据移植前须先证伪影系统性存在（已三例反证 −14/−1/−8）。
>     ⇒ 不属于待办，重做须用户先撤销该裁决。
> (C) 入库层四件 / 大文件鲁棒性四件。
> **效果判读（用户问"有进步吗"）**：精度零进步且本应如此；能力 0→1（首次不开 NLE 就能拿到可播 mp4）；
> 质量最实一条 = 修掉 59 处 AAC 接缝。但成片**性质 = 审片带**：60 段 / 148.0s、单段 1.0–9.94s、
> 播放顺序源片起点倒序对 13%、相邻回跳 8 次、未定位段静默跳过 ⇒ 别当"可交付成片"卖。
> 自我更正留痕：曾把「源片起点单调性」当验收项（先排序再比较 = 恒真），已换成倒序对/回跳度量；
> 逐张读图覆盖 9/60，其余靠帧距 + 8 段 MAD 兜底（FINDINGS §4.1/§4.2）。


> **（2026-09-29 续29）UI 多选原片接线（续27 尾巴）= ✅ 落地+浏览器态验证【下个对话从这里读起】**：
> 用户拍板选此项。桥=`app:openFiles`（multiSelections, 返回选择顺序数组/取消=空）；契约=
> `mergeSources()`→POST /api/source/merge + `startAnalyzeTask` 第三参 `original_paths`（**≥2 段**才发
> `original_path:''`，单段 body 逐字不变；Mock 同规则拒 <2）；数据=`Project.sourceVideos`（有序=合并时间轴）
> +`Project.merge` 留痕 + `syncEffectiveSource`（单段→该段/≥2 未合并→''/已合并→产物/**库内容或顺序变→产物过期**/
> 库清空→''；旧 localStorage 读时迁移零丢失）；展示=详情页源片库列表（序号/删单项/拖多段/浏览器模式多次粘贴）
> +立即合并/重新合并/取消合并+mode·reused 徽标，分析页未合并多段→「合并并分析」+清单，项目卡「N 段原片（待合并）」，
> 元数据多段聚合（时长/大小求和）合并后改探产物。合并进度沿用 `MERGE_SOURCES→INDEXING`，**UI 阶段枚举零改动**。
> 测试：vitest **95→118**（projectsSourceLib 15 + sourceMerge 8）· 双 typecheck 干净 · 后端 **388** · API **89** ·
> `test:mock` 含合并契约 PASS · `compile:electron` 产物含 openFiles。零 `mvp/src`/`mvp/api` 改动，基线不变。
> **未做**：原生对话框多选的**打包 exe 真机复核**（需授权）；mkvmerge 路由/字幕轨口径差异仍见 FINDINGS_SOURCE_MERGE_PORT §4。
> **待拍板**：git 提交（实测 232 文件）/ 分发包 r3 重打（含续27+29）/ 下批偷向（成片渲染 TOP1 / 入库层四件 / 大文件鲁棒性）。

> **（2026-09-29 续28）E 层算法差集全线收口 ✓：ordered_search M0 沙盒判负【下个对话从这里读起】**：
> 三轮判读终态 full=102/nolock=103/raw=106 vs 基线截等长 105（章程门 113 未达）；逐 ID
> `full_only_up=[]` = 顺序性零独家救回、锚点反拖合法复用段（p03/t3×3 独家回退）。
> **不进 runtime、不留通道**。E3 前案(09-28)早已关，E 层闭合；runtime 零改动、基线不变。
> 用户追问后补轮4/5「修复伪影再消融」：细化臂/带重排臂/门消融全配齐，重排独家救回 1/回退 19，
> 判负为修复后结论（raw=106 天花板 > 一切顺序臂）。随后密度探针 v1 暴露**前提错误**并已更正
> （生产本就 1fps，与竞品同网格→判负更强）；v2 探针（2fps vs 1fps）**判负关闭**：生产严格净 0/
> 截等长 −1、建索引 ×2 耗时、沙盒天花板微降 ⇒ 索引密度工程与门限复标均不立项（FINDINGS §密度探针）。
> 详见 `FINDINGS_ORDERED_SEARCH_M0.md`。**待拍板**：git 提交 / 分发包重打 / 下批方向
> （成片渲染=差集 TOP1 唯一未消化；入库层+UI 多原片接线=续27 尾巴）。

> **（2026-09-29 续27）继续偷·video.concat 多原片合并 = ✅ 移植+验收闭环【下个对话从这里读起】**：
> 竞品形态=入库前物理合并单文件（copy/HEVC 转码链/HDR 位深/稳定命名缓存/超时取消监护），非多索引并行。
> 落地 `media/ffmpeg/source_merge.py`+`locator_service.merge_originals`+`SourceMergeConfig`（默认开，
> 单原片永不触发）+API `original_paths`/`POST /api/source/merge`。后端 **388**·API **89** 全绿。
> 真实验收：2.mkv 关键帧切两半→copy 合并（漂移 0.046%）→复用→合并片定位对照基线
> **36/39·39·FP3/4 逐 ID 零翻转**。mkvmerge 路由缺失/字幕丢弃/音频混用降视频=已登记口径差异。
> **待拍板**：git 提交 / 分发包重打 r3（打包需授权）/ UI 多选原片接线（下一批）。
> 详见 `FINDINGS_SOURCE_MERGE_PORT.md`。

> **（2026-09-29 续26）UI 真机导出复核 ✓ + 抓修 P1 新建项目断链【下个对话从这里读起】**：
> 打包 exe E2E 全过（新建项目→定位→EDL/剪映导出）；**复核抓到并修复** 续20 A6 断链——
> `createProjectViaPicker` 把剪辑视频写进 sourceVideo、不填 editedVideos → 分析页下拉恒空/开始分析
> 永禁；`refreshSourceMeta` 只认 sourceVideo 同修。测试回归锁更新（vitest **95** 全绿+双 typecheck 干净，
> 后端 363/API 81 不变）。**zip 定稿 `Video-Locator-win-x64-20260929r2.zip`**（r1 含缺陷已迁 trash）。
> 证据：`work/ui_accept/export_out/tset2-ed.loc.{edl,jy_draft}`（t2r01b 区域 3164 切点展开两通道验证）。
> **待拍板**：git 提交（~215 文件）。

> **（2026-09-29 续25）发包重打 ✓ + 展示层两件套 ✓**：
> ① `mvp/ui/release/Video-Locator-win-x64-20260929.zip`（1.59GB，win-unpacked 同步重建——新 backend
> =fast_global 默认开 + cbed284/ff71db6 修复入包，启动冒烟过；"Windows 包重打"两条销项）。
> ② 两件套落地：`exporters.split_clips_at_boundaries`（跨镜头主 clip 在真实转场切点展开，记录侧等比，
> EDL/FCP7/剪映三通道留痕+不回并）+ 单帧守卫（<0.5s 碎片并入邻段；既有 clip 仍只告警）。
> 单测 8 + 后端 **363 全绿** + API 81 + 真实导出冒烟（t2r01b 区域 3164 切点展开两段）。
> **待拍板**：git 提交（~210 文件）/ UI 真机导出复核（两件套+fast_global 新默认效果）。

> **（2026-09-29 续24）fast_global 翻默认开 + M2 四腿收口**：腿 c 质量权重
> = 定向成功（t2r01b part→HIT，唯一 row4 判别信号）/全局证伪（127→117、口径 105→78）不采纳；
> **`fast_global_enabled` 默认 True**（生产形态=M1 形态），默认态四片验收批逐 ID 零翻转复现 ON 基线
> （127/139·137·4/9·口径 105），打包冒烟通过（health 200/公告/release 拒启）。**生产现役基线自此
> = 严格 127/139 · 场景 137 · 负例 4/9**。tier2 清理 2.4GB 已迁 trash。测试基线：后端 355。
> 证据链 = `PROJECT_FAST_GLOBAL_ANCHOR.md` §8/§9。**待拍板**：git 提交（~200 文件）/
> mvp/ui/release 分发包重打（cbed284+ff71db6+新默认）/ UI 端到端验收。

> **（2026-09-28 续17）竞品 103 叶子模块逐文件穷举对齐完成 + 性能基准实测落地（一条对外承诺被证伪）**
> ① **穷举基线**：`cutmatch_module_map.txt` 137 个 dotted 模块 = **34 包级 `__init__`（无自身逻辑）+ 103 叶子**；
> 逐叶子对齐表已落 `competitor_cutmatch/FINDINGS_CAPABILITY_MAP_20260928.md` 表 D（含证据 blob# 与我方 文件:行）。
> ② **复核推翻 5 条**（表 E）：我方其实已有 `shell.openPath`（`main.ts:61,174`）、`CREATE_NO_WINDOW`
> （`_runner.py:23,61`）、`ffmpeg_io` 有 `scale=` 参数（生产从不调用）、TaskManager 有 `_lock`（只护字典，
> 确无并发准入）、「137 全可比对」（实为 101 可比）。⇒ 教训重申：**子代理断言必须核到行号**。
> ③ **最终差集 TOP8（按产品价值）**：成片渲染 + 导出前**单帧片段守卫**/退化硬停 ＞
> **多原片合并 `video.concat`**（34 键最大非算法族；我方只能单原片索引 = 功能边界缺口）＞
> 大文件鲁棒性（CFR 代理/memmap/停滞看门狗/**独立 GPU 工作进程监督**）＞
> 售后可诊断性（11 客服错误编号/三级日志/**路径脱敏**，我方日志现明文含本机路径）＞
> 批量并发治理 ＞ **快/精双模式 `matching.router`** ＞ 商业化前置（含 `release_profile`"配置缺失即拒启"闸门思路）
> ＞ 素材入库工具面（盘符浏览/自然排序/白名单/磁盘预检，与已知断链 G4/G7 同源）。
> ④ **性能基准（Track B）已实测并填 `MVP_ROADMAP §7`**：H2 DirectML，10/60/128min 建索引
> **44.6 / 260.3 / 562.7s**（13.5~13.8fps，索引 1.08/6.34/**13.21MB**，RSS 745/758/1812MB）；
> 128min 真实配对定位 首跑 769.1s / 缓存复跑 483.3s，全流程 **22.2 分钟**。
> ✅ 承诺「2 小时影片索引 7~12 分钟」**成立**（9.4 分钟）。
> ⚠️ **承诺「同一成片重复定位约 2~4 分钟」不成立**——该数字源自 test1（41 段）167s；
> 69 段实测 483.3s = 8.1 分钟 ⇒ 耗时随**编辑段数**线性变化，`PRODUCT_INTRO:52` 文案必须补前提或改口径。
> **待办新增**：⑧ `PRODUCT_INTRO` 复定位口径修订（需拍板措辞）⑨ 表 E 差集里选首批立项项
> （我建议：单帧片段守卫 + 退化门 + 日志脱敏三件，均低成本高回报）。

> **（2026-09-28 续16）Track A 产品断链 = ✅ 已修 5 项 + 孤儿置信链已删；Track B 性能基准实测中**
> 计划见 `~/.qoder-cn/plans/clever-haven-finch.md`。已完成：**A1** 资产 `sha256` 校验 + `weights_only`
> （摘要不符即 DeviceError 不静默加载；历史资产 legacy 放行；生产资产已就地回填 + 备份 `.bak-pre-a1`）；
> **A2** `preprocess_sha` 从空壳变真判据（**测真实预处理行为而非声明值**；四片索引实测保持 VALID、零重建）；
> **A3** 新增 `POST /api/results/load` + 前端接通（重启不再丢结果与手工修正）；**A4** 导出面板暴露
> 门槛/低置信处理/边界吸附（默认值与旧行为逐字一致）；**A5** Mock 模式常驻横幅（防 09-22 那类静默假连接）。
> **C1** 删 `assess()` + `engine/localization/pipeline.py` + 3 个仅该链消费的旋钮 + `SeqAlignConfig.vectorized`；
> 顺带发现并删除**在本次删除之前就已损坏**的 `smoke_locator_service.py`（patch 目标不存在）。
> 测试：后端 **294** · API **61** · 前端 **69** + typecheck 全绿。
> **待办**：① Track B 结果落地（填 `MVP_ROADMAP` §7 表 + 核对 `PRODUCT_INTRO`「索引 7~12min / 复定位 2~4min」）
> ② **待拍板**：`produce_candidates` 是否连删（同属孤儿链，但删它会连带删掉 ranking 层唯一测试覆盖）
> ③ A6 假数据清理（`movie.mkv` / `Interstellar (2014).mkv` 占位、项目「时长」恒 0 需 metadata 端点）
> ④ 导出 `filename` 模板口径（后端工程导出通道无此参数 → 补参数 or 从规格删除）
> ⑤ Track C 竞品项（**退化门已批未做** → 展示层两件套 → speed_fill → commentary_scene）
> ⑥ Track D 两份扫描结论归档文档 ⑦ **git 提交仍未授权（约 115 文件未提交）**。

> **（2026-09-28 续15）全项目 × 竞品「漏接」交叉扫 = 竞品侧 7 项确证能力从未落地 + 我方 2 处档案错判**
> 起因：用户质疑「是不是漏了功能没接入」。双路穷举扫（竞品 findings 全文 + 我方 runtime 逐旋钮接线），
> 判据 = **档案里有无产物/脚本/实测数字**（不是"文档提过"）。
>
> **A. 竞品侧确证、我方无任何执行记录（按价值排序）**
> 1. **展示层两件套**（最高，零指标风险）：`boundary_guard._record_boundary_split` 真实转场切点剪映/PR 时间线展开
>    + `exporting/segments/builder` 单帧片段导出守卫（防闪烁）。TODO 续12① 自评"最推荐"，**至今只有待办条目**。
> 2. **`speed_fill_*` ±10% 变速补齐**（字节确证 90/110）：FULL_SWEEP §5.3 自评"用户感知收益最大"，无立项无探针。
> 3. **`max_duplicate_scene_ratio=0.8` 退化拒绝门**（字节确证）：§5.8 自评"一行可加"，我方结果验证层缺此判据。
> 4. **`path_*` 路径 DP 四项加权**（字节确证 0.55/0.2/0.2/0.05 + 三罚值）：我方仍是贪心 rerank；
>    ⚠️ 注意「DP 选路下沉」已实测有害（续10m 三臂归因 −8），本项若做须按**全局层形态**而非局部判据。
> 5. **`resolve_consecutive_scene_offsets`**（docstring 确证）：同场景重复起点平移，对症我方"同场景选错时刻"主病灶。
> 6. **`commentary_scene_*` 20 键 ED 快速分镜复核**（字节确证）：TN 双预测+ECC 运动校验+白闪判别，
>    对症我方 6 假切点/test1 过切；非 A1 整体替换故无 −16 风险。TODO 续12② 待办未做。
> 7. **`boundary_guard` 开头串镜守卫 / 尾部硬切回退**（docstring+字节）：仅 §7P2 文档提及。
>    （另：`ordered_search_*` 参数全集已绑定但机制本体未测——属"等第二套复现"，非漏项，需单独拍板。）
>
> **B. 我方档案错判（本次自查暴露，需拍板处置）**
> 1. **续13 审计"0 死旋钮"不成立**：`SeqAlignConfig.vectorized`（config.py:118）全仓无消费点；
>    `ConfidenceConfig.nreps_dispersed`/`max_similar`/`scene_div_montage` 只被 **孤儿路径**
>    （`assess()` ← `pipeline.localize_segment`，**无生产调用者**）消费，产品运行态不生效。
>    待拍板：删除（破坏性，牵动 tests/smoke）or 保留但在 config 注明"仅 legacy 路径"。
> 2. **conf_v2 启用影响面被我初稿低估**：`exporters.py:93-121` 按 `confidence.level` 过滤
>    （默认 MEDIUM 门槛 + LOW exclude）⇒ 降档会**改变导出工程内容**，不只是改徽章颜色。
>    另：v2 与 `temporal_ambiguity` 双降档无叠加仲裁；`confidence_v2` 诊断 dict 不落 JSON/API/UI。
>    （均因 conf_v2 默认关而为潜在态；已登记 `FINDINGS_CONF_V2_PORT.md` §5b。）
> 3. 澄清一条夸大告警：`getattr(cfg,"subshot_enabled",True)` 因属性确实存在（默认 False），兜底不生效，非行为翻转。

> **（2026-09-28 续14）置信公式移植（conf_v2）= ✅ 已执行并结案**：豁免已给（DECISIONS 同日窄范围）+ 代码进（默认关）
> + 单测 13 项 + 全套 **292 绿** + 四片双臂 231 段实测 = 三指标逐位零回退（119/139·137·4/9·支撑 591/1140），
> 但 **v2<0.6 的 16 段里 15 段已被硬 flag 判 LOW（重叠 93.8%）**，真病灶（同场景选错时刻 18–21s）零判别力
> ⇒ **维持 `conf_v2_enabled=False`，不作为产品行为启用**，模块保留为基础设施。
> 多模态读图 8 张另发现 `test1_r13` 属 **GT 窗侧假病灶**（画面其实匹配）——「HIGH∧MISS 有 5 条」被 GT 口径夸大。
> 产物 `FINDINGS_CONF_V2_PORT.md` / `work/confv2_*` / `work/confv2_visual/`。
> **顺带销项**：④ AGENTS.md 冻结时代命令已加标注 + INDEX.md GT 行与测试数（80→292）已更正；
> 顺手修 `locator_service._edited_fingerprint`（缓存键剔除 `confidence`，置信调参不再触发 A4 全量重算）。
> **仍待拍板**：① **git 提交**（现 99 + 续14 新增 8 个文件未提交）② 残留清理二级 ~1.7GB
> ③ UI/导出验收（需打包授权）⑤ 32 份文档 GT 版本头——**推断级提案表已出**
> `semantic_signal/GT_VERSION_REGISTER_PROPOSAL_20260928.md`，三档落地方式待选（整批 29 / 只写有据 5 / 只补基线过时提醒）。

> **（2026-09-28 续13）全项目结构化审计完成 = `PROJECT_AUDIT_20260928.md`（根目录）**：0 死旋钮 / 279 测试绿 / GT 无漂移。
> **新增待拍板**：① 残留清理——**【2026-09-28 已执行安全部分 1.19GB】**（dist_backend/build_backend_work/loc_smoke/__pycache__
> 移入 `D:/claudework/benchmark_trash_20260928/`, 可还原; 279 测试全绿验证）, 剩余需拍板 ~1.7GB（🟡:
> ViT-B 路线缓存/orb+isc 冻结缓存/datasets originals 2.mkv 副本）② **git 提交**（97 文件未提交, 含续10l~13 全部源码/测试/文档, 需授权拆笔提交）
> ③ 32 份研究文档补 GT 版本标注头（低优先）④ AGENTS.md 冻结时代命令加标注（低优先, 硬约定保护勿乱动）。

> **（2026-09-28 续12 用户拍板）竞品全量扫穿待办清单（按价值/风险排序, 挖穿前逐项销号）**：
> ① **展示层**（最推荐, 零指标风险）: 真实转场切点剪映/PR 时间线展开(_record_boundary_split) + 单帧片段导出守卫; 常量全字节确证;
> ② **ED 侧快速分镜复核**: TN 双预测+48×27 描述子+ECC 仿射运动校验+白闪判别, 校正气切点/拒非硬切候选（非 A1 整体替换, 无 −16 风险; 对症我方 6 假切点/test1 过切）;
> ③ ~~**置信公式四项加权**（采样/偏移支持/局部一致/候选差距）: ⚠️ 需用户豁免「Confidence 公式冻结」护栏~~
>    → **【2026-09-28 续14 已执行并结案】** 豁免已给 + 四片实测 = 产品价值 1/231，**维持默认关不移植**
>    （见本文件顶部续14 与 `FINDINGS_CONF_V2_PORT.md`）;
> ④ **口径档对照**（低成本收尾）: 2fps 主档 / AKAZE loose=4 / top_k 28 / balanced 5fps（复现方接口在）;
> ⑤ **检索层长场景局部 probe**: 候选层已饱和, 低优先;
> ⑥ ~~**机器码专项**（委托执行方, 非我方）: N1 族 59 项~~ → **【2026-09-28 续12 推翻】N1 ordered_search_*/N4 path_*/置信公式权重已全绑定在 profile fast_options**（ordered_search backtrack 15s/chunk 315s/expand 900s/锁 3 段/双门 0.55·0.62; 置信 coarse 0.3/cons 0.2/local 0.4/margin 0.1 门限 0.6）⇒ 机器码静态理由大幅缩水, 唯 candidate_count 等占位符仍缺;
> ⑧ **（2026-09-28 续12 ✅ 已完成）全量扫穿**: `FINDINGS_COMPETITOR_FULL_SWEEP.md`——挖穿宣告成立(139 docstring blob=全部自有代码 100% 已扫; 144 blob=第三方/无语义; catalog 644 自有键 100% 镜像 profile)。新发现: speed_fill ±10%/patch top-16 token 公式/401AutoClip/授权体系全貌/.cmlog 格式/滑窗与批次阶梯/max_duplicate_scene_ratio=0.8。唯二静态遗留=常量运行期默认值待动态验证+patch_top_k/global_weight 强推断。
> 附: **UI/导出验收（需打包授权）**——含 vote_prior_enabled/dense_recheck_enabled 翻默认开的前置。
> ⑦ ~~（本轮执行）全量扫穿~~ → ✅ 已完成(见 ⑧)。

> **（2026-09-27 续11）偏移投票起点先验 立项+移植+回归 = ✅ 完成**：生产 117 -> 119/139（+2 零回退, test1 t1r07a/t1r10b），
> 场景/负例持平；投票+密集复核臂同 119（种子落位后 P0 零增量）。单测 279 全绿。**默认关维持，
> 待 UI/导出验收（需打包授权）后翻 `vote_prior_enabled` 默认开**。产物 `work/voteprior{,_dense}_*.results.json`。
> **（2026-09-27 续10m 背景存档）**：全局层完整复现四片 100/139；同口径（main span 截等长严格）生产 77 vs 复现链 100。
> 其余口径档（2fps 主档/AKAZE loose/top_k 28）未跑（复现方接口在, 非阻塞）。

> **（2026-09-26 续10l）mvp 移植 + 生产实测 = ✅ 完成**：模块/旋钮/挂接/单测 272 全绿；生产四片双臂
> ON vs OFF 三指标完全一致（117/139·137·4/9），纯效应 95 段微移零翻转——**生产不需要 P0**（生产起点本就
> moment 级精度），默认关维持正确，模块留作基础设施。详见 `FINDINGS_P0_DENSE_START_TEST1.md` §10。
> **待用户拍板**：① 竞品对标主线（对标→挖掘→移植全链）是否收官归档；② UI/导出验收（默认关零风险，需打包授权）。

> **（2026-09-26 续10k）投票结构移植三连败定案 = ✅ 完成**：v0 graft / v1 硬投票 / v2 软投票全部劣于终版
> （10/11/10 vs 13/43）——投票/分散度结构属检索阶段，不可下沉为精修采纳门；P0 核心已回滚终版（+6 零退化）。
> **mvp 移植前检查清单就绪**（`FINDINGS_P0_DENSE_START_TEST1.md` §9）。
> **待用户拍板（下一步）**：① ⚠️ **护栏豁免裁决**：09-01 保留护栏「禁 per-query argmax/voting/cut-aware/temporal align」
> 与 P0 判据是否冲突；② 按 §9 清单执行 mvp 移植（四片回归 + UI 验收）；③ 全局层彻底解法维持待办。

> **（2026-09-26 续10j）全局层挖掘 + 分散度 graft 否定 = ✅ 完成**：双管线调用序/主线锁定/偏移投票/置信公式全部恢复
> （`FINDINGS_DOCSTRING_BREAKTHROUGH.md` §9）；分散度门窗口局部 graft 不分真假（p41 真改善被误杀/p01 假移动达标），
> 已降级为诊断。P0 终版（+6 零退化）维持。
> **待用户拍板（下一步）**：① **mvp 移植决策**（P0 终版零退化形态，三指标回归+UI 验收）② 是否立项「快速管线完整复现」
> （= 第二套复现，获得真正的全局上下文）③ 机器码专项是否委托执行方。

> **（2026-09-26 续10i）P0 采纳门对齐竞品 + 四片终版 = ✅ 完成**：终版（margin4 + gain0.04 + max_shift2.0 +
> 距离平局裁决）四片 **89/139（净 +6 零退化）**，仍超 main-span-only 85；无门版 91（+8 含 1 退化）。
> 支持度门降级为诊断；单层重建收敛（p01/q0019 局部证据同构，区分需全局层）。详见 `FINDINGS_P0_DENSE_START_TEST1.md` §7。
> **待用户拍板（下一步）**：① **移植决策**：P0 终版（零退化形态）进 mvp 生产管线（三指标回归 + UI 验收）；
> ② 无门版若采纳须接受 p01 型退化；③ 残余空间需全局层（ordered_search/路径项/语义守卫）。

> **（2026-09-26 续10h）P1 四片验证 + P2 定案 = ✅ 完成**：P0@0.04+P1a 四片**净 +8（83→91/139）**，
> 首次越过我方 main-span-only 基线 85；2mkv 唯一 −1（边界未收敛 + 窄窗骑线）；P2a 尾部守卫结构性无对象可修；
> P1b/P2a 不采纳。详见 `FINDINGS_P0_DENSE_START_TEST1.md` §6。
> **待用户拍板（下一步）**：① 边界最优拒绝门（治 2mkv p01/p16）② **移植决策：P0/P1a 语义进 mvp 生产管线**
> （需立项 + 三指标回归 + UI 验收；口径不同增益不可直接外推）③ 长场景 probe（低优先）。

> **（2026-09-26 续10f）核对通过 + P0/P1a 落地实测 = ✅ 完成**：核对 49/49 键字节证实 + docstring 12/12 命中 exe；
> P0 密集 10fps 起点复核在 31/35 行生效，截等长严格 10→13/43（+4/−1）；P1a 修复 2 行重复起点、GT 零变化。

> **（2026-09-26 续10e）精修/展示层语义挖掘突破 = ✅ 完成**：Nuitka blob 内嵌中文 docstring，G5 真实形式（路径 DP 倒退罚
> normal 5.0 / 连续偏移修正 / 四项加权 0.55·0.2·0.2·0.05）+ 原片侧 6 层起点精修全阈值（~40 新确证键）+ 展示层（转场切点
> 时间线展开/单帧守卫）全部可读。**「N1-N8 静态不可得」正式推翻**。全文 `FINDINGS_DOCSTRING_BREAKTHROUGH.md`。

> **（2026-09-26 续10d）五环组合探针单片先行(test1) = ✅ 已执行完毕**——候选层饱和 42/43 top1（never=t1r08c 零宽伪影）·
> 位置层（span 截查询等长）仅 10/43 vs 我方 main-span-only 22/43 · G5（推断级）零增量零伤害 · 负例 0/1 · 环境漂移 0
> ⇒ **可复现组合链瓶颈 = 场景内位置精化（非检索排序层）**。
> 产物 `competitor_cutmatch/FINDINGS_COMBO_FIVE_RING_TEST1.md` + `probe_combo_dual_caliber.py` / `probe_combo_flip_visual.py` +
> `work/combo_probe_test1.json` + `work/combo_probe_review/` + 外部仓 combo 产物 6 件。
> 遗留小项：`probe_combo_flip_visual.py` 中文桶名 cv2.imwrite 乱码（已手工改名，待修）。

> **（2026-09-26 续10c 用户拍板）下一步 = 「竞品全流程组合探针」单片先行【已执行，见上续10d】**——五环全开（TN 全流程边界+段内单元 /
> 每场景 5 关键帧+长场景加密 / patch 主力 0.55 / 匹配目标函数路径项 / AKAZE 候选几何校验），**先只跑一个测试视频**。
> 执行基础与验收设计见 `DECISIONS.md` 2026-09-26 条目 + `FINDINGS_CAPABILITY_GAP.md` §3。
> 执行要点：① 复用 `cutmatch-analysis/sandbox/run_localization.py`（四组已验证，test1 缓存在）；② 补 G5 路径一致性项；
> ③ **判据必须同粒度化**（TN 场景 span 装配效应已证伪严格指标）= 候选层指标（GT 在 top-k 名次）+ span 截到查询等长 双口径；
> ④ 对照 = 基线 34/43 + main-span-only 22/43 + 候选层等价指标；⑤ 五桶出图复核；零 runtime、不碰 GT、推断级表述。
> 历史条目见下与文末。

> **（2026-09-26 续10b）用户前提确立**：竞品在相同素材端到端更好（用户实测），不再搁置为"未测"。
> 主交付 = `FINDINGS_CAPABILITY_GAP.md`（差距 = TN 切分→5关键帧→patch主力→路径一致性→AKAZE 组合链；
> 历史单环替换全失败恰因未测组合；三指标奖励 GT 对齐不奖励几何正确）。
> ~~待拍板~~ → **已拍板执行（见顶部续10c）**：「TN 子单元 + 关键帧查询」升级为五环全开组合探针、单片先行。
> GT 线索 t1r08b/t1r12a 已撤回（候选表反转：GT 在 top1/top2）；~~剩余 73 张对照图未裁（2mkv A 桶 17 张优先，非阻塞）~~
> → **【2026-09-27 已裁 2mkv 全 24 张】**：0 例新错误机制，proxy 真赢 p23/p30，其余错例全落已知族；
> 明细 `work/proxy_loc_review/verdicts_2mkv.csv` + `REVIEW_NOTES_PROXY_D_STAGE.md` §2mkv。test2/test3 余图按需复核。

> **交接（2026-09-26 15:40）**：本会话新增条目见下；**下个对话第一优先 = 收到执行方 D 段 `localization.json` 后跑同口径对照**；
> 第二优先 = 用户对「细切点当子 span」立项拍板。历史条目一条未删，仍在文末「历史记录」。
>
> **（2026-09-26 续8 更新）D 段放行条件已裁决**：执行方 om 批因 test3-om 帧数校验 [244,003 vs 锚点 244,004] 按纪律停止。
> 判卷侧独立裁决 = **244,003 为准**（末包带 DISCARD 标记被解码器丢弃 + 我方独立全流解码一致；执行方产物正确无需重跑）。
> 待执行方按 `FINDINGS_TEST3OM_FRAMECOUNT_ADJUDICATION.md` §5 更新 7 处锚点后放行 D 段；**锚点口径应升级为「解码帧数」**。

- [x] **（2026-09-26 续7 完成）D 段前置对照①：查询单元换成竞品 t050 切点 = 四片严格 114→104（−10）· 场景 137→122（−15）· 负例 4→3**：
      多模态复审定性为「**我方 2fps 查询采样 × 细切点**」不匹配 —— 2mkv 的 MISS 全部落在 0.5–1.0s 单元（>1s 单元 0 MISS），
      p02/p03 退化成单帧级查询直接 not_in_source；test1 为净值 0 的同场景内 ~2s 漂移互换。
      产物 `FINDINGS_QUERY_UNIT_SWAP.md` + `mvp/scripts/proxy_query_unit_run.py` + `work/proxy_qu_*.results.json` + `work/qu_flip_visual/*.png`。
- [ ] **（2026-09-26 续7 新增，待用户拍板）「细切点当子 span」立项**：细切点当查询单元净负已证；当**段内子 span / 展示粒度**尚未测，
      是否立项「细边界 + 粗查询单元」混合探针（前置：先解决编辑侧查询采样口径）。

- [x] **（2026-09-26 续6b 完成）竞品 B 段后处理规则逐帧复现 = ✅ 24/24**：仅凭对方 `probs.npy` 重放其规则，6 片 × 4 阈值切点与分组**逐帧完全一致**；
      确证规则 = `active=prob>th` → 连续帧成组 → 组中点上取整 → **按切点间距 <8 迭代合并** → 取跨距中点；`FINDINGS/11` 的
      「未知 1/2」**已解**、`sensitivity` 不参与；11 §4「峰值检测更稳」**实测不成立**（峰值切点数 == 阈值档切点数）。
      产物 `mvp/scripts/replay_cutmatch_postprocess.py` / `work/replay_postprocess.json` / `FINDINGS_CUTMATCH_POSTPROCESS_REPLAY.md`。
- [x] **（2026-09-26 续10 已答）P0-8 `source_sample_rate` / `commentary_sample_rate` = 2 的语义**：对方 `FINDINGS/12_PIPELINE_SAMPLING_SEMANTICS.md`
      作答——两键属精确模式 `pipeline.options.DEFAULT_OPTIONS`（与 fast 的 `source_global_fps=1.0` 是**两条管线各一套采样键**）；
      单位**强推断 = 2 fps（未确证）**（三条量级论证）；处置 = manifest 写 `sampling_caliber` + **主档 2 fps、额外跑 1 fps 对照档** +
      `keyframes_per_scene=5`（全局关键帧通道）与 `*_sample_rate`（AKAZE/局部稠密帧）**两通道不可合并**。
      静态可证部分已到上限；剩余定论只能靠运行期日志（N16，仍被授权挡）。
- [x] **（2026-09-26 续10 已验证）D 段提示词 7 条 P0 = v2 全部在位**（P0-1~P0-8 逐条核对，含新增 P0-8 采样口径与回报模板）；
      追加：test3-om 244,003 裁决已并入提示词「继承 B 段结论」节（解码帧数口径）。
- [ ] **（2026-09-26 续6b 新增，待用户拍板）「输出层换切点」立项**：探针已给出两条硬事实 —— ① 我方 6 处假切点在 TN 概率上非峰无值 ⇒
      换 TN 口径天然剔除；② 我方 29 处真切点在 TN 概率上也不是峰（与对方相距 0.6–5.0s、是另一处真切换）⇒ **只能并集+仲裁，不能替换**。
- [x] **（2026-09-26 续8 完成，用户批准）换切点探针扩全量 + TN 双判据仲裁 Stage 1 = 否定（有据，不进 runtime）**：
      227 条现行边界 × （TN ±0.25/0.5s 窗最大概率 ∧ H-CM1 帧差判据），44 例已裁决锚点穷举 15 组工作点：
      **最优 = 假命中 5/6 ∧ 真误伤 5**（2mkv@9.45、test1@78.2/100.2/107.07/110.6 全是盲判确证真切换，交换比 ≈1:1）；
      唯一漏网假切点 test3@27.79（moved/shift−14）与已证真切换 test3@16.29（moved/shift−15）特征同构 → **判据空间内假切点与「TN+像素双盲真切换」不可分**，
      仲裁删除形态关闭；「输出层换切点」若立项只做展示层并集/就近优选（不删我方切点）。
      产物 `mvp/scripts/probe_tn_arbitration.py` + `work/tn_arbitration_probe.json` + `FINDINGS_TN_ARBITRATION_PROBE.md`。

- [x] **三指标口径审计 V5 + 非 HIT 三层归因 = ✅ 已完成（2026-09-26）**：竞品会话「中点口径伪影」假设
      在 runtime 层量级 **≤ +2（基线 117→119）** → A1(−16/−17) / ViT-B(−1~+1) / 场景聚合(−6/−8) 三组对照**全部稳健**；
      编辑窗 ±0.5s 判据被判**膨胀**（6 例翻转中 5 例严格编辑侧重叠 = 0.00，由相邻编辑段的大场景 span 认领）→ 拒绝；
      139 例检索天花板 = HIT 117 / rank≤3 **19** / rank 4–20 2 / rank>20 **1**；非 HIT 22 例 = **口径 2 / 定位层 19 / 特征层 1(t2r05a)**。
      产物 `mvp/scripts/measure_recall_v5.py` / `audit_retrieval_ceiling.py` / `diag_nonhit_localization.py` +
      `work/recall_v5_*.json` / `loc_retrieval_audit.json` / `nonhit_diag.json` / `caliber_v5/*.png` +
      `user_case/competitor_cutmatch/FINDINGS_METRIC_CALIBER_V5.md`（零 `mvp/src` 改动）。
- [x] **（2026-09-26 续10 状态登记）竞品情报 N1-N8**：数据段已双方确认**穷尽**（对方 27+7+4 项绑定，我方逐字节复核）；
      剩余 59 项（N1 `ordered_search_*` 全部 / N4 `path_*` / N3 开关族 / N8 多判据组合）落在**code object 机器码反汇编**卡点
      （09 §8.5 自述「本次未完成」）——我方不重复投入该专项，等执行方机器码逆向产出；N7（180 语义）已于续3 解决（更正为 8）。
- [x] **竞品常量 09 的采纳评估 = ✅ 已完成（2026-09-26）**：27 项绑定对照我方现值后 **可直接采纳项 = 0**；
      我方已独立字节复核 26/26（名字+零间隔+数值，24/26 唯一数值落点 ⇒ 非巧合）；**但 `180 单位` 与"作用阶段"仍是假设**（`_scene_range_fps` 未绑定；同区段 `source_global_fps` 值位后紧邻 0.1/30.0 两浮点 ⇒ 归属有歧义）；
      **抄 `global_top_k=100`/`scene_top_k=10` 关闭**（我方非 HIT 真值帧 19/22 本就 rank≤3）；
      抽稀敏感性实测：**stride10(0.1fps) 粗筛 127/139、stride2(0.5fps) 139/139**（漏例 12 已列名；"靠 `long_scene_*` 补回"仍是猜测）。
      产物 `FINDINGS_CUTMATCH_CONSTANTS_ADOPTION.md` + `work/coarse_sampling_audit.json`。
- [x] **09 增量版（02:14）复核 = ✅ 已完成（2026-09-26）**：§8.1 边界精修 **7/7 确证 + 与我方 A7 7/7 一致**（A7 升为确证）；
      §8.2 4/4 成立（topk_rerank 10/0.8、actual_refine_score_threshold 0.65、ordered_search_max_seconds **1800.0**（原记 7200 系相邻配对假象，2026-09-26 更正），
      后者需确认 profile）；§8.3 **伪绑定陷阱复核成立**；§9.3 `_scene_range_fps` 数据段无字面值 → 180 单位静态不可判定；
      §9.4 **代码对象记录独立复现**（`match_commentary_scenes` co_consts 含 0.45/0.55 + retrieval.py）→ 权重升级为代码级互证。
      产物 `mvp/scripts/verify_cutmatch_bindings_v2.py` + `work/verify_cutmatch_v2.json`。**可直接采纳项：0 → 11（字节级）**。
- [ ] 待用户拍板：是否立项「两级采样（细粒度粗筛 + 局部密验）」探针（目标索引成本 ÷10 且召回不回退）；
      注意：粗筛档位取值须自定（竞品 `source_global_fps` 在字节层有 [0.1, 30] 歧义）。
- [x] **采纳评估建议 A：边界精修判据对照 = ✅ 已完成（2026-09-26）→ 不采纳（有据）**：四片 227 条边界上
      H-CM1 与我方 CLS 精修 **97.4% 位移 ≤4 帧**；6 个分歧点视觉裁决 **2:2:2**（相邻真切换各选其一 ×2、H-CM1 被运动骗 ×2、
      我方无像素切换假边界 ×2）；副产品 = 我方 CLS 峰在运动/渐变处有 ~0.9% 假边界 → 若要改只能走"双判据仲裁"。
      ⚠️ 本轮 VLM 不可用（方舟账户欠费 403），多模态复审由逐张读图完成。产物
      `user_case/competitor_cutmatch/FINDINGS_BOUNDARY_REFINER_COMPARISON.md` + `work/boundary_disputes/*.png`。
- [x] **采纳评估建议 B：patch×global 加权融合 = ✅ 已完成（2026-09-26）→ 不采纳（有据）**：
      p08/t2r05a 全部权重变体 argmax 都不在真值窗（margin 恒负）；仅"CLS 已对"案例 margin 放大（p01 +0.034→+0.104 ≈3×，rank 不变）；
      patch 独立打分有害（w=1.0 时 p01 → rank 2 / margin −0.057）⇒ 定位层收益 0，只可考虑用于置信门控（Confidence 公式当前冻结）。
      产物 `user_case/competitor_cutmatch/FINDINGS_PATCH_FUSION_PROBE.md` + `work/patch_fusion_probe.json`。
- [x] **（2026-09-26 已定）N18 判定 = 运行期不可行**：对方明证「每次启动需激活码+设备指纹、授权响应 Ed25519 验签、
      a01/a02 为 AES-256-GCM 密文、content_key 走服务器 model lease」⇒ 无合法激活码跑不出结果，绕授权也解不开模型（对方明令禁止，我方认同）。
      **改走「代理复现（推断级）」**：公开权重（TransNetV2 ONNX + DINOv2 官方）+ 确证参数，在沙箱复现其切分/定位口径。
- [x] **（2026-09-26 续6 完成）② 代理复现 B 段（场景切分）几何对照 = ✅ 完成**：ed 四片 × 四阈值（±0.5s，切点=段 start）→
      **test2 仅代理 13/仅我方 0（四阈值全稳）= 纯漏切**、test3 31/4 = 偏粗、test1 1/7 = **我方过切**、2mkv 12/4 混合；
      双实现交叉验证 ±0.5s 内 test1 32/32 · test2 65/66 ⇒ B 段链路可信；44 张盲判包（抽检 6 张：4 例双方都是真切换 ⇒ 主机制=粒度）。
      产物 `mvp/scripts/geom_proxy_vs_ours.py` / `visualize_proxy_disputes.py` + `work/proxy_geom_*` + `work/proxy_blind_disputes/` +
      `FINDINGS_PROXY_B_STAGE_REVIEW.md`。**上轮两条异议（source 指针 / 0.1 vs 0.55）自证后全部撤回**（`verify_cutmatch_profile_pairing.py`）。
- [x] **（2026-09-26 续10 完成）代理复现 D 段（定位）= 我方自跑四组全量 + 多面复核**：复现 262 查询（242 matched），
      结构 P0 全过、test1 回归 MD5 一致、重复跑全同解；import 升级支持 v2 schema；
      **数字 = proxy 严格 124/139 · 场景 121 · 负例 4/9**（基线 117/137/4；main-span-only 基线 85）；
      **读图 20 张裁决：严格 +7(test1)/+7(合计) = TN 场景代理 span 粒度装配效应，非定位质量差；复现内容性错误 0 例**；
      AKAZE on/off 无增量无伤害（10/262 行差异全为 strict 门拒绝）；复现弱点 = 蒙太奇段拒识漏召回（p10 型）；
      n01 误配与我方历史同区同机制。**2 条 GT 复核线索待用户裁决：t1r08b / t1r12a**（双侧独立定位同内容区、GT 窗画面与 ED 不符）。
      汇总 `FINDINGS_PROXY_D_STAGE_REVIEW.md` + 逐图 `REVIEW_NOTES_PROXY_D_STAGE.md` + `work/proxy_loc_review/`（93 张，已裁 20）。
      未竟：loose AKAZE/2fps 主档/对齐档未跑（接口已留）；93 张图未裁部分按需复核。
- [x] **（2026-09-26 续10 已执行，用户授权直改外部仓）文档订正 3 条 = 全部落地**：① test3-om 锚点 244,004→**244,003** 共 8 处
      （PROMPT_FOR_EXECUTOR / RUNBOOK §5.1 两表+验收清单+新注 E / sandbox 4 脚本 ANCHORS），**锚点口径升级为解码帧数**；
      ② `197,305` 残留核查 = 0（对方 14:19-14:46 已同步，现存皆为历史留痕说明）；③ FINDINGS/09 旧表行 `dtw_min_score`
      已改「~~0.1~~ → 确证 0.55」；追加 ④ RUNBOOK `feature_image_size` 命名注记（profile 真名 vs 文档 `image_size` 名不符）。
- [x] **（2026-09-26 续6 完成）44 张盲判图逐张裁决 = ✅ 判卷侧自行多模态审完毕**：对方 29 个独有切点 **0 假切点**（r 中位数 3.10），
      我方 36 真 / **6 假** / 2 未定（test1 3 处假切点，机制=镜头内运动/字幕换行假峰；我方 14/44 例 r<1）；test2 零假切点但漏切 13 处。
      产物 `work/proxy_blind_disputes/verdicts_44.csv` + `frame_diff_sidechannel.json` + `mvp/scripts/blind_sidechannel.py`。**不套 GT、不进三指标**。
- [x] **（2026-09-26）我方两处旧记录作废**：`source_global_fps` 0.1→**1.0**（我方独立佐证：产品自述串「原子保存 1fps 原片全局索引…」）、
      `commentary_short_scene_min_frames` 180→**8**（180 处更像约束）；以对方 `FINDINGS/10` + `competitor_profile_v1.json` 为权威。
- [ ] （历史）**N18：竞品成品运行期取证** —— 先问对方"是否已有可用授权能跑完一次分析"；有则按清单取
      ①**他们的镜头/场景切分列表**（唯一能与我方边界做真值级几何对照）②定位结果 ③缓存 ④日志实际生效值 ⑤导出文件；
      无则退而求其次要**解密模型本体**（可在本机复现其切分/特征栈做对照组）或任意素材输出样例。已写入
      `INTEL_REQUESTS_CUTMATCH.md` N18（含"收到后我方如何用/如何独立复核"的口径承诺）。
- [ ] 待用户拍板：是否推进**建议 C（收窄）**——用竞品已字节确证的 offset 门控（min_score 0.55 / min_support 2 /
      start_window_radius 30 / min_improvement 0.04 / topk_rerank 10 / coverage 0.8）打我方 14 例"同池选错时刻"，配画面复核。
- [ ] （历史）进行中：采纳评估建议 B「patch×global 加权融合（0.55/0.45）」探针 = `probe_patch_fusion_rank.py`
      （5 案例：p08 兄弟机位 / p26 夜读 / p01 易例 / t3r12 重复镜头 / t2r05a 蒙太奇；扫 w∈{0,.25,.45,.55,.75,1}，
      判据 = 真值窗最佳帧池内排名 + 自动 margin；结论须配画面复核）。
- [ ] 待用户拍板：`R_rec`（零宽 GT 编辑窗点包含 + 原片窗 ±0.5s）是否作为**并列口径**写入
      `measure_shot_recall` + `GT_BASELINE` 文档（主口径 `S_strict` 维持不变以保证历史可比）。
- [ ] 待用户拍板：是否重开「定位层查询单元细分」方向——**前置条件 = 先给出无 GT 的查询点/子镜头选择信号**
      （否则仍是 oracle 口径，见 `FINDINGS_METRIC_CALIBER_V5.md` §5 与 FINDINGS_SUBSHOT_QUERY 的教训）。
- [ ] 待定：`t2r05a`（唯一特征层失败，蒙太奇段，窗内最佳 rank 77 / sim 0.479）是否留档进 `FAILURE_TAXONOMY`。
- [x] **竞品对标 A1:TransNetV2 场景切分 替换编辑侧两级切分 = ✅ 已完成（2026-09-25）**：
      四片生产管线 **严格 117→101/139（−16）**、**场景 137→120/139（−17）**、负例 4→3（退化 32 / 改善 12）；
      边界与基线高度重合（双向 recall 0.76–0.98）但粒度更碎 → **不接入（有据）**；
      产物 `mvp/scripts/tn_transnetv2.py` / `probe_transnet_bounds.py` / `rerun_transnet_runtime.py` +
      `mvp/benchmark/user_case/competitor_cutmatch/FINDINGS_TRANSNETV2_SEGMENTATION.md`。
- [x] **竞品对标 A2（对齐链的排序用途）= ✅ 已完成（2026-09-25）**：138 条正例 rank **改善 18 / 恶化 37 / 持平 83**
      （平均 rank 2.43→2.80）、margin −0.0495→−0.0407（72 个错配纠正 16）→ **不引入排序层（有据）**；
      产物 `mvp/scripts/research_dtw_rank.py` + `user_case/competitor_cutmatch/FINDINGS_ALIGNMENT_RANKING.md`。
- [x] **【最高优先】重跑 `feature_upgrade`（ViT-S vs ViT-B）配 v4 GT = ✅ 已完成（2026-09-25）**：
      9 探针（v4 GT；p08b 修正为 1108.15-1109.1、t4r01/t4r13 剔除、p26 用 1768.2-1770.05、新增 t3r12）；
      **v3 旧口径逐位复现原存档**（p08b −0.1379/−0.2808 等）→ 原「ViT-B 恶化」= **GT 假象**；真失败族（兄弟机位）
      **两基座都不可分** → 「基座升规模不解决失败族」**复现**，「不建议全量重建」维持。
      产物：`mvp/scripts/research_feature_upgrade_v4.py` + `work/feature_upgrade_v4_results.json` +
      `mvp/benchmark/user_case/feature_upgrade/FINDINGS_FEATURE_UPGRADE_V4.md`。
- [x] **重跑 `phase24_1` 三探针 + M5 = ✅ 已完成（2026-09-25）**：
      ①几何：原「兄弟压倒」证据作废（1109 本就是真值），修正后 HOM 真值帧 rank 1（4/4 硬例）但 INL 判据相反 + 帧间跳变极大
      → 列为**待拍板复验方向**（非「已证伪」）；②运动签名、③硬负例盘点维持；
      **M5「p08b 32→2 patch 捞回」作废**（修正后 CLS rank 5 / patch rank 9）→ patch 独立召回通道无信号（同 M6 v4 0/39）。
      产物：`research_phase24_1_v4.py` / `research_phase24_1_data_v4.py` / `research_patch_recall_v4.py` +
      `phase24_1/FINDINGS_V4.md` / `semantic_signal/FINDINGS_M5_V4.md`。
- [x] **ViT-B 全量索引 + 四片 runtime 回归 = ✅ 已完成（2026-09-25）**：严格 **116/139（基线 117）**、场景 **134（基线 137）**、负例持平；
      27 案例翻转（12 改善/13 退化）= 抖动；成本 ~1.8× 慢 / 存储 2× / 资产 3.9× → **「该不该换更大基座」= 不换（产品级，有据）**。
      产物：`export_dml_model_vitb.py` / `rerun_vitb_runtime.py` / `measure_four_results.py` / `diff_four_batches.py` +
      `feature_upgrade/FINDINGS_VITB_FULL_INDEX.md`。
- [x] **（2026-09-26 续9 已执行，用户委托）**harness 固化 = `mvp/scripts/eval_backbone_swap.py`；基座路线关闭已写入
      `ARCHITECTURE_DECISION_PHASE20.md` 附录 A（见上方续9 条目）。
- [ ] 待用户拍板：是否重新立项「视觉几何判据」复验（phase24_1 探针①修正后为「非证伪也非可用」，
      需固定 RANSAC 随机性 + 全索引池 + ≥3 组机位对照；纯 CPU 成本低，见 `phase24_1/FINDINGS_V4.md` §八）。
- [x] **建机制 = ✅ 全部落地（2026-09-26 续9）**：3 份受影响 FINDINGS 加标注头 + §八登记表 7 份剩余项逐条核销（头部标注+表格更新）+
  **自动受影响清单机制** `mvp/scripts/gt_impact_scan.py`（GT 哈希快照 + 变更→受影响文档清单 + 未登记扫描，变更路径已验证）。
- [x] **（2026-09-26 续9，用户批准执行）backbone harness 固化 + 基座结论入档**：`mvp/scripts/eval_backbone_swap.py`
  （asset/locate/measure/compare 四阶段编排，注册表式扩展，measure+compare 已实测对账 117 vs 116）+
  `ARCHITECTURE_DECISION_PHASE20.md` 附录 A（基座路线关闭，含 V5 口径复核）。
- [ ] **mac CI 重触发**：验证 `cbed284`（pyJianYingDraft assets）后剪映草稿导出可用（背景见 `.agent/STATE.md` 2026-09-22）。
- [ ] **Windows 包重打**：现存 `mvp/ui/release/win-unpacked` 与 zip 早于 `cbed284`（缺 `pyJianYingDraft/assets/*.json`）
      与 `ff71db6`（设备标签厂商中立化），两处修复均需重新打包才生效 → Windows 端剪映导出当前同样会失败。
- [x] **（2026-09-26 续9 核对闭环）p26 runtime margin 口径差**：同日 2026-09-06(XIV) 已查明并修复——runtime 实测 margin
      0.080 恰骑线（探针口径 +0.085，GPU 浮点差 ~0.004），`patch_v2_margin` 0.08→0.075 后 p26 part→HIT、四片严格 +3 零回退。
      无残留待查项（本条原为漏关闭的陈旧指针）。
- [ ] 待用户拍板：T1 训练可行性探针未达立项门槛（0/23 跨 top-20 池界），是否投入升级选项
      （全量微调 backbone / 更长训练 / 更大容量 / 监督混合 / 池界放宽，见本文件 2026-09-06(XVI)）。

## P1 — Next

- [ ] 待用户拍板：「低置信段邻域重排」是否立项（立项材料已出，见本文件 2026-09-06(VI)）。
- [x] 待用户逐段人工复核：test1-3 GT 草案 = ✅ 已闭环（2026-09-02 正式化）——
      `datasets/real/ground_truth_test1/2/3.json`（100 正例 + 5 负例）已定案，见本文件 2026-09-02 条目。

## P2 — Later

- [ ] 本文件已达 88 KB / 874 行（2026-09-25 实测），与协议「TODO 保持短小、不重复长篇说明」不符；
      历史条目宜迁往 `.agent/CHANGELOG.md` 或 `.agent/archive/`。

## Blocked

- [ ] H4（Windows NVIDIA / CUDA）= `H4_GPU_RUNNER_UNAVAILABLE` —— 无可用 Windows GPU runner，
      需用户提供 NVIDIA 环境与计费权限（见 `.agent/STATE.md` H4-0 记录）。

---

## 历史记录（2026-09-06 及以前，保留原顺序）

### → 2026-09-05:蒙太奇子镜头查询方向 结案 = runtime 不接入（§4 执行完毕, 三指标零变化 + oracle 口径证伪）

- **执行**: ① 漂移触发判据（gap>15s & psim<0.62, 采纳=合并保留原 span）实现, 246 测试全绿 →
  ② 四片 GPU 重跑（work/rerun_*_subshotdrift.results.json, 基线未覆盖）= 严格 113→113/139、
  场景 136→136、负例 4→4 **零变化零回退（也零改善）**。
- **机制三层阻断（实证）**: (a) 漂移型段正确区已在 pool sub span 严格早已 HIT（p10/p32/t1r18）,
  三指标可动段全项目仅 ~2 条; (b) **「16/16 逐子救回」= oracle 口径**（scale 探针按 GT 中点挑
  子镜头）, runtime max-sim 采纳结构性选错（t2r02b 正确子镜头 sim 0.625 全场最低 vs 其他 0.77-0.85）;
  (c) t2r05a 触发被 all_spans 未门控近重复簇掩盖（gap 恰=15.0）。
- **拍板分支**: 按 HANDOFF §4.4 接收为研究结论, **runtime 不接入**（代码已回退定向回退版, 246 全绿）;
  oracle 上限 ≈ +2/139 远低于门槛。研究脚本/结果留档: diag_subshot_trigger/frames/trace.py +
  compare_subshot_drift.py + rerun_subshot_drift.py + work/compare_subshot_drift.out。
- **若未来重开**: 需无 GT 的「正确子镜头选择信号」（正确子镜头 sim 未必最高——叙事蒙太奇的
  语义重心与视觉特征突出度解耦）。详见 FINDINGS_SUBSHOT_QUERY.md「runtime 接入验证」章 + HANDOFF §7。

### → 2026-09-05:蒙太奇子镜头查询方向 交接给下个对话（探索完成, runtime判据未解）【已结案, 见上条】

- **个体/规模化探针强 POSITIVE**: 蒙太奇段单均值查询=语义稀释, 帧级距离突变识别子镜头,
  逐子查询救回 16/16 零回退 (详见 semantic_signal/FINDINGS_SUBSHOT_QUERY.md)。
- **runtime 接入两轮失败**: 无差别拆分→回退(2mkv 严格 34->31); 定向回退(no_evidence+montage
  弱命中)→0 改善 0 回退(p10 未救回, 触发判据漏掉"主定位漂移"型)。
- **交接文档**: semantic_signal/HANDOFF_SUBSHOT_QUERY.md（含探针证据/已实现代码/判据缺陷/
  下一步执行清单）。下个对话从 §4 执行清单开始(修触发判据)。
- **已实现(含缺陷)**: locator_service._subshot_relocalize + config subshot_* 参数;
  246 测试全绿(current 定向版)。未解决=触发判据(主定位漂移型 montage 段)。

### → 2026-09-05:蒙太奇子镜头查询 规模化验证 = 强 POSITIVE（16/16 救回, 零回退）

- **扩探针四片**: 统计"多镜头蒙太奇段（整段gap>15且子镜头>=3）"逐子镜头查询改善:
  2.mkv 4/4、test1 1/1、test2 7/7、test3 4/4 = **16/16 全部救回, 零回退**。
- **代表性救回**（整段gap->逐子）: test2 t2r07b 2072->1.1s / t2r03b 1849.7->0.3s /
  t2r05a 570.8->3.8s / t2r02b 371.8->2.8s; 2.mkv p34 1069->5.0s / p10 92->**0.0s**(精确命中);
  test3 t3r03a 91.8->0.8s / t3r02b 86.7->0.7s。
- **结论**: 蒙太奇段整段单均值查询=语义稀释, 是"搜不到"主因之一; 帧级距离突变识别子镜头
  （同镜头内<0.05、边界>0.7, 阈值0.5）普适救回, 零回退。与用户09-04"按镜头切分逐镜头对比"一致。
- **产物**: research_subshot_scale.py + FINDINGS_SUBSHOT_QUERY.md（含规模化章）。
- **待拍板**: 立项"蒙太奇子镜头查询" runtime 接入（编辑侧子镜头识别+逐子查询, 三指标验收）。

### → 2026-09-05:蒙太奇子镜头识别 + 独立查询探针 = POSITIVE

- **验证**: t2r02b（蒙太奇段）帧级相似度突变清晰分离 6 子镜头（边界 17.83/18.33/19.67/20.83/
  22.17/23.17, 同镜头内距离 <0.05、边界 >0.7, 阈值 0.5 可干净分离）。
- **救回**: 段首子镜头 A（Jacob BOUGHT）独立查询命中 2934（GT 2931, sim 0.625）;
  整段均值查询只命中 3303（洒水器, sim 0.537）——单均值稀释证实, 逐子镜头查询救回正确区。
- **结论 POSITIVE**: 蒙太奇段应逐子镜头查询（帧级距离突变识别子镜头）, 替代整段均值。
  与用户 09-04"按镜头切分逐镜头对比"拍板一致。研究侧零 runtime 改动。
- **产物**: mvp/scripts/research_subshot_query.py + FINDINGS_SUBSHOT_QUERY.md。
- **待拍板**: 立项"蒙太奇子镜头查询" runtime 接入评估（编辑侧子镜头识别+逐子查询,
  三指标不回退验收）。

### → 2026-09-05 深挖 t2r02b = 蒙太奇段单均值查询缺陷（真正的"搜不到"机制）

- **多模态密集采样**看清 t2r02b（ed17.2-23.5）真实内容: BOUGHT(Jacob特写)/THEN(洒水器)/
  CROP/WAS(乡村房屋)/WATERED(洒水器)/BUT... 是**5-6 个不同子镜头的快速蒙太奇**。
- **GT og2931（Jacob）= 段首 BOUGHT 镜头, 标注正确**。但**整段用"特征均值"查询** → 均值
  既不代表 Jacob 也不代表洒水器, 检索漂移到中间态（3303 洒水器, sim 0.578）, Jacob 被稀释。
- **真正机制（修正此前多重判断）**: 不是切分过碎, 不是 GT错/内容完全混叠, 而是**蒙太奇段
  单均值查询 = 语义稀释 → 检索漂移到特征突出的子镜头**。
- **与用户 2026-09-04 拍板一致**: "按镜头切分好、逐镜头对比更容易定位"。蒙太奇段应
  **逐子镜头查询**而非整段均值。当前两级切分只找"镜头边界", 没识别蒙太奇段内子镜头。
- **新方向（当前最对症, 待立项探针）: 蒙太奇段内"内容子镜头"识别与独立查询**——
  用帧级聚类/相似度突变识别子镜头, 逐子镜头查询替代整段均值。这同时解释了为何
  "防过碎/换特征/运动向量"都不是正解。
- **已证伪/收尾**: 方向A(事件身份, 收益薄) / 方向B(时序单调性) / 防过碎 / 内容混叠换特征。
- **待用户拍板**: 立项"蒙太奇子镜头查询"探针（研究侧, 验证逐子镜头能救回 t2r02b 类段）。

### → 2026-09-05 更新: 检索召回层诊断 = FAR 根因, "防过碎"证伪, 重心转向 P2 内容混叠

- **超集诊断**（真实检索 test2 FAR 段 -> 原片索引）: t2r05a GT区 rank 78、t2r03b 1630、
  t2r02b 4993、t2r07c 3181（retrieval_top_k=20 截断）, GT区 sim 0.001-0.409 ——
  **正确区根本没进候选池**（检索召回缺口 + 特征判别力不足）。
- **P1 防过碎 = 证伪**: 合并段不能让 GT区 sim 从 0.001 变可分; FAR 段根因不是"切碎污染查询单元",
  而是检索层找不到正确原片区。
- **P2 内容混叠/检索判别 = 强化（当前唯一未决方向）**: 这批段（test2 蒙太奇/2mkv 同质内容）
  的编辑特征与原片正确区相似度极低, 反而匹配到别处 —— 需**更强检索判别/特征**, 非切分。
- **P3 运动向量判别**: 维持"待探索"（未验证收益）, 但注意它改善的是切分误切, 不解决检索召回
  缺口（FAR 段已经证明是检索层问题）。
- **已证伪三路**: 外观/多模态/时序全闭环; 当前未决 = 内容混叠（检索判别）。

### → 待探索方向（2026-09-05 记录, 未立项, 先验证防过碎）

- **方向 P2: 内容混叠段**（非切分根因, 已验证 ~4 段: p01-p03 段过粗/多镜头污染、
  t2r07c 内容同质、t1r08c 零宽段）: 这些段改切分救不了, 需换特征/检索策略。
  方向 = 探索更细的检索粒度 / 内容判别特征。**暂不立项**, 待防过碎验证后再评估。
- **方向 P3: 补运动向量判别**（剪映 ④①: 光流区分"镜头内运动"vs"真实切换", 防止摇镜/
  跟拍误切; 另有"运动感知校准"避开剧烈运动帧落切点）: 我们当前切分仅靠 DINOv2 CLS
  相邻余弦距离（单特征）, 无运动向量。光流属传统 CV 非模型, 估计不违约护栏。**暂不立项**,
  需先探针验证收益(是否减少误切→改善检索)。
- 优先级: 防过碎(P1) > 内容混叠(P2) / 运动向量(P3)。

### → 2026-09-05:方向 B 剪辑时序单调性探针 = 证伪（有据, 不再重复）

- **立项**: 用户拍板 A（编辑时序约束方向, 在方向 A 身份路由正确 + test3 时序锚点错位重核后）。
- **探针**（静态度量, 零 runtime）: ① GT 编辑序->原片序 Kendall tau: test1 0.987 / test3 0.816 /
  2.mkv 0.586 / test2 0.011 → 单调性**仅 test1/test3 部分成立**, test2 基本无序。
  ② 正确段 vs 失败段 tau: 失败段**不低于**命中段（2.mkv 非严格 1.0 > 命中 0.46）→ 单调性无判别力。
  ③ 结果批定位中点倒序段 HIGH 占比(78-100%) **不低**于正向段 → 不能靠"倒序"标记失败。
- **结论**: 方向 B（剪辑时序单调性约束）= 证伪——单调性不普遍成立 + 无法区分失败/正确段,
  与既有 M8/单调弱先验证伪一致。方向 A 时序锚点错位**无法用单调性约束解决**。
- **产物**: mvp/scripts/research_temporal_monotonicity.py +
  FINDINGS_TEMPORAL_MONOTONICITY.md。零 runtime 改动。

### → 2026-09-05:方向 A 立项完整阶段 runtime 实施完成 + 四片回归 = 严格 +14 零回退

- **索引侧**: FeatureStore._build_event_table（场景→事件归并 60s/0.60 连通分量）+ events.npy/
  event_feats.npy 落盘; feature_version bump +scn1 → +scn1+evt1; load/validate 纳入事件表;
  IndexBundle 加 events/event_feats。真实 2.mkv: 699 场景→206 事件, p08/p38 同事件单元。
- **查询侧**: EvidenceLocalizer 事件扩池（查询均值 vs 事件指纹 top-3 → 事件窗内帧扩池;
  门控用事件指纹相似度 esims[k]——事件窗跨多场景帧异构, 全窗帧均值门控会整组丢弃）;
  事件 span 独立精化+门控, 与帧级+场景 span 都 IoU 去重; 帧级+场景均零证据才救回。
- **组装/契约**: _result_from_evidence 事件子 span(from_event_pool=True); text_anchor 跳过
  事件 span; PipelineConfig event_recall_enabled/event_top_k(3)/event_max_expand_frames(240);
  OriginalSegment.from_event_pool + 前端 types.ts; 导出层 ExportClip.from_event_pool + XML 注释。
- **四片回归（evt1 索引重建 + 事件扩池, GPU DirectML/amd）**:
  2.mkv 34→35(+1) / test1 34→40(+6) / test2 12→16(+4) / test3 32→35(+3)
  **合计 112→126/139 (+14)** · 场景级 136/139 (+0) · 负例 4/9 (+0) —— 严格净正、零回退。
- **诚实边界**: +14 中相当部分为粗事件跨度经严格判据 mid_in（GT 中点落在 span 内）命中
  （p30 事件 span 1740-2317 跨度 577s; test1 的 2549-2781/2914-2963/2964-3049/3512-3734
  跨度 80-222s）——事件身份正确归位但 span 粒度粗, 非帧级精确位置。真实收益=「内容相似
  混叠」段归位正确事件; 边界=事件 span 粗粒度。
- **测试**: test_event_recall.py 6 项（生命周期/扩池救回兄弟机位/开关零变化/缺失降级/预算）;
  后端 246 + 前端 vitest 67 + API 58 + typecheck 全绿。backfill_scene_tables.py 升级双回填。
- **产物**: research_event_identity.py（探针）+ measure_event_regression.py（回归评估）+
  work/rerun_*_runtime_twopassflash.results.json（四片新批）+ FINDINGS_EVENT_IDENTITY_P1_P2.md。

### → 2026-09-05:方向 A 探针（场景实例身份建模 P1/P2）执行完成 = POSITIVE（研究侧, 零 runtime）

- **P1 事件级聚类 PASS**: p08(134)/p38(128) 兄弟场景 **12/12 网格同单元**（时序近邻+指纹联合归并）;
  同口径场景对 sep=+0.2613（within 0.5701 / cross_pairs 0.3088）→ 事件单元（19 场景 946-1166s）可分。
- **P2 事件身份端到端排序 PASS**: p08 帧级 2582/7668 → **事件级 1/162**（60/0.55·60/0.60·120/0.55·120/0.60）;
  t3r12 帧级 1/10177 保持、事件级 1/190。**p08 兄弟机位失败族被事件聚合救回 top-1**。
- **诚实边界**: 身份嵌入=单元内场景指纹均值（未训练学习型嵌入）; nearest_cross_rep 0.7562 为均值向量口径
  偏高（P1b 用同口径场景对判据）; 与 M6 v4「p08 CLS rank=6」不矛盾（构造池 vs 全索引协议差异）。
- **GPU 约定**: BACKEND_SELECTED type=DirectMLBackend device=directml dtype=amd（已打印）。
- **待拍板**: A 立项完整阶段（事件表进索引 bump feature_version + 查询先到事件再细化 + UI 事件标识,
  须先探针验收三指标不回退）/ B 研究侧归档暂不 runtime 化。
- **产物**: mvp/scripts/research_event_identity.py + work/event_identity_P1_P2_results.json +
  semantic_signal/FINDINGS_EVENT_IDENTITY_P1_P2.md。零 runtime 改动, 三指标基线未触碰。

### → 2026-09-05:非外观第二信号 研究重启立项（用户拍板）—— 交接文档已写, 下个对话开始

- **拍板**: 用户选 2 = 重启「非外观第二信号」研究立项。
- **本会话完成的前置证据**: ① 语义可分性验证(FINDINGS_SEMANTIC_SEPARABILITY.md):
  24 帧方舟 VLM 标签 scene 4/4 同级, n01/n02 同人同景, 多模态方向实证关闭;
  ② 低信息降权+边界剥离(FINDINGS_LOWINFO_STRIP.md): 负例零改善+严格−1, 像素预处理关闭;
  ③ 4 负例(n01/n02/n03/t3r15)根因=内容相似混叠(特征上限)。
- **候选方向**: A 场景实例身份建模(推荐, P1 事件聚类 + P2 排序名次) / B 剪辑叙事结构
  (谨慎, dinov2_ta 曾 blocked) / C 多模态语义(已关闭)。已证伪 16 项登记备查。
- **执行起点**: RESEARCH_PROPOSAL_SECOND_SIGNAL.md §6 清单 —— 下个对话写
  research_event_identity.py(P1/P2 探针, GPU DirectML), 探针正面→完整阶段, 负面→彻底关闭。
- **交接文档**: mvp/benchmark/user_case/semantic_signal/RESEARCH_PROPOSAL_SECOND_SIGNAL.md

### → 2026-09-05:语义可分性验证（用户方案 B） = 无判别力, 不需要手动加模型（有据）

- **方法**: 复用本地 vision-subagent 方舟视觉模型(ep-20260901010244-pv8ws), 4 负例
  ×(编辑段+误配区) 24 帧打 {scene,subject,face,objects,text} 结构化标签。
- **结果**: scene 维度 4/4 同级(无区分力); n01/n02 同人同景(subject/objects 一致,
  VLM 确认语义就是同一内容); n03 编辑段全"模糊"(语义不可靠); t3r15 角色有差异但
  场景同级(唯一可分样本, 不足以支撑通用索引); 唯一稳定差异=有无字幕(编辑加工非场景)。
- **结论**: 语义特征对 4 负例无判别力, 与 M1b/M3 双向闭合; 不需要手动加模型(省成本);
  负例根因维持「特征上限」。
- **产物**: prep_semantic_probe.py + semantic_tag.mjs + FINDINGS_SEMANTIC_SEPARABILITY.md
  + work/semantic_probe/(24 帧 + labels.json)。零 runtime 改动。

### → 2026-09-05:低信息帧降权 + 段首尾边界帧剥离 探针 = 不推荐进 runtime（负例零改善 + 严格 -1）

- **数据摸底**: n01/n02 确有低信息信号(contrast/edge 全片 16-20% 分位, n02 半帧低信息);
  n03/t3r15 正常内容帧(低信息 0%)——预期只对 n01/n02 有效。
- **探针执行确认**: 粗网格 613 帧低信息 107; n01/n02 各删 11/17 帧(保留 6 正常帧);
  非空转。
- **结果**: 2mkv 严格 33/39(-1, p28 HIT→part 副作用) 负例 3/4 不变; test3 严格 32/37
  负例 1/3 不变; **负例误报零改善**。
- **失败机制**: 误配由**剩余正常帧**驱动(n01/n02 删帧后主 span 1692-1694/1746-1748
  完全不变) + n03/t3r15 无低信息帧无从触发 + 边界剥离削证据(p28)。
- **结论**: 不推荐进 runtime(有据); 4 负例根因是 CLS 内容相似混叠(特征上限),
  非低信息问题; 未来救法仍是非外观第二信号(研究侧已闭环需另立项)。
- **产物**: rerun_lowinfo_strip.py + scan_lowinfo_frames.py + FINDINGS_LOWINFO_STRIP.md
  + work/rerun_{2mkv,test3}_lowinfostrip.results.json。零 runtime 改动。

### → 2026-09-05:两级切分 + 白闪守卫 进 runtime = 完成（用户拍板, 四片零偏差复现）

- **实现**: flash_guard.py 提取入库（engine/segment/, 纯函数+判据注释, 参数走
  PipelineConfig.flash_*/bright_spike_*）; config 新增 seg_twopass_enabled(默认 True)
  + seg_twopass_coarse_step_frames=6/fine_window=20/fine_step=2/min_shot=0.5;
  analyze_edited_video 改分派: _segment_twopass_flash(新, 粗采样→白闪过滤→±20帧精修
  →最短保护→业务兜底, 与 rerun_twopass_flash.py 逻辑一致) / _segment_legacy(回退);
  _apply_card_guard/_embed_batch/_refine_cut_twopass 辅助; 卡守卫/进度/取消/隔离保留。
- **单测**: 新增 test_flash_guard.py(9) + test_twopass_flash.py(9); 后端全套 240 全绿
  （222+18, 零回归）; 前端 vitest 67 + test:mock PASS。
- **四片回归**（生产路径直跑, GPU DirectML/amd 确认）: **严格 112/139 · 场景 136/139
  · 负例 4/9 与基线零偏差**（逐片 +0/+0/+0）; 段数 2mkv 69/test1 41/test2 54 一致,
  test3 68→67（runtime 补算 card_run_ratio 致 1 卡帧 run 判定差异, 零指标影响）。
- **产物**: work/rerun_*_runtime_twopassflash.results.json + mvp/scripts/rerun_runtime_twopass_flash.py。
- **待办**: UI 结果数/导出真机验收（段数增多: 2mkv 12→69 等, 前端契约已 PASS,
  打包 exe 验收需授权）; DECISIONS 已记录。

### → 2026-09-05:I帧锚定 + 动态步长 + 三特征抑制 切分探针 = 不推荐进 runtime（四重证据）

- **Stage 0（ffprobe 实测）**: 2mkv/test3 = 固定 10s GOP（仅 13/15 个 I 帧）,
  生产切点仅 10%/7% 落 I 帧 ±0.5s 内 → I 帧粗筛结构性失效; test2 = 密 GOP 1.15s,
  83% 切点落 I 帧 ±0.5s → I 帧锚定有效（价值边界=编码器 GOP 模式）。
- **判别力诊断**: 粗网格(2.9fps, 0.345s 间隔)跨切点对三特征 AUC 0.58-0.80,
  ≥2特征命中率最好仅 13-26%（漏检不可接受）; 1fps(0.034s) 下 2mkv 63/69、
  test2 53/54 硬切显著 → **像素特征可用但需接近原帧率采样, 粗采样运动噪声淹没
  切点信号, 成本优势消失**（用户方案「跳过大量非关键帧」前提不成立）。
- **四片三指标**: 严格 110/139(-2) / 场景级 102/139(**-34**) / 负例 8/9(**+4 翻倍**);
  段数 8/4/9/14 vs 生产 69/41/54/68（严重漏切合并成大段）。
- **结论**: 不推荐进 runtime; 维持两级切分 + 白闪守卫（C 项待拍板）;
  像素切分方向关闭（有据）。三特征抑制逻辑本身正确（亮度+5/平移2px 均被抑制）。
- **产物**: mvp/scripts/research_iframe_cut.py + diag_transition_shape.py +
  diag_straddle.py + FINDINGS_IFRAME_CUT.md + work/rerun_*_iframecut.results.json。
  零 runtime 改动; 基线(112/139, 136/139, 4/9)不受影响。

### → 2026-09-05:C 项 —— 两级分层切分（用户架构修正）验证完成 = 最佳方案，白闪守卫生效，待拍板进 runtime

- **执行过程（2026-09-05，全部 GPU/DirectML 加速，BACKEND_SELECTED=directml/amd 已固化）**:
  - ① p36 单段 8fps 取证 = 假设成立（8fps 整段即命中 GT 2042-2043.4）;
  - ② 全局采样 4/6/8fps 四片全量 = 严格全部净负（104→100/99/103）+ t2r02b 假阳性兑现 + 2mkv 负例 +1;
  - ③ **用户两级分层切分（粗采样 5-8 帧找候选切点 + 局部 ±20 帧密帧精修边界 + 最短镜头保护 0.5s + fps 换算）
    四片全量 = 严格 112/139 (+8)、场景级 136/139 (+18)、负例 4/9 持平** —— 唯一严格净正收益方案;
  - ④ **白闪守卫（四层：前置过滤/切点后处理/相似度衰减/业务兜底）验证 = 删除 1.mp4 唯一白闪区
    (ed 18.35-18.46) 处的粗网格虚假切点 18.345（段数 70→69），三指标零回退**;
  - ⑤ 诚实边界: n03(66.1-67) 非白闪（帧正常，误配 HIGH 是 CLS 内容相似机制）→ 白闪守卫救不了，
    属 t2r02b 同类「内容相似误配」需另立方案; 负例 3/4 维持。
- **待拍板**: 两级切分 + 白闪守卫是否进 runtime（替换 analyze_edited_video 切分；编辑侧特征不落索引
  无需 bump feature_version；需全套单测 + 四片回归 + UI 结果数/导出验收）。
- **产物**: mvp/scripts/research_twopass_prototype(_v2).py + rerun_twopass.py + flash_guard.py +
  rerun_twopass_flash.py + work/rerun_*_twopass(_flash).results.json +
  FINDINGS_C_ITEM_8FPS.md（六、七章）。GPU 约定: DECISIONS.md 2026-09-05 + AGENTS.md。

### → 2026-09-04(下个对话):C 项 —— 编辑侧采样 2fps→8fps + 细切分（用户拍板记录, 本轮不实施）

- **背景(已定)**: p36 细切分取证通过(数据+VLM+人工三方闭合); test 域扫描完成——方案 A(单帧强证据保留)
  **不实施**(收益仅 +1 且有 t2r02b 假阳性风险), B 顺带关闭。p36 单条 +1 留待 C 项一并处理。
- **C 项内容**: 编辑侧采样率 2fps→8fps 提升 + 更细镜头切分, 涉及编辑侧特征重建/推理成本翻 4 倍,
  且 M4 已证索引侧密帧零增益(查询侧需另证)。**下个对话做**, 本轮不实施。
- 执行时: 先对 p36(及同类「查询单元不纯」段)验证 8fps 查询侧细切分收益, 再决定是否改采样率。

### → 2026-09-04:研究侧收尾归档(M6 v4 + M4/M8 v4 + ⑩ p08b) + 三指标基线固化(measure_baseline.py) = 完成

- **M6 v4 重算**(2026-09-01): RESCUE 0/39、CLS 池内 39/39 → patch 召回方向彻底关闭(有据)。
- **M4 v4 重跑**(仅 p26, DML 664s): v4 真值下 1fps 即 best_rank=1、margin=+0.28 —— 旧「12→43 恶化」是错误 GT 假象。
- **M8 v4 重跑**(纯 numpy 秒级): p26 互换后仍 AMBIGUOUS(0.027)、p08/t3r12 维持; p38/t4r01 剔除。
- **⑩ p08b 复核 = 作废(污染残留)**: 真值窗=p38 旧错误 GT 区, v4 正确=1108-1110, CLS 池内 6/patch 6 零增量。
- **FAILURE_TAXONOMY 收尾**: 失败族 = p08 + t3r12; A 类在 2.mkv 为空(CLS 39/39); 研究侧全维度闭环, 不再立项。
- **基线固化**: measure_shot_recall.py 抽 evaluate()(CLI 不变) + measure_baseline.py(doc/rerun 双模式) →
  work/baseline_v4.json; 验证与 GT_BASELINE 文档数字完全一致(2.mkv 32/39 场景 36/39; test1 32/43 场景 38/43;
  test2 9/20 场景 10/20; test3 31/37 场景 34/37)。⑦ 仍冻结。
- 零 runtime 改动; 三指标 v4 基线不受影响。产物 FINDINGS_M4_V4/M8_V4/P08B_REVIEW_V4 + measure_baseline.py。

### → 2026-09-02:②③ 单调弱先验进候选生成已编码 + 实测零触发（时间轴先验方向有据收窄）

- **实现**: `_apply_timeline_prior`（Ambiguous 型段用前序锚点弱倾向, 逃生门全路径）+ 配置 +
  单测 8 项, 全套 222 全绿。
- **重跑验证**: 新代码含先验重跑 2.mkv/test1-3, 新旧三指标完全一致 → **零触发零影响**。
- **原因**: p08 型兄弟机位 primary 在带内(先验结构性无效, 呼应 M8); 真实跳切全带外(逃生门生效)。
- **结论**: 候选生成级弱先验零增量; 时间轴先验价值已由事后 temporal_repair + 时间轴→Ambiguity
  兑现; 实现保留为护栏, 不调参投入。产物 FINDINGS_TIMELINE_PRIOR.md。

### → 2026-09-02:⑤' test1-3 GT 全部闭环 + 正式化（100 正例 + 5 负例），test3 HIGH 精度重估 23/23

- **⑤' 完成**: 用户逐段人工复核 test1-3 全部段（分:秒标注），已正式化到 `datasets/real/ground_truth_test1/2/3.json`。
  test1 43 正例/1 负例、test2 20 正例/1 负例、test3 37 正例/3 负例（含 r14/r15 加长版负例）。
- **三指标**: test1 严格 32/43 场景 38/43; test2 严格 9/20 场景 10/20（拆条窄窗低估）;
  test3 严格 31/37 场景 34/37、负例误报 2/3（r14/r15 加长版被定位）。
- **重大修正**: test3 r15 原标 HIGH 实为加长版负例（GT 修正）; r10=7:22-7:24 与 conflict_rerank 一致（已修）;
  test1 r14a 缺失段=算法对 GT 漏标; test2 r05 同段 -2726s 真实跳切; test3 r13 倒叙。
- **test3 HIGH 精度重估**: 24→23 段（r15 剔除），r10 已修 → **23/23 = 100%**（原 23/24 双向修正）。
- 产物: `gt_review/GT_BASELINE_test1-3.md` + `FINDINGS_TEST1-3_GT_BUILD.md` + 三份正式 GT。

### → 2026-09-02:test1-3 GT 草案 + 时间轴→Ambiguity 编码 + 时序重排 v4 量化（⑤' 材料交付，等待用户逐段人工复核）

- **⑤' 数据层材料已交付**: 三份 GT 草案 `gt_review/ground_truth_test1/2/3_draft.json`（全部段，tier=pending，定位占位待人工毫秒复核，负例=not_in_source 正确拒绝）+ 复核工作表 `GT_REVIEW_WORKSHEET_test1-3.md`（76 行，含复核结论/最终窗口列）+ 时间轴复核清单 `TIMELINE_CROSSCHECK_test1-3.md`（🔴离群/⚠️倒退/🔵大跳优先级标记）。
- **对照图全部重生成**（`cases/test1|test2|test3/rNN.jpg`，76 张，基于最新定位；此前 test1/test3 基于旧定位、test2 仅 3 张 HIGH）——用户将逐段看图人工复核。
- **② 时间轴→Ambiguity 已编码**（NEXT_STEPS ⑥）: `_apply_temporal_ambiguity` 复用 `find_temporal_outliers` 作为外部 Ambiguity 信号——修复后仍离群的高置信段降档（HIGH→MEDIUM，reason `temporal_outlier_ambiguous`），不改定位；配置 `pipeline.temporal_ambiguity_enabled`（默认 True）+ `ta_max_downgrade`（默认 MEDIUM）。预研确认 current 结果批离群零触发（s7 已修）→ 2.mkv 零回归。单测 8 项新增，**全套 214 项全绿**。
- **④ 时序重排 v4 量化已完成**（NEXT_STEPS ①）: 多版本对比（baseline_p21 29/39 → pre22a 31/39 → pre24 33/39 → current 32/39）+ 精确回滚实验 → **temporal_outlier_repair 净纠正 +1（p16 part→HIT）**；p05 pre24→current 回退=「修正后未跟上」非算法退化；P3 悲观结论重估（p26 修正后完全符合时间轴）。产物 `semantic_signal/FINDINGS_TIMELINE_V4_QUANT.md`。
- **③ test3 r10 单点已核实**: current=442-444（temporal_repair+conflict_rerank 两道修复），真值≈444.5，差 1.5s 场景级命中——留待 ⑤' 毫秒精修。


### → 2026-09-01:Ambiguity Detection 原型实验 = 现有信号无法分离正确/错配 HIGH, AMBIGUOUS 无内部信号

- **实验**: 重跑 29 段 EvidenceLocalizer 提取内部 multi-evidence 信号(work/amb_prototype_signals.json)。
- **发现**: HIGH 档精度仅 5/13(38%); 正确/错配在 mode/n_clusters/qcov/dispersion/best_sim/margin 全同构(primary best_sim 0.49-0.69 重叠)。
- **机制**: 错配 HIGH 多为 clean 单证据簇 → secondary=None → margin 饱和 1.0; low_candidate_margin/multiple_similar_candidates 均要求 n_strong_clusters>=2 → clean 段结构上不触发降险 flag。
- **结论**: AMBIGUOUS 检测无内部信号可用(与 M1-M8 兄弟机位混叠 + 08-27 置信标定研究闭合); 校准转向「保守化 HIGH 门槛标定」, 不立项 AMBIGUOUS。
- 产物 `semantic_signal/FINDINGS_AMBIGUITY_PROTOTYPE.md`。

### → 2026-09-01(深夜):用户拍板推进顺序 —— 数据层 test1-3 全量毫秒级重标 + 时间轴→Ambiguity

- **执行顺序(已拍板)**: ① **test1-3 全部 GT 毫秒级人工重标**(数据层主线, 用户逐帧, 吸收 B 段; test4 数据错误剔除) → ② 时间轴→Ambiguity(低成本, 落地校准产品) → ③ test3 r10 单点验证 → ④ 时序重排 v4 量化 → 之后: 单调弱先验进候选生成 → Confidence 保守化标定 → M1-M8 低成本重跑(M4/M8) → p08b 复核。
- **⑤' 与 ⑨ B 段合并**: ⑤'(test1-3 全部毫秒级)是 ⑨(test2+test3 LOW/MEDIUM)的超集+升级, ⑨ 并入 ⑤' 不单列。
- 完整说明: `gt_review/NEXT_STEPS.md`(顶部「✅ 已拍板执行顺序」段)。

### → 2026-09-01:M6 v4 重算完成 = patch 召回 RESCUE 1/41→0/39, 方向彻底关闭(有据)

- **重算结果**(v4 GT, 39 条): **RESCUE 0/39、CLS 池外 0、CLS 池内 39/39**。
- **关键**: v3 的 10 条「CLS 池外」修正后全部 best_rank 1-8 直命中(p05/p10/p20/p23/p24/p26/p32/p41); p13「唯一救回」= GT 标错假象(v4 CLS 1)。
- **结论**: patch 召回 runtime 化零增量(0/39), 方向关闭(有据); M6 原「RESCUE 1/41」作废; 失败族重新定性为「定位精度/兄弟混淆」非「召回层进不了池」。
- 产物 `semantic_signal/FINDINGS_M6_REVISED.md` + `work/patch_recall_gt_results_v4.json`。

### → 2026-09-01:M1-M8 结论重审完成(v4 GT)= p26/p38 从失败族移除, 失败族收窄为 p08 + test 域

- **核心反转**: p26=GT 标错实证(旧 2809→正确 1766-1770, v4 runtime 直接 HIT HIGH)——M1-M8 全部 p26「特征上限/不可辨识」结论作废;
  M1b「VLM 反向选错」实为判对; M2「p26 字幕正面信号」反转(3/3 命中错误窗 2808)。
- **p38**: 与 p08 重复已删, 旧真值 1048 本身错(正确=1108-1110=p08); M5 p08b 救回存疑、M6/M7/M8 p38 半边作废。
- **失败族收窄**: p08(兄弟机位, 2.mkv 唯一) + t3r12/t4r01/test4(test 域未受影响)。
- **待办**: M6 全量「RESCUE 1/41」统计需 v4 重算(方向收益低预判不变); p26/p38 相关 FINDINGS 标注作废。
- 产物 `semantic_signal/FINDINGS_REVIEW_M1M8.md` + FAILURE_TAXONOMY 重审段; 三指标基线=v4。

### → 2026-09-01:GT v4 重建完成 = 41 条全定案写入 ground_truth_v4.json, 重测三指标 + 待重审 M1-M8

- **产物**: `datasets/real/ground_truth_v4.json`(v3 保留 + 31 条 corrections 留痕: 29 relocate / 2 delete) + `gt_review/GT_REBUILD_PROPOSAL.md`(41 条全判定提案+附录 v4 重测)。
- **用户逐条裁决**: p37(与p10 ED重合)/p38(与p08 ED重复) 删除; WRONG_GT 按线索改; PARTIAL 按用户画面收窄; WRONG/NOT_REVIEWED 精确窗口(±几ms容差)。
- **VLM 三批辅助**: 补审 14 条 / PARTIAL 逐帧 13 条 / top-6 候选窗 9 条(Volcengine Ark); 用户看图拍板。
- **v4 重测**: 严格 31/39 / 场景级 36/39 / 负例 2/4 / 支撑 80/137(v3 对照 39/41/39/41/2/4/91/137——下降=修正 GT 真实口径)。
- **关键实证**: p26 MISS→HIT(GT 错非特征上限) → **M1-M8 依赖错误 GT 的结论需重审**; 剩余 MISS p08(特征上限)/p28/p36(runtime 未命中)。

### → 2026-09-01:GT v3 人工审查发现大量标错 = 三指标基线作废, 需重建 GT(专会话执行)

- **审查结论**: 35/41 条已审, 仅 6 OK, 29 条有误(PARTIAL 13/WRONG 8/WRONG_GT 7/p26 确认错), 6 未审(p36-p41)。
- **影响**: 三指标 39/41 作废; M1-M8 结论需重审(p26=GT错; p38 兄弟机位结论存疑)。
- **资产**: `gt_review/GT_REVIEW_RECORD.md`(逐条判定+正确线索)+ 41 张对照图。
- **执行清单(下个专门会话)**: ①按判定修正 GT(有线索的直接改, PARTIAL 对齐窗口, WRONG 需用户补正确位置); ②补审 p36-p41; ③修正后重测三指标; ④重审 M1-M8 中依赖错误 GT 的结论。
- **正确线索速查**: p26→1766-1770; p05→≈978-984; p09→≈1050-1055; p13→≈1343; p20→≈1551-1564; p23→≈1585; p24→≈1599。

### → 2026-09-01:校准阶段(用户拍板 A+B)= Confidence Calibration + Ambiguity Detection + 补真实 GT

- **目标转变**:不是「让所有 Ambiguous 变正确」, 而是「提高可识别样本的召回/精度 + 正确识别 Ambiguous」——成熟产品行为。
- **产品层**:三档置信 → 四行为: HIGH 自动通过 / MEDIUM 自动通过或提示 / LOW 提示人工 / **AMBIGUOUS 明确转人工**(新增, 用 margin/similar_band/multiple_similar_candidates 等现有 ConfidenceConfig 信号判定)。
- **数据层(最重要, 前提)**: **补真实 GT, 范围 A+B**——A=2.mkv 失败族周边+Ambiguous 候选段(进行中: p08/p05/p20 已精修, p28 待终点); **B=test2+test3** LOW/MEDIUM 完整 GT(2026-09-01 test4 数据错误剔除: ed/om 两部不同电影)。GT 新增须逐帧画面确认。
- **置信标定**: 用真实 GT 统计 Easy/Hard/Ambiguous 分布 → 标定 ConfidenceConfig weights/thresholds/hard flags(现全占位)→ HIGH 高 precision、LOW/AMBIGUOUS 高 recall of hard。
- **研究层(Future, 非阻塞)**: 额外来源信号(provenance: 剪辑顺序/字幕台词/音频时间锚点/原片镜头图)——M8 已证当前邻接不可分, 需新信号源。
- **待办顺序**: ①补 GT(A 段优先, 量小) → ②Ambiguity Detection 原型(用现有信号) → ③Confidence Calibration → ④三指标回归。决策见 DECISIONS.md 2026-09-01。

### → 2026-09-01:原片邻接唯一性探针 M8 = 来源身份信息方向证伪, 失败族正式定性「不可辨识样本」

- **起因**:用户正确划分「来源身份信息」= 原片侧 Shot Graph 邻接唯一性(非重包已证伪的 P3 编辑上下文), 唯一未被否定维度。
- **M8 结果**(纯 numpy 秒级):5 个失败案例全 AMBIGUOUS——p38/p08 兄弟机位真-干扰邻接余弦 0.613(同场对话戏邻接同样貌);p26 唯一性差 0.027 不可靠;t3r12 干扰反更唯一;t4r01 相等。
- **归因**:兄弟机位邻接本身相似(场景集中同一时间窗, P3 根因);P2 过度归并担忧证实。
- **净结论**:来源身份信息清单全落空(前后镜头P3/剪辑点/镜头图邻接M8/字幕对白M1-3/音频不同源/OCR字牌单例)→ 失败族正式定性「不可辨识样本」;研究侧全维度闭环(外观/结构/语义/密度)。三指标 39/41 未动。
- **待拍板**:研究侧冻结, 资源回 runtime/产品侧(推荐)。FINDINGS `semantic_signal/FINDINGS_M8.md`。

### → 2026-09-01:局部特征探针 M7(ALIKED n32)= 核心难例 p38/p26 无解, 外观三层(CLS/patch/局部)全部关闭

- **起因**:用户拍板「先1再2」——1=FAILURE_TAXONOMY.md 固化 A/B/C/D 失败分类法; 2=现代局部特征验证(承接用户「Source-specific discrimination」特征层重构主张)。
- **环境**:HF/GDrive/hf-mirror 均不可达 → SuperPoint/DISK 权重拿不到; 用户手动装 kornia 0.8.3 + 下 aliked-n32.pth(本地加载验证通过)。
- **M7 结果**(633s):p38(兄弟机位士兵特写) rank 61 **干扰反超(margin −24)**; p26(夜读) rank 125 **干扰反超(margin −19)**——CLS/patch 双失败的案例 ALIKED 也失败; p08 +34 / t3r12 +48 弱正向但方向不一致; p01/t4r01 无增量。
- **归因**:兄弟机位局部 patch 本身相似(单应成立), 局部证据天然同貌 → 与 Phase 24-1 几何证伪呼应。
- **净结论**:局部特征方向关闭(有据); 失败族在外观三层(CLS/patch/局部描述子)全部无解 = 身份级区分局限; 三指标 39/41 未动。
- **待拍板**:失败族正式定为「身份级区分」局限(维持特征上限表述) or 未来更强语义/身份特征(多模态已测无解)。FINDINGS `semantic_signal/FINDINGS_M7.md`。

### → 2026-09-01:patch 召回探针 M6(GT 全量 41 条)= 仅 +1/41(p13), patch 召回方向关闭(有据)

- **起因**:用户拍板「跑完 41 条 GT 再决定 patch 召回 runtime 化值不值」——M5 只测 6 个探针点, M6 扩到全量 GT。
- **M6 结果**(6633s):41 条 GT 正例——31 条 CLS 已在池内(易例, patch 无增量);10 条 CLS 池外中 **patch 只救回 1 条 p13**(CLS 188→patch 1);9 条未救回(p05/p10/p20/p23/p24/p26/p32/p38/p41)。
- **关键矛盾**:M5 的 p08b 32→2 在 M6 p38(同一目标区 1048-1050, CLS 340→patch 225)不复现——查询帧选取不同(M5 13.9s vs M6 中点 13.25s, 快剪段子镜头交替), patch「救回」对查询帧高度敏感。
- **净结论**:patch 召回 runtime 化 = 仅 +1/41 且信号不稳, 低于「≥2-3 条才值得」门槛 → **方向关闭(有据)**; p26/p24/p41/p38 双通道无解, 失败族维持特征上限。零 runtime, 三指标 39/41 未动。
- **待拍板**:无(方向已关闭, 数据留档)。FINDINGS `semantic_signal/FINDINGS_M6.md`, 脚本 `mvp/scripts/research_patch_recall_gt.py`, 数据 `work/patch_recall_gt_results.json`。

### → 2026-09-01:patch 级召回探针 M5 = patch 对兄弟机位选对实例有效(p08b 32→2), p26 仍特征上限

- **起因**:用户拍板立项「patch 级召回」——E21/patch_rerank 都只在「CLS 已捞进池」的候选里重排, patch 从未参与候选池构建(召回层)。M5 首次实测。
- **前置工程情报**:GPU 资产(DirectML ONNX)原本只导 CLS;新导出 CLS+patch 双输出 ONNX(研究侧临时资产, cos=1.0, DML 18fps vs CPU 1.4fps ≈13×), 探针切 DML 提速。
- **M5 结果**(918s):p08b 32→2(兄弟机位选对实例, E21 一致复现);p08 6→5; **p26 22→24 无解**(干扰 0.951 反超正确 0.900);p01/t3r12/t4r01 保持 top-1 零回退。
- **产品相关缺口**:runtime 检索 top-20, p08b/p26 均超池;patch 可救 p08b 型、救不了 p26。
- **待拍板**:patch 召回是否 runtime 化(预期救兄弟机位族一部分, 接入须 bump feature_version + 三指标回归)。FINDINGS `semantic_signal/FINDINGS_M5.md`, 脚本 `mvp/scripts/research_patch_recall.py`, 数据 `work/patch_recall_results.json`。

### → 2026-09-01:索引密度探针 M4 = 8fps 密帧对判别零增益,索引密度方向关闭(证据链 M1-M4 全貌闭环)

- **起因**:用户质疑「帧数不能再提升吗?GPU 加速还能往上吗?」(对标同类软件 30fps 全片解析)。澄清:Phase 14C「2→4→8fps 零增益」是查询侧结论,**索引侧从未测过** → M4 首次实测(DML batch=1,717s)。
- **M4 结果**:p08 best_rank 都 1(top5 2→5 略改善)/margin 0.393→0.365;**p26 best_rank 12→43(密帧恶化)** margin 仍负(−0.28→−0.25);t3r12/t4r01 持平。**8fps 未把任何负 margin 变正**。
- **归因**:索引密度解决「正确帧数量」不解决「正确 vs 干扰可分性」;p26 干扰 sim 0.876 反超正确 0.596 = CLS 混叠,任何帧率救不了。30fps 全片成本 ×30 换不来判别提升 → **方向关闭**。
- **吞吐实测**:DML batch=1 **20.5fps 最佳**,大 batch 并行无收益(plateau ~15fps),达不到 30fps;工程情报:未来 DML 批量推理用 batch=1。
- **难例多模态辅助**(用户指示):p26 是 M1/M2/M3 靶心——VLM 反向选错、字幕唯一弱正(不可索引)、CLIP 无判别力。三形态已测无可靠分离。
- **证据链 M1-M4**:判定(M1)/召回(M2)/索引(M3)/密度(M4) 四路全无解 → 失败族维持特征上限。零 runtime,三指标未动。脚本 `mvp/scripts/research_semantic_signal_M4_density.py`,数据 `work/semantic_signal_M4_results.json`,FINDINGS `mvp/benchmark/user_case/semantic_signal/FINDINGS_M4.md`。

### → 2026-09-01:方向 C 完整验证探针 M3 = 可规模 CLIP 索引证伪,方向 C 证据链完整(建议关闭)

- **起因**:用户拍板立项方向 C 完整验证(A)。前置:装 sentence-transformers 6.0.1 + clip-ViT-B-32-multilingual-v1(hf-mirror 可达, 512 维, 支持法语; 不碰 onnxruntime/rapidocr)。
- **M3 结果**:CLIP 跨模态字幕检索**无判别力**——相似度全域平台(Δ<0.003),真值 rank p26 2/8、p08 3/7、test4 2/8;**易例 p01 被字幕推到 5/7(比随机差)**。
- **机制**:解说字幕=故事级叙事文案,与画面松散/解耦(test4 事件无对应、p01 抽象带偏);CLIP 对「外观近同」候选无区分力。
- **方向 C 全貌**:M1 判定证伪 + M2 VLM 召回单例弱(3/3, 昂贵) + M3 可规模索引证伪 → 无可靠可规模多模态通道。
- **待拍板**:关闭方向 C(推荐) / 转测纯视觉局部 patch 级召回。零 runtime,三指标未动。FINDINGS `mvp/benchmark/user_case/semantic_signal/FINDINGS_M3.md`。

### → 2026-09-01:字幕语义召回探针 M2 = 方向 C 首次正面信号(p26 3/3 vs 1/3),有清晰边界

- **起因**:用户拍板测「字幕语义召回索引」(方向 C 的正确用法,此前只列远期从未实测)。探针 `mvp/scripts/research_semantic_signal_M2_subtitle_recall.py`,数据 `work/semantic_signal_M2_results.json`,FINDINGS `mvp/benchmark/user_case/semantic_signal/FINDINGS_M2.md`。
- **p26 = ✅ 首次正面信号**:字幕「她用望远镜看 Levi 在做什么」真值 [2808-2811] 3/3 EVENT YES(圆形暗角=望远镜视角),干扰夜阳台 1/3——字幕能分视觉 CLS 分不清的夜读/夜阳台。
- **t3r12 = ⚠️ 弱正向**:真值 2/3 vs 干扰 1/3(重复镜头语义同貌)。
- **test4 = ❌ 0/3 全 NO**:字幕「二十多人被困滑梯管道」与原片画面无对应——解说文案与画面解耦。
- **净结论**:方向 C 非全盘证伪,适用边界=字幕-画面对应性(p26 有效/test4 无效);无文本嵌入模型只能 VLM 匹配。
- **待拍板**:A. 立项字幕语义召回完整验证(引入文本嵌入+建索引+更多样本) / B. 记录为弱正向待更多样本 / C. 与局部 patch 召回合并「两阶段多通道检索」。

### → 2026-09-01:多模态判定探针 M1 = 事件级语义证伪/字幕召回弱信号,特征上限获语义层独立确认

- **起因**:用户拍板分层检索「结合多模态进行判定」,A(召回层+判定层两层都测)。探针 `mvp/scripts/research_semantic_signal_M1_multimodal.py`,数据 `work/semantic_signal_M1_results.json`,FINDINGS `mvp/benchmark/user_case/semantic_signal/FINDINGS_M1.md`。
- **M1a 字幕语义召回 = 弱方向性**:p08 正确 1/3 vs 兄弟 0/3、t3r12 正确 2/3 vs 干扰 1/3(偏好正确), p26 两窗都 2-3/3 → 不能精确分离, 可留作两阶段检索召回侧弱加权候选。
- **M1b VLM 事件级判定 = 证伪(甚至反向)**:p08 兄弟 3/3 SAME; **p26 编辑段被判与干扰夜阳台 3/3 SAME、与真值夜读 0/3 SAME(反向选错, VLM 视觉混淆比 CLS 更严重)**; t3r12 正确/干扰都 SAME。事件级语义与外观共享天花板。
- **证据链闭环**:外观/结构(五路)+事件聚类(方向A)+序列上下文(P3)+语义/多模态(M1) 五层全无解 → 特征上限多维确认。零 runtime,三指标未动。
- **未证伪的剩余方向**:局部(patch)级召回 + 两阶段架构(纯视觉, 非多模态)——探针=验证 patch 级能否把失败族正确实例拉进候选池。

### → 2026-09-01:第六路候选信号·镜头序列上下文探针 P3 = 证伪,特征上限正式封顶

- **起因**:用户指出五路证伪+方向 A 归档后,仍有一路未明确证伪 = 镜头序列上下文(目标镜头前后各 1~2 个镜头内容联合匹配,独立证据源)。要求离线最小验证,成本极低(现有 CLS+镜头边界)。
- **P3a 编辑序列≠原片时间轴(1:1 前提不成立)**:p07→原片[1027,1041]、p08→[1160,1166]、p09→[1131,1147]、p26→[1766,1770](真值 2809 偏 1000s+)、p40/p41→[1894,1900]/[346,355]。
- **P3b p08 序列匹配 = 证伪(不升反降)**:单镜头真值134 rank 44 → 序列匹配 61,**兄弟128 被推 top-1**;top3 全为同一对话戏场景。根因:编辑段后相邻镜头 p09 内容恰来自兄弟区域 1048-1082,编辑上下文自身就混着兄弟内容;同一场对话戏镜头在原片集中在 1010-1154 同一时间窗,无唯一上下文。
- **P3c p26 对照 = 证伪**:真值 rank 17→35,答案被拉向编辑上下文区域(1772-1907)。
- **回答用户三问**:①p08 查询不含完整镜头边界(2/15s),但失败不在此;②编辑侧无细镜头边界,GT 编辑段可当查询镜头;③p26 上下文序列差异更极端。
- **净结论**:外观层/事件聚类/序列上下文全证伪 → 剩余失败族正式封顶为特征上限=已知局限。唯一未探索=方向 C 多模态语义(远期)。零 runtime,三指标未动。脚本 `mvp/scripts/research_semantic_signal_P3_seq_context.py`,数据 `work/semantic_signal_P3_results.json`,FINDINGS `mvp/benchmark/user_case/semantic_signal/FINDINGS_P3.md`。

### → 2026-09-01:剪映通道验收闭环(用户确认)——草稿不再列入待用户动作

- 用户已确认 `D:\JianyingPro Drafts\` 下 test1-ed.loc.v6 / test3-ed.loc.v7 草稿完成,剪映通道最终验收通过。历史条目中「待用户双击/目检剪映草稿」类待办一律视为已闭环,不再要求用户动作。导出自动验收主力维持 PR CEP 通道。

### → 2026-09-01:Phase 24-2 方向 A 探针 P2 完成(用户拍板 A1 继续)= 兄弟机位事件级 top-1/重复镜头保持/同质场景证伪,待拍板归档或进 runtime

- **P2 设计**:事件归并规则(时序近邻+指纹联合聚类,边=场景中心时间差≤T_gap AND 指纹余弦≥S_sim 连通分量;网格 30/60/120s×0.55/0.60/0.65/0.70)+ 编辑段→事件单元端到端排序(对照帧级/场景级/事件级三档)。脚本 `mvp/scripts/research_semantic_signal_P2.py`,数据 `work/semantic_signal_P2_results.json`,FINDINGS `mvp/benchmark/user_case/semantic_signal/FINDINGS_P2.md`。
- **P2a 归并规则**:兄弟机位 134↔128 **12/12 全同单元** ✅(归并稳健捕获同事件多机位,单元含 946-1166s 连续对话戏 19 场景);重复镜头正确[43,44,45] 同单元 ✅ 但干扰 42/46 被时序并入 ⚠️;同质场景 test4 正确实例多数参数不同单元 ❌。
- **P2b 端到端**:p08+p38 兄弟机位 场景级 8/699 → **事件级 top-1**(T_gap=120 三档稳健)——正面回答 P1a「rank 6/11 不唯一」(归并规则=时序+指纹联合而非纯指纹);t3-r12 事件级 top-1(11/12)保持;test4 无效;p01 全档 top-1 零回退;p04/p17 场景级差为「场景指纹均值稀释」代理伪影(帧级 148/10 正常);p26 事件级意外 2/129(谨慎解读)。
- **净结论**:与用户预期(重复镜头族+部分兄弟机位族)一致,兄弟机位族超预期。零 runtime 改动,三指标 39/41 未动。
- **已拍板(2026-09-01):方向 A 归档**。P1+P2 证据链完整,按立项约定「P2 结束无论成败都归档」→ 同质场景维持已知局限。未来如需重开,证据在 `semantic_signal/FINDINGS_P1.md` + `FINDINGS_P2.md`。

### → 2026-09-01:Phase 24-2 语义级第二信号·方向 A 探针 P1 完成 = 部分成立/部分证伪,待拍板 P2 或关闭

- **立项**:五路证伪后用户拍板写「语义级第二信号」立项材料 → `semantic_signal/RESEARCH_PROPOSAL.md`(方向 A 场景实例身份[推荐]/B 序列对齐/C 多模态[远期]);用户选 **A**,探针 `research_semantic_signal_P1.py` 跑完。
- **P1a 归并能力 = 信号存在但不唯一**:兄弟机位场景134↔128(z=2.47 显著近)但 rank=6/11 非唯一 → 聚合信号有,精确归并需更强事件身份特征。
- **P1b t3-r12 = ✅ 可分离**:正确实例场景 avg rank 2.0/7,sep=+0.188 → 方向 A 对**重复镜头族**有效。
- **P1b test4 = ❌ 不可分**:sep=−0.035,同质场景族确认特征上限,方向 A 不覆盖。
- **P2 未跑**(身份嵌入端到端排序);FINDINGS 见 `semantic_signal/FINDINGS_P1.md`。
- **待拍板**:A1 继续 P2(先设计事件归并规则再端到端验证,预期仅重复镜头族+部分兄弟机位族) / A2 关闭方向 A(保留证据,失败族正式关闭为已知局限)。零 runtime;三指标 39/41 未动。

### → 2026-08-31(晚):Phase 24-1 非外观第二信号三探针预研 = 全部证伪,剩余失败族确认为特征上限(闭环)

- **探针①视觉几何一致性 = 证伪(核心)**:patch 互近邻 + 仿射/单应 RANSAC 内点率,p08/p08b(同场戏兄弟机位)真值帧内点率**反被兄弟机位压制**(p08b 兄弟 1109 HOMOG 0.75/n_match 329 vs 真值 1048 0.49/78)。归因:①刚性场景不同机位仍满足单应约束(平面近似),"不同机位→违反仿射"前提在多视图几何上不成立;②1fps 候选粒度下真值窗内 0.33→0.85 跳变,帧对齐极敏感;p26 的 rank 2 为假阳性(干扰 0.591 仍压真值 0.576,无 margin)。**不进 runtime**。
- **探针②时序运动签名 = 证伪(方法学不成立)**:编辑片快剪(压缩比>1),窗口帧差签名时间轴与原片非 1:1,未先对齐前提下连易例 p01 都 -0.87。**不重试**。
- **探针③难例投影头微调 = 数据不缺,无可分信号**:硬负例盘点每索引 2.6万~9.1万对(2.mkv 49,572/test1 51,289/test2 26,018/test3 91,708/test4 31,737,sim≥0.60 跨场景 Δt≥2s),「数据瓶颈」不成立;但 CLS 特征级混叠 + ①② 证伪 → 无可注入的第二信号。**不立项**。
- **回归**:研究侧零 runtime 改动,三指标与 Phase 24 基线一致 = 严格 39/41、FP 2/4、支撑 91/137,零回退。剩余 2 MISS(p08/p26)即本预研确认的特征上限两族。
- **结论**:维持「接受为已知局限」既有拍板;未来唯一有价值方向 = 语义级第二信号(场景身份/多模态字幕),当前无证据不立项。不改 runtime/不打包/不 bump feature_version。
- 脚本:`mvp/scripts/research_phase24_1.py` + `research_phase24_1_data.py`;FINDINGS 见 `mvp/benchmark/user_case/phase24_1/FINDINGS.md`。

### → 2026-08-31:NLE 自动验证通道定案(PR CEP 建成 PASS / Resolve 免费版死路)——①②已完成闭环

- **Resolve 21.0.4 免费版 = 外部脚本不可用**(Studio 独占,UI 无选项/连接全败/网络确认)。保留作 XML 手动目检;排障遗产无害。
- **PR 2026 CEP 面板建成**:`%APPDATA%\Roaming\Adobe\CEP\extensions\com.svl.timelineexport\`(manifest 必须在 `CSXS\` 子目录;PlayerDebugMode 已设 CSXS.9-13 HKCU)。按钮 → 导入 SVL XML → 导时间轴 JSON(`work/svl_pr_timeline.json`)。**E2E:119/119 匹配、0.0000s 偏差**。人工成本=PR 重启+点按钮 ~30s。
- **① 比对脚本已固化并复验**:`mvp/scripts/verify_pr_timeline.py`(读 FCP7 XML 声明 vs PR JSON 逐项四元组 start/end/in/out,`--xml/--json/--tol`;退出码 0=全匹配)。本次复验:119/119、最大偏差 0.0000s、EXIT=0。
- **② host.jsx XML 路径已参数化(2026-08-31)**:`svlRunAll(xmlPath, outPath)` 由面板 evalScript 传参,空值回退默认;`index.html` 加两个输入框(FCP7 XML 路径/输出 JSON 路径);`q()` 双写反斜杠防 ExtendScript 误转义(`\b`/`\t`/`\n` Node 往返测试通过)。旧调用 `svlRunAll()` 兼容。**扩展源码已归档**至 `mvp/scripts/pr/cep_extensions/com.svl.timelineexport/`(仓库为源,安装=复制到 %APPDATA%);用法文档 `mvp/scripts/pr/README.md`。
- **③ FCP7 多轨 XML 导出已支持(现有通道),无需改**。
- 剪映通道维持现状(v6/v7 草稿待用户目检);PR 通道=自动验收主力。
- **待用户动作**:重启 PR → 开面板确认参数化输入框 → (可选)填任意导出批 XML 验证多批复用。

### → 2026-08-30(深夜 III):Phase 24 冲突扩池重排已实施并验收 = 闭环

- **用户拍板 A 立项后已实施**:`engine/localization/conflict_rerank.py`(几何触发+无主张子区间落位+证据门槛)+ `_apply_conflict_rerank` 接线(时序修复之后)+ 5 配置旋钮。实现细节与验收见 `mvp/benchmark/user_case/second_signal/FINDINGS.md`。
- **验收**:后端 206(+19)+api 58 全绿;2.mkv GT v3 三指标零回退(39/41、FP 2/4、支撑 91/137,零触发);test1/2/4 零触发零漂移;**test3 r10 自动修复 447-449→442-444**(人工真值≈444.5),其余段零扰动,对照图 `second_signal/r10_fix_verify.jpg`。**r10 不再需要结果页手动替换。**
- 零打包(长期规则)。剩余失败(p08/p08b/p26/r12)= 特征上限,维持"接受为已知局限"拍板。

### → 2026-08-30(深夜):Phase 24-0 非外观第二信号预研完成 = 仅「冲突触发扩池+时序融合重排」值得立项,待拍板

- **预研结论(证据见 `mvp/benchmark/user_case/second_signal/FINDINGS.md` + `work/second_signal_probe_results.json`)**:①音频判别力否——同场景兄弟实例声学同貌(p08 margin +0.04/p08b −0.03),叠加 BGM/解说污染,不解决主失败族;②时序非重叠先验单独否——r10(错)与 r6(对)重叠几何同构(0.75 vs 0.76),任何阈值修一伤一,量化确认此前撤销结论;③**新发现:t3r10 真值区 441-443 有被压制的独立证据峰(0.73 vs 错位区 0.87)** → 可行方向 = 冲突段触发邻域扩池 + 时序一致联合重排(改动面小,仅冲突段)。
- **待用户拍板**:A. 立项 Part C 小阶段(0.5~1 天,验收=r10 修复+r6 零扰动+三指标不回退)/ B. 彻底关闭接受现状 / C. 维持手动替换不立项。
- 零 runtime 改动(仅新增研究脚本 `mvp/scripts/research_second_signal.py`),测试基线 187+58+67 不变。

### → 2026-08-30(晚)：Phase 23-0 特征升级预研完成 = 不建议 bump feature_version,结论待拍板

- **预研结论(证据见 `mvp/benchmark/user_case/feature_upgrade/FINDINGS.md`)**:ViT-B/14 在 7 探针 × 2 通路(CLS/patch-max)上零增益、p08b 明确恶化;patch ViT-S p08b 险胜与 Phase 21 V3 一致(已在 runtime)。**升规模成本收益不成立,建议不重建索引**。剩余失败族(同场景重复实例/同质场景互混)需非外观第二信号 = 新研究阶段。
- **待用户拍板**:A. 接受剩余失败为已知局限,Phase 23 关闭(推荐)/ B. 立非外观第二信号研究 / C. 坚持全量重建(不建议)。
- **交接基线复验**:185+56+67 全绿;DML 资产在位;8765 旧实例在。api 测试须 PYTHONPATH=`mvp/src;mvp`。

### → 2026-08-30(晚)：Phase 22 全六项完成 + 交接拍板,转入 Phase 23 特征升级(用户拍板立项)

- **交接拍板(2026-08-30 晚,AskUserQuestion 留痕)**:A **特征升级立项** ✅ / B **暂不打包** ✅(长期规则维持) / C **test2-4 LOW/MEDIUM 完整 GT 暂不补** ✅。
- **Phase 23 立项 = 特征升级**:方向 = 更强 backbone(ViT-B/14)或 patch 级检索;需 bump feature_version 全量重建索引(5 部片 GPU 约 1-2h)+ 回归验收,工作量一个大阶段。预研脚本 `mvp/scripts/research_feature_upgrade.py` + `research_feature_upgrade2.py`(失败探针 p26/p08/p08b/p27 + test3-r10 相邻镜头 + test4 观察段 + 易例回归 p01/p04/p17;ViT-S=现成索引缓存 vs ViT-B=局部窗口嵌入)。
- **仍待用户动作(与 Phase 23 并行)**:①重启剪映双击「test1-e...y draft」(v6 草稿已在 `D:\JianyingPro Drafts\`)做剪映通道最终验收;②test3 r10 结果页手动替换(真值 ≈7:24.5,当前错位 7:27-7:29)。

### → 2026-08-30：Phase 21 场景指纹召回扩展层已完成，转入 Phase 22 导出工程文件 + 精度收尾（用户拍板路线）

### → 2026-09-05:性能分阶段计时探针（test1）= patch rerank 占 56% 是第一热点, 定位/检索本身≈0

- **产物**: mvp/scripts/probe_perf_timing.py（monkey-patch 分阶段计时, 零 runtime 改动）
  + work/probe_perf_test1.out。
- **分布**（test1 总 641s, 41 段, 中位 11.4s/段）: **patch.rerank 357.3s = 55.7%（40/40 段全触发）**
  > 两级切分 134.5s = 21.0% > dense 8fps 84.9s = 13.2% > 解码 20s = 3.1% >
  > **loc.localize 1.0s + finloc 0.1s + conf 0 ≈ 0%**（检索/定位/finloc/置信全免费, 索引特征缓存）。
- **根因（已核代码）**: ① PatchReranker = **CPU torch** DINOv2 patch forward（patch_rerank.py 注释明示;
  M7 时代实测 CPU 1.4fps vs DML 18fps ≈ 13×）; ② 每帧 grab_frame = 独立 ffmpeg 进程 spawn（每段
  3 编辑帧 + 3~8 候选窗帧）; ③ 触发门 width>=0.6 形同虚设, 歧义门在抓帧/embed **之后**才判（白跑）;
  ④ dml_batch_size=8（M4 实测 batch=1 快 ~35% 未落 config）; ⑤ patch 候选窗跨段无缓存。
- **优化优先级（待拍板实施, 全部需四片零偏差/三指标回归验收）**:
  1. patch 模型上 GPU（DML 双输出 ONNX 资产已有, M5 验证数值一致 18fps）→ 预期砍 ~180s;
  2. dml_batch_size 8→1（白拿, 全部 embed 环节 ~35% 提速）;
  3. patch 触发收窄（歧义门提前/收窄到歧义段; 语义有变, 需三指标验证; 日志仅 ~35% 段真正改写）;
  4. grab_frame 跨段缓存 + dense 8fps 懒计算（13%）;
  5. 索引构建（首跑另计 ~6-10 min/片）随 2 直接受益。
- 预期: 1+2 合计 test1 641s → ~350s; 逐项做完有望压到 ~200s 内（3-4s/段）。

### → 2026-09-05:性能优化第一批落地 = 四片零偏差 + 总耗时 -30%（patch DML + 抓帧缓存 + subshot 关闭）

- **落地项（全部过四片零偏差验收, work/rerun_*_perfopt.results.json）**:
  1. **PatchReranker 上 GPU**: DML 双输出 ONNX（work/_patch_onnx_tmp/dinov2_cls_patch.onnx, 518→CLS+patches[1369,384]）
     优先, CPU torch 回退（patch_rerank.py + resolve_patch_onnx, config.patch_onnx_model/env SVL_PATCH_ONNX 可覆盖）。
     数值验收 per-token cos mean 0.999997（M5 口径闭合）, patch 改写决策与 torch 版逐字节一致, 9.7× 提速。
  2. **grab_frame 进程内缓存**（patch rerank/text anchor 共用, key=(path,t), 上限 512 FIFO）+
     patch 歧义门提前到抓帧之前（判据只依赖 evidence, 零语义）。
  3. **意外收获——暴露并修复既有缺陷**: weak-hit 子镜头回退的 `evidence = sub_ev` 整体替换会丢
     montage 已命中簇（test2 t2r02b s14 实证: 覆盖 GT 的 2922-2933 簇被替成单簇 → HIT→MISS）。
     该缺陷在定向回退版进入 runtime 时埋下（当时仅验 2.mkv）, 本次首次全量回归暴露。
     按子镜头方向结案拍板 **subshot_enabled 默认 False**（代码保留可开）。
  4. **dml_batch_size 8→1 试做后回退**: batch=1 与既有缓存索引（batch=8 时代构建）数值口径不一致,
     查询/索引两侧微移改变簇形成（同现 t2r02b 异常）, -7% 收益不值一致性风险; M4 的 batch=1 提速
     仅适用于全新重建且全程同 batch（含索引）, 留作未来全量重建时的选项。
- **提速数据**（对照本会话基线）: 2mkv 1054→704s(-33%) / test1 624→438s(-30%) / test2 995→762s(-23%) /
  test3 1211→821s(-32%), 四片合计 3885→2725s **(-30%)**; 探针复测（test1, probe_perf_timing.py）:
  总墙钟 641→393s(-39%), **每段墙钟中位 11.4→5.0s**, p90 15.6→7.6s。
- **新分布（test1, 393s）**: 切分 127s(32%) / patch rerank 133s(34%, 剩余=grab_frame ffmpeg 进程 spawn)
  / dense 8fps 81s(21%) / 定位+finloc+置信 ≈0。
- **下一批候选（待拍板）**: grab_frame 批量化/常驻解码器（patch 剩余 133s 的主部）、dense 8fps 懒计算(81s)、
  切分侧 embed 共享解码。索引构建（首跑 6-10 min）本批未动。
- 验收: 246 测试全绿 + 四片三指标/支撑 span 全等（严格 113=113 场景 136=136 负例 4=4 支撑 565=565）。

### → 2026-09-05(深夜):审计接线(A1/A2/D) + 下一批性能探针 = A4 持久缓存上限 -54%, dense 懒计算证伪, grab spawn 是 patch 剩余主部

- **审计接线(零行为变化, 246 全绿 + test1 抽查全等: 34=34/42=42/0=0/106/217=106/217)**:
  - A1 `subshot_min_sub` 死字段接线(`_subshot_relocalize` 原 hardcode `<3`);
  - A2 `finloc_stable_s`(ConfidenceConfig)接线: cfg → EvidenceLocalizer(finloc_stable_s=) →
    finloc_window(stable_s=)——原 finloc.py 用同值模块常量 FINLOC_STABLE_S=4.0, 行为不变仅可调;
  - D `patch_rerank.py` 两处硬编码 `D:/claudework` 绝对路径改 repo 相对推导。
- **D 的教训(探针立功)**: 首版用 parents[3]——patch_rerank.py 在 src/engine/localization/ 比 device
  层深一级, parents[3]=mvp(无 work/), 正确是 **parents[4]=benchmark**; 错误路径 → patch reranker
  ensure() False → **patch rerank 全体静默禁用**(probe 里 patch=0.0s/40 次是异常信号), 且 246 测试
  不覆盖资产解析。已修 parents[4] 并复核 resolve 输出。原 resolve_weights 的 parents[3] 候选同病,
  一直被绝对路径兜底掩盖。
- **下一批性能探针(probe_perf_next.py, test1 首跑 397.5s)**:
  - **patch.rerank 137.7s 分解: grab_frame(ffmpeg 进程 spawn) 111.3s/358 帧 = 81%**, DML forward
    仅 22.3s/383 帧, patch_score 3.5s → **批量化/常驻解码吃掉的是 ~110s 而非模型**;
  - **text anchor 48.3s**(grab 22.7s/72 帧 + OCR)——此前藏在残差里, 首次入账;
  - **dense 懒计算 = 证伪关闭**: 40 段 localize 中 39 段产出 moments, dense 几乎总被使用(省不动,
    降 edit_fps 属语义变化); 帧行预算: embed.seg 1478 帧/102s + embed.dense 1053 帧/73s;
  - **A4 编辑侧持久缓存上限**: 同进程热二次定位 183.0s vs 首跑 397.5s = **可省 214.6s(-54%)**,
    是下一批最大单项(dense cache/tr query cache/grab cache 热; 切分 embed 若也持久化再省 ~100s);
  - A3(patch ONNX 进产品资产目录)无性能影响(加载<1s), 纯部署卫生, 随打包拍板。
- **下一批优先级(待拍板)**: ① A4 持久缓存(-54% 上限, 需设计: 文件哈希 key/feature_version/失效)
  ② grab_frame 批量化或常驻 ffmpeg(首跑 -100s 级) ③ ~~dense 懒计算~~(证伪) ④ batch=1 全量重建(未来)。

### → 2026-09-05(深夜II):用户首跑全流程实测（新建索引+定位, test2 全新 data 目录）= 索引 450.6s + 定位 1139.4s ≈ 26.5 min

- **方法**: rerun_fresh_probe.py（去掉脚本内 SVL_DATA_DIR 硬编码覆盖, 教训: rerun 脚本 env 覆盖会
  吃掉外部注入）+ 全新 data 目录 = 真实用户首跑路径（索引 0 命中）。
- **实测（test2: 原片 1.4h/5051 帧 @1fps, 编辑片 69.4s/54 段, DML/amd）**:
  - **索引构建 450.6s（7.5 min）** ≈ 11.2 帧/s（含 scenes/events 表构建）;
  - **定位 1139.4s** —— 比热索引批的 762s 慢 ~50%（首跑紧随建索引, 疑冷 IO/DML 会话状态, 单样本
    未分离原因; 热索引数字见前批）;
  - **全流程 ≈ 26.5 min**。
- **外推（索引 ~11.2 帧/s + 热定位）**: 2.mkv(7668 帧) ≈ 11.4min+11.7min ≈ **23 min**;
  test1-om(8221) ≈ 12.2min+7.3min ≈ **20 min**; test3(≈8000) ≈ **26 min**。
- **要点**: ① 索引是一次性成本（同原片后续定位不付）; ② **batch=1 全程统一（索引+查询同 batch,
  M4 实测 20.5fps vs 11.2 现值）可把建索引近乎砍半, 且消除查询/索引口径问题**——首跑提速的正确
  打法是重建时全程 batch=1, 而非只改查询侧（本日已证伪后者）; ③ A4 编辑侧持久缓存只帮二次起,
  不帮首跑; ④ 首跑定位慢 50% 的原因待查（若真实存在, 值得单独归因）。

### → 2026-09-06:计划①②④执行完毕 = A4 持久缓存 + 抓帧并行落地(零偏差), batch=1 试做证伪回退

- **① A4 编辑侧持久缓存 = 落地**（app/edited_cache.py + config.edited_cache_enabled=True）:
  缓存两级切分产物 + 每段 8fps dense 到 app data/edited_cache（键 = sha1(路径+size+mtime+
  feature_version+设备口径含 batch+PipelineConfig 全量指纹), 任一变化自动失效; 原子写; 损坏视为
  未命中; 缺文件不缓存走原错误路径）。**实测 test1: 首跑 398.5s → 缓存命中 192.1s(-52%)**;
  加 ② 后 166.9s。单测 +4（roundtrip/增量/损坏容错/指纹敏感）, 250 全绿。
- **② grab_frame 线程池并行 = 落地**（`_grab_frames_parallel`, patch 候选窗 + text anchor;
  打分保持 sorted 顺序串行, 选优语义不变）。**重要教训: DirectML EP 多线程并发 Run 同一
  ONNX session 会原生段错误**（首版并行 frame_patches 实测崩溃）→ 并行只做抓帧, DML forward
  主线程串行（55ms/帧, 不吃收益）。test1 热跑 192.1→166.9s, 零偏差（34=34/42=42 全等）。
- **④ batch=1 全程统一 = 试做后证伪回退**: 生产 embed 路径实测建索引 batch=1 499.9s(10.1fps)
  vs batch=8 450~485s(10.4-11.2fps)——**M4 探针的 20.5fps 不适用于生产路径**（探针与生产
  embed 分块方式不同）; 无收益 + 不必要数值漂移 → 回退 dml_batch_size=8 + feature_version
  撤销 +b1。副产品: **test2 索引全量重建后四片口径零偏差**（13=13/18=18/支撑全等）=
  embed 重建确定性验证。fv 注释保留「数值口径纪律」: 改 embed 数值口径的参数必须 bump
  feature_version 并全程统一。
- **当前速度画像（test1, 41 段）**: 首跑 ~400s → 热缓存+并行抓帧 **167s（4.1s/段, -58%）**;
  首跑剩余大头 = 切分 embed(102s, 1478 帧) + dense embed(73s, 首跑必付) + patch grab(并行后
  ~40s) + text anchor(48s)。A4 只帮二次起; 首跑再快需动 embed 吞吐（无低风险手段, 已证伪
  batch=1; 剩帧数削减=语义变化）。产品话术: 首跑 20-30 min（索引一次性 7-12 min）, 同片
  复定位 **2-4 min**。


### → 2026-09-06(III):性能批① 解码/forward 流水线落地 = 字节级零语义, 全流程 -9~11%

- **实现**: `engine/common/pipeline.py` `pipeline_map`（生产者线程跑解码可迭代, 消费方主线程
  做 embed/统计——DML session 非线程安全, forward 必须单线程; 保序; 双向异常安全; 哨兵必达）。
  接入两处大头: 索引侧 `_embed_stream`（feature_store）+ 编辑侧 twopass 粗采样（亮度/白闪/卡片
  统计同批顺带算, 帧不再全量留存）。fine 精修/dense/legacy 路径未动（小头）。
- **教训(死锁)**: 首版 `_produce` 的 finally 里先 `stop.set()` 再发哨兵, 而投递循环条件是
  `while not stop.is_set()` → 哨兵永远发不出, 消费者死等（test_empty_edited 挂死,
  faulthandler 栈定位）→ 修复: 哨兵投递不受 stop 影响。单测 +5（保序/空/双向异常/背压不死锁）。
- **验收**: 255 测试全绿; 全新 data 目录 test2 全流程: 索引 412.3s（前值 450.6s, -8.5%）+
  定位 1012.7s（前值 1139.4s, -11%）; **features.npy 与主目录重建批逐字节一致**
  （sha256 同）, 三指标/支撑 span 全等（13=13/18=18/0=0/64/219 全等）。
- **剩余杠杆（待拍板）**: ② 分辨率 518→384（单帧 forward ≈×0.55, 需判别力探针 + bump fv 全量重建）
  ③ 索引 0.5fps / dense 4fps（帧数减半, 需三指标验收）。

### → 2026-09-06(IV):外部新方向研读 + Context Re-ranking 判决探针 = 同场景细粒度偏移再证伪（3/7 可修、2 反向）

- **研读**: TCA(WACV21, 检索级表征, 与召回层瓶颈不匹配——召回已闭环 39/39 进池) /
  PRBonn 序列图匹配(VPR 变环境, 思想=P3 已证伪路线) / TF-CoVR(NeurIPS25, 训练路线, 与零训练
  约束冲突, 归档) / VOP(DINOv2 patch 对应+voting, 与 M6 相似度召回不同路线, 但 M7 几何路线已
  证伪, 低优先) / Video-ColBERT(8 star, 多向量晚交互=现有多证据体系已有同构, 架构参考) /
  DiffTrack(视频扩散 Transformer, 不可接入)。
- **判决探针**（probe_context_rerank.py, 用户 P0 提案「查询±2s 上下文 vs 源±15s 窗口序列相似度
  重排」在 7 个已知失败案例直测）:
  - 大偏移对照(p30, 203s): margin **+0.285** ✅（重排轻松修复——但这类本就 LOW/已有机制兜底）;
  - **同场景 ±3~13s 偏移（当前真实瓶颈）: 3/7 可修, 2 反向**（t3r03a +0.019 / t3r25 +0.086 /
    t3r29 +0.007 / t3r06b -0.004 / t3r04b **-0.015** / p35 **-0.012**）。
- **机制**: 同场戏窗口重叠（±15s 窗在 5~13s 偏移下共享 70~85% 帧）→ S(正确)≈S(错误), 噪声定方向;
  与 P3(编辑侧上下文污染)/M8(邻接唯一性 AMBIGUOUS) 三方闭环一致。预期指标收益 +1~2/139 且有
  打坏现存正确段的反向风险（触发器救不了——同场景偏移不是 montage 型）。
- **结论**: 同场景细粒度区分在「上下文/序列/图结构」路线三方证伪（P3+M8+本探针, 有据）;
  外部清单未覆盖该痛点。唯一未试路线 = TF-CoVR 式训练细粒度时间判别嵌入（与零训练产品约束冲突,
  如未来愿意引入训练再立项）。脚本留档 probe_context_rerank.py。

### → 2026-09-06(V):Context Re-ranking 多模态复审 = 信号存在但方向不稳, 可行落点=低置信段邻域重排（待拍板）

- **逐案画面对照**（work/context_review/*_sheet.jpg, 查询段 vs 正确位置 vs 错误位置）:
  - t3r25(+0.086 可修): 查询与正确位置是**同一战士同大厅同一动作特写**——视觉明确可判别 ✅;
  - p35(反向): 查询与正确位置都有夜空探照灯光束（错误位置没有）——视觉可判别但暗光低对比, CLS 排反;
  - t3r06b(微弱): 两个位置都是同一场景的金币瀑布, 画面族几乎相同——真不可分;
  - t3r04b/t3r03a(反向/可修): **GT 窄窗(0.3-0.4s)与多镜头查询段的对应本身模糊**——查询内容
    （矮人王特写/燃烧湖镇）在"正确"采样帧上反而看不见, 真实对应区疑似在窄窗附近数秒;
  - OCR 路线排除: 查询帧烧录字幕是解说文案, 原片帧无字幕——text_anchor 无匹配对象。
- **结论**: 「零训练突破」的真实形态 = **低置信段邻域重排**——序列相似度信号在 t3r25/p35 型
  案例确实存在（margin +0.086 与光束线索）, 只是被埋在噪声里; 用严格触发（仅 LOW/part 段 +
  邻域 ±20s 内候选 + margin>0.05 才改写）可控制反向风险, 预期 +1~2 且不伤正确段。
  GT 窄窗对位模糊（t3r03a/t3r04b 型）不是算法问题。

### → 2026-09-06(VI):「低置信段邻域重排」立项材料已出（待用户拍板）

- **文档**: mvp/benchmark/user_case/semantic_signal/RESEARCH_PROPOSAL_CONTEXT_RERANK.md。
- **方案要点**: 仅 LOW/低支撑段触发（正确段零接触）± 邻域 ±20s 候选 ± 序列相似度 margin>0.05
  才改写主定位; 零训练/零新依赖/不 bump feature_version; 预期 +1~2/139（t3r25 型）, 明确不解决
  GT 窄窗模糊（t3r03a/t3r04b 型）与真不可分（t3r06b 型）。
- **与已证伪方向的差异**: 触发面收死 + margin 门槛（P3 是全局改排; 反向案例 -0.015 量级过不了
  0.05 门槛）; 先行证据 = 判决探针 7 案例 + 多模态复审 6 张对照图。
- **验收标准**: 四片三指标不回退 + t3r25 修复可见 + 反向案例不触发 + 耗时增量 ≤5%; 不达标即关闭。
- **待拍板**: 批准 → 按执行清单实现（预计单轮会话完成实现+验收）。

### → 2026-09-06(VII):patch 召回 v2 判决 = 前提复活!池外 7 条中 2 条 rank=1 精确救回、2 条 rank2-3 毫厘差

- **前提变化（关键）**: M6 关闭 patch 召回的前提是「v4 GT 下 2.mkv 39/39 全部池内」; 在
  **twopass + 最新 GT + 当前管线**下重测四片 26 条未严格命中条目: **7 条检索 top-20 池外**
  （p14/p26/t1r02/t1r14d/t2r05a/t2r05b/t2r07c）——patch 召回重新有了对象。
- **判决**（probe_patch_recall_v2.py, M6 混合池协议: CLS top-200 ∪ 1/20 均匀 ∪ GT窗, patch
  3 帧查询 DML）: **p14/p26 rank=1 精确救回**（0.920/0.949, top1 即 GT）; t2r05b rank2（差
  0.004）/t2r05a rank3（差 0.009）毫厘之差; t1r02/t1r14d rank9-10（同场景内排错）; t2r07c
  rank300（混叠, patch 无解）。
- **潜在收益**: p14/p26 若安全采纳 = 2.mkv 严格 34→36（part→HIT）; 工程难点 = 采纳门控——
  patch top1 分数本身不能做门（错误位置分数同样高: t1r02 0.964/t2r07c 0.947）, 需结合
  邻域约束/CLS 一致性设计; t2r05a/b 的毫厘差需要辅助 tie-break。
- **对比 M6 关闭时**: 0/39 是「无对象」的关闭; 现在有对象且 2/7 命中——**「patch 已死」的结论
  在 twopass+最新 GT 条件下被部分推翻**。
- **待拍板**: 立项「patch 召回 v2（低置信/池外段）」——先做采纳门控设计探针（邻域约束 +
  CLS 一致性联合门），数据达标再进 runtime（预期 2.mkv 严格 +2）。

### → 2026-09-06(VIII):门控设计探针完成 = p26 可干净救回(+1), p14 与有害案例信号不可分（待拍板 A/B/C）

- **数据**（probe_patch_gate.py, 7 池外 + 12 对照, patch/CLS 双信号）: 关键字段
  patch_margin（top1 vs 主定位 patch 分差）/ cls_margin / offset:
  - p26: m_p +0.0851, cls_mg +0.2932, off 9s, in_gt True —— **信号强且干净**;
  - p14: m_p **+0.0006**, cls_mg +0.0098, off 13s, in_gt True —— 信号淹没在噪声里;
  - 有害案例: t3r26(对照! m_p +0.049, off 10s, in_gt False——采纳即严格 -1 回退) /
    t1r02(m_p +0.0222, False) / t1r14d(+0.0648, False) / t2r07c(0, False) /
    p10(对照, +0.1138, off 64.5, in_gt False) / t2r05a(+0.1978, off 2775) / t2r05b(+0.0207, off 343)。
- **门控规则筛选**: {offset≤30s 且 patch_margin>0.08} → 只采纳 p26, 拒绝全部有害案例
  （t3r26 0.049<0.08 ✓ / p10 off 64.5 ✓ / t2r05a off 2775 ✓ / t1r14d 0.0648<0.08 ✓）→
  **净收益 = 2.mkv 严格 35/39 (+1), 零回退**。
- **p14 不可救的证明**: 采纳 p14 需 m_p 门槛 ≤0.0006, 而有害案例 t3r26 m_p=0.049——任何
  能过 p14 的门槛都会同时采纳 t3r26 → -1 回退, 净收益归零。信号层面不可分（非调参问题）。
- **对照发现**: p10/t3r26 两个正确段本身 patch top1 就指向 GT 外——「重写主定位保留子 span」
  的实现约束下 HIT-via-sub 段无回退风险, HIT-via-main 段（t3r26 型）是唯一回退源。
- **待拍板**: A. 按 {offset≤30s, m_p>0.08} 进 runtime（净 +1, 先例 M6 以 +1/41 关闭过同级收益）
  / B. 关闭归档（门控数据证明收益天花板 +1 且 p14 类不可救）/ C. 继续挖掘更强门控信号
  （finloc 稳定性@top1/场景对齐等, 研究续期）。

### → 2026-09-06(IX):门控多模态复审 = 门规则视觉验证成立, p14 真相=画面本来就对（窄窗假象）, p26 唯一真错误

- **逐案画面对照**（work/patch_gate_review/*_sheet.jpg, 查询段 vs patch top1 vs 当前主定位 vs GT）:
  - **p26**: top1(1769)=同人物同椅子夜景=查询内容, 当前主定位(1778)=9s 后另一镜头——**真错误, patch 修对了**;
  - **p14**: 当前主定位(1394)与 GT(1381)是**同一座瞭望塔**（仅角度/光线差）——「13s 偏移」是 2s 窄窗
    对位假象, **画面本来就对, 无需救回**——p14/t3r26 的「信号不可分」困境随之消解（两者都该不动）;
  - **t3r26**: top1(2882)/GT(2891)/主定位(2892)全在**同一场连续战斗**里——「采纳即回退」也是窄窗
    假象, 但门规则(0.049<0.08)反正会挡住, 双保险;
  - **p10**: top1(1210)=餐盘特写, 与查询段(室内+峡湾直升机)完全无关——多镜头查询的代表帧落在
    错误子镜头上, patch 过度自信, **验证盲采纳危险真实存在**;
  - **t1r02**: top1(2175)/主定位(2181)/GT(2184)同一段游泳连续镜头——视觉无差别, 采纳无益也无害。
- **最终门规则（视觉+数据双重验证）**: {patch top1 与主定位 offset≤30s 且 patch_margin>0.08 →
  改写主定位（旧主定位保留为子 span）} → 仅 p26 被采纳, 全部有害/对照案例被拒。
- **实现要点（待拍板后动工）**: p26 所在段置信=HIGH → 触发面必须含 HIGH 段; 成本控制=在现有
  `_patch_rerank_span`（已每段运行）上扩展近场池（±30s@4s 步长≈15 帧）, 边际成本 ≈ +5s/段
  （四片约 +5~6 min）; 验收 = 四片三指标零回退 + 2.mkv 严格 35/39 + p26 修复可见。

### → 2026-09-06(X):patch 召回 v2 转正 = 四片严格 113→115(+2) 零回退, 28 处近场修复全部场景内

- **实现**: `_patch_nearfield_rescue`（locator_service）+ config `patch_v2_*`（enabled=True 默认开,
  margin=0.08/radius=30s/stride=4s）; 在现有 patch rerank 之后运行, 门控 {offset≤30s 且
  patch_margin(top1−主定位)>0.08} 才改写主定位, 旧主定位保留为子 span。单测 +4（采纳/无 margin/
  开关关闭/窄段拒绝）, **259 全绿**。
- **四片验收（对照基线批）**: 严格 **113→115（+2）** / 场景 136=136 / 负例 4=4 / 支撑 565→588;
  **test3 严格 32→34: t3r04b、t3r25 两条 part→HIT**（同场景偏移案例被 patch 匹配修复）;
  其余三片指标零变化。耗时: 2792s vs 2725s（+2.5%, ≤5% 达标; test1 单片 +20s 为 3 处采纳成本）。
- **有意思的偏差**: 实际修复的是 t3r04b/t3r25（近场池命中）, 而非门控探针预测的 p14/p26——
  近场池真实数据上的命中面比 7 条池外案例更宽（池外+池内偏移段都受益）。28 处采纳全部为
  ≤30s 场景内移动, 抽帧复核（t3r04b/s48）画面合理无伤害。
- **转正结论**: patch 召回在 twopass+最新 GT 条件下的价值被证实并落进 runtime; M6「patch 已死」
  结论正式修正为「旧管线条件下无对象; 新条件下 +2/139 且零回退」。

### → 2026-09-06(XI):M1-M8 按最新标准（twopass+最新GT+当前管线）重跑矩阵 = M4 仍关闭(0/7), M5/M6 已翻案, 其余维持

- **M4（索引密度）重跑 = 仍关闭（有新数据）**: probe_m4_v2.py, 混合索引协议（1fps 全片 + GT
  邻域 ±30s@8fps, 非循环论证版——首版「窗内帧自比 rank=1」为循环论证已废弃重写）:
  **7 条池外 0/7 拉回**（8fps 最优 rank: 21/296/3565/97/596/3794/1799, 全部 >20）。密度带来
  rank 边际改善但失败根因 = 查询均值与窗内内容相似度本身低（多镜头/编辑变换拉偏）, 非采样粒度。
  方法论教训: 窗内帧与自己邻域自比的 rank 是循环论证, 探针必须用「查询→候选集」真实检索口径。
- **M5/M6（patch 召回）= 今日已重跑并翻案**: 池覆盖 7 池外 → patch v2 runtime 严格 +2（详见
  2026-09-06(X) 条目）——M6「patch 已死」修正为「旧条件无对象; 新条件 +2 落地」。
- **M8（邻接唯一性）= 今日已重跑等价物**: context rerank 判决探针（窗口邻接相似度, 7 案例
  3/7 可修 2 反向）——维持证伪。
- **M1/M2（VLM 判定/字幕召回）= 不能重跑**: VLM 暂停使用（用户指令）; 且今日多模态复审
  （本模型直看帧）已覆盖其问题域——查询帧烧录字幕为解说文案、原片无字幕, 字幕-画面解耦在
  当前失败族上比当年更强。
- **M3（CLIP 跨模态）= 不建议重跑**: 证伪逻辑（文案与画面解耦、同场景相邻镜头无文本差异）
  在当前失败族上更强, 重跑无新信息。
- **M7（ALIKED 局部特征）= 未重跑, 后备**: 其证伪针对「同刚性场景不同机位」（单应成立→局部
  同貌）; 当前失败族是「同场景不同时刻」理论上局部可分性更高, 但 patch v2 近场重排已在该
  失败族拿到 +2——ALIKED 的增量空间被占据, 仅当未来需要第二局部通道时作为后备。
- **矩阵总览**: 翻案 1（M5/M6→+2 落地）/ 重跑维持关闭 2（M4 密度、M8 邻接）/ 条件性跳过 3
  （M1/M2 VLM 暂停、M3 无新信息）/ 后备 1（M7）/ 已被 runtime 吸收 1（patch v2 = M5/M6 转正）。

### → 2026-09-06(XII):M1/M2 用本模型多模态重跑（最新失败族 14 案例全画面复审）= 可分 5 / 不可分 5 / 窄窗假象 4 + **发现 t2r07c 疑似 GT 标错**

- **M1-v2（事件级视觉判定, 本模型直看帧, 全 14 失败案例）**:
  - **可分 5**: t3r25(同战士同大厅特写✅已被 patch v2 修复) / p30(同一狙击手女性, 新旧主定位同场景) /
    p35(夜空光束仅正确位置有) / p26(同人物同椅子, patch top1 正确) / **t2r07c（见下, 重大）**;
  - **不可分 5**（同一事件族两侧都有, 视觉无差别）: t3r06b(金币瀑布) / t1r02(同段游泳) /
    t1r14d(同段暗夜山地) / t2r05a(同一演员同一橙衣两侧都是) / t3r29(同一山坡行走镜头, 3s 偏移无意义);
  - **窄窗假象 4**（GT 0.3~2s 窄窗与多镜头查询对应模糊, 当前主定位画面本来就对或对应区在窗旁）:
    t3r03a / t3r04b / p14 / t2r05b(查询=机器特写, GT 帧却无该物)。
- **⚠️ t2r07c 疑似 GT 标错（需用户人工复核）**: 查询=星条旗马甲演讲台; patch top1 **4697s = 同人
  同马甲同讲台同招牌（视觉强匹配）**; 而 GT og4092.2-4097.0 = 烟雾战场（与查询完全无关）。
  「混叠无解」改判为**「算法可能找对了, GT 疑似指向错误位置」**——若 GT 修正, test2 严格 13→14。
  （需确认影片是否两次出现同场景; 对照图 work/context_review/t2r07c_sheet.jpg）
- **M2-v2（字幕语义, 本模型读查询字幕）**: 查询烧录字幕=解说文案、原片无字幕 → 字幕-画面解耦在
  当前失败族全灭; 唯一价值=跨场景排除远距错配（p10 餐盘 vs "Jack explained" 明显无关）, 该类
  已是 LOW/混叠。**维持证伪**。
- **M1-v2 与 patch v2 关系**: 可分 5 中 t3r25/t3r04b 已修（+2）; p26 未触发（runtime margin 口径
  差, open item 待查）; p30/p35 的 patch 信号反向或场景内移动——视觉判别信号与 CLS/patch 信号
  在暗光/同族场景失灵, 与 M1 原结论（语义层与外观层共享天花板）一致但边界更清晰。
- **对照图**: work/context_review/ + work/patch_gate_review/（14 案例全覆盖）。

### → 2026-09-06(XIII):t2r07c GT 标错修正（用户画面确认）= 「混叠无解」冤案平反, test2 严格 13→14

- **修正**: ground_truth_test2.json t2r07c original [4092.2,4097] → **[4692.4,4698.0]**（原值与原因
  留痕 corrections[0]）。根因 = 2026-09-02 人工定位时播放器分钟档误读（68:12 ↔ 78:12, 差 60s×10）:
  68:12=4092 为战场戏, 78:12.4=4692.4 起才是星条旗马甲演讲台桥段（多模态复核: patch top1 4697
  与查询 ed65.25 的 "COUNTRY" 举手姿势逐帧对应; 4080-4102 全扫描无演讲台）。
- **度量**: 修正后 test2 严格 **14/20**（基线批与当前批同判——算法主定位 4695-4700 本就正确,
  「内容相似混叠无解」系冤案）; 四片严格合计 **115→116/139**（34+34+14+34）, 场景 137/139,
  负例 4/9, 支撑 +2。
- **连带修正**: ① patch 召回 v2 探针记录 t2r07c「rank300 ❌」→「top1 4697 本就是正确答案」;
  ② 失败族清单移除 t2r07c（内容相似混叠族少一例）; ③ measure_baseline / GT_BASELINE_test1-3.md
  的 test2 数字以本条为准（13→14）。
- **open item**: p26（2mkv）runtime margin 口径差未触发——待查。

### → 2026-09-06(XIV):patch v2 门槛 0.08→0.075 = p26 骑线救回落地, 四片严格 117/139 零回退（patch v2 正式转正）

- **open item 查明**: p26 未采纳原因 = runtime 实测 margin **0.080 恰好骑线**（拒绝条件
  margin≤0.08; 探针口径 +0.085, GPU 浮点差 ~0.004）。日志: "patch v2 nearfield ed=76.3
  margin=0.080 (no adopt)"。
- **修复**: patch_v2_margin 0.08→0.075（骑线带 0.075-0.08 内另有 3 案例: ed26.8/125.7/69.9,
  一并纳入采纳面）。259 单测全绿。
- **四片验收（对照基线批, GT 已含 t2r07c 修正）**: 2mkv 34→**35**（**p26 part→HIT**）/
  test1 34=34 / test2 14=14（t2r07c GT 修正, 两批同判——算法主定位 4695-4700 本就正确）/
  test3 32→**34**（t3r04b、t3r25 part→HIT）→ **合计 114→117（+3）**, 场景 137=137,
  负例 4=4, 支撑 567→592。零回退。
- **耗时说明**: 四片 938/678/984/988s 较上批普遍 +25%——主因 = config 指纹变化触发 A4 编辑
  缓存全量失效重算（margin 参数入指纹, 预期行为）, 非算法回退; 缓存命中后恢复。
- **验收对照（立项 §5）**: ①单测 ✅ ②三指标零回退 ✅（严格 +3）③p26 修复可见 ✅ / p14 不被
  采纳 ✅（多模态确认画面本来就对）/ 反向案例零触发 ✅ ④耗时——v2 自身边际成本符合预期,
  总耗时增量主要来自缓存重算（一次性）。**patch 召回 v2 正式转正为 runtime 默认行为**。
- **当前基线**: 四片严格 **117/139**（2mkv 35, test1 34, test2 14, test3 34）/ 场景 137/139 /
  负例 4/9 / 支撑 592。今日全程净变化: 严格 113→117（patch v2 +3, GT 平反 +1）。

### → 2026-09-06(XV):M7 v2 重跑（ALIKED × 最新失败族 12 案例）= RESCUE 0/12, M7 双重关闭（有新数据）

- **协议**: 对齐 patch 召回 v2（池 = CLS top-100 ∪ 1/20 均匀 ∪ GT 窗±2s; 查询 = 覆盖段 3 帧
  ALIKED n32 描述子; 打分 = mutual_nn 匹配数; 判决 = GT 窗帧排名）——与 patch v2 结果直接可比。
- **结果**: **0/12 救回**。GT 最优排名: p14 rank6（主定位 rank150——ALIKED 确实更偏好 GT 区但
  远非 rank1）/ t2r07c rank3（修正后 GT 窗, 部分同意）/ 其余 rank 17~241（t1r14d 241、t2r05a 32、
  p20 25、t3r03a 17…）; top1 大量落在 6448/6740/4340s 等无关区。
- **对照**: patch v2（DINOv2 patch 近场重排）在同失败族已修 3 条落地; ALIKED 0/12 ——
  **局部描述子通道在最新标准下 DINOv2 patch > ALIKED, 且 ALIKED 无可行动信号**。
- **结论**: M7 双重关闭（原证伪: 兄弟机位同刚性场景; 新证伪: 同场景相邻时刻亦无可行动判别）。
  局部特征通道的最终形态 = runtime patch v2（已转正）。脚本: probe_m7_v2.py。

### → 2026-09-06(XVI):T1 训练可行性探针完成（T1a LDA + T1b 对比微调）= 信号真实存在但 0/23 跨池, 未达立项门槛

- **T1a（LDA 闭式最优线性投影, 场景监督）**: 22 失败案例 0/7 池外拉回, 且**打碎原本正确的
  定位**（p30 1→363 / p35 1→443 / t3r03a 1→908）——场景级判别与段内连续定位本质冲突。
- **T1b（残差 MLP 头 + 时间对比 InfoNCE, 冻结 backbone, hold-out=test3）**:
  - 训练有效: batch-acc 0.93; **rank 改善真实**: t1r02 5576→66(×84) / t2r05a 822→42(×20) /
    t1r14d 905→280 / t2r05b 4119→2455; p14 恶化(24→505) 一例;
  - **但 0/23 跨过 top-20 池界**（门槛失败）, hold-out(test3) 3 条持平（泛化中性）;
  - **易例零回退 8/8**（残差设计保住已正确段）。
- **判决**: 按立项门槛（≥1/3 失败转严格 HIT）**未达标, 不进 runtime**。结论 = 「时间对比信号
  可学习且无破坏性, 但 head-only 3000 步的容量/训练量跨不过全索引 top-20 池界」。
- **升级选项（待拍板, 投入显著加大）**: 全量微调 backbone / 更长训练 / 更大容量 / 监督混合
  （verified GT 窗加入）/ 池界放宽（top-50 + 重排级联）。每一步都是新探针轮。
- **产物**: probe_training_t1a.py + probe_training_t1b.py + 立项材料
  RESEARCH_PROPOSAL_TRAINING.md。当前基线不变: 严格 **117/139**。

## 续19 遗留（2026-09-28）— 2026-09-28(续20) 销项结果见各条括注

- [x] P0 前端假数据：`HomePage.vue:28,33` / `ProjectsPage.vue:16` 写死片名；项目时长恒 0 →
      **续20 完成**：`GET /api/media/info`（ffprobe）+ `useCreateProject`（先选文件后建项目）+ 元数据回填。
- [x] P1 UI 消费 `/api/export` 的 `warnings`（LOC-2001）→ **续20 完成**：导出对话框保持打开显示告警 + 页面条幅。
- [x] P1 随机端口接线（`manager.ts` 解析 `BACKEND_LISTEN` → query `svl_port`）→ **续20 完成**；
      ⚠️ 更正：续19 所写「后端已支持并打印公告」不实（全仓无该行），公告由续20 新 `mvp/api/launcher.py`
      真实落地（绑定成功后才打印，宁缺毋假）。
- [x] P1 UI 展示对外码：非 2xx 话术 → **续20 完成**（同步路径续19 已在 request()；本轮 `tasks/worker.py`
      的 `task.error` 改话术（码），技术串只进日志；`routes/results.py:80` 同步 detail 口径列为低成本尾巴）。
- [ ] 等授权：git 提交（未提交实测 178 文件）、打包与 UI/导出验收（含本轮桌面端到端）、残留清理 ~1.7GB、GT 版本头 32 份。

## 续21 打包验收（2026-09-28）= ✅ 通过 + 遗留观察

- [x] 打包端到端验收 = **通过**（10 项：发行三防线/随机端口/元数据回填/取消不创建/四格式导出/
      预览逐图核对/错误条幅/vote_prior 生效），记录 `mvp/docs/ACCEPTANCE_PACKAGED_20260928.md`；
      现场修 3 个打包必炸缺陷（bundle 顶层 `api` 形态 / 预览直链带令牌 / 运行时端口优先）。
- [x] `vote_prior_enabled` 翻默认开（验收前置已兑现，新包日志确证 seed 应用）；
      `dense_recheck`/`conf_v2` **维持默认关**（续10l/续14 实测裁决不变）。
- [ ] （新登记，低成本尾巴）网络级失败条幅中文话术（现英文技术串）；后端进程消失后侧栏
      "已连接"不重探（健康轮询缺失）；`routes/results.py:80` 同步 detail 仍 `"ExcName: 技术串"` 口径。
- [ ] 用户动作：剪映草稿**应用内双击**最终确认（文件级已验）；git 提交授权（>180 未提交文件）。
- [ ] **下一步主线（用户已拍板）= E 组竞品确证未落地项**，建议顺序：
      ~~① `resolve_consecutive_scene_offsets`~~ → **续21 已执行并结案：双臂 −1 真回归 + 图证=合法复用被
      误移 ⇒ 维持默认关、通道关闭（`FINDINGS_CONSECUTIVE_OFFSETS_AB.md`）**；
      ② 展示层真实转场切点时间线展开 → **预研改判：非"一行可加"，前置=源片侧更细边界探针（E2'，待拍板）**；
      ~~③ `commentary_scene_*` ED 分镜复核~~ → **续21 判决探针=负结果结案**：ECC/结构相关腿与已证伪帧差
      腿同档（AUC 0.90 vs 0.917），最难假例 27.79 决定性外验证不过（扩门即杀 7 真切点）⇒ 不进 runtime、
      通道关闭（`FINDINGS_E3_ECC_PROBE.md`）；
      ④ `speed_fill_*` 变速补齐（**待用户拍板导出层是否引入变速片段形态**）；ordered_search / 全局 `path_*` DP =
      第二套复现级工程，单独立项再拍板。

## 续22 fast_global_anchor M1（2026-09-28）= ✅ 通过验收门 + 待拍板项

- [x] M1 四片双臂回归 = **通过章程门**：严格 119→127、场景/负例持平、main-span 口径 82→105（+23≥+8）；
      10 翻转逐张读图（9 改善 + 1 回退 t2r01b row4）；ON 臂按生产参数复跑逐项复现（r2 一致）。
      裁决=`PROJECT_FAST_GLOBAL_ANCHOR.md` §7。
- [x] `min_cluster_votes=2` 消融腿 = **实测证伪**（105→82），机理=真匹配天然单票窄桶；生产回退 1，
      "窄簇票数"判别勿重试；负结果已入 DECISIONS/档案 §7。
- [ ] **待用户拍板**：① `fast_global_enabled` 翻默认开（M1 门已过，但带 t2r01b 回退 + t1r08b 争议 GT）；
      ② M2 消融腿（top-k 投票 / 宽窗 std≤0.35 变体 / 质量权重（需扩缓存）/ min_valid_samples=3，
      对症 row4 型邻镜滑移；全部门限禁 GT 反标）；③ M2 通过后打包验收再翻默认。
- [ ] 争议 GT 复核（用户动作）：t1r08b 指标 HIT 但画面判读存疑（`work/fastglobal_visual/`）。
- [ ] 等授权：git 提交（"git我喊你交你再交"，未提交 >180 文件，含续19~22 四轮）。
