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

> **▶ 2026-10-06（续61 补八）— 预览联动的真浏览器前提已实测确证（补三/补四/补七挂着的目检项闭合）**
> 现役组件 `VideoComparisonPlayer.vue` 被临时探针页直接挂载在 vite dev + Chromium 里跑真 `<video>`
> （合成两路 3.000s / 6.000s），在 `pause` 触发瞬间打印 `el.ended`。四条全过：
> ① **顺序是 `pause` 先于 `ended`**，但那一刻 `el.ended` 已为 `true` ⇒ 现役实现读**元素属性**
> （`VideoPlayer.vue:75` `if (v?.ended)`）成立。**要是当初写成「`ended` 回调置标记、`pause` 读标记」，
> 在本顺序下直接失效** —— 前提方向与设想相反，实现恰好走对，这是本轮唯一硬收获；
> ② 一路先播完不拽停另一路（ed 停后 og 仍放到 4.017s，6.000s 才停）；③ 手动暂停仍两路同停
> （`el.ended=false` 走 `reportPause`）；④ 图标真值 + 播完重播从 0 起。
> 事件序列留证 `work/preview_coupling_probe_20261006.md`；探针页/临时素材/临时 dev 日志**已删**，
> 工作区无残留。**口径边界**：测的是 Chromium 不是 Electron 34 内核，素材是合成片不是真项目
> ⇒ "打包态 Electron + 真素材再目检一次"仍未做（要用户在 r13 顺手确认一次即可销）。
> **待拍板 → 2026-10-06 用户裁决（本轮）**：**① mac 严格惰性再 dispatch 先不做，留着待办**
> （mac-alpha 继续用预钳制版；勿再主动排批、勿重复解释 ≈180 macOS 分钟这笔成本）；
> ② LOC-1107 拆码、③ 下一刀 A1→A2 ∥ A3、④ 性能口径三处对齐 同样先不做。
> 唯一未拍板 = ⑤ 竞品 opcode 通道可行性。
> **本会话新增未提交**：档案三件（STATE/TODO/CHANGELOG）+ 上述留证文件；git 提交等口令。
>
> **▶ 2026-10-06（续61 补七）— 现役包 = r13；EOF 兜底改严格惰性并有真实片判决**
> 三件事收尾（细节全在 `.agent/CHANGELOG.md` 续61 补六/补七）：
> ① **mac 包体门槛三轮转正**（#26 脚本自身相对路径 bug → #27 抓到**真缺陷** ISC 片尾越界
> t=20.500 vs 20.0s → #28 `FAILED=0`，publish 现受门槛管；mac zip 913MB 含 patch/ISC 权重）；
> ② **LOC-1107 收口到解码层**，且**预钳制版已被撤**：`grab_frame` 只在「原始 t 真的取不到帧
> 且 `t > cap`」时用 `_grab_last_frame()` 返回片内最后一帧（cap 只当判据，不当钳制值 ——
> 它是末帧时间的**下界**，预钳会把 `(cap, 时长]` 内本来正确的帧换掉）；`grab_frames` 取消预钳与别名键；
> ③ **两条实测判决**：真实片 test1 对照修复前基线 = **55/55 段、strip 后 identical、兜底命中 0 次**
> （⇒ 补六"免跑四片"的构造性论证这轮有背书，其余三片仍是论证不是实测）；
> 包体三世代同素材 `short20`（20s 原片 + 其 6–12s 剪辑）= **r11 failed LOC-1107 / r12 completed 1 段 /
> r13 completed 1 段** ⇒ 这条从续61 补一挂到现在的"包体级判别未实证"**已闭合**。
> 现役包 = `mvp/ui/release/Video-Locator-win-x64-20261006r13.zip`（981,636,653 B / 7,078 条目；
> backend.exe 77,445,580 B `sha16=52ca8c225bbc3683`）；accept/三防/启动冒烟 **FAILED=0**；
> 门禁 后端 **546** · API **105** · FFmpegIO **21** · vitest **142** · 双 typecheck 干净。
> **判卷抓手已修**：`attr_packaged_headless.py` 的 `[done]` 现在打 `status/err`，`package` 字段
> 按实测 backend.exe `sha256[:16]+size+mtime` 生成（此前硬编码 "r4" 害我把 r11 的 failed 读成 0 段）。
> **分发包保留**（口令"只留 r10、r11、最新包"）：r8/r9 已删，r13 过验收后 r12 已删。
> **仍开放/待拍板**：① mac 现役 = 预钳制版（严格惰性未上 mac，是否再 dispatch ≈180 macOS 分钟）
> ~~② 预览联动的真浏览器目检~~（**已由补八实测确证闭合**，剩打包态真素材一次目检）
> ③ LOC-1107 是否拆码 ④ 下一刀 A1→A2 ∥ A3
> ⑤ 性能口径三处对齐（PRODUCT_INTRO 19~31 vs 现役）⑥ 竞品 opcode 通道可行性。

> **▶ 2026-10-06（续61 补五）— mac 包体验收脚本 + publish 门槛已接线（未跑过真 mac）【已销项，见补七】**
> 动因：mac 包过去只验「构建成功 + 静态库 + ad-hoc 签名」，从未做包体实测；且 `macos-package`
> 最后一步是**构建成功即 `gh release upload --clobber` 到公开 rolling tag `mac-alpha`**
> （实测该 release 现有两资产，旧 `Video.Locator-0.1.0-arm64-mac.zip` dl=12）。
> 新 `mvp/scripts/accept_packaged_bundle_mac.py`（Windows 版绑死 win-unpacked/backend.exe/三条 DML
> 判据不可复用）= 结构+资产 sha256 · **patch/ISC 在位（缺=FAIL，可显式豁免留痕）** · 起包 ·
> 无令牌 401 负例 · 包内 ffmpeg 现造素材端到端 locate + **中文路径** · `backend selected=mps`。
> CI 已插在 upload 之后、publish 之前 ⇒ **FAILED>0 就不再对外发布**。
> ⚠️ **第一次 dispatch 预期会红**（不是脚本 bug）：`build_backend_mac.py` 从未复制 patch/ISC ONNX，
> mac 包至今缺这两份资产（= 当年 Windows 精排静默回退 CPU 慢 2.6~3.9× 的同型缺口，mac 未收）。
> 收口办法 = 两资产随包（ONNX provider 列表本就含 CPU 兜底）。
> ⚠️ 本脚本**从未在真 macOS 执行过**，只过了 py_compile + 平台守卫 + 接口契约核到源码。
> 待拍板：是否 dispatch 验证本门槛（≈180 macOS 分钟，预期红）· 是否补 mac 精排/ISC 资产 ·
> r11 档案与 LOC-1107 拆码 · 下一刀 A1→A2 ∥ A3 · 性能口径三处对齐 · 旧包删除授权。

> **▶ 2026-10-06（续61 补四）— r11 已出包（三项修复入包），包体内实测进度分级；现役包 = r11【下个对话从这里读起】**
> 现役 = `mvp/ui/release/Video-Locator-win-x64-20261006r11.zip`（981,635,025 B / 7,078 条目，head `db0d86d`）；
> r10/r9/r8 留作回滚（未做删除授权）。验收：accept **FAILED=0**（冒烟 26.5s）· 三防 **FAILED=0** ·
> 启动冒烟 Electron4+backend1 · zip 抽验可开读；backend.exe 尺寸逐代递增（r9 77,440,920 →
> r10 77,441,843 → r11 77,442,958）。
> **包体内两条硬证**：① 进度切片 —— 包内 backend headless `syn` 事件进度序列 =
> **92.0→94.0→95.0→97.0→100**，正好落在新切四段边界（旧代码会整片停 92.x）；
> ② 预览联动 —— 包内 `resources/app/dist/assets/ResultsPage-xeWnraUr.js` 含压缩后的 `ed:!1,og:!1`
> （= `initialSyncState`），与 vite 产物同哈希 ⇒ 修复在包里。
> **仍开放三件**：① 预览 pause/ended 顺序前提**没在真浏览器目检**；② LOC-1107 包体级判别复现仍缺
> 用户 16:34 那条真项目重跑（我构造的两条素材在 r9 包上不崩）；③ macOS CI run #25（head `db0d86d`）待收。
> 待拍板：LOC-1107 是否拆码 · 下一刀 A1→A2 ∥ A3 · 性能口径三处对齐 · 旧包（r8/r9/r10）删除授权。

> **▶ 2026-10-06（续61 补三）— 预览"一路播完拽停另一路"+ 时长 00:00 已修（UI，未提交）【下个对话从这里读起】**
> 根因：`VideoPlayer` 把 `<video>` 的 `pause` 一律上报成"用户暂停"，而**播到末尾也会 fire pause**
> ⇒ 剪辑放完 ⇒ 共享 `playing=false` ⇒ 原片被 watch 暂停（症状单向可佐证：原片那路当时根本没接
> `@playing-change`）。时长 00:00 = `duration` 只在 `timeupdate` 更新 + `preload=metadata` 未开播。
> 修：元素 `ended` 标志区分两种 pause（播完改发 `ended`）+ 补 `@loadedmetadata` + 按钮图标用本地
> `showPlaying`；联动判定抽成纯函数 `src/utils/previewCoupling.ts`（手动暂停=两路停；
> 单路播完=另一路继续，两路都完才停；重播清标记），两路都接 playing-change + ended。
> 门禁：typecheck 干净 · vitest **142**（+5 判别锁）。**未验证**：pause/ended 先后是规范前提，
> 没在真浏览器跑过 ⇒ 需 dev 目检或 r11 实测。
> 本会话累计未提交 = 进度切片(后端5文件) + 计时(UI store+页面) + 本次预览联动 + r10 档案；
> **r10 包不含这三项**，要见效需 r11。

> **▶ 2026-10-06（续61 补二）— 进度条 92% 卡死 + 计时 00:00 已修（源码已改，未提交；r10 包不含）【下个对话从这里读起】**
> 用户报打包态「镜头分析 92.1% 00:00」长时间不动。两条根因：
> ① REFINE 的 (92,6) 区间被**修复链/拆分/patch 逐段/ISC 逐段**共用同一条 0→1 ramp，而修复链
> 整段只发一条 `current=0` 事件 ⇒ 停 92.1 数分钟，后面逐段又被单调钳制挡住；
> ② elapsed 是 `AnalysisPage.vue` **组件本地** setInterval 计数 ⇒ 换页/重挂即归零不再走。
> 修：`ProgressEvent.phase`（空=旧行为逐位不变）+ `worker._PHASE_RANGES` 切四段互不重叠
> （fix 92-94 / split 94-95 / patch 95-97 / isc 97-98，带 phase 时 current 按**已完成数**解释）
> + 修复链补 5 个粗步事件 + 起点时刻移进 store `taskStartedAt`（页面按 Date.now() 差值现算）。
> 门禁：后端 **543 OK** · API **105 OK**（含"无 phase=92.1 旧行为"回归锁）· vitest **137** ·
> 双 typecheck 干净。纯展示层 + 事件 schema，**零定位语义变更**（无新旋钮/GT/feature_version）。
> ⚠️ **现役 r10 包不含此修复**（17:31 构建，只含 LOC-1107）⇒ 要让包内进度动起来需 **r11**。
> 待拍板：① 提交本批（源码 5 文件 + UI 3 文件 + 新测 2 个 + r10 档案）② 打 r11
> ③ LOC-1107 是否拆码 ④ 下一刀 A1→A2 ∥ A3 ⑤ 性能口径三处对齐。

> **▶ 2026-10-06（续61 补一）— r10 已出包（含 LOC-1107 修复），包体验收全过；唯一未闭合项=包体级判别复现【下个对话从这里读起】**
> 现役包 = **`mvp/ui/release/Video-Locator-win-x64-20261006r10.zip`**（981,634,169 B / 7,078 条目，
> 含 `3a6aa4c` 片尾钳制）；r9（11:32）+ r8 留作回滚。验收：`accept_packaged_bundle.py` FAILED=0
> （资产 sha256 · 冒烟 30.3s · DML 生效 · 精排/ISC GPU 未回退）· 三防冒烟 FAILED=0 ·
> 启动冒烟 Electron 4 + backend 1 存活 25s · zip 抽验关键条目可开读 ·
> 包内 backend.exe 尺寸 77,441,843 ≠ r9 77,440,920（含修复的硬证，包内无散装 pyc 故不能用字符串 grep）。
> macOS CI run #24（head `137866f`，**用户手动 dispatch**）= **Ran 543 → OK (skipped=45)** 三 job success。
> ⚠️ **未闭合**：我造的片尾素材（末 6s 切片、126.8s 解说 vs 63s 原片）在 **r9 包上不崩**
> ⇒ 包体级"修复前必崩"没实证，本次修复的证据面 = 源码级真 FFmpegIO A/B + 543 单测 + CI 543。
> **请用户拿 16:34 那次失败的同一项目（31 段解说 vs `src_part1.mp4`）在 r10 里重跑一次**作判别测试。
> 待拍板：r10 档案与 `attr_packaged_headless.py` 新用例（`eof63`/`eof126`）的 git 提交；
> LOC-1107 是否拆码；下一刀 A1→A2 ∥ A3；性能口径三处对齐。

> **▶ 2026-10-06（续61）— LOC-1107 片尾越界真缺陷已修 + 竞品入口/资源层整值读完（9 条新形态）【下个对话从这里读起】**
> **(a) 真缺陷修复（源码已改，未提交）**：打包态 r9 跑 `work/e2e_r3/src_part1.mp4`（**63.000s**）时
> 整条 locate 失败 = `MediaError: grab_frame returned no frame at t=63.500`。
> 根因两条叠加：① `patch_refine` 精扫窗 `g1 = mid + REFINE_WIN_S(5s)` **无任何片尾边界**
> （`grep duration engine/localization/patch_refine.py` 修复前 = 零命中）；② `grab_frames` docstring
> 承诺的"超片尾逐帧回退"不成立——补帧走 `FFmpegIO.grab_frame`，取不到帧即 **raise**（`ffmpeg_io.py:177`）
> ⇒ 单点越界把任务打死。
> 修法 = 上游钳制（新增 `apply_patch_refine(source_duration_s=…)`，生产传 `bundle.meta.duration`）：
> 窗尾 `min(g1, 片尾)`，钳后 `g1<=g0` 的候选跳过（该段原样返回）。**刻意不用索引末点**（比片尾早 ~1s，
> 会削掉原本成功的窗 = 语义变更）。两处假承诺注释已改（`ffmpeg_io.py` docstring、`locator_service.py:2517`）。
> 验证：后端 **543 OK (skipped=2)**（+3 新锁：钳制生效 / `dur=None` 旧行为逐位不变 / 窗整体越界→原样返回）
> · API 104 OK · 真素材 A/B（`work/fix_eof_ab_probe.py`）= 未钳制臂复现抛错、钳制臂 OK（最大请求 t=62.48）。
> **零语义是构造性论证**（钳制只作用于 `t >= 容器时长`，而这类点过去必抛 ⇒ 过去能跑通的一帧不动），
> 故**未重跑四片**；残留下界 = [视频流末点, 容器末点) 的一帧缝（实测本例 0.019s，属既有行为未扩大）。
> ⚠️ **验收盲区登记**：四片回归素材母片均 ~2h，"短原片 + 段落落片尾"从未进集 ⇒ 这类越界过去抓不到。
> **(b) 竞品入口/资源层读完**（`FINDINGS_CUTMATCH_ENTRY_LAYER_20261006.md`）：清点发现续37 只挖了
> 9,850/37,041 值（26.6%），第一方另 **10,721 值 / 74 模块从未读**；本次整值读 17 模块 3,634 值。
> 结论 = **精度侧确实仍无肉**（matching 整族 58 模块全覆盖，"已挖干净"在其范围内成立），
> 但**工程/UX/售后侧出 9 条形态**，4 条直接回答我方挂着的待办：720p 代理 + `is_proxy_frame_accurate`
> 帧精确门禁（CFR 代理项）、按可用内存收缩 batch/预取 + `low_memory_mode` 上报（memmap 项）、
> 子进程 `CUTMATCH_DEVICE_CONFIRM=` 标记行回报真实设备（UI-P3 徽标误标的根因级解法）、
> 阶段延迟发布 + `heartbeat`（UX-P1 92% 卡感）。另 `xml_only` 在竞品是**入口开关不是失败兜底**
> ⇒ 「竞品渲染失败仍出 XML」的口径要重问；macOS 打包有中文路径 locale 明文教训（对今天刚出的
> mac artifact 直接相关）。口径类收益 = 竞品默认 `matching_mode=standard` 从反推变直证。
> **(c) 待拍板**：① **git 提交**（本轮源码 = patch_refine/locator_service/ffmpeg_io 注释 + 3 测试；
> 档案 = 新 FINDINGS + 两份清点产物）；② 是否把 LOC-1107 按竞品形态**拆码**（MEDIA-002 式一码一因，
> 触 `errors.py` 码规则=只增不改）；③ 下一刀 A1→A2 ∥ A3 仍未拍板；④ 性能口径三处对齐仍挂。
> **(d) 已更正留痕**：`model_lease` 我上一轮口头猜"GPU 模型占用治理"**错**，入口层证据 =
> 授权租约（`verified_model_lease`/`missing_model_lease`）；另本轮先前"27% 已读 ⇒ 精度结论不成立"
> 的质疑被清点数据削弱（三方噪声占 44.5%），已按实测改口。

> **▶ 2026-10-06（续60）— stable 修复双链验证 PASS（四片零差异 + macOS CI 全绿）**
> 续59 两项未完全部结案，**无阻塞、无需回滚**：
> ① **四片零差异回归 = PASS**（进程当时未断，本会话按 log 接管到 `ALL_DONE`）：
> `work/stable_sort_regress/summary.json` 四片 **`strip_identical=true` / `n_diff_rows=0`**
> （2mkv 1584.3s · test1 1202.5s · test2 1642.6s · test3 1548.5s；对照
> `work/defaults_flip_ab/<case>/on.results.json`）⇒ **stable 排序生产不变性成立**。
> ② **macOS CI 全绿**：run 37425131410（#23，head `eded658`）`mvp-tests-macos` 实测
> **Ran 540 tests → OK (skipped=45)**，`mps-poc`/`macos-package` 亦 success ⇒ 5 失败已修。
> ⚠️ **更正（重要，影响后续操作习惯）**：**push 不会触发 macOS CI** —— 该 workflow `on:` 只有
> `workflow_dispatch`（刻意省 macOS runner），验证跨平台须**手动 dispatch**（本次经用户口令执行）。
> 另一处错记：STATE「明细 CHANGELOG 续59」指向空条目，已在本文件补记「续59 补记」。
> 未动的平局敏感点（漂移时首选排查面，改动须重走四片零差异）：`locator_service.py:1863`、
> `evidence_localize.py:168/198/493`、`montage_localize.py:57`、`offset_vote_prior.py:123`、`retrieval.py:50`。
> **待拍板不变**：① 工作区 git 提交（本会话仅档案文档；铁律「git 我喊你交你再交」）
> ② 下一刀 A1 降子补记分 → A2 异源选优 ∥ A3 导出含子（`RESEARCH_PROPOSAL_NEXT_CUT_20261006.md`）。

> **▶ 2026-10-06（续59）— macOS CI 5 失败修复已推送；四片零差异回归在跑【销项：见上方续60】**
> CI（macOS runner）在推送后跑全套抓到 5 失败（patch_refine×2 + isc_l2_index×3，Windows 全绿）。
> **根因**：numpy SIMD 快排对精确平局跨架构顺序不同 ⇒ `_clusters` 候选代表帧不同 ⇒ 下游
> 精扫窗/宽扫排除集漂移；生产真实 sims 连续浮点无精确平局，产品语义不受影响。
> **修复（已提交推送 3230fad）**：两处 argsort 加 `kind="stable"` + patch 两断言更新
> （E2 代表帧 112 ⇒ start 110）+ isc_l2 夹具真峰移库外 139-141（采纳决策与平局顺序无关）。
> 后端 540 全绿（Windows）。**未完项 → 2026-10-06 续60 全部结案**：
> ① 四片零差异回归 **PASS**（`work/stable_sort_regress/summary.json` 四片 identical=true / diffs=0）。
> ② macOS CI **不是 push 自动触发的**（workflow 只有 `workflow_dispatch`）——本会话经口令手动 dispatch
> 后 run #23 全绿（Ran 540 → OK, skipped=45）。
> ③ 归档销项已完成；剩余平局敏感点（evidence_localize:168 / locator_service:1863 等）本轮未动、未需要。
> 明细 CHANGELOG「续59 补记 + 续60」（续59 当时漏写 CHANGELOG，已补）。

> **▶ 2026-10-06（续58 补一）— r9 包真机全链复核 = PASS
> 口令「跑吧」：`attr_packaged_headless.py test1`（包内 backend.exe headless；**脚本 env 补齐
> `SVL_PATCH_ONNX`/`SVL_ISC_ONNX` 注入对齐 main.ts**——r3 时代旧跑手缺这两项，不补会复现
> 精排静默回退 CPU 事故）⇒ wall **1196.9s = 19.9min**（实验室同代码态 1320.5s，headless 无
> UI 观察侧，方差内）· 55 段 task completed 零错误 · DirectML 生效（无回退）· 索引复用 VALID ·
> 轮询 p50 4.7ms。**最硬一条：包内结果 vs 实验室 defaults_flip_ab/test1/on 臂 strip 后
> 逐字节 identical = True** ⇒ r9 包 = 实验室同语义，三旋钮新默认在包内正确生效。
> 阶段观感：逐段定位 ~7s/段 → REFINE ~10min，进度通道全程有消息（续40 修复生效）。
> ⚠️ 包 = 未提交工作区构建 ⇒ **git 提交前勿再改工作区**。
> **待拍板**：① 工作区 git 提交 ② 下一刀拍板（A1→A2 推荐 ∥ A3 产品选项，见 RESEARCH_PROPOSAL_NEXT_CUT_20261006.md）。

> **▶ 2026-10-06（续58）— r9 出包完成 + 验收全过**
> 口令「出包」：`build-release.ps1` 四步全过（首跑败于旧 win-unpacked 文件被占用，清进程删目录
> 重跑即过）→ `accept_packaged_bundle.py` **FAILED=0**（backend.exe/patch/ISC sha256 全过 ·
> 包内冒烟 33.9s≤75s · DirectML 生效 · 精排 GPU 未回退 · ISC GPU）+ **启动冒烟 PASS** +
> zip 抽验（936MB/7078 条目/CRC OK/main.js+preload+渲染层+三模型资产全在）。
> **`mvp/ui/release/Video-Locator-win-x64-20261006r9.zip` = 现役包**：三旋钮新默认
> （定位 15~31min/片）+ UI 五件修复进包。release 现役 = r8（回滚）+r9；r7 已删（2026-10-06 用户口令「留r8删r7」，1.68GB 释放）。
> ⚠️ 包 = 未提交工作区构建 ⇒ **git 提交前不要再改工作区**（保包↔提交一致）。
> **待拍板**：① 工作区 git 提交 ② r8 删除授权 ③ r9 真机全链复核 ④ 算法下一刀立项。

> **▶ 2026-10-06（续57 夜间批二）— 计划项 1「ISC margin 门标定」= 判负关闭（已回滚）【从这里读起】**
> 按「按你的计划来」执行计划项 1（原 ED 子镜头对齐 → 材料复读修正为 ISC margin 门标定：
> t1r08c/t1r12a 探针 margin 0.0457/0.0391 卡 0.05 门）。两级探针后**判负关闭**：
> ① 全量 0.035 臂（2mkv 实跑）读图 = 1 真增益（row23 近场 1.5s）+ **1 真损失**
> （row77 0.9s 窄段 HIGH 被远跳 56.6s）⇒ 亚门分不可作远距重锚证据；② 近场限定设计在
> 实现+单测阶段**机制否证**——`_score_mid` 评分窗（±(w/2+1.5s)）内取 max ⇒ 近场峰被主分
> 吸收 margin 恒 0，无可达面；探针点评分 vs runtime 窗 max = 口径错位教训。
> **处置**：isc_refine/config/locator_service/单测全部回滚（判负不进 runtime 不留通道），
> 后端 **540 OK** 复验；探针留证。真救回需换评分几何（主分排除峰侧/锚点级），与「扫描行为
> 缩减」同层级立项。明细 FINDINGS_NEXT_DIRECTIONS §7。
> **工作区（仍未提交未打包，按口令）**：三旋钮翻默认 + 回归锁 + pd__lib 修复 + 探针
> （defaults_flip_ab / fp16_ab / isc_margin35 / isc_subgate_ab / rerank_grid_ab 路径修正）。
> **醒来待拍板**：① 本工作区 git 提交（含三旋钮翻默认）② r9 出包 ③ 下一刀
> （ED 子镜头对齐仍待真正设计 / mkv 建表异步化需产品口径 / 扫描行为缩减）。

> **▶ 2026-10-06（续57 夜间批次）— 三旋钮已翻默认（四片 PASS）+ 真机复核过 + FP16 判负【从这里读起】**
> 按口令「翻→真机复核→列方向评估→按计划执行；**不推 git 不打包**」完成：
> ① **翻默认**：前置补齐联合双臂四片（`probe_defaults_flip_ab.py`）全 PASS —— test2 **1.294×**
> 0/67 · test3 **1.276×** 0/103 · 2mkv **1.162×** 0/84 · test1 0/55 ⇒ `patch_refine_grid=True` ·
> `rerank_grid_grab=True` · `cluster_workers=4` 已生效，**三指标 136/131/138/4·9 自动成立**，
> 后端 540 OK。**新默认态 ≈ 15~31min/片**（on 臂实测 22.0/27.0/30.1/31.6）。
> ② **真机复核**：UI dev 浏览器目检续57 四件全过 + **抓修第 5 处同类溢出**（`.pd__lib` grid
> min-width:auto 面板撑破，已修+复验）；vitest 136 · 双 typecheck 绿。
> ③ **FP16 探针（L4 销项）**：ISC **1.806×**（cos 0.999992）但 DINOv2 CLS 0.845×（更慢）/
> patch dual 1.014×；采纳 = feature_version bump+全量重建换 ~2.5% 全链 ⇒ **判负（有据）**。
> ④ **方向评估**（`FINDINGS_NEXT_DIRECTIONS_20261006.md`）：抓帧三桶已到解码地板 ⇒ 纯性能侧
> 挤干（账单拟合实测）；剩余杠杆 = 扫描行为缩减（语义变更）。建议排序：ED 子镜头切分对齐
> （精度，救 t1r08c/t1r12a part 族）> mkv 建表异步化 > r9 出包 > 扫描缩减 > 代际差穷举。
> **工作区未提交**（按口令）：config 翻默认 + 回归锁 + pd__lib 修复 + 3 探针。**未打包 r9**。

> **▶ 2026-10-06（续57）— UI 真机反馈四件（卡片溢出/新建直进构建页/剪辑可删/按钮间距）= 完成**
> ① `ProjectCard.vue` `.pcard` 加 `min-width:0`（grid 子项 min-width:auto 是溢出根因）+「剪辑」行
> 只显示文件名；② `useCreateProject.ts` 重写 = 新建项目**不再弹对话框选剪辑视频**，直接建空项目
> 跳 ProjectDetailPage 自选素材（HomePage/ProjectsPage 两入口同口径；2026-09-29 断链根源随流程
> 删除而消失）；③ store 新增 `removeEditedVideo` + 剪辑列表行加同款 ×删除按钮；④ `.pd__pickrow`
> 加 flex+gap。门禁：vitest **136 全绿** · 双 typecheck 干净；纯 UI 层零后端改动。明细 CHANGELOG 续57。
> **✅ git 已提交推送**（2026-10-06 续57，用户口令「先提交」）：`2d2c993..1a697ec` 三笔 =
> `6fae6a7` fix(mvp) 续55~56 源码+测试 · `f78e0f2` chore(scripts) 探针+FINDINGS ·
> `1a697ec` feat(ui) 续57 + docs(agent) 档案。工作区清零。
> **待拍板/等口令**：翻默认三旋钮（各需三片双臂）/ r9 出包 / UI 真机复核。

> **▶ 2026-10-06（续56）— other 桶网格接线落地：test1 双臂 1.132× 零语义【下个对话从这里读起】**
> **做了什么**（按续55「下一刀候选」执行，源码已改未提交）：新旋钮 `pipeline.rerank_grid_grab`
> （**默认关**）= locate 主循环两处源片重排窗抓帧改走网格抽取——① patch v2 近场池
> （`_patch_nearfield_rescue`，±30s@4s 均匀网格，other 桶主力）② 字牌锚定源窗
> （`_apply_text_anchor`，每窗 4 个 `_rep_times` 均匀点）。与 `patch_refine_grid` 语义解耦。
> **验证**：test1 同脚本紧邻双臂（`work/rerank_grid_ab/`，DML 断言）off **1601.0s** →
> on **1413.7s** = **1.132×**，strip 55 段 **0 差异** + 信封一致 ⇒ 端到端零语义；与账单预期
> 吻合（other 桶 294.4s≈22%，管道量 ÷~100）。**续54~56 干净双臂最大一刀**（对照 1.068×/1.071×）。
> 门禁：单测 +7（近场池 4 + 字牌 2 + 默认锁 1），后端全套 **540 OK (skipped=2)**。
> 明细 FINDINGS §5.12；探针 `mvp/scripts/probe_rerank_grid_ab.py`。
> **待拍板/等口令**：git 提交（续54~续56）/ 翻默认三旋钮（`patch_refine_grid` ·
> `cluster_workers` · `rerank_grid_grab`，各自还需三片双臂）/ r9 出包。
> 未改 GT / 未 bump feature_version / 现役默认态行为不变（三旋钮默认关/1）。

> **▶ 2026-10-06（续55）— `%.6f` 真缺陷修复 + 三刀提速（并集才是主力）：现役默认态 19~31min**
> ① **账单换位**（`probe_locate_stage_timing.py` 阶段归因 + `windows_*.jsonl` +
   `analyze_window_merge.py`）：窗 spawn 已由 4600 降到 **680 摊在 561 次调用（≈1.2 簇/调用）**，
   固定开销 ~0.17s/次，成本改由**解码跨度主导（0.164s/解码秒）** ⇒ 减「解码秒/管道量」是主路
   （⚠️ 本条初版据此判「并集收益有限」，已被 ④c 三片实测推翻）。**CPU 抓帧 1043s=78% vs DML 推理合计 ~239s=18%**
   （更正续54「GPU 仅 2.4%」= 只数了 `backend.embed_frames` 一个入口，漏 patch/ISC）。
   ⚠️ 假读数留痕：按 `id(frame)` 判「重复嵌入」dup=1463/2130 是**假信号**（numpy 对象释放后
   id 会被新对象复用），按 round(t,3) 键实测重复率 0.00 ⇒ 嵌入去重方向关闭。
> ② **真缺陷已修**：`FFmpegIO._grid_select_expr` 用 `%g` 格式化簇起点 ⇒ 三位小数被截成两位
   （3638.351→3638.35），select 窗起点偏离目标 ≤0.005s ⇒ 跨源合成 micro 实测修复前
   test2 1/300 · 2mkv 6/300 · test3 6/300 **取到不同帧**（0.5s 护栏抓不到，偏差 <0.5s）；
   改 `%.6f` 后 **四片 1200/1200 逐字节同帧**。影响面 = 所有带小数锚点的网格调用
   （宽扫粗扫 `round(wlo+i*2,3)` / 精扫 / L2 建表）；**L2 索引标签全整数秒 ⇒ 已入库索引不受影响、
   无需重建**。端到端零语义（无旋钮直接生效，四片）：test1 0/55 · test2 0/67 · test3 0/103 · 2mkv 0/84。
> ③ **三项提速**：(a) 新旋钮 `pipeline.patch_refine_grid`（**默认关**）= patch 候选窗网格抽取
   （真实窗形状 micro 2.28× · 120/120 同帧；跨源 1.86~3.29×；test1 同脚本双臂
   1384.2→1296.0s = **1.068×** + strip 0 差异）；(b) `patch_refine` **段内候选窗并集**（无旋钮，
   纯调度；**网格形态不并集**——select 只服务单一相位）test1 与并集前臂 strip 0 差异；
   (c) 新配置 `media.cluster_workers`（**默认 1 = 现役串行**）+ `grab_frames` 簇间并发
   （失败簇隔离 + 逐帧回退语义不变），test1 双臂 1155.4→1078.9s = **1.071×** + strip 0 差异。
> ④ **现役耗时**：test1 = **18.0min**（本会话开始时 21.5min）；三片参照
   test2 38.0 / test3 40.3 / 2mkv 31.3min（并集已在三片验证，见 ④c；`cluster_workers` 三片未验）。
   ⚠️ 口径：test1 同代码态跨 run 实测 1155.4/1287.3/1384.2s ⇒ **方差 ±18%**（大于既往 ±10%），
   提速数字只认同脚本双臂。
> ④b **硬解穷尽（AMD 三入口全判负/不可用）**：**d3d12va 本 build 解不出帧**（三片 hw 可用窗
   **0/6**、md5 0/6；单窗真实报错 `hardware accelerator failed to decode picture`），且解码地板
   sw/hw = **0.67~0.78×**（test1 3.94 vs 5.07s · 2mkv 2.20 vs 3.31s · test2 4.00 vs 5.17s）；
   **dxva2 同样 0/6 出帧**，地板更差 = **0.38~0.50×**（4.98 vs 9.89s / 2.6 vs 6.8s / 4.49 vs 9.5s）；
   唯一能出帧的 d3d11va 已由续54 实测净 **0.42×**。⇒ 日志里 31~148× 全是**空输出的假速度**；
   硬解要回本必须换形态（帧不回 CPU 的 GPU 前处理链 = 重构级）。macOS VideoToolbox 仍未测。
   产物 `work/hwaccel_probe/probe_hwaccel_window_{d3d12va,dxva2}.json`。
> ④c **并集三片回归 = PASS，且推翻本会话早先判断（2026-10-06 00:28）**：
   `work/spawn_consolidation_regress/union_*` 对照本批 postfix 臂（同代码态，仅差并集）——
   test2 **1862.8s**（2423.4 → **1.223×**）0/67 · test3 **1861.6s**（2499.9 → **1.298×**）0/103 ·
   2mkv **1407.2s**（1971.9 → **1.333×**）0/84 ⇒ `all_identical=True`，**四片零语义**。
   ⚠️ **更正本会话早先结论「并集在串行下几乎没肉」**：那是在 test1 上算的（该片候选窗重复率
   0.00），另三片候选窗重叠度高 ⇒ 并集省 1.22~1.33×。**教训：单片形状不能外推成结论**。
   口径标注：这三对是**跨 run** 对照（参照臂 = 本会话内刚测的同代码态臂，三片同向、幅度一致），
   不是「同脚本紧邻双臂」⇒ 幅度按 ±18% 方差读，方向可信。
> ④d **现役默认态耗时（含 `%.6f` 修复 + 段内并集；两新旋钮仍默认关）= 19~31 分钟**：
   test1 **19.3** · 2mkv **23.5** · test2 **31.0** · test3 **31.0**（min）。
   本会话开始时同四片为 21.5 / 31.3 / 38.0 / 40.3 ⇒ **一天内约 1.3×**。`PRODUCT_INTRO` 已同步。
   再开 `media.cluster_workers=4` 预计还有 ~7%（test1 同脚本双臂实测 1.071×，三片未验）。
> ⑤ 门禁：后端全套 **534 OK (skipped=2)**（+8：patch 网格 3 / 并集 2 / 簇并发 3）。
   明细 = `FINDINGS_COST_STRUCTURE_LEVERS_20261003.md` **§5.7~5.11**；产物
   `work/{locate_timing,patch_grid_shape,patch_grid_ab,perf_ab,spawn_consolidation_regress,hwaccel_probe}/`。
> **待拍板/等口令**：git 提交（续54~续55，24 个改动/新增文件，建议拆源码+测试 / 研究脚本 / 档案 三笔）·
   翻默认 `patch_refine_grid`（三片双臂未跑）/ `cluster_workers`（三片双臂未跑，各约 2h GPU）· r9 出包。
> **已结案**：段内并集三片回归 **PASS**（④c，`union_*`）；`%.6f` 修复四片回归 **PASS**（②，`postfix_*`）。
> **下一刀候选（按账排序）**：`other` 桶 294.4s=22%（逐段 patch 重排窗，跨度中位 24.8s、
   步长恰 4.0s ⇒ 网格抽取最契合）· isc_refine 精扫 264.5s（步长非整数，需先解相位问题）。
> 未改 GT / 未 bump feature_version / 未提交。

> **▶ 2026-10-05（续54）— 定位侧提速第一批：窗 spawn 合并（零语义 1.30×）**
> ① **定位账单定瓶颈**（计时探针补窗 spawn 记账）：窗抓帧 892s=61%，~4600 目标摊大量小窗、
   每窗 spawn 固定开销 ~1s 是主体；GPU 嵌入仅 2.4%。
> ② **路径 A（硬解）实证判负**：d3d11va 窗解码 0.42×（回传开销>收益）；探针修出
   `-copyts + -t = 0 帧` 的 ffmpeg 知识。机制层留档：统一转换链可保逐字节契约（续47）。
> ③ **三件零语义优化落地**：打分批量预取 `_preembed_mids`（每段 6~8 spawn→1~2）·
   `FFmpegIO.metadata` 缓存（省 0.08s×~800）· 精扫网格抽取（新旋钮 `isc_refine_grid_refine`
   **默认关**，单独收益≈0 保留作基建）。后端 **526 OK**。
> ④ **验证**：test1 同条件双臂 off 1671.0→**1287.3s = 1.30×**，三方 strip（合并前基线/
   新 off/新 on）**逐字节全等**。保守口径：跨脚本方差 ±10%，四片回归后定数字。
> ⑤ **四片零语义回归 = PASS（2026-10-05 续54 补，新脚本 `probe_spawn_consolidation_regress.py`）**：
   合并无旋钮直接生效 ⇒ 另三片自证。对照续52-G 常态链臂，现役默认态直跑（DML 断言）：
   test2 2277.9s **0/67 差异** · test3 2416.4s **0/103** · 2mkv 1875.4s **0/84**
   ⇒ **四片逐字节全等 ⇒ 三指标 136/131/138/4·9 自动成立（无需重测）**。跨 run 对照 1.17~1.29×
   （参照臂含争用，**不作干净数字**；干净 = test1 1.30×）。明细 FINDINGS §5.7。
> ⑥ **PRODUCT_INTRO 口径同步（用户令「改吧」）**：高精度全片 27~43min → **21~40min**
   （四片实测 21.5/31.3/38.0/40.3min + 同条件 test1 27.9→21.5）。⚠️ 更正：打包态并非「实验室
   ×1.56」——r8 打包 E2E test1 24.3min 与同代码态实验室 27.9min 同量级（1.56× 属 r3 时代，已过期）。
> **待拍板/等口令**：git 提交（续54）。grid_refine 翻默认（无收益，建议维持关）；
   patch_refine 同款 spawn 合并（下一刀候选）。
> 未改 GT / 未 bump feature_version。

