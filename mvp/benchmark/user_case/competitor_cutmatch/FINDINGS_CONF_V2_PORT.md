# FINDINGS — 竞品四项加权置信公式移植（conf_v2）= 产品价值 1/231，建议维持默认关

> **GT 版本**（登记规则①）：现行 **139 条 verified**（`ground_truth_v4.json` + `ground_truth_test1/2/3.json`，
> 2026-09-02 定案 + t2r07c 09-06 修正）。**GT 仅用于事后核对，未参与公式任何计算**（护栏保留项）。
> 定级：**实测（我方生产管线双臂）**，非代理复现。日期 2026-09-28。

## 1. 背景与形态

竞品 `fast_timeline/confidence.py`（docstring「按采样、偏移支持、局部一致性和候选差距给出稳定置信度结论」）
的四项加权公式常量已字节确证（profile_v1 `fast_timeline.options`，blob `0x174bb2ea`）：

```
score = 0.4*local + 0.3*coarse + 0.2*consistency + 0.1*margin
门限 min_confidence_score=0.6；min_valid_samples=3 / min_support_ratio=0.35 /
     min_local_score=0.55 / min_candidate_margin=0.03
```

护栏「Confidence 公式冻结」经用户 2026-09-28 窄范围豁免（详见 `.agent/DECISIONS.md` 同日条）。
移植形态 = 用户拍板 **并行通道 + 只降不升**：现行 6 软信号合成分与「任一硬 flag → LOW」全部不变，
`score_v2 < 0.6` 时仅 HIGH→MEDIUM / MEDIUM→LOW，**永不升档、不改 `score` 数值**。
consistency 输入 = 用户拍板「现有簇内分散度」，实现时改为无量纲的 `coverage_quality`（理由见 §4）。

代码：`mvp/src/engine/confidence/confidence_v2.py` + `ConfidenceConfig.conf_v2_*`（11 旋钮，默认关）
+ `ConfidenceEngine._apply_conf_v2`；UI `reasons.ts` 加 6 条文案；单测 `mvp/tests/test_confidence_v2.py`（13 项）。

## 2. 四片双臂实测（GPU DirectML/amd，与 119/139 现役基线同配置）

| 片 | 段数 | 定位逐位一致 | score_v2 区间 | 中位 | v2<0.6 段数 | **档位迁移** | HIGH∧GT=MISS OFF→ON |
|---|---|---|---|---|---|---|---|
| 2mkv | 69 | ✅ | 0.541–0.885 | 0.756 | 2 | **0** | 1 → 1 |
| test1 | 41 | ✅ | 0.739–0.941 | 0.841 | 0 | **0** | 3 → 3 |
| test2 | 54 | ✅ | 0.229–0.882 | 0.750 | 6 | **0** | 1 → 1 |
| test3 | 67 | ✅ | 0.417–0.879 | 0.757 | 8 | **1**（HIGH→MEDIUM） | 0 → 0 |
| **合计** | **231** | **✅ 全等** | — | — | **16** | **1** | **5 → 5** |

- **三指标零回退（逐位）**：严格 **119/139** · 场景 **137/139** · 负例 **4/9** · 支撑 **591/1140**，
  与 `work/voteprior_*.results.json` 基线批**逐条 139 项判定全等，差异 = NONE**（脚本级核对，非目测）。
- **v2<0.6 的 16 段里 15 段本就已被硬 flag 判 LOW** ⇒ 与现行链路的重叠率 **93.8%**。
- 唯一非冗余迁移 = `test3 r16`（ed 0:39.2–0:40.1 → og 434–436，v2=0.5861，
  reasons `weak_offset_support` + `weak_local_consistency`）。
- 后端全套 **292 测试全绿**（含缓存键改动后重跑）。

## 3. 多模态逐张读图（用户纪律：GT 不是唯一复核标准）

产物 `work/confv2_visual/`（2mkv 11 张 / test1 9 张 / test3 13 张），判读 8 张关键样本：

