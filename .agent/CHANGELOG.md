# CHANGELOG

## 2026-09-30（续 32 后续六）— (E) 形态4 runtime 化落地（默认关）+ 形态5 补跑收口：① 完成、② 建议搁置

**① 形态4 runtime 化（用户批「先一」）**：新模块 `engine/localization/shot_split.py`
（detect_shots 硬切+谷值纯函数 + split_results 逐镜拆分，宽 span 保全 ⇒ 严格结构性零回退；
单镜/拒识/手动/排除段不碰）；接线 `locator_service.locate` 退化门后；
`pipeline.shot_split_enabled` **默认 False**。回归：新单测 7 项 + **后端 444→451 全绿 + API 99**
。**真实验收 PASS**（`accept_shot_split.py`，test2，DML 硬断言）：关侧与生产现役逐段一致、
开侧 54→67 段/EDL 39→41 事件、严格 18→18、FP 0→0、导出实得 14→15、LOC-2002 照常。

**② 决策层融合评分（用户批「再二」）**：形态5 margin 统一到 0.05 补跑 = **导出 107→108（+1）、
严格 130→130、FP 4→4、t1r14c 修复**（门槛达标）但 8 增 7 损、净收益薄 ⇒ **建议搁置**：
独裁重选形态收口，融合评分参数面大、GT 无关先验定标困难，留待指纹粒度升级一并评估。
归档 `FINDINGS_INSCENE_REFINE_PROBE_20260930.md`（形态 1~5 + runtime 化全记录）。
新提交未推送（等用户口令）。

## 2026-09-30（续 32 后续五）— (E) 形态5 序列对位分：信号证实、独裁重选判负；机制诊断归档

**机制诊断**（`probe_competitor_gap_diag.py`）：6 行「修不了」行 GT 全在我方检索 top-20 ⇒ 候选层
有答案、决策层选错。全片序列投票（我方 1fps 指纹复刻竞品 DTW 思路）：t1r14c/p30 投票偏好 GT
（决策层可修），p20/p34/t3r02c CLS 真盲（竞品赢在 patch 级空间对应 = 「patch 通道判负线」的
形态性未穷尽实证；竞品代价 = 候选层弱 9 条未进表）。

**形态5**（`probe_seqvote.py`，投票峰入候选 + 对位分重选主 span + 老主降子，margin 0.015）：
严格 130→130 ✓、FP 4→4 ✓、**导出 107→105（−2）✗**——增益 8 行（两预测目标全中，读图 5 同帧级）
但 churn 换坏 10 行。**判负**；结论 = 对位分有真实信息但作唯一重排器太钝，runtime 化须与既有
决策证据融合评分（决策层重设计，待拍板）。执行事故留痕：探针先改后评致 base 失真，已离线重算。
归档 `FINDINGS_INSCENE_REFINE_PROBE_20260930.md`（形态 1~5 + 机制诊断全记录）。

## 2026-09-30（续 32 后续四）— (E) 形态4（拆分 v2）：导出 +8 / 严格结构性零回退 / 内容级 8 真 1 损 = 可用级

用户重新定标（「数据只是标准、说不定是错的」）后按竞品表示粒度重做：**谷值切镜**（抓同景软切，
学镜头优先分割）+ **margin 门**（精化须胜投影 +0.05，防挪错）+ **宽 span 保全**（子段携带父
主/子 span ⇒ 严格结构性零回退）。
结果（`probe_inscene_split_v2.py`）：拆 46 段/精化 53/margin 拦 13。**导出 107→115（+8）|
严格 130→131（结构性≥兑现）| FP 4→4 | 截等长 111→115**。
10 行翻转逐张读图：**8 行真增益**（p02/p03/t1r02/t1r19/t1r23/t2r01c 等同帧级确证；t1r20 宽
span 型打折）+ 1 行 union 作图局限 + **1 行真损失**（t3r02a，严格由父 sub 保住、导出真丢）。
⇒ 形态4 = 唯一「严格零回退 + FP 不变 + 内容净真增益」的可用形态，**runtime 化待用户拍板**。
归档 `FINDINGS_INSCENE_REFINE_PROBE_20260930.md`（形态 1~4 全记录）。

## 2026-09-30（续 32 后续三）— (E) 形态3 段级拆分探针：未达门槛，(E) 按预定计划关闭

**形态3**（`probe_inscene_split.py`，多镜段拆为逐镜结果、单镜段不动、导出语义零改动）：
拆 32 段/精化 52 镜。**导出 107→112（+5 < 门槛 +10）| 严格 130→125（−5）| FP 4→4 | 口袋 2/8**
⇒ **未达标**。携带父宽子 span 变体仍 125 ⇒ −5 = 窄化 span 丢宽 cov 口径记账（t3r01 读图坐实）。
翻转 7 行读图：增益（p02/p03 同装置帧、吊架同帧）与损失（t3r01 挪出窗）都真实。

**结案定性**：「同场景 2–7s 偏移」族 = ① 多镜段子族（拆分可修但不满足安全门槛，+5/−5 交换
留档待用户决定）+ ② 单镜段子族（1fps CLS 指纹粒度上限，与 patch/密度线同因，维持关闭）+
③ 跨景误配（p30/p34，另病独立立票）。**(E) 关闭**，零 runtime / 零 GT / feature_version 零变更。
归档 `FINDINGS_INSCENE_REFINE_PROBE_20260930.md`（形态1/2/3 全记录）。

## 2026-09-30（续 32 后续二）— (E) 探针开工：两形态实测，病灶改判「导出 span 选择」

**形态1 主 span 平移**（`probe_inscene_refine.py`）：严格 130 零回退、FP 不变，但产品导出 107→**105（−2）**、
口袋 1/8 → **判负**。首跑事故留痕：med 是绝对映射常数直接当平移量，197/231 段打飞（已修：减隐含偏移 cs−rs0）。

**形态2 分镜×逐镜 span**（`probe_inscene_refine_pershot.py`，4fps 切镜 + 逐镜偏移 + agree 门）：
严格/导出/FP 三口径零变化（结构性：主 span 不动、子 span 只增不减）。**但信号被证明是准的**：
2mkv s0 切 4 镜，逐镜 span 精确落进 p02/p03 GT 窗（agree=1.0，读图+算术双确认）。

**病灶改判（本批最大发现）**：8 条口袋在基线严格口径下**本来就 HIT**（宽子 span cov 记账），
导出拿不到只因 `export_project` 硬编码只用主 span ⇒ 严格 130 与导出 107 的 23 行差集 =
「答案已在结果结构里」。(E) 从「特征/检索问题」改判为「**导出 span 选择 / 段级拆分**」，
上限 23 行，属产品导出语义变更 → **待用户拍板**；拍板前零 runtime 改动。
归档 `FINDINGS_INSCENE_REFINE_PROBE_20260930.md`。

## 2026-09-30（续 32 后续）— 18 条 GT 工单逐帧裁决闭环：GT 重锚定落地 + 新基线 130/107 + (E) 影响面统计

**裁决链（铁律全流程）**：自动判别（生产检索 top-20，16 疑错/2 同源重复/0 推翻）→ 六张拼图逐张读图
（`work/gt_tickets_visual/`，18/18 与判别一致）→ **用户逐帧裁决「18 条全部确认」**。

**应用**（`mvp/scripts/apply_gt_ticket_reanchor.py`）：12 行重锚定（t2r02a/t2r05a/t3r03a 多工单取并集，
镜头级边界精修后续另做）+ 2 行同源重复注释（p24/t2r03b）；corrections 逐条落账；
改前快照 `work/gt_backup_pre_ticket_20260930/`（GT 不在 git）；manifest 哈希更新。
两条定性翻案：**t2r05a「我方唯一特征层失败」= GT 窗错**（正式翻案）；**t2r03a 旧 HIT = 双错相消假 HIT**
（旧 GT 窗与我方落位都错到一处）。归档 `FINDINGS_GT_TICKET_ADJUDICATION_20260930.md`。

**新基线（仅换 GT，同一结果批）**：严格 **130/139**（+3）· 导出实得 **107/139**（+7）·
场景 137/139（持平）· 负例 4/9（持平）· 截等长主 span 111/139（旧 105）。
对竞品复现链真实领先 = **107 vs 83**（导出实得口径）。回归：后端 444 OK · API 99 OK
（后端/UI 源码零改动，vitest/typecheck 不涉）。

**(E) 影响面统计（新 GT 口径，`mvp/scripts/probe_inscene_offset_impact.py`）**：导出实得未命中 32 行 =
同场景族 **23 行**（gap≤7s 16 / 7–30s 6 / overlap 1）+ 30–120s 5 + >120s 3 + no_segment 1
⇒ (E) 可救池 23 行（替代旧「上限 +27」口径）。

**口袋测试集重推（用户令多模态复核，`mvp/scripts/probe_pocket_retest_gt130.py`）**：13 条候选
（复刻原口径：复现链截等长命中 && 我方主 span 截等长未 HIT）逐条三模态交叉——四拼图 13 行逐张读图
+ 落窗算术 + 生产检索 top-20（DML 硬断言）⇒ **剔 2 条容差类**（p14：PROXY 帧室内机房 ≠ GT 雷达远景；
t2r01c：PROXY 大胡子男 ≠ GT 两人队伍）⇒ **(E) 测试集 = 8 条生产未命中真口袋**
（p02/p03/p20/p30/p34/t1r14c/t2r06c/t3r02c = 同场景偏移 6 条 + 跨景误配 2 条）；
t3r05/t3r26/t3r01 单列（生产全 span 已 HIT，仅截等长口径下是口袋；t3r01 检索三窗全不支持、低置信）。
旧 14 条中 t2r02a/t2r05a/t2r05b 因重锚定转我方 HIT 退出。产物 `work/combo_pocket_retest_gt130/`
（旧目录不覆盖）。**(E) 门槛更新：8 条命中 ≥3/8 且 严格 130 零回退。**

## 2026-09-30（续 32）— 交接铁律立档；三条历史判负补读图复核（两维持一翻出夹具缺陷）；18 条 GT 工单自动判别

**铁律（用户立）**：结论不得只靠数据——逐张读图 + 至少一条独立证据。全文置顶 `PROJECT_HANDOFF.md`
（五方面复核清单 + 历史复核台账），STATE 顶部 banner；**AGENTS.md 里我加的那条按用户令撤除**。

**补复核**（`mvp/scripts/review_retro_three.py`，三张图全读）：续28 ordered_search 判负成立且更强
（4 条独家回退全真错；t3r05/t3r13/t3r29 被 FULL 臂拖到同一落点 5088-5089 = 多查询坍缩）；
索引密度 2fps 判负成立且保守（1fps/2fps 落位逐帧相同或都错）；续27 合并翻出**夹具**缺陷
（拼接点重复 ~3.5s、其后偏移；39 条 GT 全在拼接点前故原验收未暴露）。

**缺陷定性更正 + 修复**：初版归因 `source_merge.py` 是错的（产品只 concat 不切分）；修的是验收夹具
（part2 以 part1 实际末帧起切 + 互斥断言 + 时间轴同一性锁「δ 前 0 后恒定 ≤0.5s」）。
重跑 δ 前 0 / 后恒 0.167s ⇒ 合并产物恢复可用。锁的首版"同 t 逐字节相等"被容器粒度误报，改"位移恒定"。

**GT 工单自动判别**（`mvp/scripts/probe_gt_tickets_retrieval.py`）：16 疑错 / 2 同源重复 / 0 推翻读图 /
0 无效；t2r05a 原"特征层失败"定性大概率 GT 窗侧。GT 修改待用户逐帧裁决，本批不改 GT。

**同批前段**：① `measure_shot_recall` 新增并列读数 `main_hit`（导出实得 100/139 vs 严格 127/139；
105 截等长含 ±2s 容差 +18 已加注）② 重复认领告警两路径实测否决（主 span 胜率 95%；LOC-2003 误报 97%）
③ conf_v2 正式关闭（36 段读图真错仅 4，靶子是假的）。测试 444/99/127 全绿，生产三指标不变。

## 2026-09-29（续 31 补二）— 竞品整套链四片双口径对照：「换架构」量化否决，改判「挖它的表示粒度」

**触发**：用户三连问「架构不行就换呗」「有没有完整换过，人家说不定是一整套」「判了没用之后改过算法吗」。
自查承认两条：① **整套从未测过**（五环组合探针只在 test1 一片跑过，从未扩四片、从未 runtime 化）；
② 部分判负项**未穷尽改造就收了**（conf_v2 没换饱和判据 / E3 没换载体 / 两级采样探针从未跑）。

**补测（新脚本 `mvp/scripts/probe_combo_caliber_all_cases.py`，零 runtime / 零 GT / 零 GPU）**：
链路一致性先核 —— 两份 manifest 逐路径 diff，160 个字段仅 32 个不同且全是 case 输入/统计/耗时，
A1–A25 假设登记逐字一致，`g5.enabled` 两边皆关 ⇒ 四份 `localization_*.json` 是同一套四环链。
公平性再核 —— 复现链 ED 窗中位（1.60/2.30/0.90/1.45 s）不高于我方（1.59/2.33/1.07/1.86 s），
test2/test3 上它更短 ⇒ 截等长不是窗长红利。

**四片同判据读数**：复现链截等长 **83/139** vs 我方 **105/139**（去 ±2s 容差 = 67 vs 85）；
候选层复现链 **9 条 GT 从未进表** vs 我方 oracle 仅 1 条 rank>20；其完整 span 124/139 接近我方 127
**全部来自 TN 场景 span 装配效应**（test1 41 vs 10 最夸张）。逐 ID 差集 = 复现独家 16 vs **我方独家 38**。
⇒ **「整套换过来更好」被否，且是四片实测而非推断。**

**但据此修正我此前的族级结论**：16 条口袋里 **14 条是真命中**（剔除 2 条 ±2s 容差漏洞：
p14 窗外 0.67s、t2r01c 窗外 0.04s），`mvp/scripts/probe_combo_pocket_visual.py` 出 6 张 16 行
逐张读图确认 ≥8 条属**「同场景内 2–7s 偏移」**= 我方唯一未解决主病灶族，复现链在该族**确实锚得更准**；
机制 = 它的**场景内稠密局部对应**（每场景 5 关键帧 + patch 0.55 主力 + 段内 DTW/offset），
而我方 `patch v2` 是 ±30s/4s 步长/margin>0.075 的**近场稀疏重排**。

