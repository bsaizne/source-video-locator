# Phase 24-2 · 多模态召回探针 M2 FINDINGS —— 字幕事件语义召回(方向 C 首次实测)
> ⚠️ **test4 数据错误(2026-09-01):** test4-ed.mp4 与 test4-om.mkv 为两部不同电影(81s竖屏 vs 71min横屏), 本文件中依赖 test4/t4r01 的结论全部作废(逻辑剔除, 详见 datasets/real/test4-INVALID.md)。

> 日期:2026-09-01 | 性质:**研究侧探针(零 runtime 改动, VLM 调用 24 次)**
> 起因:用户拍板「结合多模态判定」后,进一步拍板测**字幕语义召回索引**(方向 C 的正确用法)
> ——此前方向 C 只列远期、从未建过字幕→原片场景的召回通道;这是「早期纯视觉决策是否
> 错过多模态红利」的直接裁决。
> 脚本:`mvp/scripts/research_semantic_signal_M2_subtitle_recall.py` | 数据:`work/semantic_signal_M2_results.json`
> 前置:M1(FINDINGS_M1.md)= 字幕语义弱信号、VLM 事件级判定证伪

## 探针设计

M2 换 M1 的视角:不做「判定」(候选池内选对),做**「召回」**——字幕描述的**具体事件**
(如 test4「二十多人被困滑梯管道」)能否在原片候选窗中命中正确事件。用 VLM EVENT-MATCH
(字幕文本 + 候选窗帧 → 该事件是否发生在画面中),判据 = 正确窗命中率 vs 干扰窗命中率。

环境约束:本机**无文本嵌入模型**(sentence-transformers/transformers/fastembed 全 MISS),
无法做向量双塔检索 → 探针用 VLM 语义匹配形态(受限但诚实的最小版)。

## 结果

### p26 夜读 = ✅ 字幕语义召回首次正面信号(3/3 vs 1/3)

字幕:「She used binoculars to watch what Levi was doing」(她用望远镜看 Levi 在做什么)

| 窗 | EVENT YES | VLM 理由 |
|---|---|---|
| **真值 [2808-2811]** | **3/3** | 2808.2「woman holding and looking through binoculars」/ 2809.5「circular vignette = view through binoculars looking at Levi」/ 2810.8 同上 |
| 干扰 [1766-1770] | 1/3 | 1769.8「circular vignetting typical of binocular point of view」 |

→ **字幕语义精确匹配原片真值区**(望远镜视角看 Levi 的画面),视觉 CLS 分不清的
夜读/夜阳台,**字幕能分**。这是**方向 C 首次展示真实判别力**,也是 p26 上
第一个正向信号(M1b 帧级事件判定在 p26 是反向的 0/3)。

### t3r12 精灵王 = ⚠️ 弱正向(2/3 vs 1/3)

字幕:「But the Elven King just stands there and watches」(精灵王只是站着看)

| 窗 | EVENT YES | VLM 理由 |
|---|---|---|
| 真值 [454-480] | 2/3 | 467.0「Elven King (Thranduil) present, observing」/ 479.8「standing and observing」;454.2 NO(骑鹿非站着) |
| 干扰 [481-488] | 1/3 | 484.5 YES(山丘上站着看);481.2 NO(骑鹿)、487.8 NO(Thorin 非精灵王) |

→ 字幕能部分区分正确/干扰重复实例(命中正确窗更多),但区分度弱——重复镜头语义同貌,
干扰区 484.5 也命中同一「精灵王站着看」事件。

### test4 同质滑梯 = ❌ 0/3 全 NO(字幕与画面解耦)

字幕(法语):「Plus de vingt personnes sont restées coincées dans le tube du toboggan」
(二十多人被困在滑梯管道里)

| 窗 | EVENT YES | VLM 理由 |
|---|---|---|
| 真值 [3335-3350] | **0/3** | 3335.2「people already in pool at end, no one stuck」/ 3342.5「empty slide structures」/ 3349.8「one shirtless person splashing」 |
| 干扰 [3319-3329]/[3355-3359]/[3359-3377] | 0/3 × 3 | 全部「没有二十多人困在管道」的实景 |

→ 字幕描述的事件(二十多人被困管道)在**原片画面里根本没有对应**——解说字幕是
**叙事文案**(编辑者要讲的故事),与原片(水上乐园怪谈恐怖片)画面**解耦**。

## 净结论

1. **方向 C(字幕语义召回)不是全盘证伪——p26 首次展示真实判别力(3/3 vs 1/3)**。
   字幕精确描述原片画面事件(望远镜视角看 Levi)时,字幕语义召回**有效**,能分清
   视觉 CLS 分不清的夜读/夜阳台。这修正了此前「方向 C 结构性不可行」的悲观判断。
2. **但适用边界明确:字幕事件必须与原片画面有真实对应才有效**。
   - p26 有效:原片真值区恰好是字幕描述的「望远镜看 Levi」画面;
   - test4 无效:字幕讲「新闻叙事」(二十多人被困),原片画面没有该实景 → 解说文案与画面解耦。
3. **t3r12 弱正向**:重复镜头语义同貌,字幕区分度有限(2/3 vs 1/3)。
4. **环境约束**:无文本嵌入模型 → 当前只能 VLM 逐窗匹配,无法建可检索的向量索引;
   若立项需先引入文本嵌入模型(sentence-transformers 类)或逐场景 VLM caption 化。
5. **零 runtime 改动**;三指标 39/41 不受影响。

## 诚实边界

1. p26 为**单案例正面**(且该案例字幕与原片画面对应性强);t3r12 弱、test4 无;
   「字幕召回有效」需更多样本(尤其更多「字幕精确描述画面事件」的案例)才能定论。
2. VLM 单帧单判;字幕取编辑段中心 1 帧 OCR(未做整段旁白聚合)。
3. 本探针为「研究侧验证信号存在性」,不含:字幕→原片全场景索引构建、文本嵌入模型、
   召回集成进 runtime——那些是立项后的事。
4. test4 的 0/3 也可能受「候选窗未覆盖字幕事件对应画面」影响,但全窗 0/3 强提示
   字幕与画面解耦,非抽样误差。

## 交接(待用户拍板)

M2 给出了方向 C 的**首个正面信号(p26)**与清晰边界(字幕-画面对应性)。后续选项:
- **A. 立项「字幕语义召回」完整验证**:引入文本嵌入模型 → 建「字幕语义→原片场景」索引
  → 在更多案例上量化召回增益(重点收集 p26 型「字幕精确描述画面事件」案例)。
  工作量一大阶段;收益待定(仅 p26 单例正面)。
- **B. 记录为「弱正向信号,待更多样本」**:维持零 runtime,方向 C 保留为已知弱信号,
  不再投入;失败族维持已知局限。
- **C. 结合局部 patch 级召回一起立项**:把字幕召回(视觉之外的弱通道)与纯视觉的
  patch 级召回(①③)合并成「两阶段多通道检索」大阶段。

## 相关产物

- 脚本:`mvp/scripts/research_semantic_signal_M2_subtitle_recall.py`
- 数据:`work/semantic_signal_M2_results.json`
- 前置:M1(`semantic_signal/FINDINGS_M1.md`);P1/P2/P3 FINDINGS 见 `semantic_signal/`
