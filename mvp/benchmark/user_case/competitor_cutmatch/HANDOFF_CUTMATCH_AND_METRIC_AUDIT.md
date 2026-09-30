# HANDOFF —— 竞品对标 + 切分/评估口径审计（2026-09-25 会话交接）

> ⚠️ **2026-09-26 更正（见 `FINDINGS_METRIC_CALIBER_V5.md`）**：本文件 §3 的「口径伪影」结论**量级被高估** ——
> 在 runtime 三指标层，把判据放宽到「任意 ≥0.5 s 重叠」只让基线 **117 → 118/139**（推荐修正口径 119），
> 22 例非 HIT 中**只有 2 例**与判据有关（1 例零宽 GT 编辑窗的结构性缺陷 + 1 例 0.33 s 容差边界）；
> 其余 20 例机制为**定位层 19 / 特征层 1（t2r05a）**。故 §5.1「必须重跑四片基线」**不成立**：
> A1(−16/−17)、ViT-B(−1~+1)、场景聚合(−6/−8) 在 7 组判据下**全部稳健**。
> 另更正 §0 的 A1 翻转数（实测退化 28 / 改善 12，原文 32/12 算术不自洽）与 §3 的 `t1r08b` REAL_FAIL
> （系审计脚本边界 bug，窗内最佳帧 rank 1 / sim 0.838）。**编辑窗 ±0.5 s 判据属口径膨胀（邻段大场景 span 认领），不采用。**

