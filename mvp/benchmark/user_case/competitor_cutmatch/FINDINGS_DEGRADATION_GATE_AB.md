# FINDINGS — 退化拒绝门 + 场景覆盖门槛 移植实测（2026-09-28 续19, T1-1）

> **GT 版本**：`ground_truth_v4.json`(2mkv) + `ground_truth_test1|2|3.json`（139 正例 / 9 负例，v4 口径）
> **基线批**：`work/rerun_<case>_perfopt.results.json`（生产现役两级切分 + 白闪守卫，严格 **117/139**）
> **判据**：`measure_shot_recall.evaluate`（S_strict 主口径 + 场景级 ±15s + 负例误报 + 支撑 span），
> 双臂 = **同一结果批、同一 GT、同一判据**，唯一差别是门开没开 ⇒ 差异全部归因于门本身。
> **runtime 改动**：新增 `engine/localization/degradation_gate.py` + 3 个旋钮，**默认全关**，
> 生产链路行为与改前逐字节一致（门在 `locate()` 末尾，`enabled=False` 时零 mutation）。

---

## 1. 竞品语义与确证值

`cutmatch.results.validation` 三条硬停（字节确证，见 `FINDINGS_COMPETITOR_FULL_SWEEP.md` /
`FINDINGS_CAPABILITY_MAP_20260928.md` 表 D）：

| 竞品键 | 值 | 语义 |
|---|---|---|
| `max_duplicate_scene_ratio` | **0.8** | 重复率退化 → 硬停 |
| `min_scene_coverage` | **0.2** | 覆盖不足 → 硬停 |
| （候选为空） | — | 空答案 → 硬停 |

另有 `exporting.segments.builder` 的导出前告警「N 个单帧片段 → 会生成闪烁视频」。

## 2. 我方口径映射（不是照抄实现）

| 竞品 | 我方落地 | 为什么这样映射 |
|---|---|---|
| 重复率退化 | 本段主 span 被**更强的其它结论**已认领区间的覆盖比 > `max_duplicate_scene_ratio` ⇒ 该段拒识 | 竞品是 scene→scene 路径匹配，"同一源场景被反复交答案"= 匹配器卡位；我方按镜头细切分，判据只能落在主 span 归属上 |
| 覆盖不足 | 候选子 span（场景/事件扩池产物）`cover < min_scene_coverage` ⇒ 丢弃该子 span，不给它兜底 | 我方 `cover` 字段与竞品 scene coverage 同量纲（0~1） |
| 单帧片段告警 | 导出计划中宽度 < `export.min_clip_s`(0.15s) 的 clip 计数 → `LOC-2001` 告警，**只告警不裁剪** | 竞品同为告警语义；改数据要用户拍板 |

实现细节：按置信分降序处理（同分按编辑序），**最强认领者存活**、被拒者不再认领（避免一处误配级联
拉黑全部重叠段）；被拒段写 `failure_reason="degenerate_duplicate"` + 降 LOW + reason
`degenerate_duplicate_rejected`，`build_export_plan` 天然跳过；用户手改/已排除/未定位段不受管辖。

## 3. 实测结果（`mvp/scripts/replay_degradation_gate.py` → `work/degradation_gate_ab.json`）

### 3.1 竞品原值双臂（门开 = dup 0.8 + cover 0.2）

| 片 | 严格 | 场景级 ±15s | 负例误报 | 支撑 | 被拒段数 | 子 span 丢弃 |
|---|---|---|---|---|---|---|
| 2mkv | 35 → **32** (−3) | 39 → 35 | 3/4 → 3/4 | — | 7 | 103 |
| test1 | 34 → **33** (−1) | 42 → 41 | 0/1 → 0/1 | — | 2 | 19 |
| test2 | 14 → **7** (−7) | 19 → 15 | 0/1 → 0/1 | — | 3 | 120 |
| test3 | 34 → **31** (−3) | 37 → 34 | 1/3 → 1/3 | — | 8 | 76 |
| **合计** | **117 → 103 (−14)** | **137 → 125 (−12)** | **4/9 → 4/9 (±0)** | **591/1140 → 390/762** | 20 | 318 |

翻转清单（HIT→MISS/part）18 条，全部是**单向变差**，无一例 MISS→HIT：
`p23 p29 p35 p36` · `t1r14e` · `t2r01a t2r01c t2r02a t2r02b t2r05a t2r06c t2r07a t2r07b` ·
`t3r02b t3r02c t3r04b t3r06b`。

### 3.2 消融（把两条门拆开算账）

| 配置 | 严格 | 场景 | 负例 |
|---|---|---|---|
| 仅重复率门（dup 0.8，cover 0.0） | 117 → **109 (−8)** | 137 → 129 | 4 → 4 |
| 仅覆盖门槛（cover 0.2，dup 1.0） | 117 → **110 (−7)** | 137 → 133 | 4 → 4 |
| 重复率门阈值放宽到 0.95 | 117 → **109 (−8)** | 137 → 129 | 4 → 4 |

