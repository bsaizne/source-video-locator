# FINDINGS — 方案 B「正交预训练 backbone 集成」可行性探针 = **正判，ISC21 通过门槛**（2026-10-02）

> **GT 版本**：2026-10-01 续39 重锚定后 GT（ground_truth_v4 / test1/2/3，版本标记 gt-gap-review-20261001-r1）。
> 结果批 = 现役 r7 对应批 `work/spl_patch_arms/on_*.results.json`（两旋钮 ON，基线严格 133/139）——与方案 A 同一批。
> **定级**：探针（零 runtime、零 GT 修改、不 bump feature_version）。ISC/DINO 两臂 DirectML 硬断言通过；CLIP 臂 CPU 回退（留痕见 §6）。
> 接续：`FINDINGS_PATCH_DENSE_CORR_20261002.md` §7（方案 A 判负 → 方案 B 立项，用户 2026-10-02 拍板）。

## 0. 结论（一句话）

**ISC21（`isc_ft_v107`，copy-detection 专用描述子，与 DINOv2 完全异族）在 MISS6 上给出真实的位置判别信号**：
严格未命中 5/6 gt>main 且 **6/6 gt_is_peak**（含被判"不可救"的 t2r03b——ISC 峰恰落在 GT 窗上），
MISS+POCKET 合计 7/12 ≥ 1/3 门槛，对照组 7/8 peak 且唯一失败例为噪声级边界翻转
⇒ **方案 B 探针正判，进采纳门控设计（待用户拍板）；CLIP 臂弱信号不单独采纳；dino sanity 臂行为符合已知基线。**

## 1. 动机与假设

方案 A 判负 + 双栈解读（FINDINGS_DUAL_STACK）确立根因 = DINOv2 CLS/patch 余弦的**语义不变性**
（同场景不同时刻本就相近）⇒ 剩余候选 = 非 DINOv2 同族的正交预训练 backbone。ViT-B 同族换大已证无增益。
本探针假设：一个**训练目标不同的强 backbone**（copy-detection / 语义对比）与 DINOv2 在
「同场景内哪个时刻正确」这一维度上犯不同的错，其证据可把 GT 位置从错误主定位中挑出来。

## 2. 方法（probe_orthogonal_backbone.py）

- 四臂，全部走与方案 A 相同的扫描协议（source 时间轴 [min(GT,main)−10s, max+10s] 步长 1s，
  每位置抓 1 帧；query = edited 段 3 帧余弦均值；判据 ① margin=GT窗内最高−主定位处 >0.02；
  ② gt_is_peak = 全局峰落在 GT 窗 ±1.5s；门槛 = MISS+POCKET 命中 ≥1/3 且对照零反噬）：
  - **isc**：ISC21 官方 `isc_ft_v107`（EfficientNetV2-M @512 → GeM → 256-d L2；权重本地恢复自
    tier2 trash `work/isc21_weights_ortho_probe/`，离线加载；Phase 12 只在旧 GT v1/解说片场景用过，
    从未对当前 MISS 族做过判别探针）→ ONNX（gem p=1 重写为 ReduceMean 后 DML 可授权）→ **DirectML**；
  - **clip**：OpenAI CLIP ViT-B/32 视觉塔 @224（语义监督家族对照）→ ONNX → **CPU**（见 §6）；
  - **dino**：现役 DINOv2 CLS-384（`PatchReranker.frame_dual`，DML）——sanity 基线，已知无判别力；
  - **ens**：三臂逐位置 z-score 均值（方案 B 的 runtime 集成形态）。
- 案例集与方案 A 完全一致：MISS6 / POCKET8（去重）/ CONTROL8，共 20 案例。
- ⚠️ 口径警示（同方案 A §3）：干净目标集 = MISS6；POCKET8 里 p02/p03/t1r14c 在现役批已接近正确
  （margin≈0 无判别意义）；t2r03b/p30 主定位为占位/出窗（main_in_window=False），margin=None，
  只参与 gt_is_peak 判据。

## 3. 结果（20 案例，产物 work/orthogonal_backbone/）

| 臂 | MISS6 gt>main | MISS6 gt_is_peak | POCKET gt>main | POCKET peak | CONTROL gt>main | CONTROL peak |
|---|---|---|---|---|---|---|
| **isc** | **5/6** | **6/6** | 2/6 | 5/6 | 3/8 | **7/8** |
| clip | 3/6 | 4/6 | 2/6 | 2/6 | 1/8 | 4/8 |
| dino (sanity) | 2/6 | 2/6 | 3/6 | 5/6 | 1/8 | 8/8 |
| ens | 5/6 | 6/6 | 2/6 | 5/6 | 4/8 | 7/8 |

ISC 臂逐案例（gt_sc/主定位分/峰位）：