> **GT 版本**：\`ground_truth_v4.json\` + \`ground_truth_test1|2|3.json\`（139 正例 / 9 负例，v4 口径）
> **基线批**：\`work/rerun_<case>_perfopt.results.json\`（生产两级切分 + 白闪守卫）＝ 严格 117/139、场景 137/139
> **性质**：竞品对标 + 研究侧审计　**runtime 改动**：零（本会话所有脚本都在 \`mvp/scripts\` 与 \`work\`，未改 \`mvp/src\`）

## 0. 五条结论（按重要性）

1. **⚠️ 最重要：我方「严格命中」口径存在系统性缺陷** —— 它用 **GT 编辑段中点**代表整段，
   当 GT 窗跨越多个镜头或窗很窄时，中点会落到**错误的镜头**上，把"实际命中"判成 MISS/part。
   实测：四片非 HIT 的 22 例中，**17 例（77%）在真值窗内都有 rank ≤ 3 的帧**（\`work/rescue_audit.json\`）。
   ⇒ **过去所有以"严格 117/139"为标尺的对比（A1 的 −16、ViT-B 的 −1、场景聚合的 −6）都带这个噪声。**
2. **竞品的切分确实更准（几何）**：盲判显示"仅 TransNetV2 独有"的切点 **8/8 是真切换**，
   "仅我方基线独有"的只有 **2/8（2mkv）、4/6（test3）**——我方既过切又漏切。
3. **但不该把 TN 切点用进定位层**：A1 实测替换后严格 117→101（−16）；相似度场景聚合也救不回来
   （2mkv 35→29/27）。正确落点是**导出/展示层**（用户看得见的那一层），或作为**段内子 span**。
4. **不要抄 \`feature_image_size=224\`**：视觉 + margin 双重检验，518 在 4/5 难例上更强（p08 兄弟机位 −0.157）。
5. **失败族叙事需要重写**：t3r12（"重复镜头失败"）**翻案** —— 6/6 查询点真值窗内最佳帧 **rank = 1**；
   视觉上查询与 466s 就是同一条麋鹿镜头。所谓 rank 1055 是"窗中心 472s 落在另一镜头"造成的伪结论。

## 1. 竞品对标：做过什么、结论是什么

### A1 —— TransNetV2 替换编辑侧两级切分（\`FINDINGS_TRANSNETV2_SEGMENTATION.md\`）
- 依据：竞品 137 模块图 \`matching.scene_detection.*\` ↔ a01 = TransNetV2（容器级确证）；
  a02 = DINOv2 ViT-S/14 且**未微调**（与官方权重 SHA256 逐字节一致）。
- 方法：官方代码 + 官方权重（state_dict 90 张量 / 7,618,056 元素 == a01 明文计数），
  ONNX 对拍官方 PyTorch **max|diff| = 6.1e-8**；零 \`mvp/src\` 改动（monkey-patch \`_segment_twopass_flash\`）。
- 结果：**严格 117→101/139（−16）**、场景 137→120、负例 4→3；翻转退 32 / 改 12。
- 边界证据：与基线双向 recall 0.76–0.98、中位距离 <0.1 s ⇒ **判的是同一批边界，差异在粒度**。

### 盲判 —— 谁的切点更准（\`FINDINGS_TN_CUT_QUALITY_VS_METRIC.md\`）
| 案例 | 仅基线独有（真切换） | 仅 TN 独有（真切换） | 集合关系 |
|---|---|---|---|
| 2mkv | **2 / 8** | **8 / 8** | 分歧对称 |
| test2 | — | 8 / 8（抽样） | **基线切点 ⊂ TN 切点** |
| test3 | **4 / 6** | **8 / 8** | TN 多检出 25 个 |

素材：\`work/border_review/*.png\`（每行 t−0.5 / t−0.1 / t+0.1 三帧）。

### A2 —— 对齐分用于候选排序（\`FINDINGS_ALIGNMENT_RANKING.md\`）
- 事实核查：我方**已有** \`engine/localization/seq_align.py\`（单调 DP，REUSE research \`ta.py\`）且**已接入 runtime**（窗内 moment 精修）。
- 138 例：rank 改善 18 / 恶化 37 / 持平 83，平均 rank 2.43→2.80 ⇒ **不引入排序层**。

### 输入尺寸 224 vs 518（本会话新增）
| 探针 | 224 | 518 | Δ |
|---|---|---|---|
| p08 兄弟机位 | +0.2315 | **+0.3882** | −0.157 |
| p08b | +0.0101 | **+0.1033** | −0.093 |
| p26 夜读 | **+0.3104** | +0.2874 | +0.023 |
| p01 易例 | +0.1091 | **+0.2009** | −0.092 |
| t3r12 | **+0.4143** | +0.3753 | +0.039 |

视觉图（\`work/input_size_visual/*.png\`）显示 224 明显糊掉窗格/人脸/暗部 ⇒ **不抄**。

## 2. 竞品常量情报（来自 \`cutmatch-analysis/FINDINGS/09\`）

**已高置信绑定（27 项，节选）**：\`source_global_fps=0.1\`、\`commentary_sample_fps=3.0\`、\`dense_sample_fps=10.0\`、
\`balanced_coarse_sample_fps=5.0\`、\`feature_image_size=224\`、\`scene_proxy_height=720\`、\`global_weight=0.45\`、
\`patch_weight=0.55\`、\`scene_top_k=10\`、\`global_top_k=100\`、\`offset_refine_min_score=0.55\`、\`offset_refine_min_support=2\`、
\`offset_refine_dtw_max_samples=64\`、\`offset_refine_dtw_start_window_radius_frames=30\`、
\`offset_refine_dtw_start_window_min_improvement=0.04\`、\`commentary_boundary_refine_proxy=96×54\`、
\`long_scene_min_seconds=6\`、\`long_scene_max_keyframes=16\`、\`long_scene_probe_window_seconds=3\`、
\`long_scene_probe_stride_seconds=1.5\`、\`min_candidate_margin=0.1\`、\`offset_bucket_seconds=0.5\`。

**两处必须记住的修正**：
- \`0.55/0.35/0.62\` **不是** \`commentary_scene_dual_*\` 阈值（线性对齐已证伪）；
- \`commentary_short_scene_min_frames=180\` 绑定正确但**语义未定论**（按 6 s 合并实测灾难）。

**A1/A2 核心阈值（dual/visual/structure/motion/flash）仍未绑定** —— 在机器码里，需读 code object 常量索引。

**值得抄的三条**（我方完全没有的机制）：
1. \`patch_weight 0.55 + global_weight 0.45\` 的**加权融合打分**（我方 patch 只做门控 rescue）；
2. **两级采样**：原片全局 0.1 fps 粗筛 + 局部 10 fps 密验（我方是单一 1 fps + 8 fps 密查询）；
3. \`offset_refine_*\` 门限（H4 场景级 offset 路径选择用）。

## 3. ⚠️ 评估口径审计（本会话最重要产出）

\`work/rescue_audit.py\` / \`work/rescue_audit.json\` / \`work/rescue_audit/*.png\`：

| 判定 | 例数 | 含义 |
|---|---|---|
| **SUSPECT_METRIC** | **17** | 真值窗内存在 rank ≤ 3 的帧 ⇒ 实际命中，被"窗中点"口径误判 |
| PARTIAL | 3 | 窗内最佳 rank 5–7 |
| REAL_FAIL | 2 | t1r08b、t2r05a |

**视觉抽检结果**（推翻 REAL_FAIL 标签）：
- \`2mkv/p14\`：窗内最佳帧（1380–1381s, sim 0.79–0.90, **rank 1–2**）与查询视觉一致（森林雪地）；
  而"窗中心"rank 7150 ⇒ 口径问题确证。
- \`test1/t1r08b\`：全片 top1 = **2922.0s**，GT 窗是 **[2922.2, 2924.2]** —— **只差 0.2 秒**！
  我的脚本用 \`times >= 2922.2\` 把 2922.0 排除，才导致"窗内最佳"变成 2924.0（坐着的人，视觉不像）。
  ⇒ **也是口径伪影（1 fps 粒度 vs 2 秒宽 GT 窗）**。

⇒ **结论：22 例"非 HIT"里，至少 17+2 例是口径伪影；真正待定的只剩 \`test2/t2r05a\`（rank 77）。**

**建议的新口径（供后续拍板）**：
- 判定"命中"时不要用**单个中点**代表整窗，而用**窗内最佳帧的 rank**（或编辑段多点查询后取最佳）；
- 或至少把 GT 窗边界做 **±0.5 s 容差**再取中间帧；
- 三指标（严格/场景/负例）**不能**再作为"A 方案 vs B 方案谁更好"的唯一标尺 —— 本会话已出现
  −16（A1）、−1（ViT-B）、−6（场景聚合）三种噪声量级的差异，而它们是同一批口径伪影的函数。

## 4. 产物清单

| 文件 | 内容 |
|---|---|
| \`FINDINGS_TRANSNETV2_SEGMENTATION.md\` | A1：TN 替换四片回归 |
| \`FINDINGS_TN_CUT_QUALITY_VS_METRIC.md\` | 盲判 + 场景聚合 + 口径解释 |
| \`FINDINGS_ALIGNMENT_RANKING.md\` | A2：对齐分排序无增量 |
| \`INTEL_REQUESTS_CUTMATCH.md\` / \`TASK_FOR_REVERSE_AGENT.md\` | 给逆向对话的需求单 |
| \`RUNBOOK_COMPETITOR_MEASUREMENT.md\` | 竞品实测采集清单（实测受阻于授权） |
| \`mvp/scripts/tn_transnetv2.py\` / \`probe_transnet_bounds.py\` / \`rerun_transnet_runtime.py\` | TN 推理与边界/定位 harness |
| \`mvp/scripts/probe_transnet_variants.py\` / \`rerun_scene_agg_runtime.py\` | 变体筛选 + 场景聚合 harness |
| \`mvp/scripts/research_dtw_rank.py\` / \`research_input_size_probe.py\` | A2 探针、224 vs 518 探针 |
| \`mvp/scripts/probe_export_cut_split.py\` | 导出层 TN 重划验证 |
| \`work/border_review/*.png\` | 分歧切点视觉素材 |
| \`work/fullpool_visual/*.png\` | 全片池竞争帧（p08 兄弟机位视觉确证） |
| \`work/input_size_visual/*.png\` | 224 vs 518 视觉对照 |
| \`work/subshot_check/t3r12_rows.png\` | t3r12 翻案图 |
| \`work/rescue_audit/*.png\` + \`.json\` | 22 例非 HIT 重估图与数据 |
| \`work/scene_agg_stats.json\` / \`tn_variants_summary.json\` / \`tn_four_metrics.json\` | 支撑数据 |

## 5. 下一步（按优先级，供下个对话拍板）

1. **口径修正（最高优先）**：把"真值窗内最佳帧 rank"或"多点查询取最佳"作为新的命中判定，
   **重跑四片基线**，得到一份"去掉口径伪影"的真实指标；然后**重估** A1/ViT-B/场景聚合三组对比。
2. **产品/导出层采用 TN 切点**（几何正确即用户价值；已用 \`probe_export_cut_split.py\` 验证可行，
   边界位移仅 0.03–0.07 s，需决定是否值得接入、以及是否只对 shot 级呈现生效）。
3. **patch × global 加权融合（0.55/0.45）**：竞品配方里我方完全没有的机制（patch 资产在位）。
4. **H4 场景级 offset 路径选择**：门限已从常量流拿到（\`offset_refine_*\`）。
5. **等逆向对话补 A1/A2 核心阈值**（dual/visual/structure/motion/flash）后，再谈"多判据场景切分"。

## 6. 三条给下个对话的提醒

- **先看图再下结论**：数字（rank/margin）会把"同场景相邻帧占名次"、"查询点落在错误子镜头"、
  "GT 窗中点落在另一镜头"三种完全不同的事混成一个数。本次三处翻案全部来自看图。
- **别再用"单个中点"代表 GT 窗**；也别再用局部小窗口探针推全片结论（A1/A2/224 都吃过这个亏）。
- **竞品的运行期路线已关闭**（需卡密 + 模型走服务器 lease）；情报只能来自静态常量流（逆向对话在推进）。
