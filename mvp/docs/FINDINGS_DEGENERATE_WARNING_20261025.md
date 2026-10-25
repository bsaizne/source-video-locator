# FINDINGS — `degenerate_warning` 旁路标注落地（2026-10-25 续95②）

> 口令「开始」（续95 批第 2 件）。方案来源 = `FINDINGS_TOGGLE_AB_20261025.md` §3（续94 裁决：
> degradation_gate 维持默认关，拒因降级为旁路标注形态）。代码笔 `d8ee02b`。**未出包。**

## §1 形态

- **域**：`domain.DegenerateWarning(ratio, threshold)` + `Result.degenerate_warning`（to_dict/from_dict 对称，学 query_cross_cut / face_identity 先例）。
- **引擎**：`engine.localization.degradation_gate.annotate_degenerate_duplicates(results, *, max_duplicate_scene_ratio)` —— 与 `apply_degradation_gate` 第 2 步**同判据同处理序**（`_answerable` 管辖、置信分降序、最强认领者存活、被标注者不再认领、并集重复率、严格大于阈值才标），但超阈段只写 `degenerate_warning`：不写 failure_reason、不动置信度、不删子 span/行。gate 真拒的段（failure_reason 非空）自动不在标注范围。
- **接线**：`locator_service` 在 gate 之后、shot_split 之前（与 gate 同辖区=最终主 span）；纯计算零解码/推理，**始终运行**（无独立开关，阈值共用 `max_duplicate_scene_ratio=0.8`；「阈值开满 vs 关死，除本字段外结果 JSON 逐键相同」的单测已锁）。
- **gate 本体不动**：`degradation_gate_enabled` 维持默认 False（拒识语义保留给显式开启者）。

## §2 验证

1. **单测 +8**（`test_degradation_gate.py` 36 项）：超阈标注零语义面 / 阈值边界 / 被标注者不再认领 / skip 规则与 gate 一致 / gate 拒识行不被标注 / 阈值开满静默 / 序列化 roundtrip / GateStats.warned。
2. **生产链 E2E（test2 全链重跑，当前默认 = dense_recheck True + 标注）**：67 段 **degenerate_warning=1** —— seg17 edited 14.000-15.467 ratio=0.864，**与 A/B 中 gate 拒识的正是同一行**（t2r02b 家族，续86/87 定案的已知真错「多取」）；该行 `failure_reason=None`、confidence HIGH 0.8655 未动。三指标与 scn4 基线 / dense A/B 腿**逐位一致**（strict 25 / main 23 / verified 19 / scene 25 / fp 0）。耗时 1816s（≈30min，dense 腿在位）。
3. **落盘产物重放对账的边界（留档防误读）**：拿旧 results.json 重放标注函数**对不齐 gate 拒识集是预期行为**——gate/标注在 shot_split **之前**（split 前父 span 辖区）判，而 results.json 存的是 split 后子行（span 被 re-project、被拒行未拆分），辖区不同不可直接比对。等价性由「同一函数体 + 同一调用点辖区 + 单测」构造性保证，E2E（上条）实证。

## §3 test3 六条被拒行逐图定案（续94 遗留核验，接触表 `work/contin95_gatecheck/`）

| 行 | edited | 认领 orig | 画面判读 | 定性 |
|---|---|---|---|---|
| seg13 | 14.14-15.21 | 449.96-451.04 | 编辑=巨龙俯瞰燃烧城镇 / 原片窗=士兵夜战庭院，不符；区间被 seg47/48（HIGH）邻近认领 | **拒对** |
| seg14 | 15.21-15.75 | 440.07-440.61 | 编辑=巨型弩炮特写 / 原片窗=燃烧城镇俯瞰，不符；被 seg43-46 认领族包围 | **拒对** |
| seg15 | 15.75-16.29 | 7893.23-7893.77 | 编辑=弩炮特写 / 原片窗=暗色兽人大厅，不符 | **拒对** |
| seg53 | 64.00-66.21 | 465.50-467.50 | 编辑=瑟兰迪尔骑麋鹿 / 原片窗=**同一镜头同一主体**，内容匹配 | **误伤** |
| seg56 | 69.86-71.14 | 244.88-246.88 | 编辑=Erebor 绿厅 / 原片窗=同景异镜（矮人人群） | **NEAR**（合法歧义） |
| seg66 | 86.64-88.07 | 500.63-502.63 | 编辑@86.6s 与编辑@139.8s（seg98 HIGH）**两处真实取用同一山坡镜头**（不同字幕），内容都匹配 | **误伤**（解说片刻意复用） |

**合计 3 拒对 + 2 误伤 + 1 NEAR** —— 与续94「价值真实（打掉无支撑行）但有误伤面（NEAR/复用族）」的定性完全吻合，且实证标注形态下误伤从「伤害」降为「提示」是对的。seg53/seg66 的内容匹配同时说明：这批「重复」多数不是定位错，是**剪辑片叙事性复用**——用户看到 `degenerate_warning` 提示后自行取舍即可。

## §4 边界与未结

- UI 呈现层未做（同 face_identity：PLAN 决策点③待拍板，契约已在 results JSON）。
- 未重跑其余三片的生产链（标注纯计算、test2 E2E 已证触发与零语义面；全量回归留给 r29 出包批）。
- gate 本体的「覆盖不足丢子 span」分支未动（属拒识语义，gate 默认关下无生产影响）。