> **▶ 2026-10-05（续53 补三）— E2E 抓到「第二次分析必崩」真缺陷 + 修复；r8 定稿**
> ① **r8 包 runtime 功能确认全过**（探针 `probe_pkg_runtime_features.py`）：fsbrowse 路由 ·
   L2 翻默认行为证据（syn 中自动建索引）· patch/ISC GPU · PYZ 模块齐 · main.js 注入齐。
> ② **E2E 抓到续52-G 潜伏崩溃**：`_isc_l2_validated` 初始化成 `{}`（dict）⇒ `.add` 即崩——
   只命中「加载已存在有效索引」分支（续52-G 复验全走重建故漏测）⇒ **用户第二次分析同一原片必崩**。
   归因靠补的可诊断性修复（worker 异常堆栈落 tasks logger；此前 no-op）。venv 复现 PASS 的
   矛盾由双索引根（Local 无索引走建表）解释。
> ③ **修复**：`set()` + 2 回归测试 + worker 堆栈留痕。后端 **523 OK**；E2E 第 4 轮 **PASS**
   （24.3min/55 段/L2 加载 8221 帧分支/DML）；accept **FAILED=0**；zip 0 缺漏；启动冒烟 PASS。
   **r8 zip 已重打定稿**（04:36，981MB）；release = r7（回滚）+ r8（现役）。
> **等口令**：~~git 提交（续53 修复三件 + 新探针 2 个）~~ **已提交推送**（`6fcf399..3f42e65`：
> fix 7864b33 崩溃修复+堆栈留痕+回归测试 / chore 探针 2 个 / docs 交接；工作区清零）/
> r8 真机 UI 全链复核（可选，headless E2E 已过）。
> 未改 GT / 未 bump feature_version。

> **▶ 2026-10-05（续53 补二）— git 三笔推送 + r8 出包验收全过；release 只留 r7+r8**
> git `199c010..6fcf399`（feat 7c6e485 / chore ee4c58a / docs 6fcf399）已推 origin/master，工作区清零。
> **r8 = `Video-Locator-win-x64-20261005r8.zip`（981MB）**：accept **FAILED=0**（资产 sha256 全对 +
> 包内 backend headless 冒烟 49.6s + DML/精排/ISC 全 GPU + 定位出段）+ zip 完整性（testzip OK、
> 与 win-unpacked 逐文件 0 缺漏）+ Electron 壳启动冒烟 PASS。r6 已删；**release 现役 = r7（回滚）+ r8**。
> ⚠️ 留痕：r7 的 .zip 实为 tar 流（无 PK 头，解包用 tar 工具）；r8 为真 zip（1.8GB→981MB 系压缩率）。
> **待办**：真机端到端复核（r8 包上跑一条真实成片全链，顺带核对 L2 翻默认后的首跑画面索引构建
> 进度文案与 27~43min 口径观感）；mkv 建表异步化（解耦）/ 代际差精确点位穷举（下批）。
> 未改 GT / 未 bump feature_version。

> **▶ 2026-10-05（续53 补一）— L2 翻默认已执行（用户拍板口令「1」）：`isc_l2_index_enabled=True` 生效**
> `config.py` 翻默认（证据链+回退路径入注释）· 回归锁翻转（`test_default_knob_on`）·
> DECISIONS 2026-10-05（续53）落账 · PRODUCT_INTRO 口径同步（高精度全片 45~60min →
> **27~43min**，新增一次性画面索引 5~11min/部原片）· 顺带修 `_ensure_isc_l2_index`
> stat/sha 步骤无保护的生产健壮性缺陷（翻默认后单测暴露 3 例；现与构建失败同语义 =
> WARNING + 回退宽扫）。门禁后端全套 **521 OK (skipped=2)**。
> **生产现役默认态自此 = L1 网格抽取 + L2 画面索引宽扫全开**（严格 136 / 导出实得 131 /
> 场景 138 / 负例 4/9，三指标与基线逐项一致）。
> **待拍板/等口令**：git 提交（续41~续53）/ r8 重打（L2 翻默认 + 建表修复需进包）/
> mkv 建表异步化（解耦，已无性能压力）/ 代际差精确点位穷举（下批）。
> 未改 GT / 未 bump feature_version / 未提交。

> **▶ 2026-10-05（续53）— mkv 建表性能结案（5.01×）+「mkv 慢」错误归因更正；翻默认前置全部清除**
> ① **归因更正**：续52「test1(mkv) tp 建表 3.0 帧/s = mkv+select 解码路径本身慢」不成立。
   真因 = test1-om.mkv **容器时长比视频流末帧晚 8.4s**（音频尾）⇒ 脚本版 builder 尾部 8 个
   死目标各触发一次**整表重试**（每次全片解码 ~350s）≈ 2800s 纯浪费；2.mkv 尾距 0.08s 免疫
   （其 15.7 帧/s 本就证伪「mkv 慢」）；探针实证 select 路径任意位置 22 帧/s、关键帧密度三源同级。
   「大簇优化无效（2.6 vs 3.0）」结论同批作废。
> ② **修复**（`isc_l2_index.py`，runtime/脚本共用）：`_capped_target_n` 按最后视频帧 pts 截断
   （ffprobe 尾扫 0.15s + 双级回退）· 死簇守卫（消除整簇不可取时的潜在死循环）· `c0 += n_c/fps`
   （fps≠1 修正）· 脚本 truepts 分支委托 build_tp_index（删重复实现）。
> ③ **验证**：test1-om tp 重建 **638.3s（12.9 帧/s）vs 3198.1s = 5.01×**，与验收索引
   **times/feats 逐字节相等** ⇒ 续52-F/G A/B 验收与三指标字节等价自动沿用；单测 +3；
   后端全套 **521 OK (skipped=2)**。备份 `work/isc_source_index_backup_20261005/`；
   探针 `probe_mkv_index_build_perf.py`；FINDINGS §5.6.6。
> ④ **对翻默认的影响**：建表一次性代价改写 = mp4 ~5~11min / mkv ~11min/137min 片（原
   「mkv +53min」口径作废）；翻默认 `isc_l2_index_enabled=True` 的性能前置**全部清除**。
> **待拍板**：**翻默认 `isc_l2_index_enabled=True`**（材料齐：A/B PASS 1.44× + 三指标零回退 +
   常态链等价 + 建表性能已结案）。
> **等口令**：git 提交（续41~续53）/ r8 重打 / mkv 建表异步化（解耦，已无性能压力）/
   代际差精确点位穷举（下批）。未改 GT / 未 bump feature_version / **旋钮保持默认关** / 未提交。

> **▶ 2026-10-04（续52 交接 · checkpoint-2026-10-04-2350）— L2 全链路完成（接线+常态链+复验 PASS），待拍板翻默认**
> **本会话（续52A~G）做完全部 L2 项**：
> ① **fresh 双新臂四片 0 差异** ⇒ `grab_grid_decode` 零语义收口；3+5 行差异 = `v2_*` 跨代际
> （初版「整格跳位」归因已撤回）。
> ② **代际差定位（终裁完成）**：cache 重建/窗解码/异实例索引/DML 非确定性全部证伪；
> **闭环 = 续46 窗解码在 test2/test3/2mkv 的未穷举帧差**（test1 全片验证过故零差异）；
> 精确点位穷举留下批（不阻塞）。
> ③ **产品级新发现：双时间系统 ~0.5s 错位** —— `iter_frames` 合成标签比真实 pts 晚半格
> （切点处索引帧≠扫描帧，看图裁决相邻镜头）⇒ **索引构建必须 truepts 化**（已落地）。
> ④ **L2 四件套全部落地**：tp 索引构建（`build_isc_index.py --sampling truepts`）·
> 探针 l2 模式两形态（形态 B = top-5 ±4s 达标）· **runtime 接线（默认关旋钮
> `isc_l2_index_enabled`）+ 四片 A/B PASS（1.44×，三指标 136/131/138/4·9 零回退）** ·
> **常态链（`data/isc_index/` + sha256 失效判定 + locate 内同步自动构建，复验行为等价
> PASS + 修复 builder 全片攒内存 bug）**。单测 6；后端全套 **518 OK (skipped=2)**。
> ⑤ 新增研究脚本：`probe_isc_l2_ab.py`；产物 `work/isc_l2_ab/`（v1 存档 `.v1`）、
> `work/isc_source_index/*.tp.isci.npz`、`work/exp_final_adjudication/`。
> **待拍板**：**翻默认 `isc_l2_index_enabled=True`**（材料齐：验收 PASS + 常态链就绪；
> 代价 = 用户首次分析某源片同步建索引 mp4 +5~8min / mkv +53min 一次性）。
> **等口令**：git 提交（续41~续52 全部，86 文件）/ r8 重打 / mkv 建表性能优化（解耦）/
> 代际差点位穷举（下批）。未改 GT / 未 bump feature_version / **旋钮保持默认关** / 未提交。
> 详见 FINDINGS_COST_STRUCTURE_LEVERS_20261003 §5.5~5.6.5 + CHANGELOG 续52A~G。

> **▶ 2026-10-04（续52）— fresh 双新臂四片全部 0 差异（归因结案）+ L2 首批 PASS【已并入上条】**
> ① **归因结案**：test2 双臂 0/67、test3 双臂 0/103（`ab_test2/ab_test3.json` fresh `reused=false`）
> ⇒ 加 test1/2mkv，**四片 fresh 双新臂全部逐字段 0 差异**，网格零语义收口。归档差 = **`v2_*` 跨代际**
> （vs fresh off 臂：test2 3 行 span / test3 1 行 span + 4 段边界 / 2mkv 1 段拆合；L1 在 off 路径惰性可核；
> test3 首轮「5 行」系行号对齐虚计，键对齐实为 1+4；**具体机制未定位**，候选 edited_cache 跨代际重建等，
> 未做定位实验不下结论）。⚠️ 初版「整格跳位缺陷」归因**已撤回**（FINDINGS §5.5 / CHANGELOG 续52-A 留痕）。
> 提速 test2 1.727× / test3 2.089×（两臂/off 臂与 L2 建表争用）**不作干净数字**，干净口径 = test1 1.27× / 2mkv 1.30×。
> ② **L2（源片 ISC 索引）四片建表 + 探针**：四片索引全建（test1 8221 帧/7.8MB · test2 5051/4.8MB ·
> test3 10177/9.6MB · 2mkv 7668/7.3MB；空闲 28.8 帧/s ⇒ 干净 ≈4~6min/片源）。**原文判据 >2s=0 四片全未过**
> （1/4/3/5 条），但 triage 后「峰不丢」大体成立：离群 = 窗扫复刻塌分（index 贴生产 main）+ 1s 粒度/
> 网格相位行 + 真分歧仅 1 行（test2 seg18，恰为跨代际行）。**接线暂缓**，判据口径改「index vs 现役臂」；
> FINDINGS §5.6.1。
> ①附：**代际差定位（续52-B → 续52-C 终裁已跑，用户令）**：候选①②（cache 重建改字节 / 窗解码字节差）
> **均证伪**（缓存三代际逐字节全同 + 68 点帧级全等）；「v2 异实例索引」「DML 跨实例非确定性」
> **终裁证伪**（Exp-A：隔离目录重建 test3-om 索引与 09-05 逐字节全同）。
> **新发现 = 双时间系统 ~0.5s 错位**（产品级）：`iter_frames` 合成标签（`start + i/fps`）比真实 pts
> 晚 ~半格（两区实测 +0.50/+0.50s，生产 grab_frames 真实 pts 密池定位 cos 0.999），镜头内无感、
> **切点处索引帧≠扫描帧**（cos 0.42）⇒ 解释 L2 seg18 真分歧与索引 matmul 峰位 +0.5s 偏移；
> **L2 接线前置项 = 索引构建 true-pts 化（select 路径）或半格校正**。
> **代际差闭环判定**：8 行 = 续46 窗解码在 test2/test3/2mkv 的未穷举帧差（唯一自洽：test1 全片验证过
> 窗解码 ⇒ 两代零差异 ✓）；v2 目录实例假设降级；精确点位穷举留下批（不阻塞双新臂口径）。
> **✅ L2 前置项已落地（续52-D，仅研究脚本）**：`build_isc_index.py` 增 `--sampling truepts`
> （L1 grab_grid select 抽取，真实 pts + first_ge，产物 `.tp.isci.npz`，片尾守卫）；tp 标签 2781.0 vs
> seek 抓帧 cos=1.0000（seq 0.42）⇒ 双时间系统归一。四片 tp 探针：中位 0.416/0.500/0.188/0.492
> （三片改善），>2s 1/5/2/2 —— 插桩实证 seg18 双方同网格点分数逐字相同（0.3986=0.3986），
> 时间系统贡献归零；残余离群零「索引错」（混叠=索引峰更高 / 窗扫复刻塌分=确定性伪影 / ±2.5s 粒度）。
> **tp 索引具备接线条件**。FINDINGS §5.6.2。
> **✅ 接线形态验证完成（续52-E）**：探针 `--mode l2`，对照 fresh 现役臂。形态 B（top-5 ±4s）
> 达接线可行轮廓：中位 0.50/1.06/0.56/0.53s、>2s 2/4/2/6（2mkv 大离群全消 max 30→4s），
> 成本 ≈45 嵌入/段 = 现役 1/3；残余 = 粒度级 + 采样混叠（FINDINGS §5.6.3）。
> mkv 建表大簇优化无效（2.6 帧/s vs 3.0，mkv+select 解码路径本身慢，一次性 53min/137min 片）。
> **✅ L2 runtime 接线完成 + 四片 A/B PASS（续52-F，默认关旋钮）**：`pipeline.isc_l2_index_enabled`
> （默认 False，knob 关 = 逐位无操作）+ `isc_refine` L2 分支（matmul 粗排 + 真帧精化，margin 门复用）+
> service tp 索引加载/回退。单测 +5；后端全套 **517 OK**。四片 A/B（off=当前代码 fresh 复用）：
> **1.375/1.339/1.630/1.381×，合计 1.44×**；差异 15/309 行（9 行 ≤1.1s，置信 15/15 不变）；
> **三指标 136/131/138/4·9 与基线逐项一致零回退 ⇒ 验收 PASS**。FINDINGS §5.6.4。
> **✅ 常态链落地 + 复验等价 PASS（续52-G）**：`data/isc_index/` + sha256 失效判定 +
> locate 内同步自动构建（异步因 DML 并发风险降为同步，如实记档）；复验抓到并修复 builder
> 全片攒内存 bug（逐簇流式嵌入）；四片新 on 臂与验收臂 strip 后 0 差异 ⇒ 行为等价，
> 三指标字节等价成立。单测 6；后端全套 **518 OK**。FINDINGS §5.6.5。
> **待拍板**：翻默认 `isc_l2_index_enabled=True`（前置仅剩 mkv 建表性能——已解耦可翻后做）。
> **下一步**：① 翻默认等口令；② mkv 建表性能优化（可与翻默认解耦）；③ 代际差精确点位
> 穷举（下批）；git 提交（续41~续52）/ r8 重打 —— 仍等口令。未改 GT / 未 bump
> feature_version / 未翻默认 / 未提交。

> **▶ 2026-10-03（续51 补一）— `grab_grid_decode` 已翻默认 True（用户拍板选项 B）【归因已结案，见上条】**
> 依据：① 帧级逐字节等价（安全网后 4 组生产相位网格 0 差异）② test1 逐字段 0 差异 **1.27×**（46.2→36.4min）
> ③ 2mkv 双新臂逐字段 0 差异 **1.30×**（53.8→41.3min）④ **四片三指标逐项一致**（严格 136/139 · 导出 131 ·
> 场景 138 · 负例 4/9；支撑 1103→1108）⑤ 门禁 **512 OK (skipped=2)**。落地：`config.py` False→True
> （注释写全证据 + 回退路径）+ 默认值回归锁；决策全文 `DECISIONS.md` 2026-10-03（续51）。
> **未归因项（如实登记）**：test2 3 行 / test3 5 行 **LOW 置信** span 形状差异（对归档参照，**不移动指标**）；
> 2mkv 已证「归档批 vs 当前代码」存在跨代际差异 ⇒ fresh 双新臂（job pwsh-51/52）后台跑完补记。
> **下一步**：① fresh 臂出数 → 归因补记；② L2（源片 ISC 索引）：`build_isc_index.py` 冒烟已过
> （test1 60s 切片 3.8s，整片估 ~9min）→ 建 test1 表 → `probe_l2_index_replay.py` 对照（20 段）；
> ③ git 提交（续41~续51）/ r8 重打 —— 仍等口令。未改 GT / 未 bump feature_version。

> **▶ 2026-10-03（续51）— 四片 A/B 抓到真缺陷（生产网格整格跳位）⇒ 安全网修复 + 重跑队列运行中（后已翻默认，见上条）**
> **现象**：test1 PASS（0 差异）；**test2 3/67 段落点差**（LOW，位移 23~26s）；**2mkv 段数 83→84**。
> **排查**：逐项证伪窗解码（1.mp4/test1-ed 0/120、0/60 不一致）· 帧不同（test2-om/2.mkv/test3-om 各 91 点 0 不同帧）
> · 非确定性（同配置两遍一致、旋钮开关切分一致 69=69=69）。
> **真因**：生产网格 `round(wlo+i*2,3)` 步长有 0.001s 抖动，select 窗口按统一 step 生成 ⇒ 窗口起点漂到目标之前
> ⇒ 个别目标被分到下一格（+2s）的帧（t0=1285.533 的 91 点里 6 个）⇒ 低置信段 argmax 翻转。
> **修复**：`_decode_window(max_pts_lag=)` —— 分配帧 pts 晚于目标超过 `min(step,0.5)` 就拒绝，回退逐帧精确抓取。
> **验证**：4 组生产相位网格 **0 不同帧**，抖动相位触发 6 次精确回退（可忽略）。
> **协议修正**：归档 `v2_*` 不能当单变量 A/B 的 off 臂（2mkv 段数差与旋钮无关 = 跨代际）⇒ 2mkv 走**双新臂**。
> **重跑中**（job pwsh-47）：A=test2 on（带网）· B=2mkv `--force` 双新臂 · C=test3 on（带网）。**test1 结论不变**。
> 门禁：本批需重跑后端全套（改了 `media/ffmpeg`）。未改 GT / 未翻默认 / 未提交。

> **▶ 2026-10-03（续50 补四）— test1 整条 A/B = PASS（零语义 + 1.27×），三片回归运行中（后因抓到缺陷而改判，见下条）**
> `probe_isc_grid_ab.py --case test1`：off 臂 = 现役默认批（续47 defaults_check 逐位一致），on 臂 =
> `grab_grid_decode=True`。**结果**：on **2186.1s = 36.4min**（55 段）vs off 2772s（46.2min，defaults_check）
> / 2888.4s（续45 v2 臂）⇒ **1.27×~1.32×，单片省 ≈9.8min**；`strip(result_id)` 后 **0 处差异**（主/子 span、
> 置信、reasons、alternatives、信封全比）⇒ **零语义漂移**。门禁：后端全套 **512 OK (skipped=2)**（100.2s）。
> **运行中**：2mkv / test2 / test3 三片回归（on 臂，off 复用 `work/isc_refine_arms/v2_*`，≈2.5h），
> 产物 `work/isc_grid_ab/`。**待拍板**：四片齐 → 翻 `grab_grid_decode` 默认；随后 L2（ISC 源片索引）立项。
> 未改 GT / 未 bump feature_version / 未翻默认 / 未 git 提交。

> **▶ 2026-10-03（续50 补三）— select 漂移修复（网格路径升级为逐字节等价）+ 其它抓帧点实测否定 + A/B 重跑中（已完成，见上条）**
> 用户第二次「继续」⇒ 三件事：① **漂移修复**：初版 `gte(t-prev_selected_t,step)` 在 step 非源帧长整数倍时
> 逐步累积（1s 网格 600 点仅 121/600 同帧；0.208s 步长 15 点仅 3/15、ISC cos 0.335）⇒ 改
> `_grid_select_expr(lo, step)`：**锚定每个解码簇起点**的绝对窗口取首帧（`filters` 支持 callable 按簇生成），
> 修复后 **300s@1s = 300/300、180s@2s = 90/90 逐字节同帧**，加速 2.36~2.61×（≈零语义级别）；
> 亚秒步长由 `MIN_GRID_STEP_S=1.0` 护栏回退旧路径（护栏 + 单测）。
> ② **其它抓帧点实测否定**：shot_split 形状（3s@4.8fps）虽 2.10× 但保真 min cos 0.335（亚秒步长），
> patch_refine 小窗仅 1.08× ⇒ **不再接线**；网格抽取只服务「宽扫粗扫」这一形状。
> ③ **L2 建表形状实测**：test1-om 600s@1s base 123.6s → grid 49.4s（**2.50×**）⇒ 建表成本同幅下降。
> **A/B 重跑中**（旧判据那轮已主动中止，其 on 臂 79/91 证据过时）：off 臂复用现役默认批
> `work/isc_refine_arms/v2_test1.results.json`（续47 defaults_check 已证逐位一致），**on 臂运行中**
> （`grab_grid_decode=True` + DML + radius=90，产物 `work/isc_grid_ab/`）。定向单测 3 文件全绿。
> **待办**：A/B 出数 → 四片三指标回归 → 拍板翻默认；L2 立项；后端全套（A/B 后跑）。未改 GT/未翻默认/未提交。

> **▶ 2026-10-03（续50 补二）— L1 接线完成（宽扫粗扫走网格抽取）+ test1 整条 A/B 运行中（后升级为漂移修复版）**
> 用户令「继续」⇒ 把 L1 接进生产路径（**唯一变量 = `pipeline.grab_grid_decode`，默认 False**）：
> ① `isc_refine.apply_isc_refine` 增 `grab_grid` 可选参数 + `_embed_missing_grid`（**只用于宽扫粗扫**
> `coarse_ts`；候选窗/细化窗相位非网格对齐，仍走 `grab_frames` 以免选帧偏移）；
> ② `FFmpegIO.grab_grid_times(path, times)`（显式时间表、**允许带洞**：select 抽超集 + `first_ge` 配对）；
> ③ `locator_service._grab_grid_batch`（旋钮关/接口缺省/超片尾三路回退 + 复用 512 FIFO 缓存）。
> 单测 +8（isc 粗扫一致性 & 缺帧回退；locator 开关/回退/缓存；grab_grid_times size 自动 scale 等），
> 定向 3 文件全绿。**A/B 运行中**：`probe_isc_grid_ab.py --case test1`（两臂完整 `locate()`，
> strip(result_id) 逐字段比对 + 墙钟；产物 `work/isc_grid_ab/`），off 臂已确证 `BACKEND=DirectMLBackend`。
> **下一步（等 A/B 出数）**：① 结果逐位一致 + 提速 → 四片三指标回归 → 拍板翻默认；
> ② 随后接 shot_split / patch_refine 的网格抓帧（同一原语，收益同源）；③ L2（ISC 源片索引）。
> **待跑**：后端全套（A/B 结束后跑，避免 GPU 争用）。未改 GT / 未翻默认 / 未 git 提交。

> **▶ 2026-10-03（续50 补）— L1 落地：`grab_grid` 网格抽取 2.5×（已到解码地板），待接线**
> 用户令「开始吧」⇒ 实施 L1（此前结构账/实测见续50）。**落地**（`mvp/src/media/ffmpeg/ffmpeg_io.py`）：
> 新增 `grab_grid(path,t0,step,n)` = `select='isnan(prev_selected_t)+gte(t-prev_selected_t,STEP)'`
> **+ `-fps_mode passthrough`**（必带，否则 vsync 复制帧 5→149）+ 冻结 `first_ge` 选帧；
> `grab_frames` 增 `filters/size/match/passthrough` 透传，`size` 自动拼 `scale=`。
> **两个反例留痕**：`fps=1/N` **重定时间轴**（帧落 +0.5s、ISC cos 0.78）⇒ 弃用；缺 passthrough 复制帧。
> **A/B（test1-om t0=1382.5 / 180s / 2s 网格 / 91 点）**：base **27.9s** → grid **11.1s（2.51×）**、
> grid512 10.7s（2.61×）；79/91 **逐字节同帧**、余 12 点 ≤1 源帧；ISC cos mean **0.997** / min 0.922。
> **新关键事实 = 解码地板**：同窗纯解码 8.5s（21× 实时；顺序 26~27×）⇒ 11.1s 里 8.5s 是解码，
> L1 已把「管道搬运」从 ~20s 压到 ~2.4s。**要继续降本必须减少「被解码的秒数」** ⇒ L2（源片索引 =
> 全片一次顺序解码）与硬解（对扫描路径做 cos A/B，不照搬旧判负）成为下一步。
> 门禁：后端全套 **505 OK (skipped=2)**（95.8s，+6 项单测）。**未接线**（宽扫仍走旧路径）、未改 GT/默认值/未提交。
> **待拍板**：① 接线到宽扫粗扫 + test1 整条 A/B（今天可出）；② 随后四片回归（≈3h）；③ L2 是否立项；④ 硬解路径 A/B。

> **▶ 2026-10-03（续50）— 定位成本结构实测：抓帧是「管道 I/O」瓶颈（4× 于推理），杠杆排序已定**
> 用户令「性能侧还可以怎么优化，必须先把成本打下才好继续优化算法」⇒ 新探针
> `mvp/scripts/probe_isc_cost_levers.py`（main-score / index-pilot 两子命令）实测四片，**零 runtime 改动**。
> **① 成本单元（实测）**：ISC 推理 **30.4 fps（0.0328 s/帧）**；窗解码抓帧 **7.65 帧/s（0.1308 s/帧）
> = 推理的 4×**；原始帧 2.64~5.97 MB（2mkv 1280x688 / test1 1920x960 / test2 1920x1036 / test3 1920x800）；
> 推算管道 ≈676 MB/s。根因 = `_decode_window` 对窗内**每帧**都读一份原始 BGR（只取其中 1/25~1/30）
> ⇒ **抓帧成本正比于「解码多少秒」，与「要几帧」几乎无关**。**续47「宽扫大头在 embed 而非抓帧」需更正。**
> **② L1（首选·全链）= 网格抽取 `-vf fps=1/N`（+ 消费者侧 `-s`）**：粗扫本就是 2s 网格、候选/细化 1s 网格
> ⇒ 管道量 ÷25~60（再 ÷9 若 512² 预缩放）⇒ 抓帧 0.131→~0.005~0.02 s/帧，宽扫 18~24 s/段 → 3~6 s/段，
> 且同时命中 shot_split/patch_refine（续34：grab 占两旋钮段 77.6%）。零语义版本风险（扫描帧从不进索引），
> 验证 = 抽样逐字节/max|Δpixel| + 同 t ISC 余弦 + 四片回归。
> **③ L2（结构）= ISC 源片索引**：实测 test1-om 1s 网格试建（600s）= grab 78.5s + embed 19.7s ⇒ 外推整片
> **22.4 min / 8.4 MB**；收益在「同一母片多条成片」复用（N≥2 起每片省 ~22 min）+ 扫描范围 ±90s→全片；
> 建表本身也吃同一条管道 ⇒ **先 L1 再 L2**。**④ L3 main-agreement 门 = 实测不可分，不建议单独上**：
> 301 段仅 15 段（5.0%）被切换，但真增益行 p20 0.598 / p34 0.674 / t2r06c 0.509 落在未切换段主体
> （p25 0.678 / 中位 0.771）之内 ⇒ θ=0.70 才保住增益、只跳 67.1% 且误跳 3 段；θ=0.80 才误跳 0 但只跳 33.2%。
> **⑤ L4 FP16 = 未测（便宜、正交）**。已判负不再碰：硬解 / ISC 批 / 索引密度 ÷2 / 阶梯。
> **待拍板**：是否立刻开 L1 实施（改 `media/ffmpeg` 网格抓帧路径 + 抽样逐字节/余弦验证 + 四片回归）；
> L2 是否随后立项；L4 是否并行。归档 `FINDINGS_COST_STRUCTURE_LEVERS_20261003.md` + `work/isc_cost_levers/`。
> git 提交（续41~续50）/ r8 重打仍等口令。

> **▶ 2026-10-03（续49）— 索引密度 ÷2（TODO ④「两级采样索引探针」）结构账 + 敏感度实测 = 建议不立项**
> 用户令「继续这个项目」（无新指令）⇒ 按续48 教训「先做结构账再决定实跑」，对 P0 ④ 做零 runtime、
> 零 GPU 的结构账，并新写敏感度探针 `mvp/scripts/probe_index_fps_sensitivity.py`。**三条硬结论**：
> ① **收益错配**：索引密度 ÷2（1.0→0.5fps）收益**全部落在一次性成本**——四片真实索引 31,117 帧 /
>   53.2MB / 建索引折算 38.1min（13.6fps 口径），÷2 省 **19.1min + 26.6MB**；**每次定位
>   （现役 45~60min/片，test1 46.2min）一分不省**——ISC 宽扫与抓帧按任意时刻抓帧，不经索引
>   （源码事实 `isc_refine.apply_isc_refine` → `_grab_many(source_path, coarse_ts)`）。
> ② **精度侧不是阻碍**：现役默认批 v2_*（严格 136 / 导出 131 / 场景 138 / 负例 4·9）原片侧 span
>   端点吸附 2s 网格（偏差 ≤1s）后重算 = **137 / 131 / 138 / 4·9**（严格 +1，唯一翻转 t1r12a
>   part→HIT 增益）；平移 ∓1s = −4 / −1；**唯一大损失形态 = 两端各缩 1s（−18 / −48）但它是
>   「span 变短」不是「网格变粗」，且现役 patch/ISC 细化给出的是 0.25s 步长端点（非索引网格）**。
> ③ **检索保真度复算（当前 GT，DML 206s）**：stride2(0.5fps) 粗池命中 **139/139**、rank **p99=11.0**
>   ≪ 我方 `retrieval_top_k=28` ⇒ 0.5fps 检索层同样不是阻碍；stride10(0.1fps) = 130/139、p99=448.6
>   （须密验兜底）。口径更正留痕：2026-09-26 档案记 p99=25.3 / 127 命中，本批 11.0 / 130 差异 =
>   GT r1 修订，非算法。**裁决建议 = 不立项 (a)（或降级 (b) 新装机可选档）；(c) 若仍要实跑，
>   方案已备（隔离 SVL_DATA_DIR + sampling_fps=0.5 重建四片 ≈19min + 现役配置四片全跑 ≈3h）**。
> **替代杠杆（同「两级采样」思想搬到花钱处）**：现役 ISC 宽扫**已是两级**（粗 2.0s + top-3 峰
> ±2.0s@1s），粗步长 2.0s→4.0s 可省 ≈42% 宽扫 embeds；结构账需先落盘小样本 ISC 粗曲线
> （runtime 不落盘、既有产物只有 PNG）⇒ 提案 = 20~30 段 ×±90s @1s 曲线探针（≈5~10min GPU），
> 门槛 峰值保持 ≥95% 且落点差中位 ≤1.0s。**未改 runtime / 未 bump feature_version / 未翻默认 /
> 未改 GT / 未 git 提交**。门禁：后端全套 **499 OK (skipped=2)**（91.9s，零 `mvp/src` 改动）。
> 归档 `FINDINGS_INDEX_DENSITY_DIV2_20261003.md`（含 GT 版本头 + §八 登记行）。
> **待拍板**：① ④ 采纳 (a) 不立项 / (b) 降级可选档 / (c) 实跑四片回归；② 是否接 5.2 替代杠杆
> （ISC 粗步长 4.0s 曲线探针）；③ git 提交（续41~续49，仍等口令）；④ r8 重打。

> **▶ 2026-10-03（续48）— v3 阶梯宽扫验收 = FAIL（计时判负），`isc_refine_ladder_s` 维持 0.0**
> `mvp/scripts/rerun_isc_refine.py ladder`（radius=90 + ladder=30）实跑，2mkv/test1/test2
> 三片自然完成、**test3 主动中止**（REFINE ~42/103，前三片计时已一致更慢，PY_EXIT=127 中止
> 留痕）。**计时 3/3 片全部更慢（判负依据）**：2mkv 3167.7s vs 2923.8s（+8.3%）/ test1
> 2928.0s vs 2888.4s（+1.4%）/ test2 3738.0s vs 3302.3s（+13.2%），3 片合计 +719.2s
> （**+7.9%，节省为负**）。精度侧 3 片零回退（严格 99 · 导出 95 · 场景 101 · 负例 3/6
> 逐片持平），**mark/main_hit 双口径翻转 0 行**；生死线 **p20/p34/p14 保持 HIT 且落点与 v2
> 臂逐位同**；churn 4 行（p12/p13/t1r20/t1r26）拼图读毕全部同景内选位差、无真损失；切换段
> 21 vs v2 19。**机制复盘（设计错误非实现错误）**：内圈收工前提 = 多数段内圈有过 margin 门
> 的峰，但过门峰≈最终切换段仅 ~10%（21/206）⇒ ~90% 段白付内圈粗扫+细化再扩外圈，10%:90%
> 的省/付比注定净亏。**教训：「提前收工」类优化先用验收数据做结构账（切换率 10% 一页纸即可
> 判负），再决定是否实跑。** 裁决 = **FAIL，维持 ladder 0.0**（精度无损但无收益，纯负优化）；
> 未改 GT、未 bump feature_version、未 git 提交、未翻任何默认值。归档 FINDINGS
> _ORTHOGONAL_BACKBONE_PROBE_20261002 §12；分析 `work/isc_refine_arms/analysis_ladder/`
> （对照脚本 + metrics/flip/fine/churn/inner_hit + 拼图 7 张全读毕，既有产物零覆盖）。
> **待拍板**：git 提交（续41~续48）/ r8 重打；性能侧下一杠杆 = 两级采样索引探针（TODO P0 ④）。

> **▶ 2026-10-03（续46 补）— v2 radius=90 翻默认（严格 136/导出 131 生效）+ defaults_check 实测中【下个对话从这里读起】**
> 用户拍板「1」：`pipeline.isc_refine_scan_radius_s` **0.0→90.0**（续45 验收 PASS：严格 134→136
> p20/p34 获救 · 导出 128→131 · 翻转全真增益 · churn 无损失；代价四片 +88min 无窗解码口径，
> 续46 窗解码 1.34× 部分对冲）。PRODUCT_INTRO 时间口径 18→30~45min（精确数字等 defaults_check
> 实测回填，同时交叉验证 vs v2_test1 逐位一致——两改动各自零语义，合成应逐位同）。
> 门禁后端 **496 全绿**。DECISIONS/CHANGELOG/TODO 已记。
> **待拍板**：git 提交（续41~续46）/ r8 重打。

> **▶ 2026-10-03（续46）— 窗批量抓帧解码 = test1 全片 1.34× 逐位一致，翻默认开【下个对话从这里读起】**> **▶ 2026-10-03（续46）— 窗批量抓帧解码 = test1 全片 1.34× 逐位一致，翻默认开【下个对话从这里读起】**
> 用户令做「ffmpeg 解码侧」。`FFmpegIO.grab_frames`（簇一次 spawn：窗解码 + showinfo pts +
> **-copyts**；gap≤4s/跨度≤40s 聚类；失败逐帧回退）+ `_grab_frames_window`（缓存查漏回填 +
> 假体鸭子回退）+ `pipeline.grab_window_decode` **翻默认 True**。两真 bug 留痕：loglevel 吞
> showinfo（死等）；无 -copyts 选帧差一帧（像素差实测，flag 是前提不可省）。零语义链：单测
> 逐字节 → 2.mkv 132 帧 1.73× 逐字节 → test1 全片 A/B **21.5→16.0min=1.34×，55 段
> strip(result_id) 逐位一致+信封一致**（work/grab_window_ab/）。门禁后端 **496 全绿**。
> 硬解（-hwaccel）留作下一杠杆。**待拍板**：① v2 radius=90 翻默认（PASS 在手，+88min/四片，
> 本优化可部分对冲）；② git 提交（续41~续46）；③ r8 重打。

