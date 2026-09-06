# 交接 checkpoint — test1-3 GT 全量复核 + 单调弱先验 + 时间轴 Ambiguity（2026-09-02~04）

> 用途：让新对话无缝接续。读本文件 + `.agent/STATE.md` Current Task 顶部 + `.agent/TODO.md` 顶部 + `.agent/DECISIONS.md` + `.agent/CHANGELOG.md` 即可。
> 环境：项目在 D:\claudework\benchmark；python = D:\claudework\video-dedup-tool\.venv\Scripts\python.exe；
> SVL_DATA_DIR = C:\Users\Bsaizne\AppData\Roaming\Video Locator AI\data（重跑分析必须设，否则找不到索引/模型）；
> ffmpeg = tools\ffmpeg.exe、ffprobe = video-dedup-tool venv static_ffmpeg（重跑必须设 MEDIA_FFMPEG/MEDIA_FFPROBE，否则 ffprobe binary not found）。
> ⚠️ 工具调用纪律：本环境所有工具（read/write/pwsh 等）只能经 `run_code` 内部调用。
> ⚠️ pwsh 沙箱写不了 D:\claudework\benchmark\work\（工作区在 D:\deepseek harnees）——重跑脚本输出默认走 TEMP（沙箱重定向到 Local\Temp\dsh-*），结果批需用 node fs 复制回 work/。

---

## 1. 本会话完成了什么（全部闭环）

### ① ⑤' test1-3 全部 GT 人工复核闭环（数据层主线，用户逐段逐帧确认）
- **三份正式 GT**：`datasets/real/ground_truth_test1.json`（43 正/1 负）、`ground_truth_test2.json`（20 正/1 负）、`ground_truth_test3.json`（37 正/3 负）——全部 tier=verified（用户分:秒标注人工复核），吸收 ⑨ B 段。
- 拆条：test1 r07/r08/r10/r12/r13/r14/r30、test2 r1-r7、test3 r2/r3/r4/r6 按用户子镜头标注拆细（v4 口径）。
- **重大修正**（vs 旧结果批/multi_case）：
  - **test3 r14/r15 = 加长版内容（原片正常版没有）→ 负例**（r15 原标 HIGH 且 multi_case 算对，实为负例）→ **test3 HIGH 精度重估 23/23 = 100%**（24→23 段剔除 r15，r10 已修）。
  - **test3 r10 = 7:22-7:24 与 conflict_rerank 自动修复一致**（原"差 1.5s 待修"实际已修好）。
  - **test1 r14a 缺失段**（ed46-49→51:59-52:02）：原算法定位 3121-3123 实为**正确**，GT 漏标（"算法对、GT 错"反转，同 2.mkv p26/p28 模式）。
  - test2 r05 同段内跳跃 -2726s（72分↔26分）= 真实跳切；test3 r13 倒叙（7:46→4:06）。
- **三指标（新 GT）**：test1 严格 32/43 场景 38/43（88%）| test2 严格 9/20 场景 10/20（拆条窄窗低估）| test3 严格 31/37 场景 34/37（92%）、负例误报 2/3（r14/r15 加长版被定位）。
- 资产：`gt_review/GT_BASELINE_test1-3.md` + `FINDINGS_TEST1-3_GT_BUILD.md` + `GT_REVIEW_WORKSHEET_test1-3.md` + `TIMELINE_CROSSCHECK_test1-3.md` + 对照图 76 张（按最新定位重生成）。

### ② ②③ 单调弱先验进候选生成（已编码 + 实测零触发，有据收窄）
- 实现 `_apply_timeline_prior`（Ambiguous 型段用前序段定位中点做锚点：带外 primary + 带内竞争候选 cover 落差≤0.10 才切；逃生门=唯一强候选/首段/前段未定位/带内/全带外不触发）+ 配置（timeline_prior_enabled/ta_band_s=45/ta_max_cover_drop=0.10）+ reason 留痕 timeline_weak_prior。
- 单测 8 项（test_timeline_prior.py）；**全套 222 项全绿**（214 原 + 8 新）。
- **重跑验证**（新代码含先验，复用索引）：2.mkv/test1-3 四片新旧三指标完全一致（32/39、32/43、9/20、31/37 零变化）→ **先验零触发零影响**。
- 原因：①多数 montage 段 primary 带外但带内无 cover 接近竞争候选；②**p08 型兄弟机位 primary 1048 恰在带内（离前段 33s）、真值 1108 带外——先验结构性无效**（呼应 M8 邻接证伪）；③真实跳切段全带外，逃生门不误伤。
- **结论**：候选生成级弱先验零增量；时间轴先验价值已由事后 temporal_repair(+1 p16) + 时间轴→Ambiguity 兑现；实现保留为护栏（默认开零回归），**不调参不投入**。
- 产物：`semantic_signal/FINDINGS_TIMELINE_PRIOR.md` + `work/rerun_2mkv|test1|test2|test3_timelineprior.results.json` + `mvp/scripts/rerun_timeline_prior.py` + `eval_timeline_prior.py`。

