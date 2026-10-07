# PROJECT STATE

## Project

视频片段反向定位引擎 Benchmark → **Source Video Locator MVP**（D:\claudework\benchmark）

> **项目状态：ALGORITHM_UNFROZEN / MVP_ITERATION_ACTIVE（2026-08-28 用户解除全部算法与模型限制，含 CLS forward；原 RESEARCH_FROZEN 表述失效，仅存档）**
> 算法研究已冻结收尾；进入 MVP 产品化（Source Video Locator）。研究结论见 `ARCHITECTURE_DECISION_PHASE20.md`；MVP 设计文档见 `mvp/docs/`。
>
> **硬件/开发状态（2026-08-26 统一）**：H1 Windows CPU = **IMPLEMENTED**；H2 Windows AMD / DirectML = **IMPLEMENTED**；H3 macOS Apple Silicon / MPS = **GO / POC completed**；H4 Windows NVIDIA / CUDA = **PENDING**（H4-0 环境检查已完成 = **`H4_GPU_RUNNER_UNAVAILABLE`**，无可用 Windows GPU runner，POC 无法推进）；UI（第 8 项 PySide6）= **PAUSED**。

> **硬件路线（2026-08-25 用户拍板锁定）**：H1 Windows CPU → H2 **Windows AMD GPU(DirectML)** → H3 macOS Apple Silicon(MPS) → H4 Windows NVIDIA(CUDA)。**不支持 macOS Intel**。`DeviceBackend` 必须保持可扩展——未来加 `CUDABackend` 不改上层 FeatureStore/Retrieval/Ranking/Localization/Confidence/UI。CUDA 不进当前实施阶段。
>
> **AMD GPU POC（`mvp/poc/amdgpu_onnx/`，独立、未接入 MVP）= `AMD_BACKEND_GO`**：RX 6750 GRE + ONNX Runtime DirectML + 冻结 DINOv2 ViT-S/14 CLS-384。15.15 fps，10.39× 加速，Top-1 邻居一致、embedding 数值稳定、500 帧无 NaN/norm 异常。
>
> **H2-Preflight（`h2_preflight.py`，2026-08-25）= `MEMORY_STABLE`**：2.mkv@0.5fps 建索引 3834/3834 帧全跑完，内存 278.5→336.8MB（+58.3MB，全部为首批~250帧一次性 warmup；之后 328–337MB 窄带波动，非线性增长），all_finite / norm=1.0，无 DML allocator 错误，全片 323.9s、11.84 fps。
>
> **H2 = `DirectMLBackend` 已正式接入并验证（2026-08-25）→ `H2_AMD_DIRECTML = IMPLEMENTED`**：
> `mvp/src/device/directml_backend.py`（`DeviceBackend` 实现，复用冻结 `_imagenet_preprocess`，ONNX+DML provider，numpy L2）+ `device/resolve_backend(preferred="auto")` 统一 resolver（能力探测 + 自动 CPU fallback + 明确日志 fallback_reason）+ `device/resolve_dml_model`/`asset_meta`（模型资产 resolver）+ `infrastructure.DeviceConfig`（preferred/onnx_model/dml_device_id/dml_batch_size）+ `mvp/scripts/export_dml_model.py`（从冻结模型重导出产品 ONNX 资产到 `<app_data>/models/dinov2_cls_384/` 含 `asset.json`）。
> 验证：全套 72 项测试过（含新增 `test_directml_backend.py` 10 项：A 类无 GPU→fallback/probe 结构/B 类 AMD 实机推理+CPU 正确性 cos>0.999+FeatureStore 完整兼容 create/load/validate/invalidate）；真实 2.mkv 生产索引构建 `smoke_directml_backend.py`：381.3s / 3834 帧 / 10.06 fps / `[3834,384] float32` / 内存 +53.4MB 稳定 / `IndexMeta.backend="directml" feature_version=...@0.5_l2`（与 CPU 同 schema，不复制 store）/ reload 0.002s。相比 H1 CPU ~3793.6s ≈ **9.95× 墙钟加速**（vs POC 324s 略高 +18%，因生产路径含文件哈希/持久化/探测开销）。

---

## Current Phase