> **▶ 2026-10-03（续45）— ISC 门控 v2 宽幅扫描生产验收 = PASS，待用户拍板翻 `isc_refine_scan_radius_s=90`【下个对话从这里读起】**
> `mvp/scripts/rerun_isc_refine.py v2` 四片实跑（完整 `srv.locate()`，唯一变量
> `pipeline.isc_refine_scan_radius_s` 0→90；isc 双臂同开），ALL_DONE/PY_EXIT=0，总 212.4min
> （2mkv 2923.8s / test1 2888.4s / test2 3302.3s / test3 3631.1s；vs 续44 ON 臂 124min，
> 宽扫开销 ≈+88min）。对照臂 = `work/isc_refine_arms/on_{case}`（radius 0 现役）。
> **三指标硬门全过（零回退全升）**：严格 134→**136**（+2）· 导出实得 128→**131**（+3）·
> 场景 138 持平 · 负例 4/9 持平（分片 3/0/0/1 逐片持平）· 支撑 1094→1103。
> **翻转 3 条全真增益、零回退零真损失**：**2mkv/p20 part→HIT**（ON 同景 7.5s 后行走 → V2
> 窗内同款劳作动作，续43 探针 margin +0.11 兑现）；**2mkv/p34 part→HIT**（ON 错场景男子举牌
> → V2 窗内同女子，margin +0.33 兑现）；test2/t2r06c main F→T（ON span 漂过切点 → V2 窗内
> 同内容）。**v2 立项动机（破 CLS 聚簇提案视野）直接兑现，MISS6 缺口 6→4**。
> **churn 3 行**（判据行口径 >1s 位移共 5 行，其中 2 行无指标影响：t2r04b 同隧道镜头内 2.2s /
> t3r22 同战斗蒙太奇 1.4s，拼图读毕无隐藏损失），远低于 >20 预警线；ISC 切换段 31（v1 21），
> `-iscw` 宽扫胜出 14 段 ⇒ margin 门+先粗后细+距主≥2s 三重约束把 churn 压住。
> **MISS6 逐条**：p20/p34 获救；p14 保持 HIT（落点逐位同）；t1r08c/t1r12a 仍 part（落点
> 逐位同，宽扫峰未过门）；t2r03b 仍 MISS（0s 占位段 width≤0.01 按模块边界跳过，无候选不救
> 设计内）。**自信错点名 t1r30a/t2r04a 双臂一致 HIT、落点逐位同，无恶化**。
> **裁决 = PASS，可进用户拍板翻 `isc_refine_scan_radius_s=90`；radius 保持 0.0 未翻**
> （未改 GT、未 bump feature_version、未 git 提交）。归档 FINDINGS_ORTHOGONAL_BACKBONE_PROBE
> §11；分析产物 `work/isc_refine_arms/analysis_v2/`（对照脚本 + metrics/flip/fine/churn +
> 拼图 8 张全读毕，既有 analysis/ 零覆盖）。**待拍板**：① 是否翻 radius 90（验收 PASS 在手，
> 注意宽扫代价 +88min/四片）；② git 提交（续41~续45，仍等口令）。
>
> **▶ 2026-10-02（续44）— ISC 第二意见局部重排生产验收 = PASS，待用户拍板翻默认【下个对话从这里读起】**
> `mvp/scripts/rerun_isc_refine.py on` 四片实跑 ON 臂（完整 `srv.locate()`，唯一变量
> `pipeline.isc_refine_enabled`，默认仍 False），ALL_DONE/PY_EXIT=0，总耗时 ≈124min
> （2mkv 1879s / test1 1595s / test2 2009s / test3 1958s）。OFF 臂 = 现役默认批
> `work/spl_patch_arms/on_{case}` 复用（配置断言 + 续39 重计 133/125/138/4 逐位一致旁证等价）。
> **口径勘误**：续39 GT r1 下「导出实得」权威基线 = **125**（119 是修订前旧数）。
> **三指标硬门全过**：严格 133→**134**（+1）· 导出实得 125→**128**（+3）· 场景 138 持平 ·
> 负例 4/9 持平。**翻转 3 条全真增益、零回退零真损失**：2mkv/p14 part→HIT（OFF 错场景地堡庭院
> →ON 落 GT 窗内天线场景，MISS6 唯一获救）；test2/t2r07c、test3/t3r02c main F→T（同镜头命中、
> span 端点距 GT 窗 0.35s/0.48s，±2s 容差记账/子镜头粒度）。churn 9/139 无指标影响（逐条核验
> 无隐藏损失，t1r02/t3r19 覆盖率反升）。**MISS6 逐条**：p14 获救；p20/p34/t1r08c/t1r12a 仍 part；
> t2r03b 双臂均 0s 占位（v1 门控不救无候选段，符合预期，留门控 v2）。**旋钮观察**：翻转 3/139、
> aligned 零翻转 ⇒ margin 门不松不紧；增益落点全部紧贴 GT 窗（span 收缩偏保守，观察点=端点贴窗
> 而非 margin）。**裁决 = PASS，可进用户拍板翻默认；`isc_refine_enabled` 保持 False**（未翻默认、
> 未改 GT、未 bump feature_version、未 git 提交）。归档 FINDINGS_ORTHOGONAL_BACKBONE_PROBE §10；
> 分析产物 `work/isc_refine_arms/analysis/`（双臂 metrics + 翻转清单 + 拼图 3 张全读毕）。
> **待拍板**：① 是否翻默认 `isc_refine_enabled=True`（验收 PASS 在手）；② git 提交
> （续41~续44，仍等口令）。
>
> **▶ 2026-10-03（续44 补）— 翻默认已执行（用户拍板「1.翻，2.待定」）**
> `pipeline.isc_refine_enabled` **False→True**（config.py，注释同步改写）；margin 0.05 不变。
> 打包接线三件套落地：① 资产入册 `mvp/ui/resources/models/isc_ft_v107/`（图 1.6MB + 外部权重
> 209MB；**二进制 gitignore**——GitHub 100MB 上限，构建时从 `work/isc21_weights_ortho_probe/`
> 拷入 + `asset.json` sha256 fail-fast，同 patch 口径）；② `main.ts` 注入 `SVL_ISC_ONNX`；
> ③ `accept_packaged_bundle.py` 加 ISC 断言（清单/图/权重/sha256 + 冒烟日志
> `isc refine device=dml` 检查，SMOKE_WALL_S 45→75s）+ `locator_service` 加设备留痕日志。
> 再生成链补齐 = `mvp/scripts/export_isc_onnx.py`（torch→ONNX，实测 vs 仓内参考 cos=1.0、
> max|d|=0、权重 sha256 相同；图字节随导出器版本可变，数值等价即有效）。
> 门禁：后端全套 **492 全绿**（88s，翻默认后无回归）· vitest 138 · 双 typecheck · compile:electron 绿。
> 已知上限（登记进 config 注释）：候选提案来自 CLS 聚簇 ⇒ p20/p34 型 CLS 真盲救不到
> （门控 v2 = 提案放宽到检索 top-N）；t2r03b 无候选不救。**r8 重打未做（打包需授权，等口令）**。

> **▶ 2026-10-02（续43）— 方案B 正交 backbone 探针 = 正判，ISC21 通过门槛【下个对话从这里读起】**
> 用户拍板方案B（正交预训练 backbone 探针）。三臂 20 案例实测（与方案A 同扫描协议/判据/案例集，
> `mvp/scripts/probe_orthogonal_backbone.py`，产物 `work/orthogonal_backbone/`）：
> **ISC21**（`isc_ft_v107`，EfficientNetV2-M@512/256-d copy-detection 专用，权重自 tier2 trash 恢复离线加载，
> ONNX gem→ReduceMean 后 **DirectML** 生效）= MISS 严格未命中 **5/6 gt>main、6/6 gt_is_peak**
> （p14 +0.074 / p20 +0.110 / p34 +0.326 / t1r08c +0.046 / t1r12a +0.039 / t2r03b 峰落 GT±0.4s），
> MISS+POCKET 7/12 ≥ 1/3 门槛 ✓；对照组 7/8 peak，唯一失败例 t1r27 = margin −0.02 噪声级边界翻转
> （非灾难反噬）。**CLIP ViT-B/32 臂弱信号**（MISS 3/6、曲线近水平=语义不变性更甚）不单独采纳；
> **dino sanity 臂 2/6** = harness 无 GT 泄漏旁证；ens 集成与 ISC 持平（增益全部来自 ISC）。
> 逐张读图 9 张曲线 + 3 张帧拼图确证：峰为孤立真峰非噪声台地，GT 帧与 ED 查询同内容，
> p34/p20 我方主定位帧=同场景另一时刻 ⇒ **ISC 补的正是 DINOv2 缺的「同场景内时刻判别力」**。
> **t2r03b 续42"不可救"结论限定改写**：DINOv2 证据链上不可救成立，但 **ISC 证据链能救**（峰在 GT±0.4s）
> ⇒ 该案例列为采纳门控设计必验收样本。Phase 12 旁证：ISC+TransVCL 是旧 GT v1 时代唯一产出过
> 视觉确认真定位的特征链。**工程留痕两条**：① CLIP 图 DML 授权失败（E_INVALIDARG）会污染进程，
> 之后任何 DML Run 段错误（EXIT=139，对照复现归因）⇒ 未来多模型 runtime 的 DML 授权失败必须
> fail-fast 隔离；② t2r03b 主定位=0s 占位把扫描窗炸成全片 3580 位置（方案A 同窗逻辑同踩），
> 已修 = 窗口 >150s 钳到 GT 邻域 ±15s 并记 main_in_window=False。CLIP 臂 CPU 回退留痕（DML 尝试会段错误故不做）。
> 归档 `FINDINGS_ORTHOGONAL_BACKBONE_PROBE_20261002.md`。
> **▶ 扩验证（同日拍板选项②，`probe_ortho_full139.py`，35min）**：全 139 正例 ISC+dino 双臂峰位分布
> = **信号真实非运气但分层**：核心判别桶（drift+far+nowin，63 例）ISC 峰命中 **44/63 (70%)** vs
> dino 37/63，配对仅ISC中 15 vs 仅dino中 8；drift(2-15s) 73% / far(>15s) 43% / nowin 8/8；
> MISS6 全部 peak✓。**ISC 独家增量 12 例**（margin 至 0.37，10/12 在 drift+far）。
> 失败 19 例两族：近位移边界翻转 9 例（disp≤5s、gap 噪声级）/ 远位移一致错 10 例（点名读图
> t1r30a/t2r04a 确证 **ISC 与 dino 同峰同错**、gap 可达 +0.6，部分有 GT 疑点成分）；t1r18 点名
> 确证 ISC 真独家判别。⇒ **门控设计约束**：ISC 只能做歧义段「第二意见 tiebreaker」不能当主判据
> （全局重排必 churn，同形态5 教训）；判据须含 margin 绝对门 + 候选窗约束 + 两臂分歧才介入。
> 归档同上 §9。**立项前多模态复核已补齐（用户问「多模态复核没」）**：独家增量 12 例逐张读图全毕
> = **11 干净 + 1 边界**（t2r07b ISC 峰内容真但锚到 GT 窗前 2.2s 相邻子镜头 = 多镜段子单元族）⇒
> 独家增量按干净 11 例记账；门控新增约束 = ED 段含切点时容忍子镜头粒度（±2~3s）或结合 ED 子镜头
> 切分对齐（曲线 12 + 拼图 6 全读毕，VLM 仍不可用）。
> **待拍板**：① 门控设计已获选项①拍板 ⇒ 下批 = **采纳门控设计实现**（歧义段 top-K ±5s ISC 重扫 +
> margin 绝对门 + 候选窗/子镜头粒度约束 + 融合判据 + 三指标回归 + MISS6/t2r03b 必验收）；
> ② git 提交（续41+续42+续43，仍等口令）。

> **▶ 2026-10-02（续42）— 双栈解读 + 方案A判负 + TN喂饱探针(含bug更正) + t2r03b结案 + 竞品技术栈解读【下个对话从这里读起】**
> 用户令对双栈做完全解读并给零训练高精度算法。竞品逆向工作区深挖 + 我方源码精读结论：
> 竞品特征基座与我方**逐字节同**（DINOv2 ViT-S/14，a02 SHA256 同）；我方表示更强
> （518/1369-token vs 224/256、1fps 逐帧 vs 场景5关键帧）；且已移植竞品几乎全部全局层机制
> （REDIG_20261001 实测逐条 graft = 两项净零一项净负）⇒ **根因 = 特征判别力（语义不变性）**，
> 非锚定方式/切分/检索。5.4G vs 1.6G = torch 打包差异，与精度无关。
> **方案A = patch 级稠密几何对应**（mutual-NN + 仿射 RANSAC 内点率，利用 patch_score 丢掉的
> argmax 落点）探针 20 案例 GPU 实测：MISS6 gt_is_peak **1/6**、margin 噪声级（<0.1）；
> CONTROL 7/8 但属同义反复（定位已对时 main≈GT）；机理 = **背景主导稀释**（同场景偏几秒
> 静止背景仍对齐、掩盖前景错位）⇒ **判负，不进 runtime、不留通道**
> （`FINDINGS_PATCH_DENSE_CORR_20261002.md` + `work/patch_dense_corr/`）。
> 剩 6 条严格未命中 = 特征上限族 + t2r03b。**t2r03b 查证结案**：0s 仅 unresolved 的
> `Result.original` 占位（models.py:173），导出/渲染/UI 全正确过滤或标「未定位」⇒ **非用户可见缺陷**
> （早前"0s 缺陷"说法已更正）。根因 = 0.9s 窄段证据太弱（检索 GT rank1 但 cover 0.062/bsim 0.413）：
> 窄窗豁免可过弱簇门但 `dense_retry_min_sim=0.62` 仍挡、降门会放回 test4 假定位(0.53-0.60)
> ⇒ **不可救，接受为未命中**；窄窗豁免已回退，仅保留 `reasons.ts` 补 no_evidence 中文映射
> （vitest 138 + 双 typecheck 绿）。诊断 `probe_t2r03b_diag.py`。
> **方案1 TN 喂饱探针（续42 补，用户问「为何加 TN 效果不一样」）**：TN 臂@2/4/8fps 严格
> **116→118→122**（场景 123→130→135）单调升 ⇒ **采样耦合成立**（用户直觉对，续7饿死假设正面证实，
> TN 越喂越好）。两级臂（默认 coarse≈4.8fps）= 严格 **130** > TN@8fps（更密）122 ⇒ TN 喂更密仍不敌。
> ⚠️ **探针 bug 更正（子代理复核发现）**：初版用 edited_segment_fps 扫两级臂，但该参数只进
> _segment_legacy（现役 twopass 走 coarse_fps 不读它，locator_service.py:357 vs 412/429），
> twofed_2/4/8 md5 相同=死参数 ⇒ 撤回初版「两级喂饱零变化=单元够大」「同8fps两级胜TN」两处错判
> （两级自身提采样未测，且 twopass 切分与查询采样耦合在同一 coarse_fps 难独立扫）。
> ⇒ **TN 不接入（两级@4.8fps 已 > TN@8fps；换 TN 是负优化）**。**多模态复核 16/16 张**：A 类 5/8
> 强确证两级胜 TN（TN 漂到不同内容/场景）；B 类喂饱救回**真锚对仅 1/8(p36)、余 6/8 判据边界翻转**
> （8fps→span 变宽→覆盖窄 GT→假性提分，同续31 §7.5）⇒ 喂饱的"+6/+12"收益本身多是噪声，不接入更硬。
> `FINDINGS_TN_SAMPLING_COUPLING_20261002.md` §3.5。逐帧密读(ms)确证：p36 两臂画面不同=真锚对；
> t1r08b/t2r07c 两臂画面相同/都在 GT 场景=span 边界抖过判据线（非真锚对）。
> **待拍板**：方案B（正交 backbone 探针）/ 接受精度现状转产品鲁棒性 / git 提交（仍等口令）。

> **▶ 2026-10-02（续41 后续）— r7 出包 = 现役包【下个对话从这里读起】**
> `Video-Locator-win-x64-20261002r7.zip`（1.68GB/8364 条目）= r6 + 续41（入库层四件 + 快/精双模式）。
> accept FAILED=0 · 三防全过 · 启动冒烟 PASS · 真机快验：FileBrowser 真实盘符/卷标/容量、
> 白名单目录、快速档 `refine=fast` 日志确证跳过拆分、修掉「0.0 GB」显示缺陷后**重建再验** ✓。
> **待拍板**：git 提交（续41+续41后续 未提交，等口令）/ 下批方向。r5/r6 zip 未拍板删除。


> **（2026-10-02 续41）— 入库层四件 + 快/精双模式 完成（未提交未打包）**
> ① 入库层（竞品 file_api.browser 移植）：`infrastructure/fsbrowse.py` 盘符枚举/自然排序/
> 视频白名单/磁盘剩余 + `GET /api/fs/browse` + **磁盘预检 LOC-1108**（合并=输入总和+256MB、
> 渲染=7.2Mbps 估+512MB，动手前失败）+ 前端 `FileBrowser.vue`（源片库/剪辑片区「浏览选择」，
> 多选顺序=合并顺序）；dev 浏览器实测自然排序/白名单/顺序添加全 ✓。
> ② 快/精双模式：`locate(refine=None/bool)` 逐任务覆盖两旋钮（默认高精度不变），
> API body 显式才带 refine、UI 模式单选 + localStorage 记忆、日志 `refine=fast` 留痕。
> 门禁：后端 **485** · API **104** · vitest **138** · 双 typecheck · mock 契约全绿；零 feature_version。
> **待拍板**：git 提交（续41 未提交）/ **r7 重打**（续41 两批需进包，需授权）。
> 现役包仍 = r6（含 UI 三修复 + 售后三件）。


> **（2026-10-02 续40 后续三）— r6 出包 + 包体真机全验 = 现役包**
> `Video-Locator-win-x64-20261002r6.zip`（1.68GB/8364 条目）；accept=FAILED=0（22.3s）·
> 三防全过 · **调试档包内冒烟 PASS**（SVL_LOG_DEBUG=1 → debug.log 在位）· 启动冒烟 PASS ·
> CDP 真机快验（合成素材）：「未分析」徽标 / 全量新文案 / 一位小数 92.0% / device=dml 全 ✓。
> r6 = r5 + UI 三修复 + 售后三件。**数据留存裁决：残留不删、待办撤档**（§9 仅审计留档）。
> **待拍板**：下批方向。（git 已提交 2026-10-02：00b34f1 产品代码 /
> e85f4b9 脚本 / 3f527d9 档案，工作区干净。**A 成片缺口标记 2026-10-02 裁决先不做**，
> 候选剩 (C) 入库层/大文件鲁棒性、快精双模式 UI 档。）


> **（2026-10-02 续40 后续二）— 售后可诊断性三件完成**
> 纠档：路径脱敏主体续19 已落地，本批补漏+另两件：① uvicorn access_log 关闭（原始 query 泄
> 百分号编码路径且不过我方过滤器）+ 百分号盘符路径/API `*path=` 参数两条新打码规则；
> ② 三级日志（客户=UI话术+LOC码 / 支持=video_locator.log INFO+ / **调试=debug.log 默认关，
> SVL_LOG_DEBUG=1 开**，两档互不重复）；③ `mvp/docs/SUPPORT_ERROR_CODES.md` 13 码全表
> （含义/话术/触发/处置/竞品归口 + AUTH/DISK/MEM 预留）+ 防漂移双向断言测试。
> 门禁：后端 **469(+9)** · API **100** 全绿，前端零改动。
> **r6 重打累计 = 续40 后续（UI 三修复）+ 本批三件**（等打包授权）。
> **待拍板**：r6 / git 提交（续33后续~续40后续二）/ 下批方向 (A) 缺口标记。


> **（2026-10-02 续40 后续）— 真机 UI 三问题修复完成（未进包）**
> 用户 r5 真机反馈三条全部落地：① 项目卡 `empty` 直显英文枚举 → 「未分析」+ 徽标成组靠左 +
> 长文件名单行省略号；② 进度卡 92 → 新增 `ProgressStage.REFINE`（worker 92→98 逐事件插值、
> 链入口补发首条消息覆盖 ~6.5min 空窗）+ `Task.progress` float + 显示一位小数；③ 全部进度文案
> 去技术化重写 21 条（patch 局部精排→画面深度复核 i/n、segment→逐段定位、reuse index→复用已有
> 母片索引、特征提取→分析剪辑画面、twopass→镜头边界粗扫/精修 等）。
> 门禁：后端 460 · API 100 · vitest 132 · 双 typecheck · test:mock 全绿；
> dev 前端+源码树后端（DML 实跑）目检「画面深度复核 1/1 · 98.0% · 新文案」逐条 ✓。
> 登记：dev 态侧栏徽标「CPU 回退」与实测 directml 不符（打包态显示正确，未修）。
> **待拍板**：**r6 重打**（本批 UI 修复只有重打才到用户手上）/ git 提交（续33后续~续40后续）/
> r4 旧包删除 / 下批方向 (A)(C)。

> **▶ 2026-10-02（续40）— r5 重打 + 包体验收全过 = 续36 修复真机确证**
> 用户拍板 r5。`Video-Locator-win-x64-20261001r5.zip`（1.68GB/8364 条目）出包；
> `accept_packaged_bundle.py` FAILED=0（r4=5）；三防冒烟全过（新 `work/pkg_attr/three_defense_smoke_r5.py`）；
> 真机 test2 全链（CDP）：**包内 `patch reranker device=dml`**、**locate 1622.0s=27.0min**（r4 62.6min，
> 达成 ~23min 级目标）、结果与 r3 逐字段一致（67段/31高9中25低2未定位/精排切换11）零语义漂移；
> r4 两尾巴销项：精修进度文案「patch 局部精排 i/n」实测推进 ✓、导出默认「全部」✓。
> 首跑修掉 `build-release.ps1` GBK 读 UTF-8 asset.json 崩溃（`-Encoding UTF8`，该断言此前从未实跑）。
> **新登记**：段循环后→拆分前 ~6.5min 零消息+92% 钳死（UX 尾巴）；CLS asset.json 无 sha256 启动 WARNING（既有）。
> **待拍板不变**：git 提交（续33后续~续40，等口令）/ r4 旧包删除（需授权）/ 下批方向 (A)(C)。


<!-- 结构修复：同名章节在源文件中重复出现，以下内容为合并保留。 -->

> **▶ 2026-10-01（续39）— 20 条 GT 缺口核对及写回完成**
> 用户令「那你去完成啊」：原生帧节奏解码、切点/动作图证与源帧辅助匹配完成；**17 条修订、3 条保留**。
> 10 条原片窗修订 + 7 条仅 ED 锚点收紧；139 个 ID、其余119正例、9负例保留，未扩充蒙太奇标签。
> 四份 GT 版本追加 `gt-gap-review-20261001-r1`；备份 `work/gt_backup_pre_gap_review_20261001/`；MD5 manifest 已更新。
> 原 ON 结果批不变，同评估器重计 **严格 133/139 · 主片段 125/139 · 场景 138/139 · 负例误报 4/9**。
> 相对旧GT读数132/119/137：这是**标注修订导致重计，不是算法提升**。p34 HIT→part 如实保留。
> t1r08c 零时长已改一帧锚点，但严格仍未命中（MISS→part）；续38“实际覆盖该点”过强，现撤回。
> t2r03b 旧“同源重复”已追加取代说明；t1r22/t1r25/t2r06c 原标注成立。
> **范围/精度**：本轮核对20工单，非全139条重标；源窗为图证帧时间包络，不声称亚帧精度；执行者Codex，非用户逐条亲审。
> 报告 `mvp/benchmark/user_case/semantic_signal/FINDINGS_GT_GAP_REVIEW_20261001.md`；最终图证 `work/gap_gt_review_final_20261001/`。
> 校验通过：输入8哈希、备份逐字节、结果4哈希不变、未选119正例/9负例不变、ID保留。GT工单结案，算法仍有6条严格未命中。


<!-- 结构修复：同名章节在源文件中重复出现，以下内容为合并保留。 -->


> **▶ 2026-10-01(续36) — 打包态 62.6min 根因闭环：patch 精排器静默回退 CPU torch（资产未随包）+ 卫生四件【下个对话从这里读起】**
> 用户拍板「打包态性能归因第二步」+四件接线卫生。**结论：续35 的「UI/预览/CUA 干扰」假设被推翻。**
> ① 三臂对照（test2/同代码/同索引复用）：整包 E2E 3756.7s、**打包 backend.exe headless 3625.0s**、
> 源码树直跑 1396.7s ⇒ 去掉 Electron/预览/观察仍 60 分钟级（差 3.5%），**罚在冻结包本体且各阶段均匀 2.6×**。
> ② 根因＝包内日志 `patch reranker device=cpu`（源码树 `device=dml`）：`resolve_patch_onnx()` 只认
> 显式配置→`SVL_PATCH_ONNX`→**源码树** `work/_patch_onnx_tmp/`，冻结包无 work/ 且 Electron 未注入该 env
> ⇒ 精排（逐段近场重排 + patch_refine 两条热路径共用）落 CPU torch。当时只记 info，故瞒两周。
> ③ 双向验证：合成素材 无图 78.5s / 加 `SVL_PATCH_ONNX` 20.2s / 源码树 20.1s；大素材 **Arm D=1400.5s**
> （venv 1396.7s，差 0.3%；主循环 365s、后处理 1036s）⇒ 冻结包本体无罪。
> **零语义三方闭合**：Arm A(CPU精排)/Arm D(DML精排)/venv 三份结果批 67 段含 confidence+信封 两两差异 0
> ⇒ 纯性能缺陷，生产基线（严格 132/场景 137/负例 4）不变、三指标无需重跑。已排除：ffmpeg md5 相同、
> numpy OpenBLAS dll 相同、轮询 p50 4ms。详见 `FINDINGS_PKG_PATCH_RERANKER_CPU_FALLBACK_20261001.md`。
> ④ **落地（拍板「直接随包」，实测权重与 CLS 同源 ⇒ 净增 ≈88MB 而非 176MB）**：patch 图 78KB 入仓
> `mvp/ui/resources/models/dinov2_cls_patch/`（+asset.json 记 sha256/IO/opset）、`build-release.ps1`
> 装配+fail-fast+摘要断言、`main.ts` 注入 `SVL_PATCH_ONNX`、`_announce_patch_reranker` 把「GPU 后端+CPU 精排」
> 升为 WARNING（3 单测）、新 `accept_packaged_bundle.py` 包体验收（对未重打的包实测 `FAILED=5`）。
> ⑤ 卫生四件：适配器兜底 `'MEDIUM'→'LOW'`、`rendered/` 连同**整个应用数据目录**残留清单补进
> `PROJECT_AUDIT_20260928.md` 新 §9、侧栏 20s 周期健康重探（断→通重读设备，READY 后启/Mock 不启）、
> Mock 告警改 opt-in localStorage 开关（不复制后端判据）。
> **门禁**：后端 **460（+3）** · API **99** · vitest **132** · 双 typecheck 干净 · `test:mock` PASS。
> **待拍板**：**r5 重打**（本批修复只有重打才进分发包，且 `accept_packaged_bundle.py` 需对 r5 复跑 +
> 真机核对精修进度文案/导出默认项）；git 提交（续33后续~续36，铁律等口令）。
> 事故留痕：headless harness 曾把 `Path("")`→`.` 当数据目录，索引差点建进 win-unpacked，已中止清空并加断言。


> **▶ 2026-10-01(续35 收官) — 性能归因第一步闭环 + 44 份 GT 头补齐【下个对话从这里读起】**
> 用户令「性能归因，然后 32 份研究文档补 GT 版本标注头」「跑完就交接关机」。两项完成：
> **① 性能归因（第一步）**：实验环境重跑 test2 ON 臂 = **23.3 min** vs 打包态 62.6 min ⇒
> **打包环境罚 ≈ 2.69×**（问题在环境层非代码层）；微对照（1.mp4 建索引）打包 13.7 fps vs
> venv 12.7 fps ⇒ 推理/基础抓帧吞吐无差；新旧 on_test2 批 strip(result_id) 后 **67 段逐位一致**
> （跨环境零语义再证）。**下批候选 = 打包态关干扰单变量复跑**（关预览/无自动化观察）做精确分解。
> 产物 `work/spl_patch_arms_att_backup/`。详见 CHANGELOG「续35 归因」。
> **② GT 版本标注头**：44 份（提案 32 + 续29~35 新增 12）批量补齐——新脚本
> `apply_gt_version_headers.py`（幂等），H 类 3 份读文判定（montage=v2 代际/scene_recall=v3/
> second_signal=v3 预研），`FINDINGS_GT_CONTAMINATION_AUDIT.md` §八 +44 行登记表；
> 复扫 44→1（SOURCE_MERGE_PORT 关键词误报，实有头）。零正文结论改动。
> **交接状态**：工作区未提交（续33后续~续35 全部，等口令）；现役包 = **r4**；测试基线
> 后端 457 · API 99 · vitest 127 全绿；生产基线 严格 132 · 场景 137 · 负例 4/9 · 导出实得 139 口径内
> （导出默认已改「全部」，导出实得口径将随之上修——下次四片验收时同步更新）。


> **▶ 2026-10-01(续35 r4) — 导出默认「全部」+ UX-P1 后处理进度 + 徽标修复 + r4 重打【下个对话从这里读起】**
> 用户令「置信门槛默认全导出，改完改上面的问题」。三件落地（详见 CHANGELOG「续35 r4」）：
> ① `minConfidence` 默认 `'LOW'`（低置信也作为主片段导出；取代 A4「默认=旧行为」口径）；
> ② **UX-P1**：`apply_patch_refine` 加 `progress(done,total)` 逐段回调 + locate 在 shot_split/
> patch_refine 前后发 LOCALIZATION 阶段事件（UI「镜头分析」步骤显示「高精度精修：patch 局部精排 i/n」，
> 36 分钟静默卡感消除）；③ **UI-P3**：`IndexStatus.backend` 可空化，未知设备不再硬编码 cpu
> （侧栏「CPU」误标根因）。回归 后端 **457（+2）** · API 99 · vitest 127 · 双 typecheck · test:mock 全绿；
> 零 feature_version、定位语义零变化。**r4 = `Video-Locator-win-x64-20261001r4.zip`**
> （backend 三防 + 启动冒烟 PASS；r3 zip 已删同口径清理）。⚠️ r4 未真机全链复跑（下次分析顺带核对
> 精修进度文案 + 导出默认项）。**遗留**：打包态性能归因（62.6 min vs 实验室 1.56×）未做；
> 待拍板：git 提交（续33后续~续35 全部）/ 下批方向。


> **▶ 2026-10-01(续35 后续) — 两旋钮翻默认开（三选一选 c）+ r3 分发包重打 + 旧打包清理【下个对话从这里读起】**
> 用户拍板「按你的计划来」+「旧打包没影响就删掉」。**① 翻默认**：`config.py`
> `shot_split_enabled=True` / `patch_refine_enabled=True`（授权口径见 DECISIONS 2026-10-01 条目；
> 理由 = 质量收益是当前最大单项 + 开销比实测 2.72×，杠杆3 暂缓不立项）。
> `test_locator_service` 假桩补 `grab_frame`（默认开后 locate 走 shot_split 抓编辑帧）；
> `locator_service` 两处「默认关」注释更新；`PRODUCT_INTRO` 数字更新到新基线
> （严格 95% 132/139 · 场景 99% · 负例 4/9）+ 复定位口径改「高精度全片 ≈18 分钟（155s 成片、55 段）」
> （旧「4~7 秒/片段」是低精度热缓存口径，随默认翻转一并下架）。
> **回归**：后端 **455 OK（skipped=2）** · API **99 OK**。
> **② r3 重打**：`build_backend.py`（PyInstaller 1053 MiB，EXIT=0）→ backend.exe 冒烟三防全过
> （health 200 / BACKEND_LISTEN 公告 / release 无令牌拒启 exit=1）→ `npm run build:electron`
> win-unpacked 重建（剪映 assets 在位）→ **启动冒烟 PASS**（Electron 多进程 + backend.exe 子进程拉起）
> → zip `Video-Locator-win-x64-20261001r3.zip`。事故留痕：backend 冒烟日志误生成在
> `resources/backend/` 内被 e-builder 打进包，已从 resources 与 win-unpacked 双侧删除（内容与净构建等价）。
> **③ 旧打包清理**：r2 zip `Video-Locator-win-x64-20260929r2.zip`（1.5G）在 r3 验证后删除
> （用户本轮明确授权「没影响也用不上就删」）；win-unpacked 由 e-builder 原地重建非旧物。
> **生产现役基线自此 = 严格 132/139 · 场景 137 · 负例 4/9 · 导出实得 119/139（r3 包起生效）**。
> 边界：默认态四片读数 = 续33后续 ON 臂（四片全实跑）；抓帧优化代码仅 test1 做了整条 locate
> 全字段逐位一致验证，余三片靠机制同一性外推（与续34 边界一致）。
> **待拍板剩余**：git 提交（续33后续+续34+续35 全部，等口令）；UI 真机 E2E 复核
> （原生多选合并 / 渲染成片 / LOC-2002 告警文案，可在 r3 包上做）。


> **▶ 2026-10-01(续35) — 接线卫生小批：load_failed 撞码修复 LOC-1107 + 网络失败条幅中文话术【下个对话从这里读起】**
> Next Actions「接线卫生」桶里无需拍板的两件，零语义零契约变化：
> ① `/api/results/load` 400 体此前借用 `LOC-1103`（官方语义 = 原片索引损坏，IndexError/FeatureStoreError
> 同码族）= 一码两义违反「只增不改」码规则 ⇒ 改新码 **`LOC-1107`**，message 话术不变；
> `detail` 技术串口径经查**确认为设计内不动**（T1-2：detail 是工程师通道，前端只展示 message+码，
> API 测试本就断言 detail 含 FileNotFoundError）；测试补 code+message 断言作回归锁。
> ② `HttpServiceAdapter.ts` 网络级失败消息 `cannot reach backend: …` 改中文话术（技术 detail 留括号内，
> 续21 登记尾巴；vitest 只断言异常类型，零改动）。
> **未动（仍登记）**：侧栏健康重探 / `rendered/` 并入清理清单 / Mock 不产 warnings / 竞品「渲染失败仍出 XML」待拍板。
> **回归**：后端 **455 OK（skipped=2 既有）** · API **99** · vitest **127** · 双 typecheck 干净；
> 零 `feature_version` 变更，生产三指标不变。与续33后续/续34 改动同样未提交（铁律等口令）。
> **待拍板不变**（续34 交接的四项：两旋钮默认值三选一 / git 提交 / r3 重打 / 杠杆3 立项）。


> **▶ 2026-10-01(续34) — shot_split/patch_refine 抓帧提速：归因 grab=77.6% + 缓存+并行落地 = 全片 1.90× 零语义【下个对话从这里读起】**
> 起因：续33 后续两旋钮进生产路径，ON 臂 31–44min vs OFF 7–8min（旋钮自身 ~24–36min），档案明确「未做单臂拆分归因」。
> 用户问「性能有什么可优化」→ 拍板「都要」（先归因拿基线，再落零语义改动，对比提速 + 验逐位一致）。
> **归因（杠杆0）**：新探针 `mvp/scripts/probe_split_patch_timing.py`（monkey-patch 计时，`off_{case}批 → shot_split → patch_refine`
> 复现 ON 臂后半段，不重跑整条 locate）。全片 test1 baseline 臂 **grab 合计 978.9s = 77.6% wall**（源片 ffmpeg spawn 822.9s/1860次
> = 65.2%、编辑片 156.0s = 12.4%）、embed.dual 10.8%、patch_score.numpy 9.0%、embed.cls 2.2% ⇒ 与历史 `_patch_rerank_span`「grab 占 81%」
> 同量级，**瓶颈是 ffmpeg 逐帧 spawn 不是模型推理**。
> **落地（杠杆1+2，零语义）**：① `locator_service.py:1105/1123` 两旋钮 `grab_frame` 从裸 `self.ffmpeg.grab_frame` 换 `self._grab_frame_cached`
> （512 FIFO 缓存）；② 两模块加可选 `grab_frames` 批量参数 + `_grab_many` helper，生产传 `self._grab_frames_parallel`（4 线程），
> 把「grab→embed 逐帧交错」重构为「**先并行批量 grab → 再主线程串行 embed**」。**遵守续6 教训：DML forward 保持串行**
> （DML EP 多线程并发 Run 段错误），只并行 grab（纯 IO+解码），`ex.map` 保序 ⇒ 帧内容与顺序不变。`grab_frames=None` 默认回退逐帧
> ⇒ 离线验证器（`validate_patch_refine.py:85`/`validate_split_patch_refine.py:91,96`）+ 单测零回归。
> **验证（整条 locate 全字段逐位一致 = 最强零语义证明）**：① 微探针三向 span 一致
> **baseline_full == optimized_full == ref(on_test1 生产参照) = TRUE**（各 55 spans）；② 升级验证 = 跑完整
> `srv.locate()`（优化后代码、双旋钮开、test1 全片），输出与续33 原始串行生产产物 `on_test1.results.json`
> **strip(result_id) 后全部确定性字段逐一比对差异段数=0**（confidence_score/candidate_rank/alternatives/reasons/
> original_segments/信封字段全比；产物字节数 99953==99953）⇒ 零语义证明达「完整生产 locate 路径全字段级」。
> **全尺度 A/B（旋钮段）：1262.3s → 664.9s = 1.90×**（省 10.0 min/片；split 127.2→66.8、refine 1135.1→598.1）；
> 缓存把 raw grab 2591→1691 次（省 35%），并行摊剩余到 4 线程。8 段子集先行 A/B = 2.09×。
> **缓存驱逐路径全片额外覆盖**（1691 grab/512 上限 ⇒ ~3 次 clear，多线程竞争下仍逐位一致）。
> **整条 locate 实测（用户侧）**：opt_full = **1052.4s = 17.54 min**；P（pre-knob 管线，旋钮无关）= 387.5s；
> serial_full = P+1262.3 = 1649.8s = 27.5 min ⇒ **full-locate 提速 1.57×**（Amdahl：P 占优化后 37% 未被本次触碰，
> 故 1.57× < 旋钮段 1.90×）。**ON/OFF 开销比 串行 4.26× → 优化 2.72×（实测，确认此前推导的 2.4~3×）**。
> **回归门**：后端 **455 OK (skipped=2)** · API **99 OK** · 零 `feature_version` 变更 · 生产三指标不变（旋钮默认仍关）。
> **边界**：两个提速口径须分清——旋钮段 1.90× / 整条 locate 1.57×（用户实际体验）；只验 test1 全片
> （2mkv/test2/test3 未跑全片 A/B，零语义由整条 locate 全字段一致+回退兼容+全绿保证，提速机制 grab 占比 77.6% 与片子无关可外推）；
> 未做杠杆3（改 REFINE_FPS/窗口/CLS 预筛——会改结果需三指标回归）。
> **归档**：`FINDINGS_SPLIT_PATCH_GRAB_PERF_20261001.md`；产物 `work/spl_patch_timing/*`（baseline/optimized × 8段/全片 + ref_on_test1 + fulllocate_on_test1）。
> **待拍板**：① 两旋钮默认值仍关——**ON/OFF 开销比已实测降到 2.72×**（高精度全片 locate = test1 实测 17.54 min，
> 不再是原「30–45 min/片」），续33「三选一」时间口径据此更新，(c) 选项 `PRODUCT_INTRO` 文案可下修到「高精度 ≈18 min/片（test1 实测，片长相关）」；
> ② 本批 git 提交（探针×2 + 3 源码文件 + FINDINGS + 档案，等口令）；③ r3 分发包重打（需授权）；④ 杠杆3 是否立项（会改结果需三指标回归）。


> **▶ 2026-09-30(续33 后续) — 两旋钮生产路径双臂验收 = PASS（严格 130→132 · 导出实得 107→119 · FP 4→4）【下个对话从这里读起】**
> 起因：离线组合验证（把 runtime 模块套在既有结果批上）给 132/119，但**没走完整 `locate()`**；
> 默认值翻转与 r3 打包都需要生产路径证据。
> **执行**：新增 `mvp/scripts/rerun_split_patch_arms.py`（off/on 双臂，DML 硬断言，只跑生产 `srv.locate()`）
> + `diag_split_patch_flips.py`（判据机制分解）+ `review_spl_patch_flip.py`（按评估口径选行的 12 帧读图）。
> **OFF 臂等价性**：off_2mkv/off_test1 与 2026-09-29 现役默认批**逐位一致、逐 ID 零翻转** ⇒ test2/test3 的
> OFF 臂直接复用现役默认批（省一轮重复计算）。
> **结果（四片汇总）**：严格 **130→132** · 导出实得 **107→119（+12）** · 场景 137 持平 · 负例 4→4 持平 ·
> 支撑 646→1086。**与离线组合验证（132/119/4）逐位一致 ⇒ runtime 接线与离线模块行为等价**。
> **翻转 14 行机制分解**：13 增 1 损；全部 = 主 span **direct** 判据，**union 装配条款命中 0 行**
> （"p30 靠装配命中"的担心被证伪：ON 臂 p30 命中 s60 子段主 span 2002.69–2003.31）。
> 9 行 mid_in/cov 实质覆盖（p02/p05/t1r14c/t1r16/t1r19/t1r20/t1r23/t1r30a/t2r01c）·
> 4 行靠 ±2s 容差记账的亚秒级相邻（p03/p30/t1r02/t3r23）· **1 行真损失 = t3r02a**
> （OFF 宽 span 331–352 覆盖 GT，ON 窄化到 338.09–339.39 丢覆盖）。
> **逐张读图 6 张**（`work/spl_patch_visual/`）：p05 真增益（碉堡内景，OFF 落山谷空镜）· p30 真增益
> （同室另一时刻 → GT 邻域，≈203s 时刻修正）· t1r02 真增益（同段落水镜头，<1s 相邻）· t1r20 真覆盖 ·
> t3r23 **打折**（巨人出现在 span 结束后 ≈0.4s）· t3r02a 真损失（火场另一时刻 + 丢室内大厅）。
> **新增硬事实 = 耗时代价 4~5×**：ON 臂单片 31–44 分钟（2mkv≈42 / test1≈31 / test2≈40 / test3≈44，
> 合计 ≈2h35m）vs OFF 臂 7–8 分钟；主开销源 = patch_refine 歧义段 top-K ±5s 局部窗 patch+global DML 推理
> （未做单臂拆分归因）。**因此不建议无条件翻默认**。
> **归档**：`mvp/benchmark/user_case/semantic_signal/FINDINGS_SPLIT_PATCH_PROD_ACCEPT_20260930.md`；
> 产物 `work/spl_patch_arms/*`（结果批 + metrics_off/on + flip_caliber.json）+ `work/spl_patch_visual/*`。
> 零 `mvp/src` 改动、零 `feature_version` 变更；基线健康检查 = 后端 **455 OK**（skipped=2）。
> **待拍板（新增，与 r3 绑定）**：两旋钮默认值三选一 ——
> **(a)** 维持默认关 + UI/导出面板暴露「高精度复核」开关（按需付时间）；
> **(b)** 只翻 `shot_split_enabled`（收益按离线口径 ≈ 导出 +8，耗时待拆臂）；
> **(c)** 两个都翻默认开 + 把 `PRODUCT_INTRO` 时间口径改成"高精度模式 ≈30–45 分钟/片"。
> 无论选哪个都需 r3 打包 + 真机复核（打包需授权）。