⇒ 两条门各自都是净伤害；0.95 与 0.8 结果相同 ⇒ 被拒段的重叠度接近 1.0（近乎全包含），
**不是阈值敏感问题，是判据本身在我方架构上语义不成立**。

### 3.3 多模态逐图复核（用户纪律：GT 不是唯一复核标准）

`mvp/scripts/visual_gate_flips.py` → `work/gate_flips_visual/`，三行图 = QUERY / REJECTED / GT：

| 图 | dup | 读图裁决 |
|---|---|---|
| `2mkv_s03_flip.png`（seg4，ed 9.4–11.2 → REJECTED 1580.0–1583.0） | 1.00 | **REJECTED 三帧与 GT 窗三帧逐帧同内容**（瞭望塔 + 水库堤面，同构图同机位）；QUERY 是同一镜头经瞄准镜遮罩的画面 ⇒ 被拒的是**完全正确**的答案，拒因 = 另一段（瞄准镜视角那段）已认领同一源区间 |
| `test2_s46_flip.png`（seg47，ed 56.0–57.3 → REJECTED 1626.7–1631.8） | 1.00 | REJECTED 第三帧（27:11.8 紫衣男 + 绿盒测试台）与 GT 窗（1631.0–1632.3）**同镜头同主体**；前两帧是同场景相邻机位 ⇒ 仍是正确答案被砍 |

⇒ 图证与指标同向：**该门在我方口径下砍掉的是正确回答**，不是错答。机制清楚——
解成片把同一源镜头用于多个查询单元（回闪、瞄准镜/遮罩视角、快剪同场景多机位），
我方每个查询单元各自给出该源区间是**合法且有用**的输出，而竞品的"重复即退化"前提
来自它 scene→scene 一对一路径匹配架构。

## 4. 裁决

1. **默认关保持不变**（`degradation_gate_enabled=False`）。代码与旋钮保留、测试保留，
   作为将来"按片/按档位可选保守门"或"仅对 LOW 段生效的保守版"的落点。
2. **不做阈值再调**：0.95 与 0.8 同结果已证明不是灵敏度问题；再调就是拿 GT 反推参数（越界）。
3. **碎片告警保留并可用**（`LOC-2001`，只告警不改数据，零指标影响）；
   `min_clip_s` 默认 0.15s 是保守值，等真机导出验收时按用户反馈再定。
4. **竞品这条能力对我方关闭移植**，与 `conf_v2 置信公式`（231 段仅 1 段有效降档）、
   `TN 替换切分`（−16）、`DTW 排序层`（平均 rank 变差）同族：**它的判据长在它的架构上**。
   本轮新增的通用结论 = *凡"跨段全局一致性/唯一认领"类判据，必须先改造成
   与我方"每查询单元独立给答案"口径同构的形式，再谈移植*。

## 5. 顺带修掉的一条真断链（同轮）

`load_config` 的 pipeline 覆盖是**手写白名单**，漏了 `vote_prior_*`(5)、`subshot_*`(4)、
`patch_v2_*`(4)、`dense_recheck_*`(5)、`edited_cache_enabled`、`conf_v2_*` 等 ⇒
用户在 JSON 里写了这些键会被**静默忽略**（值根本不进 config）。已改为
**以 dataclass 字段为唯一权威清单**泛化覆盖（`_build_dataclass` + `_cast`），并：
- 未知键不再丢弃而是 `warning` 留痕（不静默出错）；
- 修掉旧代码 `bool("false") == True` 的坑（`_cast` 对 bool 字段按词解析 `1/true/yes/on`）；
- media/device/export 三块同样泛化，杜绝同类漂移。
回归：新增 `ConfigOverrideGeneralisationTest` 4 例 + 后端 311 / API 61 全绿。

## 6. 复现命令

```bash
PY="D:/claudework/video-dedup-tool/.venv/Scripts/python.exe"
$PY mvp/scripts/replay_degradation_gate.py --write                       # 竞品原值双臂
$PY mvp/scripts/replay_degradation_gate.py --min-cover 0.0               # 仅重复率门
$PY mvp/scripts/replay_degradation_gate.py --max-dup 1.0                 # 仅覆盖门槛
$PY mvp/scripts/measure_four_results.py --pattern "work/gateon_{case}.results.json"
$PY mvp/scripts/visual_gate_flips.py 2mkv ; $PY mvp/scripts/visual_gate_flips.py test2
$PY -m unittest mvp.tests.test_degradation_gate -v                        # 17 例
```

产物：`work/degradation_gate_ab.json`、`work/gateon_<case>.results.json`（4 份，gated 批）、
`work/gate_flips_visual/`（10 张 + index.json）。