**路线裁决**：不换架构，**移植表示粒度** —— 立项「场景内稠密局部位置信号」，以这 14 条为现成测试集，
不做 GT 反标，门槛 = 命中 ≥1/3 且现有 127 条零回退（patch v2 同规格）。先例 = `fast_global`
（吸收"全局一致性"但不接受"scene 唯一认领"）与 `vote_prior` 两次成功。

**顺带两条我方自身问题**：① 口径 —— `within = span ⊆ GT窗±2s` 在截等长口径下给我方 **+18 行**
（105→85）、给复现链 +16 ⇒ 方向不变（delta +22→+18），但 **105 这个被引用数字必须标注口径**
（M1 章程门用双臂同口径差值，不受影响）；② 命中质量虚高三例 —— p30 生产 HIT 靠 **577s 宽事件 span**
兜住（落点差 200s）、p34/t2r05b 靠宽窗 cov 吃 1–2s 窄 GT 窗 ⇒ 严格口径复核时应把"宽 span 兜住"单列。

**未动**：「形态性未穷尽」清单第 2~5 项（conf_v2 换饱和判据 / 两级采样探针 / E3 换载体 /
`min_scene_coverage` 换判据）。归档 `FINDINGS_COMBO_CALIBER_ALL_CASES.md`；
产物 `work/combo_caliber_all_cases.json` + `work/combo_pocket_visual/`。

## 2026-09-29（续 31）— 用户撤裁决重做「退化拒绝门」：分腿归因 + 并集缺陷修正 + 同构安全形态 LOC-2002（只提示不删答案）

**档案错判更正（先于一切）**：TODO/STATE 把「(B) 退化拒绝门」写成"差集 TOP1 剩余半边、已批未做"，
实际续19 已实现（`engine/localization/degradation_gate.py`）、已接线（`locator_service.py:1087-1089`）、
已双臂否决（DECISIONS 续19：严格 −14 / 场景 −12 / 支撑 −201，明文"不做阈值再调"）。TODO 已就地销项。
用户仍选「仍做 B（需撤裁决）」⇒ 执行改按续21-E1 自立的纪律：**先影响面统计，再谈形态改造，不做 GT 反标**。

**影响面统计（新脚本 `mvp/scripts/probe_degradation_impact.py`，零 GPU、离线重放现役基线批）**：
四片 224 可回答段中 31 段（**13.8%**）存在单一伙伴 ≥0.8 的重复认领，但**无一属竞品那种伪影**。三条机制
= ① 相邻细段拼接铺满同一区间（2.mkv seg3/25/52 并集 0.88~1.00 却无单一伙伴，分类器判 `unique_correct`）；
② 宽窄 span 分层包含（test3 seg17 的 12.6s 场景池宽 span 被 6 条 2s 窄段"遮挡"，它独力承重三条 GT）；
③ **对称重复 + 等证据 = 掷硬币**（test3 seg41 HIGH 0.87 与 seg61 HIGH 0.89 指向完全同一 2s 源区间，
读图 = 同一「矮人立于山岩」镜头被解说在 86s / 139s 各复用一次）。

**分腿消融（续19 未做，五臂 off/dup_only/subs_only/both_partial/both_allnone）**：
拒识腿单独 = 严格 **−2** / 场景 −1 / **负例 ±0**；续19 的 −14 里 **test2 的 −5 全部来自子 span 腿
「全低即整段清空」形态**（`both_allnone` 10/20 vs `dup_only` 15/20 vs `subs_only` 部分丢 15/20），
与竞品 `max_duplicate_scene_ratio` 无关。独立实现 `replay_degradation_gate.py` 同批跑出 127→118/137→132
逐位互证。**裁决：`degradation_gate_enabled` 维持默认关（第四次独立确证）**。

**真缺陷修正（runtime）**：`duplicate_ratio` 把各邻居重叠**直接累加**，邻居互叠时同一区间重复计数；
改**并集**后 test3 seg17 由误拒转为保留 ⇒ 分腿复测回收 **严格 +2 / 场景 +1**。三条单测锁死。

**新立同构安全形态（进 runtime，默认开）**：`duplicate_claim_groups()`（并查集传递闭包）+
`duplicate_claim_warnings()` 产 `LOC-2002` 话术，挂既有 `last_export_warnings` → `/api/export` →
结果页导出对话框（**UI 零改动**）。判据 = 重叠/较窄侧 ≥0.8 **且** 窄宽比 ≥0.5；计算时机 = clip 几何
全部定稿之后（门槛→吸附→切点展开→剪映取材扩展）。旋钮 `export.duplicate_claim_warn` /
`duplicate_claim_min_ratio` / `duplicate_claim_min_width_ratio`。

**真实导出冒烟（`mvp/scripts/accept_duplicate_claim_warning.py`）**：2.mkv/test1 零组、test2 一组
（第 12、13 段 → 3277.0-3280.6s）、test3 两组（34、37 段；42、62 段）；**开关两侧 EDL 逐字节一致**
（= 不动数据的硬证）；逐张读图 6 张（ffmpeg 精确 seek 出对照图）确证三组均为同镜头重复素材。
**读图抓到并修掉 1 例假阳性**：无宽度比下限的首版把 test3 第 30、31 段也报成重复，画面实为
**Thorin 特写** 与 **Thranduil + 麋鹿** 两个不同角色不同镜头（只是 8s 宽 span 含住 2s 窄 span）。

**测试**：后端 **433→444**（`test_degradation_gate` +11）· API **99** · vitest **127** · 双 typecheck 干净 ·
`test:mock` PASS。生产三指标不变（127/139·137·4/9·105），零 `feature_version` 变更。
归档 `mvp/benchmark/user_case/competitor_cutmatch/FINDINGS_DEGRADATION_LEGS_AND_DUP_CLAIM_WARN.md`。

**执行事故留痕**：本批首跑误用 `replay_degradation_gate.py` 的硬编码输出路径，覆盖了续19 的
`work/degradation_gate_ab.json`（`work/` 不在 git ⇒ 不可恢复）；该文件聚合数字在 DECISIONS/CHANGELOG/STATE
均有留痕、结论未受影响；已给脚本补 `--report` 参数防复发。

**全量逐图复核（用户令「全部读一遍」，新脚本 `mvp/scripts/review_degradation_visual.py`，16 张拼图 /
本批累计 25 张逐张读毕）**：① 拒识腿实际砍的 8 段逐一看画面 —— 2.mkv 三条（p06/p23/p31）是
「相邻细段各认领同一连续区里的不同镜头」（水塔-掩体区、夜屋正反打区，s52/s53 还交叉映射），
test2 s12 与 test3 s5/s33 确为无归属噪声（该拒），而 **t3r12 / t3r18 两条是真画面损失**
（s41 与 s61 同指山岩镜头，0.87 vs 0.89 = 掷硬币）⇒ 我中途按「s30 中帧落在相邻镜头」判过一条属
GT 口径，读完更正，裁决依据反而更强；② **新工程事实**：test2 被整段清空的 6 条 GT 行，其承重子
span 的 `cover` 是 **0.00~0.19** ⇒「cover 低 ≠ 该 span 无用」，`min_scene_coverage` 与我方子 span
语义不同物（要启用须换判据而非调阈值）；③ LOC-2002 在 2.mkv 零组**不是漏报**（那 3 对各含一条
LOW 被导出门槛挡在工程外，口径 = 工程内重复素材）；④ 出图脚本自身两处缺陷（OM 格误用编辑时间轴、
文件名不含 case 致四片互相覆盖）均在读图时暴露并修 —— 与 `--report` 硬编码同族教训。

**尾巴**：Mock 适配器不产 `warnings`（dev 态看不到 LOC-2002）；打包 exe 真机复核告警文案（需授权，
可与续30 渲染按钮并一次）；`min_scene_coverage` 整段清空形态缺陷**未**改 runtime（门默认关无生产影响，
探针已量化「部分丢」形态可免掉 test2 的 −5）；竞品「相近片段自动合并」未做（本次只提示，合并留给用户）。

## 2026-09-29（续 30）— 成片渲染（竞品差集 TOP1）移植 + 真实素材验收 = PASS；新工程结论：中段音频不能用 AAC

**立项**：用户令「先下批偷向吧」→ 按档案排序做表 D 唯一判「缺失」的 TOP1
`exporting.rendering.video_renderer`。形态字节确证 = blob #138（527 常量 / 75 条中文 docstring）：
逐段 CFR（`fps=fps=`+`trim`+`setpts`+`round=near`+`-frames:v`）→ 合并优先流复制、失败回退重编码 →
逐段帧数校验（`nb_frames` 快速 / `-count_frames` 严格）→ 硬件编码器失败拉黑回退软件 →
停滞看门狗 + `-progress pipe:1` 读取线程 + terminate/wait/kill → 片段并发保序、失败回退串行 →
稳定命名产物。在位数值 `1920/1080/48000/1800.0/120.0/2/6`。

**用户拍板口径（与竞品两处刻意不同）**：① **紧凑拼接**，不落地黑场空档腿；② **音轨取原片对应区间**，不用解说轨。

**落地**：`mvp/src/media/ffmpeg/timeline_render.py`（纯函数命令构造 + `TimelineMovieRenderer` 监护执行；
复用续27 `concat_list_text/parse_progress_seconds/error_summary/_runner`，不重复实现）、
`config.RenderConfig`、`paths.rendered_root()`、`ProgressStage.RENDER_MOVIE`、
`locator_service.render_movie()`（**与 export_project 同一套 clip 计划**：门槛→吸附→切点展开，
返回 `clip_ranges` 供验收/展示）、`POST /api/tasks/render`（新增 `Task.kind=analyze|render`，
渲染批**提交时锁定**防排队竞态，`worker.run_render_worker` 分派）、UI `startRenderTask` +
`composables/useRenderMovie`（轮询/取消/打开所在目录）+ 结果页导出对话框「成片渲染」区块。

**本批最大发现（新工程结论，两处回归锁）**：中段音频**不能用 AAC**。AAC 每帧 1024 样本
（48k = 21.3ms）补齐段尾 ⇒ 中段音频恒比视频长一帧，concat demuxer 按容器内最长流推进偏移 ⇒
2.mkv 60 段成片出现 **59 处 0.0417→0.0630s 视频接缝**、容器帧率被探成 `48000/1001`。
`-shortest` 是错误解法（实测反截 3 帧、间隙放大到 0.103s，已弃用）；
正解 = **中段 MOV + PCM 24bit + 终片只复制视频、音频整片转一次 AAC**，复跑 = 3552 帧、
**不规则帧距 0 处**、帧率回到 `24000/1001`。中段容器名进稳定命名哈希，旧形态缓存不会被误复用。

**真实验收（PASS，`mvp/scripts/accept_video_render_2mkv.py`）**：60 段 / 3552 帧 / 148.17s；
`nb_frames` == `-count_frames` == 计划；8 段抽样对齐 **0 或 −1 帧**（MAD 噪声底 0.33-0.47）；
逐张读图 9 张（clip00/05/10/20/31/35/43/52/59）左右画面同景同人同动作；EDL 60 段与成片同计划；
编码器 `h264_amf`（本机 AMD 硬件在位无需回退）；首跑 54.7s（0.9s/段）、二次命中缓存 0.2s；
`hdr_downgraded=True`（高位深源降 SDR 成片，工程仍指原片）。产物 `work/render_accept/`。

**测试**：后端 **388→433**（`test_timeline_render` 29 + `test_render_movie_service` 16）·
API **89→99**（`test_render_task` 10）· vitest **118→127**（`renderTask` 9）· 双 typecheck 干净 ·
`test:mock` 契约含渲染段 PASS。生产基线不变（127/139·137·4/9·105），零 `feature_version` 变更。

**尾巴**：打包 exe 真机复核（结果页渲染按钮/进度/打开目录）等授权；`rendered/` 未进残留清理清单；
竞品「相近片段合并」「渲染失败仍出 XML」未复刻（我方失败即抛对外话术，改不改待拍板）；
`workers=2` 与 `=1` 的耗时差未测。档案：`FINDINGS_VIDEO_RENDER_PORT.md`（新建）+
`FINDINGS_CAPABILITY_MAP_20260928.md` 表 D/表 E/结论 TOP1 销项。

**效果判读（同日收尾，用户问"有进步吗"）**：精度层面零进步且本应如此（未动算法/未 bump fv）；
能力层面 0→1（首次不打开 NLE 就能拿到可播 mp4）；质量层面最实一条 = 修掉 59 处 AAC 接缝拉伸。
但补做了**成片性质度量**后结论要收紧：60 段 / 148.0s、单段 1.0–9.94s（中位 2.0s）、
按播放顺序源片起点**倒序对 13%**、相邻回跳 8 次（>60s 的 5 次）、未定位段静默跳过
⇒ 当前成片是**审片带/素材堆**，不是可对外交付的叙事片。
两处自我更正留痕：① 曾把「源片起点是否单调递增」当验收项，实为**先排序再比较 = 恒真**的口径错误；
② 测量脚本用名义秒累加成片时间轴会假跑出 4 帧漂移，改帧精确累加后对齐 = 0 或 −1 帧。
验收覆盖缺口如实登记：逐张读图 9/60 张，其余靠帧距规则性 + 8 段 MAD 兜底。
下一步三选一已写进 STATE「Next Actions」：(A) 成片补缺口标记（黑场腿/时间码条 + 可选解说轨）
(B) 退化拒绝门（TOP1 剩余半边）(C) 入库层四件 / 大文件鲁棒性四件。


## 2026-09-29（续 29）— UI 多选原片接线（续27 video.concat 的产品入口）= 落地 + 浏览器态验证

**范围**：纯 `mvp/ui` + Electron 桥，`mvp/src`/`mvp/api` 零改动 ⇒ 生产基线（严格 127/139·场景 137·负例 4/9·口径 105）不动。

- **桌面桥**：`app:openFiles`（`openFile`+`multiSelections`）返回**用户选择顺序**的绝对路径数组，取消=空数组
  （顺序即合并时间轴顺序）；preload + `electron.d.ts` 同步；`compile:electron` 产物已含 openFiles。
- **服务契约**：`mergeSources(paths)`→`POST /api/source/merge`（`{paths}`→`{merged_path,mode,reused,duration_s}`）；
  `startAnalyzeTask(edited, original, originalPaths?)`——≥2 段发 `original_path:''`+`original_paths`（与
  `routes/tasks.py` 同规则），单段 body 与旧版逐字一致；Mock 适配器同规则拒 <2 段，`test:mock` 补合并契约段。
