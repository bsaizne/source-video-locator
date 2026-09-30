# E1 resolve_consecutive_scene_offsets 移植双臂实测 = 无收益 + 1 真回归 ⇒ 维持默认关（2026-09-28）

> GT 版本：test2 = ground_truth_test2.json（v4 时代口径，139 正例现行集内条目）；
> 双臂 = `work/consec_{off,on}_test2/test3.results.json`（同批同 GT 同判据，唯一差异 = 旋钮；
> GPU 硬断言 DirectMLBackend，日志 `work/rerun_consecutive.out`）。

## 结论

**竞品该判据在我方生产形态下无目标对象且有伤害面 ⇒ `resolve_consecutive_enabled` 维持默认关，
移植通道关闭**（代码/单测 10 项/旋钮保留为基础设施，同 dense_recheck/conf_v2 先例）。

## 数字（test2+test3，影响面所在片；2mkv/test1 预统计 0 对未跑）

| 臂 | test2 严格 | test3 严格 | 场景 | 负例 | 支撑 |
|---|---|---|---|---|---|
| OFF | 14/20 | 34/37 | 19+37 | 0+1 | 71+230 |
| ON  | **13/20（−1）** | 34/37 | 持平 | 持平 | 持平 |

唯一翻转 **t2r01b HIT→part**；ON 臂共平移 2 对（idx4 起点重复 0.5s / idx21 完全同 span 3423.4），
idx21 无指标影响、idx4 即回归源。

## 图证（`work/consec_flip_visual/t2r01b_mid.png`，逐张读）

被平移段 OFF span 中帧 = 牛栏+水塔+GRANMIO 饲料槽（与 GT 窗同内容）；ON 平移后 = 洗车隧道红车
（完全无关内容）。⇒ 该"重复起点"是**编辑侧两段重叠（ed 5.27–6.27 与 5.8–10.5）合法取自同一素材区**，
平移砍的是正确答案，非伪影。

## 根因（与退化拒绝门续19 同型, 升级为两条独立证据）

竞品判据长在 **scene→scene 一对一认领**架构上：其单位是场景，同场景重复起点 = 必然伪影。
我方按镜头细切分 + 编辑窗可重叠 ⇒ "起点相邻/重复"是**正常叙事复用形态**。
**可复用推论（入对标纪律）**：凡"去重/唯一认领/跨段一致性"类竞品判据
（`resolve_consecutive_scene_offsets`、`max_duplicate_scene_ratio` 退化门、`ordered_search` 去重 0.25s、
路径 DP 的"孤立跳点压制"同理），移植前必须先回答"**我方架构下该伪影是否系统性存在**"——
目前四项里已实测三项不成立（退化门 −14/场景 −12、本项 −1、DP 下沉 −8）。

## 产物

`engine/localization/consecutive_offsets.py`（纯函数+留痕）· `mvp/tests/test_consecutive_offsets.py`(10)
· 旋钮 `resolve_consecutive_enabled=False` + `resolve_consecutive_dup_tol_s=1.0`（字节确证常量）
· `mvp/scripts/rerun_consecutive.py`（双臂+后端硬断言）· `visual_consec_flip.py` + 出图 ·
`work/consec_{off,on}_*.results.json` + `work/consec_{off,on}_metrics.json`。
后端全套 334 全绿（324+10）。