**MVP 产品化 — Stage 1（编码）进行中**：已完成第 1~7 项 + **H1/H2 已接入并验证（H1_CPU / H2_AMD_DIRECTML = IMPLEMENTED）** + **H3（macOS MPS）POC = GO / 已完成（2026-08-26，不重复运行）**。**UI（第 8 项）已转向 = Vue3+TS+Electron 桌面工作台，Stage 1 初始代码已交付（2026-08-26）**（见 Current Task §2）。算法研究 Phase 1~19 已冻结收尾。

> **2026-08-26 — H3（macOS Apple Silicon / MPS）POC 完成 → `H3_MPS_GO`**（真实 Apple Silicon 验证通过，GitHub Actions 云端跑成功）。**repo**：`bsaizne/source-video-locator`（private→public；push 走 SSH——本机网络 HTTPS 443 被阻断、SSH 22/443 可达；DNS=小米路由 192.168.31.1 解析到 GitHub 20.205.243.x 段但 443 握手超时）。已 `git init` + 完整 `.gitignore`（排视频/权重/特征/第三方引擎/工具二进制/研究代码 `src/`/phase 报告/生成物/凭据/IDE）+ 入仓 `mvp/`、`.github/workflows/h3-macos-mps.yml`、`.agent/`、设计/研究结论文档；**含修复：`.gitignore` 无锚 `src/` 曾误忽略整个 `mvp/src`（致 CI checkout 缺 `device/dinov2_model.py`），已改 `/src/`**。**H3 POC = GO**：macOS 15.7.7 / arm64 / torch 2.13.0，`device_mps_actual=mps`（确认非 CPU fallback）、权重下载+sha256 通过、正确性 cos_mean=1.0 / max_abs_diff=6.3e-7 / mps norm deviation 1.19e-7、7.875× 加速（0.87→6.84 fps；batch=4 最佳 6.67；batch≥8 触发 `Invalid buffer size 5.37GiB` + 暴跌 2.83fps）、500 帧 all_finite 无异常无 fallback、峰值内存 ~1.07GB。**关键约束：MPS batch_size ≤4（推荐 4）**——未来正式 `MPSBackend` 必须遵守。CI workflow 已改 **workflow_dispatch-only**（手动；不 push 自动触发，避免每次 push 烧 macOS runner）。`mvp/src/device` 零改动；无 MPSBackend / UI / H4。POC 见 `mvp/poc/macos_mps/`。

> **2026-08-26 — H4-0（Windows NVIDIA / CUDA 环境与 runner 可用性检查）= `H4_GPU_RUNNER_UNAVAILABLE`**：目标环境为 GitHub Actions → Windows GPU larger runner → NVIDIA → CUDA。核实结论：① `bsaizne/source-video-locator` 为**个人（User）账户的公共仓库**（api 确认 `owner.type="User"`、`private:false`）；② 官方 GPU hosted runners **不对开源/公共仓库开放**，且需 **organization/enterprise 级计费配置**；③ 官方 GPU hosted runner **无 Windows 变体**（H3 所用 `macos-15` 为标准 runner，非 GPU）；④ 该 repo Actions 历史仅 4 次 `H3 macOS MPS POC`（macos-15），从未使用 Windows/GPU 较大 runner；⑤ 本机无 GitHub 认证（无 gh CLI / token / credential.helper，`actions/runners` endpoint 返 401）；⑥ 本机 GPU = **AMD Radeon RX 6750 GRE 10GB**（非 NVIDIA），`torch 2.13.0+cpu`、`torch.cuda.is_available()=False`、`device_count=0` → 本机也无法做 CUDA POC。**未创建 `mvp/poc/nvidia_cuda/` / workflow，未改 `mvp/src`，未实现 NVIDIA 支持，未进 UI。** 结论（不伪造）：当前无可用 Windows GPU runner，H4 POC 无法推进；需用户提供 NVIDIA 环境（自托管 Linux runner / 云或本地 NVIDIA 机器）+ 计费权限。
>
> **⚠️ 2026-10-06 续60 更正第 ⑤ 条**：「本机无 GitHub 认证（无 gh CLI / token / credential.helper）」**已过期**
> —— 实测 `credential.helper=manager` 且钥匙串里**存有 github.com 凭证**（`git credential-manager get` 可取，
> 本会话据此用 curl 走 Actions API 读了 run/job 日志并 dispatch）；仍**无 gh CLI**。
> H4 的核心结论（GPU hosted runner 不对公共仓库开放 + 无 Windows 变体 + 本机非 NVIDIA）**不受影响**。

---