- **项目状态机**（`stores/projects.ts`）：`sourceVideos`（有序原片库）+ `merge` 留痕 + `syncEffectiveSource`
  生效规则：单段→该段 / ≥2 未合并→''（不再拿第一段假装全片）/ 已合并→产物路径 / **库内容或顺序变化→产物过期** /
  库清空→'' / 裸文件名不覆盖已生效路径；旧 localStorage 项目读时迁移（`normalize`），历史项目零丢失。
- **展示**：详情页「源片库」列表（序号、删除单项、一次拖入多段、浏览器模式可多次粘贴追加）+「立即合并/重新合并/
  取消合并结果」+ `mode`/`reused` 徽标；分析页未合并多段显示清单且按钮改「合并并分析」，已合并显示产物 +
  「合并自 N 段 · copy」标签，无源片时按钮禁用（补此前可空源点击的 400 路径）；项目卡显示
  「N 段原片（待合并）」或「产物名（合并 N 段）」；元数据多段=逐段探测聚合（时长/大小求和），已合并=探产物。
  合并进度沿用后端 `MERGE_SOURCES→INDEXING` 映射，UI 阶段枚举零改动。
- **验收**：vitest **95→118**（`projectsSourceLib.test.ts` 15 + `sourceMerge.test.ts` 8）· 双 typecheck 干净 ·
  后端 **388**（skipped=2 既有 MPS 类）· API **89** · `test:mock` PASS · 浏览器态（Mock 后端 + CDP 结构快照）
  真点：两段入库→聚合时长 4h37m→立即合并→产物+徽标→取消合并→分析页「合并并分析」+清单；旧版项目迁移后
  原片库/时长自愈正常。
- **未做（诚实边界）**：打包 exe 原生多选对话框 + 真实 ffmpeg 合并 + 合并片定位导出端到端的**真机复核**
  （需打包授权，随 r3 一批）；`FINDINGS_SOURCE_MERGE_PORT.md` §4/§5 已改「UI 已接线」。
- **待拍板**：git 提交（实测 232 文件未提交，含续23~29）/ 分发包 r3 重打 / 下批偷向（成片渲染·入库层·大文件鲁棒性）。

## 2026-09-28（续 22）— fast_global_anchor M1 双臂回归 = 通过验收门（口径 82→105）；min2 消融腿证伪、生产参数回退

**M1**：`global_offset_anchor`（无位移帽 + 宽窗共识门 + 平移保宽度，替换 vote_prior 应用点）四片双臂，
DirectML 硬断言，ON 臂复跑逐项一致：严格 119→**127**、场景/负例持平、main-span 截等长口径 82→**105**
（≥章程门 +8）。10 翻转逐张读图 = 9 真改善 + 1 回退（t2r01b row4 邻镜滑移）+ t1r08b 争议 GT 标注。
**裁决=通过但 `fast_global_enabled` 维持默认关，翻默认/M2 待拍板**。

**min2 证伪**：对症 row4 单票众数桶尝试 `min_cluster_votes=2` ⇒ 口径 105→82、严格 127→118、9 项改善全灭
（真匹配在 1s 库网格天然单票窄桶，票数不是判别维度；"竞品 min_valid_samples 确证"归因撤回）。参数保留=消融接口，
生产=1（config 注释钉死证据链）。

**产物**：`PROJECT_FAST_GLOBAL_ANCHOR.md` §7 裁决 · `diff_two_metrics.py`（逐 ID 翻转）·
`work/fastglobal_on_min2_*`（证伪腿证据）· `work/fastglobal_on_r2_*`（复现核验）· 锚定单测 9 项（含证伪回归测）。
测试基线：后端 **343** · API **81** · vitest **95** · typecheck 干净。工程坑注：Windows Git Bash
PYTHONPATH 分隔符须 `;`（`:` 静默假失败）。

## 2026-09-28（续 21-E3）— ECC/结构相关边界复核探针 = 负结果, commentary_scene 不进 runtime

42 已裁锚点(36真/5假): ecc_resid AUC 0.900、hist_corr 0.911、帧差基线 0.917 —— **新信号腿与已证伪腿同档**,
假切点非仿射可解释运动; 组合工作点(拦4/杀1)为小锚集扫描假象, 决定性外验证(最难假例 test3@27.79 raw=0.053
落区域外, 扩门即误杀 7 真切点)回到 ~1:1, 与续8b 三方闭合。架构解释: 竞品复核层修自家 TN 的毛病, 我方
6 假切点是 CLS 切分副产品。零 mvp/src 改动; 产物 `FINDINGS_E3_ECC_PROBE.md` + `mvp/scripts/probe_ecc_boundary.py` +
`work/ecc_boundary_probe.json`。

## 2026-09-28（续 21-E1）— E1 resolve_consecutive 双臂实测 = −1 真回归 + 图证合法复用 ⇒ 维持默认关、通道关闭；立"去重类判据前置纪律"

**数字**：test2 严格 14/20→13/20（−1）、test3 持平、零改善（同批同 GT 同判据，GPU DirectML 硬断言）。
**图证**：t2r01b OFF span=牛栏+水塔（=GT 内容）、ON 平移后=洗车隧道（无关）⇒ 平移砍的是正确答案。
**纪律**：见 DECISIONS 同日 E1 条（"去重/唯一认领"类判据移植前置=影响面证伪影系统性存在；四项已三项反证）。
**产物**：`FINDINGS_CONSECUTIVE_OFFSETS_AB.md` + `engine/localization/consecutive_offsets.py` + 10 单测 +
`rerun_consecutive.py`/`visual_consec_flip.py` + `work/consec_*`。后端全套 334 全绿。

### Notes

- Created `checkpoint-2026-09-28-1742.md` checkpoint (187 modified/untracked file(s)).

- Created `checkpoint-2026-09-28-1741.md` checkpoint (186 modified/untracked file(s)).

## 2026-09-28（续 21）— 打包端到端验收通过（现场修 3 个必炸缺陷）+ vote_prior 翻默认开

**验收**：`release/win-unpacked` 整包 + CDP/UIAutomation 驱动，10 项全过（发行三防线负例/随机端口
BACKEND_LISTEN/门禁 401→200/新建项目取消不创建/元数据回填/打包态分析 directml/预览直链逐图核对/
四格式导出文件级校验/错误条幅/vote_prior 生效）。记录 `mvp/docs/ACCEPTANCE_PACKAGED_20260928.md`，
证据 `work/ui_accept/`。

**现场修复 3 真缺陷**：① `run_backend.py`/`backend.spec` 的 `mvp.api` 命名空间依赖构建 cwd，本次
PYZ 零桥层模块、backend.exe 启动即崩 → 改 bundle 正规顶层 `api` 形态；② `<video src>` 直链不带
会话令牌 → 发行态预览全黑 → `previewResult`/`getEditedVideoUrl` 拼 `svl_session`；③ 构建期
`VITE_API_BASE` 经构造参数压过运行时 `svl_port` → 直连 URL 指回 8765 → 运行时端口优先。各带 vitest 回归。

**vote_prior 默认开**（验收=既定前置；新包日志 seed 19.6s applied，合成夹具窗口 22–24→19–24 完整覆盖 GT；
dense_recheck/conf_v2 维持默认关）。基线：后端 324 · API 81 · vitest 95 · 双 typecheck 干净。

## 2026-09-28（续 20）— 续19 遗留三项全落地：/api/media/info+假数据清除 / 导出 warnings+task 错误话术 / 随机端口端到端（更正续19 假前提）

**① P0 metadata 端点 + 前端假数据**：新增 `mvp/api/routes/media.py`（`GET /api/media/info?path=<绝对路径>`，
复用冻结 `media/ffmpeg/ffprobe.py` 的 `FFmpegIO.metadata`；400 `invalid_path` / 404 `file_not_found`（detail 只回
文件名=脱敏）/ 500 `public_error` 带 LOC 码）+ `schemas.MediaInfoResponse`。前端：`ServiceAPI.getMediaInfo` +
Http/Mock 适配器 + `projects` store `updateProject/refreshSourceMeta` + 新 composable `useCreateProject`
（**新建项目=先弹原生对话框选真实视频，取消不创建**；项目名=文件名去扩展名；时长/fps/分辨率/大小实测回填，
旧项目打开时 duration=0 自动补探）。`HomePage/ProjectsPage` 的 `movie.mkv`/`Interstellar (2014).mkv` 死值清除；
`ProjectCard` 显示 basename + 时长「—」占位；`mockData.ts` 假片名属 Mock 明示假数据，保留。

**② P1 warnings + 话术**：`exportResults` 契约 widened 为 `{path, warnings?}`；`ResultsPage` 告警非空 ⇒ 导出
对话框保持打开显示 LOC-2001 碎片告警（「知道了」关闭后页面仍有条幅）。`mvp/api/tasks/worker.py` 的
`task.error` 由 `"ExcName: 技术串"` 改为 **`public_error` 话术（LOC 码）**，技术细节只进日志（分析页错误条幅
直接可读；同步非 2xx 路径续19 已在 `request()` 优先展示话术，本轮补测试锁定两侧契约）。

**③ P1 随机端口（含假前提更正）**：续19 交接称「后端已支持 SVL_API_PORT=0 并打印 BACKEND_LISTEN 公告」——
grep 证实**全仓无该行**（只存在于 `main.py` docstring；打包 exe 真入口 `run_backend.py` 读 `SVL_BACKEND_PORT`
且无任何公告）。本轮真实落地：新 `mvp/api/launcher.py`（`uvicorn.Server.startup` 挂钩，**绑定成功后**才打
`BACKEND_LISTEN <host> <port>`，失败=宁缺毋假；通配 host 归一回环；`make_server` 可测），
`python -m mvp.api.main` 与 `run_backend.py` 共用。Electron：`process.ts` stdout **行缓冲**（公告不被 chunk 切断）；
`manager.ts` 解析公告、`config.port===0` 时以公告门控 `waitForHealth`（进程先退 fast fail）、健康检查走
`configWithListen` 真实地址；`main.ts` 打包态注入 `SVL_BACKEND_PORT=0` + 就绪后回填活配置 + 页面 query
`svl_port`（`readBackendBootstrap` 已支持）。开发态维持固定 8765 行为不变。

**验证**：后端 324 / API **81**（+media_info 6、export warnings 1、launcher 8，含真实 uvicorn 随机端口起停例）/
vitest **93**（+renderer 12、electron 8）/ `typecheck` + `typecheck:desktop` 干净。真机冒烟（源码态）：公告随机端口
→ `/api/health` 200 → `/api/media/info` 实测（1.mp4 126.79s/29fps/544×960）→ 相对路径 400。
**未做**：打包 exe 端到端 UI 验收（等授权）；`routes/results.py:80` 同步 detail 仍技术串口径（尾巴已登记）。

## 2026-09-26（续 10 完成）— D 段代理复现四组全量 + 多面复核：严格 124/139 = span 粒度装配效应；复现内容性错误 0；产出 2 条 GT 复核线索

**流程**：子代理参数化 `run_localization.py --case`（test1 回归 MD5 逐字节一致）→ 四组全量（262 查询/242 matched，
重复跑四组全同解，含 7 行短场景 span 倒置 clamp 修复）→ import 升级支持 v2 schema（旧通道兼容）→ measure →
`review_proxy_loc_visual.py` 五桶出图 93 张 → 判卷侧逐图裁决 20 张。

**数字**：proxy **124/139 严格 · 121 场景 · 负例 4/9**（基线 117/137/4；main-span-only 基线 85）。

**多面复核结论（用户纪律：不只靠数据/GT）**：
- **严格「反超」是伪影**：复现 span = TN 场景代理（om/ed 时长比中位 8.7×）；A 桶翻转全部 part→HIT 装配效应（内容同场景/同动作，
  0 例"复现找到基线找不到的内容"）；严格与场景指标对粗 span 方向相反（124↑/121↓）⇒ 单一指标必误读；
- **复现内容性错误 0 例**（B 桶 8 张 + E 桶抽样）；**2 条 GT 疑错线索：t1r08b/t1r12a**（双侧独立定位同内容区，GT 窗画面与 ED 不符；
  复现在 test1 仅有的 2 条严格 MISS 恰是这两例）；
- AKAZE on/off = 10/262 行差异全为 strict 门拒绝，两档 span 完全一致 ⇒ 无增量无伤害；
- 复现真实弱点 = 蒙太奇段拒识漏召回（2mkv p10 型，每场景 5 关键帧代表不足）；n01 误配与我方历史同区同机制（非复现特有）。

**定论（有据）**：复现管线实现与内容质量可信；**不构成"竞品定位更好"的证据，也不构成反向证据——端到端谁更准仍是未测**
（同粒度化对照设计见 FINDINGS §5）。GT 线索待用户裁决。

**产物**：`FINDINGS_PROXY_D_STAGE_REVIEW.md` · `REVIEW_NOTES_PROXY_D_STAGE.md` · `review_proxy_loc_visual.py` ·
`work/proxy_{case}.results.json` · `work/proxy_four_metrics.json` · `work/proxy_loc_review/`（93 图，已裁 20）；
复现侧 `cutmatch-analysis/sandbox/`（脚本参数化 + 四组×3 JSON + assumptions 25 条）。

## 2026-09-26（续 10）— 外部 6 项接管执行（用户授权直改外部仓）：A2/A3/A4/A5 销项，A1 自跑 D 段复现启动

**背景**：用户指示「外部 6 项你自己做，都有外部文件路径了」。逐项处置：

- **A2（P0-8 采样语义）= 已答销项**：对方 14:46 新交付 `FINDINGS/12_PIPELINE_SAMPLING_SEMANTICS.md` ——
  `source_sample_rate`/`commentary_sample_rate` 属精确模式 `pipeline.options.DEFAULT_OPTIONS`（与 fast 的
  `source_global_fps=1.0` 是两条管线各一套采样键）；单位**强推断 2 fps（未确证）**；D 段处置 =
  manifest `sampling_caliber` + 主档 2 fps / 额外 1 fps 对照档 + `keyframes_per_scene=5` 与 `*_sample_rate` 两通道不可合并。
- **A3（文档订正 3 条）= 我方直接落地（外部仓 8+3 处）**：test3-om 锚点 244,004→**244,003** 共 8 处
  （PROMPT_FOR_EXECUTOR / RUNBOOK §5.1 两表+验收清单+新增注 E / sandbox 4 脚本 ANCHORS），锚点口径升级**解码帧数**；
  FINDINGS/09 旧表行 `dtw_min_score` 改「~~0.1~~ → 确证 0.55」；RUNBOOK 追加 `feature_image_size` 命名注记。
  `197,305` 残留核查 = 0（对方已同步）。
