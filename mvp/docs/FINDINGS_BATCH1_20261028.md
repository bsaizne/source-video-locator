# FINDINGS — 批次1（2026-10-28 凌晨）：三 bug 复核修复 + mAP@δ 边界尺子

> 自包含。任务来源：用户 2026-10-28 凌晨口令（03:00 定时启动、每阶段 git 回滚点）；
> 依据 `mvp/docs/PLAN_BATCH1_20261028.md`（含调研 v2 全文存档）。分支 `develop`，
> 基线 `6271b19` → 本批 `0085d9c`(bug1) / `13d199c`(bug2) / `c92ec9b`(bug3) / `7e5ee73`(尺子)。
> **纪律声明**：调研文档的 bug 定位只是线索；以下三条全部由本批执行者亲读源码 + 数值复现
> 独立证实后才动手，未引用调研结论当证据。

## 0. 一句话

三条复核**全部属实**并已修（各带单测、各自独立 commit 回滚点）；bug3 复核时**顺带挖出并修掉
一个调研没报的潜伏缺陷**（finloc 短窗 mask 长度错位）；mAP@δ 尺子落地并给出四片基线：
**素材起点亚秒精度首次可量化——池化 AP@0.5s=0.447 / @1s=0.647 / @2s=0.753**。
bug1 是唯一有生产行为面的修复（OCR 字牌腿在中文素材上由死信号变活信号），**出包前建议四片 A/B**。

## 1. bug1 — text_anchor 归一化剥光中文（高严重度，属实）

- **位置**：`mvp/src/engine/localization/text_anchor.py:21`（`_NORM_RE = re.compile(r"[^a-z0-9]+")`），
  生效点 = `normalize_text` → `filter_watermark`（`len(n)<3` 当噪声丢行）与 `_ngrams`。
- **复核**：中文字卡整行经 lower + `[^\a-z0-9]` 剥除后为**空串** ⇒ 被 `filter_watermark` 全部丢弃、
  `line_vs_lines` 恒 0。而 `config.py:233` `text_anchor_enabled=True` **默认开**，模块设计目标
  （docstring 实证案例）恰是中文字牌 ⇒ OCR 字牌腿对中文内容**整条哑火**（生产从未真正生效）。
- **修法**：归一化保留字符改为 ASCII 字母数字 + CJK 汉字（含扩展A）：`[^0-9a-z\u3400-\u9fff]+`。
  ASCII 行为逐位不变（既有 12 项测试零改动全过）；水印判定（ASCII 字面量）不受影响。
- **行为面（必须知道）**：这是本批唯一"从死变活"的修复——中文素材上 OCR 锚点腿将首次真正
  参与重排（设计意图即如此，离线证据在模块 docstring）。**未做生产 A/B**（属四片重跑量级，
  超本批"零风险"预算）⇒ 建议：下次出包前跑四片 A/B 验证净效应；若出现 churn 可临时
  `text_anchor_enabled=False` 回到修复前等效态。
- **测试**：`test_text_anchor.py` +3（CJK 保留/混合/中文相似度与水印过滤），16 项全绿；
  后端全套 **761 OK(skipped=2)**（758 基线 + 3）。

## 2. bug2 — isc_refine 宽扫/细化/评分窗高侧越界（中严重度，属实）

- **位置**：`mvp/src/engine/localization/isc_refine.py` 三处高侧无钳制：宽扫粗网格
  `whi = main_mid + R`、两处细化窗 `t0 + WIDE_REFINE_S`（grab 路径与 L2 索引路径）、
  评分窗 `_mid_ts` 的 `hi`；低侧均有 `max(0.0,…)`。
- **复核**：函数签名无 `source_duration_s`（对照 `patch_refine.py:76` 有——2026-10-06 修
  LOC-1107 时加的，同族坑此处漏接）；`ffmpeg_io.grab_frame:204-212` 明确实现"越界且取不到帧
  时惰性返回片内最后一帧" ⇒ 越界采样点**全部用同一张片尾帧重复评分**，尾段附近可造假峰。
- **修法**：签名加 `source_duration_s: float | None = None`，四处高侧按 `hi_bound` 钳制
  （含粗扫窗 `whi<=wlo` 与细化窗 `rhi<=rlo` 的退化守卫）；`None` = 旧行为逐位不变。
  生产接线 `locator_service.py` ISC 调用点传 `bundle.meta.duration`（与 patch_refine 同基准：
  容器时长 ≥ 流末点，不削任何原本成功的点）。
- **测试**：`test_isc_refine.py` +2（钳制后全部源片取帧 ≤ 时长；缺省 None 时高侧不钳），
  16 项全绿。

## 3. bug3 — finloc 3 帧平滑零填充（中严重度，属实 + 1 个调研未报的潜伏缺陷）

- **位置**：`mvp/src/engine/localization/finloc.py:148`
  `cs = np.convolve(cover, np.ones(3)/3.0, mode="same")`。