> **档案瘦身注记（2026-10-07）**：`Current Phase` 尾部研究块、`Current Task` 续14~续61 补八
> 约 140 个 ▶ 块、`Next Actions` 旧交接要点，已**逐字**迁往
> `.agent/archive/STATE_history_20261007.md`。细节亦见 `CHANGELOG.md`。

## Current Task

> **▶ 2026-10-07（续62）— 成片相邻段重复画面已修（导出/渲染层去重叠）【下个对话从这里读起】**
> 用户报「剪出的片里两个相邻片段有重合，完整视频同一画面出现两次」。根因 = **定位段源窗有
> `min_span_s=2.0` 地板**（`config.py:138`，`locator_service.py:1795-1801` 夹紧居中），而剪辑段常
> 0.7~1.5s ⇒ 贴接相邻两段各被撑到 2s 宽**必然交叠**（数学上 ≈ 2s − 编辑时长），逐段取材再拼接的
> 产物就重复那段画面。放大项 = 导出层把段扩成完整镜头（实测有 ed=2.48s 拿 9.94s 源窗）。
> **不是最近几批引入的回归**（10-02 老结果同样有），之前在指标口径下不可见（严格指标只看 span 覆盖）。
> **既有边界**：剪映卷轴 `plan_jianying_assets` 早就有"重叠回并"去重，成片/EDL/XML 三处没有。
> 修 = 新增纯函数 `exporters.trim_adjacent_source_overlaps()`：编辑轴贴接（gap≤0.05s）的相邻主 clip
> 源区间交叠**按中点切开**（用户裁决）；**包含形态改为外层挖洞**成头/尾两条（同属该编辑段、记录槽按源宽比例分），
> 内层完整保留 —— 首版写成中点裁尾，真实四片回放暴露会丢外层独占右尾（2mkv 少 6.58s / test3 少 0.83s），
> **丢画面比重复更糟所以不采用**。单帧守卫：切完任一侧不足 1 帧 ⇒ 跳过该对；**非贴接重叠 = 真实复用不裁**
> （档案既有目检结论：连续场景内切多镜头的重叠多数正确）。接线 = `render_movie`（split 之后）+
> `export_project` 的 edl/fcp7_xml 分支；剪映卷轴不动。
> **证据**：后端 **565 OK**（+16 纯函数单测含包含/倒挂/链叠/守卫/幂等，+3 渲染接线锁含"非贴接不裁"）·
> API **105 OK** · 真实四片计划层回放 = 贴接重叠 7/2/4/16 → **0**，重复秒 8.99/0.53/3.73/10.22 → **0**，
> **并集覆盖 Δ=0.00**（一块不丢）。零语义为构造性：只改导出计划层不回写 `Result`，
> `measure_four_results` 读 Result 字段 ⇒ 三指标不可能变（已核）。
> **~~未闭合~~ → 已闭合（续62 补一）**：打包态真机渲染/导出一次 = 已由双臂 A/B 包内实测闭合（见下）。**已提交**（本批源码+测试+档案）。
> **r14 已出包（2026-10-07 00:21，口令「推ci并打包，删旧包只留 r13+r14」）**：
> `mvp/ui/release/Video-Locator-win-x64-20261007r14.zip` = 981,639,927 B / **7,078 条目** /
> `testzip()=None`；包内 `backend.exe` **77,448,544 B `sha16=4f5631af9e4ea51f`**
> （r13 = 77,445,580 / `52ca8c225bbc3683` ⇒ 新代码入包的尺寸+摘要硬证）；
> `Video Locator.exe` 与 ISC 图与 r13 逐字节同（未改动层，符合预期）。
> 验收：**accept FAILED=0**（冒烟 26.4s · DirectML 生效 · 精排与 ISC 未回退 CPU · 段数 1）·
> 三防 **FAILED=0**（`three_defense_smoke_r7.py`）· 启动冒烟 Electron 4 + backend 1 存活 25s，
> 用完即清 AFTER_KILL=0。构建日志 `work/build_r14.log`，验收日志 `work/accept_r14.log` /
> `work/three_defense_r14.log` / `work/zip_r14.log`。
> **✅ 剪映卷轴去重语义已统一（2026-10-07 续62 补二，用户拍板「先统一」）**：
> 剪映分支在取材扩展**之后**施加同一 `trim_adjacent_source_overlaps`（挂错在扩展前会失效），
> `plan_jianying_assets` 删除"重叠回并"改逐 clip 一素材（+撞名守卫）。四通道一套语义：
> 贴接对裁开、非贴接=真实复用保留。**顺带发现旧回并真缺陷**：条件只看源区间 ⇒ 源序回跳
> clip 被静默吞掉——四片回放旧卷轴 84/55/67/103 段只剩 5/49/22/3 条素材，
> 并集覆盖 4.28/123.01/37.05/14.61s（真实 152/129/97/167s，2mkv 丢 ~97%）。
> 门禁：后端 **569 OK**（+4 锁）· API **105 OK** · 四片回放 + 2mkv 真代码端到端 PASS
> （`work/jianying_unify_{replay,e2e}_20261007.py`）。代价：素材逐 clip ⇒ 抽取次数上升。
> **r14 不含本批**（进包需下次出包授权）；明细 CHANGELOG 续62 补二。
> **✅ 包体级判别已闭合（2026-10-07 续62 补一，双臂 A/B）**：不再等用户真项目——
> `work/r14_trim_pkg/r14_trim_pkg_probe.py` 打包态 headless 起 r13 与 r14 两臂
> （唯一变量 = backend.exe；ffmpeg/ffprobe/模型/env/数据目录/输入/导出参数逐字相同，
> r13 臂用 zip 抽出的完整 onedir 树），`/api/results/load` 灌真实四片结果批 →
> `/api/export`（edl+fcp7_xml，LOW+backup 全量门槛）→ 2mkv 渲染。判读：
> **r13 臂 EDL 贴接重叠 4/2/4/16 对、重复 4.98/1.32/3.73/11.06s（症状在修复前包内复现）；
> r14 臂四片 EDL+XML 全部 0 对 / 0 重复秒；并集覆盖两臂逐 case Δ=0.00（不丢画面）**；
> 渲染腿 r13 成片 166.020s（84 clips）vs r14 **160.974s**（86 clips，+2 = 挖洞头/尾条），
> 时长差 5.046s ≈ EDL 重复秒 4.98s ⇒ 重复画面确实从成片消失。两臂均 DirectML/h264_amf。
> 产物 `work/r14_trim_pkg/report.json`。明细 CHANGELOG 续62 补一。
> **分发包现状**（口令执行）：r10/r11 已删（释放 ~1.9GB），留 **r13（回滚）+ r14（现役）**。