- **A4（D 提示词 7 条 P0）= 验证在位 + 补裁决**：v2 的 P0-1~P0-8 逐条核对齐全；test3-om 244,003（解码帧数、
  DISCARD 末包机制、benchmark 裁决文书指针）并入「继承 B 段结论」节。
- **A5（N1-N8）= 状态登记，不重复投入**：09 §8.4/8.5 自述数据段穷尽，剩余 59 项（N1 `ordered_search_*` / N4 `path_*` /
  N3 开关族 / N8）全部落在 **code object 机器码反汇编**卡点（专项未完成）；我方等该专项产出，不另起炉灶。
- **A6（N16/N18 运行期）= 维持不可行**（授权+lease；不绕授权拍板不变）。
- **A1（D 段产物）= 我方自跑**：不再等执行方——子代理按 `PROMPT_FOR_EXECUTOR_D.md` v2 + RUNBOOK §7-D 在
  cutmatch-analysis 沙盒实现 `run_localization.py`（DINOv2 ViT-S/14 @224 官方权重 strict 加载、t050 查询单元、
  global/patch/scene 三通道 + AKAZE on/off、候选表、双时间码、manifest 全字段），test1 组先行、验收后跑齐四组。

**验收口径（预先声明）**：复现产物 = main-span-only 口径；同口径公平基线 = 严格 85/139 · 场景 128/139 · 负例 4/9（续9 预演实测），
不得直接对 117/139。

## 2026-09-26（续 9）— 可执行项批量推进（用户委托）：6 项完成 + D 段对照口径发现

**完成项**：
1. **p26 margin 口径差陈旧待办关闭**：2026-09-06(XIV) 同日已查明修复（0.080 骑线 → margin 0.075），补指针销项。
2. **GT 版本登记表 7 份剩余文档逐条核销**：IFRAME_CUT / LOWINFO_STRIP / SEMANTIC_SEPARABILITY / TIMELINE_V4_QUANT /
   EVENT_IDENTITY_P1_P2 / P36_FINESEG / AMBIGUITY_PROTOTYPE —— 均按 v4/verified-139 执行（脚本直读 GT 已核对），
   全部加「GT 版本」标注头 + 审计 §八 🟡 行改为 7 条 ✅。
3. **GT 修正自动受影响清单机制落地**：`mvp/scripts/gt_impact_scan.py` —— 8 个 GT 文件哈希快照
   （`work/gt_version_manifest.json`）+ `--check` 自动列出受影响文档（`AFFECTED_MAP` 与 §八 同步）+ 未登记文档扫描；
   变更路径注入式验证通过（伪哈希 → v4 → 10 份受影响清单 → 恢复）。
4. **基座路线关闭写入 `ARCHITECTURE_DECISION_PHASE20.md` 附录 A**（探针级 + 产品级 + V5 口径复核 + 产品含义）。
5. **backbone harness 固化 `mvp/scripts/eval_backbone_swap.py`**：asset/locate/measure/compare 四阶段编排、
   注册表式扩展（新 backbone = 加一个注册项 + 一个 rerun 模块）；measure/compare 已实测对账
   （基线 perfopt 117/139 vs ViT-B 116/139，与档案逐位一致）。
6. **D 段接收侧全链路预演通过**：`mvp/scripts/dryrun_proxy_loc_channel.py` 反向构造对方 schema
   （`work/_loc_dryrun/localization_*.json`）→ `import_competitor_proxy.py --loc` → `measure_four_results.py`，零崩溃。
   顺手修 import 脚本 docstring SyntaxWarning。

**⚠️ 重要口径发现（D 段对照设计输入）**：对方 localization.json 每条只有一对主 span 起止毫秒 ——
把我方完整结果批（含子 span）压缩成该格式再评估，严格 **117→85/139**、场景 137→128、负例 4/9、支撑 180/224。
⇒ **同口径公平基线 = 85/139（main-span-only）**，不得拿对方数字直接对 117；若对方按我方 7 条 P0 交付候选表，可对齐完整口径。

**工程注记**：`import_competitor_proxy.py --loc` 输出路径硬编码 `work/proxy_<case>.results.json`（不随目录参数走），
真产物导入前先清点该名字（本次预演产物已移入 `work/_loc_dryrun/`）。

## 2026-09-26（续 8b）— TN 双判据仲裁探针 Stage 1 = 否定（不进 runtime）；全仓 open item 清点完成

**背景**：用户批准「TN 双探针」（= TODO「换切点探针扩全量」+ 仲裁形态验证）。纯 numpy、零 runtime、零 GPU；
真值只用 44 例人工盲判（不套 GT）。

**协议**：227 条现行边界 × 判据 A（执行方 probs ±0.25/0.5 s 窗最大概率）∧ 判据 B（H-CM1 帧差判据：
below_threshold / peak vs thr / shift / 自身帧差）；44 例已裁决锚点（真 29 / 假 6 / 未定 2）上穷举 15 组工作点。

**结果（否定）**：
- 最优工作点 = **假命中 5/6 ∧ 真误伤 5**（被误伤：2mkv@9.45、test1@78.2/100.2/107.07/110.6——全部盲判确证真切换；交换比 ≈1:1）；
- 唯一漏网假切点 test3@27.79（moved/shift−14/自身帧差 5.5）与已证真切换 test3@16.29（moved/shift−15）在规则可观测特征上**同构**；
- 四特征诊断（tn@、TN 窗最大、帧差峰、自身帧差）假切点 vs 被误伤真切点**区间完全重叠** ⇒ 判据空间内不可分。

**结论**：仲裁删除形态关闭（会以 ≈1:1 误伤真切换为代价剔除假切点）；「输出层换切点」若立项只做**展示层并集/就近优选**（不删我方切点）；
重启仲裁需第三类信号（语义/OCR/音频——均已证伪或不存在）或逐段多模态复核（成本不成立）。test2 合并候选 0 条（问题只在漏切侧）。

**产物**：`mvp/scripts/probe_tn_arbitration.py` · `work/tn_arbitration_probe.json` ·
`user_case/competitor_cutmatch/FINDINGS_TN_ARBITRATION_PROBE.md`。

**同轮**：全仓 FINDINGS/提案/交接文档 open item 清点完成（见 STATE/TODO 未完成清单：等外部 6 / 等拍板 13 / 可执行 3 / 工程 4 / 档案 3）；
`D:\dsh-work` 授权逆向目录完成「存在 + 边界」登记（不推进、不引申，用户复核口径）。

## 2026-09-26（续 8）— test3-om.mp4 帧数锚点裁决 = 244,003（锚点 244,004 偏高 1 帧）；执行方 om 批放行条件确立

**背景**：执行方 om 批交付（test2-om / test3-om 的 probs.npy）时帧数交叉校验失败
`[('test3-om.mp4', 244003, 244004)]`，按任务书「任一片帧数与 §5.1 锚点不符 ⇒ 停下报告」停止（行为正确）。
判卷侧独立裁决完成，**执行方产物正确、无需重跑**。

**证据链（判卷侧独立实测）**：
- packet 数 = nb_frames 元数据 = 244,004（锚点来源，巧合相等）；
- pts 网格：244,004 包占 244,006 槽位、尾部 2 个空洞（#244002/#244004）+ 2 个包 pts 超出容器时长；
- **全流恰好 1 个 DISCARD（`_D_`）标记包 = 最后一个包（pts 10,177.166875）→ 解码器按标记丢弃**；
- 尾部解码实测：最后解码帧 pts = 10,177.083490（该包未出帧）；
- **我方独立全流解码 `ffprobe -count_frames` → `nb_read_frames = 244,003`**，与执行方管线一致；全解码零报错（按标记丢弃，非解码失败）；
- test2-om 同批复核四方一致（121,094）。

**澄清**：对方 `four_clips_framecount_verify.json` 的 `frames_cv2` 是 cv2 `CAP_PROP_FRAME_COUNT` **元数据估值**
（铁证：同文件 test1-om 行报 197,305 = 已作废的时长×fps 值），与本裁决零矛盾。

**结论与升级**：
- 裁决 244,003 为准；被丢帧 = 全片最后一帧（≈42 ms，仅影响最后一个下标）→ **对 D 段切点/定位零影响**；
- **锚点口径升级**：本项目两次踩坑（时长×fps 偏高 199 / packet 数含 DISCARD 偏高 1）⇒ 锚点应改为**解码帧数 `nb_read_frames`**，packet 数降为交叉校验；
- 待执行方按 `FINDINGS_TEST3OM_FRAMECOUNT_ADJUDICATION.md` §5 更新 7 处锚点（runbook 3 处 + PROMPT 1 处 + sandbox 脚本 3 处）后重放 `verify_proxy_output` → 交付 D 段。

**产物**：`user_case/competitor_cutmatch/FINDINGS_TEST3OM_FRAMECOUNT_ADJUDICATION.md` ·
`work/_t3om_pts.txt`（全流 pts 转储）· `work/_t3om_readframes.txt`（244,003）· `work/_t2om_readframes.txt`（121,094）。

## 2026-09-26（续 7）— D 段前置对照①：查询单元换成竞品 t050 切点 → 四片严格 114→104（−10）· 场景 137→122（−15）

**做法（零 `mvp/src` 改动）**：`mvp/scripts/proxy_query_unit_run.py` 只把编辑侧查询单元换成对方 B 段 `scene_split_t050` 的切点
（71/35/67/87 单元），我方索引 1.0 fps/518、检索、事件扩池、patch v2、置信、卡守卫全部不变；GPU DirectML 实跑四片。

| 片 | 基线 严格/场景 | 换竞品单元 严格/场景 |
|---|---|---|
| 2mkv | 34/39 · 39/39 | **26/39** · 34/39 |
| test1 | 34/43 · 42/43 | 34/43 · 40/43（**严格持平**） |
| test2 | 14/20 · 19/20 | 13/20 · **14/20** |
| test3 | 32/37 · 37/37 | 31/37 · 34/37 |
| **合计** | **114/139 · 137/139 · 负例 4/9** | **104/139 · 122/139 · 负例 3/9** |

**多模态复审**（`work/qu_flip_visual/*.png`，锚点取评估器实际采用的 main/sub span；早期误用未被采用的主 span 作图已修正）：
① 2mkv 的 MISS **全部**落在 0.5–1.0 s 查询单元（>2 s 单元 8/8 HIT、1–2 s 单元 0 MISS），单元对 GT 编辑窗覆盖率中位 2mkv 0.67 vs test1 1.00；
   p02/p03 的单元退化成 1.5–1.5 / 2.5–3.5 的单帧级查询 → 直接 `not_in_source`。
② test1/test2/test3 以**判据边界 / 同场景漂移**为主：test1 6 失 6 得（净 0）、t1r00 2154–2156 vs 2156–2158 同人物晚 ~2 s；
   test2 t2r07c 内容一致但原片侧重叠 45% < 50% 判 MISS；t2r03a 查询子镜头换成人群 → 定位去人群。

**结论**：细切点**当查询单元**净负，成因是「我方 2 fps 查询采样 × 细切点」口径不匹配（竞品查询侧 = 每场景 5 关键帧），**不是对方切点不准**；
与既有结论同向（A1 直接替换 −16；盲判相邻真切换各选其一）⇒ 细切点只能作为**段内子 span / 输出展示粒度**（并集 + 仲裁）。

**产物**：`user_case/competitor_cutmatch/FINDINGS_QUERY_UNIT_SWAP.md` · `mvp/scripts/proxy_query_unit_run.py` · `probe_qu_flip_visual.py` · `diag_query_unit_length.py` ·
`work/proxy_qu_*.results.json` · `work/_four_{base,pqu}.json` · `work/qu_flip_visual/*.png`。

## 2026-09-26（续 6c）— 我方记录更正：`ordered_search_max_seconds` = **1800.0**（非 7200）；D 提示词 v2 回执

**更正来源**：执行方 D 提示词 v2 指出该键默认值应为 1800.0，我方独立字节复核**确认对方正确**——
profile v2 `key_off 0x174bc26a`（名字自证通过）/ `val_off 0x174bcc1f` = `66 00 00 00 00 00 20 9c 40` → **1800.0**；同 blob 内名表名次 = 值表名次 = 17。
我方旧读数 7200.0 取自**键名之后的相邻字节**（其后紧跟下一个键名 `min_supp…`）⇒ **相邻配对假象第 3 例**
（前两例：`offset_refine_dtw_min_score` 0.1→0.55、`commentary_short_scene_min_frames` 180→8）。

**系统对账**（新脚本 `mvp/scripts/reconcile_cutmatch_bindings.py`）：我方 11 条历史「相邻配对」绑定 vs profile v2 的 `val_off` 值 ——
**仅 1 条真错**（即本条），其余 10 条一致（含 `commentary_boundary_refine_max_move_frames` 的 `<<PREV>>` 解析后 = 16，与我方读数相同）。

**风险重估**：`ordered_search_max_seconds` = **1800 s = 30 min**，而本次**四部原片全部超限**
（2.mkv 7,667 / test1-om 8,229 / test3-om 10,177 / **test2-om 5,051**；按 7200 估时 test2-om 被误判为「安全」）
⇒ 执行方 v2 §P0-5 的处置（不施加全片上限或仅当单次搜索窗，并在 manifest 声明）**我方完全同意**，此为本轮最大假差异来源。

**已更正位置**：`INTEL_REQUESTS_CUTMATCH.md`（§8.2 + 回执）/ `FINDINGS_CUTMATCH_CONSTANTS_ADOPTION.md` / `.agent/STATE.md` / `.agent/TODO.md` / 本文件。

**新增待澄清 P0-8**：profile v2 中 `source_sample_rate` = **2**、`commentary_sample_rate` = **2**（均为 `<<PREV>>`），
与 `fast_options.source_global_fps = 1.0` 并存 ⇒ 需对方说明单位与作用阶段，并写入 manifest。

**产物**：`mvp/scripts/reconcile_cutmatch_bindings.py` · `work/binding_reconciliation.json` ·
`user_case/competitor_cutmatch/REVIEW_PROMPT_FOR_EXECUTOR_D.md`（已改写为 v2 回执版）。

## 2026-09-26（续 6b）— 竞品 B 段后处理规则**逐帧复现（24/24）**：11 的两条未知已解、峰值建议被实测否证；附 D 段提示词 P0 复核

**一、独立重放（只读对方产物，零 `mvp/src` 改动）**：用 `sandbox/out/*.probs.npy` 自己实现后处理，在 6 片 × 4 阈值 = **24/24** 上
切点集合**逐帧完全一致**，`groups_t*.json` 也 **24/24** 一致；覆盖区间内部 NaN 全 0（独立验证其 trim/stride 主张）。脚本 `mvp/scripts/replay_cutmatch_postprocess.py`。

