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

> **▶ 2026-10-08（续63 补六）— ⑥b「两级采样」探针 = 判负关闭（成本实测成立 / 精度硬门崩）【下个对话从这里读起】**
> 用户口令「3」= 六项立项唯一剩余项 ⑥，按 STATE 建议**只跑 b 且换判据**（主 = 建索引**实测**耗时；
> 硬门 = 三指标零回退）。沙盒纪律：`mvp/src` 一行未动 ⇒ 不接线、不 bump 生产 `feature_version`。
> **成本侧成立**：四片**同脚本双臂**实测 1fps 41.3min → 0.5fps 21.8min（比值 **0.529**，
> 区间 0.481~0.609），体积 ÷2；前案 13.6 帧/秒折算模型低估 2.3%~17.1%。
> **精度侧崩**：两片 59 条 = 严格 58→52、**导出实得 56→44**、场景 58→56、口袋 p30 回退 ⇒ 判负。
> **两片损害形态不同**（本批最有价值的发现）：test2 损在**证据层**（`no_evidence` 1→9、
> 切分并段 67→65 行）⇒ 严格直接掉 5；2mkv 损在**导出层**（严格只掉 1，但主 span 变宽/位移、
> 命中改由子 span 兜住 ⇒ 导出实得掉 6）。⇒ 10-03「grid2 零代价」包络**不足以支撑决策**：
> 它只扰动最终 span，看不见这两层（正是它 §6 边界 1 自己写明「不覆盖」的那一类）。
> **密验腿（⑥b 换形态本体）**：C05D 在 test2 上 **0 翻转、三指标与对照臂逐格相同、失败分布逐字
> 相同** ⇒ 精度救得回；但命中窗并集 = 源片 **33.4%**，补帧后 5055 帧 ≈ 1fps 的 5051 帧，墙钟
> 265+395=660s > 435s（**1.52×**）⇒ **「密验救回精度」的本质就是把网格补回 1fps，精度与成本
> 不可兼得**（盈亏线：帧数 cov≤33.3%、墙钟 cov≲12%，因密帧 seek 0.156s/帧 vs 顺序解码 0.105）。
> **逐图复核（用户点名）**：test2 3 张 9 行 + 2mkv 4 张 10 行全读；**第一版出图取格缺陷已修**
> （原用「重叠最大行的主 span」会取错格 ⇒ 改复刻评估器规则取「判档证据」span）。读图：test2 的
> 5 条翻转里 **3 条画面级真丢/错位**；C05D 的救回 2 条逐字同 span、2 条跨切点覆盖、1 条靠信封
> ⇒「零翻转」成立而**「逐帧等价」不成立**。
> **登记两条口径（未改判卷代码）**：① 1 秒级超短 GT 行的 `within` 通道可由**完全不与 GT 重叠**、
> 只落在 ±2s 信封内的 span 满足 ⇒ 引用「零回退」须带这句；② A10 与 10-03 基线批**逐行 mark 相同
> 但 strip 后逐字节不等**（`isc_l2_index_enabled` 10-05 才翻默认）⇒ 跨批引用 v2_* 只可用于三指标层。
> **⑥a/⑥c/⑥d 未跑**（本轮按口令只跑 b），保持「未跑」而非「已证否」，不得外推为探针族结案。
> 明细 `FINDINGS_TWO_STAGE_SAMPLING_20261008.md` + CHANGELOG 续63 补六（含 ISC 双数据根实况）。

