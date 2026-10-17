# TODO

> **结构说明（2026-10-07 瘦身）**：本文件 = P0/P1/P2/Blocked 四容器 + 指针，目标 ≤100 行。
> 历史条目（原 43 个 ▶ 块 + 「历史记录」全节）已**逐字**迁往
> `.agent/archive/TODO_history_20261007.md`，一条未删。防复发纪律见 AGENTS.md「上下文更新约定」：
> P0 保持 ≤1 块，新增块时旧块即迁 archive。**续迁**：P1 里已结清/已被取代的历史条目（r15~r17 出包身份、
> 第十轮 mac 出包链、竞品 opcode 结案等 49 行）于 2026-10-13 逐字迁 `archive/TODO_history_20261013.md`。

## P0 — Current

> **▶ 2026-10-17（续63 补十八）— 上一会话三批未提交改动收口：音轨布局回退 + 竞品黑盒对照 + 取材扩宽 1.5【现读这条】**
> 接手时工作树 = 三批**未提交未出包**改动（交接件 `.agent/archive/HANDOFF_20261017_rea_competitor_blackbox.md`）。
> 先验 mtime 无孤儿写入者，再自己重跑门禁（不引用上一会话数字）。
> **① 音轨回退（`2afcec7`）**：「N 声道 + 未指定布局」源被原生 aac 拒收（rc=-22、0 字节）⇒ 抽素材整腿失败；
> 触发面 = **本产品自抽的 clip 天然是这种源**（5.1(side) 编进 MP4 后布局丢失）。次生陷阱 = 失败留 0 字节 +
> 剪映腿裸 `exists()` ⇒ 第二次导出静默写坏草稿。修 = 首跑参数逐字不变、失败后按 48k/stereo 重试一次 +
> 清半成品 + 判据收一 `app.exporters.clip_present`（教训 ⑲）。改前 A 臂 MediaError / 改后 A 臂 OK 447,853B
> 且 C 臂仍 rc=-22（判据真咬）。**同族已枚举**：另两处「存在即复用」自带有效性判据、无潜伏问题；
> `source_merge.py::_transcode_args` 同形缺陷**未改**（硬失败非静默，需单独立批）。
> **② 竞品黑盒对照**（同尺 `boundary_gt_v1.json`，竞品侧只读）：切点 ±1.0s P/R/F1 = 竞品 t0.50
> **0.885/0.958/0.920**（test1 F1 1.000）vs 我方 scn2 **0.550/0.917/0.687**（test1 0.200）；
> 后处理规则可用其 probs **逐帧复现**（1874/1874、491/491 全等）⇒ `sensitivity=18` 对切点集合无可观测作用。
> **导出层双臂**：我方切点 131/139 vs 竞品切点 130/139（严格同 135）⇒ **换更准切点在导出实得不涨**；
> 竞品优势在**信号源（TN 逐帧概率）**不在后处理三条。
> **③ `material_expand_rel_cap` 2.5 → 1.5（`beedb91`，口径用户拍板）**：四档（2.5/2.0/1.5/1.2）导出实得
> 131/139、严格 135/139 **逐位不变**，Σ素材宽 499.1→421.7s ⇒ 高 cap 扩宽是纯代价。
> ⚠️ **cap 1.5 ≈ 关闭扩宽**（不变式扩宽条数 0/0/0/1，本会话重跑独立印证；Σ421.7 ≈ core 419.9）=
> 卷轴只给解说引用窗、不再撑成完整镜头；温和档 = **2.0**（−9.4%）一句话可切。
> **门禁（本会话逐字跑，`work/verify_20261017/`）**：后端 **Ran 675 OK (skipped=2) / rc=0**（199.8s，
> `BACKEND_DEVICE directml amd`）· API **Ran 150 OK / rc=0** · 导出计划不变式 **FAILED=0 / rc=0**。UI 无改动面。
> **静态线两次判死已收线**（REA Win Ghidra P0 只收原生 PE；全量 PE 2G→OOM、10G 30min 无产出）⇒ 别再重开。
> **边界（如实）**：**观感面未测**（cap 1.5 成片接缝/硬切无读图，本批只数据面）· 黑盒只覆盖共同可测的
> 2mkv+test1 · **未出包** ⇒ 用户手上仍是 r24 · `mvp/ui` 零改动 ⇒ **mac 不必另 dispatch** · 未推远端。
> **主线「过渡不流畅」仍未结**：缺他指认的秒数 / 未转码原始 `movie_*.mp4` / `*.results.json`；
> `og720-720` 相似度 0.08 vs 0.97 自相矛盾仍挂账。
> 明细 = STATE Current Task 顶部「补十八」块 + `mvp/docs/` 无新增（本轮未写方案文档）。

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