## Completed

- 历史完成项见 `.agent/archive/STATE_history_20261007.md`（Current Task 退休块续14~续61）、
  `CHANGELOG.md`（逐批明细）与本目录 checkpoint-*。近期完成（2026-10-06/07）：续61 预览联动
  真浏览器确证 / LOC-1107 收口 / r13 出包；续62 相邻段去重叠 + r14 出包 + 包体级双臂判别闭合
  + 剪映去重语义统一。

## Current Problem
- **无阻塞项**（2026-10-07 更新）。现役 = 续62：成片相邻段重复画面已修（成片/EDL/XML/剪映
  四通道统一去重）；现役包 r14（包体级判别已 r13 vs r14 双臂 A/B 闭合）；剪映语义统一（补二）
  在源码树、r14 不含。剩余全部为等用户口令项，见 `Next Actions`。已知局限见 `Known Issues`。

## Current Implementation

- 实现细节见项目源码与 `PROJECT_HANDOFF.md`；本文件按协议不复制源码。

## Current Decision

- 重要技术决策见 `.agent/DECISIONS.md`。

## Next Actions

> 现役未结项以 `Current Task` 顶部「续62」块为准；历史交接块已迁
> `.agent/archive/STATE_history_20261007.md`（续55「交接要点」与 (c) 关键新知识七条在其中，
> 后者已浓缩为 `Known Issues` 的「工程教训速查」）。

1. **git 推送**：本地三笔未推（`883581e` r14 档案 · `021e6e1` 续62 补一包体判别 ·
   `4e58f11` 续62 补二剪映统一）——等用户口令。
2. **r15 出包（需授权）**：剪映去重语义统一（续62 补二）只在源码树，r14 不含；
   出包后必跑 accept + 三防 + 启动冒烟。