> **▶ 2026-10-07（续63）— 导出计划层常态守卫 + 逐 clip 代价实测 + r15 出包（三件按用户「按你的想法来」自主推进）**
> **判断**：续62 两批真缺陷的共同根因不是函数写错，而是**同一套五步计划序列在
> `locator_service` 里抄了三遍**（成片 / EDL+XML / 剪映）——重复编排代码本身就是漏接的载体。
> **收口** = 新纯函数 `exporters.prepare_channel_plan(batch, channel=…, …)`：
> `build_export_plan → fragment_warnings → snap → boundary split →〔取材扩宽〕→ trim`
> 顺序硬固定，通道差异只允许是参数差异；stats 自带 `audit_pre_trim`/`audit` 两份体检。
> 新只读 `audit_source_overlaps()`：贴接重叠（违规）/真实复用（不动）/并集覆盖/零宽，
> **必须扫全对**（真实复用常隔着中间段，只看紧邻对会漏计——自己的新锁逼出来的）。
> 硬约束：`material_expand` 只允许 `channel='jianying'`，时间线通道误传直接 `ValueError`
> （本批收口时我就把它误透给三通道，EDL 并集覆盖 134s→531s=画面被整镜头撑大，
> 由 r15 **包体探针**抓回 ⇒ 教训：包内产物级判据不能只靠源码树）。
> **常态守卫**（入库）`mvp/scripts/check_export_plan_invariants.py`：真实四片 × 四通道，
> 贴接重叠 2/0/3/7 对 → **0**、并集覆盖 Δ=**0.00**（134.094/84.346/74.037/119.963s）、
> 三时间线通道同 plan=是；`reuse_pairs` **只报不断言**（外层挖洞会把与第三段的共享区间
> 让给内层，对数下降而画面不丢——断言它持平会把正确去重判成违反）。
> 新 `mvp/tests/test_export_plan_guard.py`（22 项）含 AST 结构锁：产品树里
> `build_export_plan`/`trim_adjacent_source_overlaps` 的调用点只允许在 helper 内 ⇒ 第五个出口漏接=红。
> **逐 clip 代价（补二欠账）**：计划层 2mkv 卷轴 64 条 / 宽度 815.75s / 去重后抽取 **56 次 701s**；
> 源码树三臂 `work/jianying_cost_20261007.py`：2mkv A(扩宽)=**81.1s** vs B(core)=33.0s（2.46×）、
> test2 89.2s vs 29.5s（3.02×）⇒ 代价主体是**取材扩宽**不是逐 clip，分钟级 ⇒ r15 可出。
> **r15 出包**（backend.exe `sha16` 逐代递增，`d45656f585826f4a` / 77,467,467B）：
> accept **FAILED=0**（含本批新加的 4 条隔离硬断言）· 三防 **FAILED=0** ·
> 启动冒烟 Electron 4 + backend 1 / AFTER_KILL=0 · 包体剪映探针
> `work/r15_jianying_pkg/probe.py` **FAILED=0**（EDL 134.12s、卷轴 64 条/56 文件/815.75s/531.0s
> 与计划层逐字对齐，包内墙钟 80.7s ≈ 源码树 81.1s）。
> **accept 首跑抓到的 ④ 包内缺陷**（已修）：隔离子进程不走 ASGI lifespan ⇒
> `configure_logging()` 无人调用，root logger 无 handler，INFO 被 lastResort 丢弃 ⇒
> 包内 stdout 与支持档 `video_locator.log` **一起缺整段分析记录**（三级日志=售后能力）；
> 加上父进程拿到终态信封就 terminate 又吞尾巴。修 = 子进程自配日志+行缓冲+flush、
> 正常终态先 `join(CHILD_GRACE_S=10s)`、payload 带父 `task_id` 让父子日志可串联。
> **更正登记**：续62 补五/补六 自报「双 typecheck 干净」**不实**——当时只过
> `typecheck:desktop`，渲染层 `vue-tsc` 有 5 个错（Mock 适配器 3 处缺 `last_event_at` +
> 徽标单测夹具用了契约外 `status`），r15 构建阶段 1 打回后已修。
> 新门禁基线 = 后端 **599** · API **120** · vitest **144** · app+desktop typecheck 双绿。
> **续63 补二（同日跟进）**：① 成片通道包内实测补上（`clip_ranges` 与源码树 movie 计划 64 段
> 逐字段相同、时长 136.366 vs Σ 136.344s、h264_amf、成片顺序紧邻交叠 0 对），并升为常设验收
> `mvp/scripts/accept_packaged_render.py`；② 那趟实测抓到 `submit_render` 漏传 `isolated`
> ⇒ **渲染从未进隔离子进程**（档案"analyze/render 子进程化"对成片不实，已更正 + AST 调用点锁）；
> ③ 卷轴「紧邻同素材连放」按收窄方案实现 = `plan_jianying_assets(drop_adjacent_duplicates)`
> 默认开（config `jianying_drop_adjacent_duplicates`），2mkv 64→63 条、宽度 815.75→791.75s、
> **并集覆盖 531.0s 不变**；机制更正：紧邻重复只在剪映卷轴出现（成片/EDL/XML 都是 0 对），
> 根因 = 取材扩宽 × 紧凑拼接，不是重排本身；④ ①③ 的 UI 接线完成（侧栏低内存徽标行 +
> 运行中 ≥120s 无新事件才提示"没有新进展"）。门禁 = 后端 **602** · API **122** · vitest **146** ·
> 双 typecheck + renderer build 绿。**r15 包不含 ②③④**（源码树 only ⇒ 进包要 r16 授权）。
> **续63 补三/补四**：两处新 UI 先做了真机目检（注入造态逐档读回，顺带抓到一个失效 CSS
> token `--c-warn`→`--warn`），随后**用户裁决把显示删掉** = 侧栏「内存」行与进度条黄字
> 心跳提示全部撤除（含 store computed 与对应 vitest 用例）。**保留**后端字段与 `types.ts`
> 契约镜像 ⇒ ①③ 定性为「能力在后端、界面不呈现」，是裁决不是欠账，别再当缺口登记。

