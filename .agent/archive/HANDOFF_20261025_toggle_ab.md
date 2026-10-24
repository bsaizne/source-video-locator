# HANDOFF — 续94 开关矩阵 A/B（2026-10-25）

> 自包含交接件。上一份有效交接 = STATE `Next Actions` 续93 指针。
> 一句话：review 发现 5 个「代码进 runtime、带正收益证据、默认关且四片生产 A/B 从未做」的开关
> （dense_recheck / degradation_gate / resolve_consecutive / fast_global_quality_weights / conf_v2）；
> 本批跑四片生产 A/B 矩阵出默认值结论。**跑完本批后交接。**

## 1. 本批做了什么

1. **review 扫描**（口令「review 一下有什么该进 runtime 的功能但是没进的」）：config 7 个默认关开关
   × FINDINGS 结论 × PLAN × Known Issues 全对照 ⇒ 5 个待验证 + 3 个待拍板形态（OmniShotCut 候选 A /
   人脸多脸侧 / 无支撑素材警告）+ 确认排除清单（DTW/TopK/TN 原片侧/三通道/subshot/非外观信号/灰带阈值）。
2. **工具**：`mvp/scripts/rerun_toggle_ab.py`（通用开关 A/B：每轮单变量、四片全链 locate、
   索引/编辑缓存复用、DML、产物 `work/ab_{tag}_{case}.results.json`、SVL_FORCE_RERUN 重跑）。
3. **矩阵**：5 开关 × 4 片 = 20 全链（顺序执行，每片 15~35 分钟——dense_recheck/qw 腿要逐段
   抓密帧 DML 嵌入，是最重的两腿）。对照评估：`work/ab_compare_20261025.py`（三指标现行 GT 150 行
   + 逐行翻转 + HIGH 计数；基线 = `work/scn4_{case}.results.json`）。

## 2. 结果与裁决（自包含，明细见 `mvp/docs/FINDINGS_TOGGLE_AB_20261025.md`）

- **① dense_recheck = 净正，建议默认开**：四片严格 **146→147**、导出实得 **141→142**，唯一翻转
  `test1/t1r25 part→HIT`，**零退化**（与沙盒 89/139 净+6 同向；幅度变小 = 现行基线已吸收后续增益）。
  代价 ≈ locate +5~15 分钟/片。**改默认待用户一句口令**（改后须全套测试 + 四片导出不变式）。
- **② degradation_gate = 价值真实但有误伤面，维持默认关**：严格 146→**144（−2）**、导出实得 ±0。
  −2 构成 = `t2r02b`（已知真错「多取」的假阳被打掉，**拒得对**）+ `t2r06a`（M7 兄弟机位族 NEAR，
  **误伤**）；另拒 ~10 条无支撑额外行（2mkv 3 条已核不在任何 GT 窗；test3 6 条 GT 覆盖小未逐一确证）。
  **形态建议**：拒因降级为旁路标注字段（`degenerate_warning`，学 query_cross_cut 先例）——
  保可见性、不拒行、不动三指标，下批若做则误伤问题同时消解。
- **③④⑤ 未跑**（矩阵按交接预算停在 2/5 轮），续跑命令在 FINDINGS §4；conf_v2 的 A/B 口径
  = HIGH 层误报数（非三指标）。

## 3. 别再做的事

- 已判负不再立项：DTW、TopK、TransNetV2 原片侧（scn5）、正反打三通道（续74）、换形态 ⑥b、
  subshot（采纳层死结，续78）、编辑侧非外观信号（用户 2026-10-19 裁定）、灰带阈值下放（续93 闭合）。
- OmniShotCut 出切点表（它只是段级存在性信号源，帧级 ±1s 命中 1/5）。

## 4. 环境与复现

- `PY=D:/claudework/video-dedup-tool/.venv/Scripts/python.exe`；矩阵：
  `$PY -u mvp/scripts/rerun_toggle_ab.py`（全矩阵）或 `$PY -u mvp/scripts/rerun_toggle_ab.py dense_recheck_enabled`
- 对照：`$PY -u work/ab_compare_20261025.py`（产物存在即纳入，缺则记 MISSING）
- 基线三指标（现行 GT 150）：严格 146 / 导出实得 141 / 场景 149。
- ⚠️ 若矩阵被中断：脚本按产物存在跳过，`SVL_FORCE_RERUN=1` 强制重跑缺的轮次。

## 5. 未结与下一步（按优先级）

1. **一句口令即可执行**：`dense_recheck_enabled` 默认改 True（config 一行 + 后端全套 + API +
   四片导出不变式 + 出包 r29 同批）。
2. **degradation_gate 改标注形态**（degenerate_warning 旁路字段 + 逐图 test3 六条被拒行）——
   下批候选，方案已在 FINDINGS §3。
3. **③④⑤ 补跑**（命令在 FINDINGS §4；每轮 ≈1.5~2 小时；qw 最重、conf_v2 口径不同）。
4. 出包 r29（含 face_identity 续93 + 本批若改默认的 dense_recheck）；mac 另 dispatch。
5. 旧未结：OmniShotCut 候选 A / UI 呈现层 / v3 口径（分母 150）。