| 样本 | 画面事实（读图） | v2 判定 | 结论 |
|---|---|---|---|
| `test1_r21` HIGH∧MISS | 编辑帧=雾中马+跟随狐狸进洞；**GT 52:51 正是岩石洞口+小狐狸**；算法定位 52:30 空旷荒原夜景，**错 21s** | 0.7522 **未接住** | **真病灶，v2 无效** |
| `2mkv_r26` HIGH∧MISS | 编辑帧=男子侧脸举双筒望远镜；**GT 26:25 同姿势同机位**；算法定位 26:43（同演员同场景另一镜头），**错 18s** | 0.8656 **未接住** | **真病灶，v2 无效** |
| `test1_r13` HIGH∧MISS | 编辑帧=金发男肩扛农具走过草坡；定位 49:11–49:13 **同人同姿势同背景**；GT 48:42 是同场景另一动作（劈木桩/举手） | 0.8564 未接住 | **假病灶**（GT 窗侧问题，本就不该降档） |
| `test3_r16` 唯一迁移 | 定位 span 前两帧=金币堆缠斗，**第三帧 7:16 是绿色大厅两矮人持剑**（跨镜混入无关内容） | 0.5861 **判不稳** | **v2 方向正确**（硬 flag 漏抓） |
| `2mkv_r61` v2gate | 定位 span 混入**另一男子**侧脸镜头（编辑帧是女子侧脸） | 0.5411 判不稳 | 方向正确，但现行已 LOW（冗余） |
| `2mkv_r55` v2gate | 主 span 是女子在望远镜旁另一镜头，与编辑帧（暗处人影+胡子男特写）不同 | 0.5913 判不稳 | 方向正确，但现行已 LOW（冗余） |
| `2mkv_r31` 负例 n01 | 编辑帧与定位帧=**同一女子、同一栏杆场景**（原片帧带望远镜圆形暗角） | 0.8512 高分 | 与档案「n01 同人同景」记录一致，非 v2 可辨 |
| `2mkv_r33` 负例 n02 | 定位 span 首帧是男子看书（不同人），后两帧=同一女子仰头特写 | 0.858 高分 | 未接住 |

**读图带来的两个反转**：① 5 条 HIGH∧MISS 里至少 `test1_r13` 是 **GT 窗侧假病灶**（画面其实匹配），
「病灶有 5 条」这个前提本身被 GT 口径夸大；② 真病灶（r21/r26）形态 = **同场景内选错时刻 18–21 秒**，
与 `FINDINGS_METRIC_CALIBER_V5.md` 的「非 HIT 主因 = 定位层 19 例」完全对上。

## 4. 根因（为什么竞品公式搬不动）

四项信号在我方证据簇上的分布与竞品不同构，**三项恒饱和**：

- `margin`：clean 单证据簇 `secondary=None` → 恒 1.0（与 2026-09-01 原型实验记录的同一机制）；
- `coarse`：我方用 `evidence_qcov`（保留 span 覆盖编辑帧比例）代理，绝大多数段 ≥0.85；
- `consistency`：实现时发现**不能**用簇内 `timestamp_std`——它是「原片 best_t 尺度」，随段长自然增大，
  借竞品 0.35s 锚会把长段一律判死；改用无量纲 `coverage_quality`（单峰集中度）。
  竞品该项源自**全片 3fps 逐样本偏移投票**共识，我方无对应物（续10j 已实测「窗口局部重算的分散度不分真假」）；
- 只剩 `local`（`best_sim`）有真实变化，但权重 0.4 独木难支。

⇒ 竞品该公式的判别力**寄生在它自己的检索/精排景观上**，与我方 `v2_score` + 证据簇体系不同分布。
这与「全局层语义是管线级属性，不可拆解为局部判据」（续10j 定论）是同一件事，只是发生在置信层。

## 5. 建议

**维持 `conf_v2_enabled=False`，不作为产品行为启用**（不移植）。理由：231 段仅 1 段有效降档（0.43%），
对主要病灶（同场景选错时刻）零判别力，而 93.8% 的判断已被现行硬 flag 覆盖。
模块 + 旋钮 + 单测**保留为基础设施**（同 `dense_start_check.py` 处置先例：默认关、零生产影响、未来可复用）。

### 5b. 启用前必须先补的接线缺口（本轮自查发现，如实登记）

本报告正文说「只降档不改定位」——对**定位与三指标**成立（实测逐位全等），但**对产品影响面不止于此**：