**规则（确证）**：`active=prob>th` → 连续帧成组 → 组中点上取整 → **按切点间距 <8 迭代合并** → 取合并后跨距中点（取整同规则）。

**二、对 `FINDINGS/11` 的答复**：其「未知 1 组中点取整」= **上取整**、「未知 2 min_gap 保留谁」= **都不保留（迭代合并 + 跨距中点）**，两条**已解**（其它 5 种策略只能到 10–22/24）；
`sensitivity` **不参与**切点生成（不用它也能 24/24）。

**三、11 §4「峰值检测更稳」= 实测不成立**：峰值规则切点数 == 交付 0.50 档（71/34/66/87）、th=0.3 时 == 0.30 档（77/35/66/97）；
原因是激活组绝大多数为单帧（0.50 下多帧组占比 ≤7%，test1-ed/test2-ed 为 0%）⇒ 组中点本身即局部极大；真正自由度是**阈值与 min_gap**。

**四、「输出层换切点」探针（锚点 = 已裁决 44 例，不套 GT）**：我方 6 处假切点在 TN 概率上**既非峰也无值**（0.0001–0.021）⇒ 换 TN 口径**天然剔除**这 6 处；
但我方 29 处**已裁决为真**的切点在 TN 概率上也不是峰（中位数 0.0012）—— 它们与对方切点相距 0.6–5.0 s，是**另一处真切换**
⇒ **「换切点」≠「替换」，而是「并集 + 仲裁」**（与 A1 实测「直接换成 TN 切分 → 117→101」方向一致）。脚本 `mvp/scripts/probe_cut_swap.py`。

**五、D 段提示词复核**（`PROMPT_FOR_EXECUTOR_D.md`）：认可执行；补 **7 条 P0**（每段一行含未匹配行 / query_id 对应 B 段 scene_index / 时间码双写 /
候选表落盘 / **`ordered_search_max_seconds`（我方原记 7200 系相邻配对假象，经独立字节复核更正为 1800.0，4 部原片全部超限）的截断风险** / AKAZE 固定 seed / 原片索引口径明写）+ 5 条口径混杂因素
（224 vs 我方 518、编辑侧 2 fps 均匀 vs 5 关键帧/场景、候选池 28 vs 100+20、AKAZE 我方无此通道、GT 与判据）。

**产物**：`mvp/benchmark/user_case/competitor_cutmatch/FINDINGS_CUTMATCH_POSTPROCESS_REPLAY.md` ·
`user_case/competitor_cutmatch/REVIEW_PROMPT_FOR_EXECUTOR_D.md` · `mvp/scripts/replay_cutmatch_postprocess.py` · `mvp/scripts/probe_cut_swap.py` ·
`work/replay_postprocess.json` · `work/cut_swap_probe.json`（+ `INTEL_REQUESTS_CUTMATCH.md` 回执 §H）。

## 2026-09-26（续）— 代理复现 B 段判卷侧复核：几何对照定性逐片偏置、双实现交叉验证、44 张盲判包；我方两条旧异议自证后撤回

**背景**：执行方（`D:\claudework\cutmatch-analysis`）交付 B 段（代理复现场景切分）v4.2 全套产物。
我方按 `HANDOFF_B_STAGE.md` §4.2 分派，对已交付的 **ed 四片**做几何对照（不依赖仍缺的 2 片 om 与 D 段定位产物）。
定级写死：**「代理复现（推断级）」≠ 竞品实测**，结论只写"口径差异"。零 `mvp/src` 改动。

**一、交付物验收（我方独立复核，不采信文字）**
- **帧数**：我方自用 ffprobe（`-count_packets`，与对方不同调用路径）独立数 6 片 → 3677 / 183,837 / 4,070 / **197,106** / 2,083 / 4,357，与对方 `frame_counts.json` 逐片一致
  ⇒ **裁决 `test1-om.mkv` 以 197,106 为准**（锚点 197,305 = duration 8,229.28 s × 23.976 fps 估算，偏大 199 帧 ≈ 8.3 s）；**不要求重跑该片**。
- **模型字节级同一**：对方 `run_manifest.json` 的 `model_sha256 c4d54a68…8e0c` = 我方导出 `work/transnetv2/probe_transnetv2.onnx`（31,250,929 B）SHA256，**逐字符一致**。
- **三处规范偏差全部认可**；其中「ONNX 需 raw 0..255 而非 /255」**系我方任务书笔误**（`tn_transnetv2.py` 第 11 行原文即「值域 0-255(RGB)」），执行方实测纠正正确。

**二、几何对照（主结果，`geom_proxy_vs_ours.py` → `work/proxy_geom_*` 32 份 + `proxy_geom_summary.json`）**
- 切点口径统一为**段 start**（与对方 `cuts` 同义）：我方 `tn` 批是**非链式分段**（end_i ≠ start_{i+1}），首跑用 start∪end 得到 `ours_only 63` 属**假象**，已纠正。
- 对照现行生产切分（两级切分+白闪守卫，±0.5 s）：**test2 = 纯漏切画像**（仅代理 13 / 仅我方 0，且 0.3/0.4/0.5/0.6 四组**全部稳定**）；
  **test3 = 我方偏粗**（仅代理 23–34 / 仅我方 3–8）；**test1 = 反向，我方过切**（仅我方 7 / 仅代理 1）；2mkv 混合（12/4 附近）。
- 代理侧阈值稳定性：test2 **100%**、test1 97.1%、2mkv 80.5%、test3 77.5% ⇒ 后续任何"替换切分"回归必须按阈值分组报数。

**三、双实现交叉验证（本轮最有工程价值的一条）**
同一 ONNX（字节级同一）、**互不共享后处理代码**的两条实现（我方：window100/step50 重叠窗均值 + `pred>0.5` 上升沿；
对方：win100/stride50 + trim 25:75 + 阈值族 + `group_midpoint` + `min_gap 8`），在 ±0.5 s 内
**test1 32/32 · test2 65/66（98.5%）**，2mkv 67/76 · test3 84/93，中位距离 **0.10–0.17 s**
⇒ **B 段链路本身可信**，代理 vs 我方的差异可归因到**切分策略**，而非复现走样。

**四、盲判全量裁决（44/44 张，判卷侧逐张读图 + 帧差旁证）**
本地 VLM 仍 403 欠费 ⇒ 由判卷侧逐张读图完成全量 44 张（非抽样），并新增客观旁证 `mvp/scripts/blind_sidechannel.py`：
r = 跨点帧差(±0.07 s) / 同侧基线帧差。结果：**对方 29 个独有切点：真 27 / 未定 2 / 假 0**（r 中位数 3.10，**44/44 全部 r>=1**）；
**我方：真 36 / 假 6 / 未定 2**（r 中位数 1.66，**14/44 例 r<1** = 该点不是跨点帧差峰）。
我方 6 处假切点集中在 **test1（2.53 / 44.73 / 73.93）**，另 2mkv 113.17、test3 49.14 / 27.79（后者与 2026-09-26 border_review 独立裁决逐点吻合）；
机制 = 镜头内运动 / 字幕换行诱发的 CLS 距离峰。**test2 零假切点但漏切 13 处** ⇒ 「相邻真切换各选其一（粒度）」与「我方假峰」是**两个不同的病**，不能用同一药。
明细 `work/proxy_blind_disputes/verdicts_44.csv` / `verdicts_44_enriched.json`；**不套 GT、不进三指标**。

**五、我方两条旧异议：自证后全部撤回（新脚本 `verify_cutmatch_profile_pairing.py`）**
- **`source` 指针「不可独立复现」→ 撤回**：profile v2 约定即**字节偏移**（`key_off`/`val_off`/`raw`）。对 162 条独立验证：
  **名字自证 161/162**、**raw 逐字节 162/162 一致**、数值自证 162/162、**名表↔值表名次零颠倒**（blob 95/61/6 条）⇒ 顺序映射成立且可复现。
  上轮按 `@0x174e0158#116` 这类**序号**形式找 `8` 找不到，是**读法**问题。
- **`offset_refine_dtw_min_score` 0.1 vs 0.55 → 撤回，0.55 成立**：`val_off 0x174e18c8` = `66 9a 99 99 99 99 99 e1 3f` = 0.55；
  **0.1 属邻键 `offset_refine_dtw_sample_interval_seconds`**（`0x174e18d1`，紧邻 +9 字节）；我上轮引的 `0x174e04c1` 位于**另一区域**
  （其后紧跟 `T 01 aoffset_refine_dtw_sample_interval_seconds`）⇒ 系 `FINDINGS/09` 早期「相邻配对」取到邻键值位；对方 09 §296 / 10 §247 早已订正。

**六、新增对方动作项（不阻塞 D 段）**
① profile `/feature_extraction/image_size` 的 `key_off 0x174bc0cd` 实际解出 `feature_image_size`（1/162 名不符）；
② `197,305` 在 runbook §5.1 表 / `PROMPT_FOR_EXECUTOR.md` / `run_scene_split.ANCHORS` / `verify_proxy_output.ANCHOR_ORDER` **四处未同步**；
③ `FINDINGS/09` §82 旧表行建议标注"已被 §296 取代"。

**产品含义（有界）**：若要做"输出/展示层换更准切点"，**首选 test2**（代理 66 切点四阈值全稳、我方零独有 ⇒ 替换风险最低），
test3 次之（须按阈值分组验收），test1 属**反向问题**（我方更碎，不可直接替换）。**不改变** 2026-09-26 已定版四条立场；未改 GT / 索引 / runtime。

**产物**：`mvp/scripts/geom_proxy_vs_ours.py` · `visualize_proxy_disputes.py` · `verify_cutmatch_profile_pairing.py` ·
（扩展）`import_competitor_proxy.py`（新增 `--clip` 多片打包支持 + 切点口径 + ours_only 最近邻）+
`work/proxy_geom_*`（32 份）· `work/proxy_geom_summary.json` · `work/verify_cutmatch_profile_pairing.json` ·
`work/proxy_blind_disputes/`（44 张 + 答案键）+
`mvp/benchmark/user_case/competitor_cutmatch/FINDINGS_PROXY_B_STAGE_REVIEW.md`（+ `INTEL_REQUESTS_CUTMATCH.md` 追加回执节）。

## 2026-09-26 — 三指标口径审计（V5）：口径伪影量级 ≤ +2、三组对照稳健、非 HIT 主因重定位到定位层

**背景**：`HANDOFF_CUTMATCH_AND_METRIC_AUDIT.md` §3 断言「严格命中用 GT 编辑段中点代表整段 → 17/22 非 HIT 是口径伪影，
过去所有以 117/139 为标尺的对比（A1 −16 / ViT-B −1 / 场景聚合 −6）都带该噪声」。本轮把该假设做对做全并裁决。

**方法（零 `mvp/src` 改动，三个只读脚本）**：
`measure_recall_v5.py`（7 组判据并行：S/Z/T/R_rec/O/A/SE）、
`audit_retrieval_ceiling.py`（DML，139 例 × 6 个 GT 引导查询点，窗 ±0.5 s 取最佳帧全片 rank，218 s）、
`diag_nonhit_localization.py`（非 HIT 三层分诊）+ `visualize_loc_audit.py`（22 例全出图）。

**结果**：

| 判据 | 基线 | A1 TransNetV2 | ViT-B | 场景聚合(仅 2mkv) |
|---|---|---|---|---|
| S_strict（现行） | 117/139 | 101（Δ−16） | 116（Δ−1） | 29 / 27（Δ−6 / −8） |
| Z_point（零宽修复） | 118 | 101（−17） | 117（−1） | 29 / 27 |
| T_tol05（原片窗 ±0.5s） | 118 | 101（−17） | 119（+1） | 29 / 27 |
| **R_rec（推荐修正口径）** | **119** | 102（−17） | 120（+1） | 29 / 27 |
| O/A（重叠式宽松上界） | 117 / 118 | 101 / 102（−16） | 116 / 117（−1） | 29 / 27 |
| SE_diag（编辑窗 ±0.5s，**膨胀，拒绝**） | 123 | 115 | 120 | 30 |

**结论**：① 口径噪声量级 **≤ +2**（117→119），A1 差异 −16 → **「必须重跑四片基线」不成立**；
② 真正缺陷仅 2 例（`t1r08c` 零宽 GT 编辑窗公式缺陷、`t1r07a` 0.33 s 容差边界），均出图确认；
③ `SE_diag` 6 例翻转中 5 例严格编辑侧重叠 = 0.00（命中由**相邻编辑段**的大跨度场景 span 认领）→ 判为膨胀，不采用；
④ 139 例检索天花板 = HIT 117 / rank≤3 **19** / rank 4–20 2 / rank>20 **1**；
⑤ 非 HIT 22 例 = **口径 2 / 定位层 19 / 特征层 1（t2r05a，rank 77 sim 0.479）**；
⑥ 更正交接文档：A1 翻转实测 **退化 28 / 改善 12**（原文 32/12 算术不自洽）、`t1r08b` REAL_FAIL 系脚本边界 bug（rank 1）。
⑦ ViT-B 与基线差距在多判据下为 −1 ~ +1 → 表述改为「**该口径下两基座不可区分**」，不再称「轻微负向」。

**产物**：`FINDINGS_METRIC_CALIBER_V5.md`（`user_case/competitor_cutmatch/`）+ `work/recall_v5_{baseline,compare,saagg}.json` +
`work/loc_retrieval_audit.json` + `work/nonhit_diag.json` + `work/caliber_v5/*.png` + `work/loc_audit_visual/*.png`（22 例）。

**待拍板**：`R_rec` 是否写入 `measure_shot_recall` 并列输出；定位层方向是否重开（前置 = 无 GT 的查询点/子镜头选择信号）。

## 2026-09-25(续2) — 产品级定论：ViT-B 全量索引 + 四片 runtime 回归 = 无增益 → 「换更大基座」关闭

**方法**（零 `mvp/src` 改动）：导出 ViT-B/14 CLS-768 ONNX（346.5MB，torch↔onnx cos=1.000000）→ 隔离数据目录 `work/vitb_data` →
研究侧 monkey-patch FeatureStore（`feature_version=handwritten_vitb14_cls_768d@1_l2+scn1+evt1`、`feature_model=dinov2_vitb14`、接受 768 维）→
`device.onnx_model` 指向 ViT-B + `dml_batch_size=1`（实测 7.01 fps 最优）→ 生产 `SourceLocatorService.locate` 跑四片（31,117 帧 @1fps）。
**工具**：`export_dml_model_vitb.py` / `rerun_vitb_runtime.py` / `measure_four_results.py` / `diff_four_batches.py`。