> **▶ 2026-09-30(续33) — GT 工单裁决落地 + (E) 线六形态 + 两模块 runtime 化【下个对话从这里读起】**
> **GT 逐帧裁决已落地**：18 条工单（16 疑错/2 同源重复）经「检索判别→六拼图读图→用户逐帧确认」
> 全链，12 行重锚定 + 2 行注释（corrections 落账、快照 `work/gt_backup_pre_ticket_20260930/`）。
> 两条翻案：t2r05a"特征层失败"=GT 窗错；t2r03a 旧 HIT=双错相消。**GT 镜头级边界精修尝试判负**
> （多镜/蒙太奇段 1:1 映射不成立 + CLS 同景歧义，证据 `work/gt_boundary_refine*/`），GT 维持现状。
> **新基线**：严格 130（组合形态离线 132）· 导出实得 107（组合离线 119）· 场景 137 · 负例 4/9。
> **(E) 场景内信号线六形态全记录**（`FINDINGS_INSCENE_REFINE_PROBE_20260930.md`）：
> 形态1 主span平移判负(−2)；形态2 逐镜子span指标盲（信号准）；形态3 拆分v1 未达门槛(+5/−5)；
> **形态4 拆分v2 = 可用（+8/严格结构性零回退）**；形态5 序列重选判负（信号真、独裁钝）；
> **形态6 patch 局部精排（local_refiner 形态）= 信号证实**（盲区 4/5 峰落 GT 窗、9/9 读图；
> p20 连 patch 都盲 = 真盲实锤）。纯数据判负审计：patch 融合"全局打分"判负维持但局部形态未测已补、
> DTW 排序/精排用途分账、AKAZE/E3 维持。
> **runtime 化已落地（代码进主链路、两开关默认 False）**：
> `engine/localization/shot_split.py`（谷值切镜拆多镜段，宽 span 保全）+
> `engine/localization/patch_refine.py`（歧义门 + top-K 候选 ±5s patch+global 精排，
> 双信号融合判据 patch≥0.05 或 patch≥0.02∧序列≥0.05，老主降子）+
> `PatchReranker.frame_dual`。接线 `locator_service.locate`：门 → 拆分 → 精排 → 结果批。
> **组合形态离线验证（`validate_split_patch_refine.py`）**：严格 130→132 | 导出 107→119（+12）|
> FP 4→4 | 15 翻转读图 ≈11 真增益（含 2 行 MISS→HIT：p05/t3r23）、1 真损失（t3r02a）、
> 2~3 行 union 装配打折（p30 疑似仍 1799 装配命中）。回归：后端 455 全绿 · API 99 ·
> 单测 +11。feature_version 零变更。
> **git 已交**：`3ed468c`（feat runtime）+ `49e79e0`/`63bc24b`/`0480f1a`（docs）已推 origin/master。
> 事故留痕：组合验证脚本复用输出目录覆盖单跑产物（"输出路径自带区分度"再证）。
> **待拍板**：① 两旋钮默认值翻转（建议随 r3 真机复核 UI：结果列表变多/告警文案）；
> ② r3 分发包重打（需授权）。研究遗留：指纹粒度升级（patch 线换形态已部分验证）、
> p20/p30/p34 类"重复布景/近同构镜头"深盲区（连 patch 都分不开）。

> **▶ 2026-09-30(续32 后续) — 18 条 GT 工单逐帧裁决闭环：GT 重锚定 + 新基线 130/107 + (E) 立项影响面统计【下个对话从这里读起】**
> **裁决链（铁律全流程）**：生产检索自动判别（16 疑错 / 2 同源重复 / 0 推翻）→
> `review_gt_tickets_visual.py` 六张拼图逐张读图（每行 GT_ED|OURS|GT_OG，**18/18 与判别一致**，
> `work/gt_tickets_visual/`）→ **用户逐帧裁决「18 条全部确认（按建议口径改）」**。
> **应用（`apply_gt_ticket_reanchor.py`）**：12 行重锚定（t2r02a/t2r05a/t3r03a 多工单行取并集；
> 镜头级边界精修后续另做）+ 2 行同源重复注释（p24/t2r03b 窗不动）；corrections 逐条落账；
> 改前快照 `work/gt_backup_pre_ticket_20260930/`（GT 文件不在 git）；manifest 哈希已更新。
> **两条定性翻案**：① t2r05a「我方唯一特征层失败（蒙太奇 rank77）」= **GT 窗错**，正式翻案；
> ② t2r03a 旧 HIT = **双错相消假 HIT**（旧 GT 窗 3406 泥地与我方 3406-3408 相合，ED 内容实为 3419 围栏人群）。
> **新基线（同一结果批，仅换 GT）**：严格 **130/139**（+3）· 导出实得 **107/139**（+7）·
> 场景 137/139（持平）· 负例 4/9（持平）· 截等长主 span 111/139（旧 105）。
> 对竞品复现链真实领先 = **107 vs 83**（导出实得口径）。回归：后端 **444 OK** · API **99 OK**
> （后端/UI 源码零改动，vitest/typecheck 不涉）。归档
> `FINDINGS_GT_TICKET_ADJUDICATION_20260930.md`。
> **(E) 立项影响面统计（`probe_inscene_offset_impact.py`，新 GT 口径）**：导出实得未命中 32 行 =
> **同场景族 23 行**（gap≤7s 16 / 7–30s 6 / overlap 1）+ 30–120s 5 + >120s 3（候选层）+ no_segment 1
> ⇒ **(E) 可救池 = 23 行**（替代旧「上限 +27」口径）。
> **口袋测试集重推（用户令，多模态复核，`probe_pocket_retest_gt130.py`）**：13 条候选 →
> 三模态交叉（四拼图 13 行逐张读图 + 落窗算术 + 生产检索 top-20）→ 剔 2 条容差类
> （p14 / t2r01c，均 PROXY 画面不符）⇒ **(E) 测试集 = 8 条生产未命中真口袋**
> （p02/p03/p20/p30/p34/t1r14c/t2r06c/t3r02c；同场景偏移 6 条 + 跨景误配 2 条）；
> 另 3 条单列（t3r05/t3r26 宽 span 生产已 HIT、t3r01 检索三窗全不支持低置信）。
> 旧 14 条中 t2r02a/t2r05a/t2r05b 因重锚定转我方 HIT 退出（正是裁决修复的行）。
> 产物 `work/combo_pocket_retest_gt130/`（旧目录不覆盖）。
> **(E) 探针两形态实测（2026-09-30 续32 后续二，`FINDINGS_INSCENE_REFINE_PROBE_20260930.md`）**：
> 形态1 主 span 平移 = 严格零回退但产品导出 −2、口袋 1/8 → **判负**；形态2 分镜×逐镜 span =
> 三口径零变化，**但信号被证明精准**（s0 逐镜 span 精确落进 p02/p03 GT 窗，读图+算术双确认）。
> **病灶改判**：8 条口袋基线严格口径本来就 HIT（宽子 span cov 记账），瓶颈 = export_project
> 硬编码只用主 span ⇒ (E) 改判为「**导出 span 选择/段级拆分**」（上限 23 行差集，产品导出语义
> 变更）→ **待用户拍板**；拍板前零 runtime 改动、feature_version 零变更。
> **(E) 探针三形态全部实测完毕（2026-09-30 续32 后续三），(E) 按预定门槛关闭**：
> 形态1 主 span 平移判负（导出 −2、口袋 1/8）；形态2 分镜×逐镜信号精准但三口径零变化；
> 形态3 段级拆分（`probe_inscene_split.py`）= 导出 +5（< 门 +10）、严格 −5（窄化 span 丢宽 cov
> 记账，t3r01 读图坐实）、口袋 2/8 ⇒ **未达标，按预定计划归档负结果并关闭**。
> 「同场景 2–7s 偏移」族终局定性：多镜段子族 = 段粒度问题（拆分可修，+5/−5 交换留档待用户决定）；
> 单镜段子族 = 1fps CLS 指纹粒度上限（与 patch/密度线同因，维持关闭）；跨景误配（p30/p34）另病立票。
> 零 runtime / 零 GT / feature_version 零变更。归档 `FINDINGS_INSCENE_REFINE_PROBE_20260930.md`。
> **(E) 形态4（拆分 v2）= 可用级（2026-09-30 续32 后续四，用户令「数据只是标准，学竞品改到能用」）**：
> 谷值切镜 + margin 门 + 宽 span 保全 ⇒ **导出 107→115（+8）| 严格 130→131（结构性≥兑现）|
> FP 4→4**；10 行翻转读图 = 8 真增益 + 1 union 作图局限 + 1 真损失（t3r02a，严格由父 sub 保住）。
> **runtime 化（分段层改造 + 全套回归 + 真实导出冒烟）待用户拍板**；拍板前零 runtime 改动。
> 形态1 判负 / 形态2 指标盲（信号准）/ 形态3 未达门槛——全记录在
> `FINDINGS_INSCENE_REFINE_PROBE_20260930.md`。
> **git 已交（2026-09-30 用户令）**：三笔提交 `f03ea65`（mvp 源码+测试）/ `b8da8a3`（研究脚本+findings）/
> `5b7e338`（档案）已推 `origin/master`；⚠️ 仓库当前 **Public**（未登录 API 200），用户知悉，
> 如需私有需网页翻转（SSH 改不了可见性）。GT json 依 .gitignore 设计不入 git（datasets/ 整体排除）。
> **(E) 形态5 + 机制诊断（2026-09-30 续32 后续五）**：6 行「修不了」行 GT 全在检索 top-20（候选层
> 有答案）；全片序列投票诊断 = t1r14c/p30 决策层可修、p20/p34/t3r02c CLS 真盲（竞品赢在 patch
> 级空间对应 = 形态性未穷尽实证）。形态5（投票峰入候选+对位分重选，margin 0.015）：严格/FP 结构性
> 保住、**导出 107→105（−2）判负**——信号真实（两预测目标全中+8 增益）但独裁重选 churn 换坏 10 行；
> runtime 化须融合评分（决策层重设计，待拍板）。四形态+诊断全记录在
> `FINDINGS_INSCENE_REFINE_PROBE_20260930.md`；**可用级仍只有形态4（导出 +8）**。
> **(E) ①② 执行完毕（2026-09-30 续32 后续六）**：**① 形态4 runtime 化落地**——
> `engine/localization/shot_split.py` + `pipeline.shot_split_enabled`（**默认关**）+
> 接线 locate 退化门后；新单测 7 项 + 后端 444→**451** 全绿 + API 99；真实验收 PASS
> （test2：关侧与现役逐段一致、开侧 54→67 段/EDL 39→41、严格 18→18、FP 0→0、导出 14→15）。
> **② 融合评分建议搁置**——形态5 margin 0.05 补跑 = 导出 107→108（+1）、t1r14c 修复，但
> 8 增 7 损净收益薄，独裁重选收口；6 行终局 = t1r14c 可修 / p30 险胜 / t2r06c 半盲 /
> p20/p34/t3r02c CLS 真盲（留指纹粒度升级评估）。全记录
> `FINDINGS_INSCENE_REFINE_PROBE_20260930.md`。新改动未提交（等口令）。
> **GT 镜头级边界精修尝试 = 判负（2026-09-30）**：两版自动精修（argmax 中位数 / 稠密投票）
12 行提案读图多数与已确认内容矛盾（多镜/蒙太奇编辑窗 1:1 映射不成立 + CLS 同景歧义）⇒
**不采纳，GT 维持重锚定后现状**；自动精修仅 ED 单镜段可靠，未来如做须人工逐行。
证据 `work/gt_boundary_refine*/`，结论见 `FINDINGS_GT_TICKET_ADJUDICATION_20260930.md` §7。
> **(E) 形态6 = patch 局部精排信号证实（2026-09-30 续32 后续七，用户令「开始」+「不纯数据定案」）**：
> `probe_patch_local_refine.py`（竞品 local_refiner 形态首次实测，global .45/patch .55）：盲区 4/5
> patch 峰落 GT 窗且 9/9 全量读图确证（t3r02c CLS 全盲行被 patch 分开 margin .115；p20 连 patch
> 也偏好邻镜 = 真盲实锤）；对照 4/4 稳定。**部署形态 = top-K 候选各自局部精排再择优**（竞品
> TopK-DTW+local_refiner 组合；t3r02c +19s / p30+p34 82-204s 超局部窗，仅落位邻域微调不够）。
> 纯数据判负审计：patch 融合「全局打分」形态判负维持但局部形态未测已补；DTW 排序/精排用途
> 应分开记账；AKAZE/E3 维持。
> **形态6 runtime 化落地（2026-09-30 续32 后续八，用户令「开始1」）**：
> `engine/localization/patch_refine.py`（歧义门 + top-K 候选 ±5s patch+global 精排 + margin 0.05
> 切主 + 老主降子；`PatchReranker.frame_dual` 双输出接口；`pipeline.patch_refine_enabled` **默认关**）。
> 回归：新单测 4 项、**后端 444→455 全绿、API 99**。**离线验证 PASS**（runtime 模块套四片生产批）：
> **严格 130→130 | 导出 107→109（+2）| FP 4→4 | 仅 2 翻转零损失**（t1r14c ✓、t3r23 ✓，读图真增益）
> ——形态5 的 churn 问题被歧义门+patch 判别力解决。t2r06c/t3r02c/p30/p34 未翻转（歧义门保守，
> 需候选层配合），留指纹粒度升级。执行事故留痕：网格帧曾误抓编辑片已修。
> **组合形态验证（shot_split → patch_refine，续32 后续九）= 显著正收益**：
> **严格 130→132 | 导出实得 107→119（+12）| FP 4→4**；15 翻转读图 ≈11 真增益
> （含 2 行 MISS→HIT：p05/t3r23）、1 真损失（t3r02a）、2~3 行 union 装配需打折。
> 段级混合查询稀释信号是 patch_refine 单跑不动盲区行的根因，组合后解决。
> 事故留痕：组合验证脚本复用输出目录覆盖单跑版产物（教训再证）。回归 后端 455 + API 99 全绿。
> **git 已交（2026-09-30 用户令）**：`3ed468c`（feat: shot_split+patch_refine runtime, 默认关）
> + `49e79e0`（docs: (E) 线收口归档）已推 origin/master。
> **待拍板剩余**：两旋钮默认值翻转（随 r3 真机复核）/ r3 分发包重打（需授权）。

> **▶ 2026-09-30(续32) — 交接铁律立档 + 三条历史判负补读图复核 + 合并夹具缺陷修复 + 18 条 GT 工单自动判别**
> **铁律（用户立）**：任何影响采纳/关闭/翻默认/判负/换架构/改口径的结论不得只靠数据——逐张读它点名的
> 样本 + 至少一条独立证据。全文置顶写入 `PROJECT_HANDOFF.md`（含五方面复核清单 + 历史复核台账）。
> **用户随后令撤除我加进 AGENTS.md Working Rules 的那条**（已撤，AGENTS.md 恢复原状）；
> STATE 顶部 banner 版被 `agent-context checkpoint` 冲掉（该工具只保留 12 章节）⇒
> **规则权威位置 = HANDOFF 置顶**，STATE/TODO 只留本条记录。
> **补复核三条（`mvp/scripts/review_retro_three.py`，三张图全读）**：① 续28 ordered_search 判负**成立且
> 更强**——4 条独家回退全真内容错，且 t3r05/t3r13/t3r29 三条互不相干查询被 FULL 臂拖到**同一落点
> 5088-5089**（锚点/主线锁 = 多查询坍缩）；② 索引密度 2fps 判负**成立且保守**——4 项翻转里 1fps 与
> 2fps 落位要么逐帧相同（p14/p08）要么都错（p30/p34），密度没改变任何一帧的画面归属；
> ③ 续27 合并**翻出夹具缺陷**：拼接点重复 [K,K′]≈3.5s、其后时间轴偏移（读图坐实），而 39 条 GT 全在
> 拼接点前（max 2427s < join 3837s）故原验收没暴露。
> **缺陷定性更正（说错留痕）**：初版写成 `source_merge.py` 切点不互斥——**错**，产品只 concat 不切分；
> 重叠两半是验收夹具 `-ss key_t` 起切 part2 的 copy 语义落点早 ~3.4s。已修夹具：part2 以 part1 实际末帧
> 起切 + 互斥断言（|part1+part2−原片|≤0.5s）+ **时间轴同一性常驻锁**（拼接点前 δ=0、拼接点后 δ 恒定
> ≤0.5s、全片采样同 t 帧逐字节比对；首版锁"同 t 相等"过严被 copy-concat 容器粒度误报，改"位移恒定"）。
> 重跑实测 δ 前 0 / 后恒 **0.167s**（4 帧，无重复无累积，`work/merge_accept/timeline_shift.json`），
> 读图 5 行确认拼接点前后连续单调无重复段（`C2_join_after_fix.png`）；验收重跑 EXIT=0：
> 合并批 36/39 · 39/39 · FP 3/4，与基线**逐 ID 零翻转**，新并列口径复现（导出实得 29/39）
> ⇒ 续27 验收结论在正确切分的合并片上重新成立，合并产物拼接点后**恢复可用**。
> **18 条 GT 工单自动判别（`mvp/scripts/probe_gt_tickets_retrieval.py`，生产 CLS + DML 硬断言）**：
> ED 帧 → 原片 1fps 索引 top-20 ⇒ **GT 疑错 16 / 同源重复 2（p24 rank14、t2r03b rank12）/ 推翻读图 0 /
> 无效 0**，与读图裁决零冲突；含 **t2r05a**（档案原"我方唯一特征层失败/蒙太奇 rank77"定性大概率是
> GT 窗侧问题）。**GT 修改须用户逐帧确认（护栏），本批只产工单不改 GT**（`work/gt_tickets_retrieval.json`）。
> **同批前段（续31 补二/补三）也已落地**：① 三指标并列读数 `main_hit`（导出实得 100/139 vs 127）；
> ② 重复认领告警的两种实现路径均被实测否决（主 span 胜率 95%；LOC-2003 误报率 97%）；
> conf_v2 线**正式关闭**（36 段读图 = 真内容错仅 4 段，靶子是假的）。
> **测试基线**：后端 **444** · API **99** · vitest **127** · 双 typecheck 干净。生产三指标不变。
> **待拍板**：git 提交（246+ 条）/ 分发包 r3 / **14 条 GT 行逐帧裁决**（工单已备）/ 下批方向
> （清单 3 入库层四件 / 清单 4 大文件鲁棒性 / 锚点线以「导出实得」判据重开）。

> **▶ 2026-09-29(续31) — 用户撤裁决重做「退化拒绝门」= 分腿归因 + 并集缺陷修正 + 同构安全形态 LOC-2002 落地【下个对话从这里读起】**
> **先更正档案错判**：TODO/STATE 把 (B) 写成"已批未做"不实——续19 已实现（`engine/localization/
> degradation_gate.py`）、已接线（`locator_service.py:1087-1089`）、已双臂否决（DECISIONS 续19
> 严格 −14）。用户仍选「撤裁决重做」⇒ 按续21-E1 自立的纪律执行：**先影响面统计，再谈形态改造，
> 不做 GT 反标调参**。
> **① 影响面（`mvp/scripts/probe_degradation_impact.py` 新，五臂消融，零 GPU）**：四片 224 可回答段
> 中 31 段（13.8%）存在单一伙伴 ≥0.8 的重复认领，但**无一属竞品那种伪影**；三条机制 = 相邻细段
> 拼接铺满同一区间（2.mkv seg3/25/52 并集 0.88~1.00 却无单一伙伴）、宽窄 span 分层包含
> （test3 seg17 12.6s 场景池宽 span 被 6 条 2s 窄段"遮挡"）、**对称重复 + 等证据 = 掷硬币**
> （test3 seg41 HIGH 0.87 与 seg61 HIGH 0.89 指向完全同一 2s 源区间，读图=同一镜头复用两次）。
> **② 分腿归因（续19 没做）**：拒识腿单独 = 严格 −2 / 场景 −1 / **负例 ±0**；续19 的 −14 里
> **test2 的 −5 全来自子 span 腿「全低即整段清空」形态**，与竞品那条判据无关。两实现互证
> （`replay_degradation_gate.py` 同批 127→118/137→132 逐位一致）。
> **③ 真缺陷修正（runtime）**：`duplicate_ratio` 把邻居重叠**累加**（邻居互叠时重复计数）→ 改
> **并集**；test3 seg17 由误拒转为保留 ⇒ 回收 严格 +2 / 场景 +1。三条单测锁死。
> **④ 裁决**：`degradation_gate_enabled` **维持默认关**（第四次独立确证，拒识=掷硬币且负例零改善）。
> **⑤ 新立同构安全形态（进 runtime 默认开）**：`duplicate_claim_groups/warnings` = 只**提示**不删答案，
> 挂既有 `last_export_warnings` → `/api/export` → 导出对话框（**UI 零改动**）。判据 = 重叠/较窄侧 ≥0.8
> **且窄宽比 ≥0.5**（下限由读图抓到的假阳性逼出：首版把 test3 30/31 段报成重复，画面实为 Thorin 与
> Thranduil 两个不同角色不同镜头，只是 8s 宽 span 含住 2s 窄 span）。旋钮 `export.duplicate_claim_warn`
> /`_min_ratio`/`_min_width_ratio`；计算时机 = clip 几何定稿后（门槛→吸附→切点展开→剪映取材）。
> **真实导出冒烟（`mvp/scripts/accept_duplicate_claim_warning.py`）**：2mkv/test1 零组、test2 一组
> （12、13 段→3277.0-3280.6s）、test3 两组（34、37 段；42、62 段），**开/关两侧 EDL 逐字节一致**
> （不动数据硬证），逐张读图确证三组均为同镜头重复素材。产物 `work/dupwarn_accept/`。
> **全量逐图复核（用户令「全部读一遍」，`mvp/scripts/review_degradation_visual.py`，16 张拼图 /
> 本批累计 25 张逐张读毕）**三条新事实：① 拒识腿的 −2（t3r12/t3r18）**都是真画面损失**，不是 GT
> 口径假象（s41 ED 与 OM 同为山岩镜头 = 答案正确，被无归属的 s61 以 0.89>0.87 挤掉；我中途按
> 「s30 中帧落在相邻镜头」判过一条属 GT 侧，读完更正）；② **承重的子 span 其 `cover` 字段是
> 0.00~0.19** ⇒ 「cover 低 ≠ 该 span 无用」，`min_scene_coverage` 与我方子 span 语义不匹配（这才是
> test2 −5 的根因，也解释「全低则保留」为何能免掉）；③ LOC-2002 在 2.mkv 零组**不是漏报**：
> 那 3 对每对都含一条 LOW（0.41/0.38）被导出门槛挡在工程外，告警口径 = 工程内重复素材。
> 出图脚本自身两条缺陷也在这轮暴露并修（OM 格误用编辑时间轴 ⇒ 右列全错帧；拼图文件名不含 case
> ⇒ 四片互相覆盖），与 `--report` 同族教训：**出图/出表脚本落盘路径必须自带区分度**。
> **测试基线**：后端 **433→444** · API **99** · vitest **127** · 双 typecheck 干净 · `test:mock` PASS。
> 生产三指标不变（127/139·137·4/9·105），零 `feature_version` 变更。归档
> `FINDINGS_DEGRADATION_LEGS_AND_DUP_CLAIM_WARN.md`；DECISIONS 续31 条目已立（含撤裁决记录）。
> **尾巴**：Mock 适配器不产 warnings（dev 态看不到 LOC-2002）；打包 exe 真机复核告警文案（需授权，
> 可与续30 渲染按钮并一次）；`min_scene_coverage` 整段清空形态缺陷未改 runtime（门默认关无生产影响，
> 探针已量化「部分丢」形态可免掉 test2 的 −5）；竞品「相近片段自动合并」未做（本次只提示）。
> **执行事故留痕**：首跑误用 `replay_degradation_gate.py` 硬编码输出路径，覆盖了续19 的
> `work/degradation_gate_ab.json`（`work/` 不在 git ⇒ 不可恢复）；聚合数字在 DECISIONS/CHANGELOG
> 有留痕、结论未受影响，已补 `--report` 参数防复发。
> **待拍板剩余**：git 提交（实测 **244** 条未提交，用户本轮选「暂不提交」）/ 分发包 r3（用户选
> 「等下批做完一起打」）/ 下批方向 = (A) 成片缺口标记、(C) 入库层四件、(D) 大文件鲁棒性四件。
>
> **▶ 2026-09-29(续31 补二) — 用户追问「架构不行就换 / 有没有整套换过 / 判负后改过算法吗」→ 补测「竞品整套链四片双口径」**
> ① **整套换 = 净退步，已被量化**：同判据同粒度下复现链截等长 **83/139** vs 我方 **105/139**
> （去 ±2s 容差 = 67 vs 85）；候选层复现链 **9 条 GT 从未进表** vs 我方 oracle 仅 1 条 rank>20；
> 其完整 span 读数 124 接近我方 127 **全靠 TN 场景 span 装配效应**（test1 41 vs 10 最夸张）。
> 逐 ID 差集 = 复现独家 16 vs **我方独家 38**。链路一致性已核（两份 manifest 160 路径仅 32 不同且全为
> 输入/统计；A1–A25 假设逐字一致；G5 从未扩片且 test1 上零翻转）；ED 窗长复现链更短 ⇒ 非窗长红利。
> ② **真挖到东西**：16 条里 **14 条是真口袋**（剔 2 条 ±2s 容差漏洞），6 张 16 行逐张读图确认
> ≥8 条属**「同场景内 2–7s 偏移」**= 我方唯一主病灶族；复现链靠**场景内稠密局部对应**
> （每场景 5 关键帧 + patch 主力 + 段内 DTW）锚对，我方 `patch v2` 是 ±30s/4s 步长/margin>0.075 的
> **近场稀疏重排** ⇒ 该挖它的**表示粒度**、不是它的判据（同 fast_global「吸收性质不接受前提」路径）。
> ③ 3 条口袋暴露我方**命中质量虚高**：p30 生产 HIT 实为 577s 宽事件 span 兜住（落点差 200s）、
> p34/t2r05b 靠宽窗 cov 吃窄 GT 窗。
> ④ **我方口径需加注**：`within = span ⊆ GT窗±2s` 在截等长口径下给我方 +18 行（105→85）、
> 给复现链 +16 ⇒ 方向不变（delta +22→+18），但 105 这个被引用数字要标口径；M1 章程门用双臂同口径
> 差值故不受影响。
> ⑤ **下一步（第 1 项产出物 = 立项材料）**：以这 14 条为测试集做「场景内稠密局部位置信号」影响面统计
> + 无 GT 反标探针，门槛 = 命中 ≥1/3 且 127 条零回退（patch v2 同规格）。
> 归档 `FINDINGS_COMBO_CALIBER_ALL_CASES.md`；新脚本 `probe_combo_caliber_all_cases.py` /
> `probe_combo_pocket_visual.py`；产物 `work/combo_caliber_all_cases.json` + `work/combo_pocket_visual/`。
> 零 runtime / 零 GT / 零 GPU。**「形态性未穷尽」清单第 2~5 项（conf_v2 换饱和判据 / 两级采样探针 /
> E3 换载体 / min_scene_coverage 换判据）仍未动。**

> **▶ 2026-09-29(续30) — 下批偷向 = 成片渲染（差集 TOP1）移植 + 真实验收【下个对话从这里读起】**
> 用户令「先下批偷向吧」→ 按档案排序做竞品 `exporting.rendering.video_renderer`（表 D 唯一
> 判「缺失」的 TOP1 项）。**形态确证**（blob #138，527 常量 / 75 条中文 docstring 全读）：
> 逐段 CFR 重编（`fps=fps=`+`trim`+`setpts`+`round=near`+`-frames:v`）→ 合并优先流复制
> （`-f concat -c:v copy -avoid_negative_ts make_zero -movflags +faststart -sn -dn`）失败回退
> 重编码 → 逐段帧数校验（`nb_frames` 快速 / `-count_frames` 严格，文案「帧数错误: 第 N 段…」）
> → 硬件编码器失败拉黑回退软件 + 停滞看门狗（120.0）+ `-progress pipe:1` 读取线程 +
> terminate/wait/kill + 片段并发（2/6）保序 + 稳定命名产物。
> **用户拍板两处口径**：① **紧凑拼接**（不落地竞品黑场空档腿）；② **音轨取原片对应区间**（不用解说轨）。
> **落地**：`media/ffmpeg/timeline_render.py`（纯函数命令构造 + `TimelineMovieRenderer` 监护执行，
> 复用续27 的 `concat_list_text/parse_progress_seconds/error_summary/_runner`）+
> `RenderConfig`（默认只由显式入口触发）+ `paths.rendered_root()` + `ProgressStage.RENDER_MOVIE` +
> `locator_service.render_movie()`（**与 export_project 同一套 clip 计划**：门槛→吸附→切点展开）+
> `POST /api/tasks/render`（`Task.kind=analyze|render`、渲染批**提交时锁定**防竞态、worker 分派）+
> UI `startRenderTask`/`useRenderMovie`（轮询进度/取消/打开目录）+ 结果页导出对话框「成片渲染」区块。
> **本批最大发现（新工程结论，已写进模块头 + 两处回归锁）**：中段音频**不能用 AAC**——
> AAC 每帧 1024 样本补齐使中段音频恒长视频一帧，concat 按最长流推进偏移 ⇒ 2.mkv 60 段成片
> 出现 **59 处 0.0417→0.0630s 视频接缝**（容器帧率被探成 48000/1001）。`-shortest` 是错误解法
> （实测反截 3 帧、间隙放大到 0.103s）；正解 = **中段 MOV + PCM 24bit + 终片只复制视频、音频转一次 AAC**。
> **真实验收（PASS）**：60 段 / 3552 帧 / 148.17s，`nb_frames`==严格计数==计划，
> **不规则帧距 0 处**，帧率回到 24000/1001，8 段抽样对齐 **0 或 −1 帧**，逐张读图 9 张
> （clip00/05/10/20/31/35/43/52/59 对照图）画面同景同人同动作，EDL 60 段与成片同计划，
> 编码器 `h264_amf`（本机 AMD 硬件在位、无需回退），首跑 54.7s（0.9s/段）、二次命中缓存 0.2s，
> `hdr_downgraded=True`（高位深源降 SDR 成片，工程仍指原片）。产物 `work/render_accept/`。
> **测试基线**：后端 **388→433**（`test_timeline_render` 29 + `test_render_movie_service` 16）·
> API **89→99**（`test_render_task` 10）· vitest **118→127**（`renderTask` 9）· 双 typecheck 干净 ·
> `test:mock` 契约含渲染段 PASS。生产基线不变（127/139·137·4/9·105），零 `feature_version` 变更。
> **尾巴**：打包 exe 真机复核（结果页渲染按钮/进度/打开目录）需授权；`rendered/` 未进残留清理清单；
> 竞品「相近片段合并」「渲染失败仍出 XML」两条语义未复刻（我方失败即抛话术，是否改为"仍出工程+告警"待拍板）。
> 归档 `FINDINGS_VIDEO_RENDER_PORT.md`；能力表 D/表 E/结论 TOP1 已销项。
> **效果判读（用户问"有进步吗"的结论，权威见 FINDINGS §4.1/§4.2）**：精度层面**零进步且本应如此**
> （未动算法/未 bump fv）；能力层面 0→1（首次可不开 NLE 直接拿到可播放 mp4）；质量层面最实的一条
> = 修掉 59 处 AAC 接缝拉伸的真缺陷（现严格 CFR）。但成片**性质 = 审片带/素材堆**，不是可交付叙事片：
> 60 段 / 148.0s，单段 1.0–9.94s（中位 2.0s），按播放顺序源片起点**倒序对 13%**、相邻回跳 8 次
> （>60s 的 5 次），且未定位段静默跳过 ⇒ 看片者不知道哪里缺。
> **自我更正留痕**：我一度把「源片起点单调性」当验收项，实为**先排序再比较 = 恒真**的口径错误；
> 已换成"按播放顺序数倒序对/回跳"，并写进 FINDINGS §4.1。验收覆盖也有缺口：逐张读图只做了
> **9/60 张**，其余靠帧距 + 8 段 MAD 度量兜底。
> **由此产生的下一步判断**：若目标是"客户双击能看且知道缺在哪"，性价比最高的不是继续偷新面，
> 而是给成片补**缺口标记**（黑场腿或时间码条，竞品有现成形态）+ 可选解说轨开关；
> 若坚持按档案顺序，则是差集 TOP1 剩余半边「退化拒绝门」。两者都等用户拍板，未开工。
> **待拍板剩余**：git 提交（现 241 文件未提交，含续23~30）/ 分发包 r3 重打（含续27+29+30）/> 下批 = 退化拒绝门（差集 TOP1 剩余半边）或入库层四件 / 大文件鲁棒性四件。

> **▶ 2026-09-29(续29) — UI 多选原片接线 = 续27 video.concat 的产品入口闭环【下个对话从这里读起】**
> 用户从四项拍板中选「UI 多选原片接线」（后端 API 续27 已就绪，缺 Electron 入口+展示）。
> **落地**：① Electron 桥 `app:openFiles`（`openFile`+`multiSelections`，返回**选择顺序**数组、取消=空数组）
> → preload/`electron.d.ts` 同步；② ServiceAPI `mergeSources(paths)`（POST /api/source/merge）+
> `startAnalyzeTask(edited, original, originalPaths?)`——Http 适配器口径：**≥2 段**才发
> `original_path:''`+`original_paths`（与 `routes/tasks.py` 同规则），单段 body 与旧版逐字一致；
> Mock 适配器同规则拒 <2 段（dev 态两分支都跑得通）；③ `Project.sourceVideos`（有序=合并时间轴）+
> `Project.merge` 留痕 + `syncEffectiveSource` 生效原片规则（单段→该段；≥2 未合并→''；已合并→产物；
> **库内容或顺序变化即判产物过期**；库清空→''；裸文件名不覆盖）+ 旧 localStorage 项目读时迁移（零丢失）；
> ④ 详情页「源片库」= 列表（序号/删除/一次拖入多段/浏览器模式可多次粘贴追加）+「立即合并/重新合并/
> 取消合并结果」+ `mode/reused` 徽标；分析页多段未合并时按钮改「合并并分析」并列清单，合并进度沿用
> 后端既有 `MERGE_SOURCES→INDEXING` 映射（**UI 阶段枚举零改动**）；项目卡显示「N 段原片（待合并）」/
> 「产物名（合并 N 段）」；元数据多段聚合（时长/大小求和、分辨率取首段），已合并则探产物。
> **验收**：vitest **95→118**（新增 `projectsSourceLib.test.ts` 15 + `sourceMerge.test.ts` 8）·
> 双 typecheck 干净 · 后端 **388**（skipped=2 既有 MPS 类）· API **89** · `test:mock` 契约 PASS（含合并段）·
> `compile:electron` 产物含 openFiles。**浏览器态真点验证**（Mock 后端 + CDP 结构快照）：两段入库→顺序列表
> 4h37m 聚合→立即合并→产物路径+「合并自 2 段 · copy」→取消合并→分析页「合并并分析」+清单；
> 旧版项目（无 sourceVideos）迁移后原片库/时长自愈均正常。
> **边界**：本批零 `mvp/src`/`mvp/api` 改动（纯 UI/桥），生产基线不变；**原生对话框多选 + 真实合并的
> 打包 exe 真机复核未做**（需打包授权）；mkvmerge 路由/字幕轨取舍等口径差异仍见 FINDINGS_SOURCE_MERGE_PORT。
> 文档：`FINDINGS_SOURCE_MERGE_PORT.md` §4/§5 已更新为「UI 已接线」。
> **待拍板剩余**：git 提交（现 232 文件未提交，含续23~29）/ 分发包 r3 重打（续27+29 全部入包，打包需授权）/
> 下批偷向（成片渲染=差集 TOP1 唯一未消化 / 入库层四件 / 大文件鲁棒性）。

> **▶ 2026-09-29(续28) — E 层（算法层差集）全线闭合 = ordered_search M0 判负【下个对话从这里读起】**
> 用户令「先把e层做了」。E3 commentary_scene 已有 09-28 判决探针前案（`FINDINGS_E3_ECC_PROBE.md`，
> ECC/48×27 结构相关腿与已证伪帧差腿同档、交换比≈1:1，不进 runtime），本批实做 = ordered_search
> （D#173 八句 docstring + options#68 十四键字节确证）第二套复现级工程 M0。
> **沙盒三轮判读**（`sandbox_ordered_search_replay.py`，已存特征矩阵离线重建，推断级）：
> 轮1 margin=歧义门 → 全拒（连续场景 coarse 平坦 top1−top2≈0.005，诊断探针确证）；
> 轮2 margin=簇内取最早 → 81/139 且回退 11 ID 全部同向左偏 2~4s（平带左界伪影）；
> 轮3（终态）选择=argmax+竞品三门原样 → **full=102 · nolock=103 · raw(无顺序全片argmax)=106 vs
> 基线截等长 105，章程门 113 未达**。逐 ID 归因：四片 `full_only_up=[]`——顺序性（锚点/窗/锁）
> 相对独立检索**零独家救回**，独家回退 p03/t3×3（锚点拖走合法复用段, E1/退化门/DP 同族第五次复现）。
> **裁决：不进 runtime、不留通道**（机制形态未在复现中站稳，区别于 conf_v2 基础设施保留）。
> **轮4/5 修复伪影再消融**（用户追问「知道问题为啥不改」）：量化→抛物线细化臂、margin
> 误读→0.03 分数带重排臂（无窗口、复用段自动逃逸）、门→单独开关臂——修完后
> raw=106 > argmax_g=101 > rr=93 > rrnop=88：**连续性重排相对无顺序天花板独家救回 1/回退 19**，
> 判负是修复后结论而非伪影背锅（详见 FINDINGS §轮4/5）。
> **v2 前提更正（同日密度探针暴露）**：本文与 FINDINGS 原版「我方 0.5fps/2s 网格 vs 竞品 1fps」
> 错误——生产 `index_sampling_fps` 出厂默认=1.0（实测 2.mkv 索引 7668 行/1s 间距），轮1~5
> 全部本就是 1s 网格 ⇒ 判负更强（无密度差可修照输）；v1 探针（1fps vs 1fps）作废留证
> `work/fps1_probe_v1_falsepremise/`（副产品=生产复跑逐 ID 零翻转回归）；有效问题=
> **2fps>竞品密度还有没有红利** → `probe_index_density_gain.py` **已出数判负**：生产严格
> 36→36（净零）、截等长 29→28（门 ≥+3 未达）、建索引 ×2 耗时、定位 +54%，沙盒天花板同向
> 微降（raw 27→26）⇒ **索引密度工程不立项、门限复标随之取消必要性**；竞品「网格」维度
> 我方无欠账，且反证 ordered_search 判负数字全部产在与竞品同密的 1s 网格上。
> **E 层闭合**：E1/E3/ordered_search 已关，path_* 全局 DP 按 09-28 裁决不重开。runtime 零改动，
> 基线不变（后端 388·API 89·vitest 95）。归档 `FINDINGS_ORDERED_SEARCH_M0.md`；表 E 销项四条已记
> （capability map）。**待拍板**：git 提交 / 分发包重打（续27 concat 后）/ 下批方向=
> 成片渲染（差集 TOP1 唯一未消化）或入库层+UI 接线。