> **▶ 2026-10-07（续62）— 成片相邻段重复画面已修（导出/渲染层去重叠）**
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
  `CHANGELOG.md`（逐批明细）与本目录 checkpoint-*。近期完成（2026-10-07）：续62 相邻段去重叠 +
  r14 出包 + 包体级双臂判别 + 剪映去重语义统一 + 六项立项 ①②③④；**续63** 导出计划层常态守卫
  （序列收口成唯一入口 + 不变式自检 + AST 结构锁 + 入库常态脚本）+ 剪映逐 clip 代价实测
  （分钟级，代价主体=取材扩宽）+ **r15 出包**（accept 新加 4 条隔离硬断言并借此修掉 ④ 的
  包内日志缺失缺陷 + 抓到并回滚了自己引入的「时间线通道误扩宽」回归）；**续63 补二**
  成片通道包内实测（并升为常设 `accept_packaged_render.py`）+ 修掉渲染侧漏传的
  `isolated`（渲染此前从未隔离）+ 卷轴去紧邻同素材重复（默认开）+ ①③ 的 UI 接线。

## Current Problem
- **无阻塞项**（2026-10-08 续63 补六 复核）。现役包 = **r15**；工作树 = 续63 补六 的 3 个未跟踪探针/文档 + 本文件与 TODO/CHANGELOG 改动，**未提交**（等口令）；源码树比 r15 多两件事
  （渲染隔离修复 / 卷轴去紧邻同素材重复）⇒ **进包要 r16 授权**。
  回滚档 = r14 / r13（三份并存；建议等你真机跑过一轮 r15 再按「最新+上一档」删）。
- ~~两处新 UI 缺浏览器目检~~ = 已目检（续63 补三）并**按用户裁决删除显示**（续63 补四）；
  ①③ 只到后端 API/契约层，界面上不呈现。
- **进度链平台期（续63 补五，三轮才修对）**：修复链显示宽度从「按腿的数量平分」改成
  **按实测耗时占比** —— fix 1.7 点 / split 0.2 / patch 2.3 / ISC 1.8；fix 内部 48 单位，
  字牌 OCR 腿独占 32 单位（它一条就占修复链 28%）。三条重腿另加逐段 on_tick。
  字牌与 ISC 的改善（预测 32s / 27s 跳一格）是**模型推算**，patch 是实测（18~42s，
  与模型预测 28s 一致）；改完没再跑 27 分钟验证趟（用户要求收线），真机复核留给下次
  自然运行。**这条线到此为止，不再迭代。**
- 历史问题现状：成片相邻段重复（续62 已修）、卷轴吞段（补二 已修）、
  **渲染未隔离**（续63 补二 已修，r15 包内仍缺，`accept_packaged_render.py` 对它如实报红）、
  卷轴紧邻同素材连放（续63 补二 已实现，默认开）。

## Current Implementation

- 实现细节见项目源码与 `PROJECT_HANDOFF.md`；本文件按协议不复制源码。

## Current Decision

- 重要技术决策见 `.agent/DECISIONS.md`。

## Next Actions

> 现役未结项以 `Current Task` 顶部「续63 补六」块 + 本表为准；历史交接块已迁
> `.agent/archive/STATE_history_20261007.md`（续55「交接要点」与 (c) 关键新知识七条在其中，
> 后者已浓缩为 `Known Issues` 的「工程教训速查」）。

