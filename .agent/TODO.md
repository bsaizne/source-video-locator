# TODO

> **结构说明（2026-10-07 瘦身）**：本文件 = P0/P1/P2/Blocked 四容器 + 指针，目标 ≤100 行。
> 历史条目（原 43 个 ▶ 块 + 「历史记录」全节）已**逐字**迁往
> `.agent/archive/TODO_history_20261007.md`，一条未删。防复发纪律见 AGENTS.md「上下文更新约定」：
> P0 保持 ≤1 块，新增块时旧块即迁 archive。

## P0 — Current

> **▶ 2026-10-07（续62）— 成片相邻段重复画面已修【现读这条】**
> 根因 = 定位段源窗 `min_span_s=2.0` 地板 vs 0.7~1.5s 剪辑段 ⇒ 贴接相邻两段必然交叠
> （≈ 2s − 编辑时长），逐段取材再拼接的成片/EDL/XML 重复画面；非最近批次引入。
> 修 = `exporters.trim_adjacent_source_overlaps()`（中点切开 + 包含形态外层挖洞，内层完整保留；
> 非贴接重叠=真实复用不裁；单帧守卫），接线 `render_movie` 与 edl/fcp7_xml 导出。
> 门禁：后端 **565 OK** · API **105 OK** · 真实四片回放重叠 → 0 且并集覆盖 Δ=0。已提交已推送。
> **现役包 = r14**（`Video-Locator-win-x64-20261007r14.zip` 981,639,927B / 7,078 条目 /
> backend.exe `sha16=4f5631af9e4ea51f`）；accept+三防+启动冒烟全 **FAILED=0**；r10/r11 已删，留 r13+r14。
> **✅ 包体级判别已闭合（续62 补一）**：r13 vs r14 双臂 A/B（唯一变量 backend.exe，打包态 headless
> 灌真实四片结果批 → edl/fcp7_xml 导出 + 2mkv 渲染）：r13 EDL 贴接重叠 **4/2/4/16 对**
> （症状复现）；r14 **全 0**；并集覆盖两臂 Δ=0.00；渲染时长差 5.046s ≈ EDL 重复秒 4.98s。
> 留证 `work/r14_trim_pkg/report.json`。
> **✅ 剪映去重语义已统一（续62 补二，用户拍板「先统一」）**：剪映分支取材扩展后施加同一
> trim，`plan_jianying_assets` 删回并改逐 clip 一素材。**顺带发现旧回并真缺陷**：条件只看源区间
> ⇒ 源序回跳 clip 被静默吞掉——旧卷轴四片只剩 5/49/22/3 条素材、覆盖 4.28/123/37/15s
> （真实 152/129/97/167s）。门禁：后端 **569 OK**（+4 锁）· API **105 OK** · 四片回放 +
> 2mkv 真代码端到端 PASS（`work/jianying_unify_{replay,e2e}_20261007.py`）。
> **r14 不含补二**（剪映统一只在源码树，进包需下次出包授权）。
> **待拍板**：① 是否出 r15（补二进包）。~~剪映卷轴语义统一~~（本轮已做）。
> **仍搁置（用户裁决，勿再提议）**：mac 再 dispatch · LOC-1107 拆码 · A1→A2∥A3 · 性能口径对齐 · 成片缺口标记。
> 另：~~竞品 opcode 通道可行性~~ = 已试采结案（续62 补三，blob 序通道打开）；`883581e` 起全部档案推送等口令。

## P1 — Next

- [ ] 待用户口令：git 推送（本地五笔：`883581e` r14 档案 / `021e6e1` 续62 补一包体判别 /
      `4e58f11` 续62 补二剪映统一 / `030b6d6` 档案瘦身 / `eb9f6ed` 续62 补三 opcode 结案）。
- [ ] 待用户授权：r15 出包（续62 补二剪映语义统一只在源码树，r14 不含）；
      出包后必跑 accept + 三防 + 启动冒烟。
- [x] 竞品 opcode 通道可行性 = ✅ 已试采结案（2026-10-07 续62 补三）：字面通道判死（0 pyc，
      Nuitka AOT）；机器码绑定通道判死（LEA→blob / MOV→平铺数组两形态不成立，全量反汇编
      路径未立项）；**blob 序通道打开**（blob 序=源码书写序，进度 pct 互证；tracker 阶段词表
      「特征→候选→召回→定位」与 V2 流程注册序已产出）。
      明细 `competitor_cutmatch/FINDINGS_OPCODE_CHANNEL_20261007.md`。
- [ ] **六项立项已拍板（2026-10-07），先入文档后动码**——计划 =
      `mvp/docs/PLAN_HARDENING_SIX_ITEMS_20261007.md`，执行顺序建议：②设备回报 → ①低内存
      收缩 → ③防抖+心跳（小三件一批）→ ④独立进程监督（单独批）→ ⑤导出实得口径（与性能
      口径对齐联动）→ ⑥换形态探针族（研究线，沙盒纪律）。逐项完成打勾：
      - [x] ② 子进程设备回报标记 = ✅（2026-10-07：backend stdout 一次性 `BACKEND_DEVICE <name> <type>` 标记行（懒构建点=真实解析点）；UI 首启 READY 前拉 actual 三元组、buildIndex 不再用索引历史标签覆盖徽标）
      - [x] ① 低内存收缩 batch+预取 = ✅（2026-10-07：`media/resource_budget.py` 纯函数三档（unknown→全默认零语义；tight/critical 收缩），接 `_grab_frames_parallel` 线程与 `build_tp_index` 簇上限（切簇只改批次不改帧），`/api/settings/device` 补 low_memory_mode/memory_tier/grab_workers/max_cluster_frames）
      - [x] ③ 阶段进度防抖+心跳 = ✅（2026-10-07：`api/tasks/debounce.py` ProgressDebouncer（同阶段最小间隔合并、阶段切换/终态直通、held 先补发）接 analyze/render worker；Task 补 `last_event_at` 心跳并暴露 to_dict/UI 契约；进度条 0.2s 过渡既有）
      - [x] ④ 独立 GPU 工作进程监督 = ✅ 第一步任务级隔离（2026-10-07：`api/tasks/isolated.py`，analyze/render 子进程化，硬崩无信封退出 → failed(带 exitcode)，服务与其它任务存活；取消 = terminate；spawn 不可用回落线程内；`run_backend` 补 freeze_support；故障注入钩子 + 6 单测含真实 spawn。打包态 spawn 验证挂 r15 accept。监督重启（崩溃计数+冷却）暂不需要——任务全为用户显式发起，无自动重试消费方）
      - [ ] ~~⑤ 指标 HIT ≠ 导出实得~~ → **2026-10-07 用户裁决不做，丢回搁置区**（重启需用户再提；与「性能口径三处对齐」同批处理最合适）
      - [ ] ⑥ 换形态探针族 4 条（a 置信非饱和 / b 两级采样 / c E3 换载体 / d 退化门换判据）

## P2 — Later

- [x] TODO 瘦身 = ✅（2026-10-07：历史迁 `.agent/archive/TODO_history_20261007.md`，
      防复发纪律写入 AGENTS.md）。

## Blocked

- [ ] H4（Windows NVIDIA / CUDA）= `H4_GPU_RUNNER_UNAVAILABLE` —— 无可用 Windows GPU runner，
      需用户提供 NVIDIA 环境与计费权限（见 `.agent/STATE.md` H4-0 记录）。
