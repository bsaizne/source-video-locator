# CHANGELOG

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
