## Current Task

> **▶ 2026-09-06(XIII) — t2r07c GT 标错修正（用户画面确认）= 「混叠无解」冤案平反, 四片严格 116/139**:
> M1/M2 多模态重跑（本模型直看帧, 14 失败案例全覆盖）发现 t2r07c 查询（星条旗马甲演讲台）与
> patch top1 4697 强匹配, 而 GT 4092-4097 为战场戏; 4080-4102 全扫描无演讲台。用户确认:
> 正确桥段 = 78:12.4-78:14（**2026-09-02 人工定位把 78 分钟档误读为 68 分钟档**）。
> GT 修正 [4092.2,4097]→[4692.4,4698.0]（corrections 留痕）→ test2 严格 **14/20**（算法主定位
> 4695-4700 本就正确, 「内容相似混叠」系冤案）; 四片严格 **116/139**、场景 137/139。（续）patch_v2_margin 0.08→0.075 修复 p26 骑线未采纳（runtime 实测 margin 0.080 恰压线）→ **四片严格 117/139 零回退, patch v2 正式转正**（2mkv 35: p26 part→HIT; 耗时增量主要为 config 指纹变化触发的编辑缓存重算, 一次性）。
> M1-v2 判定表: 可分 5 / 不可分 5 / 窄窗假象 4; M2-v2 维持证伪（字幕-画面解耦）。
> open item: p26 runtime margin 口径差未触发待查。详见 TODO 2026-09-06(XIII)。

> **▶ 2026-09-06(X) — patch 召回 v2 转正 = 四片严格 113→115(+2) 零回退**:
> 门控探针（probe_patch_gate.py, 19 案例）设计采纳门 {offset≤30s 且 patch_margin>0.08} →
> runtime `_patch_nearfield_rescue`（config patch_v2_*, 默认开, 旧主定位保留为子 span）→
> 四片验收: 严格 113→115（test3 t3r04b/t3r25 part→HIT）、场景/负例持平、支撑 +23、耗时 +2.5%、
> 259 单测全绿、采纳段抽帧复核无伤害。**M6「patch 已死」正式修正**: 旧管线条件下无对象（39/39
> 池内）; twopass+最新 GT 条件下近场池命中面更宽（池外+池内偏移都受益）, +2/139 落地。
> 门控多模态复审（work/patch_gate_review/）: p14 主定位画面本来就对（窄窗假象）, 唯一真错误
> p26 被规则精确放行。立项材料: RESEARCH_PROPOSAL_PATCH_RECALL_V2.md。

> **▶ 2026-09-06(III) — 性能批① 解码/forward 流水线落地 = 字节级零语义, 全流程 -9~11%**:
> `engine/common/pipeline.py pipeline_map`（解码线程 + 主线程消费, forward 单线程——DML session
> 非线程安全）接入索引侧 `_embed_stream` 与 twopass 粗采样（亮度/白闪/卡片统计同批顺带）。
> 教训: 首版哨兵投递被自身 stop 标志吞掉 → 消费者死等（test_empty_edited 挂死定位）, 修复后
> 哨兵必达; 单测 +5。验收: 255 全绿; 全新目录 test2 全流程索引 412.3s(-8.5%) + 定位 1012.7s(-11%),
> features.npy 与重建批逐字节一致, 三指标/支撑全等。剩余杠杆（待拍板）: 分辨率 518→384 探针、
> 索引 0.5fps / dense 4fps。

> **▶ 2026-09-06 — 性能第二批落地 = A4 编辑侧持久缓存 + 抓帧并行（零偏差）, batch=1 证伪回退**:
> ① A4 持久缓存（app/edited_cache.py, edited_cache_enabled=True）: 键=sha1(文件身份+fv+管线配置+
> 设备口径), 原子写/损坏容错; **test1 首跑 398.5s → 命中 192.1s(-52%)**。② 抓帧线程池并行
> （patch 候选窗+text anchor, 打分串行保语义）→ 热跑 166.9s。**教训: DirectML EP 并发 Run 同一
> session 会原生段错误**——并行只做抓帧, forward 串行。④ batch=1 生产实测 10.1fps < batch8 10.4-11.2fps
> （M4 探针 20.5fps 不适用于生产 embed 路径）→ 证伪回退, fv 撤 +b1; 副产品: test2 索引全量重建
> 零偏差 = embed 重建确定性验证。250 测试全绿; test1/test2 抽查全等。
> **速度画像（test1/41 段）**: 首跑 ~400s → 热缓存+并行 **167s(4.1s/段, -58%)**; 产品话术:
> 首跑 20-30 min（索引一次性）, 同片复定位 2-4 min。
> 详见 TODO.md 2026-09-06 条目。

> **▶ 2026-09-05(深夜) — 审计接线 + 下一批性能探针 = A4 持久缓存上限 -54%, dense 懒计算证伪, grab spawn 是主部**:
> 盘点「有用但没进 config/runtime」: A1 `subshot_min_sub`/A2 `finloc_stable_s` 两个死字段接线(行为零变化),
> D 硬编码绝对路径改 repo 相对推导(首版 parents[3] 深度错误致 patch 静默禁用, 探针抓出 patch=0.0s 异常,
> 已修 parents[4], 教训: 资产解析无测试覆盖+静默回退)。探针(probe_perf_next.py): patch 137.7s 中
> **grab_frame spawn 111.3s=81%**(DML forward 仅 22.3s); text anchor 48.3s 首次入账; **dense 懒计算证伪**
> (39/40 段产 moments); **A4 编辑侧持久缓存上限 = 首跑 397.5s → 热跑 183.0s(-54%)**。
> 下一批优先级(待拍板): ① A4 持久缓存 ② grab_frame 批量化/常驻 ffmpeg ③ batch=1 全量重建(未来)。
> 验收: 246 全绿 + test1 抽查全等(34=34/42=42/0=0/支撑全等)。详见 TODO.md 深夜条目。

> **▶ 2026-09-05(晚) — 性能优化第一批落地 = 四片零偏差 + 总耗时 -30%（patch DML/抓帧缓存/subshot 关闭）**:
> 计时探针（probe_perf_timing.py）定位: patch rerank 占 56%（CPU torch patch 模型 + 每帧 ffmpeg 进程 spawn）、
> 切分 21%、dense 13%、定位/检索≈0。落地: ① PatchReranker 上 GPU（DML 双输出 ONNX, cos 0.999997,
> 决策逐字节一致, 9.7×）; ② grab_frame 进程内缓存 + 歧义门提前; ③ **意外暴露既有缺陷**——weak-hit
> 子镜头回退整体替换 evidence 丢 montage 已命中簇（test2 t2r02b HIT→MISS, 定向版入 runtime 时仅验
> 2.mkv）→ subshot_enabled 默认 False; ④ dml_batch_size 8→1 试做后回退（与缓存索引数值口径不一致）。
> 验收: 246 全绿 + 四片三指标/支撑 span 全等（113=113/136=136/4=4/565=565）。
> **提速**: 四片 3885→2725s(-30%), 每段中位 11.4→5.0s; 新分布: 切分 32%/patch 34%（剩余=grab spawn）/
> dense 21%。下一批候选（待拍板）: grab_frame 批量化/常驻解码、dense 懒计算、切分侧共享解码。
> 详见 TODO.md 2026-09-05 性能条目 + DECISIONS.md。