### ③ ②⑥ 时间轴→Ambiguity（已编码，2026-09-02 完成）
- `_apply_temporal_ambiguity`：复用 find_temporal_outliers，修复后**仍离群**的高置信段 HIGH→MEDIUM + reason temporal_outlier_ambiguous；不改定位；2.mkv 零触发零回归。
- 配置 temporal_ambiguity_enabled（默认 True）/ta_max_downgrade（默认 MEDIUM）；单测 8 项（test_temporal_ambiguity.py）。

### ④ ④ 时序重排 v4 量化（完成）
- 多版本结果批对比 + 精确回滚 → **temporal_outlier_repair 净纠正 +1（p16 part→HIT）**；p05 pre24→current 回退=「修正后未跟上」非算法退化；P3 悲观结论重估（p26 修正后完全符合时间轴）。
- 产物：`semantic_signal/FINDINGS_TIMELINE_V4_QUANT.md` + `mvp/scripts/research_timeline_v4_quant.py` + `research_timeline_v4_rollback.py`。

### ⑤ ③ test3 r10 单点（已核实闭环）
- current=442-444（temporal_repair+conflict_rerank 两道），用户复核确认 7:22-7:24 = conflict_rerank 修复位置一致。

---

## 2. 已拍板执行顺序（下个对话接续点）

> 完整说明：`gt_review/NEXT_STEPS.md` 顶部「✅ 已拍板执行顺序」段

1. ~~⑤' test1-3 全部 GT 毫秒级重标~~ — **✅ 本轮完成（正式化 datasets/real/ground_truth_test1/2/3.json）**
2. ~~⑥ 时间轴→Ambiguity~~ — **✅ 本轮完成编码（_apply_temporal_ambiguity）**
3. ~~⑧ test3 r10 单点~~ — **✅ 本轮核实闭环（7:22-7:24 与 conflict_rerank 一致）**
4. ~~① 时序重排 v4 量化~~ — **✅ 本轮完成（FINDINGS_TIMELINE_V4_QUANT）**
5. ~~②③ 单调弱先验~~ — **✅ 本轮编码 + 实测零触发（保留护栏，不再投入）**
6. **⑦ Confidence 保守化门槛标定** — 用户 2026-09-02 拍板**暂停**；test1-3 全量 GT 已就绪，随时可恢复（需用户解除「Confidence 公式冻结+不标定占位」护栏）
7. **④ M1-M8 低成本重跑（M4 密度 / M8 邻接）** — 待做（纯 numpy/已用索引，快）；用 v4 + 新 GT 口径刷新
8. **⑩ p08b 复核** — 待做（v4 口径清污染残留；p08b 用 1048-1050 当真值=旧 p38 区，需核对）
9. 之后：**一切用到 GT 的算法/评估均以新 GT 重跑**（用户拍板：算法无论什么都重新跑一次）

---

## 3. 守卫 / 纪律（贯穿）

- GT 新增/修改须**用户逐条画面确认**，不自动填充
- 打包需用户明确允许
- 三指标以新 GT 为准：test1 32/43、test2 9/20、test3 31/37、2.mkv v4 32/39
- 不物理删数据文件（test4/旧 GT 保留证据）；研究代码保留 + 物理隔离
- 后台任务已全部结束无残留（pwsh-3/pwsh-4 已 completed）

## 4. 关键资产速查

| 资产 | 路径 |
|---|---|
| test1 GT 正式 | `datasets/real/ground_truth_test1.json`（43 正/1 负） |
| test2 GT 正式 | `datasets/real/ground_truth_test2.json`（20 正/1 负） |
| test3 GT 正式 | `datasets/real/ground_truth_test3.json`（37 正/3 负，含 r14/r15 加长版负例） |
| 2.mkv GT | `datasets/real/ground_truth_v4.json`（39 正/4 负，基线 32/39） |
| GT 基准/构建 FINDINGS | `gt_review/GT_BASELINE_test1-3.md` + `FINDINGS_TEST1-3_GT_BUILD.md` |
| 复核工作表 | `gt_review/GT_REVIEW_WORKSHEET_test1-3.md`（分:秒格式） |
| 时间轴复核清单 | `gt_review/TIMELINE_CROSSCHECK_test1-3.md` |
| 单调弱先验 FINDINGS | `semantic_signal/FINDINGS_TIMELINE_PRIOR.md` |
| 时序重排 v4 量化 | `semantic_signal/FINDINGS_TIMELINE_V4_QUANT.md` |
| 重跑结果批 | `work/rerun_2mkv|test1|test2|test3_timelineprior.results.json` |
| 重跑/评估脚本 | `mvp/scripts/rerun_timeline_prior.py` + `eval_timeline_prior.py` |
| 时间轴→Ambiguity 测试 | `mvp/tests/test_temporal_ambiguity.py` |
| 单调弱先验测试 | `mvp/tests/test_timeline_prior.py` |
