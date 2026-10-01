# 两旋钮（shot_split / patch_refine）**生产路径**四片双臂验收（2026-09-30 续33 后续）

> **GT 版本**（2026-10-01 补登记，批量执行）：现行（重锚定后基线：严格 130→132 · 导出实得 107→119，生产路径双臂验收）。

> 目的：离线组合验证（`validate_split_patch_refine.py`，把 runtime 模块**套在既有结果批上**）给出
> 严格 130→132 / 导出实得 107→**119** / FP 4→4，但它没有走完整 `SourceLocatorService.locate()`。
> 默认值翻转（`pipeline.shot_split_enabled` / `pipeline.patch_refine_enabled`）与 r3 打包都需要
> **生产路径**证据，本批补上；同时给耗时代价定性。

## 1. 执行

```bash
# OFF 臂：出厂默认（两旋钮 False）—— 2mkv/test1 本轮真跑，test2/test3 复用现役默认批（见 §2 等价性）
D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/rerun_split_patch_arms.py off
# ON 臂：两旋钮 True（走完整 locate：切分→检索→定位→退化门→重排→shot_split→patch_refine）
D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/rerun_split_patch_arms.py on
# 指标 / 翻转 / 机制分解 / 读图
python mvp/scripts/measure_four_results.py --pattern "work/fastglobal_default_{case}.results.json" --out work/spl_patch_arms/metrics_off.json
python mvp/scripts/measure_four_results.py --pattern "work/spl_patch_arms/on_{case}.results.json" --out work/spl_patch_arms/metrics_on.json
python mvp/scripts/diff_four_batches.py --a "work/fastglobal_default_{case}.results.json" --b "work/spl_patch_arms/on_{case}.results.json"
python mvp/scripts/diag_split_patch_flips.py        # 逐行判据机制（direct/union + within/mid_in/cov）
python mvp/scripts/review_spl_patch_flip.py --case <case> --gt <gt_id>   # 逐行 12 帧读图
```

- 硬件：`DirectMLBackend`（脚本内硬断言，非 CPU fallback）；`fast_global_enabled=True`（现役默认）。
- 产物：`work/spl_patch_arms/{off,on}_{case}.results.json`、`metrics_{off,on}.json`、`flip_caliber.json`；
  读图 `work/spl_patch_visual/*_sheet12.png`。
- 基线健康：改动前 `python -m unittest discover -s mvp/tests` = **455 OK（skipped=2）**；本批**零 `mvp/src` 改动**
  （只新增 3 个 `mvp/scripts/` 验收脚本）。

## 2. OFF 臂等价性（为什么 test2/test3 用现役默认批）

`diff_four_batches.py`（OFF 臂本轮 vs 2026-09-29 现役默认批）：

| 片 | 本轮 OFF | 现役默认批 |
|---|---|---|
| 2mkv | 36/39/3/182 | 36/39/3/182 |
| test1 | 40/42/0/114 | 40/42/0/114 |

严格/场景/FP/支撑**逐位一致、逐 ID 零翻转** ⇒ 现役默认批可作 OFF 臂；故 test2/test3 的 OFF 臂直接取
`work/fastglobal_default_{case}.results.json`（省一轮重复计算，OFF 臂单片 7–8 分钟）。

## 3. 三指标（四片汇总）

| 口径 | OFF（两旋钮关 = 现役） | ON（两旋钮开） | Δ |
|---|---|---|---|
| **严格**（任一 span） | 130/139 | **132/139** | **+2** |
| **导出实得**（仅主 span） | 107/139 | **119/139** | **+12** |
| 场景级 ±15s | 137/139 | 137/139 | 0 |
| 负例 FP | 4/9 | 4/9 | 0 |
| 支撑 span | 646/1138 | 1086/1749 | +440 |

分片：2mkv 36→37（导出 30→34）· test1 40→41（30→37）· test2 18→18（14→15）· test3 36→36（33→33）。

**与离线组合验证逐位一致**：`work/patch_refine_validate/report.json` = sb 130 / ss 132 / eb 107 / es 119 / fb 4 / fs 4。
⇒ **runtime 接线与离线模块行为等价**（生产路径未引入额外漂移或损失），离线结论可直接外推。

## 4. 翻转 14 行 + 判据机制分解（`diag_split_patch_flips.py`）

**导出实得：13 增 / 1 损（净 +12）；严格：+2（p30、t1r02）**。全部 14 行的判据机制 = **direct（主 span 直接满足）**，
**union「编辑侧联合覆盖 + 主 span 并集」装配条款命中 0 行** —— 即 +12 不是并集装配撑出来的
（早前档案"p30 疑似 1799 装配命中"的担心被证伪：ON 臂 p30 命中的是 s60 子段，主 span
`2002.69–2003.31`，落在 GT `2003–2004` 邻域）。