> **▶ 2026-09-29(续27) — 继续偷·video.concat 多原片合并 = 移植+验收闭环【下个对话从这里读起】**
> 用户令「继续偷」，拍板起手项=多原片合并（竞品差集 TOP8 第 2 位、功能边界缺口）。
> **形态确证（挖穿 D#221/#240）**：竞品=入库前**物理合并成单文件**（签名全等→流复制；否则 HEVC
> 硬件链→libx265 medium/CRF18 兜底；HDR/10bit→p010le/yuv420p10le；稳定命名 md5 缓存复用；
> 1h 超时/取消/5s 心跳/输出校验），**非**多索引并行匹配。我方发行物无 MKVToolNix ⇒ mkvmerge
> 路由缺失记口径差异（等价=concat demuxer copy，实测 1GB 5.7s）。
> **落地**：`media/ffmpeg/source_merge.py` + `locator_service.merge_originals` +
> `SourceMergeConfig`（4 旋钮，**默认开**——多路径为新入口，单原片行为逐字节不变、零基线影响）+
> `<appdata>/merged/` + `ProgressStage.MERGE_SOURCES` + API `original_paths`/`POST /api/source/merge`
> + worker 合并产物回写 original_path（下游 domain/索引/导出零改动）。
> **测试**：后端 **388 全绿**（363+25）· API **89**（81+8）· 前端零改动。skipped=2 为既有 MPS 平台类。
> **真实素材验收（accept_source_merge_2mkv.py）**：2.mkv 关键帧切两半→合并 copy（+3.5s/0.046%
> 漂移，容差内）→reused=True→接缝出图正常→DML 硬断言下合并片定位 69 段——**对照
> fastglobal_default_2mkv 基线 严格 36/39·场景 39/39·负例 FP3/4 逐 ID 零翻转**（含负例）。
> 已知取舍：copy 丢字幕轨（2.mkv 46 条 subrip，匹配不消费，NLE 素材无字幕——素材入库批一并处理）；
> 音频有无混用→转码降纯视频；UI 多选入口**未接线**（下一批）。
> 归档 `competitor_cutmatch/FINDINGS_SOURCE_MERGE_PORT.md`；产物 `work/merge_accept/`。
> **待拍板**：git 提交（续23~27 累计 ~215+ 文件）/ 分发包 r3 重打（打包需授权）/ UI 多选接线。

> **▶ 2026-09-29(续26) — UI 真机导出复核通过 + 抓修 1 个 P1 新建项目断链【下个对话从这里读起】**
> 用户令"ui真机导出复核"。全程计算机操控打包 exe 完成 E2E：
> **① 复核抓到 P1 真缺陷并已修**（续20 A6 落地断链，vitest 只测了 Mock 态没测 Electron 桥）：
> `useCreateProject.createProjectViaPicker` 把对话框选到的**剪辑视频**写进 `sourceVideo` 且不填
> `editedVideos` → 分析页「剪辑视频」下拉恒空、开始分析永禁（旧项目 acc-source 正常故 续21 未暴露）；
> 顺带 `refreshSourceMeta` 只认 sourceVideo → 剪辑主线项目时长/分辨率恒 0。修复：picked 路径进
> `editedVideos:[path]`、sourceVideo 置空、meta 探测目标=sourceVideo‖首个绝对路径剪辑视频；
> 测试更新为回归锁（`projectsMedia.test.ts`）。**vitest 95 全绿 + 双 typecheck 干净**。
> **② 修复后 E2E 全过**（打包 exe + computer-use 操控）：新建项目（对话框选 tset2-ed.mp4）→
> 项目卡/详情页剪辑视频正确登记 → 选源片 test2-om.mp4 → **分析页下拉自动填充 ✓** → 开始分析
> （索引复用 reuse index，~22 分钟全链）→ 结果页 26高/9中/17低 + 双画面预览正常 → **EDL 导出**：
> `boundary split: 2 clips expanded`，seg5(=t2r01b 区域 3162-3167) 在 3164 真实切点展开两段、
> seg9 在 3043 展开，`split=k/2` 标记在位 → **剪映草稿导出**：切分段作独立素材不回并
> （`og3041-3043.mp4`+`og3043-3045.mp4`），located 轨 20 段整镜头对齐。产物
> `work/ui_accept/export_out/tset2-ed.loc.{edl,jy_draft}`。
> **③ 分发包定稿**：win-unpacked 含两件套+P1 修复；**zip 刷新为 `Video-Locator-win-x64-20260929r2.zip`**
> （r1 含缺陷已迁 trash）。测试基线：后端 363 · API 81 · vitest 95。
> **待拍板剩余**：git 提交（~215 文件，未授权）。

> **2026-09-29(续25) — release 分发包重打 + 展示层两件套落地【下个对话从这里读起】**
> 用户拍板"先发包重打，然后做两件套"。全部完成：
> **① 发包重打 = 完成**：electron-builder 重建 win-unpacked（含新 backend.exe=fast_global 默认开 +
> 续19~23 全部修复 + pyJianYingDraft assets 确证在位）；**启动冒烟过**（Electron 多进程 + backend.exe
> 子进程真实拉起）；新 zip `mvp/ui/release/Video-Locator-win-x64-20260929.zip`（1.59GB；旧 9/10 zip
> 已迁 trash）。TODO 里"Windows 包重打"两条销项（cbed284/ff71db6/新默认全部入包）。
> **② 展示层两件套 = 落地并实测**（竞品 boundary_guard._record_boundary_split + segments/builder
> 单帧守卫语义重建）：①`exporters.split_clips_at_boundaries`——跨镜头主 clip 在**内部真实转场切点**
> （scenes.npy）上展开成多段，记录侧按源宽等比分配（匀速假设），EDL `split=k/n` 注释 + FCP7
> `boundary-split piece` 留痕 + 剪映分段不回并（`plan_jianying_assets` 只并严格重叠）+
> `expand_material_spans` 跳过切分段（防轨道重叠）；②单帧守卫（硬）=`<boundary_min_piece_s`(0.5s)
> 碎片并入邻段绝不出闪烁片；既有 clip 维持"只告警不裁剪"（LOC-2001）不变。旋钮
> `export.boundary_split_enabled=True`（默认开）/`boundary_min_piece_s=0.5`。
> **验收**：单测 8 项 + 后端全套 **363 全绿**（355+8）+ API 81 全绿 + **真实数据导出冒烟**：
> test2 默认态批导出 EDL/FCP7，seg5（=t2r01b 区域 3162-3167）在 3164 真实切点展开两段、记录侧
> 时间码首尾相接（`work/export_smoke/`）。零 API/UI 契约变化。
> **待拍板剩余**：git 提交（未授权，~210 文件）；UI 端到端验收（新包两件套效果需真机导出复核）。

> **2026-09-29(续24) — M2 四腿收口 + fast_global 翻默认开 + tier2 清理 2.4GB**
> 用户拍板"继续1,2，然后4"（①腿 c ②翻默认 ④清理；git 仍未授权）。全部完成：
> **① 腿 c 质量权重 = 定向成功/全局证伪，不采纳**（沙盒 F1/F2 同款形态 + 独立 dense_quality 缓存通道 +
> 4 旋钮默认关）：严格 127→117（−10）、口径 105→78（−27），11 项回退 vs **1 项改善=t2r01b（part→HIT）**
> ——质量权重是 M2 四腿**唯一找到的 row4 判别信号**（票外信息），但全局重加权代价远超收益；
> 未来若救 row4 只走"质量门窄形态"另行立项，禁借 t2r01b 反标。**多模态复核（2026-09-29 质询后补做）**：
> t2r01b 双向图证（`work/fastglobal_visual/t2r01b_qw/strip.png`——QW 臂 GT 牛栏窗全含=真修复，ON 臂
> 第三帧已滑进洗车房镜头）+ t1r26 回退抽查（`t1r26_qw/strip.png`——QW 臂丢失正确时刻，
> "重加权推离真锚定"图证坐实）。**M2 四腿终局**：a/b 证伪、c 定向成功全局
> 证伪、d 零翻转无害——票面三维度无判别力，row4 处置=接受 1 项回退（`PROJECT_FAST_GLOBAL_ANCHOR.md` §8）。
> **② fast_global 翻默认开**（`fast_global_enabled=True`，生产形态=M1 形态）：后端 **355 全绿**
> （350+5 腿 c 单测）；**默认态四片验收批零环境注入 = 逐 ID 零翻转复现 ON 基线**（严格 127/139 ·
> 场景 137 · 负例 4/9 · 口径 105/139，该形态三轮一致：M1 首跑/r2/默认态批）；**打包冒烟通过**
> （backend.exe 1053MiB：health 200 + BACKEND_LISTEN 公告 + release 无令牌拒启 exit=1）。
> **生产现役基线自此 = 严格 127/139 · 场景 137 · 负例 4/9（+8 vs 119 时代）**。
> **④ tier2 清理 = 已执行 2.4GB** 迁 `benchmark_trash_20260928/tier2/`（ViT-B 路线缓存/orb/isc/
> transvcl 冻结缓存/datasets originals 2.mkv 副本——移前 sha256 校验与 D:\video\2.mkv 逐字节一致；
> 两个 H2 smoke 脚本改指 D:\video\2.mkv；移动后 355 全绿复验）。另: 竞品安装器 CutMatch_V7.1.0(1).exe
> 双份 6.3GB 经查无引用（提取产物 802MB 已归档 cutmatch-analysis/data + sha256 溯源留痕 + 动态验证用
> D:\cm 安装目录），已答复用户可删。**测试基线：后端 355 · API 81 · vitest 95。**
> **待拍板剩余**：git 提交（未授权，未提交 ~200 文件）；mvp/ui/release 分发包重打（cbed284+ff71db6+
> 本轮新默认，打包脚本就绪）；UI 端到端验收。

> **2026-09-28(续23) — M2 消融腿全部实测完毕：腿a/腿b 证伪、腿d 零翻转无害；M2 剩腿c+打包验收**
> **① 已落地**：腿 a/b/d 三旋钮进 `global_offset_anchor`（`vote_top_k`/`wide_std_max_s`/`min_valid_samples`，
> 默认值=M1 生产形态=行为零变化）+ `config.fast_global_*` 三旋钮 + 单测 7 项（**后端全套 350 全绿**，343+7）
> + `rerun_fast_global.py` 支持 `SVL_FG_TOP_K/SVL_FG_WIDE_STD/SVL_FG_MIN_SAMPLES` 注入与 `SVL_OUT_TAG`
> 独立产物命名（OFF 基线复用 M1 产物）。**默认值未动，生产行为零变化**；git 未提交（未授权）。
> **② 腿 a top-k=3 = 四片完整证伪**（`work/fastglobal_on_tk3_*`）：严格 127→119、口径 105→86、
> **8 项 M1 改善全部回退**（恰为 M1 改善集），t2r01b 未修。机理=rank2/3 干扰票稀释单票窄桶共识
> （与 min2 同型）。k=2 同机理先验不乐观，未跑；要试须拍板。
> **③ 腿 b 宽窗 std≤0.35 = 四片完整证伪**（test3 首轮被中止、续跑补齐 494s；`work/fastglobal_on_wstd_*`）：
> 严格 127→122、口径 105→95，5 项改善回退（p35/t1r08b/t1r14d/t1r26/t3r06b）、零改善、t2r01b 未修
> ——真锚定宽窗票集 std 天然 ~0.3-0.6s，0.35 门拒掉的是真共识。
> **④ 腿 d min_valid_samples=3 = 四片与基线逐 ID 零翻转**（严格 127、口径 105 全同）——
> **无判别力但无害**（3fps 采样下 <1s 短段才触发）；生产取 2/3 实测等价。
> **⑤ 腿 c 质量权重 = M2 唯一剩余项，需扩 edited_cache 像素统计口径 = 登记待拍板**（不擅自改缓存 schema）。
> **⑥ M2 合并定论**：t2r01b 假共识与真共识在票面结构上**同构**（连贯单峰/宽窗支持度 1.0），
> 票面三维度（票数/top-k/宽窗 std）全部无判别力——row4 型邻镜滑移出路只剩腿 c 或接受该 1 项回退
> （M1 聚合门已达标）。完整证据链与裁决表 = `PROJECT_FAST_GLOBAL_ANCHOR.md` §8。
> **⑦ 待拍板**：fast_global 翻默认开（前置=腿 c 决策+打包验收）/ git 提交 / 残留清理 ~1.7GB。

> **2026-09-28(续22) — fast_global_anchor M1 双臂回归 = 通过验收门（口径 82→105=+23），维持默认关；min2 消融腿实测证伪**
> 用户令"立"（第二套复现最小证据形态）+"先检索竞品对应信息"+"没干就开始吧"。完整裁决=
> `PROJECT_FAST_GLOBAL_ANCHOR.md` §7（含 §6 竞品对照四差项→M2 消融腿）。要点：
> **① M1 双臂**（`work/fastglobal_{off,on}_*`，DirectML 硬断言，四片全链路×两轮复跑一致）：
> 严格 119→**127**、场景 137 持平、负例 4/9 持平、**main-span 截等长口径 82→105（+23，达沙盒复现链 100 水平，推断级）**；
> 章程门"净增≥+8 且三指标零回退"**达成**。OFF→ON 10 翻转逐张读图：9 真改善（p35/t1r26/t2r03c/t3r03a/t3r06b 内容确证，
> t1r14d/t1r14b/t2r04a 同场景合理，t1r08b 指标 HIT 但属**争议 GT** 待人工复核标注）+ 1 回退
> **t2r01b（严格 HIT→part，row4 邻镜滑移，图证坐实）**——聚合门达标，逐项回退如实登记。
> **② min2 消融腿证伪（重要负结果，勿重试）**：row4 离线复算=单票众数桶假共识 → 尝试 `min_cluster_votes=2`
> → 四片重跑实测口径 105→**82**、严格 127→**118**、9 项改善全灭且连 vote_prior 已兑现 +2 丢 2 项（替换效应）。
> **机理定论：真匹配在 1s 库网格量化下 proj 天然单票窄桶（宽窗才聚拢），"窄簇票数"不是假共识判别维度**；
> 此前"竞品 min_valid_samples 族确证"归因过强已撤回。参数保留=消融接口，生产 `fast_global_min_cluster_votes=1`。
> row4 型邻镜滑移判别转入 M2 候选（a top-k 投票 / b 宽窗 std≤0.35 变体 / c 质量权重 / d min_valid_samples=3）。
> **③ 测试基线**：后端 **343**（+1 证伪回归测）· API **81** · vitest **95** · typecheck 干净。
> **④ 待拍板（未动）**：**fast_global 翻默认开**（M1 门已过但带 1 项 t2r01b 回退 + 争议 GT，需用户裁决）；
> M2 消融腿；git 提交仍未授权（"git我喊你交你再交"）。工程注：`rerun_fast_global.py` 增 `SVL_ARMS` 过滤；
> 新工具 `mvp/scripts/diff_two_metrics.py`（逐 ID 翻转对比）；Windows Git Bash **PYTHONPATH 分隔符必须 `;`**（用 `:` 会静默假失败）。

> **2026-09-28(续21) — 打包端到端验收 = 通过（现场修掉 3 个打包必炸缺陷）+ vote_prior 按拍板翻默认开**
> 用户授权"先打包验收，然后做 E 组"。完整记录 = `mvp/docs/ACCEPTANCE_PACKAGED_20260928.md`（10 项全过，
> 证据在 `work/ui_accept/`：截图逐张读图 + 包内后端日志 + 导出物文件级校验）。要点：
> **① 现场修复 3 真缺陷**：(a) `run_backend.py`/`backend.spec` 走 `mvp.api` 命名空间 → 本次构建 cwd 下
> PYZ **零桥层模块**、backend.exe 启动即崩（过去"打包验证过"隐含 cwd 运气）→ 改 bundle 正规顶层 `api`
> 形态；(b) 预览直链 `<video src>` 不带会话令牌 → 发行态预览全黑（MEDIA_ERR 4）→ `previewResult`/
> `getEditedVideoUrl` 拼 `svl_session`；(c) `.env.production` 的 `VITE_API_BASE` 经 resolveService 构造参数
> 压过运行时 `svl_port` → 直连 URL 指回 8765 → **运行时端口优先**（三处均有 vitest 回归）。
> **② 发行三防线实测**：release 缺令牌拒启（exit=1）/ 随机端口 BACKEND_LISTEN 解析 + query `svl_port` /
> 无令牌 401（LOC-1201 话术）带令牌 200。元数据回填、新建项目取消不创建、四格式导出（剪映草稿含
> cbed284 防回归 / FCP7 XML in=660 / EDL / JSON）、错误条幅不崩——全部打包态实测。
> **③ vote_prior 翻默认开**（`config.py` vote_prior_enabled=True；验收通过=既定前置；dense_recheck/conf_v2
> 因实测零增益/1-231 **维持默认关**）。新包复跑日志确证生效：seed 19.6s applied → 合成夹具窗口
> 22–24 → **19–24 完整覆盖 GT**。
> **④ 测试基线**：后端 **324** · API **81** · vitest **95** · 双 typecheck 干净。
> **⑤ 遗留观察（已入 TODO）**：网络级失败条幅为英文技术串（待中文话术）；后端被杀侧栏"已连接"不重探；
> LOC-2001 UI 路径未自然触发（契约有测试锁定）；剪映草稿**应用内双击**确认属用户动作；edited_cache 目录
> fsync Windows 静默跳过（续19 表述已更正）。**⑥ 下一步 = 用户已拍板做 E 组**（顺序建议：
> resolve_consecutive_scene_offsets → 展示层切点展开 → commentary_scene 复核 → speed_fill；
> ordered_search/全局 path DP 需第二套复现级工程，单独立项）。git 提交仍未授权（未提交实测 >180 文件）。
> **⑦ E1 resolve_consecutive 移植+双臂实测 = 无收益 + 1 真回归 ⇒ 维持默认关、通道关闭（同会话续跑）**：
> 模块/旋钮/挂接/10 单测落地（后端全套 **334** 全绿）；test2/test3 双臂 GPU（DirectML 硬断言）=
> **test2 严格 14/20→13/20（−1）、test3 持平、零改善**；图证 t2r01b（`work/consec_flip_visual/`）：
> 被平移段 OFF 与 GT 同内容（牛栏+水塔），ON 平移后=洗车隧道红车 ⇒ 该"重复起点"是编辑窗重叠
> **合法复用**，非竞品 scene 级伪影。根因与退化门(续19)同型，升级为对标纪律：**"去重/唯一认领"类
> 竞品判据移植前必须先证伪影在我方架构系统性存在**——四项已实测三项不成立（退化门 −14/本项 −1/
> DP 下沉 −8）。详见 `FINDINGS_CONSECUTIVE_OFFSETS_AB.md`。
> **E2 预研改判**：非"一行可加"——我方 scene 展开与"找内部转场"同用一张 1fps CLS 源场景表=空操作，
> 真做前置=源片侧更细边界检测探针（未立项）。E3（commentary_scene ED 复核）为下一执行项、E4（speed_fill）
> 需先定导出层形态。
> **⑧ E3 判决探针 = 负结果结案（同会话续跑）**：竞品未测信号腿 ECC 仿射运动校验（48×27, cv2
> MOTION_AFFINE）+ 结构相关腿在 36 真/5 假已裁锚点上 AUC 0.900/0.911，**与已证伪帧差腿（0.917）同档**
> ——我方假切点非仿射可解释运动（字幕/前景/光照），ECC 假设不匹配；组合工作点(拦4/杀1)系小锚集扫描
> 假象，最难假例 test3@27.79(raw=0.053) 落区域外、扩门即误杀 7 真切点回到 ≈1:1，与续8b 结论三方闭合
> ⇒ **commentary_scene 复核不进 runtime、通道关闭**（零 `mvp/src` 改动）。架构解释：竞品复核层修的是
> 自家 TN 的毛病，我方 6 假切点是 CLS 切分副产品（竞品不产此类错）→ 该错误族随信号源更换才消失
> （TN 替换=−16 已关）或业务容忍（6/227≈0.9%，定位层有兜底）。详见 `FINDINGS_E3_ECC_PROBE.md`。
> **E 组本轮到此为止**：E1/E3 结案（均默认关/不进）；E2'（源片侧边界探针）与 E4（speed_fill 导出形态）
> 均卡在需用户拍板的前置上；ordered_search/全局 DP=第二套复现级工程单独立项。

> **▶ 2026-09-28(续20) — 续19 遗留三项全部落地：/api/media/info + 假数据清除 / 导出 warnings + task.error 话术 / 随机端口端到端（并更正续19 一条假前提）**
> **① P0 前端假数据 + metadata 端点**：新增 `GET /api/media/info`（`mvp/api/routes/media.py`，复用冻结
> `media/ffmpeg/ffprobe.py`，不写第二套探测；400 `invalid_path`/404 `file_not_found`(只回文件名)/500 走
> `public_error` 带 LOC 码）。前端 `ServiceAPI.getMediaInfo` + Http/Mock 适配器 + `projects` store
> `updateProject/refreshSourceMeta` + 新 `useCreateProject` composable：**「新建项目」改为先弹原生对话框
> 选真实视频，取消=不创建**；项目名=文件名去扩展名，时长/fps/分辨率/大小由端点实测回填（打开旧项目且
> duration=0 时自动补探一次）。`HomePage.vue`/`ProjectsPage.vue` 的 `movie.mkv`、`Interstellar (2014).mkv`
> 死值清除；`mockData.ts` 的假片名属 Mock 适配器明示假数据，**保留**。
> **② P1 导出 warnings + 错误话术**：`ServiceAPI.exportResults` 返回 widened 为 `{path, warnings?}`；
> `ResultsPage` 导出后 warnings 非空 ⇒ 对话框保持打开展示 LOC-2001 碎片告警（确认后「知道了」关闭），
> 关闭后页面仍有条幅。异步任务错误：`tasks/worker.py` 的 `task.error` 从 `"ExcName: 技术串"` 改为
> **对外话术（LOC 码）**（`public_error`），技术细节只进日志——分析页错误条幅直接可读；同步路径
> （非 2xx `{code,message}`）续19 已由 `HttpServiceAdapter.request` 优先展示，本轮补测试锁定。
> **③ P1 随机端口接线 = 端到端做完，但先更正一条假前提**：续19 交接写「后端已支持 SVL_API_PORT=0 并打印
> BACKEND_LISTEN 公告」——**不实**：全仓 grep 该词只存在于 `main.py` docstring；`announce_lines` 只打
> channel/session 两行；打包 exe 真入口 `run_backend.py` 读的是 `SVL_BACKEND_PORT` 且无任何公告。本轮落地：
> 新 `mvp/api/launcher.py`（给 `uvicorn.Server.startup` 挂钩子，**绑定成功后**才打 `BACKEND_LISTEN <host> <port>`，
> 绑定失败进程退出、公告宁缺毋假；通配 host 归一 127.0.0.1；`make_server` 可测）；`python -m mvp.api.main`
> 与 `run_backend.py` 两入口共用。Electron：`process.ts` stdout 改**行缓冲**（公告不被 chunk 切断）；
> `manager.ts` 解析公告 + `config.port===0` 时以公告门控 `waitForHealth`（进程先退=fast fail）、健康检查走
> `configWithListen` 真实地址；`main.ts` 打包态注入 `SVL_BACKEND_PORT=0`，健康就绪后回填 `backendConfig`
> host/port/healthUrl（bridge/WS 活读取），并把 **`svl_port` 放进页面 query**（`readBackendBootstrap` 本就支持）。
> 真机冒烟（源码态 uvicorn 子进程）：随机端口公告 → `/api/health` 200 → `/api/media/info` 实测值
> （1.mp4: 126.79s/29fps/544×960）→ 相对路径 400。开发态仍固定 8765 不公告 = 行为不变。
> **④ 测试基线（本轮后）**：后端 **324** · API **81**（66 + media_info 6 + export warnings 1 + launcher 8）·
> vitest **93**（73 + renderer 12 + electron 8）· `typecheck` + `typecheck:desktop` 均干净。
> **⑤ 未做/边界**：以上 UI 效果未经打包 exe 端到端验收（仍等打包授权，与 vote_prior/dense_recheck 翻默认开同批）；
> macOS 打包侧 `build_backend_mac.py` 若走 `run_backend.py` 同源入口则自动获得公告能力（未实测）；
> **git 提交未授权，未提交文件实测 178 个**（含本轮 21 处源码/测试/新文件）。

> **▶ 2026-09-28(续19) — 档案语料读完 + T1 五条落地（退化拒绝门实测否决 / 脱敏+对外码 / 本机 API 门禁 / 宣传口径）**
> **① 阅读覆盖（用户质询"所有相关文件都看完了是吧"后的补做）**：`competitor_cutmatch/` 28 份、
> `semantic_signal/` 40 份、`cutmatch-analysis/FINDINGS/02~12` + 模块图 + 1563 键选项目录、
> `mvp/docs/` 11 份 + 根档案 13 份 + GT/实验档案 30 份，全部读完；差距结论已交付。
> **关键口径提醒（新会话必读）**：竞品**成品端到端从未实测**（被授权阻塞，立场=不绕授权），
> 所有"竞品侧"数字都是**我方沙盒按其字节确证参数的复现（推断级）**，不得写成竞品成绩。
> **② 退化拒绝门（原任务 #8）= 已实现 + 已实测 + 裁决默认关**：`engine/localization/degradation_gate.py`
> （重复率 = 本段主 span 被更强结论已认领区间的覆盖比，按置信降序 keep-best；子 span `cover<0.2` 丢弃；
> 导出碎片告警 `LOC-2001`），旋钮 `degradation_gate_enabled=False` / `max_duplicate_scene_ratio=0.8` /
> `min_scene_coverage=0.2`。**离线重放双臂（同批同 GT 同判据）：严格 117→103（−14）、场景 137→125（−12）、
> 负例 4/9 不变（零收益）、支撑 591→390**；消融 = 仅重复率门 −8 / 仅覆盖门槛 −7 / 阈值放宽到 0.95 仍 −8
> （⇒ 非灵敏度问题）。逐图复核 2 张（`work/gate_flips_visual/2mkv_s03_flip.png`、`test2_s46_flip.png`）：
> **被拒帧与 GT 窗逐帧同内容** ⇒ 门砍的是正确答案；根因 = 竞品该判据长在 scene→scene 一对一匹配架构上，
> 我方按镜头细切分天然多查询同源。详见 `FINDINGS_DEGRADATION_GATE_AB.md`。
> **③ 顺带修掉一条真断链**：`load_config` 的 pipeline 覆盖是手写白名单，漏了 `vote_prior_*`/`subshot_*`/
> `patch_v2_*`/`dense_recheck_*`/`edited_cache_enabled` 等 ⇒ JSON 里写了会被**静默忽略**。已改为以 dataclass
> 字段为唯一清单泛化覆盖（`_build_dataclass`/`_cast`）+ 未知键告警留痕 + 修 `bool("false")==True` 的坑。
> **④ T1-2 日志脱敏 + 稳定对外错误码**：`infrastructure/logging.py` 加 `redact_text`/`RedactingFilter`
> （绝对路径只留文件名、URL 只打码 query、`?session/token/api_key=` 打码、traceback 同样脱敏，
> `SVL_LOG_REDACTION=off` 可关）；`errors.py` 每类加 `code`+`user_message`（LOC-1000/1101~1109/9999）
> + `public_error()`，API 两个异常处理器与 `export_failed`/`load_failed` 全部带码返回，
> 前端 `HttpServiceAdapter.request` 优先展示「话术（码）」。
> **⑤ T1-3 本机 API 门禁**：新增 `mvp/api/session.py` —— `hmac.compare_digest` 校验
> `X-Locator-Session` 头或 `?svl_session=`，`/api/health` 等放行；**`SVL_BUILD_CHANNEL=release` 且缺
> `SVL_SESSION_TOKEN` ⇒ `create_app()` 直接 `ConfigError` 拒启**（= 竞品 release_profile 的"配置缺失即拒启"
> 思路，正对我方 2026-09-22 静默跑 Mock 事故同根）。Electron 打包态生成一次性令牌注入 env 并经页面
> query 交给渲染进程（`readBackendBootstrap`）。**⚠️ 未做**：随机端口接线（后端 `SVL_API_PORT=0` 已支持，
> Electron 侧未解析 `BACKEND_LISTEN` 公告），端口仍固定 8765。
> **⑥ T1-4/T1-5 部分**：`PRODUCT_INTRO` 宣传口径改实测（索引 9.4 分钟；复定位改按片段数 4~7 秒/段；
> 命中率改 117/139 · 137/139 · 负例 5/9 正确拒绝）；`edited_cache._atomic_save` 补 fsync 文件 + 目录。
> **⑦ 测试基线（本轮后）**：后端 **324** / API **66** / 前端 vitest **73** / typecheck 干净。
> **⑧ 未完**：#15 剩前端假数据（`HomePage.vue:28,33`、`ProjectsPage.vue:16` 写死片名 + 项目时长恒 0，
> 需 metadata 端点）；导出 `warnings` 字段 UI 未消费；git 提交仍未授权。
> **▶ 2026-09-28(续18) — 补漏：`D:\dsh-work`（竞品授权逆向）与 `D:\cm`（竞品真实安装目录）此前完全未扫【已归档架构部分 + 修正档案自相矛盾】**
> 用户指出「竞品有两个文件路径还有个是 d:/dsh-work，那个你看了没」——**没看**。续17 的 103 模块穷举
> 只覆盖 `cutmatch-analysis`，导致表 D 里 `licensing.*` 8 行仅写"缺失（商业化）"一句话。
> **① 已归档（用户拍板=只归档架构部分）**：授权体系设计全貌落 `FINDINGS_CAPABILITY_MAP_20260928.md` **表 F**
> （卡密双代际 / 六步签名校验含 nonce 防重放 / 14 返回码 / TPM+Secure Enclave+KSP 设备绑定与"禁止静默降级" /
> 状态文件 candidate→fsync 文件→**fsync 目录**→原子 replace / 本机服务门禁四路校验 + 常量时间比较 + 处理令牌 TTL 180s /
> `ReleaseProfile` 五开关 / AES-GCM 模型 + 租约按需解密）。**攻击路径排序、漏洞清单 V-02~V-07、内存扫描证据一律不纳入本方档案。**
> **② 由此得出 4 条我方可执行结论**：`release_profile`"配置缺失即拒启"应**现在**就借鉴（我方 09-22 正是
> CI 缺 `.env.production` → 整包静默跑 Mock 恒显"已连接"）；我方 `api/` 监听本机端口**无任何鉴权**（同机进程可
> 任意调我们的接口并读用户视频路径）；`errors.py` 8 类无稳定对外码 → 与 `diagnostics.public_messages` 缺口合并处理；
> `edited_cache.py:120` 只 `os.replace` 未 fsync 目录，掉电可留空文件。
> **③ 修正档案自相矛盾（用户拍板）**：`dsh-work` 两份报告抬头均写「纯静态分析（未运行任何程序）」，
> 但主报告 §3.5–3.7 记录的是**动态验证**（注入 `AUTOCLIP_*` 启动 `cutmatch-desktop.exe` → 直读 sidecar PEB
> 环境变量块 → 扫 687 个内存区 / 627.5MB），`hijack_observer.py`/`hijack_requests.log` 为其产物
> （日志仅见观察端自测 `GET /_selftest`，未收到客户端授权请求）。**已在两份报告顶部写「口径校正」注：以正文为准，
> 确实执行过目标程序，抬头表述作废**；`阶段一 §6` 三条破解待办（定位门禁机器码 / 检查状态文件能否伪造 /
> 端到端绕过）逐条**标废不推进**，与 STATE:321 既有「不绕授权」口径重新对齐。
> **④ 数据错值**：`阶段一 §1` manifest「208 文件」→ 实数 `D:\cm\cutmatch-sidecar.manifest.json` `files len=202`
> （与 `cutmatch-analysis FINDINGS/03` 一致）。
> **⑤ 路径清单更正**：竞品相关路径实为**三个**（`cutmatch-analysis` 逆向产物 / `dsh-work` 授权逆向 / `D:\cm` 真实安装目录），
> 我上一轮说"两个"是少算。

> **▶ 2026-09-28(续17) — 竞品 103 叶子模块逐文件穷举对齐 ✅ + 性能基准实测 ✅（一条对外承诺被证伪）**
> 穷举基线 = `cutmatch_module_map.txt` 137 dotted 模块（34 包级 `__init__` + 103 叶子），
> 逐模块对齐表见 `competitor_cutmatch/FINDINGS_CAPABILITY_MAP_20260928.md` 表 D/E（证据 blob# + 我方 文件:行）。
> 复核推翻 5 条子代理断言（我方实有 `shell.openPath`/`CREATE_NO_WINDOW`/`scale=` 参数/`_lock`；可比对模块数 101 非 137）。
> **最终差集 TOP8**：成片渲染与导出前守卫（单帧片段守卫 + 退化硬停）＞ **多原片合并 `video.concat`**
> （34 键最大非算法族；我方只能单原片索引 = 功能边界缺口）＞ 大文件鲁棒性（CFR 代理 / memmap store /
> 停滞看门狗 / **独立 GPU 工作进程监督**）＞ 售后可诊断性（11 客服错误编号 / 三级日志 / **路径脱敏**——
> 我方日志现明文含本机路径）＞ 批量并发治理 ＞ **快/精双模式 `matching.router`** ＞ 商业化前置
> （`release_profile`"配置缺失即拒启"闸门思路值得现在借鉴，与 09-22 Mock 静默降级同类）＞ 素材入库工具面。
> **性能基准（H2 DirectML 实测，已填 `MVP_ROADMAP §7`）**：建索引 10/60/128min = **44.6 / 260.3 / 562.7s**
> （13.5~13.8fps，索引 1.08/6.34/13.21MB，RSS 745/758/1812MB）；128min 真实配对定位 首跑 769.1s、
> 缓存复跑 483.3s；全流程 **22.2 分钟**。
> ✅「2 小时影片索引 7~12 分钟」**成立**（9.4min）；⚠️**「同一成片重复定位约 2~4 分钟」不成立**
> ——原数字源自 test1 41 段（167s），69 段实测 483.3s = 8.1min ⇒ 耗时随编辑段数线性变化，
> `PRODUCT_INTRO:52` 需补段数前提（待拍板措辞）。
> 脚本 `mvp/scripts/bench_perf_tiers.py`（含后端硬断言，防隔离数据目录静默 fallback CPU 重演）；数据 `work/bench_perf_tiers.json`。

> **▶ 2026-09-28(续16) — 产品断链 Track A 已修 5 项 + 孤儿置信链已删除；性能基准 Track B 实测中【进行中】**
> 计划文件 `C:\Users\Bsaizne\.qoder-cn\plans\clever-haven-finch.md`（用户批准：先修我方断链 + 补性能实测）。
> **A1 资产完整性**：`asset.json` 增 `sha256`/`size_bytes`（导出脚本自动写 + 生产资产已就地回填，
> 原文件备份 `asset.json.bak-pre-a1`）+ `DirectMLBackend.verify_asset()` 加载前校验（**摘要不符 = DeviceError，
> 不静默加载**；无摘要历史资产 = `legacy_unverified` 放行留痕）+ 三处 `torch.load` 加 `weights_only=True`。
> **A2 `preprocess_sha` 从空壳变真判据**：此前 `IndexMeta.extractor` 用 `default_factory` 从不填值 →
> INDEX_SPEC §4 承诺形同虚设。现 `create_index` 写入摘要 = hash(feature_version+fps+dim+normalize 标记
> + **真实 `_imagenet_preprocess` 行为指纹**)；`validate_index` 不符判 INVALID。
> **关键设计**：测行为不测声明（resize/均值/插值任一改动都会变摘要），且不碰 frozen 模型文件；
> 历史索引（空值）走**一次性回填放行**，实测四片索引全部保持 VALID、零重建。
> **A3 结果恢复**：新增 `POST /api/results/load`（后端 `load_results` 早就有，缺的是 HTTP 端点），
> 前端 `loadResults` 从"抛错"改为接通；恢复后 `/api/export` 可直接用。
> **A4 导出选项去写死**：`ResultsPage` 曾硬编码 `MEDIUM/exclude/snap=true`，现暴露置信门槛/低置信处理
> （exclude｜备用轨）/边界吸附三项（后端与适配器本就支持），**默认值与旧行为逐字一致**。
> **A5 Mock 横幅**：`serviceIsMock()` + App 顶部常驻黄条（09-22 macOS 整包曾静默跑在 Mock 上恒显"已连接"）。
> **C1 删孤儿置信链**：删 `assess()` + `pipeline.py`(`localize_segment`/`RefinedSegment`) +
> 3 个仅该链消费的旋钮 + `SeqAlignConfig.vectorized`（全仓无消费点）。
> 顺带发现 `scripts/smoke_locator_service.py` **在本次删除前就已坏**（patch `app.locator_service.produce_candidates`
> /`.localize_segment`，而 locator_service 早已不导入二者）→ 已删；`diag_user_signals.py` 依赖 assess() 随链删（产物 JSON 留档）。
> **保留待拍板**：`engine/candidates.produce_candidates` 同属孤儿链，但删它会连带删掉 ranking 层唯一测试覆盖 → 未删。
> **测试**：后端 **294 全绿**（+17 新用例：conf_v2 13 已在前条 + 资产 4 + 预处理 4，−6 孤儿链专属）· API **61 全绿**
> · 前端 typecheck 干净 + vitest **69 全绿**。
> **进行中**：Track B 三档性能基准 `mvp/scripts/bench_perf_tiers.py`（10/60/128min 建索引 + 128min 真实配对
> 首次/复跑定位 + 峰值 RSS + 索引体积，ctypes 实现不引 psutil）。
> ⚠️ 第一版脚本踩坑并已修：隔离 `SVL_DATA_DIR` 会**连带**隔离 ONNX 资产查找 → 静默 fallback CPU
> （那样测的数字不能用来验证 GPU 承诺）；现显式指 `SVL_DML_MODEL` 并**硬断言**后端必须是 DirectMLBackend。