- **复核（数值验证）**：① 零填充使窗两端 `cs[0]=(0+c0+c1)/3` 而非 `(c0+c1)/2` ⇒ 贴候选窗边的
  真 span mask 掉点、run 内缩 1-2 帧（阈值 0.4 下：两端 cover 各 0.5 时旧码首点 1/3<0.4 掉点）。
  ② **调研未报的潜伏缺陷**：窗口 <3 帧时 `np.convolve(mode="same")` 输出长度=3 ≠ 窗长
  （实测 nr=1→[⅓,⅓,⅓]、nr=2→长度3），`mask` 与候选窗错位 ⇒ `_runs` 索引越过窗边界取
  `orig_times`，span 时刻可能静默取错。
- **修法**：nr≥3 时按**实际参与样本数**归一（`num/den`，内部点逐位不变，仅首/尾两点修正）；
  nr<3 时退化为均值（无平滑意义，且天然等长）。冻结阈值 `FINLOC_THRESH=0.4` 未动。
- **测试**：`test_localization_confidence.py` +2（贴边 span 不内缩 span[0]==0、双帧窗
  mask 等长且 span 覆盖全窗），21 项全绿。

## 4. mAP@δ 边界尺子（新工具，零 runtime 改动）

- **位置**：`mvp/scripts/measure_boundary_map.py`（纯标准库）。口径见脚本 docstring：
  被量化的时刻 = **素材起点**（GT `original[0]` vs 主 span `candidate_start`，导出实得口径）；
  编辑侧关联守卫 ≥0.5 防跨段巧合；排序 = `confidence_score`（生产信号）→ 置信档 → 行号；
  GT 一次认领；δ ∈ {0.1, 0.25, 0.5, 1, 2}s。
- **四片基线**（输入 = 现役 XFeat 默认开态批 `work/ab_xfeat_start_*.results.json`，
  即三指标 148/150 的那批；产物 `work/batch1_20261028/boundary_map_baseline.json`）：

| 片 | n_pos | n_pred | δ=0.1s | δ=0.25s | δ=0.5s | δ=1s | δ=2s |
|---|---|---|---|---|---|---|---|
| 2mkv | 43 | 82 | 0.186 | 0.326 | 0.512 | 0.721 | 0.837 |
| test1 | 44 | 54 | 0.114 | 0.182 | 0.295 | 0.545 | 0.682 |
| test2 | 26 | 64 | 0.115 | 0.269 | 0.385 | 0.577 | 0.654 |
| test3 | 37 | 101 | 0.081 | 0.270 | 0.595 | 0.730 | 0.811 |
| **池化** | 150 | 301 | **0.127** | **0.260** | **0.447** | **0.647** | **0.753** |

（格内 = AP@δ；recall@δ 与 AP 仅在 FP 插序处不同：test1 δ=2s R=0.705、test2 δ=2s R=0.692、
test3 δ=1s/2s R=0.757/0.838，其余逐格相等——4 条假阳的插序效应，内部自洽。）

- **读数**：① 严格命中 148/150 的口径是 ±2s 窗**包含**，对"起点准不准"不敏感；
  尺子首次给出：**起点亚秒（±0.5s）准确率只有 44.7%**、±0.25s 只有 26%——亚秒级
  精修（XFeat 起点精修的下一程、dense_recheck 窗形/步长）现在有了硬标尺。
  ② test1 全档最低（δ=2s 也只有 0.682）：与其长镜头/多单元结构一致，值得专项看。
- **边界**：口径是"起点对起点"，与既有三指标（窗包含/覆盖）不可互换；GT 窗起点本身有
  ±标注粒度（GT 是段落级窗），δ=0.1s 档的读数含 GT 自身标注噪声，引用时须带此说明。

## 5. 门禁与回滚点

- 基线（修复前）：后端 **758 OK(skipped=2)**（222.6s）· API **150 OK**（10.3s）。
- bug1 后全套：**761 OK(skipped=2)**；bug2/bug3 单文件全绿后各自提交。
- 终门禁（bug2+bug3 全部就位后）：后端全套 + API 全套（读数见 §6 / PROGRESS.md）。
- 回滚点（develop，每格独立可回退）：
  `6271b19`(计划) → `0085d9c`(bug1) → `13d199c`(bug2) → `c92ec9b`(bug3) → `7e5ee73`(尺子)。
- 运行产物（gitignore 的 work/）：`work/batch1_20261028/{PROGRESS.md, baseline_*.log,
  after_bug1_backend.log, final_*.log, boundary_map_baseline.json}`。

## 6. 未做与原因

- **bug1 的生产 A/B**（四片重跑验证 OCR 腿激活后的净效应）：本批"零风险"预算不含四片
  locate 重跑（20~43 min/片）；修复语义即设计意图，风险面已有 `text_anchor_enabled` 开关兜底。
  → 建议与下次出包批合并执行。
- **mAP@δ 只做了起点口径**：中点/终点变体未做（起点是产品核心输出，先立主口径）。
- **批次2（Drop-DTW/置信三件套/VQ2D 扩窗/XFeat 加固）**：按计划留待后续批次，未动。
- **未提交 push、未出包、未动 GT、未翻任何默认值**（红线全守）。