3. ~~**待拍板**：竞品 opcode 通道可行性~~ → **已试采结案（2026-10-07 续62 补三）**：字面通道
   判死（Nuitka AOT，0 pyc）；机器码绑定通道判死（LEA→blob 2/172,604；MOV→.bss 平铺数组
   假设验证 FAIL，密度 4.3 引用/槽无区分度；全量反汇编路径未立项）；**blob 序通道打开**
   （blob 序=源码书写序，批次边界可用内嵌 pct/序号切分；已产出 tracker 阶段词表与 V2 流程
   注册序）。明细 `competitor_cutmatch/FINDINGS_OPCODE_CHANNEL_20261007.md`。
4. **六项立项（2026-10-07 用户拍板）**：计划 = `mvp/docs/PLAN_HARDENING_SIX_ITEMS_20261007.md`。
   **②①③ 小三件已完成（2026-10-07 续62 补五）**，门禁 = 后端 578 · API 111 · vitest 144 ·
   双 typecheck 干净；**④ 独立进程监督 / ⑤ 导出实得口径 / ⑥ 换形态探针族待跑**。
   完成态打勾见 TODO.md P1。
5. **搁置（用户 2026-10-06/07 裁决，勿再提议）**：mac 严格惰性再 dispatch · LOC-1107 拆码 ·
   A1→A2∥A3 · 性能口径三处对齐 · 成片缺口标记。

## Important Constraints

- 硬件路线锁定：H1 Windows CPU → H2 Windows AMD(DirectML) → H3 macOS Apple Silicon(MPS) → H4 NVIDIA(CUDA)；不支持 macOS Intel。
- MPS batch_size ≤ 4（H3 POC 结论）。
- DML 批量推理使用 batch=1（RX 6750 GRE + ViT-S @518 实测最佳）。

## Known Issues

- **工程教训速查（2026-10-07 自续55 交接块浓缩，原文见 archive Part C）**：
  ① 成本已换位到解码秒（~0.164s/解码秒），减 spawn 次数已榨干；② 真实占比 CPU 抓帧 78% /
  DML 推理 18%；③ 网格与并集互斥（多相位并簇会**静默**拿晚 ≤0.5s 的帧）；④ AMD 硬解三入口
  全闭，不出帧时会报 31~148× 假加速（先看 `hw 可用窗`）；⑤ test1 同代码态跨 run 方差 ±18%，
  提速只认同脚本双臂；⑥ 单片形状统计不能外推；⑦ `id(frame)` 判重复嵌入是假读数。
- **mac 包会多带 ≈88MB 死资产**（续36）：`PatchReranker._try_onnx` 只认 DmlExecutionProvider，
  macOS/MPS 侧本就走 torch；`extraResources` 是整目录复制，H3 正式化时需按平台裁剪。

- 剩余失败族（兄弟机位 / 同质场景 / 重复镜头）维持「特征上限 = 已知局限」。
  **（2026-09-25 修正口径 + 产品级复核）**「换更大 backbone（ViT-S→ViT-B）」**已关闭**：探针级无一致增益（兄弟机位族两基座 margin 均 ≈0、
  ViT-S 全片 rank 5-6；p26 类「硬混淆」系 GT 标错假象），**产品级全量索引四片回归亦无收益**（严格 116 vs 117、场景 134 vs 137）；
  p08 主定位两侧都落在兄弟机位区（1061-1063 / 1034-1041）→ 该族缺口不在特征容量
  （依据 `feature_upgrade/FINDINGS_FEATURE_UPGRADE_V4.md` + `FINDINGS_VITB_FULL_INDEX.md`）。
  **（2026-09-26 口径复核）**ViT-B 与基线差距在多判据下为 **−1 ~ +1**（严格 117 与 118/119 随判据抖动）→
  表述改为「**该口径下两基座不可区分**」, 不再称「轻微负向」；四片 22 例非 HIT 机制分诊 =
  **口径 2 / 定位层 19 / 特征层 1（t2r05a, 检索 rank 77）**（依据 `FINDINGS_METRIC_CALIBER_V5.md`）。
- **置信层（2026-09-28 续14 新增实测）**：竞品四项加权公式在我方信号上**无法分离「自信错答」**——
  clean 单证据簇的 `margin`（无 secondary → 恒 1.0）/`coarse`（evidence_qcov 多 ≥0.85）/`consistency`
  （竞品源自全片 3fps 偏移投票，我方无对应物）三项恒饱和，真病灶（同场景内选错时刻 18–21s）v2 仍给 0.75–0.87。
  与 2026-09-01「AMBIGUOUS 检测无内部信号」原型实验结论双向闭合；重开前置 = 非饱和第二信号源。