> **▶ 2026-09-28(续15) — 全项目 × 竞品「漏接」交叉扫完成：竞品侧 7 项确证能力零执行 + 我方 2 处档案错判【清单见 TODO P0 顶部续15】**
> 用户质疑「是不是漏了功能没接入」→ 双路穷举扫（竞品 findings 全文 / 我方 runtime 逐旋钮接线），判据 = 有无产物+脚本+实测数字。
> **结论：成立。** 漏项集中在**展示/导出层与结果验证门**（竞品文档自评"零指标风险、用户直接感知、一行可加"却未落地的一档）：
> ① 展示层两件套（转场切点时间线展开 + 单帧片段导出守卫）② `speed_fill_*` ±10% 变速补齐 ③ `max_duplicate_scene_ratio=0.8` 退化拒绝门
> ④ `path_*` 路径 DP（须按全局层形态做，局部下沉已证伪）⑤ `resolve_consecutive_scene_offsets` ⑥ `commentary_scene_*` ED 分镜复核
> ⑦ `boundary_guard` 串镜/硬切回退。
> **自查同时纠正两处档案错判**：续13「0 死旋钮」不成立（`SeqAlignConfig.vectorized` 全仓无消费点；
> `nreps_dispersed`/`max_similar`/`scene_div_montage` 只被无生产调用者的孤儿路径 `assess()`←`localize_segment` 消费）；
> conf_v2 影响面初稿低估（`exporters.py:93-121` 按 level 过滤 ⇒ 降档会改变**导出工程内容**，不只是徽章）。
> 已登记 `FINDINGS_CONF_V2_PORT.md` §5b/§5c + TODO 续15。**待用户拍板**：漏项从哪项起手 / 孤儿路径删除还是注明。

> **▶ 2026-09-28(续14) — 置信公式移植（conf_v2）已完成实测 = 产品价值 1/231 段，建议维持默认关（不移植）；三指标逐位零回退【已结案】**
> **形态**（用户拍板）= 并行通道只降不升 + consistency 用现有簇内信号；护栏豁免已入档 DECISIONS 2026-09-28（窄范围：仅允许采用竞品**字节确证常量**，保留「不用 GT 字段/score 非概率/禁裸余弦」）。
> **代码**：`engine/confidence/confidence_v2.py`（纯函数）+ `ConfidenceConfig.conf_v2_*` 11 旋钮（**默认关**）+ `ConfidenceEngine._apply_conf_v2` + UI `reasons.ts` 6 条文案 + 单测 13 项 → **全套 292 全绿**。
> **四片双臂实测（GPU DirectML/amd）**：定位逐位一致 ✅；三指标 **119/139 · 137 · 4/9 · 支撑 591/1140 与基线批逐条 139 项判定全等（差异 NONE）**；v2<0.6 共 16 段，其中 **15 段本就已被硬 flag 判 LOW（重叠 93.8%）**，唯一非冗余迁移 = test3 r16（span 跨镜混入无关内容，v2=0.586 判不稳，**读图证实方向正确**）。
> **多模态读图 8 张的关键反转**：5 条 HIGH∧MISS 中 `test1_r13` 是 **GT 窗侧假病灶**（画面其实同人同姿势匹配）；真病灶 `test1_r21`（错 21s）/`2mkv_r26`（错 18s）形态 = **同场景内选错时刻**，v2 全未接住（0.752/0.866）。
> **根因**：竞品四项里 `margin`（clean 簇 secondary=None → 恒 1.0）/`coarse`（我方 evidence_qcov 多数 ≥0.85）/`consistency`（竞品源自全片 3fps 偏移投票，我方无对应物）三项**恒饱和**，只剩 local 有变化而权重仅 0.4 ⇒ 该公式的判别力寄生在竞品自己的检索景观上，与「全局层语义是管线级属性不可拆解」（续10j）同源，只是发生在置信层。
> **定论**：`conf_v2_enabled` **维持默认关，不作为产品行为启用**；模块+旋钮+单测保留为基础设施（同 `dense_start_check` 先例）。**不得**调门限凑降档（= 用 GT 反标定，越豁免边界）。重开前置 = 先有非饱和第二信号源（vote_prior 的 support_ratio/dispersion_s 常态化）。
> 产物：`competitor_cutmatch/FINDINGS_CONF_V2_PORT.md`（含 GT 版本头）+ `work/confv2_{case}.results.json` + `confv2_diag_*` + `confv2_analysis.json` + `work/confv2_visual/*.jpg`(33 张) + `mvp/scripts/{rerun,analyze,visual}_conf_v2*.py`。
> **顺手修**：编辑侧缓存键剔除 `confidence`（`locator_service._edited_fingerprint`）——置信不参与编辑侧特征，此前任何置信调参都会触发 A4 缓存全量重算（首次实测多花 ~100s/片）。

> **▶ 2026-09-28(续13) — 全项目结构化审计完成 = 0 死旋钮/279 测试绿/GT 无漂移/无未跟踪 open item; 残留清理与 git 提交待拍板【交接快照】**
> 产物 `PROJECT_AUDIT_20260928.md`(根目录): 三遍扫描(存储层/代码层/逐文件入册 35,789 全覆盖, 清单=work/project_file_census_20260928.json)/残留判定(work 可释放 ~1.6GB🔴+1.7GB🟡)/旋钮活性 156/156/挂起项对账无遗漏。
> **待拍板**: 残留清理 / **git 提交(97 文件未提交, 含本轮全部源码+测试+文档)** / 置信公式豁免 / UI 验收打包授权。
> **下个对话读序**: TODO P0 顶部(挖穿清单⑧项+审计拍板项) → FINDINGS_COMPETITOR_FULL_SWEEP.md §5 → PROJECT_AUDIT_20260928.md。

> **▶ 2026-09-28(续12) — 竞品数据段全量扫穿完成 = 挖穿宣告成立; N1/N4「未绑定」结论推翻(值全在 profile fast_options); 剩余静态无法推进【下个对话从这里读起】**
> **本轮两件事**: ① 用户拍板「立项吧」的偏移投票先验已完成移植+回归(见下条续11); ② 用户拍板「完整挖和扫一遍竞品, 完全挖穿」→ 已执行。
> **扫穿方式**: 282 blob 全量摘要(work/full_sweep_blobs.txt)派子代理精读 + option_catalog 1563 键对账 + profile_v1 镜像核对;
> 主对话抽查复核关键翻转声明(ordered_search_*/path_*/confidence_* 逐键在 fast_options 中验值, 属实)。
> **挖穿宣告**: 139 个中文 docstring blob = 竞品全部自有代码, 语义 100% 可读已扫; 其余 144 blob = 第三方库/空块/字频表/Tauri 资源无竞品语义;
> option_catalog 自有 644 键 100% 镜像进 profile_v1(fast 94 + precise 61)。**数据段无剩余可挖, 静态挖穿关闭。**
> **重大翻转(抽查证实)**: N1 `ordered_search_*`(backtrack 15s/chunk 315s/expand 900s/max 1800s/锁 3 段/双门 0.55·0.62/窗 300s)、
> N4 `path_*`(四权重+三罚, 与续10e 字节确证一致)、`commentary_scene_*` 20 键、**置信公式完整权重 coarse 0.3/consistency 0.2/local 0.4/margin 0.1 门限 0.6**——
> 此前判「值未绑定/N1 等机器码」, 实际全绑定在 profile fast_options ⇒ **机器码专项(N1-N8 剩余 59 项)的静态理由大幅缩水**(唯 candidate_count 等占位符仍缺)。
> **其他新发现**: speed_fill ±10% 变速补齐(90/110)/patch 公式直证(top-16 token 均值)/401AutoClip 产品代号/授权体系全貌(AC-AC2+TPM+Ed25519+租约 ECDH)/
> .cmlog 加密日志格式/SceneRuntime 滑窗 [100,27,48,3]·步 50/FAISS IndexFlatIP/显存自适应批次阶梯/max_duplicate_scene_ratio=0.8 退化拒绝门。
> **唯二静态遗留**: ① 常量是否运行期默认值(需动态验证) ② patch_top_k=100/global_weight=0.45 仍为强推断。
> **下个对话第一优先**: FINDINGS_COMPETITOR_FULL_SWEEP.md §5 可行动项清单(置信公式需护栏豁免拍板/speed_fill/ordered_search 真值参数探针);
> ②=展示层(待办①)仍为产品层最优项。产物: `FINDINGS_COMPETITOR_FULL_SWEEP.md` + `work/full_sweep_blobs.txt`。

> **▶ 2026-09-27(续11) — 偏移投票起点先验 立项+移植+生产回归完成 = 生产 117 -> 119/139(+2 零回退), 默认关待 UI 验收【下个对话从这里读起】**
> **落地**: DECISIONS 2026-09-27 立项入档 + `engine/localization/offset_vote_prior.py`(纯函数, 门=support>=0.2+max_shift<=4s)
> + PipelineConfig 五旋钮(默认关) + `locator_service._apply_offset_vote_prior`(挂接在 P0 密集复核之前) + 单测 7 项(全套 279 全绿)。
> **四片双臂生产回归**(GPU DirectML): 基线 117/139·137·4/9 -> **投票先验臂 119/139·137·4/9**(test1 +2: t1r07a/t1r10b
> part->HIT 经 main span 转正, 与沙盒种子修复例一致; 其余三片逐位不变); **投票+密集复核臂 119 同臂1**(种子落位后 P0 零增量)。
> **诚实边界**: 三指标只兑现 +2(三指标判据宽松+子 span 兜底, 沙盒截等长 +23 大部分已被生产 part/子 span 认领);
> 真实价值 = main span 单发精度 + 新增全局共识信号通道; 耗时增量可忽略(复用索引特征零解码)。
> **待办**: UI/导出验收(需打包授权)通过后翻 `vote_prior_enabled` 默认开; 剩余可挖清单见 FINDINGS_FAST_GLOBAL_REPRO。
> 产物: `work/voteprior{,_dense}_{case}.results.json` + `work/voteprior{,_dense,_baseline}_metrics.json` + `mvp/scripts/rerun_vote_prior.py`。

> **▶ 2026-09-27(续10m) — 快速模式全局层完整复现(第三阶段「第二套复现」) = 偏移投票锚定 +11, 复现链 100/139 新高; 同口径下我方 main span 77 落后 +23【下个对话从这里读起】**
> **做了什么**: `run_fast_repro.py`(F1 ED 3fps 采样+质量权重 / F2 逐样本 0.05s 分桶偏移投票 OffsetCandidate / F3 四项加权两遍路径 DP+恢复候选 / F4 投票共识起点作 start_override 种子) + `run_localization.py` 加 start_override 参数(默认 None=交付口径不变)。
> **三臂归因(test1)**: p0f 13 → **DP 选路 only 5(−8, 路径 DP/恢复候选有害——全局层「选择」语义推断级不可下沉第三次证实)** → DP+种子 16 → **种子叠加贪心 23(+10 全 MISS→HIT 零退化)** ⇒ **全局层价值全在「锚定」不在「选择」**。
> **四片(胜出形态)**: test1 23(+10) · 2mkv 30(−1) · test2 14(0) · test3 33(+2) = **100/139**(p0f 89; 复现历史最高)。
> **同口径对照(main span 截查询等长严格)**: 我方生产 **77/139** vs 复现链 **100/139** ⇒ **全链闭环后唯一大差距项 = main span 单发起起点精度(落后 +23), 根因 = 我方无「跨查询全局共识先验」**(我方起点精修全是局部信号, P0 移植零增益; 竞品链靠 3fps 偏移投票)。负例同级(7~8/9)/候选层双方饱和 = 非差距项。
> **待拍板(移植立项)**: 把 F2 偏移投票作为起点先验移植进 mvp(对 winner 区域逐样本投票→共识起点作种子; 与 P0 的本质区别=全局信号 vs 局部重找; 须三指标回归+UI 验收; 风险=2mkv 型多实例种子偏置)。零 `mvp/src` 改动。
> 产物: `competitor_cutmatch/FINDINGS_FAST_GLOBAL_REPRO.md` + 外部仓 `run_fast_repro.py`/`localization_fasts_*` 全系 + `work/fasts_probe_*.json` + `work/ours_mainspan_truncated_caliber.json`。

> **▶ 2026-09-27 — D 段复核 2mkv 五桶图全量补裁（24/24 张逐图读图裁决）= 既有定论全部维持, 0 例新错误机制【其余片按需】**
> **裁决结果**（明细 `REVIEW_NOTES_PROXY_D_STAGE.md` §2mkv + `work/proxy_loc_review/verdicts_2mkv.csv`）:
> A 桶 12 张分两向——**proxy 真赢 2 例**(p23/p30, baseline main span 错实例而 proxy 逐帧对); proxy 错 5 例(p21 错场景/p25 相似夜景/p28 重复实例选错/p08 兄弟温室/p01 切点前镜头)**全部落入已知失败族**;
> 拒识 2 例(p10/p13 蒙太奇型)+装配效应 1 例(p20)+判据 artifact 2 例(p02/p07 内容正确判 part)。
> C 桶: n01 误配与历史同区同机制(图证确认)+n02 误报(狙枪女)。D 桶: proxy main anchor 正确而 baseline main span 错实例(p05/p39)。
> E 桶 4 独有例无虚高。**新增图证: baseline 2mkv 的 HIT 有 ≥7 例靠子 span 兜底(main span 错实例)** = main-span-only 基线仅 23/39 的图证。
> 无新增 GT 复核线索(2mkv GT 与画面全部相符)。「2mkv A 桶图未裁」销项; 剩余未裁仅 test2/test3 按需。
> **待拍板项不变**: ① 竞品对标主线收官归档 ② UI/导出验收(打包授权) ③ 争议 GT t1r08b/t1r12a 裁决(注: 续10b 已双撤回, 仅剩 V5 审计记录冲突待一并说明) ④ 档案瘦身。

> **▶ 交接快照（2026-09-26 晚，续10c→续10l 全链收官）——下个对话从这里读起**
> **本会话主线**：五环组合探针（沙盒, 续10c/d）→ 用户拍板「自己挖」→ Nuitka docstring 突破（续10e, 全部精修/展示层语义+~50 键值字节确证）
> → P0 密集起点复核落地+调优（续10f/g）→ 四片验证 91/139 净+8（续10h）→ 全局层挖掘+分散度 graft 否定（续10i/j）
> → 投票结构三连败定案（续10k）→ **护栏豁免 + mvp 生产移植 + 双臂实测定案 = 生产零增益零回退, 默认关维持（续10l）**。
> **最终定调**：①「锚不准」是 TN span 复现管线特有, 生产起点本就 moment 级精度——**我方生产在起点精度一环已达竞品密集复核后水平**;
> ② 投票/分散度/路径 DP 属管线级属性不可拆解下沉（三连败+graft 否定双证据）; ③ 端到端差距（若有）不在起点精度层。
> **代码状态**：mvp/src 净新增 3 文件（dense_start_check.py / test_dense_start_check.py / rerun_dense_recheck.py）+2 处挂接
> （config 五旋钮默认关 / locator_service 钩子）——**默认关=生产行为零变化**, 272 单测全绿; 外部仓 run_localization.py 多旗标(终版=--dense-start --dense-gain 0.04 --dense-margin 4.0)。
> **待拍板（下个对话第一优先）**：① 竞品对标主线是否收官归档（对标→差距→挖掘→移植全链已完成闭环）;
> ② 剩余小项: UI/导出验收（需打包授权）/2mkv A 桶 17 张图未裁/争议 GT t1r08b t1r12a 裁决/档案瘦身;
> ③ 可选后续: 快速管线完整复现（第二套复现, 工程大）/机器码专项委托——两者均为「若还要追」的选项, 非必需。
> **关键产物索引**：FINDINGS_COMBO_FIVE_RING_TEST1.md / FINDINGS_DOCSTRING_BREAKTHROUGH.md / FINDINGS_P0_DENSE_START_TEST1.md(§1-10 全链)
> / verify_refine_bindings.py(49 键核对) / work/denserecheck{,_off}_{case}.results.json(双臂) / 外部仓 localization_*_test1.json 全系。


> **▶ 2026-09-26(续10l) — mvp 移植完成 + 生产实测定案 = P0 生产零增益零回退(生产起点本就 moment 级), 默认关维持; 竞品对标主线收官【下个对话从这里读起】**
> **移植落地(按 §9 清单)**: DECISIONS 豁免入档 + `engine/localization/dense_start_check.py`(纯函数三门) + PipelineConfig 五旋钮(默认关) + `locator_service._apply_dense_start_recheck`(locate() 内 _locate_features 后) + 单测 8/8 + 全套 **272 全绿**。
> **生产四片双臂实测**: OFF 117/139·137·4/9 vs ON **117/139·137·4/9 完全一致**; 纯效应 95/231 段起点微移(中位 <1.1s)零翻转; OFF 与 perfopt 基线逐位一致(配置时代漂移≈0)。唯一级联 = test2 seg35 montage 主簇改变(子 span 0.9s 微移所致), GT 不变。
> **定案**: ① 生产不需要 P0——生产起点本就是 moment 精度,「锚不准」是 TN span 复现管线特有, 收益不随移植转移; ② 默认关维持正确, 模块留作基础设施(未来定位劣化可开); 开启代价 +45%~130% 耗时; ③ **生产在起点精度一环已达竞品密集复核后水平**——端到端差距(若有)不在此层。
> **未竟**: UI/剪映/PR 导出验收(默认关零风险, 打包需授权)。**待拍板**: 竞品对标主线是否收官归档 / 剩余待办(2mkv A 桶 17 张图/争议 GT t1r08b t1r12a/档案瘦身)。
> 产物: engine/localization/dense_start_check.py + tests/test_dense_start_check.py + scripts/rerun_dense_recheck.py + work/denserecheck{,_off}_{case}.results.json + FINDINGS_P0_DENSE_START_TEST1.md §10。


> **▶ 2026-09-26(续10k) — 投票/分散度结构移植三连败定案 = 结构属检索阶段不可下沉精修; P0 核心回滚终版; mvp 移植检查清单就绪【下个对话从这里读起】**
> **三连败实测**: v0 graft(3帧 argmax std) 10/43 · v1 硬投票(0.1s 桶) 11/43(票散 2/5) · v2 软投票(带内质心+中位数) 10/43 —— 均劣于终版 13/43(+3/−0)。根因: ±4s 精修窗内相似度景观平坦, 逐帧位置估计先天歧义; 竞品投票结构依赖全片域"真区域=全域尖峰", **属于检索阶段候选生成, 不可下沉为精修采纳门**。P0 核心已回滚终版形态并留注释。
> **收进 mvp 的回答**: 实测有用的是终版(+6 零退化: test1 13/2mkv 31/test2 14/test3 31), 不是投票结构。**移植前检查清单已就绪**(FINDINGS §9): ⚠️ 最关键一条 = 2026-09-01 保留护栏「禁 per-query argmax/voting/cut-aware/temporal align」与 P0 判据的冲突须用户明示豁免; 口径映射(224→518/5关键帧→2fps/边界)/PipelineConfig 旋钮(先默认关)/缓存键/失败隔离/单测/四片回归/UI 导出验收逐项列出; 残余风险(p01 型不可判/2.5s+ 真移动被拦)已写明。
> **待拍板**: ① 护栏豁免裁决 ② 按 §9 清单执行移植(四片回归验收) ③ 全局层彻底解法(完整复现或机器码)维持待办。
> 产物: FINDINGS_P0_DENSE_START_TEST1.md §8-§9 + sandbox/out/localization_{p0v,p0w}_test1.json(三连败留档)。


> **▶ 2026-09-26(续10j) — 全局层挖掘完成 + 分散度 graft 否定 = 竞品双管线调用序/主线锁定/偏移投票/置信公式全部恢复; 「全局层语义是管线级属性, 不可拆解为局部判据」; P0 终版(+6 零退化)维持【下个对话从这里读起】**
> **挖掘成果**: 精确模式五阶段(召回→路径DP→候选复查→边界调整→输出)与快速模式七阶段(粗定位→精排+顺序搜索+两遍DP→10fps起点对齐→边界复查)全部恢复;
> ordered_search 主线控制器(锁定/解锁/reliable_streak, 排序=local×0.7+consistency×0.3, dispersion≤0.35, 去重0.25s);
> coarse_retrieval 3fps 逐样本 0.05s 分桶加权偏移投票(OffsetCandidate{coarse,support,dispersion}); 置信公式四项加权+四类低置信原因(常量 0.1/2/3)。
> **分散度 graft 实验=否定**: test1 10/43(0 翻转, 好移动全被拦)·2mkv 30/39(p41 真改善 disp 0.616 误杀/p01 假移动 0.319 达标)——窗口局部重算不分真假, 竞品语义需全片投票上下文; 已降级为诊断字段, 终版 p0f(+6 零退化)维持不变。
> **结论**: 全局层只有两条路——①沙盒完整重建快速候选生成(=第二套复现, 工程大需拍板) ②等机器码。单层/门控挖潜到此全部收敛。
> **待拍板**: ① mvp 移植决策(P0 终版零退化形态) ② 是否立项"快速管线完整复现"第三阶段 ③ 机器码专项是否委托。
> 产物: FINDINGS_DOCSTRING_BREAKTHROUGH.md §9 + localization_p0d_{test1,2mkv}.json(分散度诊断留档) + work/combo_probe_p0d_*.json。


> **▶ 2026-09-26(续10i) — P0 采纳门对齐竞品防漂移机制定案 = 终版(margin4+gain0.04+max_shift2.0+距离平局裁决) 四片 89/139(净+6 零退化); 无门版 91(+8 含1退化); 单层重建收敛【下个对话从这里读起】**
> **竞品核查**: 无字面边界拒绝门; 有 ①max_shift(键在值未绑定) ②严格更优才替换 ③距离平局裁决(距粗起点近者优先) ④回退留痕。
> **门控两轮**: 支持度门误杀 test1 平局 → 降级为诊断; max_shift 门 2mkv 转正(p01 2.92s 假移动被拦/p16 伪峰消失/p41 强证据过)。
> **终版四片**: test1 13(+3) · 2mkv 31(+1) · test2 14(0) · test3 31(+2) = **89/139 零退化**, 仍超 main-span-only 85。
> **单层极限(本轮最重要发现)**: max_shift 同时拦 p01(假)与 t2r02b-q0019(真)——两者局部证据同构(gain大/支持强/跨场景), 场景范围门同样无效 ⇒ 区分信息在竞品全局层(ordered_search/路径DP/语义守卫), 单层不再调参。
> **待拍板**: ① **移植决策**: P0 终版(零退化形态)进 mvp 生产管线, 三指标回归+UI 验收(口径差异不可外推) ② 无门版(+8)若采纳须接受 p01 型退化 ③ 残余空间需全局层。
> 产物: FINDINGS_P0_DENSE_START_TEST1.md §7 + localization{_p0g,_p0f}_{case}.json(门控诊断逐行留档) + work/combo_probe_{p0g,p0f}_*.json。

> **▶ 2026-09-26(续10h) — P1 四片验证 + P2 定案 = P0+P1a 四片净 +8 (83→91/139), 首次越过我方 main-span-only 基线 85; 2mkv 唯一负贡献(-1, 边界未收敛+窄窗骑线); P2a 尾部守卫结构性无对象可修【已迭代定案, 见上条续10i】**
> **四片数字(截等长严格, P1v=P0@gain0.04+P1a)**: test1 10→15(+5) · 2mkv 30→29(−1) · test2 14→15(+1, t2r02b 蒙太奇救回) · test3 29→32(+3) · **合计 83→91/139**; 负例四片全不变; 候选层不变。
> **margin 4s 对照**: test1 再+1(t1r30a) 但 2mkv 逐位不变 → 窗宽非 2mkv 问题根因(多帧证据本身偏好错位); **0.04 门槛过拟合警告部分兑现**(2mkv 两个 ~0.048 边际移动有害) → 改进方向 = 边界最优拒绝 + 结构门, 非继续调门槛。
> **P2a 尾部守卫 = 诚实负结果**: 35 尾窗 0 可信硬切——复现 span 终点已是 TN 场景边界, 结构上无尾部跨镜可修(竞品 DTW 终点会过冲才需要); 剩余 P2: 长场景 probe(候选层饱和低优先)/展示层(产品层)。
> **待拍板**: ① 边界最优拒绝门(治 2mkv) ② **移植决策: P0/P1a 语义进 mvp 生产管线需立项+三指标回归(口径不同增益不可直接外推)** ③ P1b/P2a 已定案不采纳。
> 产物: FINDINGS_P0_DENSE_START_TEST1.md §6 + 外部仓 localization{_p1v,_p0m4,_p2a,_p1vp2a}_{case}.json + work/combo_probe_* ; test2/test3 源库缓存首次建成(后续零成本)。

> **▶ 2026-09-26(续10g) — P0 调优 + P1b 实测定案 = P0@gain0.04 截等长 14/43(净+4 零退化, 采纳为当前最优); P1b 推断级 DP 轻微有害(-1)不采纳; 累计 10→14/43【已并入四片验证, 见上条续10h】**
> **P0 调优**: `--dense-gain 0.04` 恰好分离真改善(0.050/0.064/0.199/0.074)与暗场误移(0.026) → **+4/−0**; t1r26 读图证实真实。⚠️ 单例调优有过拟合风险, 四片回归须复核。
> **P1b 判读(诚实负结果)**: 推断级 DP(倒退罚 5.0 normal + Σcombined)仅改 3/35 winner、净 −1(t1r12b)——test1 ED 单调性高(tau 0.987)无题可解 + DP 覆盖了 coverage-rerank 保护。**不采纳**: 真实形式要么是 fast 侧四项加权(0.55/0.2/0.2/0.05)要么需 ordered_search/边界守卫配合; 不在推断级形式上继续调参(纪律)。
> **候选层始终饱和(42/43 top1)**; 剩余差距全部在位置层其余精修(局部 3fps 多帧精排/TopK DTW 复查/边界守卫)。
> **下一步(待拍板)**: ① P1a 四片验证(2mkv 有缓存可跑; test2/test3 需提源库 ~15min/片) ② P0 四片回归(复核 0.04 门槛过拟合) ③ P2(边界守卫/长场景 probe/展示层) ④ 我方管线移植评估(把 P0 语义移植进 mvp 需立项+三指标回归)。
> 产物: `competitor_cutmatch/FINDINGS_P0_DENSE_START_TEST1.md` §4-§5 + 外部仓 `localization{_p0t04,_p1b,_p0p1b}_test1.json` + `work/combo_probe_{p0t04,p1b,p0p1b}.json`。

> **▶ 2026-09-26(续10f) — 核对通过后 P0/P1a 落地实测 = P0 密集 10fps 起点复核 截等长严格 10→13/43(+4/−1, 读图证实 3 张), P1a 零 GT 变化; docstring 语义路线验证成功【已定案, 见上条续10g】**
> **前置核对(用户要求, 全过)**: verify_refine_bindings.py = 49/49 新键字节级证实(val_off 值解码+键名在位含 0x61 前缀处理) + 名/值表排序一致性两区 True + 12/12 docstring 原文直接命中 sidecar exe。
> **实现**: run_localization.py +`--dense-start`/`--resolve-dup`(默认路径不变; 常量=确证值 margin 2.0s/10fps/前3关键帧/min_gain 0.01/重复容差 1.0s); 实现标推断级(语义+常量确证, 代码流未逆向)。
> **数字**: P0 在 31/35 行生效(gain 0.012~0.281); 截等长严格 **10→13/43**(+4: t1r00/t1r11/t1r14e/t1r26, 前 2+1 读图证实真改善·t1r14e 原"候选找到但被拒"位; **−1: t1r31 真退化**=暗场相邻相似镜头骗过首段证据 gain 0.026 即移锚→缓解=提门槛~0.05 或加结构门); 候选层 top1 42/43 零变化; P1a 修复 2 行重复起点 GT 零变化(其主战场在 2mkv/test2 留四片轮)。成本 +160s/臂。
> **下一步(待拍板)**: ① P0 调优(门槛/结构门) ② P1b 路径 DP 四项加权(需检索/精修两阶段重构) ③ P1a 四片验证 ④ P2(边界守卫/长场景 probe/展示层)。
> 产物: `competitor_cutmatch/FINDINGS_P0_DENSE_START_TEST1.md` + `mvp/scripts/verify_refine_bindings.py` + `work/verify_refine_bindings.json` +
> `work/combo_probe_p0{,p1}.json` + `work/combo_probe_review/`(+9 张) + 外部仓 `localization{_p0,_p0p1}_test1.json`。

> **▶ 2026-09-26(续10e) — 用户拍板「自己挖,死命挖」= 精修/展示层语义挖掘突破: Nuitka 常量 blob 内嵌中文 docstring, 不需机器码反汇编, 函数级语义+全部阈值直接可读; 「N1-N8 静态不可得」判断正式推翻【已落地, 见上条续10f】**
> **G5 真实语义到手**: select_scene_match_path = 路径 DP「弱惩罚倒退」(罚值 loose 2.0/normal 5.0/strict 10.0, 非我方 +0.02 加分近似);
> resolve_consecutive_scene_offsets = 修「连续命中同一源镜头重复使用起始帧」(正是本轮探针发现的 14.9s 锚距问题);
> 精修路径目标函数 = **0.55×local + 0.20×consistency + 0.20×coarse + 0.05×support** + DP 罚(grace 2.0/max 0.12/backward 0.05) + 邻接候选传播(上段最强候选按解说时间差平移/前后邻居反推)。
> **原片侧起点精修共 6 层**(密集 10fps 多帧首段复核→局部 3fps 精排→TopK DTW 复查可疑→路径 DP→连续偏移修正→开头串镜守卫/尾部硬切回退),
> 全部阈值字节确证(path_*/frame_path_refine_radius/actual_refine_*/boundary_backshift/commentary_scene_* 全族 ~40 键);
> AKAZE 语义修正 = min 作用域是**单应内点**且内点 ×3 权重; 检索层新发现 = 长场景局部 probe 提升; 展示层 = 真实转场切点剪映/PR 时间线展开 + 单帧片段导出守卫。
> **对账**: 五环探针的「锚不准」= 复现只做了 1/6 层精修, 非竞品弱 —— 续10d §3.4 推断被证据具体化证实。
> **可实现清单(待拍板)**: P0 密集 10fps 起点复核(直接对症锚不准) / P1 连续偏移修正+路径 DP 四项加权 / P2 边界守卫+长场景 probe / 展示层独立通道。
> 产物: `competitor_cutmatch/FINDINGS_DOCSTRING_BREAKTHROUGH.md`(全文); 数据源 cutmatch-analysis/data 只读; 未绕授权未解密受保护资产(拍板边界维持)。

> **▶ 2026-09-26(续10d) — 五环组合探针单片先行(test1)执行完毕 = 候选层饱和 42/43 top1 · 位置层(截查询等长)仅 10/43 · G5(推断级)零增量 ⇒ 可复现组合链瓶颈 = 场景内位置精化, 非检索排序层【已对账, 见上条续10e】**
> 两臂: A=four-ring 重跑(与已交付 localization_test1.json **35/35 行全一致**, 环境漂移 0) / B=A+G5(--g5 旗标, 外部仓已授权直改, 默认路径不变)。
> **数字**: 候选层 top1 42/43(top3/top20 同; never=t1r08c 零宽 ED 伪影; 找到但被拒=t1r14e) · 截查询等长严格 **10/43**(不含争议 GT 9/41)
> vs 我方 main-span-only 22/43 · 完整基线 34/43 · 负例 0/1 两臂一致 · G5 名次变化 0 处/严格翻转 0 处(offset 平滑 6 行 ≤1.5s 无 GT 影响)。
> **判读(读图 6 张关键张, 全部同场景 0 内容错位)**: span/查询比中位 10.9×、GT 内容距 span 起点中位 14.9s、DTW 采纳仅 2/31 行 ⇒ 「找得对、锚不准」;
> 竞品端到端优势只能来自可复现层之外(A18 边界精修 9 项/2fps 主档 A19/ordered_search A17)或 TN 展示层边界质量(G7)。
> **对路线的含义(待拍板)**: ① 展示层换 TN 边界(G7)是竞品链最有价值且零指标风险的可借鉴项; ② 位置层若追, 方向=无 GT 的场景内锚点信号, 非 top-k/权重(已饱和); ③ G5 再测前置=机器码逆向(N1-N8, blocked)。
> 产物: `competitor_cutmatch/FINDINGS_COMBO_FIVE_RING_TEST1.md` + `mvp/scripts/probe_combo_dual_caliber.py` / `probe_combo_flip_visual.py` +
> `work/combo_probe_test1.json` + `work/combo_probe_review/`(12 张) + 外部仓 `sandbox/out/localization{_comboA,_comboG5}_test1.json`(各配 akaze_off+manifest)。
> 遗留: 出图脚本中文桶名 cv2.imwrite 乱码(已手工改名待修); 挂起项不变(2mkv A 桶 17 张非阻塞/loose AKAZE/对齐档/N1-N8 等机器码逆向/档案瘦身)。

> **▶ 2026-09-26(续10c) — 用户拍板下一步 = 「竞品全流程组合探针」单片先行【已执行完毕, 见上条续10d】**
> 五环全开(TN 全流程边界+段内单元 / 每场景 5 关键帧+长场景加密 / patch 主力 0.55 / 匹配目标函数路径项 / AKAZE 几何校验),
> **只跑一个测试视频(建议 test1: GT 43 + 复现缓存全在 + 基线 34/43 已知)**。
> 执行基础 = 复用 `cutmatch-analysis/sandbox/run_localization.py`(四组已验证); 增量 = ①G5 路径一致性项(连续场景 offset 平滑
> + continuity_tiebreak_bonus=0.02); ②**判据同粒度化**(TN span 装配效应已证伪严格指标)= 候选层指标(GT 在 top-k 名次)+span 截到查询等长双口径;
> ③对照 = 基线 34/43 + main-span-only 22/43 + 候选层等价指标 + 五桶出图。零 runtime/不碰 GT/推断级表述。
> 依据: `DECISIONS.md` 2026-09-26 + `FINDINGS_CAPABILITY_GAP.md`(差距组合链) + `FINDINGS_PROXY_D_STAGE_REVIEW.md`。
> GT 线索 t1r08b/t1r12a 已撤回(候选表反转: GT 在 top1/top2 —— 复现候选生成层强, 弱在呈现粒度)。
> 其余挂起: 2mkv A 桶 17 张图未裁(非阻塞)/loose AKAZE/对齐档(接口已留)/N1-N8 等机器码逆向/档案瘦身。

> **▶ 2026-09-26(续10 完成) — 外部 6 项接管执行完毕: A2/A3/A4/A5 销项 + A1(D 段复现)四组全量完成 + 多面复核**:
> **数字**: proxy 严格 124/139 · 场景 121 · 负例 4/9(基线 117/137/4; main-span-only 基线 85)。
> **多面复核(用户纪律: 不只靠数据/GT, 五桶出图 93 张已裁 20)**: ①严格「反超」= TN 场景代理 span(时长比中位 8.7×)装配效应,
> A 桶翻转全部 part→HIT 且内容同场景, 0 例"复现找到基线找不到的内容"; 严格/场景对粗 span 方向相反 ⇒ 单指标必误读;
> ②**复现内容性错误 0 例**; **2 条 GT 疑错线索待用户裁决: t1r08b/t1r12a**(双侧独立定位同内容区, GT 窗画面与 ED 不符;
> 复现 test1 仅有的 2 条严格 MISS 恰是这两例); ③AKAZE 无增量无伤害(10/262 差异全为 strict 门); ④复现弱点 = 蒙太奇段拒识漏召回(p10 型);
> ⑤n01 误配与我方历史同区同机制。**定论**: 复现实现与内容质量可信; **不构成"竞品定位更好"的证据, 也不构成反向 —— 端到端谁更准仍为未测**
> (同粒度化对照设计见 FINDINGS §5)。产物: `FINDINGS_PROXY_D_STAGE_REVIEW.md` + `REVIEW_NOTES_PROXY_D_STAGE.md` +
> `review_proxy_loc_visual.py` + `work/proxy_loc_review/`; 复现侧 `cutmatch-analysis/sandbox/run_localization.py`(参数化)+四组产物。
> A2(P0-8 已答 FINDINGS/12)/A3(锚点 244,003 共 8 处+口径升级解码帧数)/A4(提示词 v2 验证+裁决并入)/A5(N1-N8=机器码反汇编专项,不重复投入) 均销项; A6 维持不可行。

> **▶ 2026-09-26(续10) — 外部 6 项接管执行(用户授权直改外部仓 cutmatch-analysis)**:
> **A2 ✅** P0-8 已答(FINDINGS/12: 精确模式专属键, 单位强推断 2 fps, D 段双档对照) → 销项;
> **A3 ✅** 文档订正落地: test3-om 锚点 244,003 共 8 处 + 注 E(锚点口径=解码帧数) + 09 旧表行订正 + feature_image_size 注记, 197,305 残留 0;
> **A4 ✅** D 提示词 v2 七条 P0 验证在位 + 244,003 裁决并入; **A5 登记不投入** N1-N8 = 数据段穷尽, 剩 59 项等 code object 机器码反汇编专项(09 §8.5); **A6 维持不可行**(不绕授权)。
> **A1 ▶ 进行中 = D 段复现我方自跑**: 子代理在沙盒实现 `run_localization.py`(DINOv2 ViT-S/14 @224 官方权重 strict / t050 查询单元 / global+patch+scene 三通道 / AKAZE on-off / 候选表+双时间码+manifest 全字段), test1 先行 → 我验收 → 跑齐四组 → `import --loc` → `measure` 同口径对照(**公平基线 = main-span-only 严格 85/139 · 场景 128/139 · 负例 4/9**)。

> **▶ 2026-09-26(续9) — 可执行项批量推进(用户委托) = 6 项完成, 含 1 个重要口径发现**:
> ① **p26 margin 口径差陈旧待办关闭**(XIV 同日已查明修复, 补指针); ② **GT 版本登记表 7 份剩余文档逐条核销**
> (均 v4/verified-139 执行, 头部标注+§八更新) + **自动受影响清单机制 `gt_impact_scan.py`** 落地(GT 哈希快照 8 文件 +
> 变更→受影响文档自动清单, 变更路径注入式验证通过; 人工重验半边仍由执行者做);
> ③ **基座路线关闭写入 `ARCHITECTURE_DECISION_PHASE20.md` 附录 A**; ④ **backbone harness 固化
> `eval_backbone_swap.py`**(asset/locate/measure/compare 四阶段 + 注册表式扩展, measure/compare 已实测对账: 基线 117 vs ViT-B 116 与档案一致);
> ⑤ **D 段接收侧全链路预演通过**(`dryrun_proxy_loc_channel.py`: 反向构造对方 schema → --loc 导入 → 四片评估, 零崩溃);
> **⚠️ 关键口径发现: 对方 localization.json 只有主 span ⇒ 同口径公平基线 = 严格 85/139 · 场景 128/139 · 负例 4/9**
> (117/139 含子 span 贡献; 支撑 180/224) —— D 段对照不得拿对方数字直接对 117;
> ⑥ 顺手修 `import_competitor_proxy.py` SyntaxWarning; 其 --loc 输出路径硬编码 `work/proxy_<case>.results.json` 已记入 TODO 提醒。
> 剩余未完成: 等外部 6 项(A1 放行条件已裁决) / 等拍板 11 项(⑧⑨ 已执行销 2 项) / 工程 4 项 / 档案瘦身 2 项。

