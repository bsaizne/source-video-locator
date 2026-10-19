# TODO

> **结构说明（2026-10-07 瘦身）**：本文件 = P0/P1/P2/Blocked 四容器 + 指针，目标 ≤100 行。
> 历史条目（原 43 个 ▶ 块 + 「历史记录」全节）已**逐字**迁往
> `.agent/archive/TODO_history_20261007.md`，一条未删。防复发纪律见 AGENTS.md「上下文更新约定」：
> P0 保持 ≤1 块，新增块时旧块即迁 archive。（本批 = 续65 立档，续64 块 882 字符逐字迁
> `archive/TODO_history_20261018.md`）。**续迁**：P1 里已结清/已被取代的历史条目（r15~r17 出包身份、
> 第十轮 mac 出包链、竞品 opcode 结案等 49 行）于 2026-10-13 逐字迁 `archive/TODO_history_20261013.md`。

## P0 — Current

> **▶ 2026-10-19（续73）— ✅ `og720-720` 相似度「自相矛盾」结案（只读复核，零代码改动）【现读这条】**
> 口令「继续这个项目」。**本批不动 `mvp/src`、不出包**，结的是一条自 2026-10-16 挂了三轮会话的读数。
> **一、结论**：0.08 与 0.97 **两个数都不错**，是**三个不同问题**被当成了同一个量 ——
> 0.97 = og720 在**成片**里找得到（逐帧 max 中位 0.9728，最佳匹配时刻 64.03~64.10s / 成片 64.20s）；
> 0.73 = 在**解说全片**里最好也就这样（0.7282）；0.08 = 在**解说最后几秒**里找不到（最后 1s 0.0959 / 最后 5s 0.1182；
> `centroid` 口径 0.0926~0.1069）。
> **二、反证（把「谁算错了」排除）**：35 段 og 素材对解说 `max` 中位**最低也有 0.479**、对成片**最低 0.868**
> ⇒ **0.08 不可能来自「对整部片」口径**，只能来自短窗（≤5s）或质心。
> **三、素材本体**：**真值 15 帧 / 0.626s**（缓存口径 17 帧 / 0.709s，35 段全部恒多 2 帧 = 已知假象）、帧间自相似 **0.9927**、像素帧差 `d_med` **0.19**（35 段最小）⇒ 一张定格卡。
> 0.97 的自洽性：成片末帧 vs og720 末帧 cos **0.9625**；素材 0.626s → 成片 0.07s 窗 ≈ **9:1**。
> **四、口径教训**：**「A 与 B 相似度 X」不是良定义的量**，必须先固定 ① 谁对谁 ② 窗口多大
> ③ 逐帧 max / 质心 / 逐帧配对 ④ 中位还是均值 —— 四个自由度换一个，读数就能从 0.08 跑到 0.97。
> **五、如实**：⚠️ **素材原件已不在磁盘**（`C:\Users\Bsaizne\Downloads\clips\clips` 已不存在）⇒ 只读
> 2026-10-16 落盘的特征缓存复核；**0.08 的精确单点还原未做到**（当时代码未入库），给的是能/不能出现 0.08 的口径族。
> **六、口径已裁但判负（续74，2026-10-19）**：「同场景内正反打算同一镜头」用户裁定**采纳**（选项前者 =
> 剪辑事实保留、只影响导出层拆段），但**动码前测量三条判据通道全判负**（强度 82% 顶格 · 腿来源召回 18%/精确率 60% ·
> 语义距离重叠 · 往复性 65% vs 52% 只够当弱先验）⇒ **需要人脸/ReID 这类当前管线没有的信号**。
> 建议**先不做**（硬做 = 四成真换景被误合并）。落档 `mvp/docs/FINDINGS_SAME_SCENE_REVERSE_SHOT_20261019.md` 与 STATE Current Problem。
> **七、未结（不变）**：① mac 包（需 token 或手动 dispatch）② 立项③「下游按阈值标注」③ ~~产品口径「同场景正反打算不算一个镜头」~~（**已裁=算同一镜头，但判负**，见上第六条）
> ④ 出 r28（`source_merge` 同族批 + 本批档案，用户手上仍 r27）。
> 落档 `mvp/docs/FINDINGS_OG720_RESOLVED_20261019.md`；探针 `work/probe_og720{,b,e}.py`；
> 续68 块已**逐字**迁 `.agent/archive/TODO_history_20261019.md`。

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