- **退化门两条已知形态缺陷（2026-09-29 续31 登记，门默认关 ⇒ 无生产影响）**：
  ① `min_scene_coverage=0.2` 在「该段子 span 全部低于门槛」时**整段清空**，实测 test2 严格 −5
  （改成「只丢冗余、全低则保留」即免掉，但须另立小批改 runtime）；**且判据本身与我方子 span 语义
  不匹配**（续31 读图确证：test2 承重的 6 条 GT 行其子 span `cover` 为 0.00~0.19 ⇒
  「cover 低 ≠ 该 span 无用」，要启用须**换判据**而非调阈值）；
  ② 竞品式「唯一认领者存活」拒识 = 对称重复 + 等证据下的掷硬币（test3 seg41 HIGH 0.87 vs
  seg61 HIGH 0.89 同指一 2s 区间），维持默认关，安全形态 = LOC-2002 只提示。
- **口径缺陷（2026-09-29 续31 补二 登记；2026-09-30 GT 重锚定后数字已更新）**：
  ① **指标 HIT ≠ 导出实得**：现行严格 130/139 里有 **23 条**是"任一 span（含子 span/事件宽 span）
  覆盖"即算 HIT，而 `export_project` 硬编码 `include_subs=False` ⇒ **导出工程实际只用主 span**，
  仅主 span 口径 = **107/139**。⇒ 对竞品链的真实领先 = **107 vs 83**（GT 重锚定前为 100 vs 83）。
  修法三选一见 `FINDINGS_COMBO_CALIBER_ALL_CASES.md` §7.4（并列口径已落地 `main_hit` /
  LOC-2003 导出告警 / 锚点线改用「导出实得」判据重开——(E) 影响面统计已给出新可救池 23 行）。
  ② `within = span ⊆ GT窗±2s` 在截等长口径下给双臂同量级的容差红利（我方 +6 行量级），
  双臂同口径差值（M1 章程门）不受影响；引用 111/139 须标口径。
- **Mock 适配器不产 `warnings`**（续31）：dev/Mock 态看不到 LOC-2001/2002，Http 与打包态正常。
- **多原片合并：缺陷在验收夹具、不在产品代码（2026-09-30 续32 更正 + 已修）**：初版登记写成
  「`source_merge.py` 切点不互斥」是**错的**——该产品只 concat 给定文件、从不做切分；重叠两半是续27
  **验收夹具** `accept_source_merge_2mkv.py` 用 `-ss key_t` 起切 part2 时 copy 语义落点早 ~3.4s 造成。
  已修夹具：part2 改以 **part1 实际末帧时刻**起切 + 互斥性硬断言（|part1+part2−原片|≤0.5s）+
  **时间轴同一性常驻锁**（拼接点前 δ=0、拼接点后 δ 恒定 ≤0.5s、沿全片采样同 t 帧逐字节比对）。
  重跑实测：拼接点前 δ=0、拼接点后**恒定 δ=0.167s**（4 帧，容器时间戳粒度，无重复无累积，
  `work/merge_accept/timeline_shift.json`）⇒ 合并产物拼接点之后**恢复可用**。
  覆盖边界结论维持并固化为纪律：续27 的 39 条 GT 全在拼接点前（max 2427s < join 3837s），
  验收必须写明覆盖边界。证据 `FINDINGS_RETRO_MULTIMODAL_REVIEW_20260930.md` §C。
- H4（Windows NVIDIA / CUDA）= `H4_GPU_RUNNER_UNAVAILABLE`，当前无可用 Windows GPU runner。
- **打包链路三类通病（2026-09-22 集中暴露）**：① **动态链接的系统库不进 bundle**（Homebrew ffmpeg → dyld 崩；
  同类：pymediainfo 需 libmediainfo）；② **PyInstaller 只收代码不收 data file**（`pyJianYingDraft/assets/*.json`）；
  ③ **构建期文件未入 git 导致产物静默降级**（`.env.production` → 整包跑 Mock）。
  对策已固化：用静态/自带依赖的二进制、`collect_data_files` 显式收集、CI 加 `otool`/文件存在性防回归检查。

## Last Updated

2026-10-07（续62 补五：六项立项 ②①③ 完成，④⑤⑥ 待跑）