| 案例 | GT 窗 | 我方主定位 | ISC 峰位 | 峰在 GT±1.5s | margin |
|---|---|---|---|---|---|
| p14 | [1380,1382] | 1394.2（off 13.2s） | 1381.0 | ✓ | +0.0735 |
| p20 | [1553,1554.15] | 1560.6（off 7.0s） | 1553.0 | ✓ | +0.1098 |
| p34 | [2058,2060] | 1977.1（off 81.9s） | 2060.1 | ✓ | **+0.3256** |
| t1r08c | [2952.91,2952.95]（一帧锚点） | 2951.5（off 1.4s） | 2952.5 | ✓ | +0.0457 |
| t1r12a | [3005.5,3007.5] | 3004.0（off 2.5s） | 3006.0 | ✓ | +0.0391 |
| t2r03b | [3570.43,3571] | 0s 占位（出窗） | **3571.4** | ✓ | —（出窗） |
| t2r06c (pocket) | [1626.83,1628] | 1632.8（off 5.4s） | 1627.8 | ✓ | +0.3737 |
| t3r02c (pocket) | [374.12,374.54] | 356.2（off 18.1s） | 374.2 | ✓ | +0.4379 |

对照唯一失败例 t1r27：margin −0.0217（噪声级），ISC 峰落在我方主定位（GT 窗 end+1.2s），
GT 窗内有近等高局部峰 ⇒ **边界翻转族，非灾难性反噬**（若做 runtime 峰位定位会偏 1.2s，须进门控设计考量）。

## 4. 逐张读图确证（铁律；curves/*.png 全 20 张中读 9 张关键 + sheets 3 张内容核对）

- **t2r03b（miss）**：ens/ISC 曲线在 GT 窗处一根**孤立尖峰**，高出全邻域，无台地歧义——
  被续42 判"证据太弱不可救"（DINOv2 cover 0.062/bsim 0.413）的案例，ISC 峰恰立在 GT±0.4s。
  拼图核对：ED 查询帧与 GT 帧同为夜景阳台女子，主定位侧（0s 占位）内容不符 ⇒ 内容为真。
- **p34（miss，off 81.9s）**：GT 处 ens 尖峰为全景最高；拼图核对：ED 与 GT 同一林地场景正确时刻，
  我方主定位帧 = **同一场景另一时刻**（同设不同刻）⇒ ISC 补的正是 DINOv2 缺的「同场景内时刻判别力」。
- **p20（miss）**：GT 窗处于 ISC 高区、主定位在次级峰上（margin 0.11 真实）；拼图：GT 同夜景内容，
  主定位帧已是「BEEF SUPREME」字幕卡 ⇒ 内容为真。
- **p14（miss）**：GT 处孤立尖峰，主定位侧另有宽台地但低于 GT 峰。
- **t1r08c / t1r12a（miss，off 1.4/2.5s）**：宽包络山丘，GT 处为最高点（margin 0.04-0.05，
  曲线邻域抖动 ~0.01 ⇒ 高于噪声）；属边界族，收益是把 1.4-2.5s 的偏移收进 ±1.5s。
- **t2r06c / t3r02c（pocket）/ p04（control）**：孤立尖峰或恰好罩住 GT 窗的台地，形态干净。
- **t1r27（control 唯一失败）**：GT 窗内近等高、峰在窗外 1.2s（见 §3）。
- **CLIP（紫线）全案例近水平**：语义对比特征对「同场景哪一时刻」几乎无判别力（语义不变性更甚），
  弱信号不单独采纳。

## 5. 独立证据交叉（铁律第二证据）

1. **dino sanity 臂同 harness 对照**：同一扫描/判据/出图管线上，已知无判别力的 DINOv2 CLS 测得
   2/6 MISS peak、CLIP 近水平——**harness 无 GT 泄漏旁证**（若管道有泄漏，dino 臂不会呈现已知基线行为）。
2. **sheets 内容核对**（3 张，见 §4）：GT 帧与 ED 查询帧逐张目检同内容，主定位帧内容不同
   ⇒ ISC 峰指向的是内容正确的位置，不是指标巧合。
3. **Phase 12 旁证**：ISC+TransVCL 官方链路在旧 GT v1 时代是唯一产出过视觉确认真定位的特征链
   （benchmark_report_phase12 §6.3，recall 0.143 vs DINOv2+TA=0）——方向一致，非孤证。

## 6. 工程留痕（两项新发现，影响未来多模型 runtime）

1. **CLIP 图的 DML 授权失败会污染进程**：CLIP ViT-B/32 visual ONNX（opset 14/17 均试）在
   DmlExecutionProvider 授权阶段 E_INVALIDARG(80070057) 失败；**失败路径会使同进程后续任何
   DML session Run 段错误（EXIT=139）**——已用"同序列去 CLIP 臂"对照复现归因。正解 =
   该臂直接 CPU-only 构建、不做 DML 尝试。⇒ 未来 runtime 若挂多模型，**DML 授权失败必须
   fail-fast 隔离（子进程或预检），不能让失败路径留在主进程**。
2. **主定位占位炸扫描窗**：t2r03b 主定位=0s（unresolved 占位）使 `[min(GT,main)−10, max+10]`
   变成全片 3580 位置（CPU 时间 3834s 仍"忙而不死"）。已修：扫描窗 >150s 时钳到 GT 邻域 ±15s
   并记 `main_in_window=False`。方案 A 探针同窗口逻辑（当年跑过全片扫描，只是未被识破）。