1. **导出集合会变（重要，本文初稿漏写）**：`app/exporters.py:93-121 build_export_plan` 按
   `confidence.level` 过滤，`min_confidence=MEDIUM` + `low_policy=exclude`（均默认）下，
   **MEDIUM→LOW 的降档会让该段直接不进导出工程**。也就是说 conf_v2 一旦启用，
   影响的不只是 UI 徽章颜色，而是用户拿到的剪映/PR 工程内容。若将来启用，必须同步复核定档与导出策略。
2. **双降档通道无叠加仲裁**：`_apply_conf_v2`（confidence.py:167，逐段）与
   `_apply_temporal_ambiguity`（locator_service.py:809→1718，全批后处理）都会下调 level，
   执行顺序 = 先 v2 后 ta，两者可叠加（HIGH→MEDIUM→LOW）且无幂等标记或降档上限说明。
3. **诊断值不落盘**：`ConfidenceAssessment.confidence_v2`（score_v2 + 四项信号）在
   `_result_from_evidence` 处被丢弃，`domain.Confidence.to_dict` / `api/schemas.py` / `ui/types.ts`
   均无该字段 ⇒ 产品内无法 A/B 复盘，目前只有 `scripts/rerun_conf_v2.py` 旁路记录（本轮数字即由此而来）。

## 5c. 顺带发现的两处既有档案/审计错判（与 conf_v2 无关，但由本次自查暴露）

- **续13 全项目审计的「0 死旋钮」结论不准确**（实测复核）：
  ① `SeqAlignConfig.vectorized`（config.py:118）全仓**无任何消费点**，是纯死旋钮（注释自述「未来整段对齐用」）；
  ② `ConfidenceConfig.nreps_dispersed` / `max_similar` / `scene_div_montage`（config.py:67/70/72）
  只被 `ConfidenceEngine.assess()` 链路（confidence.py:307/314/324/326/348）消费，
  而 `assess()` 的唯一入口是 `engine/localization/pipeline.py:58 localize_segment`——
  **`localize_segment` 在 `mvp/src` 与 `mvp/api` 中无生产调用者**（只有 tests 与 smoke 脚本在跑），
  即整条 single-answer 编排是孤儿路径，这三个旋钮在产品运行态实际不生效。
  处置需用户拍板（删除属破坏性且牵动测试；保留则应在 config 注明「仅 legacy 路径」）。
- 澄清一条被夸大的告警：`locator_service.py:894/909` 的 `getattr(cfg, "subshot_enabled", True)`
  因该属性**确实存在**（config.py:260 默认 False），兜底值永不生效 ⇒ 不构成行为翻转 bug（仅写法易误读）。


**明确不建议做的事**：调 `min_score`/权重去「凑」出更多降档——那等价于用 GT 结果反标定，
越出本次豁免边界（保留项「不用 GT 字段」），且 2026-09-01 置信标定研究已证该方向无内部信号。

**若未来重开置信层**，前置条件 = 先有非饱和的第二信号源（真正的跨样本偏移共识通道，
或 `offset_vote_prior` 的 `support_ratio`/`dispersion_s` 常态化产出——目前它只在触发时才有值）。

## 6. 产物索引

- 代码：`mvp/src/engine/confidence/confidence_v2.py`、`engine/confidence/confidence.py`（`_apply_conf_v2`）、
  `infrastructure/config.py`（`conf_v2_*`）、`mvp/ui/src/utils/reasons.ts`
- 测试：`mvp/tests/test_confidence_v2.py`（13 项）；全套 292 绿
- 回归：`mvp/scripts/rerun_conf_v2.py` → `work/confv2_{case}.results.json` + `work/confv2_diag_{case}.json`
  + `work/confv2_rerun.log`；三指标 `work/confv2_four_metrics.json`
- 分析：`mvp/scripts/analyze_conf_v2.py` → `work/confv2_analysis.json`（迁移矩阵/交叉表/分位/按判定分组）
- 图证：`mvp/scripts/visual_conf_v2_review.py` → `work/confv2_visual/*.jpg`（2mkv 11 / test1 9 / test3 13）
- 决策：`.agent/DECISIONS.md` 2026-09-28（豁免范围 + 常量权威值 + `min_candidate_margin` 0.1→0.03 更正）