> **▶ 2026-09-05 — 蒙太奇子镜头查询方向结案 = runtime 不接入（§4 执行完毕, 三指标零变化 + oracle 口径证伪）**:
> 按 HANDOFF_SUBSHOT_QUERY §4 执行: ① 漂移触发判据（主定位 vs 最佳 span gap>15s & psim<0.62,
> 采纳改合并不替换）实现 + 246 测试全绿 → ② 四片 GPU 重跑（rerun_*_subshotdrift.results.json）
> = **严格 113→113/139、场景 136→136、负例 4→4 零变化零回退（也零改善）** → ③ 机制三层阻断实证:
> (a) 漂移型段（p10/p32/t1r18）正确区已在 pool sub span 里严格指标早已 HIT, 三指标可动段全项目仅 ~2 条;
> (b) **规模化探针「16/16 逐子救回」= oracle 口径**（research_subshot_scale.py L70-79 按 GT 中点挑
> 子镜头）, runtime max-sim 采纳必选错（t2r02b 正确子镜头 sim 0.625 为全部最低, 其他 0.77-0.85）;
> (c) t2r05a 触发仍被 all_spans 未门控近重复簇掩盖（gap 恰=15.0）。④ 按 §4.4 **接收为研究结论,
> runtime 不接入**: oracle 上限 ≈ +2/139 远低于门槛（patch 召回 +1/41 关闭先例）; runtime 代码已回退
> 定向回退版（246 全绿）; 研究脚本/结果留档（diag_subshot_* / compare_subshot_drift / rerun_subshot_drift）。
> 若未来重开: 需无 GT 的「正确子镜头选择信号」（正确子镜头 sim 未必最高, 叙事蒙太奇语义重心与
> 视觉特征突出度解耦）。FINDINGS_SUBSHOT_QUERY.md「runtime 接入验证」章 + HANDOFF §7 有完整记录。




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

---

> **2026-09-05 — I帧锚定+动态步长+三特征抑制 切分探针 = 不推荐进 runtime**:
> 用户方案（I帧锚定粗筛+动态步长+三特征抑制）四片全量验证 = 严格 110/139(-2)、
> 场景级 102/139(-34)、负例 8/9(+4 翻倍), 段数 8/4/9/14 vs 69/41/54/68 —— 像素切分
> 严重漏切。根因: 粗采样(2.9fps) 运动噪声淹没切点信号(跨切点对 AUC 0.58-0.80),
> 1fps 下判别力 90%+ → 降步长则成本优势消失; 固定 GOP(2mkv/test3 10s) 下 I 帧锚定
> 结构性失效(仅 7-10% 切点重合), 密 GOP(test2 1.15s) 有效(83%)。结论: 维持两级切分
> + 白闪守卫(C 项待拍板), 像素切分方向关闭(有据)。详见 FINDINGS_IFRAME_CUT.md。

> **2026-09-05 — 多特征抑制并入白闪守卫 定向检查 = 不建议实施**:
> 四片 232 个切点 1fps 三特征判定: 单特征型 72 个(31%)中 36 个贴近 GT 真实边界
> = 误伤率 50%; ssd_only 占 67/72。多特征抑制「≥2 特征才保留」会误删真实切点,
> 不实施(有据); 白闪守卫维持现状; 详见 FINDINGS_IFRAME_CUT.md 第八章。

> **2026-09-05 — 两级切分 + 白闪守卫 进 runtime（用户拍板，实施中）**:
> flash_guard.py 提取入库（engine/segment/, 参数走 PipelineConfig.flash_*/bright_spike_*）;
> config 新增 seg_twopass_enabled(默认 True)+粗采样/精修/最短保护参数;
> analyze_edited_video 改分派（_segment_twopass_flash 新路径 / _segment_legacy 回退）,
> 与 rerun_twopass_flash.py 验证逻辑一致; 卡守卫/进度/取消/失败隔离保留。
> 单测新增 18 项（test_flash_guard + test_twopass_flash）, 后端全套 240 全绿零回归。
> 四片回归（生产路径直跑, work/rerun_*_runtime_twopassflash.results.json）进行中,
> 对照基线 112/139 · 136/139 · 4/9; 待达标后 UI 结果数/导出验收 + 归档。

> **2026-09-05 — 非外观第二信号 研究重启立项（用户拍板）**:
> 重启研究侧立项（此前 M1-M8 闭环+失败族=已知局限被用户重启）。本会话完成前置证据:
> 语义可分性验证（方舟 VLM 24 帧, scene 4/4 同级 → 多模态方向关闭）+ 低信息降权探针
> （负例零改善+严格−1 → 像素预处理关闭）。候选方向 A 场景实例身份建模（推荐）/
> B 剪辑叙事结构 / C 多模态（已关闭）。交接文档 =
> mvp/benchmark/user_case/semantic_signal/RESEARCH_PROPOSAL_SECOND_SIGNAL.md,
> 下个对话从 §6 执行清单开始（写 research_event_identity.py P1/P2 探针）。

## Current Task

> **▶ 2026-09-05 — C 项验证完成：两级分层切分 = 最佳方案（严格 +8 / 场景 +18 / 负例持平）+ 白闪守卫生效 + GPU 优先约定固化**:
> 按 TODO 顶部 C 项执行：① 先验证 8fps 查询侧细切分收益（p36 单段取证 = 假设成立，8fps 整段即命中 GT）→
> ② 全局采样 4/6/8fps 四片全量对照 = 严格全部净负（104→100/99/103）+ t2r02b 假阳性兑现 + 2mkv 负例 +1 →
> ③ **用户提出两级分层切分架构修正（粗采样 5-8 帧找候选切点 + 局部 ±20 帧密帧精修边界 + 最短镜头保护 0.5s +
> fps 换算间隔）→ 实现并四片全量验证 = 严格 112/139 (+8)、场景级 136/139 (+18)、负例 4/9 (持平)**——
> 唯一严格净正收益方案（p36 目标救回，2mkv/test3 场景级满分；全局采样方案全被两级切分取代）;
> ④ **白闪守卫（用户四层方案：特征前置过滤/切点后处理/相似度衰减/业务兜底）实现并验证**：真实白闪定位
> 1.mp4 ed 18.35-18.46（唯一白闪区，恰被粗网格误报切点 18.345）→ 守卫删除该虚假切点（段数 70→69），
> 三指标零回退；判据校准（白闪 mean 219-251 非纯白 → mean≥200 且亮像素占比≥0.5；尖峰判据相邻差≥80 且
> 峰值≥180，20.07 真实切换不误伤）; ⑤ **诚实边界：n03（66.1-67）非白闪**——帧为正常画面，误配 HIGH [116-118]
> 是 CLS 内容相似机制（4 帧特征稳定指向源片 117），白闪守卫救不了它（doc 2fps 1 帧被 min_frames=2 门掉才
> 碰巧正确拒绝），属 t2r02b 同类「内容相似误配」需另立方案，负例 3/4 维持。
> **GPU 优先约定固化（用户拍板）**：算法/推理类任务一律优先 GPU（DirectML，本机 RX 6750 GRE），启动打印
> BACKEND_SELECTED（=DirectMLBackend/amd 生效，实测 3D 引擎 88-92%），DML 不可用才显式 fallback CPU 留痕——
> 已写入 DECISIONS.md 2026-09-05 + AGENTS.md。
> **产物**：research_twopass_prototype(_v2).py + rerun_twopass.py + flash_guard.py + rerun_twopass_flash.py +
> work/rerun_*_twopass(_flash).results.json + FINDINGS_C_ITEM_8FPS.md（六、七章）。
> **待用户拍板**：两级切分 + 白闪守卫是否进 runtime（替换 analyze_edited_video 切分，跑全套单测 + 四片回归；
> 编辑侧特征不落索引，无需 bump feature_version；段数增多影响 UI 结果数/导出需回归验收）。