3. CLIP 权重经 openaipublic 下载成功（HF 不可达）；`clip` 包经 github pip 安装。
4. GPU-first 留痕：ISC 臂 DML 生效；CLIP 臂 CPU 回退（模型仅 87MB@224，代价可忽略；
   DML 尝试会段错误故不做，见本节①）。

## 7. 裁决与下一步

- **方案 B 探针正判**：ISC21 信号存在且门槛通过（MISS 5/6 >> 1/3；对照 7/8 peak 零灾难反噬）。
- **不直接进 runtime**（探针=位置扫描 oracle 形态；采纳需先做门控设计，与 patch_v2 同路径）：
  下一步候选（**待用户拍板**）：
  1. **采纳门控设计**：ISC 作为「第二意见」只对**歧义段**（patch_refine 歧义门命中的 top-K 候选）
     做 ±5s 局部窗 ISC 重扫重排（非全片扫描，成本 ≈ 候选数 × ~20 帧 × EffNetV2-M@512 DML），
     融合判据与三指标回归（严格/导出实得/负例零回退 + MISS6 目标命中）。
  2. 或先小批扩展验证（全 139 正例位置扫描复算 ISC 峰位命中分布，确认 5/6 不是小样本运气），
     再做门控设计。
- t2r03b 的续42"不可救"结论需要**限定改写**：DINOv2 证据链上不可救成立，但 **ISC 证据链能救**
  （峰在 GT±0.4s）——该案例应作为采纳门控设计的必验收样本。
- CLIP 臂：弱信号，不单独采纳，留档作对照。

## 8. 产物

- 脚本 `mvp/scripts/probe_orthogonal_backbone.py`；stdout `work/probe_orthogonal_backbone_stdout.log`
- `work/orthogonal_backbone/{index.json, curves/*.png(20), sheets/*.png(20)}`
- 权重/ONNX `work/isc21_weights_ortho_probe/`（isc_ft_v107.pth.tar 自 tier2 trash 恢复 + 两份导出 ONNX）
- 新依赖：`clip`（github pip）+ CLIP ViT-B/32 权重（~/.cache/clip）

## 9. 扩验证（2026-10-02 续43 拍板选项②）：全 139 正例峰位分布 = 信号真实、非小样本运气，但强度分层

脚本 `mvp/scripts/probe_ortho_full139.py`（同协议同判据，只跑 ISC+dino 两臂，CLIP/ens 砍掉；
GT 锚窗口径不变），产物 `work/orthogonal_backbone_full139/`，耗时 35.0min。

### 9.1 分布（gt_is_peak = 全局峰落 GT±1.5s；桶按 |main−GT中点|）

| 桶 | n | ISC | dino | 配对（双中/仅ISC/仅dino/双缺） |
|---|---|---|---|---|
| aligned（off≤2s，main≈GT） | 76 | **71/76** | 71/76 | 68/3/3/2（基线同义反复，两臂一致） |
| drift（2<off≤15s） | 41 | **30/41 (73%)** | 26/41 | 23/**7**/3/8 |
| far（off>15s） | 14 | 6/14 (43%) | 5/14 | 3/3/2/**6** |
| nowin（主定位占位/出窗） | 8 | **8/8** | 6/8 | 6/2/0/0 |
| **核心判别桶（drift+far+nowin）** | **63** | **44/63 (70%)** | 37/63 (59%) | 双中29/**15**/8/11 |
| 全体 | 139 | 115/139 (83%) | 108/139 | 100/15/8/16 |

margin>0.02（gt>main，仅主定位在窗内）：drift 桶 ISC 22/41 vs dino 16/41（ISC 优）；
aligned 27/76 vs 32/76（噪声区两臂相当）。

### 9.2 读数

1. **非运气**：MISS6 的 6/6 在 139 例分布下收敛为「核心桶 70%」——信号真实但强度分层：
   drift（2–15s 偏移）73% > far（>15s）43%；nowin（占位/出窗）8/8（t2r03b/p30/t1r08a/t3r02a 型全中）。
2. **ISC 独家增量 12 例**（仅 ISC 峰中、dino 未中）：p14/p20/p28/p34/p09、t1r08a/t1r12a/t1r18、
   t2r06c/t2r07b/t2r07c、t3r02a——10/12 在 drift+far 桶，margin 至 0.37，与 MISS6 高度重叠。
3. **失败两族（19 例未中）**：
   - **近位移边界翻转 9 例**（disp=峰到 GT 窗距离 ≤5s，gap ≤0.10 噪声级：p12/p24/t1r14b/t1r27/
     t3r04a/t3r16/t3r27/t2r03a/t2r01b）——软融合/容差可能救，单案收益低；
   - **远位移一致错 10 例**（disp 9–106s：t1r02/t1r08b/t1r10a/t1r14d/t1r30a/t2r04a/t2r05b/
     t3r02b/t3r04b/p33）——点名读图 t1r30a/t2r04a 确证：**ISC 与 dino 同峰同错**（峰都在我方
     主定位处、GT 处同为低谷，t1r30a ISC 0.887 vs GT 0.286）⇒ 不是 ISC 边界抖动，是两族特征
     共同的上限（部分案例本有 GT 疑点成分，如 t1r08b 历史争议标注）。