**结果（vs 同 GT 同评估器基线批 117/139）**：

| 片 | 基线 严格/场景/负例/支撑 | ViT-B | Δ |
|---|---|---|---|
| 2.mkv | 35/39 · 39/39 · 3/4 · 182/343 | 36/39 · 39/39 · 3/4 · 199/332 | +1 / 0 |
| test1 | 34/43 · 42/43 · 0/1 · 109/220 | 35/43 · 40/43 · 0/1 · 101/203 | +1 / −2 |
| test2 | 14/20 · 19/20 · 0/1 · 71/229 | 14/20 · 19/20 · 0/1 · 77/233 | 0 / 0 |
| test3 | 34/37 · 37/37 · 1/3 · 230/349 | 31/37 · 36/37 · 1/3 · 220/309 | **−3 / −1** |
| **合计** | **117/139 · 137/139 · 4/9 · 592/1141** | **116/139 · 134/139 · 4/9 · 597/1077** | **−1 / −3** |

**关键观察**：① 27/139 案例翻转（严格口径 12 改善 / 13 退化）= 抖动而非系统提升；test1 t1r17/t1r18 由 HIT 变 MISS。
② 兄弟机位族主定位层未解决：p08 两侧主 span 均落在兄弟区（1061-1063 / 1034-1041），命中靠子 span 枚举，ViT-B 反把该段置信 HIGH→LOW。
③ 下游阈值未重标定导致漂移：切分段数 2.mkv 69→66 / test1 41→37 / test3 67→60，置信档分布同步变化。
④ 成本：索引吞吐 ~11 → 7.0 fps（四片 47→82 min），features.npy 47.8→95.8MB，ONNX 资产 88→346.5MB。
⑤ DML batch 不变性实测 cos=1.00000000 / max|d|≤1.1e-6 → batch 口径差异不构成偏置。

**裁决**：「该不该换更大基座（ViT-S→ViT-B）」= **不换（产品级，有据）**，与探针级 `FINDINGS_FEATURE_UPGRADE_V4.md` 收敛；
基座路线正式关闭。遗留可复用资产 = 一键换 backbone 四片回归 harness。
## 2026-09-25(续) — GT 污染审计 P0 第 2 项闭环：`phase24_1` 三探针 + M5 配修正 GT 重跑（研究侧）

**脚本**：`research_phase24_1_v4.py`（探针①几何/②运动，393 s）、`research_phase24_1_data_v4.py`（探针③盘点，27 s）、
`research_patch_recall_v4.py`（M5，1210 s，研究侧 DML 双输出 ONNX）。**报告**：`phase24_1/FINDINGS_V4.md`、`semantic_signal/FINDINGS_M5_V4.md`。

**phase24_1 ①视觉几何 = 原证伪证据作废**：原「p08b 兄弟压倒（真值 1048 HOM 0.488 vs 兄弟 1109 HOM 0.752）」中
**1109 本就是真值**（p08 正确位置 1108.15-1109.1），1048-1050 是已作废的 p38 旧错误 GT；p26「几何 rank 2 假阳性」同源于标错窗口。
修正后 **HOM（单应内点率）在 4 个硬例上把真值帧排 rank 1**（真值 0.849/0.752 > 兄弟 0.506/0.534），
但 **INL（部分仿射）判据相反**（真值 0.407/0.405 vs 兄弟 0.411/0.431）且真值窗内帧间跳变极大（1108 HOM 0.331 → 1109 0.849）；
另发现原存档 p08 的 `GEOM_HOMOG=[1,41]` 与其 FINDINGS 文字「兄弟反超」自相矛盾。→ 裁决：几何**既非已证伪也非已可用**，
列为待拍板复验方向（需固定 RANSAC 随机性 + 全索引池 + ≥3 组机位对照；纯 CPU，成本低）。

**phase24_1 ②运动签名 / ③硬负例盘点 = 维持**：修正 GT 后 6/6 探针 corr_margin 全负（含 sanity p01 −0.463/−1.357）；
硬负例量级一致（2mkv 49,572 / test1 51,284 / test2 26,018 / test3 91,827 / test4 31,737），修正锚点（p26@1769 场景 top 0.939）密度不降。

**M5 patch 召回 = 核心卖点作废**：原「patch 把兄弟机位捞回池（p08b 32→2）」在修正 GT 下反转为 CLS rank 5 / patch rank 9（NO_RERANK_GAIN）；
p26 修正后 CLS/patch 均 rank 1；p08 CLS 6→patch 5 维持；p01 CLS 2→patch 1 微弱。→ patch 作为独立召回通道**无信号**（与 M6 v4 0/39 一致）。

**失败族再收窄**：2.mkv 侧真实失败案例仅剩**兄弟机位族（p08/p08b）**；p26（夜读）在三份 v4 重跑中一致消解（ViT-S 全片 rank 1）。
两份受影响 FINDINGS 头部已加作废标注并指向 V4 版（防复发机制第 2 次执行）。

**产物**：`work/phase24_1_v4_probe_results.json` · `work/phase24_1_v4_data.json` · `work/patch_recall_v4_results.json`（各留副本于对应 user_case 目录）。
## 2026-09-25 — GT 污染审计 P0 闭环：`feature_upgrade` 配 v4 修正 GT 重跑（研究侧，零 runtime 改动）

**起因**：`FINDINGS_GT_CONTAMINATION_AUDIT.md`（09-22）指出「换更大基座（ViT-S→ViT-B）无效」这一被反复引用的结论，
其 9 个探针中 3 个建立在已证伪数据上（p26 GT 标错 / p08b 真值窗 1048-1050 = p38 旧错误 GT 区 / t4r01 test4 数据无效），
且「ViT-B 更差」的**最强证据**（p08b −0.138→−0.281）恰来自污染案例。

**执行**：`mvp/scripts/research_feature_upgrade_v4.py`（9 探针 / CPU / 1294 s / 一次 forward 同出 CLS+patch / 支持 `--only` 单探针复算），
真值窗取自 `ground_truth_v4.json` 与 `ground_truth_test3.json`；t4r01·t4r13 剔除、p08b 修正为 1108.15-1109.1、p26 用 1768.2-1770.05、
新增 t3r12（重复镜头硬例）；同一批嵌入帧上同时计算 v3 旧口径与 v4 修正口径两套标签。

**可信度自检**：v3 旧口径行**逐位复现原存档**（CLS 与 patch 两条通路全部一致），索引 `features.npy`/`times.npy` 与 `.idx.stale` 逐字节相同，
`D:\video\2.mkv` sha256 与索引记录一致（素材/ViT-S 基线未变）。首版脚本曾漏「逐帧 L2 再求均值」（p01 复算 0.7817 vs 存档 0.7869），已修并留痕。

**结果**：① p08b「ViT-B 恶化」= **GT 假象**（修正口径 S −0.0139 / B −0.0171，两者≈0）；
② 真失败族（兄弟机位 p08/p08b）**两基座都不可分**（margin ≈0、ViT-S 全片 rank 5-6）→「基座升规模不解决失败族」**复现**；
③ 修正口径 CLS **5:4** / patch **6:3**，除 p26 外 |Δ|≤0.08 → **无一致方向**；
④ p26「最硬案例」消失（正确位置全片 **rank 1**；9 探针中 7 个真值帧 rank 1）；
⑤ t3r10 旧「margin 恒 0」= 口径缺陷（真值窗与错位干扰窗共享 447 s 帧），修正后 S +0.019 / B +0.018。

**结论（表述改写）**：「换更大基座无效」→「**无一致增益，且不解决失败族；原最强反证是 GT 污染假象（已撤回）**」；
「不建议 bump feature_version 全量重建」**维持**（依据换成修正口径）。残留问题：本探针 ViT-B 侧为局部窗口嵌入，
不能回答「ViT-B 能否把 CLS 漏掉的正确区召进池」；产品级定论需 ViT-B 全量索引 + 四片 runtime 回归（~半天 GPU，当前证据不支持其必要性）。

**防复发机制（部分落地）**：`feature_upgrade/FINDINGS.md`、`phase24_1/FINDINGS.md`、`semantic_signal/FINDINGS_M5.md` 三份文档加「GT 版本」标注头；
审计新增 §八「GT 版本登记表」；仍缺「GT 修正时自动列出受影响结论」。

**产物**：`mvp/scripts/research_feature_upgrade_v4.py`｜`work/feature_upgrade_v4_results.json`（副本 `mvp/benchmark/user_case/feature_upgrade/`）｜
`mvp/benchmark/user_case/feature_upgrade/FINDINGS_FEATURE_UPGRADE_V4.md`｜`.agent/TODO.md` P0 更新。
## 2026-09-22 — macOS 打包链路集中修复（5 个 commit，全部已 push）

mac 包从「整包 Mock + 打不开」到端到端跑通（实测：索引 6798 帧 / 553.8s @MPS；定位 36 段 / 1017.5s，
23 高 / 3 中 / 8 低）。暴露的 5 个缺陷**全部属于打包/分发链**，非算法问题：

- `83c73e1` **整包跑 Mock（最隐蔽）**：`.gitignore` 的 `.env.*` 排除了 `mvp/ui/.env.production` → CI checkout 无该文件 →
  `VITE_BACKEND_MODE` 未定义 → `resolveService()` 回落 `MockServiceAdapter`（恒报「已连接」+ 日志 `[mock] log line 1/2`，
  分析永不结束）。修：生产构建默认 `http`（不依赖 env 文件）+ workflow 显式注入 + gitignore 放行 `.env.production`。
- `bb419c0` **ffprobe 动态链接崩（每次建索引必崩）**：CI 用 Homebrew 动态 ffmpeg，只 copy 二进制进 bundle →
  用户机 `dyld: Library not loaded .../libavdevice.63.dylib`。修：改用 `static_ffmpeg` 静态构建 + CI `otool` 防回归。
- `78bee3d` **剪映导出缺 `pyJianYingDraft`**：该模块在 `exporters.py` 函数内延迟 import，mac CI 从未安装；
  且依赖 `pymediainfo`，mac 上它不自带 dylib、需系统 `libmediainfo`（无 fallback）。修：CI 装包 + `brew install libmediainfo`
  + spec hiddenimports + 把 `libmediainfo.0.dylib` 装进 `_internal/pymediainfo/`（pymediainfo 从自身包目录加载）+ 缺失硬失败。
- `cbed284` **`pyJianYingDraft/assets/*.json` 未收集**：`get_asset_path()` 基于 `Path(__file__).parent` 读包内模板，
  而 PyInstaller 只收代码不收 data file → `Asset file ... does not exist`。修：`collect_data_files("pyJianYingDraft")`。
  ⚠️ **Windows 包同样受影响**（现存 win-unpacked 无 `_internal/pyJianYingDraft`）。
- `ff71db6` **设备标签厂商中立化**：`AMD GPU (DirectML)`→`GPU (DirectML)`、`Apple GPU (MPS)`→`GPU (MPS)`；
  下拉框改由后端 `available_devices` 驱动（Windows 不再出现 Apple/MPS 字样）；`device_settings()` 补 MPS 探测。

验证：前端 vitest 67/67 + typecheck、后端 test_settings 4/4、YAML/Python 语法、`collect_data_files` 实收 2 个 JSON，全绿。
遗留：mac CI 重触发验证导出；**Windows 包需重打**；`patch reranker` 仍跑 CPU（可选优化）。详见 `.agent/STATE.md` 2026-09-22。

## 2026-09-04 — 研究侧收尾归档(M6 v4 + M4/M8 v4 + ⑩ p08b 复核) + 三指标基线固化(measure_baseline.py)

- **p36 细切分取证(2026-09-04, 用户假设验证)**: 数据实验——整段查询(现状)未命中, 单帧 110.75 独立查询→[2040-2044] 命中 GT,
  机制=3 帧 argmax 分散(1856/2042/2829)→2042 单例簇被 min_frames=2 门掉+scene 回退漏正确 scene 232;
  VLM 多模态复审(BEST_WINDOW=W0 2040-2044, YES; W1 2060-2065 仅 PARTIAL)→ 双证据闭合: 细切分救回的是内容真匹配位置;
  **用户人工复审已确认(2026-09-04): ED↔W0(2040-2044) 匹配, ED↔W1(2060-2065 当前定位) 不匹配** —— 三方证据
  (数据实验+VLM语义+人工)完全闭合, 细切分救回成立, 非相似度巧合。
- **test 域细切分扫描(2026-09-04, 用户拍板第 2 步)**: 24 段严格未命中中 6 段「单帧可命中」候选, 4 段基线已 HIT(无增量);
  **真新增 2 段(t2r02b/t2r03a) VLM 语义复审 + 用户人工复审(与 VLM 一致)全部不成立**——t2r02b 单帧窗与 ED 不匹配
  (假阳性候选), t2r03a 现状整段定位反而更匹配(细切分会回退) → **test 域真实新增严格命中 = 0**。
- **最终决策(2026-09-04)**: 方案 A(单帧强证据保留) **不实施**(收益仅 +1/p36 且 t2r02b 假阳性风险, ROI 不成立);
  B(scene 回退扩容) 顺带关闭; **C(编辑侧 2fps→8fps+细切分) 记录入 TODO, 下个对话做**。产物 FINDINGS_P36_FINESEG.md
  + work/fineseg_scan_test.json + work/fineseg_review/。

- **M6 v4 重算(2026-09-01)**: RESCUE 0/39、CLS 池外 0、CLS 池内 39/39 —— v3 的 10 条「CLS 池外」全是 GT 标错假象;
  p13「patch 唯一救回」也是 GT 错(v4 CLS best=1)。patch 召回 runtime 化零增量, 方向彻底关闭(有据)。
- **M4 v4 重跑**(仅 p26, DML 664s, research_semantic_signal_M4_density_v4.py): **反转**——v4 真值下
  p26 在 1fps 稀疏索引即 best_rank=1、margin=+0.2802(correct 0.8757 vs dist 0.5955); 旧 M4「12→43 恶化/margin −0.28」
  是错误 GT 假象(p26 非特征上限, 与 M6 v4 CLS best=1 双向闭合); 8fps 密帧 rank 持平 1、margin 略降 → 密度方向维持关闭。