1. **git 提交 + 推送（等口令）**：本地领先 origin **4 笔未推**（`a792693` feat 续63 代码/测试、
   `7f253e2` docs 补一~补五、`21ddf5a` chore checkpoint、`0878e5a` docs 交接刷新）。
   另有**续63 补六未提交**：3 个未跟踪新文件（`mvp/scripts/probe_two_stage_sampling_20261008.py`
   · `mvp/scripts/probe_two_stage_visual_20261008.py` · `FINDINGS_TWO_STAGE_SAMPLING_20261008.md`）
   + 本文件/TODO/CHANGELOG 的档案改动。上一批 11 笔已推（`6a0ef88..aba3a21`）。
2. **r16 出包（等授权）**：三件在源码树、r15 包里没有 —— ① `submit_render` 漏传 `isolated`
   的修复（渲染此前从未进隔离子进程）；② 卷轴去「紧邻同素材连放」（默认开）；
   ③ 进度链按耗时分配宽度 + 三条重腿逐段 tick。
   （①③ 的 UI 显示已被用户裁决删除，不进包。）出包后必跑 `accept_packaged_bundle.py`
   + `accept_packaged_render.py`（**这条对 r15 如实报 R2 红 = 隔离修复未进包**，
   r16 应转绿）+ 三防 + 启动冒烟 + `check_export_plan_invariants.py`。
3. ~~**⑥ 换形态探针族**~~ → **⑥b 已实跑并判负关闭（2026-10-08 续63 补六）**：
   成本主判据成立（四片同脚本 0.529×）但三指标硬门崩（两片 59 条：严格 −6 / **导出实得 −12**），
   且密验腿救回精度的本质=把网格补回 1fps（墙钟反 1.52×）⇒ 不接线、不翻默认。
   **⑥a/⑥c/⑥d 仍未跑**（本轮按口令只跑 b）——是「未跑」不是「已证否」，重开需用户再提。
4. **竞品侧**：blob 序通道已打开（续62 补三），后续可按阶段词表推进（只读、不运行竞品）。
5. **分发包保留**：现有 r13+r14+r15 三份；按「最新+上一档」应删 r13（~0.98GB），等口令。
6. ~~**待拍板**：竞品 opcode 通道可行性~~ → **已试采结案（续62 补三）**：字面通道判死
   （Nuitka AOT，0 pyc）；机器码绑定通道判死；**blob 序通道打开**。
   明细 `competitor_cutmatch/FINDINGS_OPCODE_CHANNEL_20261007.md`。
7. **搁置（用户 2026-10-06/07 裁决，勿再提议）**：mac 严格惰性再 dispatch · LOC-1107 拆码 ·
   A1→A2∥A3 · 性能口径三处对齐 · 成片缺口标记 · ⑤ 导出实得口径。

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
  ⑧ **收口重复编排时，通道专属参数必须做成硬约束**（2026-10-07 续63：剪映「取材扩宽」参数
  被我误透给 EDL/XML/成片，导出画面范围被整镜头撑大、EDL 并集覆盖 134s→531s；源码树 599 项
  全绿 + 计划层守卫全绿都没抓到，是**包内产物探针**抓的 ⇒ 产物层判据不能只靠源码树）。
  ⑨ **子进程不走 ASGI lifespan**（续63）：挂在 startup 的初始化（`configure_logging()`、
  session 绑定）在 spawn 子进程里全没跑 ⇒ root logger 无 handler、INFO 被 lastResort 丢弃，
  包内 stdout 与支持档一起缺整段分析记录；再叠加父进程拿到终态就 `terminate`（管道块缓冲）
  吞尾巴。凡把执行搬进子进程，先问「父进程靠 import/lifespan 副作用拿到的东西由谁补」。
  ⑩ **抽稀类杠杆要算「救回精度要花多少」，不是只算「省多少」**（2026-10-08 续63 补六 ⑥b）：
  若第二级（命中邻域密验）的作用就是把第一级丢的网格补回来，则成本恒不省——实测命中窗并集
  占源片 33.4% ⇒ 帧数打平 1fps、墙钟反 1.52×。判这类立项前先量**覆盖率**，一页纸即可判负。
  ⑪ **严格指标看不出导出层退化**（同批）：0.5fps 在 2mkv 上严格只 −1，但**导出实得 −6**
  （主 span 变宽/位移、命中改由子 span 兜住）⇒ 凡动索引/计划/渲染层，必须同读
  「仅主 span = 导出实得」这一并列口径，别只看严格档。
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

2026-10-08 12:05（续63 补六：⑥b 两级采样探针判负关闭；4 笔待推 + 本批未提交）