4. **ISC 真独家判别确证**（点名 t1r18）：ISC 峰在 GT 窗内 3601s，dino 峰在窗外 3609s 且 GT 区
   dino 值更低——同批同帧上两臂分歧真实存在。

### 9.3 对采纳门控设计的约束（下一步拍板材料）

- **ISC 只能做「第二意见 tiebreaker」，不能当主判据**：t1r30a/t2r04a 型两臂一致错 +
  aligned 桶两臂同基线 ⇒ 全局重排必然 churn（与形态5 的教训同构）。
- 采纳形态必须收敛在**歧义段**（patch_refine 歧义门触发的 top-K 候选），判据建议含：
  ISC margin 绝对门（≥0.03~0.05）+ 候选窗约束（峰必须落在候选邻域内）+ dino/ISC 分歧才介入
  （配对 15:8 说明分歧集足够小）。
- **收益期望要设对**：严格未命中现有 6 条全部 peak✓（这是直接目标）；额外可救池 = drift 桶
  ISC 独家增量（~7 例）± far 少数；风险 = aligned 71/76 的 5 例峰不中 + 边界翻转族引入 churn
  ⇒ 三指标回归（严格/导出实得/负例零回退）仍是硬门。
- 口径边界不变：GT 锚窗 oracle 扫描，测的是**信号存在性分布**；runtime 能力由门控设计 +
  三指标回归另行证明。

### 9.4 扩验证产物

- 脚本 `mvp/scripts/probe_ortho_full139.py`；stdout `work/probe_ortho_full139_stdout.log`
- `work/orthogonal_backbone_full139/{index.json, spot/*.png(3 张点名曲线)}`

### 9.5 立项前多模态复核（2026-10-02 用户问「多模态复核没」后补齐）：独家增量 12 例全读毕 = 11 干净 + 1 边界

扩验证阶段只点名读了 3 张（t1r30a/t2r04a/t1r18）；立项拍板（选项①）后补齐独家增量 12 例
逐张读图（6 例补出曲线+内容拼图，`spot/*2mkv_p28|p09|test1_t1r08a|test2_t2r07b|t2r07c|test3_t3r02a*`，
其中 p14/p20/p34/t1r12a/t2r06c 探针阶段已读）：

- **干净确证 11/12**：p14/p20/p28/p34/p09（ISC 峰在 GT 窗内或窗缘、DINO 峰在我方错误主定位；
  帧拼图 ED/GT/ISC峰 三帧同内容——p28 举牌「We ARE NOT ALLOWED to CONTACT」、p09 Levi 特写、
  t1r08a 强喂镜头）/ t1r08a（nowin 无候选，ISC 峰在 GT 窗缘 0.6s）/ t1r12a / t1r18（ISC 峰 GT
  窗内 3601、dino 峰窗外 3609）/ t2r06c / t2r07c（ISC 峰恰在 GT 4697，dino 峰在错误侧 4700）/
  t3r02a（nowin，ISC 峰 GT 窗内 333，三帧同瞭望塔火景）。
- **边界 1/12 = t2r07b**：ISC 峰 2544 内容真实（与 ED 查询中帧同镜头）但**落在 GT 窗前 2.2s，
  GT 窗内是另一子镜头**（ED 段含切点、GT 锚后一子镜头）——计数上仍 gt_is_peak=1（±1.5s 容差
  边界），视觉上是**多镜段子单元族**，与续42 B 类「span 抖判据线」同族 ⇒ 该例不算干净命中。
- **结论修订**：ISC 独家增量按「干净 11 例」记账（drift/far 主场不变）；门控设计新增一条约束：
  **ED 段含切点/多子镜头时，ISC 峰允许锚到相邻子镜头（±2~3s），采纳判据须容忍子镜头粒度或
  结合 ED 子镜头切分对齐**（否则 t2r07b 型案例会以「峰在窗外」被误拒/误接受）。
  VLM 方舟仍不可用（历史欠费 403），本轮多模态复核 = 逐张读图（曲线 12 + 帧拼图 6，全读完）。

## 10. 采纳门控生产验收（续44，2026-10-02/03）

`mvp/scripts/rerun_isc_refine.py on` 走完整 `srv.locate()` 生产路径四片实跑 ON 臂（唯一变量
`pipeline.isc_refine_enabled`，margin/候选窗等门控参数=runtime 现值），ALL_DONE + PY_EXIT=0。
**OFF 臂 = 现役默认批 `work/spl_patch_arms/on_{case}.results.json` 直接复用**（等价性声明：
该批即 shot_split+patch_refine+fast_global 全开、isc_refine_enabled=False 的现役默认定位输出；
OFF 臂路径与它配置逐项相同、isc 关闭时定位路径确定性等价；数值旁证 = 同 GT r1 重计
133/125/138/4 与 STATE 续39 权威基线逐位一致）。**口径勘误**：任务书「导出实得 119」是续39
GT 修订前旧数，现行 GT（gt-gap-review-20261001-r1）下权威基线 = 主片段 125/139（CHANGELOG
2026-10-01 续39 条），本验收按 133/125/138/4 执行硬门。

### 10.1 双臂三指标（硬门 = 零回退）

