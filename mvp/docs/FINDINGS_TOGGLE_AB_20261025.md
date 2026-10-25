# FINDINGS — 默认关开关的四片生产 A/B（2026-10-25 续94）

> 口令「review 一下有什么该进 runtime 的功能但是没进的」+「开始吧，跑完就交接」。
> 背景：config 有 5 个默认关开关，历史欠四片生产回归（`rerun_toggle_ab.py` 本批补齐工具）。
> **`mvp/src` 零改动（纯测量批）；矩阵跑了 2/5 轮后按交接预算停，③④⑤ 如实记未完成。**

## §1 方法

每轮**单变量**开一个开关，四片全链 `SourceLocatorService.locate`（索引/编辑缓存复用、
feature_version 不变、DML），产物 `work/ab_{tag}_{case}.results.json`；基线 = `work/scn4_{case}`；
三指标 = `measure_shot_recall.evaluate`（现行 GT **150** 行）。对照脚本 `work/ab_compare_20261025.py`。
基线读数：严格 146 / 导出实得 141 / 场景 149。
耗时实测：单片全链 20~43 分钟（dense_recheck 腿要逐段 ±4s@10fps 密帧 DML 嵌入，最重）。

## §2 第①轮 dense_recheck（密帧起点复核）= 净正，**建议默认开**

| 指标 | 基线 | +dense_recheck |
|---|---|---|
| 严格 | 146 | **147（+1）** |
| 导出实得 | 141 | **142（+1）** |

- 全四片唯一翻转：`test1/t1r25 part→HIT`（main_hit False→True）；test2/test3/2mkv 持平，**零退化**。
- 与沙盒结论（89/139 净+6，续10l）同向；幅度变小是因为现行基线已吸收 scn3/scn4/fast_global 增益。
- 裁决：**建议 `dense_recheck_enabled` 默认改 True**（净正零退化 + 竞品同语义逐字
  （dense_alignment，增益门 0.04）+ 攻现役剩余误差主体「起点精度」）。代价 = locate 增时
  ~5-15 分钟/片。改默认需：全套测试 + 四片导出不变式（改后跑）。

## §3 第②轮 degradation_gate（退化拒绝门）= 价值真实但有误伤面，**维持默认关**（建议改标注形态）

| 指标 | 基线 | +degradation_gate |
|---|---|---|
| 严格 | 146 | **144（−2）** |
| 导出实得 | 141 | 141（±0） |

- 两条翻转全在 test2：**`t2r02b HIT→part`（拒得对——续86/87 定案的已知真错「多取」假阳被打掉）**
  与 **`t2r06a HIT→part`（误伤——M7 兄弟机位族，v2 校准点 NEAR：同机位反复出现的合法歧义）**。
  即 strict −2 = −1 正确恶化（假阳）−1 误伤，导出实得分毫未动。
- 被拒额外行（不影响任何 GT 行命中）：2mkv +3、test2 +1、test3 +6、test1 +0，拒因几乎全
  `degenerate_duplicate`——与 a7「无支撑素材」族同向（导出层盲区：多余素材不减召回所以三指标
  看不见）。2mkv 3 条已核不落任何 GT 窗（拒对）；test3 6 条（og 441~502 蒙太奇段）GT 覆盖小
  **未能逐一确证**，留待逐图。
- **更优形态建议（下批）**：三个拒因（degenerate_duplicate / 覆盖不足）从 `failure_reason`
  降级为**旁路标注字段**（如 `degenerate_warning`，学 query_cross_cut / face_identity 先例）——
  既保留用户可见性，又不拒行、不动三指标，NEAR 族误伤也从「伤害」降为「提示」。

## §4 ③④⑤ 补跑结果（2026-10-25 续95④ 完跑；基线口径改 = dense 腿/现役栈）

> 三轮在续95 跑（dense_recheck 已默认开）⇒ 单变量对照基 = `ab_dense_recheck_{case}`（现役栈），
> scn4 只作历史参考；ab_compare 对 scn4 的 +1 全部来自 dense 腿本身。

- **③ resolve_consecutive = 净零，维持默认关**：严格 147→147，四片三指标逐位持平
  （2mkv/test3 sup ±2/±3 微动）——与 E1 预统计（影响面 7 对且多合法复用）一致。
- **④ fast_global_quality_weights = 净零，维持默认关**：⚠️ 首跑暴露 qw 广播 bug
  （旧内联 `(n,)−(3,)` 必炸，224 段 fast_global 整段放弃 = 该腿生产从未真跑过），
  修复（`combine_quality_weights`，代码笔 `3db0391`）后重跑：37 行 span 微动
  （12/6/6/13），三指标与 dense 腿逐位相同 ⇒ 质量权重无净收益。
- **⑤ conf_v2 = 微收益零代价，维持默认关（是否翻默认待拍板）**：span 逐位一致（只改档位）；
  全四片**恰 1 条变化** = test3 一条无支撑行 HIGH→MEDIUM（edited 39.214，UNMATCHED），
  零 HIT 误伤、负例档位不变（HIGH 185→184）。
- 续跑命令（原始）：
```bash
PY=D:/claudework/video-dedup-tool/.venv/Scripts/python.exe
$PY -u mvp/scripts/rerun_toggle_ab.py resolve_consecutive_enabled
$PY -u mvp/scripts/rerun_toggle_ab.py fast_global_quality_weights_enabled
$PY -u mvp/scripts/rerun_toggle_ab.py conf_v2_enabled
$PY -u work/ab_compare_20261025.py   # 汇总自动纳入新产物
```
注意：conf_v2 的 A/B 看「HIGH 层误报数」而非三指标（confidence 不进三指标）；qw 腿与 dense_recheck
同量级重（重提密帧）。

## §5 review 全景（同批交付）

- **该进没进（本批已裁决）**：①建议开（净正）；②维持关 + 形态建议改标注。
- **待拍板形态**：OmniShotCut 长镜头存在性标注（PLAN 候选 A，包体 +1GB/建索引翻倍）；人脸身份门
  多脸侧（逐人跟踪，未立项）；「无支撑素材」全量导出警告（a7 产品化，成本高）。
- **确认不进**：DTW、TopK、TN 原片侧（scn5）、正反打三通道（续74）、subshot（死结）、
  编辑侧非外观信号（用户裁定）、灰带阈值下放（续93：切换组与无切换组 dmax 完全重叠）。