> **▶ 2026-09-26(续8b) — TN 双判据仲裁探针 Stage 1(用户批准) = 否定, 不进 runtime**: 227 条现行边界 × (TN ±0.25/0.5s 窗最大概率 ∧ H-CM1 帧差判据), 44 例已裁决锚点穷举 15 组工作点 → **最优 = 假命中 5/6 ∧ 真误伤 5**(交换比 ≈1:1); 唯一漏网假切点 test3@27.79 与已证真切换 test3@16.29 特征同构(moved/大位移同型) ⇒ **判据空间内假切点与「TN+像素双盲真切换」不可分**, 仲裁删除形态关闭; 「输出层换切点」若立项只做展示层并集/就近优选。同轮完成: 全仓 open item 清点(等外部 6 / 等拍板 13 / 可执行 3 / 工程 4 / 档案 3)。产物: `FINDINGS_TN_ARBITRATION_PROBE.md` + `probe_tn_arbitration.py` + `work/tn_arbitration_probe.json`。

> **▶ 2026-09-26(续8) — test3-om 帧数锚点裁决完成: 真实可解码帧数 = 244,003(锚点 244,004 偏高 1 帧, 计入了被 DISCARD 标记的末帧); 执行方 om 批产物正确、无需重跑, 更新锚点表后 D 段即可放行**
> 触发: 执行方 om 批交付时帧数校验失败 [test3-om, 244003, 244004] 按任务书停止(行为正确)。
> 证据链(判卷侧独立实测): packet 244,004 = nb_frames 元数据(巧合相等); pts 网格 244,004 包占 244,006 槽位、尾部 2 空洞 + 2 包 pts 超出容器时长;
> **全流恰好 1 个 `_D_`(DISCARD) 包 = 最后一个包(pts 10,177.166875) → 解码器按标记丢弃**; 尾部解码实测最后帧 pts=10,177.0835(该包未出帧);
> **我方独立全流解码 `nb_read_frames=244,003`** 与执行方管线一致, 且全解码零报错(是"按标记丢弃"非"解码失败")。
> test2-om 同批复核: 四方一致 121,094, 无分歧。
> **澄清**: 对方 `four_clips_framecount_verify.json` 的 `frames_cv2=244004` 是 cv2 `CAP_PROP_FRAME_COUNT` 元数据估值(铁证: 同文件 test1-om 行报 197,305 即已作废的时长×fps 值), 与本裁决零矛盾。
> **锚点口径升级建议**: 已两次踩坑(时长×fps 偏高 199 / packet 数含 DISCARD 偏高 1) ⇒ **锚点应改为解码帧数 `nb_read_frames`**, packet 数降为交叉校验。
> 影响: 被丢帧是全片最后一帧(≈42 ms, 仅影响最后一个下标) ⇒ **对 D 段切点/定位零影响**。
> 产物: `user_case/competitor_cutmatch/FINDINGS_TEST3OM_FRAMECOUNT_ADJUDICATION.md` + `work/_t3om_pts.txt` / `_t3om_readframes.txt` / `_t2om_readframes.txt` 等; 含 7 处待同步位置清单(对方仓)。
> **同日追加 — `D:\dsh-work` 授权逆向工作区登记**: 该目录为竞品授权体系逆向(非 B/D 段数据), 核心发现 = 发行构建三信任链要素(服务器地址/验签公钥/签名强制)可被 env/file 覆盖 → 我方 N16「绕授权也拿不到模型」论据不再可靠; **处置口径维持「不绕授权」拍板, 不推进其破解待办, 不引申任何衍生动作(用户复核)**。详见 `INTEL_REQUESTS_CUTMATCH.md` N18 补充登记。
> **↳ 2026-09-28 续18 更正**：本条「不推进其破解待办」的口径**当时与工作实际不符**——`dsh-work` 主报告 §3.5–3.7 已做过动态验证（注入 `AUTOCLIP_*` 启动竞品、直读 sidecar PEB 环境块、扫 687 个内存区），而两份报告抬头却写「纯静态（未运行）」。现已在两份文件顶部加口径校正注（以正文为准）、`阶段一 §6` 三条破解待办逐条标废，并确立归档范围 = **只归档授权体系架构（表 F），不归档漏洞与攻击路径**。详见 `DECISIONS.md` 2026-09-28「三路径」条。
> **待办**: 待执行方按裁决更新锚点(7 处)后重放 `verify_proxy_output` → 交付 D 段 `localization*.json` → 我方跑同口径对照。

> **▶ 2026-09-26 交接快照（下个对话请从这里读起）— 本会话完成 4 件事 + 3 条待办**
> ① **代理复现 B 段判卷侧复核**（对方 runbook v4.2）：帧数我方独立 ffprobe 逐片一致（锚点 197,305→**197,106** 裁决）；模型**字节级同一**；
> ed 四片几何对照（test2 纯漏切 13 / test3 偏粗 / test1 我方过切 / 2mkv 混合）；**44/44 盲判全量裁决**（对方 29 个独有切点 **0 假切点**、
> 我方 6 处假切点[test1 3 处]）→ `user_case/competitor_cutmatch/FINDINGS_PROXY_B_STAGE_REVIEW.md`。
> ② **竞品 B 段后处理规则逐帧复现 24/24**（仅凭对方 `probs.npy`）：规则已确证（组中点上取整 + 按切点间距迭代合并 + 跨距中点）；
> FINDINGS/11 的「未知 1/2」**已解**、`sensitivity` 不参与；其 §4「峰值检测更稳」**实测不成立** → `FINDINGS_CUTMATCH_POSTPROCESS_REPLAY.md`。
> ③ **我方记录更正**：`ordered_search_max_seconds` **7200→1800.0**（第 3 例「相邻配对」假象；系统对账 11 条仅此 1 错，其余一致）
> → 全仓已更正 + 新脚本 `mvp/scripts/reconcile_cutmatch_bindings.py` + 复盘口径写入 DECISIONS。
> ④ **D 段前置对照①**：查询单元换成竞品 t050 切点 → 四片 **严格 114→104（−10）· 场景 137→122（−15）· 负例 4→3**；
> 多模态复审定性为「**我方 2 fps 查询采样 × 细切点**」口径不匹配（非对方切点不准）→ `FINDINGS_QUERY_UNIT_SWAP.md`。
> **待办（下个对话）**：① 等执行方 **D 段 `localization.json`** → `import_competitor_proxy.py --loc` → `measure_four_results.py` 同口径对照；
> ② 待用户拍板「**细切点当子 span**（细边界 + 粗查询单元）」立项（前置 = 先定编辑侧查询采样口径）；
> ③ 待对方澄清 P0-8 `source_sample_rate`=2 语义 + profile `image_size` 名不符（1/162）。
> **纪律**：外部产物**独立复核后才进结论**；对照全程标注「代理复现（推断级）」；本会话 `mvp/src` **零改动**。


> **▶ 2026-09-26(续7) — D 段前置对照实验①: 把编辑侧查询单元换成竞品 t050 切点 → 四片**严格 114→104(−10) · 场景 137→122(−15) · 负例 4→3**; 多模态复审定性为「我方 2fps 查询采样 × 细切点」不匹配, 非对方切点不准**
> 做法: `mvp/scripts/proxy_query_unit_run.py`(monkey-patch `_segment_twopass_flash` → 竞品 t050 切点, 71/35/67/87 单元;
> 我方索引 1.0fps/518、检索、事件扩池、patch v2、置信一行不改; GPU DirectML; 零 `mvp/src` 改动)。
> **四片**: 2mkv 34→26(场景 39→34) / test1 34→34(场景 42→40) / test2 14→13(场景 **19→14**) / test3 32→31(场景 37→34);
> 支撑 span 565→593(结果更碎)。翻转: 2mkv 8失1得 · test1 **6失6得(净0)** · test2 5失4得 · test3 5失4得。
> **多模态复审**(`work/qu_flip_visual/` 逐张读图, 锚点=评估器实际采用的 main/sub span):
> ① **2mkv 的 MISS 全部落在 0.5–1.0s 查询单元**(>1s 单元 0 MISS); 单元对 GT 编辑窗覆盖率中位 2mkv **0.67** vs test1 **1.00**;
> p02/p03 的 pqu 单元是 1.5–1.5 / 2.5–3.5 的**单帧级查询** → 直接 not_in_source(对照图该行空白)。
> ② test1/test2/test3 以**判据边界翻转**为主: test1 两侧常落在同场景不同子镜头/相差 ~2s(t1r00 2154–2156 vs 2156–2158; t1r07a pqu 反而更近);
> test2 t2r07c 是同一内容但原片侧重叠 **45% < 50%** 判 MISS; t2r03a 是查询子镜头换了(沙地纹理 → 人群)。
> ⇒ 结论: **细切点不能当查询单元用**(与 A1 直接替换 117→101、盲判「相邻真切换各选其一」同向);
> 要用只能当**段内子 span / 输出展示粒度**(并集+仲裁), 且前置条件是先解决**编辑侧查询采样**(我方 2fps vs 竞品每场景 5 关键帧)。
> 产物: `user_case/competitor_cutmatch/FINDINGS_QUERY_UNIT_SWAP.md` + `mvp/scripts/proxy_query_unit_run.py` / `probe_qu_flip_visual.py` / `diag_query_unit_length.py` +
> `work/proxy_qu_*.results.json` / `work/_four_{base,pqu}.json` / `work/qu_flip_visual/*.png`。


> **▶ 2026-09-26(续6) — B 段(代理复现场景切分)判卷侧复核完成: 帧数我方独立复核逐片一致(锚点 197,305→197,106 裁决采纳); 模型字节级同一; ed 四片几何对照 + 双实现交叉验证 + 44 张盲判包交付; 我方上轮两条异议自证后全部撤回**
> 执行方 v4.2 交付 `sandbox/out/`(scene_split_t{030,040,050,060} + groups + probs.npy + cut_set_diff + manifest + frame_counts + DELIVERY_NOTES + HANDOFF_B_STAGE)。
> **交付物验收(判卷侧只读, 零 `mvp/src` 改动)**:
> ① **帧数**: 我方自用 ffprobe 独立数 6 片(3677/183837/4070/**197106**/2083/4357) 与对方逐片一致 ⇒ **裁决 `test1-om` 以 197,106 为准**
> (锚点 197,305 = duration 8229.28s × 23.976 估算, 偏大 199 帧); ② **模型字节级同一**: 对方 manifest `model_sha256 c4d54a68…8e0c`
> = 我方导出 `work/transnetv2/probe_transnetv2.onnx`(31,250,929 B) SHA256 **逐字符一致**;
> ③ 三处规范偏差全认可, 其中「raw 0..255 而非 /255」**系我方任务书笔误**(`tn_transnetv2.py` 第 11 行原文即 0-255 RGB)。
> **几何对照(`mvp/scripts/geom_proxy_vs_ours.py` → `work/proxy_geom_*` 32 份 + `proxy_geom_summary.json`)**: 切点口径统一为**段 start**
> (我方 `tn` 批是非链式分段, 用 end 会虚增 —— 首跑 `ours_only 63` 即此假象); 对照现行生产切分(±0.5s):
> **test2 仅代理 13 / 仅我方 0(四阈值全稳) = 纯漏切**; **test3 31(仅代理)/4(仅我方) = 偏粗**; **test1 1/7 = 我方过切**; 2mkv 12/4 混合。
> 代理侧阈值稳定性 test2 **100%** / test1 97.1% / 2mkv 80.5% / test3 77.5%。
> **双实现交叉验证(本轮最有价值)**: 同一 ONNX、互不共享后处理代码的两条实现, ±0.5s 内 **test1 32/32 · test2 65/66(98.5%)**,
> 2mkv 67/76 · test3 84/93, 中位距离 0.10–0.17s ⇒ **B 段链路可信, 差异归因切分策略而非复现走样**。
> **盲判全量裁决 44/44**（判卷侧逐张读图 + 帧差旁证 r；先看图后查键, seed 20260926）:
**对方 29 个独有切点 = 真 27 / 未定 2 / 假切点 0**（r 中位数 3.10, 44/44 全部 r>=1）;
**我方 36 真 / 6 假 / 2 未定**（r 中位数 1.66; 我方 **14/44 例 r<1** = 该点不是跨点帧差峰）;
我方 6 处假切点 = 2mkv 113.17 / test1 2.53·44.73·73.93 / test3 49.14·27.79（**test1 3 处**, 机制 = 镜头内运动/字幕换行诱发的 CLS 峰;
test3 27.79 与 2026-09-26 border_review 独立裁决逐点吻合）; test2 **零假切点但漏切 13 处** ⇒ 两类问题分开治。
判定明细 `work/proxy_blind_disputes/verdicts_44.csv`; **不套 GT、不进三指标**。
> **我方上轮两条异议 = 自证后全部撤回**(新脚本 `mvp/scripts/verify_cutmatch_profile_pairing.py`):
> ① `source` 指针「不可独立复现」→ 撤回(profile 约定即**字节偏移**; 162 条 **raw 逐字节 162/162 一致**、数值 162/162、**名表↔值表名次零颠倒**[95/61/6 条]
> ⇒ 顺序映射成立可复现; 上轮按 `#116` **序号**形式找 `8` 是读法问题);
> ② `offset_refine_dtw_min_score` 0.1/0.55 → **撤回, 0.55 成立**(`0x174e18c8` = `66 9a 99 99 99 99 99 e1 3f`); 0.1 属**邻键**
> `offset_refine_dtw_sample_interval_seconds`(`0x174e18d1`, 紧邻 +9 字节), 我上轮引的 `0x174e04c1` 在**另一区域**(其后紧跟该键名); 对方 09 §296 / 10 §247 早已订正。
> **新增对方动作项(不阻塞 D)**: profile `/feature_extraction/image_size` 的 `key_off 0x174bc0cd` 解出 `feature_image_size`(1/162 名不符);
> `197,305` 另有四处未同步(runbook §5.1 表 / PROMPT_FOR_EXECUTOR / run_scene_split.ANCHORS / verify_proxy_output.ANCHOR_ORDER); 09 §82 旧表行待标注。
> **待 D 段**: `--loc` 通道与 `work/proxy_<case>.results.json` schema 已就绪, 产物到即跑同口径三指标对照。
> 产品含义(有界): 若要"输出层换更准切点", **首选 test2**(代理 66 切点四阈值全稳、我方零独有 ⇒ 替换风险最低), test3 次之(须按阈值分组验收), test1 属反向(我方更碎, 不可直接替换)。
> 产物: `FINDINGS_PROXY_B_STAGE_REVIEW.md` + 3 个脚本 + `work/proxy_geom_*`/`proxy_blind_disputes/`/`verify_cutmatch_profile_pairing.json`。