| 指标 | OFF（现役默认） | ON（isc_refine） | 判定 |
|---|---|---|---|
| 严格 | 133/139 | **134/139**（+1） | ✓ 无回退 |
| 导出实得（主 span） | 125/139 | **128/139**（+3） | ✓ 无回退 |
| 场景级 ±15s | 138/139 | 138/139 | ✓ 持平 |
| 负例误报 | 4/9 | 4/9 | ✓ 持平 |
| 支撑 span | 1078/1749 | 1094/1770 | — |

分片严格：2mkv 36→37 · test1 41→41 · test2 19→19 · test3 37→37。ON 臂耗时：2mkv 1879s /
test1 1595s / test2 2009s / test3 1958s（总 ≈124min；OFF 臂未复跑无同轮耗时对照）。

### 10.2 翻转清单（逐 ID，共 3 条增益、0 条回退；mark 与 main_hit 双口径全查）

| ID | 翻转 | OFF 落点 | ON 落点 | GT 窗 | 读图定性 |
|---|---|---|---|---|---|
| 2mkv/p14 | part→HIT · main F→T | [1392.3,1396.3] 地堡庭院（错场景） | [1379.5,1380.6] | [1380,1382] | **真增益**：ED=森林天线场景，OFF 落点错场景；ON 落 GT 窗内、与 ED 主体同内容（sheet `isc44_2mkv_p14_sheet12.png`） |
| test2/t2r07c | HIT→HIT · main F→T | [4697.5,4702.5] 窗缘后漂入切镜（5s span 超窗） | [4695.2,4696.8] | [4697.2,4697.7] | **真增益**（±2s 容差记账/子镜头粒度）：同主持镜头命中，span 端点距 GT 窗 0.35s（sheet `isc44_test2_t2r07c_sheet12.png`） |
| test3/t3r02c | HIT→HIT · main F→T | [355.6,356.9] 17s 外拱廊庭院（错场景） | [372.4,373.6] | [374.1,374.5] | **真增益**（容差记账）：同燃烧城垒镜头命中，端点距 GT 窗 0.48s（sheet `isc44_test3_t3r02c_sheet12.png`） |

无指标翻转的 span churn 9/139，其中 6 条 mark/main_hit 双臂全一致且逐条核验均仍在判据内
（t1r02 cov 0→1.0、t3r19 cov 0.52→0.75 反而更紧；t1r26/t2r04b/t2r06b 覆盖率略降仍在 ±2s 内；
t3r02a 双臂均 main F，5928→460 大跳但无指标影响）⇒ **无隐藏损失**。

### 10.3 MISS6 / t2r03b 逐条（必验收）

- **p14 = 获救**（part→HIT，上表）。
- **p20 / p34 / t1r08c / t1r12a = 仍 part**（双臂逐位同 mark/main_hit，无变化）。
- **t2r03b = 仍 MISS**：双臂均 0s 占位（main=[0,0]，conf=LOW）+ 邻域候选行 [3591.25,3593.25]
  双臂逐位相同——**符合预期**（v1 门控不救无候选段；该例 ISC 证据链可救但需先有候选，留待
  门控 v2 若扩「无候选段兜底重扫」再验收）。

### 10.4 裁决（机械执行预定门）

**PASS**：三指标零回退（严格 +1 / 导出实得 +3 / 场景持平 / 负例持平）且 3 条翻转全部真增益、
无真损失。**结论 = 可进用户拍板翻默认；`isc_refine_enabled` 保持 False，本轮未翻默认、未改
GT、未 bump feature_version、未 git 提交。**

### 10.5 margin/门控旋钮观察（不改默认值，供拍板参考）

- 翻转仅 3/139（2.2%），aligned 噪声区零翻转 ⇒ margin 门**不算太松**；drift 主场 p14 获救
  ⇒ **不算太紧**。churn 9/139 全部无指标影响。
- 3 条增益落点全部紧贴 GT 窗（窗内 / 窗前 0.35s / 窗前 0.48s）：ISC 重排能把落点锚到正确
  子镜头，但 span 端点常停在窗缘前 ~0.5s（span 收缩偏保守）——若未来想多救 part→HIT，
  观察点是 span 端点贴窗现象而非 margin 本身。
- t3r02a 型（双臂均 main F）大位移无指标影响，但提示占位/nowin 段的候选选择在 ON 臂仍有位移，
  留观察。

### 10.6 产物与覆盖边界

- 产物：`work/isc_refine_arms/on_{2mkv,test1,test2,test3}.results.json`（ON 臂实跑）；
  stdout `work/rerun_isc_refine_stdout.log`；分析 `work/isc_refine_arms/analysis/`
  （`metrics_off_arm_reused_splpatchon_20261002.json` / `metrics_on_arm_20261002.json` /
  `isc44_flip_list_20261003.txt` / `isc44_fine_diff_20261003.txt` / `make_isc44_flip_sheets.py` /
  拼图 3 张 `isc44_*_sheet12.png`）。出图脚本复用 `review_spl_patch_flip` 口径
  （best_row=evaluate 对齐）+ `visual_fastglobal_flip.grab/tile`。
