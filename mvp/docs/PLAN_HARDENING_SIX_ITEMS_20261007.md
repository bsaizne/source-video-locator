# PLAN — 六项立项工作清单（2026-10-07 用户拍板，先入文档后动码）

> **范围**：低内存收缩 batch+预取 / 子进程设备回报标记 / 阶段进度防抖+心跳 /
> 独立 GPU 工作进程监督 / 「指标 HIT ≠ 导出实得」口径收口 / 「换形态重试」探针族（4 条）。
> **性质**：①~④ 为工程项（可带单测验收），⑤ 为口径项（改文档与评估口径，不改结果），
> ⑥ 为研究探针族（沙盒纪律：零 runtime，探针 PASS 才接线）。
> **证据源**：竞品形态 = `competitor_cutmatch/FINDINGS_CUTMATCH_ENTRY_LAYER_20261006.md`
> §2（entry view 行号可回查）；我方缺陷登记 = `.agent/STATE.md` Known Issues。

---

## ① 低内存收缩 batch+预取

- **作用**：小内存机器能跑完整分析且不 OOM；降档时用户可见（非静默变慢）。
- **竞品形态**（entry view:372-393）：按可用内存同时收缩 `memory_batch_size` 与
  `max_prefetch_batches`（varname 链 `requested→raw_frame_bytes→estimated_per_frame→reserve→usable`），
  读 `GlobalMemoryStatusEx`/`SC_PHYS_PAGES`；`low_memory_mode`+`fallback_stage` 作为**状态字段上报**。
- **我方现状**：`DeviceConfig.dml_batch_size=1` 固定；ISC L2 建表批量与抓帧预取无内存感知；
  进度/设备接口无低内存档字段。
- **实施要点**：新增 `media/resource_budget.py`（可用内存 → batch/预取/档位，纯函数可测）；
  接线 L2 建表批量与 `_grab_frames_parallel` 预取深度；`/api/settings/device` 与进度事件补
  `low_memory_mode`/`fallback_stage` 字段。
- **验收**：注入 `available_bytes`（依赖注入，不真压内存）单测覆盖收缩曲线；
  不触发降档时四片计划层零语义；后端全套 + API 全套全绿。
- **边界**：不动定位语义；Windows 优先（GlobalMemoryStatusEx），psutil 兜底。

## ② 子进程设备回报标记

- **作用**：修 UI-P3 徽标误标的**根因**——UI 显示配置意图；改为显示真正干活的设备实际值。
- **竞品形态**（view:366-368, 275, 463）：子进程打 `\x1eCUTMATCH_DEVICE_CONFIRM=...\x1e`
  标记行，主进程解析后映射厂商（cuda/nvenc→nvidia · amf→amd · mps→apple · software→cpu）。
- **我方现状**：单进程 backend；`resolve_backend` 已探测实际设备，`GET /api/settings/device`
  已返回 `actual_device_name/actual_device_type/fallback`——**后端数据已对，UI 没接**。
- **实施要点**：UI 侧栏/项目卡徽标改读 `/api/settings/device` 的 actual 三元组（带缓存 +
  未连接态）；backend stdout 增打一行 `BACKEND_DEVICE=<actual>`（与 BACKEND_LISTEN 同机制），
  供 headless 验收与日志取证；厂商映射表同竞品。
- **验收**：dev + 打包态徽标 = actual 值（DirectML 机显示 amd/directml）；无后端显示未连接；
  vitest + 双 typecheck 绿。

## ③ 阶段进度防抖 + 心跳

- **作用**：消除"92% 卡死了吗"的观感——快阶段不闪跳，慢阶段有活着的心跳。
- **竞品形态**（view:872, 905, 937-946, 768, 928）：`_make_stage_delay_progress_callback`
  对短阶段延迟发布；`heartbeat` + `progress_updated_at` 证明在动。
- **我方现状**：续61 补二已把 REFINE 92→98 切四段、计时移进 store；但无防抖、无心跳字段。
- **实施要点**：进度发布层加最小展示时长（stage_delay，纯发布层不碰阶段语义）；
  `Task` 状态补 `last_event_at`（心跳=轮询响应自带）；UI 对 <阈值 进度跳变做平滑。