> **同轮追加(2026-09-26 续6b) — 竞品后处理规则被**逐帧复现**(24/24) + 「换切点」探针 + D 段提示词复核**:
> ① 仅凭对方 `probs.npy` 重放其 B 段后处理, **6 片 x 4 阈值 = 24/24 切点逐帧一致**、`groups_t*.json` 24/24 一致;
> FINDINGS/11 的「未知 1(中点取整)=**上取整**」「未知 2(min_gap)=**按切点间距迭代合并后取跨距中点**」**已解**, `sensitivity` **不参与**切点生成;
> 覆盖区间内部 NaN 全为 0(独立验证其 trim/stride 无空洞主张)。脚本 `mvp/scripts/replay_cutmatch_postprocess.py`。
> ② 11 §4「峰值检测更稳」**实测不成立**: 峰值规则切点数 == 交付 0.50 档(71/34/66/87), th=0.3 时 == 0.30 档(77/35/66/97)
> (激活组绝大多数单帧, 组中点本身即局部极大) ⇒ 真正自由度是阈值与 min_gap。
> ③ **换切点探针**(锚点=已裁决 44 例): 我方 6 处假切点在 TN 概率上既非峰也无值(0.0001-0.021) ⇒ 换 TN 口径**天然剔除**;
> 但我方 29 处**已裁决为真**的切点在 TN 概率上也不是峰(中位数 0.0012) —— 它们与对方切点相距 0.6-5.0s、是**另一处真切换**
> ⇒ **换切点 != 替换, 而是并集+仲裁**(与 A1「直接换成 TN 切分 → 117→101」方向一致)。脚本 `mvp/scripts/probe_cut_swap.py`。
> ④ **D 段提示词复核**(执行方 `PROMPT_FOR_EXECUTOR_D.md`): 认可执行, 补 **7 条 P0**(未匹配行/query_id 对应 B 段/时间码双写/候选表落盘/
> `ordered_search_max_seconds=**1800.0**(原记 7200 系相邻配对假象, 已于 v2 复核时更正) 对 4 部原片的截断风险/固定 seed/原片索引口径明写) + 5 条口径混杂因素(224 vs 我方 518 等)。
> **同轮追加(续6c) — D 提示词已升 v2(我方 7 条 P0 + 5 条 P1 全部并入); 且对方纠正我方一处错记录:**
> `ordered_search_max_seconds` 默认值 = **1800.0**(非 7200) —— 我方独立字节复核**确认对方正确**(profile `val_off 0x174bcc1f` = `66 00 00 00 00 00 20 9c 40`;
> 键名自证通过; 同 blob 名表/值表名次均为 17); 我方旧读数取自键名相邻字节 ⇒ **相邻配对假象第 3 例**。
> 已用 `mvp/scripts/reconcile_cutmatch_bindings.py` 对全部历史相邻绑定对账: **11 条中仅此 1 条错**, 其余一致;
> 全仓 7200 → 1800.0 已更正(INTEL §8.2 / FINDINGS_CONSTANTS_ADOPTION / STATE / TODO / CHANGELOG)。
> **风险重估**: 上限 1800s = 30min, **四部原片全部超限**(2mkv 7667 / test1-om 8229 / test3-om 10177 / test2-om 5051, 后者原按 7200 被判安全)。
> 新增待澄清 P0-8: `source_sample_rate`/`commentary_sample_rate` = **2**(`<<PREV>>`)与 `source_global_fps=1.0` 并存的单位与阶段。
> 产物: `FINDINGS_CUTMATCH_POSTPROCESS_REPLAY.md` + `REVIEW_PROMPT_FOR_EXECUTOR_D.md` + 2 个脚本 + `work/replay_postprocess.json` / `cut_swap_probe.json`。

> **▶ 2026-09-26(续5) — 代理复现 runbook v4 复核: 我方 4 条已闭环; 但我方发现 \`source\` 指针粒度不可独立复现 + 一处内部不一致**
> v4 已并入: ① \`probs_fill{head:NaN,tail:NaN}\` + \`covered_frames\`/\`covered_frame_count\`; ② \`groups_t{030,040,050,060}.json\`(合并前连续激活分组);
> ③ \`fps_mode\`/\`fps_rational\`/\`tbn\`/\`pts_max_residual_us\` + **帧数交叉校验锚点**; ④ \`min_scene_frames\` 确认为他们自造字段名, 已改名;
> 并**主动纠正 v3 一处错误**: \`commentary_short_scene_min_frames\` 语义是**与相邻场景合并**(键名 \`*_merge_*\` + 伴随开关 True)而非丢弃 ⇒ 主交付 \`short_scene_policy=none\`(纯几何切分)。
> **我方独立复核**: ✅ **帧数逐片一致** 3677/4070/2083/4357 与 fps 29/30/30/28 与我方解码完全相同 ⇒ **不需先对齐, 可直接开工**;
> ❌ **\`source\` 指针不可独立复现**: 按 \`pipeline.options@0x174e0158#116\` 我解析前 200 元素**无 8**; 深挖前 400 才见 \`8/0.2/0.8\` **三值连排**于索引 215–217
> (0x174e1894/1896/189f), 而键名在索引 75/76/154 ⇒ **值存在但"键↔值"按顺序映射, \`#116\` 是块级编号**, 且该指针被 \`commentary_short_scene_min_frames\`/
> \`min_scene_coverage\`/\`max_duplicate_scene_ratio\` **三键共用**; 另一处 \`fast_timeline.options@0x174bb2ea#68\` 我解析到的 **#68 是中文说明串**,
> \`source_global_fps\` 在 **#73** 且该区无数值 ⇒ 已要求对方给**每键精确指针**(含块内下标) + **可复跑脚本**(source→值+字节 hex) + 索引约定。
> **另一处内部不一致待澄清**: 同块 \`offset_refine_dtw_min_score\` 紧跟字面量 **0.1**(0x174e04a4→0x174e04c1), 而 v4 §6.4 写 **0.55**(差 5.5×, 直接决定 DTW 采纳门)。
> **不阻塞 B(切分)**: 切分侧参数(48×27 / win100 / stride50 / trim25:75 / min_gap8 / 阈值族 / 策略 none)三方自洽, 请照 §7-B 开跑。

> **▶ 2026-09-26(续4) — 代理复现任务书 v2 = 我方三条硬要求已并入; 我方交叉校验 DINOv2 权重 SHA256 逐字符一致**
> 对方 v2 已把 N18-1(阈值族 0.3/0.4/0.5/0.6 **整组回报** + cut_set_diff 稳定/敏感切点分列)、N18-2(\`akaze\` 分支**必做 + on/off ablation**)、
> N18-3(先交 B 切分, D 可降级但 AKAZE 不许砍) 写成硬要求; 交付物含 scene_split_t030/040/050/060 + cut_set_diff.md + localization.json(method 字段) + manifest。
> **我方独立交叉校验**: 本仓 \`work/dinov2_weights/dinov2_vits14_pretrain.pth\` 的 SHA256 = \`B938BF1B…60CD9\`，
> **与 runbook §5.2 期望值逐字符一致** ⇒ "特征栈可 1:1 复现"的权重前提成立(再次印证 a02 = 官方权重)。
> **我方接收侧已就绪**: \`mvp/scripts/import_competitor_proxy.py\`(localization→我方 results schema; scene_split→±0.5s 几何对照 + CSV);
> 定级纪律: **「代理复现(推断级)」≠ 竞品实测**, 对比只写"口径差异"。
> **我方仍需对方澄清 3 点**(已回): ① §7-E 不能用我方 GT 算切分 P/R(GT 是定位标注, 非镜头切点真值 —— 这正是"指标奖励 GT 对齐"的老坑),
> 切分对照应由我方做几何对照 + 逐条出图裁决; ② §3 schema 的 \`min_scene_frames\` 与 §6.4 \`commentary_short_scene_min_frames\` 是否同一参数(需 source 指针);
> ③ 请连**逐帧概率 \`probs.npy\`** 一起交(阈值与取点规则可由我方重放, 免二次开跑); ④ 素材路径待补(我方已给四片实际路径, 含 test2 的 \`tset2-ed.mp4\`)。

> **▶ 2026-09-26(续3) — 对方常量表破解(FINDINGS/10) + 代理复现任务书到位:我方两处旧记录作废, 通道改「代理复现(推断级)」**
> 对方交付: `FINDINGS/10_NUITKA_CONSTANT_BLOB_BREAKTHROUGH.md» + 机器可读 `data/competitor_profile_v1.json»(943 行, 每条带
> value/level/source=code object@offset#index) + `data/cutmatch_option_catalog.json»(1563 键) + `RUNBOOK_CUTMATCH_PROXY_REPRO.md»。
> **运行期路线被明确排除**: 每次启动需激活码+设备指纹, 授权响应 Ed25519 验签, a01/a02 为 AES-256-GCM 密文、content_key 走服务器
> model lease(P-256 ECDH+HKDF) ⇒ 无合法激活码不可能跑出结果, 且绕授权也解不开模型(对方明令禁止, 我方认同)。
> **两处更正(直接影响我方记录)**: `source_global_fps» **0.1→1.0**; `commentary_short_scene_min_frames» **180→8**。
> **我方独立复核**: 前者我读到产品自述串 `原子保存 1fps 原片全局索引及其身份 metadata。»(0x174b043d) 互证;
> 后者 180 处紧随依赖元组(`T[1]['scene_proxy_height']»)更像**约束**而非默认值, 同区确有 `i 8» 但"8"我未独立定值。
> ⇒ 作废: 我方"stride=10 模拟竞品 0.1fps"的表述(他们与我们**同为 1fps**)、"180=6s@30fps"及"匹配粒度"推论。
> **新通道 = 代理复现**(公开权重 + 确证参数, 在我方沙盒复现其切分/定位口径): 定级**「代理复现(推断级)」, 非竞品实测**,
> 对比只能写"口径差异"。我方已备 `mvp/scripts/import_competitor_proxy.py»(localization→我方评估口径; scene_split→±0.5s 几何对照
> JSON+CSV, 谁是真切换仍人工/多模态裁决); 四片素材路径已核对存在并回给对方(含 test2 实际文件名 `tset2-ed.mp4»)。
> 待对方 `sandbox/out/» 产物落地 → 导入 + 几何对照 + 同口径定位评估 + 画面复核。

> **▶ 2026-09-26(续2) — 采纳评估建议 B 执行完毕:patch×global 加权融合(竞品 0.45/0.55) = 不救失败族, 仅放大"已对"案例 margin**
> 依据: 09 §4/§9.4 —— 两权重**代码级互证**(出现在 `retrieval.py` 的 `match_commentary_scenes` co_consts); 假设 H-F1(融合形式)未确证。
> 协议: 池 = CLS top-100 ∪ 均匀 100 ∪ 真值窗 ∪ 自动干扰; 扫 w∈{0,.25,.45,.55,.75,1} × {raw, minmax}; 403 s(DML patch ONNX)。
> **结果**: ①**失败族零改善** —— p08 兄弟机位与 t2r05a 蒙太奇在**全部**变体下 argmax 都不在真值窗、margin 恒负(p08 −0.027; t2r05a −0.47~−0.52);
> ②**只在 CLS 已对的案例上放大 margin** —— p01 minmax +0.034→**+0.104(w=0.55, ≈3×)**、t3r12 +0.086→+0.089、p26 +0.012→+0.014, rank 全保持 1 零回退;
> ③**patch 不能独立打分** —— w=1.0 时 p01 掉到 rank 2 且 margin 转负(−0.057) ⇒ 竞品 patch 权重 0.55(不主导)与我方"patch 仅门控"现状一致;
> ④可用之处 = **置信/门控**(非定位; Confidence 公式当前冻结, 未实施)。
> **多模态复审**: VLM(方舟 `ep-20260901010244-pv8ws`) 返回 **403 AccountOverdueError 账户欠费**(python/node 双向复现)
> ⇒ 改由逐张读图: `work/fullpool_visual/p08_fullpool.png` 显示真值与 top 干扰帧(sim 0.76-0.82)**是同一间屋子的同一场戏**
> (不同机位/时刻) ⇒ 负 margin 是真实内容混叠非度量假象; `work/loc_audit_visual/test2_t2r05a.png` 显示查询(工业机械子镜头)≠真值窗(人群)
> ⇒ rank 124 是**子镜头/查询单元**问题, 非权重问题。
> 产物: `mvp/scripts/probe_patch_fusion_rank.py` · `work/patch_fusion_probe.json` ·
> `user_case/competitor_cutmatch/FINDINGS_PATCH_FUSION_PROBE.md`。零 `mvp/src` 改动。

> **▶ 2026-09-26(续) — 采纳评估建议 A 执行完毕:竞品边界精修判据 替换 我方 CLS 精修 = 不采纳(97.4% 一致, 6 分歧点视觉裁决 2:2:2)**
> 自审后按计划执行(A 臂)。竞品 7 参数已字节确证(`near_cut_frames=16 / absolute_diff_min=45 / mad_multiplier=4 /
> max_move_frames=16 / min_segment_frames=32 / min_side_frames=10 / max_additions_per_segment=1` + proxy 96×54),
> 但**规则形状是假设 H-CM1**(窗内帧差峰 + MAD 门 + 位移上限), 故本实验定位为"判据对照", 结论以画面为准。
> ⚠️ **口径纠正(同日, 用户指出"竞品切分就是更准" → 我亲自读图复核, 观察成立)**: 我复核了 `work/border_review/` 三张盲判图 ——
> 2mkv「仅我方独有」多为例内假切点(#7 t=87.93 / #8 t=113.17 连续镜头被切开; #2/#5 系黑底字卡过渡), 「仅 TN 独有」**8/8 全是真切换**;
> test3「仅我方独有」#1(t=27.79)/#2(t=49.14) 为假切点 ⇒ **几何切分上 TN/竞品优于我方(精确率+召回都更高), 我方过切明显**。
> 本实验只测**位置**、未测**边界是否该存在**(过切/漏切发生在存在性上) ⇒ §"不采纳"仅指"不要用帧差峰挪位置", **不等于**切分质量无需改善。
> 竞品端到端"画面更准"我方**从未测过**(未运行其产品: 需卡密+模型走服务器 lease), 标记为未测, 不反驳。
> **立场(定版, 不再随质疑漂移)**: ①**接受**"切分几何我方劣于 TN"(精确率+召回, 依据=我复核的 `border_review` 图 + 档案盲判);
> ②**不撤回**"端到端定位我方更好"(四片同 GT 同管线, TN 替换 101 vs 117, 七判据 −16~−17 稳健)与"更准切分直接替换反而更差"——这两条是实测;
> ③**未测不表态**: 竞品**成品**端到端是否更准(从未运行其产品: 卡密+服务器 lease)。
> ④**因此路线不是"全面改切分追竞品"**, 而是两条已被证据支持的**分离**动作: (a) 输出/展示层(用户可见)用更准切点——独立通道, 不碰定位指标;
> (b) 定位层做"**细边界 + 粗查询单元**"混合探针(TN/更准切点作段内子 span, 不拆查询单元, = 档案 §4 路线 2), 须过四片回归。
> **能改变②的证据**: 跑通竞品成品同素材端到端, 或"细边界+粗单元"混合方案使定位**净增**。仅凭"切分更准"不能改变②。
>
> **结果(四片 227 条现行边界)**: 位移 ≤4 帧者 **97.4%**（2mkv 68 条/4 移、test1 40/3、test2 53/27（全 1 帧）、test3 66/34（p50=1 帧））
> ⇒ 两种判据指向同一位置, **换判据不会改变任何下游结果**（定位指标为秒级口径）。
> **6 个分歧点(≥5 帧)视觉裁决 = 我方 2 / CM 2 / 平手 2**: 2 例是**相邻两个真切换各选其一**（test3 16.29/40.07）,
> 2 例是 **H-CM1 被运动骗走**（2mkv 26.83 帧差 52.9 但画面无切换; test3 117.71）,
> **2 例是我方边界落在"无像素切换"处**（test3 27.79 帧差 5.5、test3 57.21 帧差 13.5）→ 我方 CLS 距离峰在
> 快速运动/渐变/字幕变化处会给出非真切换峰（2/227 ≈ 0.9%, 此前从未验证过）。
> **副产品判据**: 两种判据各有盲区 ⇒ 若要改, 唯一合理形式是**双判据仲裁**（而非换判据）, 且须先证明影响三指标。
> **多模态复审诚实说明**: 本地 VLM(方舟 ep-20260901010244-pv8ws) 调用返回 **403 AccountOverdueError（账户欠费）**,
> python/node 双向复现 ⇒ 本轮"多模态复审"由**逐张读图**完成（6 张对照图落盘 `work/boundary_disputes/` 供复核）。
> 产物: `mvp/scripts/probe_boundary_refiner.py` · `visualize_boundary_disputes.py` · `work/boundary_refiner_probe.json` ·
> `user_case/competitor_cutmatch/FINDINGS_BOUNDARY_REFINER_COMPARISON.md`。零 `mvp/src` 改动。


> **▶ 2026-09-26 — 口径审计闭环 (V5): 竞品会话的「三指标口径伪影」假设在 runtime 层量级 ≤ +2 → A1/ViT-B/场景聚合 三组对照全部稳健; 非 HIT 主因重定位到「定位层 19 / 特征层 1」**
> 背景: `HANDOFF_CUTMATCH_AND_METRIC_AUDIT.md` §3 断言「严格命中用 GT 编辑段中点代表整段 → 17/22 非 HIT 实为口径伪影,
> 过去所有以 117/139 为标尺的对比（A1 −16 / ViT-B −1 / 场景聚合 −6）都带该噪声」。本轮把该假设**做对做全**并给出裁决。
> **A. 判据复算（零 runtime, 只读结果文件; `mvp/scripts/measure_recall_v5.py`）**: 7 组判据并行
> （S=现行严格, Z=零宽编辑窗点包含, T=原片窗±0.5s 容差, R_rec=Z+T, O=实质重叠, A=任意重叠, SE=编辑窗±0.5s 膨胀对照）:
> 基线 **117 → Z 118 → T 118 → R_rec 119 → O 117 → A 118 / SE 123**;
> ⇒ **口径噪声量级 ≤ +2**（A1 差异是 −16）→ 「必须重跑四片基线才能重估」**不成立**（假设否证, 有据）。
> **B. 真正缺陷 2 例（均出图确认）**: `test1/t1r08c` GT 编辑窗**零宽** [33,33] → `ed_inter>0` 结构性恒假（Z 修复）;
> `test1/t1r07a` span 起点越界 0.33s（T 修复）。**编辑窗 ±0.5s 判据 = 膨胀, 已拒绝**: 6 例翻转中 **5 例严格编辑侧重叠 = 0.00**
> （命中由**相邻编辑段**用 41–106s 大跨度场景 span 认领）→ 教训: 存在宽场景 span 时任何"重叠式"宽松判据都会被邻段认领。
> **C. 三组对照在 7 组判据下复算**: A1 TransNetV2 **Δ −16/−17（最宽判据仍 −16; 膨胀判据 −8）**; ViT-B **Δ −1 ~ +1**
> → **口径内不可区分**（原「轻微负向」表述改写）; 场景聚合（仅 2mkv）**−6/−8 逐位不变**。
> 更正交接文档: A1 翻转实测 **退化 28 / 改善 12**（文档 32/12 算术不自洽, 32−12=20≠净 −16）;
> `t1r08b` 被判 REAL_FAIL 系审计脚本边界 bug（`times>=2922.2` 排除 2922.0）, 窗内最佳帧 **rank 1 / sim 0.838**。
> **D. 139 例检索天花板（`audit_retrieval_ceiling.py`, DML 218s, 编辑窗内 6 个 GT 引导查询点, 窗 ±0.5s 取最佳帧全片 rank）**:
> HIT 117 / **R1(rank≤3) 19** / R2(4–20) 2 / **R3(rank>20) 1**。
> **E. 非 HIT 22 例机制分诊（`diag_nonhit_localization.py`）**: 口径 **2**（零宽 1 + 容差 1）/ **定位层 19**
> （池·选择 14 + 查询单元稀释 5, 检索 rank 全部 ≤7）/ **特征层 1**（`t2r05a` rank 77 sim 0.479）。
> ⇒ **剩余损失主因是定位层而非特征层**; 但天花板是 **oracle 口径**（GT 引导查询点）, 重开该方向前必须先给出
> **无 GT 的查询点/子镜头选择信号**（与 FINDINGS_SUBSHOT_QUERY 的 oracle 教训一致）。
> 产物: `measure_recall_v5.py` / `audit_retrieval_ceiling.py` / `diag_nonhit_localization.py` +
> `work/recall_v5_{baseline,compare,saagg}.json` / `work/loc_retrieval_audit.json` / `work/nonhit_diag.json` +
> `work/caliber_v5/*.png` + `user_case/competitor_cutmatch/FINDINGS_METRIC_CALIBER_V5.md`。零 `mvp/src` 改动。
>

> **▶ 2026-09-25(续3) — 竞品对标 A1:TransNetV2 场景切分 替换 编辑侧两级切分 = 四片显著更差 → 不接入(有据)**
> 背景:竞品 CutMatch 137 模块图 `matching.scene_detection.*`(10 模块) 对应 **a01 = TransNetV2**; 我方全仓 grep `TransNet` **0 命中**(从未评估);
> 基座同为 DINOv2 ViT-S/14 且竞品**未微调**(a02 与官方权重 SHA256 逐字节一致)。
> 方法:官方代码 + 官方权重(state_dict 90 张量 / 7,618,056 元素 == a01 明文计数; ONNX 对拍 sigmoid 后 max|diff| = 6.1e-8);
> 零 `mvp/src` 改动 —— monkey-patch `_segment_twopass_flash` → TransNetV2 边界 + 最短保护 0.5s + card_guard, 其余管线不变。
> **结果(四片生产管线, 仅切分不同)**: 严格 **117 → 101/139 (−16)**、场景 **137 → 120/139 (−17)**、负例 4 → 3;
> 翻转 = **退化 32 / 改善 12**(2mkv 35→25、test1 34→32、test2 14→13(场景 19→14)、test3 34→31)。
> **边界证据**: 与基线双向 recall 0.76–0.98、中位距离 <0.1s → 判的是同一批画面边界, 差异在**粒度**(更碎) —— 与产品约束
> 「偏向下切分/防碎片化」冲突(依赖大段 + span 枚举 + patch 事件扩池的定位层被拆碎)。
> **裁决**: 不接入; 「竞品多一个学习式场景切分」**不构成能力缺口**(同素材上更差)。
> 产物: `mvp/scripts/tn_transnetv2.py` · `probe_transnet_bounds.py` · `rerun_transnet_runtime.py` +
> `mvp/benchmark/user_case/competitor_cutmatch/FINDINGS_TRANSNETV2_SEGMENTATION.md` + `work/tn_*`(四批结果 + 边界汇总)。
>
> **▶ 2026-09-25(续4) — 竞品对标 A2:对齐链(单调 DP)用作「候选排序信号」= 无增量且更差 → 不引入排序层**
> 事实核查(修正前提):我方**已有**等价的单调 DP 对齐(`engine/localization/seq_align.py`, REUSE research `ta.py`)**且已接入 runtime**,
> 但只用于候选窗内 moment 精修 → 与竞品 `alignment.dtw` 的差异不在「有无对齐」, 而在「对齐分是否参与候选/实例排序」。
> 探针 `mvp/scripts/research_dtw_rank.py`(138 条正例, DML, 260 s): **rank 改善 18 / 恶化 37 / 持平 83**
> (平均真值 rank **2.43 → 2.80**); margin 平均 −0.0495 → **−0.0407**(72 个错配案例中 16 个被纠正 = 22%);
> 核心失败族 p08(兄弟机位)两法皆失败且对齐分 margin 更负(−0.048 → −0.106)。
> **裁决**: 对齐分**不引入排序层**(有据); 现有用法(窗内 moment 精修)维持 —— 竞品把 dtw 放进 `fast_timeline`
> 链路**不构成我方能力缺口**。产物: `user_case/competitor_cutmatch/FINDINGS_ALIGNMENT_RANKING.md` +
> `work/dtw_rank_results{,_all}.json`。
>
> **▶ 2026-09-25(续2) — 产品级定论:ViT-B 全量索引 + 四片 runtime 回归 = 无增益/轻微负向 → 「换更大基座」正式关闭**
> 零 `mvp/src` 改动(env + config + 研究侧 monkey-patch FeatureStore 支持 768d/dinov2_vitb14)。
> 脚本 `mvp/scripts/export_dml_model_vitb.py`(ViT-B CLS-768 ONNX, 346.5MB, torch↔onnx cos=1.000000)、
> `mvp/scripts/rerun_vitb_runtime.py`(harness: SVL_DATA_DIR=work/vitb_data 隔离 + device.onnx_model=ViT-B + batch=1 实测 7.0fps 最优)、
> `mvp/scripts/measure_four_results.py`、`mvp/scripts/diff_four_batches.py`。
> 产物 `work/vitb_{2mkv,test1,test2,test3}.results.json` + `work/vitb_four_metrics.json`,
> 报告 `mvp/benchmark/user_case/feature_upgrade/FINDINGS_VITB_FULL_INDEX.md`。
>
> **结果(四片 31,117 帧 @1fps 全量 ViT-B 索引, 生产管线不变)**: 严格 **116/139**(基线 117) · 场景级 **134/139**(基线 137) ·
> 负例 4/9 持平;分片 2mkv **+1** / test1 +1(场景 −2) / test2 0 / test3 **−3**。
> **27/139 案例翻转**(严格口径 12 改善 / 13 退化)→ 抖动而非系统提升;test1 t1r17/t1r18 由 HIT 变 **MISS**。
> **p08(兄弟机位)主定位两侧都落在兄弟区**(基线 1061-1063 / ViT-B 1034-1041),命中靠子 span 枚举;ViT-B 反而把该段置信从 HIGH 降到 LOW。
> **下游阈值漂移**(换基座未重标定): 切分段数 2mkv 69→66 / test1 41→37 / test3 67→60;置信档分布同步漂移。
>
> **成本**: 索引吞吐 ~11 fps → **7.0 fps**(~1.8×, 四片索引 47→82 min);features.npy **47.8 → 95.8MB**(2×);ONNX 资产 **88 → 346.5MB**(3.9×)。
> 已实测 DML batch 不变性(cos=1.00000000, max|d|≤1.1e-6)→ batch 口径差异不构成对照偏置。
>
> **裁决**: 「该不该换更大基座」= **不换(产品级, 有据)**;与探针级 `FINDINGS_FEATURE_UPGRADE_V4.md`(无一致增益、失败族均不可分)收敛。
> 原「基座升规模无效」结论**维持, 依据升级为端到端回归**。可复用资产 = 一键换 backbone 四片回归 harness。

> **▶ 2026-09-25(续) — P0 第 2 项闭环:`phase24_1` 三探针 + M5 配修正 GT 重跑 = 几何「兄弟反超」证据作废, 运动/盘点维持**
> 按 `FINDINGS_GT_CONTAMINATION_AUDIT.md` §六执行。脚本 `mvp/scripts/research_phase24_1_v4.py`(①②, 393 s)、
> `mvp/scripts/research_phase24_1_data_v4.py`(③, 27 s)、`mvp/scripts/research_patch_recall_v4.py`(M5, 1210 s, DML研究资产)。
> 产物 `work/phase24_1_v4_probe_results.json` · `work/phase24_1_v4_data.json` · `work/patch_recall_v4_results.json`,
> 报告 `mvp/benchmark/user_case/phase24_1/FINDINGS_V4.md` · `mvp/benchmark/user_case/semantic_signal/FINDINGS_M5_V4.md`。
>
> **phase24_1 ①视觉几何**:原两条核心证据**作废** —— (a)「p08b:真值 1048 HOM 0.488 vs 兄弟 1109 HOM 0.752 ❌ 兄弟压倒」
> 中 **1109 本就是真值**(p08 正确位置 1108.15-1109.1),1048-1050 才是作废窗口;(b)「p26 几何 rank 2 假阳性」来自标错窗口。
> **修正后 HOM(单应内点率)在 4 个硬例上均把真值帧排 rank 1**(p08/p08b/p26/t3r12),真值 HOM 0.849/0.752 > 兄弟 0.506/0.534;
> 但 **INL(部分仿射)判据相反**(真值 0.407/0.405 vs 兄弟 0.411/0.431)且真值窗内帧间跳变极大(1108 HOM 0.331→1109 0.849)。
> 另:原存档 p08 的 `GEOM_HOMOG=[1,41]` 与 FINDINGS 文字「兄弟反超」自相矛盾(文档未用自身名次数据) → 一并纠正。
> **裁决**:几何 **既非已证伪也非已可用** → 列为待拍板复验方向(需固定 RANSAC 随机性 + 全索引池 + ≥3 组机位对照, 纯 CPU 成本低)。
> ②运动签名 (6/6 corr_margin 全负, 连 p01 −0.463/−1.357) 与 ③硬负例盘点(每索引 2.6-9.2 万对, 修正锚点密度不降) **维持**。
>
> **M5 patch 召回**:原核心卖点「**patch 把兄弟机位捞回池(p08b 32→2)**」**作废** —— 修正后 p08b 正确位置 CLS 全索引 rank **5**、
> patch 池内 rank **9**(比 CLS 差, NO_RERANK_GAIN);p26 修正后 CLS/patch 均 rank 1;p08 CLS 6→patch 5 维持;p01 2→1 微弱。
> → **patch 作为独立召回通道无信号**(与 M6 v4 全量重算 0/39 一致), runtime 现状(池内重排)即是其全部价值。
>
> **失败族再收窄**:修正 GT 后 2.mkv 侧真实失败案例仅剩 **兄弟机位族(p08/p08b)**;p26(夜读)在三份重跑(feature_upgrade_v4 /
> phase24_1_v4 / M5_v4)中一致消解(全片 rank 1)。防复发机制:两份受影响 FINDINGS 头部已加作废标注并指向 V4 版。

> **▶ 2026-09-25 — GT 污染审计 P0 闭环:`feature_upgrade` 配 v4 修正 GT 重跑 = 「ViT-B 更差」证据作废, 实践结论复现**:
> 按 `FINDINGS_GT_CONTAMINATION_AUDIT.md` §六 执行最高优先项。脚本 `mvp/scripts/research_feature_upgrade_v4.py`
> (9 探针, CPU 前向, 1294 s; 一次 forward 同出 CLS+patch; 支持 `--only` 单探针复算),
> 产物 `work/feature_upgrade_v4_results.json` + `mvp/benchmark/user_case/feature_upgrade/FINDINGS_FEATURE_UPGRADE_V4.md`。
>
> **口径**: 真值窗取自 `ground_truth_v4.json`(2.mkv)/`ground_truth_test3.json`(test3); t4r01/t4r13 剔除(test4 数据无效);
> p08b 修正为 p08 的 1108.15-1109.1; p26 用 1768.2-1770.05; 新增 t3r12(重复镜头硬例); 同一批嵌入帧上同时算 v3/v4 两套标签。
>
> **复现性自检(可信度基础)**: v3 旧口径行**逐位复现原存档** —— p26 −0.0361/−0.0086 · p08 −0.023/−0.0006 ·
> p08b −0.1379/−0.2808 · p27 +0.2016/+0.1222 · p01 +0.1613/+0.1590 · p04 +0.1624/+0.1018 · t3r10 0/0;
> patch 通道同样逐位一致(+0.0057/−0.0027 等)。索引 `features.npy`/`times.npy` 与 `.idx.stale`(原运行所用批)**逐字节相同**,
> `D:\video\2.mkv` sha256 与索引记录一致 → 素材与 ViT-S 基线未变。首版脚本曾漏「逐帧 L2 再求均值」致 p01 复算 0.7817(存档 0.7869), 已修并留痕。
>
> **结果**: ① 原最强证据 p08b「ViT-B 恶化 −0.138→−0.281」= **GT 假象**(修正口径 S −0.0139 / B −0.0171, 两者≈0);
> ② 真失败族(兄弟机位 p08/p08b): **两基座都不可分**(margin ≈0, ViT-S 全片 rank 5-6) → 「**基座升规模不解决失败族**」**复现**;
> ③ 修正口径下 CLS **ViT-B 5 胜 4 负 / patch 6 胜 3 负**, 除 p26 外 |Δ|≤0.08(Δ 均值 +0.018 全由 p26 拉动), **无一致方向**;
> ④ p26「最硬案例」消失: 正确位置 1768.2-1770.05 在 ViT-S 全片索引 **rank=1**(7/9 探针真值帧都是 rank 1);
> ⑤ t3r10 旧「margin 恒 0」= 口径缺陷(真值窗与错位干扰窗共享 447 s 帧), 修正后 S +0.019 / B +0.018、真值 rank 3。
>
> **结论(表述改写)**: 「换更大基座无效」→ 「**无一致增益, 且不解决失败族; 原最强反证是 GT 污染假象(已撤回)**」;
> 「不建议 bump feature_version 全量重建」**维持**。防复发机制部分落地: 3 份受影响 FINDINGS 加「GT 版本」标注头
> (`feature_upgrade/FINDINGS.md` · `phase24_1/FINDINGS.md` · `semantic_signal/FINDINGS_M5.md`) + 审计 §八「GT 版本登记表」。
>
> **残留问题(已于同日解决)**: 本探针 ViT-B 侧是局部窗口嵌入, 不覆盖「全量索引 + 生产管线」——
> 同日已完成产品级回归(见本文件 2026-09-25(续2)): **严格 116/139(基线 117) · 场景 134(基线 137)** → 无增益 → 基座路线关闭。

> **▶ 2026-09-22(续) — GT 污染审计 = 用户质疑成立: 一批结论「从未用修正 GT 重验」却仍在被引用**:
> 用户质疑「前期错误数据导致后续路线与判断失误，你现在的判断不都建立在那些数据上吗」。逐实验核查「是否用修正 GT 重跑过」→
> **质疑成立**。审计全文: `mvp/benchmark/user_case/semantic_signal/FINDINGS_GT_CONTAMINATION_AUDIT.md`。
>
> **已重验(可靠)**: M6 v4 重算(0/39) / M4 v4 重跑 / M8 v4 重跑 / M7 v2 重跑(0/12) / M1-M2 v2 复审 / T1(基于 139 verified GT)。
> **从未重验(存疑, 仍在被引用)**: ① `feature_upgrade`(ViT-S vs ViT-B 特征升级, Phase 23-0) —— 9 探针中 **3 个是已证伪案例**
> (p26 GT 标错 / p08b 污染残留 / t4r01 test4 数据错误), 且**「ViT-B 更差」的最强证据 p08b (−0.138→−0.281) 恰来自被作废的污染案例**;
> ② `phase24_1` 三探针(5 探针中 3 个污染); ③ M5(patch 级召回)。
>
> **直接影响**: 「**换更大基座无效**」这一被反复引用的结论**证据不牢** —— 「该不该换更大基座」目前**无可靠证据支撑任一方**。
> **仍可靠**: t2r02b 子镜头 sim 表(多模态逐帧确认: 正确子镜头 0.625 最低 vs 洒水器 0.853 最高) / 蒙太奇识别可行
> (2/7→6/7, 用 corrected GT 校检) / OCR 结构性不可用(事实观察, 不依赖 GT)。
>
> **行动(按优先级, 见 TODO P0)**: ① **重跑 `feature_upgrade` 配 v4 GT**(最高优先, 基座路线唯一直接证据;
> 注意 p08b 用修正位置 1108-1110、t4r01 剔除、p26 用 1766-1770) → ② 重跑 `phase24_1` → ③ 重跑 M5 →
> ④ 建机制: 研究结论显式标注「基于哪版 GT」, GT 修正时自动列出受影响清单(本项目已因缺此机制亏三次)。

> **▶ 2026-09-22 — macOS(Apple Silicon) 从「整包 Mock + 打不开」到端到端跑通（5 个 commit, 全部已 push）**:
> 用户拿到 mac 包后连续暴露 5 个**打包/分发链**缺陷（都不是算法问题），逐个定位修复，最终实测跑通
> **真实影片全流程**：`index finished frames=6798 backend=mps elapsed=553.8s` →
> `locate finished segments=36 candidates=59 results=36 high=23 medium=3 low=8 elapsed=1017.5s`。
>
> 1. **`83c73e1` 整包跑在 Mock（最隐蔽）**：`.gitignore` 的 `.env.*` 把 `mvp/ui/.env.production` 排除在 git 外 →
>    CI checkout 无此文件 → `vite build` 时 `VITE_BACKEND_MODE` 未定义 → `resolveService()` 回落 `MockServiceAdapter`：
>    UI 恒显「已连接」（`checkHealth` 硬编码 CONNECTED）、日志恒为 `[mock] log line 1/2`（`fetchRecentLogs` 硬编码）、
>    分析永不结束。**修复**：`resolveService` 生产构建默认 `http`（不再依赖 env 文件是否存在）+ workflow 显式注入
>    `VITE_BACKEND_MODE` + `.gitignore` 放行 `.env.production`（仅公开 VITE_* 变量）。**实证**：移走 env 后构建，
>    产物编译为 `resolveService(){return resolveFor("http",void 0)}`（Mock 分支被常量折叠消除）。
> 2. **`bb419c0` ffprobe 动态链接崩（每次建索引必崩）**：CI `brew install ffmpeg` 是动态链接版，
>    `build_backend_mac.py` 只 `copy2` 可执行文件进 bundle → 用户机 `dyld: Library not loaded:
>    /opt/homebrew/Cellar/ffmpeg/9.0.1_1/lib/libavdevice.63.dylib`。**修复**：改用 `static_ffmpeg` 的静态构建
>    （与 Windows build_backend.py 同源）+ CI 加 `otool -L` 防回归检查（引用 Homebrew 路径即构建失败）。
> 3. **`78bee3d` 剪映草稿导出缺 `pyJianYingDraft`**：该模块在 `exporters.py:560/575` 是**函数内延迟 import**，
>    mac CI 从未安装（Windows 用共享 venv `video-dedup-tool\.venv` 装了它, 所以 Windows 正常）；且它依赖 `pymediainfo`，
>    **mac 上 pymediainfo 不自带 dylib**（Windows wheel 自带 MediaInfo.dll），无 fallback（`can_parse()` False 直接 ValueError）。
>    **修复**：CI 装 `pyJianYingDraft` + `brew install libmediainfo`；spec 加 hiddenimports；`build_backend_mac.py` 把
>    `libmediainfo.0.dylib` 装配进 bundle 的 `_internal/pymediainfo/`（pymediainfo 优先从**自身包目录**加载库，
>    与 Windows 包里 `_internal/pymediainfo/MediaInfo.dll` 同机制）+ 缺失时**硬失败**（不静默出厂坏包）。
> 4. **`cbed284` pyJianYingDraft 的 `assets/*.json` 未收集**：`assets.get_asset_path()` 基于 `Path(__file__).parent`
>    读包内模板（`draft_meta_info.json`/`draft_content_template.json`），PyInstaller 只收代码不收数据文件 →
>    `Asset file ... does not exist`。**修复**：`collect_data_files("pyJianYingDraft")`（与 rapidocr 同一手法）。
>    ⚠️ **该缺陷对 Windows 包同样成立**（现存 win-unpacked 的 `_internal/pyJianYingDraft` 不存在）。
> 5. **`ff71db6`（09-10）设备标签厂商中立化**：`AMD GPU (DirectML)`→`GPU (DirectML)`、`Apple GPU (MPS)`→`GPU (MPS)`；
>    下拉框改由**后端 `available_devices` 驱动**（Windows 不再出现 Apple/MPS 字样）；后端 `device_settings()` 补 MPS 探测。
>    （`e7439e5`（09-10）修的是 mac 包「文件损坏」：`identity: null` 完全跳过签名 + electron-builder 的 7za zip
>    丢 Framework 符号链接 → ad-hoc codesign + `ditto` rezip。）
>
> **验证**：前端 typecheck + vitest 67/67 + 后端 test_settings 4/4 全绿；YAML/Python 语法校验；
> `collect_data_files` 实收 2 个 JSON；mac CI run 18（`head_sha=83c73e1`）success。
> **下一步（未完成，见 TODO P0）**：① mac CI 重触发验证 `cbed284`（导出剪映草稿）；② **Windows 包需重打**
> （现存包早于 `cbed284`/`ff71db6`）；③ 可选优化：`patch reranker device=cpu`（patch 重排仍在 CPU 跑）。

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

---

<!-- 结构修复：以下为原文 L137 起的更早记录（2026-09-05 及以前），与此前段落合并保留。 -->

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

## Completed

- 历史完成项见本文件 `Current Task` 段落（2026-08-25 ~ 2026-09-29, 至续30）以及 `.agent/archive/` 中的 checkpoint 与 `CHANGELOG.md`。

## Current Problem

- **无阻塞项**（2026-10-01 续36 更新）。算法/竞品研究线全线收口（E 层空、数据段挖穿、
  TOP1 成片渲染已移植）；生产现役基线 = 严格 **132/139** · 场景 137 · 负例 4/9 ·
  导出实得（仅主 span）**119/139**（两旋钮 2026-10-01 翻默认开，口径与代际见 Next Actions 4）。
  打包态性能账**已闭环**（续36：根因 = patch 精排器缺资产回退 CPU torch，实测 2.6~3.9×；
  修复已落源码，Arm D 大素材 1400.5s ≈ venv 1396.7s，零语义三方差异 0）。
  剩余全部是**等用户拍板项**：
  ① **git**：续33 已交并推送；**续33后续 + 续34 + 续35 + 续36 改动未提交，等用户口令**
  （铁律「git 我喊你交你再交」，建议拆笔：mvp 源码+测试+资产清单 / 研究脚本+探针+验收 / 档案文档）；
  ② **r5 重打（新）**：续36 的修复只有重打才进分发包；重打后必须跑
  `mvp/scripts/accept_packaged_bundle.py`（当前对 r4 win-unpacked 实测 `FAILED=5`，重打后应全 PASS）
  + 真机核对精修进度文案与导出默认项（r4 遗留未复核项）；
  ③ ~~分发包 r3/r4~~ → 已完成（现役包 = r4 `Video-Locator-win-x64-20261001r4.zip`，仍带 CPU 回退缺陷）；
  ④ ~~UI 真机 E2E 复核~~ → 已完成（2026-10-01 续35 E2E 全过 + 4 项新发现，其中 UX-P1/UI-P3 已在 r4 修）；
  ⑤ ~~两旋钮默认值翻转~~ → 已完成（2026-10-01，选 (c)），DECISIONS 2026-10-01 条目；
  ⑥ ~~`rendered/` 并入残留清单 + 32 份研究文档 GT 版本头~~ → 已完成（`PROJECT_AUDIT_20260928.md`
  新 §9 全量应用数据目录清单；44 份文档补头）；**清理执行**仍等拍板（可释放 ≈2.06GB，全在产品运行时目录）；
  `routes/results.py` 尾巴**已结（2026-10-01 续35）**：`load_failed` 撞码改 `LOC-1107`、
  `detail` 技术串确认为设计内不动。
- 已知局限见 `Known Issues`。

## Current Implementation

- 实现细节见项目源码与 `PROJECT_HANDOFF.md`；本文件按协议不复制源码。

## Current Decision

- 重要技术决策见 `.agent/DECISIONS.md`。

## Next Actions

> **时效校准（2026-10-06 续60）**：现役未结项以本文件 `Current Task` 顶部「续60」块为准。
> 下面 `0-new`（续55 交接）里的 **(d) 等口令三项已全部落地**——三旋钮翻默认（续57 四片联合双臂
> PASS）、r9 出包 + 真机全链复核 PASS（续58/续58 补一）；git 提交仍等口令。
> **计时口径**：该块标题的「19~31 分钟」是翻默认**之前**的默认态；现役 = **15~31 分钟/片**（续57 on 臂）。
> 该块 **(c) 关键新知识**（成本换位到解码秒、CPU 抓帧 78%/DML 18%、网格与并集互斥、
> 硬解三入口全闭 + 假加速陷阱、test1 跨 run ±18% 方差、单片形状不外推、`id(frame)` 假读数）
> **仍然有效，后续必读**。

0-new. **▶ 交接要点（2026-10-06 续55，现役默认态 = 一条片 19~31 分钟）**

   **(a) 这批做了什么（源码已改，未提交）**：① 真缺陷修复 `FFmpegIO._grid_select_expr` 的 `%g`
   → `%.6f`（簇锚点三位小数被截成两位 ⇒ select 窗偏离 ≤0.005s ⇒ 跨源实测修复前 test2 1/300 ·
   2mkv 6/300 · test3 6/300 **取到不同帧**，而 0.5s 护栏抓不到；修后四片合成 micro
   **1200/1200 逐字节同帧**；L2 索引标签全整数秒 ⇒ **已入库索引无需重建**）；② 新旋钮
   `pipeline.patch_refine_grid`（**默认关**，test1 同脚本双臂 **1.068×** + 0 差异）；
   ③ `patch_refine` **段内候选窗并集**（无旋钮、已生效，本批最大一刀）；④ 新配置
   `media.cluster_workers`（**默认 1 = 现役串行**，test1 同脚本双臂 **1.071×** + 0 差异）。
   门禁后端 **534 OK (skipped=2)**；未改 GT、未 bump `feature_version`。

   **(b) 零语义验收链（可直接沿用）**：`%.6f` 四片 strip 全等（test1 0/55 · test2 0/67 · test3 0/103 ·
   2mkv 0/84）；并集同样四片全等 ⇒ **三指标 136/131/138/4·9 因字节等价自动成立，不需重跑**。
   参照臂 = `work/spawn_consolidation_regress/{on_<case>(续52-G), postfix_*(修复后), union_*(并集后)}`。

   **(c) 关键新知识（后续必读）**：① **成本已换位到「解码秒数/管道搬运」**（拟合 ~0.17s/spawn +
   **0.164s/解码秒**；680 spawn / 561 调用 ≈1.2 簇/调用）⇒ 减少解码量才是主线，减 spawn 次数已榨干；
   ② **真实占比 CPU 抓帧 78% / DML 推理 18%**（续54 写的「GPU 仅 2.4%」= 探针只数了一个入口，已更正）；
   ③ **网格与并集互斥**：select 只服务单一相位，多相位并簇会**静默**拿到晚 ≤0.5s 的帧 ⇒ 代码与单测已锁；
   ④ **硬解 AMD 三入口全闭**：d3d11va 净 0.42×（续54）· d3d12va 与 dxva2 本 build **解不出帧**
   （hw 可用窗 0/6，报错 `hardware accelerator failed to decode picture`）且解码地板 0.38~0.78×
   ⇒ 判负表在 FINDINGS §5.9；**探针读数陷阱**：不出帧时汇总会算出 31~148× 假加速，先看 `hw 可用窗`；
   ⑤ **test1 同代码态跨 run 方差实测 ±18%**（1155.4/1287.3/1384.2s）⇒ 提速只认同脚本双臂；
   ⑥ **单片形状统计不能外推**（本批据此判「并集没肉」被三片实测推翻，见 STATE 续55 ④c）；
   ⑦ `id(frame)` 判「重复嵌入」是假读数（CPython 地址复用），要判重复回到时间戳/键集合。

   **(d) 等口令（铁律）**：① **git 提交**（续54~续55 共 24 个改动/新增文件；建议拆 mvp 源码+测试 /
   研究脚本+探针 / 档案文档 三笔）；② **翻默认两旋钮**（`patch_refine_grid`、`cluster_workers`
   各自还差**三片同脚本双臂**，约 2h/个）；③ **r9 出包**（现役 r8 不含续54~续55）。

   **(e) 下一刀候选（按账排序）**：① `other` 桶 **294.4s = 22%**（主循环内逐段 patch rerank /
   patch_v2 近场救援 / text_anchor OCR；窗跨度中位 24.8s、步长多为**恰 4.0s** ⇒ 整数秒网格可用，
   先按 §5.7 的跨源合成 micro 验相位再接线）；② isc_refine 精扫 264.5s（步长 0.866/0.956 等非整数 ⇒
   先解相位，`isc_refine_grid_refine` 维持默认关）；③ 遗留不阻塞项：**mkv 建表异步化（解耦）**、
   **代际差精确点位穷举**（8 行 `v2_*` 跨代际差，续52 口径已结案）。

   **(f) 上一批（2026-10-05 续53）交接原文**：保留在下面，历史细节以 CHANGELOG +
   `.agent/archive/` 为准（mkv 建表 5.01× 结案、`isc_l2_index_enabled` 已翻默认 True）。

   ---
   **▶ 交接要点（2026-10-05 续53，mkv 建表性能结案——翻默认前置全部清除）**

   **(a) 续53 一件**：「mkv 建表慢」错误归因更正（真因 = 容器尾部音频比视频流晚 8.4s ⇒
   死目标逐个整表重试）+ `isc_l2_index.py` 三缺陷修复（pts 截断/死簇守卫/fps≠1 推进）+
   脚本委托 build_tp_index。test1-om 重建 5.01×（3198→638s）且**逐字节等价** ⇒ 续52 验收沿用。
   后端 521 OK。明细 = FINDINGS §5.6.6。

   **(b) 已拍板执行（2026-10-05 口令「1」）= 翻默认 `isc_l2_index_enabled=True`**：config 注释
   证据链+回退路径 · 回归锁翻转 · DECISIONS 落账 · PRODUCT_INTRO 口径同步（27~43min）·
   `_ensure_isc_l2_index` stat/sha 保护补齐；后端 521 OK。**等口令**：git 提交（续41~续53）/
   r8 重打 / mkv 建表异步化（解耦，已无性能压力）/ 代际差精确点位穷举（下批，不阻塞）。

   **(c) 关键新知识（后续必读）**：① 双时间系统 ~0.5s 错位（iter_frames 合成标签 vs 真实 pts，
   索引/建表一律 truepts 化）；② 归档批 `v2_*` 跨代际差异 8 行（续46 窗解码未穷举帧差，
   双新臂口径不变）；③ 本进程内异步 DML 有段错误/污染风险（续6/续43）⇒ 后台任务做 DML
   前必须先做进程隔离。

   **(a) 本批已完成（源码已改，未提交）**：宽扫粗扫「网格抽取」L1 —— `FFmpegIO.grab_grid_times` /
   `_grid_select_expr`（锚定簇起点的无漂移 select）/ `MIN_GRID_STEP_S=1.0` 亚秒护栏 /
   `_decode_window(max_pts_lag=)` 安全网 / `isc_refine.grab_grid` 注入 / `locator_service._grab_grid_batch`；
   **`pipeline.grab_grid_decode` 已翻默认 True**（用户拍板选项 B）。验收五条 = 帧级逐字节等价 · test1
   逐字段 0 差异 1.27×（46.2→36.4min）· 2mkv 双新臂 0 差异 1.30×（53.8→41.3min）·
   **四片三指标逐项一致（严格 136/139 · 导出 131 · 场景 138 · 负例 4/9）** · 后端全套 512 OK。
   决策全文 = `DECISIONS.md` 2026-10-03（续51）；明细 = `FINDINGS_COST_STRUCTURE_LEVERS_20261003.md` §5。

   **(b) ✅ 已结案（2026-10-04 续52，口径定稿）**：fresh 双新臂 test2/test3 由旧会话跑完（本会话子代理
   轮询接管监控），两片 **0 差异** ⇒ 四片全部 0 差异；归档差 = **`v2_*` 跨代际**（vs fresh off：
   test2 3 行 span / test3 1 行 span + 4 段边界 / 2mkv 1 段拆合；L1 off 路径惰性；机制未定位留白，
   「整格跳位」旧归因已撤回；FINDINGS §5.5 定稿）。监控/接手续命作废。

   **(c) L2 = 源片 ISC 索引**（把「每条成片重复解 180s×N 段」换成「每部母片一次」）：
   ✅ **test1 首批过**（建表 8221 帧/7.8MB + 探针 20 段 |Δt| 中位 0.5s、>2s 条数 0）；
   **剩余**：test2/test3/2mkv 建表 + 扩样验证 → 接线立项（改 runtime，需验收）。

   **(d) 等口令（铁律）**：① **git 提交**（续41~续51 全部未提交，80 个改动文件；建议拆 mvp 源码+测试 /
   研究脚本+探针 / 档案文档 三笔）；② **r8 重打**（现役包 r7 不含续41~续51 任何改动）。

   **(e) 口径提醒**：① 归档批 `v2_*` **不能**当单变量 A/B 的 off 臂（跨代际差异已实测）；
   ② 加速比只报干净口径（test1 1.27× / 2mkv 1.30×）；③ 未改 GT、未 bump `feature_version`。

0. **GT 核对已完成（2026-10-01 续39）**：20条结案，17修订/3保留；当前同批读数133/125/138、负例误报4/9，版本与证据见Current Task。后续比较须使用同GT版本；算法未命中仍按报告保留。

0b. **等用户拍板（2026-10-02 续43 新增）**：**方案B 探针正判（ISC21 过门槛）后的下一步**——
   ① **采纳门控设计**（ISC 作第二意见，只对 patch_refine 歧义段 top-K 候选做 ±5s 局部窗重扫重排，
   融合判据 + 三指标回归 + MISS6/t2r03b 必验收）或 ② **先扩验证**（全 139 正例位置扫描复算 ISC
   峰位命中分布，排除 5/6 小样本运气）；② git 提交（续41+续42+续43，铁律等口令）。

1. **等用户拍板（2026-10-02 续40 更新）**：
   ① ~~r5 重打~~ → **已完成（2026-10-02 续40）**：`Video-Locator-win-x64-20261001r5.zip` 出包，
   `accept_packaged_bundle.py` FAILED=0、三防冒烟全过、真机 test2 全链 27.0min + device=dml +
   精修进度文案/导出默认「全部」两尾巴销项（详见 Current Task 续40 块与 CHANGELOG）；
   ② **git 提交**——续33后续 + 续34 + 续35 + 续36 + 续40 未提交（源码假桩修测 + `config.py` 翻默认 +
   `results.py` LOC-1107 + `HttpServiceAdapter` 话术与默认门槛 + `session.ts`/`App.vue` 健康重探 +
   `MockServiceAdapter` 告警开关 + patch 资产与 `asset.json` + `build-release.ps1`（含续40 编码修复）/
   `main.ts` 接线 + 探针/验收脚本 6 个 + FINDINGS 3 份 + PRODUCT_INTRO + 档案）；
   铁律「git 我喊你交你再交」。建议拆笔：mvp 源码+测试+资产清单 / 研究脚本+探针+验收 / 档案文档；
   ③ ~~分发包 r3 重打~~ → **已完成（2026-10-01）**：`Video-Locator-win-x64-20261001r3.zip`
   （backend.exe 02:25 构建 + 三防冒烟 + 启动冒烟 PASS；旧 r2 zip 已删，用户授权）；
> **③ UI 真机 E2E 复核（可在 r3 包上做，唯一未过的验收项）**——
> **✅ 已完成（2026-10-01 续35 E2E，全过 + 4 项新发现，详见 CHANGELOG「续35 E2E」）**：
> 多选对话框/真实合并(copy 126.8s)/索引复用+DML 确证/shot_split 54→67 与验收逐字一致/
> patch_refine 精排 65 段切换 11/结果页/剪映草稿/**LOC-2002×5 组双通道展示**/成片渲染
> （41 段 h264_amf 2259 帧 CFR 正常）。**新登记**：[UX-P1] 后处理阶段零进度上报（92% 卡感，
> 用户实测反馈）；[性能] 打包态 62.6 min ≈ 实验室 1.56× 需归因；[UI-P3] 侧栏后端徽标 CPU 误标；
> [日志] 预览流 asyncio 噪音。
   ④ **下批方向（(E) 研究线已收口于续32/33，(A)/(C) 未开工）**——
      (A) 成片补「缺口标记」（黑场腿或时间码条 + 可选解说轨开关）：成本中，竞品黑场腿形态已字节确证；
      (C) 入库层四件（盘符浏览·自然排序·白名单·磁盘预检）/ 大文件鲁棒性四件（CFR 代理·memmap·
          停滞看门狗·独立 GPU 工作进程）。E 层（算法差集）已空。
   ⑤ ~~两旋钮默认值翻转~~ → **已完成（2026-10-01，三选一选 (c)：两个都翻 + PRODUCT_INTRO 口径下修）**，
      DECISIONS 2026-10-01 条目；生产现役基线自此 = 132/119/137/4。
   ⑥ ~~杠杆3 是否立项~~ → **暂缓不立项（2026-10-01 随翻默认一并裁决）**：上限仅旋钮段推理 ~22%，
      翻默认后 pre-knob P 段占比更大、性价比更低；重开须四片三指标零回退验收。
2. **接线卫生（2026-10-01 续35 清两件、续36 再清四件，均已结）**：~~`results.py` 技术串口径~~
   （`load_failed` 撞码改 `LOC-1107` + detail 设计内）、~~网络级失败条幅中文话术~~、
   ~~`HttpServiceAdapter` 兜底门槛与「默认全部导出」不一致（`'MEDIUM'→'LOW'`）~~、
   ~~成片产物 `rendered/` 未进残留清理清单~~（续36 连整个应用数据目录清单补进
   `PROJECT_AUDIT_20260928.md` §9，并登记「统一清理入口仍未实现」）、
   ~~后端进程消失后侧栏不重探健康~~（`session.startHealthWatch` 20s + 断→通重读设备，READY 后启/Mock 不启）、
   ~~Mock 适配器不产 `warnings`~~（改 opt-in `localStorage 'svl.mock.exportWarnings'='1'`，
   **不在 Mock 复制后端判据**以免通道漂移）。
   剩余待拍板：竞品「渲染失败仍出 XML」语义未复刻（我方失败即抛话术，是否改「仍出工程 + 告警」）；
   打包态预览流 asyncio 噪音日志（续35 E2E 登记，未定为缺陷）。
3. **维持关闭、勿重试**（各自归档见负结果）：ordered_search/顺序重排、索引密度(2fps)、窄簇票数门、
   E1 重排、DP 下沉、**退化门「唯一认领者存活」拒识形态**（续31 第四次确证；安全形态 = LOC-2002 提示已默认开）、
   conf_v2 **启用与通道均已正式关闭**（续31 补四：36 段逐张读图裁决 = 真内容错仅 4 段，
   18 段属 GT 疑错/同源重复 ⇒ 关闭理由从"信号饱和"升级为"靶子是假的"）、
   commentary_scene(E3)、TN 仲裁换切点、patch/ALIKED 局部通道、
   多模态语义、蒙太奇子镜头查询 runtime、时间轴单调性、**整套换成竞品架构**（续31 补二 四片实测否决）、
   **patch_refine 窗内峰位移**（续37 后续：A/B 两形态导出 119→119 净零；20 行导出缺口按图分诊为异质+GT 疑点，
   下一步若再攻精度须先对这 20 行做 GT 逐帧复核，见 CHANGELOG 续37 后续）、
   **竞品全量重挖（续37 后续二）**：62 模块逐值读完，1× 偏移锚定（净零）/ 编辑帧裁黑白边（2mkv 端到端净负）
   全部关闭，总账 `FINDINGS_COMPETITOR_REDIG_20261001.md` ⇒ **竞品侧精度杠杆已空，勿再开竞品移植探针**。
   ⚠️ **区分「信息性关闭」与「形态性未穷尽」**（续31 补二 立的分类）：前者 = 该层信息被多条独立路径
   打出同一天花板，换实现无效（外观三层/跨段一致性族/语义层/运动-切换不可分）；
   后者 = 判据信息可能有用但移植形态错，**值得换形态重试**，现存 4 条未穷尽：
   conf_v2 换掉三项饱和判据 / 两级采样（细筛+密验）探针从未跑 / E3 把仿射载体换成 patch 对应 /
   `min_scene_coverage` 换成能表达"该候选窗该不该留"的量（现行 cover 语义不匹配，续31 读图确证）。
4. **生产现役基线（2026-10-01 两旋钮翻默认开后更新）**：严格 **132/139** · 场景 139 口径内 **137** ·
   负例 **4/9** · 导出实得（仅主 span）**119/139** · 截等长主 span **111+/139**（⚠️ 含 `±2s` 容差
   贡献，引用须标注；GT 重锚定前旧读数 = 127/105/100，两旋钮关时代 = 130/107/137/4，
   对照旧档案注意口径代际）。对竞品复现链真实领先 = **119 vs 83**（导出实得口径）；
   测试基线 后端 **460** · API **99** · vitest **132** · 双 typecheck 干净（2026-10-01 续36 实测）。

> 更新于 2026-09-29（续30 交接）。已完成条目的历史细节一律以 `Current Task` 各条 +
> `CHANGELOG.md` + `.agent/archive/` 为准，本节只保留当前未结项。

## Important Constraints

- 硬件路线锁定：H1 Windows CPU → H2 Windows AMD(DirectML) → H3 macOS Apple Silicon(MPS) → H4 NVIDIA(CUDA)；不支持 macOS Intel。
- MPS batch_size ≤ 4（H3 POC 结论）。
- DML 批量推理使用 batch=1（RX 6750 GRE + ViT-S @518 实测最佳）。

## Known Issues

- ~~**打包态定位慢 2.6~3.9×（续36 根因已闭、修复待 r5 生效）**~~ → **续40 已销项**：r5 包真机确证
  `patch reranker device=dml`，同素材 test2 打包态 locate **62.6min → 27.0min**（实验室 23.3min 量级达成），
  结果与 r3 逐字段一致零语义漂移。现役包 = **r5**（`Video-Locator-win-x64-20261001r5.zip`）；
  r4 zip 仍在 release/ 未删（删旧包需授权）。
- ~~**`dinov2_cls_patch.onnx` 在仓内无再生成脚本**（续36 登记）~~ → **续37 已闭**：
  `mvp/scripts/export_patch_onnx.py`（`forward_features` 双输出包装，默认出到 `work/_patch_onnx_export/`
  不覆盖仓内资产）。实测新导出 vs 仓内资产：CLS/patches 两路 max|d|=0、`.data` sha256 相同（亦与 CLS 资产同字节）、
  DML 加载 `device=dml`；`.onnx` 图字节不同仅为元数据 ⇒ **不替换仓内资产**（保 sha256 锁定），
  `asset.json.source` 已改指该脚本。后端 460 全绿。
- **mac 包会多带 ≈88MB 死资产**（续36）：`PatchReranker._try_onnx` 只认 DmlExecutionProvider，
  macOS/MPS 侧本就走 torch；`extraResources` 是整目录复制，H3 正式化时需按平台裁剪。

- ~~**（续19）** 本机 API 门禁只做了令牌 + 发行通道拒启，端口仍固定 8765；导出 `warnings` UI 未展示~~
  → **续20 已闭环**：随机端口（BACKEND_LISTEN 公告 + Electron 解析 + 页面 query `svl_port`）与
  导出告警展示均已落地；剩余 = 打包 exe 端到端验收（等授权）。

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

2026-10-07（续62 补二：剪映去重语义统一 + 旧回并丢素材缺陷发现）