- **没验的**：① OFF 臂未同轮复跑（等价性靠配置断言+续39 重计逐位一致旁证，非本轮实证）；
  ② ON 臂耗时代价无同轮 OFF 对照（增量耗时未单测）；③ 合成集/负例扩充集未跑（验收范围=四片
  real 现役管线）；④ t2r03b 类无候选段不在 v1 门控能力内；⑤ margin 敏感性扫描未做（护栏禁 sweep）。

## 11. 门控 v2 宽幅扫描验收（续45，2026-10-03）

`mvp/scripts/rerun_isc_refine.py v2` 四片实跑（完整 `srv.locate()` 生产路径，唯一变量
`pipeline.isc_refine_scan_radius_s` 0→90；`isc_refine_enabled=True` 双臂同开；ALL_DONE/PY_EXIT=0）。
对照臂 = `work/isc_refine_arms/on_{case}.results.json`（续44 验收后现役行为：isc 开、radius 0，
三指标 134/128/138/4）。产物 `work/isc_refine_arms/v2_{case}.results.json`；分析
`work/isc_refine_arms/analysis_v2/`（对照脚本 `compare_iscv2_flips.py` + metrics/flip/fine/churn +
拼图 8 张，既有 `analysis/` 产物零覆盖）。

### 11.1 双臂三指标（硬门 = 零回退）

| 指标 | ON（radius 0，现役） | V2（radius 90） | 判定 |
|---|---|---|---|
| 严格 | 134/139 | **136/139**（+2） | ✓ 无回退 |
| 导出实得（主 span） | 128/139 | **131/139**（+3） | ✓ 无回退 |
| 场景级 ±15s | 138/139 | 138/139 | ✓ 持平 |
| 负例误报 | 4/9 | 4/9（分片 3/0/0/1 逐片持平） | ✓ 持平 |
| 支撑 span | 1094/1770（61.8%） | 1103/1780（62.0%） | — |

分片严格：2mkv 37→**39**（p20/p34 获救）· test1 41→41 · test2 19→19 · test3 37→37。
耗时：2mkv 2923.8s / test1 2888.4s / test2 3302.3s / test3 3631.1s（总 212.4min，vs 续44 ON 臂
31.3/26.6/33.5/32.6 min = 124min；宽扫开销 ≈ +88min，机制预算 ~150 embeds/段 × 279 段相符）。

### 11.2 翻转清单（3 行全 IMPROVE、0 回退；mark 与 main_hit 双口径）

| ID | 翻转 | ON 落点 | V2 落点 | GT 窗 | 读图定性 |
|---|---|---|---|---|---|
| 2mkv/p20 | part→HIT · main F→T | [1559.6,1561.6] 同景 7.5s 后（直身行走） | [1552.2,1554.0] 窗内 | [1553,1554.15] | **真增益**：ED=岩壁菜园劳作，V2 落点同款劳作动作（sheet `isc45_2mkv_p20_sheet12.png`）——**续43 探针 margin +0.11 目标兑现** |
| 2mkv/p34 | part→HIT · main F→T | [1976.1,1978.1] 错场景（男子举牌 "I'M A PRETTY GOOD SHOT"） | [2057.6,2059.6] 窗内 | [2058,2060] | **真增益**：ED/GT=黑发女子夜景室内，ON 完全错镜头，V2 同女子同景（sheet `isc45_2mkv_p34_sheet12.png`）——**续43 探针 margin +0.33 目标兑现** |
| test2/t2r06c | HIT→HIT · main F→T | [1630.3,1635.3] 5.1s span 起点在窗后 2.4s 且漂过切点（金发少年/橙衣人群） | [1626.7,1627.9] 窗内 | [1626.83,1628] | **真增益**：V2 落点=紫衣少年蓝色起爆器与 ED 同内容（sheet `isc45_test2_t2r06c_sheet12.png`） |

### 11.3 churn（宽扫 touching 面，远低于 >20 预警线）

- 判据命中行口径（与 evaluate 一致）主 span 中点移动 >1s 共 **5 行**：3 行即上表翻转 +
  **2 行无指标影响**：t2r04b（3718.6→3716.3，同隧道镜头内前移 2.2s，双臂均在 GT 窗内同景）·
  t3r22（2829.5→2830.3，同战斗蒙太奇内移 1.4s，双臂均在窗内）。拼图读毕均**无隐藏损失**
  （`isc45_test2_t2r04b_sheet12.png` / `isc45_test3_t3r22_sheet12.png`）。
- 非 judge 行（best-ov 口径）另有 t2r05a/t3r03a 大位移，但其判据命中行双臂逐位同（拼图读毕
  `isc45_test2_t2r05a` / `isc45_test3_t3r03a`，无指标无画面影响）。
- ISC 切换段总数 31（v1 臂 21），其中 `-iscw`（宽扫虚拟候选胜出）14 段；31 段切换只兑现
  3 行指标翻转 + 2 行同景内微移 ⇒ margin 门 + 先粗后细 + 距主 ≥2s 三重约束把 churn 压住了。

### 11.4 MISS6 / t2r03b / 自信错点名（必验收）

- **p20 / p34 = 获救**（part→HIT，上表）——**v2 立项动机（破 CLS 聚簇提案视野）直接兑现**，
  MISS6 收口至 6→4 缺口（p14 续44 已救）。