> **▶ 2026-09-04 — 研究侧收尾归档（M6 v4 重算 + M4/M8 v4 重跑 + ⑩ p08b 复核）+ 三指标基线固化（measure_baseline.py）**:
> 研究侧收尾: **M6 v4 重算(RESCUE 0/39, CLS 池内 39/39, 2026-09-01)** + **M4 v4 重跑(仅 p26, DML 664s)**: v4 真值下 1fps 稀疏索引即
> best_rank=1、margin=+0.2802 → 旧「p26 12→43 恶化」是错误 GT 假象(p26 非特征上限, 与 M6 v4 CLS best=1 双向闭合);
> **M8 v4 重跑(纯 numpy 秒级)**: p26 真值/干扰互换后仍 AMBIGUOUS(uniq 差 0.027)、p08 维持 AMBIGUOUS、t3r12 维持;
> **⑩ p08b 复核 = 作废(污染残留)**: M5「patch 救回 32→2」真值窗(1048-1050)=p38 旧错误 GT 区, v4 正确位置=1108.15-1109.1,
> M6 v4 证 CLS rank=6(池内)/patch 6 零增量 → E21/M5 正面结论作废, patch 召回方向维持关闭(0/39)。
> **FAILURE_TAXONOMY 收尾归档**: 失败族最终 = p08(2.mkv 唯一兄弟机位) + t3r12(test 域); p26 移除(GT 错)、test4 逻辑剔除;
> A 类在 2.mkv 为空(CLS 39/39 进池) → 研究侧全维度闭环, 不再立项新探针。
> 三指标基线固化: **measure_baseline.py**(默认=文档基线批: 2.mkv→user_results.json, test1-3→cases/*_results.json;
> --use-rerun 切换 2026-09-02 重跑批) + **measure_shot_recall.py 重构抽 evaluate()**(CLI 输出不变) →
> 输出 work/baseline_v4.json。验证与 GT_BASELINE 文档完全一致: 2.mkv 32/39 场景 36/39 负例 2/4 支撑 79/137;
> test1 32/43 场景 38/43 负例 0/1 支撑 103/158; test2 9/20 场景 10/20 负例 0/1 支撑 13/40;
> test3 31/37 场景 34/37 负例 2/3 支撑 102/149。(注: 2.mkv 支撑 79/137 vs STATE 旧记录 80/137 差 1 = 历史快照差异;
> test1 rerun 批 97/152 vs 文档批 103/158 = 子 span 枚举差异, 严格/场景/负例两批完全一致。)
> 产物: semantic_signal/FINDINGS_M4_V4.md + FINDINGS_M8_V4.md + FINDINGS_P08B_REVIEW_V4.md + FAILURE_TAXONOMY.md(收尾段);
> mvp/scripts/measure_baseline.py + measure_shot_recall.py(重构) + work/baseline_v4.json / baseline_v4_doc.json。
> **同日追加 — ① p28/p36 召回层深漏验证 + ② 评测口径澄清(宽松口径)**: p28 在 rerun 批已 HIT(旧「深漏 800s」基于旧批, 已修复);
> p36 正确帧在 CLS top-20(rank 2/3)但被「帧级 argmax 分散→单例簇 min_frames=2 门掉 + scene 回退 top-5 未含正确 scene 232」
> 两级淘汰 → 定位选择问题非召回层(2.mkv 无召回层缺口, 39/39 进池已证); 剩余真漏 = p08(兄弟机位)+p36(定位选择)。
> ② 宽松口径对照: 严格 32/39 → 宽松①(±6s/覆盖≥30%) 35/39(+p20/p34/p41 边界偏差/GT前移) → 宽松②(±15s) 37/39(+p05/p35);
> 真实失败仅 p08+p36(与①双向闭合); 汇报口径建议宽松② 37/39(94.9%), 严格 32/39 为回归上限并标注 5 条口径低估;
> 不触碰 ConfidenceConfig(⑦ 冻结维持)。产物 FINDINGS_P28P36_RECALL_VERIFY.md + FINDINGS_LENIENT_V4_METRICS.md +
> mvp/scripts/measure_lenient_v4.py。
> **⑦ 保守化标定 = 冻结跳过**(护栏「Confidence 公式冻结+不标定占位+不用 GT 字段」为保留项, 2026-09-01 拍板权威; 不实施)。
> 本条目为 2026-09-04 同日工作(研究侧收尾+基线固化), 与下方历史条目独立; 全部零 runtime 改动。

> **▶ 2026-09-02 — test1 GT 人工复核闭环（43 正例 + 1 负例）**:
> 用户逐段人工复核 test1 全部段（分:秒标注），已回填 `gt_review/ground_truth_test1_draft.json`：
> 40 条按用户标注拆条（r07/r08/r10/r12/r13/r14/r30 多子镜头拆细），**r14 补缺失段 ed46-49→51:59~52:02**
> （原算法定位 3121-3123 实为正确！）+ r14 拆 5 镜头（a/c/d/e/b，连续覆盖 ed46-62.5）。
> 对照原算法定位: 12 段大位移（🔴 位移>5s），8 段微调，r08 三镜头跨度 460s 用户确认。
> **待办**: test2/test3 人工复核（用户逐个发定位中）→ 回填后统一跑 v4 口径三指标。
> 已确认关键: r14 缺失段=GT 漏标非算法错; 拆条后 test1 正例 43 条。

> **▶ 2026-09-02 — test2 GT 人工复核闭环（20 正例 + 1 负例）**:
> 用户逐段复核 test2（编辑片仅 69.4s / 9 段，段覆盖完整），已回填 `gt_review/ground_truth_test2_draft.json`：
> 按编辑时间轴拆条 20 条（r5/r6/r7 用户给的点跨越结果段边界，已按 ed54/55.2/56.5/57 归位）。
> **关键发现: test2 解说切跳极频繁**——r05a(ed43.8→72:25:24) 与 r05b(ed53.5→26:59:02) 同段内跳跃 -2726s（真实跳切）。
> 用户确认: r00 窗口=50:29:00~50:29:10(帧)、r01c 归 r1、r05a 窗口 72:25±1s。

> **▶ 2026-09-02 — test3 GT 人工复核闭环（37 正例 + 3 负例）**:
> 用户逐段复核 test3（编辑片 155.6s / 34 段），按编辑时间锚点重建，已回填 `gt_review/ground_truth_test3_draft.json`。
> **重大修正: r14/r15 = 加长版内容（原片正常版没有）→ 负例**——r15 之前被标 HIGH 且 multi_case 裁决算对，
> 实际是负例，直接影响 test3 HIGH 精度统计（此前 23/24 需重估）。
> **r10 = 7:22-7:24 与 conflict_rerank 修复一致**（此前记录的"差 1.5s 待修"实际已修好）。
> r13 倒叙（7:46→4:06 时间轴真实回溯）。宽窗口段（r16/r21/r24）用户确认保持。

> **▶ 2026-09-02 — ⑤' 全部闭环 + GT 正式化 + test3 HIGH 精度重估**:
> test1-3 三份 GT 正式化到 `datasets/real/ground_truth_test1/2/3.json`（100 正例 + 5 负例，tier=verified）。
> 三指标: test1 严格 32/43/场景 38/43; test2 严格 9/20/场景 10/20（拆条窄窗低估）;
> test3 严格 31/37/场景 34/37、负例误报 2/3。
> **test3 HIGH 精度重估: 24→23 段（r15 加长版负例剔除），r10 已修(7:22-7:24) → 23/23=100%**
> （原 23/24 中 r15 算对实为负例 + r10 算错实已修，双向修正）。

> **▶ 2026-09-02 — ②③ 单调弱先验进候选生成已编码，真实数据实测零触发（有据收窄）**:
> 实现 `_apply_timeline_prior`（Ambiguous 型段用前序段定位中点做锚点，带外 primary + 带内竞争候选
> 且 cover 落差<=0.10 才切；逃生门=唯一强候选/首段/前段未定位/带内/全带外不触发）+ 配置
> (timeline_prior_enabled/ta_band_s=45/ta_max_cover_drop=0.10) + 单测 8 项；**全套 222 全绿**。
> **重跑验证（新代码含先验，复用索引）**: 2.mkv/test1-3 四片新旧三指标**完全一致**（32/39、
> 32/43、9/20、31/37 零变化）→ **先验零触发零影响**。
> 原因: ①多数 montage 段 primary 带外但带内无 cover 接近的竞争候选；②p08 型兄弟机位 primary
> 1048 恰在带内(离前段 33s)、真值 1108 带外——先验结构性无效（呼应 M8 邻接证伪）；③真实跳切
> 段全带外, 逃生门生效不误伤。
> **结论**: 候选生成级弱先验零增量（时间轴先验价值已由事后 temporal_repair(+1 p16) + 时间轴→
> Ambiguity 兑现）；实现保留为护栏（零回归默认开）；**不建议再调参投入**（零信号）。
> 产物 `semantic_signal/FINDINGS_TIMELINE_PRIOR.md` + `work/rerun_*_timelineprior.results.json`。

> **▶ 2026-09-02 — ⑤' 材料交付(用户逐段人工复核中) + ② 时间轴→Ambiguity 已编码 + ④ 时序重排 v4 量化已完成**:
> ⑤' 数据层材料: 三份 GT 草案 `gt_review/ground_truth_test1/2/3_draft.json`(全部段, tier=pending, 定位占位待毫秒复核)
> + 复核工作表 `GT_REVIEW_WORKSHEET_test1-3.md` + 时间轴清单 `TIMELINE_CROSSCHECK_test1-3.md`;
> 对照图 76 张按最新定位全部重生成(含 test2 补齐 3→9 张)。**用户正在逐段人工复核, 待回填后 tier→verified/loose**。
> ② 时间轴→Ambiguity = `_apply_temporal_ambiguity`(复用 find_temporal_outliers, 修复后仍离群 HIGH→MEDIUM + reason
> temporal_outlier_ambiguous, 不改定位; 配置 temporal_ambiguity_enabled/ta_max_downgrade; 2.mkv 零触发零回归; 全套 214 全绿)。
> ④ v4 量化 = temporal_outlier_repair 净纠正 +1(p16), 产物 `semantic_signal/FINDINGS_TIMELINE_V4_QUANT.md`。
> ③ r10 = current 442-444 vs 真值 444.5(差 1.5s, 留 ⑤' 精修)。

> **▶ 用户拍板推进顺序(2026-09-01 深夜)= 数据层 test1-3 全量毫秒级重标 + 时间轴→Ambiguity + r10 单点**:
> 执行序: ① test1-3 全部 GT 毫秒级人工重标(数据层主线, 吸收 B 段; test4 剔除) → ② 时间轴→Ambiguity → ③ test3 r10 单点 → ④ 时序重排 v4 量化 → 之后单调弱先验→保守化标定→M1-M8 低成本重跑→p08b。
> ⑤'(test1-3 全量毫秒级) 是 ⑨ B 段的超集+升级, ⑨ 并入 ⑤'。完整见 `gt_review/NEXT_STEPS.md` 顶部。

> **▶ GT v4 重建完成(2026-09-01 专会话)= 41 条全定案写入 ground_truth_v4.json, v4 三指标 31/39, p26 实证 GT 错非特征上限**:
> 用户逐条裁决 41 条(NOT_REVIEWED p36-p41 补审 + WRONG 重定位 + PARTIAL 收窄 + WRONG_GT 按线索改)——**删除 p37(p10 ED 重合)/p38(p08 ED 重复), 29 条 relocate + 2 条 delete = 31 条 corrections 留痕**(v3 原文件保留未覆盖)。
> **辅助通道**: 三批 VLM(Volcengine Ark)补审 = ① 14 条(NOT_REVIEWED+WRONG) ② 13 条 PARTIAL 逐帧 ③ 9 条 top-6 候选窗判定; 用户看候选图逐条拍板(容差±几 ms)。
> **关键实证**: **p26 MISS→HIT**(GT 2809-2810→1768.2-1770.05 用户精修 00:29:28.20-00:29:30.05, runtime 1762-1769 HIGH 命中)= GT 标错而非特征上限 → M1-M8 中把 p26 当「不可辨识/特征上限」的结论作废; 补充线索: ed 1:17.4 闪帧子镜头=原片 1783.1(仅一瞬间)。
> **v4 重测**(同 results/脚本): 严格 **31/39**(verified 30/36, loose 1/3) | 场景级(±15s) **36/39** | 负例 **2/4** | 支撑 **80/137**。
> v3 对照: 严格 39/41 / 场景级 39/41 / 负例 2/4 / 支撑 91/137 —— **下降为修正 GT 后的真实口径, 非算法回退**(旧 GT 大量标错, 算法命中错误窗口被误计对)。
> A 段数据层补 GT 后 v4 复测(2026-09-01): p08/p05/p20 精修毫秒 + p28 修正(2810-2812→**1833.15-1836.00** 用户画面确认)→ **严格 32/39**(p28 MISS→HIT, runtime 1828-1840 命中; 再次实证旧 GT 标错致假 MISS)。剩余 v4 MISS: p08(1108.15-1109.1, 兄弟机位特征上限)/p36(2042-2043.4 runtime 未命中); part: p05/p20/p34/p35/p41(场景级命中未盖窄窗)。
> **下一步**: 重审 M1-M8 依赖错误 GT 的结论(p26 已证; p38 兄弟机位=重复已删; 三指标以 v4 为基线)。决策见 DECISIONS.md 2026-09-01。

> **▶ test4 数据错误确认并逻辑剔除(2026-09-01)= ed/om 是两部不同电影, test4 全部 GT/探针结论作废**:
> ffprobe 铁证: test4-ed.mp4(81s 竖屏 576×832) vs test4-om.mkv(71min 横屏 1920×804) 时长差50倍/横竖屏/帧率/音频全不同。
> **影响**: test4/t4r01 相关 GT 与 M2/M3/M4/M5/M7/M8/P1/P2「同质场景」失败族结论全部作废; FAILURE_TAXONOMY test4 案例失效;
> 数据层 B 段改 test2+test3; 三指标 v4 基于 2.mkv 不受影响。**逻辑剔除不物理删文件**(保留证据, 详见 datasets/real/test4-INVALID.md)。

> **▶ Ambiguity Detection 原型实验完成(2026-09-01)= 现有置信信号无法分离「正确 HIGH」与「错配 HIGH」, AMBIGUOUS 检测无内部信号**:
> 重跑 29 段 EvidenceLocalizer 提取内部 multi-evidence 信号: **HIGH 档精度仅 5/13(38%)**, 但正确/错配在
> mode/n_clusters/qcov/dispersion/best_sim/margin 上完全同构(primary best_sim 0.49-0.69 重叠)。
> 机制: 错配 HIGH 多为 clean 单证据簇(secondary=None → margin 饱和 1.0), `low_candidate_margin`/`multiple_similar_candidates`
> 都要求 n_strong_clusters>=2, clean 段结构上不触发降险 flag → 无论对错都 HIGH。
> 结论: AMBIGUOUS 检测在该特征架构下无内部分歧信号可用(与 M1-M8 兄弟机位混叠 + 2026-08-27 置信标定研究双向闭合);
> 校准转向 = 保守化 HIGH 门槛标定(用 v4 数据降「自信错答」precision), 不立项 AMBIGUOUS。产物 `semantic_signal/FINDINGS_AMBIGUITY_PROTOTYPE.md`。

> **▶ M6 v4 重算完成(2026-09-01)= patch 召回 RESCUE 1/41→0/39, v3 的 10 条「CLS 池外」全是 GT 标错假象, 方向彻底关闭**:
> 用户拍板重算 M6(v4 GT): **RESCUE 0/39、CLS 池外 0、CLS 池内 39/39**——v3 里 p05/p10/p20/p23/p24/p26/p32/p41 的
> 「CLS 池外未救回」修正后全部 best_rank 1-8 直命中(池内); **p13「patch 唯一救回」也是 GT 标错假象**(v4 CLS best=1)。
> 结论: patch 召回 runtime 化零增量(0/39), 方向关闭(有据); M6 原「RESCUE 1/41」作废。产物 `semantic_signal/FINDINGS_M6_REVISED.md`。

> **▶ M1-M8 结论重审完成(2026-09-01 GT v4 修正后)= p26/p38 从「不可辨识样本」移除, 失败族收窄**:
> 以 v4 GT 重判全部 M1-M8 存档数据: **p26=GT 标错实证**(旧 2809 错→正确 1766-1770, v4 runtime 直接 HIT 1762-1769 HIGH)——
> M1b「VLM 反向选错」实为判对(1766 SAME 3/3=真值), M2「p26 字幕正面信号」反转(3/3 命中的是错误窗 2808), M4/M5/M6/M7/M8 的 p26 行全部作废或需重算;
> **p38=与 p08 重复已删**且旧真值 1048 本身错(正确=1108-1110=p08), M5 p08b 救回存疑/M6 p38 行作废/M7-M8 p38 半边作废;
> **失败族收窄为**: p08(兄弟机位, 2.mkv 唯一合法案例) + t3r12/t4r01/test4(test 域不受影响);
> **M6 全量「RESCUE 1/41」统计作废需 v4 重算**(方向性收益低预判不变)。产物 `semantic_signal/FINDINGS_REVIEW_M1M8.md`, 三指标基线=v4。

> **▶ GT v3 人工审查发现大量标错(2026-09-01)= 三指标 39/41 基线作废, M1-M8 结论需重审, 进入 GT 重建阶段**
> 用户逐条审核 ground_truth_v3.json 的 original 窗口(35/41 条已审): **仅 6 条 OK**(p06/p17/p22/p25/p29/p30), 29 条有误
> (PARTIAL 13 / WRONG 8 / WRONG_GT 7 / p26 确认错), 6 条未审(p36-p41)。
> **后果**: 三指标 39/41 + M1-M8 依赖 p 系列 GT 的结论全部作废/需重审(p26 已证=GT 错非特征上限)。
> **资产**: `gt_review/GT_REVIEW_RECORD.md` + 41 张对照图 `gt_review/pXX_sheet.jpg`。
> **下一步**: 修正 GT(按用户逐条判定)→ 补审 p36-p41 → 重测三指标 + 重审 M1-M8。决策见 DECISIONS.md 2026-09-01。

> **▶ 校准阶段立项(2026-09-01 用户拍板 A+B)= 目标从「让 Ambiguous 变对」转为「提高可识别样本召回/精度 + 正确识别 Ambiguous」**:
> 研究侧全维度闭环(外观三层/序列P3/邻接M8/语义M1-3/密度M4)后, 失败族定性「不可辨识样本」→ 进入**校准阶段**(非继续找新模型)。
> **四层状态**: ①算法层=能力边界已知(五类信号不足以消歧 Ambiguous); ②产品层=**Confidence Calibration + Ambiguity Detection**(HIGH 自动/MEDIUM 通过或提示/LOW 提示/AMBIGUOUS 明确转人工——用 margin/similar_band/multiple_similar_candidates 等现有信号);
> ③数据层=**补真实 GT(范围 A+B)**: A=2.mkv 失败族周边+Ambiguous 候选段(已补: p08/p05/p20 精修 + p28 待终点 + 其余正确); **B=test2+test3 LOW/MEDIUM 完整 GT**(test4 数据错误已剔除, 见下); GT 逐帧画面确认纪律不变;
> ④研究层=额外来源信号(provenance)=Research/Future 非阻塞。决策见 DECISIONS.md 2026-09-01。三指标 39/41 仍为回归基线。

> **▶ M8 原片邻接唯一性探针已完成(2026-09-01,研究侧)= 来源身份信息方向证伪, 失败族正式定性「不可辨识样本」**:
> 用户正确指出「来源身份信息」是外观之外唯一未被否定维度, 并划界 = 不是重包 P3(编辑上下文), 而是**原片侧 Shot Graph 邻接唯一性**。
> **M8 结果**(纯 numpy, 秒级): 用 scenes 表(2.mkv 699 场景)对 5 个失败案例测「真值 vs 干扰 邻接唯一性」——**全部 AMBIGUOUS**:
> p38/p08 兄弟机位真-干扰邻接余弦 0.613(同一场对话戏邻接同样貌); p26 唯一性差仅 0.027; t3r12 干扰反而更唯一; t4r01 几乎相等。
> **归因**: 兄弟机位邻接本身相似(场景集中在同一时间窗, 呼应 P3 根因); P2 过度归并担忧被证实。
> **结论**: 来源身份信息清单全部落空(前后镜头P3/剪辑点/镜头图邻接M8/字幕对白M1-3/音频不同源/OCR字牌单例) →
> 失败族(p38/p26/t3r12/t4r01)**正式定性为「不可辨识样本」**——不是算法没做好, 是这些样本在可获得证据下无可区分线索。
> 研究侧全维度闭环: 外观(CLS/patch/局部) + 结构(序列P3/事件P2/邻接M8) + 语义(M1-3) + 密度(M4)。零 runtime, 三指标 39/41 未动。FINDINGS `semantic_signal/FINDINGS_M8.md`, 脚本 `mvp/scripts/research_provenance_neighbor.py`, 数据 `work/provenance_neighbor_results.json`。

> **▶ M7 局部特征探针已完成(2026-09-01,研究侧)= ALIKED 局部描述子对核心难例(p38/p26)无解, 外观三层(CLS/patch/局部)全部关闭**:
> 用户拍板「先1再2」: 1=FAILURE_TAXONOMY.md 固化 A/B/C/D 分类; 2=现代局部特征验证。网络受限下用户手动装 kornia 0.8.3 + aliked-n32.pth(本地加载验证 cos 通过)。
> **M7 结果**(CPU ALIKED, 633s): 池=均匀采样∪真值/干扰窗(~260-318帧, 不借 CLS 池, 测独立判别力)——**p38(兄弟机位士兵特写) rank 61 + 干扰反超(margin −24)**;
> **p26(夜读) rank 125 + 干扰反超(margin −19)**——两个 M6 显示 CLS/patch 双失败的案例, ALIKED 局部结构同样失败。
> p08 rank 21(margin +34)/t3r12 rank 16(+48) 弱正向但方向不一致(同对兄弟机位 p08 +34 vs p38 −24, 局部匹配对查询机位敏感);
> p01/t4r01 无退化无增量。**归因**: 兄弟机位拍同一刚性场景, 局部 patch 本身相似(单应成立), 局部证据天然同貌——M7 与 Phase 24-1 几何结论呼应。
> **结论**: 局部特征方向关闭(有据); 失败族(兄弟机位/夜读/同质/重复)在**外观三层全部无解**, 定性为「身份级区分」局限。零 runtime, 三指标 39/41 未动。FINDINGS `semantic_signal/FINDINGS_M7.md`, 脚本 `mvp/scripts/research_local_feature.py`, 数据 `work/local_feature_results.json`。

> **▶ M6 GT 级 patch 召回覆盖探针已完成(2026-09-01,研究侧)= patch 召回 runtime 化不值(数据): 仅 +1/41, 方向关闭**:
> 用户拍板「跑完 41 条 GT 再决定 patch 召回 runtime 化值不值」。M6(DML 双输出 ONNX, 6633s)对全部 41 条 GT 正例算
> CLS 全索引 best_rank + patch 混合池 best_rank——**RESCUE 1/41 = 仅 p13**(峡湾直升机航拍: CLS 188 → patch 1);
> CLS 池外 10 条中 patch 只救回 1 条, 其余 9 条未救回(p05/p10/p20/p23/p24/p26/p32/p38/p41); 31 条 CLS 本就在池内。
> **关键**: M5 的 p08b 32→2 在 M6 p38(同一目标区域 1048-1050, CLS 340→patch 225)不复现——查询帧选取不同致矛盾,
> patch「救回」对查询帧高度敏感, M5 高估了稳定性。p26/p24/p41/p38 双通道均无解, 失败族维持特征上限。
> **结论**: patch 召回 runtime 化 = 仅 +1/41 且信号不稳, 低于「≥2-3 条才值得」门槛 → **方向关闭(有据)**, 与方向 A/C 归档并列;
> p13 留档为唯一真实救回案例。零 runtime, 三指标 39/41 未动。FINDINGS `semantic_signal/FINDINGS_M6.md`, 脚本 `mvp/scripts/research_patch_recall_gt.py`, 数据 `work/patch_recall_gt_results.json`。

> **▶ M5 patch 级召回探针已完成(2026-09-01,研究侧)= patch 对兄弟机位选对实例有效, p26 仍特征上限**:
> **M5 结果**(DML 双输出 ONNX, 918s):混合池(CLS top-200 ∪ 全索引采样 ∪ 真值/干扰窗)内 patch V3 打分——**p08b 32→2**(兄弟机位选对实例, 与 E21 一致, 含采样+干扰更真实池内复现); p08 6→5 微改进; **p26 22→24 无解**(干扰 sim 0.951 反超正确 0.900, margin −0.05, patch 层同样特征上限); 易例 p01/t3r12/t4r01 全保持 top-1 零回退。**产品相关缺口**: runtime 检索 top-20, p08b(CLS 32)/p26(CLS 22) 均超池, patch 可救 p08b 型、救不了 p26。工程情报:DML patch 双输出 ONNX 18fps 数值一致, patch runtime 化可行。FINDINGS `semantic_signal/FINDINGS_M5.md`。

> **▶ 索引密度探针 M4 已完成(2026-09-01,研究侧零 runtime)= 8fps 密帧对判别零增益,索引密度方向关闭,证据链 M1-M4 全貌闭环**:
> 起因:用户质疑「帧数不能再提升吗?GPU 加速还能往上吗?」(对标同类软件 30fps 全片解析)。澄清:Phase 14C「2→4→8fps 零增益」是查询侧结论,索引侧从未测过 → M4 首次实测。
> **M4 结果**(DML batch=1,717s):同一编辑段查询,8fps 密帧 vs 1fps 稀疏索引候选池对比——
> p08 best_rank 都 1(top5 2→5 略改善)/margin 0.393→0.365;p26 best_rank **12→43(密帧反而恶化,候选池稀释)**/margin −0.280→−0.247 仍负;t3r12/t4r01 完全持平(margin 略降)。**8fps 未把任何负 margin 变正**。
> **归因**:索引密度解决「正确帧数量」不解决「正确 vs 干扰可分性」;p26 干扰 dist_max_sim 0.876 反超正确 0.596 是 CLS 特征混叠,任何帧率救不了。**30fps 全片解析成本 ×30 换不来判别增益 → 方向关闭**。
> **吞吐实测**(RX 6750 GRE + ViT-S @518):DML batch=1 **20.5fps** 最佳,大 batch 并行收益≈0(plateau ~15fps),达不到 30fps;**工程情报:未来 DML 批量推理用 batch=1 而非默认 8**。
> **难例多模态辅助**(用户指示):M4 难例 p26 正是 M1/M2/M3 靶心——M1b VLM 事件级反向选错(真值 0/3)、M2 字幕召回唯一弱正(3/3,不可索引化)、M3 CLIP 无判别力。三形态已测,无可靠分离。
> **证据链 M1-M4 全貌**:判定(M1)/召回(M2)/索引(M3)/密度(M4) 四路全无解 → 失败族维持特征上限=已知局限。零 runtime,三指标 39/41 不受影响。FINDINGS `semantic_signal/FINDINGS_M4.md`。

> **▶ 方向 C 已关闭(2026-09-01)**:多模态(字幕/VLM)语义经 M1 判定证伪 + M2 VLM 召回单例弱 + M3 可规模 CLIP 索引证伪(无判别力 Δ<0.003 + 易例回归)→ 无可靠可规模多模态通道。剩余失败族(兄弟机位/同质场景/夜读/重复镜头)维持「特征上限=已知局限」;未来如需重开,证据在 `semantic_signal/FINDINGS_M1/M2/M3.md`。
> 起因:用户拍板立项方向 C 完整验证(A)= 引入文本嵌入 → 建「字幕→原片场景」向量索引 → 多案例量化。前置已通:pip 装 sentence-transformers 6.0.1 + clip-ViT-B-32-multilingual-v1(hf-mirror 可达, 512 维, 支持法语),不碰 onnxruntime/rapidocr 依赖。
> **M3 结果(38s 纯本地)**:CLIP 跨模态字幕检索**无判别力**——所有候选场景相似度挤成平台(p26 Δ0.002、p08 Δ0.001、test4 Δ0.002),排序≈噪声;真值 rank p26 2/8、p08 3/7、test4 2/8;**易例 p01 被字幕推到 5/7(比随机差)**。
> **机制归因**:解说字幕是**故事级叙事文案**不是画面级描述,与画面松散/解耦(test4 事件无对应、p01 抽象文案带偏);CLIP ViT-B-32 文本-图像对齐对「外观近同」候选无区分力。
> **方向 C 全貌**:M1 判定证伪 + M2 VLM 召回仅 p26 单例弱(3/3 vs 1/3, 昂贵不可规模) + M3 可规模索引证伪 → **多模态语义无可靠可规模通道**。
> **对用户「早期纯视觉是否错过多模态红利」的最终回答**:方向 C 是唯一被遗漏通道,现已完整验证 = 无可靠红利可回收,「纯视觉+特征上限」经得起多模态验证。
> **已拍板(2026-09-01):方向 C 关闭**。多模态(字幕/VLM)语义经 M1 判定证伪 + M2 VLM 召回单例弱 + M3 可规模 CLIP 索引证伪(无判别力 Δ<0.003 + 易例回归)→ 无可靠可规模多模态通道。剩余失败族(兄弟机位/同质场景/夜读/重复镜头)维持「特征上限=已知局限」;未来如需重开,证据在 `semantic_signal/FINDINGS_M1/M2/M3.md`。

> **▶ 字幕语义召回探针 M2 已完成(2026-09-01,研究侧零 runtime)= 方向 C 首次正面信号(p26 3/3 vs 1/3),但有清晰边界**:
> 起因:用户拍板「结合多模态判定」后进一步拍板测**字幕语义召回索引**(方向 C 的正确用法,此前只列远期从未实测)。探针 `research_semantic_signal_M2_subtitle_recall.py`(VLM 调用 24 次,数据 `work/semantic_signal_M2_results.json`)。
> **M2 结果**:
> - **p26 夜读 = ✅ 字幕语义召回首次正面信号**:字幕「她用望远镜看 Levi 在做什么」真值区 [2808-2811] **3/3 EVENT YES**(VLM 认出圆形暗角=望远镜视角看 Levi),干扰夜阳台 1/3——视觉 CLS 分不清的夜读/夜阳台,字幕能分(p26 上第一个正向信号)。
> - **t3r12 = ⚠️ 弱正向**:真值 2/3 vs 干扰 1/3(精灵王站着看,重复镜头语义同貌区分度有限)。
> - **test4 = ❌ 0/3 全 NO**:字幕「二十多人被困滑梯管道」在原片画面无对应——解说字幕是叙事文案,与画面解耦。
> - **净结论**:方向 C **不是全盘证伪**——字幕精确描述原片画面事件时(p26)字幕召回有效,修正此前「结构性不可行」的悲观判断;但适用边界 = 字幕-画面对应性(有则有效,解耦则无效)。**环境约束:无文本嵌入模型**(sentence-transformers 全 MISS)→ 只能 VLM 逐窗匹配,未建向量索引。
> **已拍板(2026-09-01):立项方向 C 完整验证(A)**——引入文本嵌入模型 → 建「字幕语义→原片场景」向量索引 → 更多案例量化召回增益(重点收集 p26 型「字幕精确描述画面事件」案例)。**前置可行性**:本机无文本嵌入模型(sentence-transformers 全 MISS),需先确认 pip 安装/模型下载可达性;若网络不可达则退回受限形态(VLM caption 化)并如实标记。

> **▶ 多模态判定探针 M1 已完成(2026-09-01,研究侧零 runtime)= 事件级语义证伪/字幕召回弱信号,特征上限获语义层独立确认**:
> 起因:用户拍板分层检索方向「结合多模态进行判定」(A: 召回层+判定层两层都测)。探针 `research_semantic_signal_M1_multimodal.py`(VLM 调用 36 次,数据 `work/semantic_signal_M1_results.json`)。
> **M1a 字幕语义召回 = 弱方向性信号**:p08 正确 1/3 vs 兄弟 0/3、t3r12 正确 2/3 vs 干扰 1/3(弱偏好正确), 但 p26 两窗都 2-3/3 → 单靠字幕无法精确分离失败族。
> **M1b VLM 事件级判定 = 证伪(甚至反向)**:p08 兄弟 3/3 SAME(语义同貌无法区分);**p26 编辑段被判与干扰夜阳台 3/3 SAME、与真值夜读 0/3 SAME(反向选错, VLM 视觉混淆比 CLS 更严重)**;t3r12 正确/干扰都判 SAME(重复实例语义同貌)。
> **净结论**:失败族本质=「语义相同的实例」(兄弟/重复/夜读夜阳台), 事件级语义层与外观层**共享同一天花板**, VLM 事件级判定无判别力(p26 甚至反向); 字幕语义存在弱方向性但非独立判别器, 可留作未来两阶段检索的召回侧弱加权候选。
> **证据链闭环**:外观/结构(五路)+ 事件聚类(方向 A)+ 序列上下文(P3)+ 语义/多模态(M1) 五层全部无解 → **特征上限为多维独立确认的已知局限**。零 runtime, 三指标 39/41 不受影响。FINDINGS `semantic_signal/FINDINGS_M1.md`。

> **▶ 第六路候选信号·镜头序列上下文探针 P3 已完成(2026-09-01,研究侧零 runtime)= 证伪,特征上限正式封顶**:
> 起因:用户指出五路+方向 A 之后仍有一路未证伪=镜头序列上下文(用目标镜头前后镜头内容联合匹配,独立证据源)。已按用户要求做离线最小验证:`research_semantic_signal_P3_seq_context.py`(纯现有 CLS+GT 编辑段边界,零 runtime)。
> **P3 结果(全部证伪)**:
> - **P3a 编辑序列与原片时间轴非 1:1**:p07→[1027,1041]、p08→[1160,1166]、p09→[1131,1147]、p26→[1766,1770](真值 2809 偏 1000s+)、p40/p41→[1894,1900]/[346,355]——快剪解说编辑序列≠原片序列。
> - **P3b p08 序列匹配=不升反降**:单镜头真值134 rank 44 vs 序列匹配 rank 61,**兄弟场景128 被推到 top-1**。top3 全为同一对话戏场景(128/135/138)。
> - **P3c p26 对照=证伪**:真值 rank 17→35,答案被拉向编辑上下文区域(1772-1907),远离 2809。
> - **根因**:①p08 编辑段后相邻镜头 p09 内容恰来自原片 1048-1082=兄弟机位区域,编辑上下文自身就混着兄弟内容,非独立证据;②同一场对话戏镜头在原片集中在 1010-1154 同一时间窗,不存在"只在 1108 出现的唯一上下文";③p26 编辑重排致上下文把答案拉向错误方向。
> **回答用户三问**:①p08 查询片段**不含完整镜头边界**(编辑段仅覆盖场景134 内部 2/15s),但 GT 边界提供完整查询镜头,失败不在此;②编辑侧 scenes.npy 仅 2 粗场景无细边界,但 GT 编辑段可当查询镜头;③p26 上下文序列差异更极端(相邻 1772-1780 vs 真值 2809)。
> **结论**:外观层/事件聚类(P1/P2)/序列上下文(P3)全部证伪或边界受限→ **剩余失败族(兄弟机位/同质场景/夜读)正式封顶为特征上限=已知局限**。唯一未探索空间=方向 C 多模态语义(远期,工程量大且语义层可能同样分不清兄弟机位)。零 runtime,三指标 39/41 不受影响。FINDINGS `semantic_signal/FINDINGS_P3.md`。

> **▶ 剪映通道验收闭环(2026-09-01 用户确认)**:`D:\JianyingPro Drafts\` 下 test1-ed.loc.v6 / test3-ed.loc.v7 草稿已由用户双击确认完成,剪映通道最终验收通过,**不再列入待用户动作**。导出验收主力维持 PR CEP 通道(119/119 PASS)。剪映相关历史待办均视为已闭环。

> **▶ Phase 24-2 语义级第二信号·方向 A 探针 P2 已完成(2026-09-01,研究侧零 runtime)= 兄弟机位事件级 top-1/重复镜头保持/同质场景证伪 = 已拍板【方向 A 归档】**:
> 拍板:用户选 **A1 继续 P2**。P2 设计 = 事件归并规则(时序近邻+指纹联合聚类:场景中心时间差≤T_gap AND 指纹余弦≥S_sim 连通分量;网格 30/60/120s × 0.55/0.60/0.65/0.70)+ 编辑段→事件单元端到端排序(对照帧级/场景级/事件级三档)。脚本 `research_semantic_signal_P2.py`,数据 `work/semantic_signal_P2_results.json`,FINDINGS `semantic_signal/FINDINGS_P2.md`。
> **P2 结果**:
> - **P2a 归并规则**:兄弟机位(134↔128)**12/12 参数全同单元**(归并稳健捕获同一事件多机位,单元含 946-1166s 连续对话戏 19 场景);重复镜头正确[43,44,45] 12/12 同单元但**干扰 42/46 被时序并入**(过度归并);同质场景 test4 正确实例多数参数**不同单元**且干扰混入(证伪确认)。
> - **P2b 端到端**:p08+p38 兄弟机位 场景级 8/699 → **事件级 top-1**(T_gap=120 三档稳健)——**正面回答 P1a「rank 6/11 不唯一」:归并规则=时序+指纹联合而非纯指纹聚类**;t3-r12 事件级 top-1(11/12 参数)保持;test4 无效;易例 p01 全档 top-1 零回退;p04/p17 场景级排名差为「场景指纹均值稀释」代理伪影(帧级 148/10 正常,非 runtime 回退);p26 事件级意外到 2/129(谨慎解读,不宣称特征上限已解决)。
> **净结论**:方向 A 与用户拍板预期(重复镜头族+部分兄弟机位族)一致,兄弟机位族超预期(事件级 top-1)。零 runtime 改动;三指标 39/41 不受影响。
> **已拍板(2026-09-01):方向 A 归档**。P1+P2 证据链完整(兄弟机位事件级 top-1 / 重复镜头保持 / 同质场景证伪),按立项约定「P2 结束无论成败都归档」→ 剩余失败族(同质场景)维持「已知局限」。未来如需重开,证据在 `semantic_signal/FINDINGS_P1.md` + `FINDINGS_P2.md`。

> **▶ Phase 24-2 语义级第二信号·方向 A 探针 P1 已完成(2026-09-01,研究侧零 runtime)= 部分成立/部分证伪,待拍板 P2 或关闭**:
> 起因:Phase 24-1 五路信号(ViT-B 升规模/视觉几何/运动签名/投影头/OCR 文字)全部证伪 + VLM 两轮判读确认失败族为特征上限后,用户拍板写「语义级第二信号」立项材料 → `semantic_signal/RESEARCH_PROPOSAL.md`(方向 A=场景实例身份建模[推荐] / B=剪辑叙事序列对齐 / C=多模态语义[远期])→ 用户选 **A**,写探针 `research_semantic_signal_P1.py` 并跑完。
> **P1 结果(静态度量,未训身份嵌入)**:
> - **P1a 归并能力 = 信号存在但不唯一**:p08 场景134↔p38 场景128(GT 双真兄弟机位)指纹 mutual_sim=0.704、基线 0.366±0.137、**z=2.47**(显著近),但 rank=6/11(非彼此最相似,前有 5~10 个其它场景)→ 聚合信号存在,单靠指纹聚类无法精确归并。
> - **P1b t3-r12(重复镜头)= ✅ 可分离**:正确实例场景[43,44,45] vs 干扰[42,46,47,48],within=0.587 vs cross=0.399 → **sep=+0.188**,正确场景平均指纹排名 **2.0/7(top-5 达标)**——比帧级(用户判错/特征上限)更有判别力,**方向 A 对重复镜头族有效**。
> - **P1b test4(同质滑梯)= ❌ 不可分**:within=0.482 vs cross=0.516 → **sep=−0.035**(跨簇反高),确认特征上限,方向 A 不覆盖同质场景族。
> **净结论**:方向 A 对**重复镜头族**有真实价值(t3-r12 场景指纹可分离);对**兄弟机位族**信号存在但不唯一(需时序上下文/人物连续性等更强事件身份特征,当前指纹粒度不足);对**同质场景族**证伪。**P2(身份嵌入端到端排序)未跑**——P1a 的不唯一意味着仅基于场景指纹均值的身份嵌入排序提升有限,P2 需先解决"哪些场景构成同一事件"的归并规则。
> **待用户拍板**:A1 继续 P2(先设计事件归并规则[时序近邻+指纹联合聚类],再验证编辑段→事件单元端到端排序;预期收益仅限重复镜头族+部分兄弟机位族) / A2 关闭方向 A(保留 t3-r12 可分离证据,剩余失败族正式关闭为已知局限)。零 runtime;三指标 39/41 基线未动。

> **▶ Phase 24-1 非外观第二信号三探针预研已完成 = 全部证伪(2026-08-31 晚,研究侧零 runtime 改动)**:
> 起因:用户提案立 Phase 24-1(研究侧),三探针打已知失败族(p08/p08b/p26/t3-r12)+ 易例回归 + 三指标。提案的事实核对全数成立(patch-max V3 在 runtime、视觉空间几何从未试过、PRNU/加速失真不适用、时序几何已证伪)。**实测结果:三探针全部证伪,且核心预期被否定**——
> ①**视觉几何一致性 = 证伪(核心)**:patch 互近邻 + `estimateAffinePartial2D`/`findHomography` RANSAC 内点率。p08 真值帧 1108 HOMOG=0.33 vs 兄弟 1048=0.51;p08b 兄弟 1109=0.75/n_match=329 压倒真值 1048=0.49/78。**归因(理论层)**:同一刚性场景从不同机位拍摄,patch 对应仍满足单应约束(平面近似),"不同机位→违反单一仿射"前提在多视图几何上不成立;叠加 1fps 候选粒度帧对齐敏感(真值窗内 0.33→0.85 跳变)。p26 的 inlier rank 2 为假阳性(干扰 1692 0.591 仍压真值 0.576,无 margin)。
> ②**时序运动签名 = 证伪(方法学不成立)**:编辑片快剪(压缩比>1),窗口帧差签名时间轴与原片非 1:1,未先对齐连易例 p01 都 corr=-0.87。不重试。
> ③**难例投影头微调 = 数据不缺,无可分信号**:分块余弦盘点——每索引跨场景高相似对(sim≥0.60,Δt≥2s)= 2.mkv 49,572 / test1 51,289 / test2 26,018 / test3 91,708 / test4 31,737,**「数据瓶颈」论点不成立**;但 CLS 特征级混叠 + ①②证伪 → 无可注入第二信号,不立项。
> **回归**:`measure_shot_recall.py`(GT v3,41/4)现行 = 严格 39/41(verified 35/37, loose 4/4)、场景级 39/41、FP 2/4、支撑 91/137 —— 与 Phase 24 基线**完全一致,零回退**(pre24 快照 38/41 为旧态)。
> **结论**:剩余失败族(p08/p08b 同场戏兄弟机位、p26 夜读、t3-r12 重复镜头)= 特征上限,**维持「接受为已知局限」既有拍板**;未来唯一有价值方向 = 语义级第二信号(场景身份/多模态字幕),当前无证据不立项。不改 runtime/不打包/不 bump feature_version。产物:`mvp/scripts/research_phase24_1.py` + `research_phase24_1_data.py`、`work/phase24_1_probe_results.json`、`work/phase24_1_data.json`、FINDINGS `mvp/benchmark/user_case/phase24_1/FINDINGS.md`。

> **▶ 交接执行单(2026-08-31)已完成并闭环 = NLE 自动验证通道定案:PR CEP 建成并验收 PASS(119/119),Resolve 免费版路死**:
> 起因:剪映(CEF)桌面自动化不可用 → 寻找"能程序化读时间轴"的 NLE 做导出自动验收。两条路实测: