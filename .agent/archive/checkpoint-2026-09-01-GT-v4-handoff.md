# 交接 checkpoint — GT 重建专会话（2026-09-01 深夜）

> 用途：让新对话无缝接续。读本文件 + `.agent/STATE.md` Current Task 顶部 + `.agent/TODO.md` 顶部 + `.agent/DECISIONS.md` 即可。
> 环境：项目在 D:\claudework\benchmark；python = D:\claudework\video-dedup-tool\.venv\Scripts\python.exe；VLM = Volcengine Ark（D:/deepseek harnees/vision-subagent/vision-mcp-config.json，本会话 36 次调用可用）。
> ⚠️ 工具调用纪律：本环境所有工具（read/write/pwsh 等）只能经 `run_code` 内部调用；文件沙箱已在 danger-full-access（无需再申请权限）。

---

## 1. 本会话完成了什么（全部闭环）

### ① GT v4 重建完成（核心）
- `datasets/real/ground_truth_v4.json`：2.mkv 41 条全定案 → 39 条正例（p37 与 p10 ED 重合删除、p38 与 p08 ED 重复删除）+ 31 条 corrections 留痕（29 relocate + 2 delete）。**v3 原文件保留未覆盖。**
- 41 条判定表：`gt_review/GT_REBUILD_PROPOSAL.md`（含附录 v4 重测）
- 关键实证：**p26 = GT 标错非特征上限**（旧 2809 → 正确 1768.2-1770.05，runtime 1762-1769 HIGH 命中）
- 三指标（v4）：**严格 32/39**（verified 31/36, loose 1/3）｜ 场景级(±15s) 36/39 ｜ 负例 2/4 ｜ 支撑 79/137
- 对照 v3（错误 GT）：严格 39/41 → 下降为**修正后真实口径**，非算法回退

### ② 数据层 A 段补 GT（失败族周边 + Ambiguous 候选段）
- 资产：`gt_review/gt_A/`（10 张候选对照图 + GALLERY.html + GT_A_REVIEW_RECORD.md）
- 用户毫秒级裁决已写入 v4：p08→1108.15-1109.10、p05→979.25-982.00、p20→1553.00-1554.15、p28→**1833.15-1836.00**（用户确认 30:33:15-30:36:00）；p34/p35/p41/p36/t3r12 保持正确

### ③ M1-M8 重审 + M6 重算
- 重审：`semantic_signal/FINDINGS_REVIEW_M1M8.md` —— **p26/p38 从「不可辨识样本/特征上限」移除**；失败族收窄为 p08（兄弟机位）+ test 域（t3r12/t4r01）
- **M6 v4 重算 = 决定性**：`semantic_signal/FINDINGS_M6_REVISED.md` + `work/patch_recall_gt_results_v4.json` —— **RESCUE 1/41 → 0/39**，v3 的 10 条「CLS 池外」全是 GT 标错假象（修正后全 best_rank 1-8 直命中），patch 召回方向彻底关闭

### ④ Ambiguity Detection 原型 = 证伪（重要）
- `semantic_signal/FINDINGS_AMBIGUITY_PROTOTYPE.md` + `work/amb_prototype_signals.json`
- **现有置信信号无法分离「正确 HIGH」与「错配 HIGH」**（HIGH 档精度仅 5/13=38%，mode/n_clusters/qcov/best_sim/margin 全同构）
- 机制：错配 HIGH 多为 clean 单证据簇 → secondary=None → margin 饱和 1.0；low_candidate_margin/multiple_similar_candidates 都要求 n_strong_clusters>=2，clean 段结构上不触发降险 flag
- **→ AMBIGUOUS 无内部信号，校准转向保守化 HIGH 门槛标定**

### ⑤ test4 数据错误确认并逻辑剔除（重大）
- **test4-ed.mp4（81s 竖屏 576×832）与 test4-om.mkv（71min 横屏 1920×804）是两部不同电影**
- `datasets/real/test4-INVALID.md` + 11 个 FINDINGS 统一标注；**不物理删文件**（保留证据）
- 数据层 B 段范围改为 **test2+test3**

### ⑥ 时间轴先验实测（新发现）
- `gt_review/TIMELINE_PRIOR.md` + `work/_timeline_probe.py`
- **实测：编辑顺序 ≈ 原片顺序，单调 20/29**；8 段倒退含真实回溯（解说倒叙）+ 算法错配（可被时间轴纠正）
- **重要：P3 探针当年「p26 偏 1000s → 编辑序列非1:1」结论被错误 GT 污染**，修正后 p26 完全符合时间轴

### ⑦ GT 污染影响清单
- `gt_review/GT_POLLUTION_MAP.md`：被污染 = 评测判定 + 探针输入 + 失败分类；**算法本身/产品 runtime/结果文件零污染**；test1-3 HIGH 段 GT（58 段）独立未被 p 系列污染

---

## 2. 已拍板执行顺序（下个对话从第 1 步开始）

> 完整说明：`gt_review/NEXT_STEPS.md` 顶部「✅ 已拍板执行顺序」段

1. **⑤' test1-3 全部 GT 毫秒级人工重标**（数据层主线，用户逐帧毫秒标定；**吸收 ⑨ B 段**——⑤' 是 test2+test3 LOW/MEDIUM 的超集+升级；test4 剔除）
   - **ed/om 同源已由用户确认，无需校验**
   - 下个对话第一步 = 生成 test1-3 待标清单（按片分：每段编辑时间、当前定位、与前/后段单调性标记）交用户开标
2. **⑥ 时间轴→Ambiguity 外部信号**（低成本，落地校准产品目标：离群段降档/转人工，不改定位改置信）
3. **⑧ test3 r10 单点验证**（已知错配 ≈7:24.5 vs 当前 7:27-7:29，前后段已对 → 时间轴先验端到端最小案例）
4. **① 时序重排 v4 量化**（temporal_outlier_repair + seq_dp 在 v4 下实际纠正几条，顺带重估 P3）
5. 之后：**②③ 单调弱先验进候选生成 → ⑦ Confidence 保守化门槛标定 → ④ M1-M8 低成本重跑（M4/M8）→ ⑩ p08b 复核**

---

## 3. 守卫 / 纪律（贯穿）

- GT 新增/修改须**用户逐条画面确认**，不自动填充
- 打包需用户明确允许
- 三指标重测以 **v4** 为准（严格 32/39 为基线）
- 不物理删数据文件（test4 保留证据）；研究代码保留 + 物理隔离
- 后台任务已全部结束，无残留（M6 重算 job pwsh-5 已完成）

## 4. 关键资产速查

| 资产 | 路径 |
|---|---|
| GT v4 | `datasets/real/ground_truth_v4.json` |
| 41 条判定表 | `gt_review/GT_REBUILD_PROPOSAL.md` |
| A 段裁决 | `gt_review/gt_A/GT_A_REVIEW_RECORD.md` + GALLERY.html |
| M1-M8 重审 | `semantic_signal/FINDINGS_REVIEW_M1M8.md` |
| M6 重算 | `semantic_signal/FINDINGS_M6_REVISED.md` + `work/patch_recall_gt_results_v4.json` |
| Ambiguity 原型 | `semantic_signal/FINDINGS_AMBIGUITY_PROTOTYPE.md` |
| test4 无效 | `datasets/real/test4-INVALID.md` |
| 时间轴先验 | `gt_review/TIMELINE_PRIOR.md` |
| 污染清单 | `gt_review/GT_POLLUTION_MAP.md` |
| 下一步计划 | `gt_review/NEXT_STEPS.md` |
| 重审脚本(可复用) | `mvp/scripts/research_patch_recall_gt.py`(--gt/--out/resume 已参数化)、`mvp/scripts/build_gt_A_candidates.py`(CASES 已更新 v4) |