- **p14 = 保持 HIT**（落点 [1379.45,1380.55] 双臂逐位同，无扰动）。
- **t1r08c / t1r12a = 仍 part**（落点双臂逐位同 2950.5/3003.0——宽扫峰未过 margin 门或峰不在
  GT 邻域，如实记录不救）。
- **t2r03b = 仍 MISS**：0s 占位段（width≤0.01）按模块边界跳过——宽扫也无候选可评（设计内；
  「无候选段兜底重扫」仍是独立未立项形态）。
- **far 桶自信错点名 t1r30a / t2r04a = 双臂一致 HIT、落点逐位同**，无 ISC 自信错恶化
  （`isc45_test2_t2r04a_sheet12.png` 读毕同景）。

### 11.5 裁决（机械执行预定门）

**PASS**：三指标零回退（严格 +2 / 导出实得 +3 / 场景持平 / 负例分片逐片持平）且 3 条翻转全部
真增益、churn 2 行核验无真损失、无自信错恶化、churn 3 行远低于 >20 预警线。
**结论 = 可进用户拍板翻 `isc_refine_scan_radius_s=90`（本轮不翻，radius 保持 0.0；未改 GT、
未 bump feature_version、未 git 提交）。**

### 11.6 产物与覆盖边界

- 产物：`work/isc_refine_arms/v2_{2mkv,test1,test2,test3}.results.json`；stdout
  `work/rerun_iscv2_stdout.log`；分析 `work/isc_refine_arms/analysis_v2/`
  （`compare_iscv2_flips.py`、`isc45_metrics_20261003.json`、`isc45_flip_list_20261003.txt`、
  `isc45_fine_diff_20261003.txt`、`isc45_churn_20261003.txt`、`isc45_sheet_list_20261003.txt`、
  拼图 8 张 `isc45_*_sheet12.png` 全读毕）。
- **没验的**：① radius 单值 90（其它半径未扫——护栏禁 sweep，90 为任务书预定值）；
  ② 合成集/负例扩充集未跑（验收范围=四片 real 现役管线）；③ t2r03b 类无候选段不在 v2 能力内；
  ④ 宽扫开销 +88min/四片（全片高精度 locate 时长近乎翻倍，产品化需评估代价/或仅对窄段启用）；
  ⑤ t1r08c/t1r12a 的宽扫峰为何未过门未逐段归因（不留 runtime 通道，仅记录）。

## 12. v3 阶梯宽扫验收（续48，2026-10-03）= 判负（计时）

`mvp/scripts/rerun_isc_refine.py ladder` 四片实跑（完整 `srv.locate()` 生产路径，唯一变量
`pipeline.isc_refine_ladder_s` 0→30；isc 开 + radius 90 双臂同置；对照臂 = `v2_{case}`（续45
验收后的现役行为：radius 90、ladder 0））。动机 = v2 宽扫 +88min/四片的成本大头（DML 逐帧
embed）× 设计假设「多数歧义段在内圈（±30s）就有过 margin 门（0.05）的峰」→ 内圈收工省外圈。
2mkv/test1/test2 三片自然完成；**test3 被主动中止**（REFINE ~42/103；前三片计时已一致地更慢，
继续跑不改变裁决），stdout `work/rerun_iscladder_stdout.log` 末尾 PY_EXIT=127（中止留痕，
非脚本崩溃）。产物 `work/isc_refine_arms/ladder_{2mkv,test1,test2}.results.json` + 中止无
test3；分析 `work/isc_refine_arms/analysis_ladder/`（对照脚本 `compare_iscladder_flips.py`
+ metrics/flip/fine/churn/inner_hit + 拼图 7 张全读毕，analysis/ 与 analysis_v2/ 零覆盖）。

### 12.1 计时（本批核心交付；3/3 片全部更慢，判负依据）

| 片 | v2 臂（ladder 0） | ladder 臂（ladder 30） | 差 | 判定 |
|---|---|---|---|---|
| 2mkv | 2923.8s | 3167.7s | **+243.9s（+8.3%）** | 更慢 |
| test1 | 2888.4s | 2928.0s | **+39.6s（+1.4%）** | 更慢 |
| test2 | 3302.3s | 3738.0s | **+435.7s（+13.2%）** | 更慢 |
| 3 片合计 | 9114.5s（151.9min） | 9833.7s（164.0min） | **+719.2s（+7.9%）** | 纯负优化 |
| test3 | 3631.1s | 未完成（中止于 REFINE ~42/103） | — | 不参与计时判定 |

节省% = **-7.9%（负）**——阶梯没有省任何时间，反而稳定更慢。

### 12.2 三指标（3 片硬门核对 = 零回退，但无意义——计时已判负）

| 指标（3 片口径） | V2（现役） | LADDER | 判定 |
|---|---|---|---|
| 严格 | 99/102 | 99/102 | ✓ 持平 |
| 导出实得（主 span） | 95/102 | 95/102 | ✓ 持平 |
| 场景级 ±15s | 101/102 | 101/102 | ✓ 持平 |
| 负例误报 | 3/6 | 3/6 | ✓ 持平 |
| 支撑 span | 621/1120 | 627/1128 | — |

