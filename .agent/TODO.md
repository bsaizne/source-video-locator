# TODO

> **结构说明（2026-10-07 瘦身）**：本文件 = P0/P1/P2/Blocked 四容器 + 指针，目标 ≤100 行。
> 历史条目（原 43 个 ▶ 块 + 「历史记录」全节）已**逐字**迁往
> `.agent/archive/TODO_history_20261007.md`，一条未删。防复发纪律见 AGENTS.md「上下文更新约定」：
> P0 保持 ≤1 块，新增块时旧块即迁 archive。（本批 = 续65 立档，续64 块 882 字符逐字迁
> `archive/TODO_history_20261018.md`）。**续迁**：P1 里已结清/已被取代的历史条目（r15~r17 出包身份、
> 第十轮 mac 出包链、竞品 opcode 结案等 49 行）于 2026-10-13 逐字迁 `archive/TODO_history_20261013.md`。

## P0 — Current

> **▶ 2026-10-24（续91）— OmniShotCut 试点实测：段级存在性 9/15（TN 1/15）、帧级粗（1/5）、内部假切 0/9、CPU 4.4× 实时 ⇒ 段级存在性信号源【现读这条】**
> 口令「继续下一步继续」。**`mvp/src` 零改动、未出包。** 环境：api tarball + hf-mirror 权重 + 本地两行
> `cuda→cpu` 补丁（上游硬编码 CUDA，CPU 开箱炸）；venv 零新增包。
> 24 段真值对照：段级 9/15 ≫ TN 1/15；±1s 命中 1/5（idx210 +0.07）；假切 0/9 内部（3 检出=clip 边界
> 伪影）；31 分钟/片 CPU。**形态结论 = 长镜头存在性标注/复核触发器，非切点表**；接线需拍板。
> 档案：FINDINGS_OPENSOURCE_SURVEY §6；产物 `work/omnishotcut_20261024/`。
> **未结（都需口令）**：① OmniShotCut 接线方案（长镜头存在性标注形态）② 人脸身份门接线（单脸侧
> 阈 0.57）③ ai_visual 11 行用户人工复核 ④ 长镜头 GT 5 条 / 灰带 25 段 ⑤ v3 好×MISS 口径（分母 150）。
> 续90 块已迁 `.agent/archive/TODO_history_20261023_c.md`（备份 `work/premigrate_20261024_f/`）。

## P1 — Next

- [x] ~~r23 出包（等口令）~~ = ✅ **已出并四道全绿（2026-10-13 00:1x）**：
      `Video-Locator-win-x64-20261012r23.zip` 981,687,209B / 7,078 条目 / testzip=None /
      zip 内 backend.exe 77,493,384B sha16 `537bcca18760de77` == 磁盘（matches_disk_build=True）；
      **zip 内 `bridge.js` 与磁盘逐字节相同**（8,882B，含 node:http + httpRequester + data 透传）。
      bundle **28 PASS/0 FAIL**（两条新桥接锁由 r22 上的预期红转绿）· render **8 PASS/FAILED=0**
      （R1 wall=60s · 64 段无交叠 · h264_amf · 隔离在位）· 不变式 **FAILED=0** · 冒烟 AFTER_KILL=0。
      ⚠️ 订正：本条原写「预期 backend.exe sha16 与 r22 **逐字相同**」**被实测推翻** —— 实为同尺寸、
      仅 9 字节差（3 段各 3 字节，两处同值=归档长度字段）⇒ PyInstaller 非确定性构建；
      `git diff 36dec63..a84119d -- mvp/src mvp/api` 为空佐证没动 Python 运行面。
- [x] ~~待口令：release/ 四档删 r20~~ = ✅ **已删（2026-10-13 00:2x）**：删前 `zip_identity.py` 验回滚档
      r21 `testzip=None` / 7,078 条目 / backend.exe 77,493,043B / sha16 `fa3c394567cc17d2` 与档案逐字一致；
      r20 自身本批早先亦验过（`63987715436d5e31` 一致）。⇒ 现三档 r23/r22/r21。
- [x] ~~mac 包仍带同一缺陷，待用户定是否跟更~~ = ✅ **已 dispatch（2026-10-13 00:3x）**：run
      `38277827813`（ref=master，head `4fe0d96a5`，HTTP 204）。机制已读 workflow 本体验明：门槛绿 ⇒
      `gh release upload mac-alpha --clobber` **自动就地覆盖**，无需人工；门槛红 ⇒ publish 不跑、留旧包。
      用户明确「mac zip 不用你确认」⇒ **不再自行追读该 run**（watcher 日志留 `work/watch_mac_run.log`）。
- [x] ~~导出异步化（B 方案）~~ = ✅ **已落地（2026-10-13 续63 补十七）**：
      `POST /api/tasks/export` 进现有 tasks 框架（进度 0→99 + 可取消），UI 已切任务通道；
      同步 `/api/export` 保留未删。⚠️ 未提交、未出包 ⇒ 用户手上还没有；进包 = r24（mac 另 dispatch）。

- [x] ~~导出对话框 UI 修复（2026-10-10 第十三轮）~~ = ✅ **已提交并两代进包**（2026-10-12 复核）：
      `ResultsPage.vue` 告警列表加滚动 + 输出目录「浏览…」= 代码笔 `aacfaa9`（2026-10-10 23:50，实测在 master），
      `git merge-base --is-ancestor aacfaa9 09714ab` 通过 ⇒ 已在 **r21**，r22 同链继承。本条无遗留。