- **验收**：合成快/慢阶段单测（防抖不丢尾帧、心跳字段存在）；现有进度序列回归锁更新；
  后端全套 + vitest 绿。

## ④ 独立 GPU 工作进程监督

- **作用**：DML 段错误/驱动崩溃不再拖垮整个后端——崩了只损失单个任务，服务与其它任务存活。
- **背景**：本机实测 DML 多模型并发段错误（续6/续43 两次教训）；当前单进程，一崩全崩。
- **竞品形态**：独立 GPU 工作进程 + 监督（无细节，仅存在性证据）。
- **实施要点（分两步走）**：
  1. **任务级进程隔离**（最小可行）：`TaskManager` 的 analyze/render 任务改跑独立子进程
     （spawn + 结果/进度经队列回传），子进程崩溃 → 任务标 failed（带退出码），主服务存活；
  2. **监督重启**：连续崩溃计数 + 冷却，超过阈值提示用户（不无限重启）。
- **风险与边界**：帧数据/结果跨进程序列化开销（bytes 化，避免 pickle 大对象）；
  索引/嵌入缓存仍在主进程共享层（文件层，天然跨进程）；取消传播经管道。
  先做隔离不做推理级拆分（不把单次 forward 拆出去——那是另一量级）。
- **验收**：注入 `faulthandler`/abort 的假任务验证主服务存活与错误上报；既有任务测试全绿。

## ⑤ 「指标 HIT ≠ 导出实得」口径收口

- **作用**：让对外承诺的精度数字 = 用户在导出工程里**真正拿到**的段数，消除
  "指标 136、实得 131"的承诺-体感差。
- **现状**：并列口径 `main_hit` 已落地、LOC-2003 导出告警已落地（含子 span 覆盖的 23 条
  已有告警提示）；**剩最后一步 = 验收锚点线从「严格」改用「导出实得」（主 span 口径）**。
- **实施要点**：`measure_four_results.py` 把导出实得升为主报告指标（严格/场景保留为诊断口径）；
  `PRODUCT_INTRO` 对外数字与话术同步（数字会"降"约 5 条，需一并拍板对外表述——
  与搁置中的「性能口径三处对齐」联动处理）；GT 文档标注口径代际。
- **验收**：四片重计逐字段不变（只改读数口径）；档案/文档三处口径一致。
- **边界**：不改 GT、不改定位语义、不 bump feature_version。

## ⑥ 「换形态重试」探针族（4 条，沙盒纪律）

> 共同特点：信息有价值、当年移植载体选错；**全部探针级零 runtime，PASS 才立项接线**；
> 章程纪律 = 先影响面统计，门槛 = 三指标零回退 + 口袋救回 ≥1/3。

| # | 条目 | 当年载体 | 换形态 | 判别集 |
|---|---|---|---|---|
| a | 置信非饱和第二信号 | 竞品三项加权（margin/coarse/consistency 恒饱和） | 用非饱和量替换三输入（次优差、簇独立证据数、检索 rank 分布） | 口袋 8 条 + 自信错点名 t1r30a/t2r04a |
| b | 两级采样（粗筛+密验） | 从未实跑 | 索引 0.5fps 粗筛 + 命中邻域密验检索 | stride2 139/139 既有数据为起点 |
| c | E3 几何验证换载体 | 仿射 RANSAC 作主判据（判负） | patch 稠密对应只作**锚点级验证器/排序特征** | 兄弟机位族（p08 等） |
| d | 退化门换判据 | `min_scene_coverage`（整段清空判负） | 用"该候选窗该不该留"的量（独立证据数/support） | test2 承重 6 行（cover 0.00~0.19） |

---

## 建议执行顺序（供拍板，非既定）

1. **小三件一批**：② 设备回报（最小）→ ① 低内存收缩 → ③ 防抖+心跳（纯增量，零定位语义）；
2. **④ 独立进程监督**单独一批（基础设施，风险最高，先行任务级隔离）；
3. **⑤ 口径收口**一批（纯文档+评估口径，建议与搁置的「性能口径三处对齐」同批处理对外数字）；
4. **⑥ 探针族**研究线并行（沙盒，不占产品批次）。

每批完成后按惯例：后端全套 + API 全套（涉 UI 加 vitest/双 typecheck）→ 档案 → 提交等口令。