| 判据 | 行 |
|---|---|
| mid_in / cov 命中（span 实质覆盖 GT 窗）| p02、p05、t1r14c、t1r16、t1r19、t1r20、t1r23、t1r30a、t2r01c（**9 行**）|
| 仅 `within`（±2s 容差记账）| p03、p30、t1r02、t3r23（**4 行**，均为亚秒级相邻）|
| 损失 | **t3r02a**（OFF 主 span 331–352 覆盖 GT 332–333.9；ON 窄化到 338.09–339.39 ⇒ 丢覆盖）|

## 5. 逐张读图裁决（6 张，`work/spl_patch_visual/`）

图版式：行1=[ED×3, GT0]、行2=[GT1, GT2, OFF0, OFF1]、行3=[OFF2, ON0, ON1, ON2]。

| 行 | 读图结论 | 定性 |
|---|---|---|
| 2mkv/p05（MISS→HIT）| ED/GT 同为"鹰巢"碉堡内景；OFF span(837.5–839.5) 采样落山谷空镜，ON span(978.9–981.1) 与 GT 同景同机位 | **真增益** |
| 2mkv/p30（严格+1）| 同一室内布景：OFF 1799–1802 是**另一时刻**，ON 2002.69–2003.31 与 GT(2003–2004) 同景同物件（铁罐/吊灯） | **真增益**（同场景时刻修正 ≈203s）|
| test1/t1r02（严格+1）| ED/GT/OFF/ON 全为同一段"落水游向船"镜头；ON span 2181.51–2182.52 与 GT 2183–2184 相差 <1s、画面同源 | **真增益**（亚秒级相邻）|
| test1/t1r20（导出+1）| 暗厅同一场景；ON span 3608.8–3624.2 覆盖 GT 3607.67–3614 | **真增益** |
| test3/t3r23（MISS→HIT）| ED/GT 为"举臂巨人+战场"；ON span 2837.61–2838.39 采样帧为倒地人物/脸部特写，**巨人在 span 结束后 ≈0.4s 才出现** | **打折**（亚秒级相邻，靠 ±2s 记账）|
| test3/t3r02a（唯一损失）| ED 为"烈火吞城"；GT 为火场矮人侧影 + 室内大厅；ON 窄化到 338.09–339.39 = **火场另一时刻（晚 ≈5s）且丢掉室内大厅** | **真损失** |

读图覆盖 6/14 行（2 个严格翻转、2 个 MISS→HIT、唯一损失、1 个宽 span 真覆盖）；
其余 8 行机制与已读行同构（`flip_caliber.json` 逐行有 span 与判据），沿用离线验证的 15 行读图台账。

## 6. 耗时代价（本批新增的硬事实）

| 臂 | 单片墙钟 |
|---|---|
| OFF（现役） | 2mkv ≈ 8.1 分钟 · test1 431.1s（7.2 分钟）|
| ON（两旋钮开）| 2mkv ≈ 42 分钟 · test1 ≈ 31 分钟 · test2 ≈ 40 分钟 · test3 ≈ 44 分钟（合计 ≈ 2h35m）|

⇒ **ON 臂约 4~5× 慢**（patch_refine 的歧义段 top-K ±5s 局部窗 patch+global DML 推理是主开销来源，
本批未做单臂拆分归因）。这直接冲击 `PRODUCT_INTRO` 的"复定位 2~4 分钟"口径（本就已被证伪为随段数线性）。

## 7. 结论与待拍板

1. **生产路径验收 PASS（与离线同规格门槛）**：严格 132 ≥130 且无结构性回退、导出实得 119 >107、FP 4 未增、
   `feature_version` 零变更。**两旋钮的生产行为 = 离线行为**，无隐藏损失。
2. **默认值翻转 ≠ 免费**：收益是导出实得 +12（其中 9 行实质覆盖、4 行亚秒级相邻、1 行真损失），
   代价是定位耗时 4~5×。**因此不建议无条件改全局默认**；三个可拍板形态：
   - (a) 维持默认关，UI/导出面板暴露「高精度复核」开关（用户按需付时间）；
   - (b) 只翻 `shot_split_enabled`（代价待拆臂实测，收益按离线口径 ≈ 导出 +8）；
   - (c) 两个都翻默认开，接受 4~5× 耗时并把 `PRODUCT_INTRO` 时间口径改成"高精度模式 ≈ 30–45 分钟/片"。
3. **前置条件**：无论选哪个，都需要 r3 分发包真机复核（本批只跑了仓库内生产路径，未过打包 exe）。
4. **未做**：单臂（split-only / patch-only）生产路径耗时与指标拆分（离线有：split +8 / patch +2 / 组合 +12）。