- [ ] **边界线三项立项已拍板（2026-10-18，「开始立项吧」），先入文档后动码**——计划 =
            `mvp/docs/PLAN_BOUNDARY_ALIGNMENT_20261018.md`，执行顺序建议：
            - [x] ~~**① scn3 网格精度**~~ = ✅ **已落地（续66，代码笔 `5bb8089`）**：判据一格未动，边界时刻改用像素腿
            10fps 原始时刻。test1 真索引 **943 场景不变 / `scene_feats` sha 不变 / 373 条边界离开网格 / gap=0**；
            尺子三档与档案逐字一致（A .250-27 · B .050-82 · C .100-80）；**后端 699 OK · API 150 OK**；合成端到端 13 项绿。
            ⚠️ **出包前硬验收未做**：4 片导出实得 + 导出计划不变式 ⇒ 出包 r27 + mac 另走 dispatch。
      - [x] ~~**② CLS 腿独立持续性门**~~ = ✅ **已落地（续67，代码笔 `b6e9113`，方案 A2）**。
                  口径**已裁 B（剪辑镜头）** —— 依据 = 导出侧 `split_clips_at_boundaries` **默认开**、注释写明
                  「真实原片转场切点」、实测跨 30s clip 被拆 9 段 ⇒ 现役产品事实上已按 B 运行。
                  ⚠️ 我先前推荐 C 是错的（只看了 `evidence_localize` 的召回注释，漏查导出层）。
                  实现 = 像素门 **OR** 语义门（`semantic_gate_ok`）+ `cls_cut_abs` 0.30→0.40。
                  尺子 TP 109→111 / FP 25 持平 / FN 16→14；全片边界 942→912（−3.2%）。
                  **A1（不改 cut_abs）已被否**：全片 +10.9% 边界，导出段数会涨一成。
            - [x] ~~**③ 弱信号段低置信边界标注**~~ = ✅ **侧车部分已落地（续66）**：`scene_strength.npy`（`[S]` 强度，
                  第 0 个恒 1.0）+ `IndexBundle.scene_strength`；不动 `scenes.npy` schema ⇒ 旧索引照常可读，
                  侧车缺失/长度不符一律退化 None（宁可丢也不修）。**「下游按阈值标注」未做**——等 ②-0 口径裁决。
- [ ] **六项立项已拍板（2026-10-07），先入文档后动码**——计划 =
      `mvp/docs/PLAN_HARDENING_SIX_ITEMS_20261007.md`，执行顺序建议：②设备回报 → ①低内存
      收缩 → ③防抖+心跳（小三件一批）→ ④独立进程监督（单独批）→ ⑤导出实得口径（与性能
      口径对齐联动）→ ⑥换形态探针族（研究线，沙盒纪律）。逐项完成打勾：
      - [x] ② 子进程设备回报标记 = ✅（2026-10-07：backend stdout 一次性 `BACKEND_DEVICE <name> <type>` 标记行（懒构建点=真实解析点）；UI 首启 READY 前拉 actual 三元组、buildIndex 不再用索引历史标签覆盖徽标）
      - [x] ① 低内存收缩 batch+预取 = ✅（2026-10-07：`media/resource_budget.py` 纯函数三档（unknown→全默认零语义；tight/critical 收缩），接 `_grab_frames_parallel` 线程与 `build_tp_index` 簇上限（切簇只改批次不改帧），`/api/settings/device` 补 low_memory_mode/memory_tier/grab_workers/max_cluster_frames）
      - [x] ③ 阶段进度防抖+心跳 = ✅（2026-10-07：`api/tasks/debounce.py` ProgressDebouncer（同阶段最小间隔合并、阶段切换/终态直通、held 先补发）接 analyze/render worker；Task 补 `last_event_at` 心跳并暴露 to_dict/UI 契约；进度条 0.2s 过渡既有）
      - [x] ④ 独立 GPU 工作进程监督 = ✅ 第一步任务级隔离（2026-10-07：`api/tasks/isolated.py`，analyze/render 子进程化，硬崩无信封退出 → failed(带 exitcode)，服务与其它任务存活；取消 = terminate；spawn 不可用回落线程内；`run_backend` 补 freeze_support；故障注入钩子 + 6 单测含真实 spawn。打包态 spawn 验证挂 r15 accept。监督重启（崩溃计数+冷却）暂不需要——任务全为用户显式发起，无自动重试消费方）
      - [ ] ~~⑤ 指标 HIT ≠ 导出实得~~ → **2026-10-07 用户裁决不做，丢回搁置区**（重启需用户再提；与「性能口径三处对齐」同批处理最合适）
      - [x] ⑥ 换形态探针族：**b 已实跑并判负关闭**（2026-10-08 续63 补六，`FINDINGS_TWO_STAGE_SAMPLING_20261008.md`）；a 置信非饱和 / c E3 换载体 / d 退化门换判据 **未跑**（本轮按口令只跑 b；是「未跑」不是「已证否」）。
            续63 复核建议（**待拍板，不自动开跑**）：先只跑 **b**，且判据换掉——档案已有
            「2fps vs 1fps 密度探针：生产严格净 0、建索引 ×2 耗时」，密度↑不改落点 ⇒ b 的
            精度上限有限，可兑现收益在**建索引耗时/首屏延迟**（现役 22~31min/片）。
            a 撞护栏（Confidence 公式冻结+不标定），d 的退化门默认关无生产影响 ⇒ 优先级最低。

## P2 — Later

- [x] TODO 瘦身 = ✅（2026-10-07：历史迁 `.agent/archive/TODO_history_20261007.md`，
      防复发纪律写入 AGENTS.md）。

## Blocked

- [ ] H4（Windows NVIDIA / CUDA）= `H4_GPU_RUNNER_UNAVAILABLE` —— 无可用 Windows GPU runner，
      需用户提供 NVIDIA 环境与计费权限（见 `.agent/STATE.md` H4-0 记录）。