- **M8 v4 重跑**(纯 numpy 秒级, research_provenance_neighbor_v4.py): p26 真值/干扰互换后仍 AMBIGUOUS(uniq 差 0.027);
  p08 维持 AMBIGUOUS(真值邻接 0.7744 反而更不唯一); t3r12 维持; p38(已删)/t4r01(数据错误)剔除。邻接唯一性方向关闭。
- **⑩ p08b 复核 = 作废(污染残留)**: M5「patch 救回兄弟机位 32→2」真值窗(1048-1050)=p38 旧错误 GT 区;
  v4 正确位置=1108.15-1109.1, M6 v4 证 p08 CLS rank=6(池内)/patch 6 零增量 → E21/M5 该正面结论作废。
- **FAILURE_TAXONOMY 收尾归档**: 失败族最终 = p08(2.mkv 唯一兄弟机位) + t3r12(test 域); p26 移除(GT 错实证)、
  test4 逻辑剔除; A 类(召回失败)在 2.mkv 为空(CLS 39/39 全部进池)→ 研究侧全维度闭环, 不再立项新探针。
- **三指标基线固化**: measure_shot_recall.py 重构抽 evaluate()(CLI 输出不变) + 新建 measure_baseline.py
  (默认=文档基线批 2.mkv→user_results.json、test1-3→cases/*_results.json; --use-rerun 切换 2026-09-02 重跑批)
  → 输出 work/baseline_v4.json。**验证与 GT_BASELINE 文档完全一致**: 2.mkv 32/39 场景 36/39 负例 2/4 支撑 79/137;
  test1 32/43 场景 38/43 负例 0/1 支撑 103/158; test2 9/20 场景 10/20 负例 0/1 支撑 13/40;
  test3 31/37 场景 34/37 负例 2/3 支撑 102/149。(注: 2.mkv 支撑 79 vs STATE 旧记 80 = 历史快照差 1;
  test1 rerun 批 97/152 vs 文档批 103/158 = 子 span 枚举差异, 严格/场景/负例两批完全一致。)
- 零 runtime 改动; ⑦ 保守化标定仍冻结; 三指标 v4 基线不受影响。

- **同日追加 — ① p28/p36 召回层深漏验证**: p28 在 rerun 批已 HIT(旧「深漏 800s」基于旧批已修复);
  p36 正确帧在 CLS top-20(rank 2/3, M6 v4)但被「帧级 argmax 分散→单例簇 min_frames=2 门掉 + scene 回退
  top-5(297/235/216/217/228)未含正确 scene 232[2034-2044]」两级淘汰 → **定位选择问题, 非召回层**;
  **2.mkv 无召回层缺口**(39/39 进池已证)。剩余真漏 = p08(兄弟机位特征上限) + p36(定位选择, 机制已复现)。
- **同日追加 — ② 评测口径澄清(宽松口径)**: 严格 32/39 → 宽松①(±6s/覆盖≥30%) 35/39(+p20/p34/p41 边界偏差/GT前移)
  → 宽松②(±15s/覆盖≥30%) 37/39(+p05/p35 修正后未跟上); **真实失败仅 p08+p36(与①双向闭合)**;
  汇报口径建议宽松② 37/39(94.9%), 严格 32/39 为回归上限并标注 5 条口径低估; 不触碰 ConfidenceConfig(⑦ 冻结)。
- 产物: FINDINGS_P28P36_RECALL_VERIFY.md + FINDINGS_LENIENT_V4_METRICS.md + mvp/scripts/measure_lenient_v4.py。

- **④/⑩ 细节补充(2026-09-04 同批工作)**: M8 v4 中 p08 真值邻接唯一性 0.7744 vs 干扰 0.6930(真值更不唯一);
  M4 v4 中 8fps 密帧 margin 0.2467(略降); p08b 复核判定「patch 救回」是把正确画面匹配到错误但相似的士兵特写窗。

### Notes

- Created `checkpoint-2026-09-04-2256.md` checkpoint (183 modified/untracked file(s)).

- Created `checkpoint-2026-09-04-1810.md` checkpoint (168 modified/untracked file(s)).

- Created `checkpoint-2026-09-04-0207.md` checkpoint (154 modified/untracked file(s)).

## 2026-09-22

### 续19（2026-09-28）— 档案读完 + T1 五条

- **Added**：`engine/localization/degradation_gate.py`（重复率退化拒绝门 + 子 span 覆盖门槛 +
  `fragment_warnings` 导出碎片告警 LOC-2001）、`mvp/api/session.py`（本机令牌门禁 + 发行通道缺令牌拒启）、
  `infrastructure/logging.redact_text`/`RedactingFilter`、`errors.public_error()` + 全异常类 `code`/`user_message`、
  脚本 `replay_degradation_gate.py` / `visual_gate_flips.py`、文档 `FINDINGS_DEGRADATION_GATE_AB.md`、
  测试 `mvp/tests/test_degradation_gate.py`(17) + `test_logging`(+10 脱敏) + `test_domain_infrastructure`(+3 码) +
  API `SessionGateTest`(5) + 前端门禁 bootstrap(4)。
- **Changed**：`load_config` 的 media/device/pipeline/export 覆盖改为 dataclass 字段泛化驱动
  （曾静默忽略 `vote_prior_*`/`subshot_*`/`patch_v2_*`/`dense_recheck_*`/`edited_cache_enabled`），
  未知键告警、`bool("false")` 解析修正；`/api/export` 响应新增 `warnings`；异常响应统一带 `code`/`message`；
  `PRODUCT_INTRO` 性能与命中率口径改实测值；`edited_cache._atomic_save` 补 fsync 文件+目录；
  Electron 打包态注入一次性会话令牌并经页面 query 传给渲染进程。
- **Verdict（实测否决，代码保留默认关）**：退化拒绝门双臂 = 严格 117→103（−14）、场景 137→125、
  负例 4/9 不变、支撑 591→390；消融 −8/−7、阈值 0.95 仍 −8；逐图 2 张证实被拒的是正确答案
  （竞品判据长在 scene→scene 架构上）。测试基线：后端 324 / API 66 / 前端 73 / typecheck 干净。

### Added

- None.

### Modified

- `.agent/STATE.md` / `.agent/TODO.md`（续10m 条目 + 移植立项拍板项; 续11 移植完成条目）。
- `FINDINGS_FAST_GLOBAL_REPRO.md` §5（移植落地 + 生产回归结果）。
- 后端全套 279 测试全绿（272 + 新增 7）。

- Updated `.agent/STATE.md` last-updated timestamp.

### Fixed

- None.

### Removed

- None.

### Notes

- Created `checkpoint-2026-09-22-2035.md` checkpoint (7 modified/untracked file(s)).

### Notes

- Created `checkpoint-2026-09-25-1921.md` checkpoint (32 modified/untracked file(s)).

## 2026-09-26

### Added

- None.

### Modified

- Updated `.agent/STATE.md` last-updated timestamp.

### Fixed

- None.

### Removed

- None.

### Notes

- Created `checkpoint-2026-09-26-0143.md` checkpoint (42 modified/untracked file(s)).

### Notes

- Created `checkpoint-2026-09-26-1356.md` checkpoint (54 modified/untracked file(s)).

### Notes

- Created `checkpoint-2026-09-26-1535.md` checkpoint (68 modified/untracked file(s)).

## 2026-09-26（续 10b）— GT 线索撤回（候选表反转）+ 竞品关键功能差距分析（用户实测前提确立）

- **用户前提确立**：竞品在相同素材端到端更好（用户另一台电脑实测），不再作为"未测"搁置——分析目标改为定位能力差距。
- **GT 线索双双撤回**：t1r08b 实为 q0013 top1 命中 GT 窗（复核脚本"每 GT 只取一行"的选择偏差）；t1r12a GT 在候选 rank2
  （分差 0.032 骑 tie_margin 边缘）。**正面发现：复现候选生成把 GT 内容排 top1/top2** —— TN 场景+5 关键帧配方的候选层很强。
- **主交付 `FINDINGS_CAPABILITY_GAP.md`**：差距 = 组合链（TN 切分 → 每场景 5 关键帧代表 → patch 0.55 主力 → 路径一致性 → AKAZE），
  我方每环都有对应物但形态不同；历史"单环替换全失败"恰因未测组合。方法论教训 = 三指标奖励 GT 对齐不奖励几何正确（A1 −16 是口径惩罚）。
- **建议立项（待用户拍板）**：「TN 子单元 + 关键帧查询」混合探针（G1+G2+G7，研究侧零 runtime，验收=四片不回退+稀释族改善+TN 边界输出）。

## 2026-09-26（续 10c）— 用户拍板：下一步 = 「竞品全流程组合探针」单片先行（交接）

五环全开（TN 全流程边界+段内单元 / 每场景 5 关键帧+长场景加密 / patch 主力 0.55 / 匹配目标函数路径项 / AKAZE 候选几何校验），
**先只跑一个测试视频**（建议 test1：GT 43 条 + 复现缓存全在 + 基线 34/43 已知）。
执行基础 = 复用 `cutmatch-analysis/sandbox/run_localization.py`；增量 = G5 路径一致性项 + **判据同粒度化**
（候选层指标 = GT 在 top-k 名次 + span 截到查询等长双口径——TN span 装配效应已证伪裸严格指标）。
决策与验收设计全文见 `DECISIONS.md` 2026-09-26；执行清单见 `TODO.md` P0 顶部；差距分析 = `FINDINGS_CAPABILITY_GAP.md`。
GT 线索 t1r08b/t1r12a 撤回（候选表反转）。`agent-context checkpoint` CLI 本机不可用，已手工完成 STATE/TODO/DECISIONS/CHANGELOG 四件套更新。

## 2026-09-28

### Added

- `PROJECT_AUDIT_20260928.md`（续13 全项目结构化审计: 残留判定/旋钮活性/GT 漂移/open item 对账）。
- `competitor_cutmatch/FINDINGS_COMPETITOR_FULL_SWEEP.md`（竞品数据段全量扫穿, 续12: 完整性矩阵 + 新发现清单 + 挖穿宣告）。
- `work/full_sweep_blobs.txt`（282 blob 全量摘要, 扫描底稿）。
- **续14 — 竞品四项加权置信公式移植（conf_v2）= 实测结案，维持默认关不移植**：
  `mvp/src/engine/confidence/confidence_v2.py`（纯函数，四项加权 + 四类低置信原因门）+
  `ConfidenceConfig.conf_v2_*` 11 旋钮（**默认关**）+ `ConfidenceEngine._apply_conf_v2`（只降不升）+
  UI `reasons.ts` 6 条文案 + `mvp/tests/test_confidence_v2.py`（13 项，含「默认关与现行行为逐字节一致」守护）。
  回归 harness `mvp/scripts/rerun_conf_v2.py`、分析 `mvp/scripts/analyze_conf_v2.py`、
  多模态出图 `mvp/scripts/visual_conf_v2_review.py`；产物 `work/confv2_{case}.results.json` /
  `confv2_diag_*` / `confv2_analysis.json` / `work/confv2_visual/*.jpg`(33 张) /
  报告 `competitor_cutmatch/FINDINGS_CONF_V2_PORT.md`（含 GT 版本头）。
  **数字**：四片 231 段定位逐位一致，三指标 119/139·137·4/9·支撑 591/1140 与基线批逐条判定全等；
  v2<0.6 共 16 段而 15 段已被硬 flag 判 LOW（重叠 93.8%），唯一非冗余迁移 test3 r16 读图证实方向正确；
  真病灶 test1_r21（错 21s）/2mkv_r26（错 18s）v2 未接住（0.752/0.866）。全套 **292 测试全绿**。
- **续14 — GT 版本登记推断级提案表** `semantic_signal/GT_VERSION_REGISTER_PROPOSAL_20260928.md`：
  32 份未登记文档分 8 类（不适用/本体即 GT 记录/现行 139/✅有 v4 重跑/v3 时代需指向/晚于正式化/无法判定），
  并登记一条新引用风险（竞品线 7 份文档的「基线 117/139」自 09-27 续11 起应为 119/139）。**未生效，待用户选落地方式**。
- **续14 — memory 新增跨项目协作纪律**：`verification-must-be-multimodal`（GT/指标只是代理，结论前逐张读图）。

- **续16 — Track A 产品断链修复（5 项）**：A1 模型资产完整性（`asset.json` 写 `sha256`/`size_bytes` +
  `DirectMLBackend.verify_asset()` 加载前校验，摘要不符即 DeviceError 不静默加载、历史资产 legacy 放行 +
  三处 `torch.load(weights_only=True)`）；A2 `preprocess_sha` 真判据（`preprocess_probe_bytes()` 取
  **真实预处理行为指纹**，`create_index` 写入、`validate_index` 比对，历史索引一次性回填放行）；
  A3 新增 `POST /api/results/load` 端点 + `HttpServiceAdapter.loadResults` 接通（重启不再丢结果与手修）；
  A4 `ResultsPage` 导出面板暴露置信门槛/低置信处理/边界吸附（默认值与旧行为逐字一致）；
  A5 `serviceIsMock()` + App 顶部 Mock 常驻横幅（防 09-22 那类静默跑在 Mock 上恒显"已连接"）。
  新增单测：资产 4 + 预处理 4 + API 3 + 前端 2；后端 **294** · API **61** · 前端 **69** + typecheck 全绿。
- **续16 — 性能基准脚本** `mvp/scripts/bench_perf_tiers.py`：10/60/128min 三档建索引 + 128min 真实配对
  首次/复跑定位 + 峰值 RSS + 进程 CPU 秒 + 索引体积；RAM/CPU 走 ctypes（psapi/kernel32）**不引入 psutil**；
  素材用 ffmpeg `-c copy` 流复制截短（`work/bench_src/`），数据目录隔离 `work/bench_data/`。
### Modified

- **续14 — 档案卫生**：`AGENTS.md` 三处过期表述加标注（v1 GT「不得修改」→ 已证伪留档；研究时代 `src/benchmark.py`
  命令段加 MVP 现役入口指引；「无测试框架无 CI」→ MVP 层 unittest 292 + api + vitest 实测命令）；
  `.agent/INDEX.md` GT 行与 `mvp/tests` 行数（≈80 → 292 项，模块清单更新）。
- Updated `.agent/STATE.md` / `.agent/TODO.md` / `.agent/DECISIONS.md`（续14 结案条 + Known Issues 置信层条）。

- `CONFIDENCE_DESIGN.md` 顶部加「实现现状」注（single-answer 链路已删、§2 信号表保留为设计史）；
  docstring 中把 `produce_candidates`/`localize_segment` 当生产路径的表述全部改指 `EvidenceLocalizer`。
### Fixed

- **续14 — 编辑侧缓存键剔除 `confidence`**（`locator_service._edited_fingerprint`）：缓存键原为
  `asdict(config.pipeline)` **全量**（含嵌套 confidence 子字典），导致任何置信调参（含 conf_v2 A/B、
  未来翻默认开）都触发 A4 编辑缓存全量失效重算（实测多花 ~100s/片）。置信不参与编辑侧特征，剔除后消除。
- **续14 — 更正档案错值**：竞品置信 margin 门限 `min_candidate_margin` = **0.03**（profile_v1 options 簇，
  `val_off` 名次配对确证），BREAKTHROUGH §9b 原记 0.1 系 `fast_timeline/confidence` 自身 blob 的
  「相邻配对假象」（该块参数名与 reason 字符串交错），0.1 实为 `local_refiner` 同名键。

- **续16 — 删除孤儿置信链（用户拍板）**：`ConfidenceEngine.assess()` 及 7 个专属 helper、
  `engine/localization/pipeline.py`（`localize_segment` + `RefinedSegment`）、仅该链消费的
  `ConfidenceConfig.nreps_dispersed`/`max_similar`/`scene_div_montage`、全仓无消费点的 `SeqAlignConfig.vectorized`。
  ⇒ **更正续13 审计「0 死旋钮」结论**（实为 1 纯死 + 3 仅孤儿链消费）。
  顺带发现 `scripts/smoke_locator_service.py` **在本次删除前就已坏**（patch 目标 `app.locator_service.produce_candidates`
  /`.localize_segment` 早已不存在）→ 已删；`diag_user_signals.py` 依赖 `assess()` 随链删（产物 JSON 留档）。
  `produce_candidates` 同属孤儿链但**保留**（删它会连带删掉 ranking 层唯一测试覆盖）→ 待用户拍板。
- **续16 — 基准脚本首版三处自纠**：① 隔离 `SVL_DATA_DIR` 会连带隔离 ONNX 资产查找 → 静默 fallback CPU
  （CPU 数字不能验证 GPU 承诺），现显式指 `SVL_DML_MODEL` 并**硬断言**后端必须是 `DirectMLBackend`；
  ② `build_original_index` 返回 `IndexBundle` 而非 `IndexMeta`（取 `.meta`）；
  ③ ctypes 度量补 `argtypes/restype`（HANDLE 被当 32 位截断 → 返回 -1）且 CPU 秒改为 user+kernel。

### Added（续17 补充）

- **续17 — 竞品 103 叶子模块逐文件穷举对齐**：`competitor_cutmatch/FINDINGS_CAPABILITY_MAP_20260928.md`
  新增表 D（逐模块：竞品语义 + blob# 证据 + 我方 `文件:行` + 判定）、表 E（复核推翻的 5 条断言修正记录）、
  最终差集 TOP8。穷举基线 = `cutmatch-analysis/data/cutmatch_module_map.txt` 137 dotted 模块
  （34 包级 `__init__` + 103 叶子）；中间产物 `work/module_blob_index.txt` / `work/module_leaf_list.txt`。
- **续17 — 性能基准实测落地**：`work/bench_perf_tiers.json` + `MVP_ROADMAP §7` 表首次填数（H2 DirectML 列）：
  建索引 10/60/128min = 44.6 / 260.3 / **562.7s**（13.47~13.83fps，索引 1.08/6.34/**13.21MB**，
  峰值 RSS 745/758/**1812MB**）；128min 真实配对定位 首跑 769.1s、缓存复跑 483.3s；全流程 22.2 分钟。
- **续17 — 一条对外承诺被实测证伪**：`PRODUCT_INTRO:52`「同一成片重复定位约 2~4 分钟」缺前提——
  原数字源自 test1（41 段）热缓存 167s，而 69 段实测 483.3s = **8.1 分钟** ⇒ 耗时随**编辑段数**线性变化。
  已在 `MVP_ROADMAP §7` 写明并列为待拍板文案修订项；「2 小时影片索引 7~12 分钟」则**实测成立**（9.4 分钟）。
- **续17 — 复核推翻子代理 5 条断言并留痕**（表 E）：我方实有 `shell.openPath`（`main.ts:61,174`）、
  `CREATE_NO_WINDOW`（`_runner.py:23,61`）、`ffmpeg_io` 的 `scale=` 参数（生产从不调用）、
  `TaskManager._lock`（只护字典，确无并发准入）；可比对模块数是 101 而非 137。
  ⇒ 重申纪律：任何转述断言须核到 `文件:行号`。
- **续18 — 补漏：竞品逆向实为三个工作区路径**（用户指出后自查确认此前只扫了 `cutmatch-analysis`）：
  `D:\dsh-work`（授权体系逆向）与 `D:\cm`（竞品真实安装目录）完全未扫，导致表 D 的 `licensing.*` 8 行只有一句
  "缺失（商业化）"。按用户拍板**只归档授权体系架构**→ `FINDINGS_CAPABILITY_MAP_20260928.md` **表 F**
  （卡密双代际 / 六步签名校验含 nonce 防重放 / 14 返回码 / TPM+Secure Enclave+KSP 与禁止静默降级 /
  状态文件 candidate→fsync→原子 replace / 本机服务门禁四路校验 + 处理令牌 TTL / `ReleaseProfile` 五开关 /
  AES-GCM 模型 + 租约按需解密）；**漏洞清单、攻击路径排序、内存命中地址一律不纳入本方档案**。
  产出 4 条我方可评估项：构建期配置缺失即拒启闸门、**`mvp/api` 本机 HTTP 无任何鉴权**、
  `errors.py` 缺稳定对外码/话术层、`edited_cache` 原子写未 fsync 目录。
- **续18 — 修正两处档案失真**：① `dsh-work` 两份报告抬头「纯静态（未运行任何程序）」与主报告 §3.5–3.7 的
  **动态验证**（注入 `AUTOCLIP_*` 启动竞品、直读 sidecar PEB 环境块、扫 687 个内存区）自相矛盾
  ⇒ 已在两份文件顶部加「口径校正」注（以正文为准，抬头作废），并把 `阶段一 §6` 三条破解待办逐条标废，
  与 STATE 既有「不绕授权」口径重新对齐；② `阶段一 §1` manifest「208 文件」错，
  实数 `D:\cm\cutmatch-sidecar.manifest.json` = **202 条**（与 `FINDINGS/03` 一致）。
  同类失真亦存在于长期 memory（曾记「竞品从未运行」），已一并更正。

### Removed

- 零功能影响瘦身 1.19GB → `D:/claudework/benchmark_trash_20260928/`（dist_backend 883MB + build_backend_work 245MB +
  loc_smoke 63MB + 34 个 __pycache__; 全部可还原）。移动后 279 测试全绿 + 生产链路 import 验证通过。

### Notes

- Created `checkpoint-2026-09-28-1423.md` checkpoint (151 modified/untracked file(s)).

- Created `checkpoint-2026-09-28-0149.md` checkpoint (98 modified/untracked file(s)).

- 竞品数据段挖穿宣告成立：139 个中文 docstring blob = 竞品全部自有代码（语义 100% 可读已扫）, 其余 144 blob 为第三方库/空块/
  字频表/Tauri 资源; option_catalog 自有 644 键 100% 镜像 profile_v1。重大翻转(主对话抽查证实) = N1 ordered_search_*/N4 path_*/
  置信公式完整权重(0.4/0.3/0.2/0.1 门限 0.6)全部绑定在 profile fast_options ⇒ 「N1 族值未绑定/等机器码」结论推翻,
  机器码专项静态理由大幅缩水。其他新发现: speed_fill ±10% 变速补齐 / patch top-16 token 公式直证 / 401AutoClip 产品代号 /
  授权体系全貌 / .cmlog 加密日志格式 / SceneRuntime 滑窗 / FAISS IndexFlatIP / 显存自适应批次 / max_duplicate_scene_ratio=0.8。
  静态挖穿关闭; 唯二遗留 = 常量运行期默认值(需动态验证) + patch_top_k=100/global_weight=0.45(强推断)。

## 2026-09-27

### Added

- `mvp/src/engine/localization/offset_vote_prior.py`（偏移投票起点先验, 竞品 coarse_retrieval 语义重建）+
  PipelineConfig 五旋钮（默认关）+ `locator_service._apply_offset_vote_prior` 挂接 + `tests/test_offset_vote_prior.py`（7 项）。
- `mvp/scripts/rerun_vote_prior.py`（四片双臂回归 harness）+ `work/voteprior{,_dense}_{case}.results.json` +
  `work/voteprior{,_dense,_baseline}_metrics.json`。
- DECISIONS 2026-09-27 立项条目（偏移投票起点先验移植, 用户拍板）。
- `work/proxy_loc_review/verdicts_2mkv.csv`（D 段复核 2mkv 五桶 24 张逐图裁决明细）。
- `REVIEW_NOTES_PROXY_D_STAGE.md` 新增 §2mkv（A/C/D/E 四桶逐图裁决 + 中期结论）。
- `competitor_cutmatch/FINDINGS_FAST_GLOBAL_REPRO.md`（快速模式全局层完整复现, 续10m）。
- 外部仓 `sandbox/run_fast_repro.py`（F1 3fps 采样 / F2 偏移投票 / F3 两遍路径 DP+恢复候选 / F4 种子对接）+
  `run_localization.py` start_override 参数（默认 None=交付口径逐字节不变）。
- 判卷产物 `work/fasts_probe_{test1,test2,2mkv,test3}.json` / `work/fast_probe_test1.json` / `work/fastw_probe_test1.json` +
  `work/ours_mainspan_truncated_caliber.json`（我方生产同口径 77/139）。

### Modified

- Updated `.agent/STATE.md` last-updated timestamp.

### Fixed

- None.

### Removed

- None.

### Notes

- Created `checkpoint-2026-09-27-2006.md` checkpoint (93 modified/untracked file(s)).

- 偏移投票起点先验移植完成（续11, 用户拍板立项）：生产四片 117 -> 119/139（+2 零回退, 场景/负例持平）；
  投票+密集复核臂同 119。默认关维持, 待 UI/导出验收后翻默认开。零回退验收通过。
- 竞品对标第三阶段（续10m, 用户拍板「深挖全层」）：快速模式全局层完整复现完成。三臂归因（test1）= DP 选路有害（5/43, −8）,
  种子叠加贪心胜出（23/43, +10 零退化）；四片 100/139（p0f 89, +11 复现新高）。同口径对照 = 我方生产 main span 77/139
  vs 复现链 100/139 ⇒ 全链闭环后唯一大差距项 = main span 起点的「跨查询全局共识先验」缺失（落后 +23）。
  待拍板 = 偏移投票起点先验移植立项。零 mvp/src 改动。
- D 段代理复现复核：2mkv 五桶图 24/24 张判卷侧读图补裁完成（2026-09-27）。结论 = 既有定论全部维持：proxy 严格增益中真赢仅 p23/p30（baseline main span 错实例），错例 5 例全落已知失败族（p21 错场景 / p25 相似夜景 / p28 重复实例 / p08 兄弟温室 / p01 切点前镜头），拒识 2 例蒙太奇型，装配效应 1 例（p20）；n01 误配与历史同区同机制（图证确认）+ n02 误报；E 桶无虚高。新增图证 = baseline 2mkv 的 HIT 有 ≥7 例靠子 span 兜底（main-span-only 基线 23/39 的图证）。0 例新错误机制、无新增 GT 复核线索。产物更新：`REVIEW_NOTES_PROXY_D_STAGE.md` / `FINDINGS_PROXY_D_STAGE_REVIEW.md` §7 / STATE / TODO。

- Created `checkpoint-2026-09-27-2003.md` checkpoint (92 modified/untracked file(s)).

- Created `checkpoint-2026-09-27-2002.md` checkpoint (91 modified/untracked file(s)).

- Created `checkpoint-2026-09-27-0600.md` checkpoint (85 modified/untracked file(s)).

### Notes

- Created `checkpoint-2026-09-28-1512.md` checkpoint (178 modified/untracked file(s)).

### Notes

- Created `checkpoint-2026-09-28-1641.md` checkpoint (181 modified/untracked file(s)).

### Notes

- Created `checkpoint-2026-09-28-1749.md` checkpoint (189 modified/untracked file(s)).

### Notes

- Created `checkpoint-2026-09-28-1750.md` checkpoint (190 modified/untracked file(s)).

### Notes

- Created `checkpoint-2026-09-28-2152.md` checkpoint (196 modified/untracked file(s)).

### Notes

- Created `checkpoint-2026-09-28-2347.md` checkpoint (197 modified/untracked file(s)).

## 2026-09-29

### Added

- None.

### Modified

- Updated `.agent/STATE.md` last-updated timestamp.

### Fixed

- None.

### Removed

- None.

### Notes

- Created `checkpoint-2026-09-29-1733.md` checkpoint (225 modified/untracked file(s)).

- Created `checkpoint-2026-09-29-1621.md` checkpoint (223 modified/untracked file(s)).

- Created `checkpoint-2026-09-29-1602.md` checkpoint (222 modified/untracked file(s)).

- Created `checkpoint-2026-09-29-1520.md` checkpoint (219 modified/untracked file(s)).

- Created `checkpoint-2026-09-29-1348.md` checkpoint (207 modified/untracked file(s)).

- Created `checkpoint-2026-09-29-1206.md` checkpoint (206 modified/untracked file(s)).

- Created `checkpoint-2026-09-29-1120.md` checkpoint (203 modified/untracked file(s)).

- Created `checkpoint-2026-09-29-0921.md` checkpoint (198 modified/untracked file(s)).

### Notes

- Created `checkpoint-2026-09-29-1826.md` checkpoint (232 modified/untracked file(s)).

### Notes

- Created `checkpoint-2026-09-29-2021.md` checkpoint (240 modified/untracked file(s)).

### Notes

- Created `checkpoint-2026-09-29-2029.md` checkpoint (241 modified/untracked file(s)).

### Notes

- Created `checkpoint-2026-09-29-2048.md` checkpoint (242 modified/untracked file(s)).

### Notes

- Created `checkpoint-2026-09-29-2050.md` checkpoint (243 modified/untracked file(s)).

### Notes

- Created `checkpoint-2026-09-30-0053.md` checkpoint (254 modified/untracked file(s)).

### Notes

- Created `checkpoint-2026-09-30-0105.md` checkpoint (255 modified/untracked file(s)).

### Notes

- Created `checkpoint-2026-09-30-1947.md` checkpoint (1 modified/untracked file(s)).