分片逐片持平：2mkv 39/39 · test1 41/43 · test2 19/20（严格），main/scene/fp 逐片同。
test3 = ladder 未验（中止），如实标注。**mark/main_hit 双口径翻转 0 行**——阶梯的
「多峰选位差」未兑现成任何指标变化。

### 12.3 逐 ID 核对（生死线 + churn 读图）

- **p20 / p34 = 保持 HIT 且落点与 v2 臂逐位同**（p20 [1552.23,1554.02] / p34 [2057.62,2059.62]，
  sheet `isc48_2mkv_p20/p34_sheet12.png` 读毕同景同内容）——设计论证的「radius90 能救的
  阶梯全救」成立；**p14 = 保持 HIT**（[1379.45,1380.55] 逐位同）。
- **t1r08c / t1r12a 仍 part、t2r03b 仍 MISS、自信错点名 t1r30a / t2r04a 保持 HIT 落点同**
  （与 v2 臂逐位一致，无恶化）。
- **churn 4 行**（mark/main 未变但主 span 中点移 >1s；无指标翻转）：2mkv/p12（1.9s，直升机
  舱内同景）· 2mkv/p13（1.6s，航拍河谷同景）· test1/t1r20（8.0s，同暗洞鬼战蒙太奇内，
  ladder 臂 span 反而更短更贴 GT 窗）· test1/t1r26（1.5s，同洞穴取斧镜头）。拼图 4 张读毕
  **全部=纯同景内选位差，无真损失**（sheet `isc48_*_sheet12.png`）。
- 切换段总数（3 片）：v2 19（-isc 12 / -iscw 7）vs ladder 21（-isc 13 / -iscw 8）——多峰选位
  效应只多 2 段切换、零指标影响。

### 12.4 内圈命中率（近似上界，如实说明口径）

从产物**无法直接区分**「内圈收工」与「外圈扫完后仍选内圈峰」（日志无逐段阶梯留痕）。
近似上界 = ladder 臂 `-iscw` 切换段中胜出峰落在现主 ±30s 内的比例：2mkv 1/2 · test1 2/2 ·
test2 2/2，合计 **5/6**。但结构账更硬：宽扫对所有非 gate-clear 段生效，3 片切换段仅
21/206（≈10%）——**过门峰 ≈ 最终切换段**，即只有 ~10% 段有可能内圈收工，其余 ~90% 段
必然「内圈无过门峰 → 全量扩展」，纯付内圈粗扫（31 pts）+ 内圈 top-3 细化（~15 embeds）
的附加成本。

### 12.5 机制复盘（设计错误，非实现错误）

阶梯省时前提 =「多数歧义段在内圈就有过 margin 门的峰」。但续45 实证：过门峰 = 最终会
切换的段仅 ~10%（21/206，3 片口径）——margin 门本来就是拦着不切换的，**多数段在内圈
根本没有过门峰** ⇒ 这些段注定走「内圈扫完（白付 31+15 embeds）→ 阶段门判负 → 扩展外圈
（外圈粗扫不重复但内圈细化已付）」的完整路径；且非收工段比 v2 多付一整个内圈阶段
（粗扫 + top-3 细化）。收工段每段省 ~75 embeds vs 非收工段每段付 ~46 embeds，10%:90%
的比例注定净亏 ⇒ 3/3 片 +1.4%~+13.2% 更慢是**结构性的**。**设计教训：「提前收工」类
优化必须先证明目标事件（此处=内圈过门峰）在多数段发生；用验收数据（切换率 10%）
先做一页纸结构账就能判负，不必实跑 2.7 小时。**

### 12.6 裁决（机械执行预定门）

**FAIL（计时判负）**：虽然精度硬门 3 片零回退、p20/p34 保持 HIT、churn 4 行无真损失
（精度无损但无收益），但计时 3/3 片全部更慢（+7.9%），阶梯在本素材集上无省时收益，
属纯负优化。**结论 = 维持 `isc_refine_ladder_s=0.0` 不翻**；未改 GT、未 bump
feature_version、未 git 提交、未翻任何默认值。

### 12.7 产物与覆盖边界

- 产物：`work/isc_refine_arms/ladder_{2mkv,test1,test2}.results.json`（test3 中止无产物）；
  stdout `work/rerun_iscladder_stdout.log`（PY_EXIT=127 = 主动中止留痕）；分析
  `work/isc_refine_arms/analysis_ladder/`（`compare_iscladder_flips.py`、
  `isc48_metrics_20261003.json`、`isc48_flip_list/fine_diff/churn/inner_hit_20261003.txt`、
  `isc48_sheet_list_20261003.txt`、拼图 7 张 `isc48_*_sheet12.png` 全读毕）。
- **没验的**：① ladder 其它取值（20/45 等——判负后无意义，护栏亦禁 sweep）；
  ② test3 的 ladder 精度（中止未跑，若需要可日后单独补跑单臂）；③ 「只对窄 span 段启用
  阶梯」等混合形态（结构账同样受 10% 切换率约束，未立项）；④ v3 代码
  （`mvp/src/engine/localization/isc_refine.py` 阶梯分支）保留在树内但默认 0.0 不激活，
  后端测试全绿不受影响。
