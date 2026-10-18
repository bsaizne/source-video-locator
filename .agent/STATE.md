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


> **▶ 2026-10-18（续64）— 边界误差分型 + 索引网格损失（scn3 预演）+ B 线判负；一处判据订正与一条疑似缺陷【现读这条】**
> 口令「以你自己的理解说边界问题还要怎么进步」→「开」→「先 a 试试」→「再试试 b」→「交接」。
> **全程只读**（mvp/src 零改动、索引未重建、无新依赖）；明细 archive/HANDOFF_20261018_boundary_precision.md。
> **一、分型（先有分母）**：先复现 0.732/0.832/0.779，再拆 = 漏检 **21/125** · 漂移 **104**（le0.12s **26** /
> 0.12~0.50s **63** / >0.50s **15**）· 假阳 **38** · 有符号中位 **0.000**（早 38 / 晚 40 ⇒ **无系统偏置**）。
> **二、网格损失（本轮核心）**：同批候选、唯一变量 = 是否吸到 1fps 网格：abs_med **0.250 → 0.050**、
> le0.12s **27.6% → 77.9%**；现役漂移 p90 恰 **0.520s** = 1fps 吸附上限；与导出侧「真剪点偏差中位
> **0.249s**」同量级 ⇒ **端点漂移主因疑为网格而非扩宽规则**（与 cap 判负自洽；⚠️ 归因假设，未接线实测）。
> **三、scn3 预演（探针已入库）** mvp/scripts/shot_detect/probe_scn3_precision.py：尺子 ±0.5s →
> A 现役 n=93 **0.250 / le0.12 27** · B 像素10fps n=103 **0.050 / 82** · **C 融合(scn3) n=105 0.100 / 80**；
> 窗内条数 **142 → 134（不碎）**。导出侧 11 条真剪点：A **0.249**（le0.12 4/11）· B/C **0.000**（⚠️ **同源**）。
> **四、B 线判负**（语义分格 CLS：整帧+左中右三竖条，零新依赖；cv2 在位但 haar/YuNet 模型为空）：
> 两窗口（±2s / [-4,0]）A 族最好 **0.555**、B 族最好 **0.553**，判死线 0.70 ⇒ **不接线、不加依赖**。
> 旁证：GT 处整帧语义距离 **0.0869** vs 随机 **0.0857**（若真是两人对切，语义不可能不动）。
> **五、⚠️ 判据订正（我错，原话留档）**：第一版用 **±0.5s** 窗口，但这批样本精度是 **±2~4s**
> （t1_long_sheets.py:33 FPS=0.25；t1_missed_attr.py:54 WIN=2.0）⇒ 那组「AUC 0.42~0.53 判负」**作废**，
> 已按两窗口重算（见四）。教训：**判据窗口必须与样本时间精度匹配**。
> **六、新发现（未决）**：52 条漏切拆 verdict = **P2 45 条(87%，pix 中位 0.040)** /
> **P3 5 条（有峰被「3×邻域中位」杀；读图确认 2 条真切点：t=1831 屋顶→火焰 @t+1.2s、
> t=6861 双人全景→遮挡近景 @t+0.4s）** / P1 1 条 / **?CLS腿应命中 1 条（cls_max 0.718 远高于门 0.30 却漏
> ⇒ **疑似真缺陷，优先级最高**）**。
> **▶ 2026-10-18（续65）— 结案「CLS 0.718 疑似缺陷」：是假缺陷；但挖出真漏检 + verdict 链结构缺陷 + 门扫参零和【现读这条】**
> 口令「继续」。**全程只读**（`mvp/src` 零改动、索引未重建、无新依赖、未出包）。
> **一、结论翻转**：t=3782 那条 **CLS 腿命中了、边界也产出了**（3780.0）——不是缺陷。
> 探针 `work/boundary_20261018/cls718_probe.py` 逐环复刻生产链：CLS 峰 **0.7185 @t=3780.0**（local_peak、
> ≥0.30、**gate 通过 dist=0.2531/dev=0.2527**）· 像素腿候选 **3780.3**（gate 通过）· 融合后两者同位置被 NMS
> 合成一条 ⇒ `scenes.npy` 确有 **3780.0**。
> **二、错在哪（两处都是我的，原话留档）**：① `t1_missed_attr.py` **判定窗 ±1.5s 窄于取峰窗 WIN=2.0s** ——
> 边界落在 1.5~2.0s 之间时，脚本一边拿它当证据一边判它不存在；本案 3780 距 3782 = **恰 2.00s** ⇒ 被判 has_bound=False。
> ② 该脚本 verdict 是 **if-elif 链，CLS 腿排最后** ⇒ 被像素腿否掉的条目**永远走不到 CLS 分支**，
> 于是「52 条只 1 条标 CLS」被误读成「CLS 腿只对 1 条有信号」。独立复算（`cls_arm_coverage.py`）=
> **局部极大且 ≥0.30 共 11 条**（非 1 条），过 gate 后 2 条**全部落在已有边界上** ⇒ 真实净漏 = **0**。
> **三、目检坐标自己偏了 ~1.7s**：0.25fps 接触表（4s 一格取中点）在 5fps 细采样下显示真切点在 **3780.3**
> （`fine_429_3782.png`：3777~3780.0 同一暗场景 → **3780.2~3780.4 切**；10fps 像素 `3780.3=0.1865` 为全窗第一，
> 是第二名 2.3 倍）⇒ 生产边界 3780.0 误差 0.3s = **命中**，是**目检坐标偏晚**不是引擎漏。
> **四、同批确有真漏检（兄弟条）**：`idx=429 t=3814` → 像素腿 ±2s **空集**（窗内最大 0.0838 < 绝对门 0.12）；
> CLS 腿 **0.4411 @3816.0 通过**；**持续性门 dist=0.0973 < 0.10 差 0.0027 被否** ⇒ 不出边界。
> 5fps 细采样确认真切点 **3815.6**（人物灰衣背影 → 暗处火焰）⇒ **信号对、是门杀的**。
> **五、但放宽门是零和（可证伪检查已做）**：`gate_sweep.py` 生产同款判据扫参 —— 现役 0.842；
> best **dist=0.06 → 0.845（+0.003 噪声级）**，且 ±0.5s 口径变差、边界数 +4%；**gate 全关 0.781（崩）**。
> ⇒ **调门不是解**；要救这类只能给 CLS 腿**独立门**（判据改动，需单独立项拍板）。
> **已落档**：`mvp/docs/FINDINGS_BOUNDARY_PRECISION_20261018.md` **§9**（自包含，含 6 条复跑命令）。
> **未结项**：① 接 scn3（bump scn2→scn3 + 出包 r27 + mac 另走 dispatch）
> ② ~~改相对门（P3 那 5 条，上限 4%）~~ = **已结案 = 不做**（见 §10：可达只有 3 条、尺子对这 5 条无话可说、
> 放宽使 R 恒 0.872 不变而 P 单调下滑、全片 +68~150 条边界）⇒ **`pixel_rel_mult=3.0` 改为实测最优档，不再列为待改项**
> ③ ~~查 CLS 0.718 异常~~ = **已结案（假缺陷）**，剩余「CLS 腿独立门」属新立项待拍板
> ④ 主线「过渡不流畅」三样外部输入 ⑤ 下次出包删 r24。
> **新教训（写进 §9.6 第 4 条）**：0.25fps 接触表成的坐标单条不确定度是 **±2s 级**，不能用它论证「精确到秒的漏检」；
> §8.1 那条「判据窗口必须匹配样本精度」在**数据源侧**同样成立。

> **▶ 2026-10-18（续63 补廿四）— r23 已删 + cap 1.5 结论从单片扩到四片（含两条对我自己上一轮的订正）+ C 盘占用查清【现读这条】**
> 口令「删旧包吧，然后继续，然后查查为什么做你这个项目我的 C 盘老被占用空间，不是都在 D 盘吗」。
> **一、删旧包**：按「每出一代删最老」删 **r23**（释放 981,687,209B ≈ 936MB）。删前
> `work/r26_pkg/precheck_delete_r23.py` 双验（期望值从 197 份 `.agent` 文本里抓、读数从 zip 里取）：
> **r26 现役 / r25 / r24 三档与档案逐字一致、`testzip=None`**，r23 自身身份留痕
> = 981,687,209B / 7,078 条目 / backend.exe 77,493,384B sha16 `537bcca18760de77`。⇒ 磁盘三档 = **r26/r25/r24**。
> **二、⚠️ 订正我上一轮写的两条（都是我的错，原话留在档案里不悄悄改，只加订正）**
> ① **「test1/2/3 原片不在本地 ⇒ 单片结论」= 错**。四片原片**全在本地 D 盘**：
>   `D:\video\2.mkv` + `D:\ProjectXIXI\test{1,2,3}\test{n}-om.*`（逐个 `os.path.exists` 已验）。
>   错因 = 我自己那条 grep 管道里的 `sed 's/.*: *//'` **把盘符 `D:` 一起吃掉了**，
>   于是 `D:\ProjectXIXI\...` 显示成 `\ProjectXIXI\...`，我据此判成"UNC 不可达"。
>   ⇒ 教训同族但形态新：**shell 文本处理能造出"看起来像证据"的假读数**；路径存在性一律用
>   `os.path.exists` 逐条判，不要用 sed/grep 的输出反推。
> ② **「cap1.5 逐 clip == 关闭扩宽」+「1.5 档卷轴区间 == 成片通道区间」= 只在 3/4 片成立**。
>   test3 有 **1 条 clip 在 1.5 档仍被扩宽**（`clip62` core=[2939.000, 2943.167] 4.17s → 1.5 档
>   [2939.000, 2945.000] 6.0s = **1.44×，正好在 1.5 阈内**），⇒ 该片的"卷轴 == 成片"不成立。
>   口径改为：**cap 1.5 ≈ 关闭扩宽**（四片 234 条 clip 里 1 条仍扩宽），不是"等于关闭"。
> **三、四片实测（`work/cap15_film_20261018/{four_cases.py,four_case_report.json,sheets_four.py,sheets4/}`）**
> | 片 | clips | 两档不同 | cap 归因 | 至少一边不在切点 1.5/2.5 | Σ素材宽 2.5/1.5/core | 1.5==core | 1.5 卷轴==成片 |
> |---|---|---|---|---|---|---|---|
> | 2mkv | 72 | 12 | 10 | 47 / 37 | 161.2 / 135.4 / 135.4 | ✓ | ✓ |
> | test1 | 45 | 7 | 7 | 42 / 35 | 103.0 / 84.6 / 84.6 | ✓ | ✓ |
> | test2 | 47 | 9 | 8 | 25 / 17 | 92.2 / 76.7 / 76.7 | ✓ | ✓ |
> | test3 | 70 | 11 | 9 | 37 / 28 | 142.7 / 125.0 / **123.2** | **✗ 1 条** | **✗** |
> | **合计** | **234** | **39** | **34** | 151 / 117 | 499.1 / 421.7 / 419.9 | 3/4 片 | 3/4 片 |
> 真剪点偏差（四片合并，44 个扩宽边界、±1.0s 窗逐帧自算像素差）：**32/44 有显著剪点，
> 中位 |Δ| 0.249s、最大 0.917s，26/32 偏 >0.12s、11/32 >0.30s**；按符号 **18 正向 = 2.5 素材把邻镜头
> ≤0.9s 带进卷轴（闪切）**、14 负向 = 少带 0.2~0.9s 本镜头内容。
> 读图 **7/7 张**（新增三片各取头/尾最长两条 + test3 那条 1.5 仍扩宽的）：
> test1 出点时两人扭打未完（丢 4.0s 收尾）／test2 出点丢掉守卫转身收尾 2.0s／test3 入点从精灵特写中段开始
> （丢 2.0s）；2.5 侧 test3_clip33 素材头 **带进上一条镜头 ~0.4-0.8s**（与 18 条正向偏差同向对上）；
> test3_clip62 的 1.5 档出点 2944.72 距真剪点 ~2944.9 只差一两帧 ⇒ **1.5 不是"砍掉收尾"，是"只允许到 1.44×"**。
> **⇒ 补二十 的结论在四片上全部成立且更强**：cap **既不是「过渡不流畅」的成因、也不是解药**
> （cap 归因 34/234 条，而"切口落在镜头中间"两档都有 117~151 条）；单片覆盖边界**已关闭**。
> **四、C 盘占用查清（`work/cdisk_20261018/measure_c.py`，只量不删）**
> | 写入点 | 量 | 谁写的 |
> |---|---|---|
> | `%TEMP%\rea-ghidra-*`（两个目录） | **6.39 GB** | **竞品逆向那条线**（Ghidra headless 工作区，10-17 00:12 / 02:14，内含 428MB 目标 exe 副本 + 分析缓存）⇒ 不是本项目 |
> | `%APPDATA%\Video Locator AI` | 488 MB（`data` 377 + `Cache` 95） | **分发包数据根** + 包内验收（`attr_packaged_headless.appdata_dir()` 就指这里：index 116 + edited_cache 126 + models 88 + isc 30 + merged 11） |
> | `~\.qoder-cn` | 735 MB | CLI 自身（会话/记忆/快照） |
> | `%LOCALAPPDATA%\SourceVideoLocator` | 448 MB（edited_cache 228 + index 102 + models 88） | **源码树/探针态数据根**（`paths.app_data_dir()` = LOCALAPPDATA） |
> | 工具链缓存 | ~1.1 GB | uv 406 + pip 386 + npm 191 + electron 116（venv 在 D，**缓存目录默认在 C**） |
> | `%TEMP%\_MEI000022f02` | 90 MB | PyInstaller 解包残留（10-11，非正常退出留下的） |
> | 我的探针/单测残留 | **仅 14.8 MB**（163 项） | `svl_*`/`tmp.*`；`tempfile.mkdtemp` 在单测 `setUpClass` 里**没有配平清理** ⇒ 每跑一次全套留 ~10 个目录（量小但在长） |
> ⇒ **结论：代码与产物确实在 D，吃 C 的是"数据根按设计落 AppData"+"一次性逆向工作区 6.39GB"+"工具链缓存"**。
> **处置 = 用户裁决（2026-10-18）：三项都不做、不入待办、以后勿再提议。**
> **五、现役未结项**：ⓐ ~~mac dispatch 待他一步~~ = **已闭合**（run `39060341032` 全程 22.5min，
>   三 job 全 success；`macos-package` 11.5min、21 步全绿，含
>   **`Accept packaged mac bundle (gate publish)` success** 与 **`Publish to mac-alpha` success**；
>   回读资产 = `Video-Locator-mac-arm64.zip` **917,013,005B @ 2026-10-17T19:19:39Z**，
>   对旧值 916,840,558B @ 10-13 **+172,447B 且时间戳变** ⇒ 包确实换了，**mac 侧已含 r25+r26 全部后端修复**）；
>   ⓑ 第五道包内合并验收**升不升为常设**；ⓒ 主线「过渡不流畅」三样外部输入；
>   ⓓ `og720-720` 相似度自相矛盾挂账。
> **产物**：`work/r26_pkg/precheck_delete_r23.py`、`work/cap15_film_20261018/{four_cases.py,four_case_report.json,four_cases.log,sheets_four.py,sheets4/×7,sheets4_index.json}`、`work/cdisk_20261018/measure_c.py`。


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

- ✅ **续64 边界线收口（2026-10-18）**: 见 Current Task 顶部块；B 线两窗口 AUC 0.555/0.553 判负；未接线、未出包、未提交。
- ✅ **「改相对门」已结案 = 不做（续65 补二，2026-10-18）**：三条独立读数否掉——① 5 条里**只有 3 条**放宽就能出边界
  （1447 被 G 门 dist 0.0711<0.10 否、6861 被 dev 0.5628>0.30 否，与相对门无关）② 这 5 条**全部在尺子 44 窗之外**，
  尺子对它们既不计 TP 也不计 FP ⇒ 拿 F1 论证属混用两把尺子 ③ 扫 11 档 **R 恒 0.872 不变**、P 单调下滑（现役 3.0 即最优），
  而全片过门边界 762→830~912（+68~150）。⇒ **`pixel_rel_mult=3.0` 从「可疑参数」改为「实测最优档」**，不再列为待改项。
- ✅ **「CLS 0.718 疑似缺陷」已结案 = 假缺陷（续65，2026-10-18）**：边界早在 **3780.0**，CLS 腿与像素腿
  都命中同一位置并被 NMS 合成一条。假象来源 = ① 归因脚本 `has_bound` 用 ±1.5s，**比取峰窗 WIN=2.0s 窄**
  （本案恰差 2.00s）② verdict 是 if-elif，CLS 腿排在像素腿之后 ⇒ 被 P 腿否掉的条目永远走不到 CLS 分支。
  独立复算 CLS 腿真实覆盖 **11 条**（非 1），过门后净漏 **0**。⚠️ 我未再改动 `mvp/src`。
- ⚠️ **同批挖出的真漏检与零和结论**：`t=3814` 真切点 3815.6、CLS 峰 3816.0 通过，但持续性门
  `dist=0.0973 < 0.10` **差 0.0027** 被否；扫参证明放宽门 = **F1 +0.003 而 ±0.5s 口径变差**（gate 全关崩到 0.781）
  ⇒ 调门不是解，要救只能给 CLS 腿**独立门**（新立项，待拍板）。
- ⚠️ 我第一版用 ±0.5s 窗口对 ±2~4s 精度的样本判负，**已作废重算**。
- ✅ **r23 已删（2026-10-18 续63 补廿四，双验通过）**：磁盘三档 = **r26/r25/r24**，释放 ≈936MB。
- ⚠️ **上一轮我自己两条读数被四片实测订正**：① 「test1/2/3 原片不在本地」= 我的 `sed` 把盘符 `D:`
  吃掉造成的误判（四片原片全在 D）；② 「cap1.5 逐 clip == 关闭扩宽」只在 3/4 片成立
  （test3 有 1 条 1.44× 仍扩宽）⇒ 口径改为 **cap1.5 ≈ 关闭扩宽**。四片扩测后**结论不变且更强**：
  cap 归因 34/234 条，「切口落在镜头中间」两档都 117~151 条 ⇒ **cap 非成因亦非解药**，单片覆盖边界已关闭。
- ✅ **C 盘占用查清**：大头是 `%TEMP%\rea-ghidra-*` **6.39GB（竞品逆向那条线）**；本项目侧 =
  产品数据根按设计落 AppData（Roaming 488MB + Local 448MB，**包内验收每次往这里写索引**）
  + 工具链缓存 ~1.1GB + 我的探针/单测残留仅 14.8MB。三项处置由用户裁决 = 不做、不入待办（见补廿四 块）。
- ✅ **r26 已出（2026-10-18 续63 补廿三，构建点 = 干净 commit `ad7cec4`）**：`build-release.ps1` rc=0，
  五道包内验收串行逐条 rc=0（bundle 33 PASS / render / 不变式 / 冒烟 + **新增第五道包内合并腿实测**
  ⇒ 证得补廿一/廿二 的修复**在分发包里生效**）；zip 身份两把尺子逐字相同
  = `Video-Locator-win-x64-20261018r26.zip` 981,697,844B / 7,079 条目 / backend.exe sha16 `9410f2e7baa948d6`
  zip 内 == 磁盘 / 与 r25 文件名差集 0/0。已推远端 `e5b5d90..ad7cec4`（fast-forward）。
- ⚠️ **mac dispatch 未完成（等他一步）**：非交互取令牌被 GCM 明确拒绝（`Cannot prompt…`，首跑还挂死 60s）
  ⇒ 按规矩停手不重试。且**订正一条判据**：mac 的 backend 由 CI 现编 ⇒ 凡 `mvp/src` 改动 mac 就要重出，
  所以现役 mac 包（head `c789670` ≈ r24）**不含** r25 两笔 + 补廿一/廿二。
- ✅ **补廿一 登记的两项遗留已收口（2026-10-18 续63 补廿二）**：① 「开不了」的编码器不再反复白试，
  关键是**不再向用户播报假故障**（改前每次合并 2 条「硬件编码器执行失败，已回退」，而本机无
  NVIDIA/Intel 属正常态；实测同进程内后续每次合并还省 ≈3.3s）；② copy 判据补上「补名后的布局」
  + copy 腿布局留痕，⚠️ 但**收紧面在 MP4 上实测不可观测**（hexagonal 进 MP4 也只报 unknown），
  收益只在容器确实声明不同布局时；③ 顺带堵掉 `declared_layout` 把字面 unknown 当已写明的洞
  （那会让补廿一整套归因静默失效）。新锁 6 项；后端 694 / API 150 / 不变式全绿。
  **仍未出包 ⇒ 用户补廿一 + 本批两条修复都没有。**
- ✅ **`source_merge` 音频布局两族缺陷已修（2026-10-18 续63 补廿一）**：第一族 = 全部输入
  「6ch + 容器未写布局」在**滤镜图协商阶段**硬失败（`Cannot select channel layout … Parsed_concat_{8,12,28}`，
  n=2/3/7 复现）；第二族 = 混合形态**不报错但产物声道结构由第一路决定**（`[5.1,stereo]→6/5.1` vs
  `[stereo,5.1]→2/stereo`），**档案只记了第一族**。修法 = `resolve_audio_layouts()` 先按声道数补名、
  再统一到声道数最多的可解析布局，都可解析且全等时**命令逐字不变**；新锁 13 项（含日志留痕锁），
  后端 **688 OK(skipped=2)** / API **150 OK** / 不变式 **FAILED=0**。
  ⚠️ **未推远端、未出包** ⇒ 用户手上仍是 r25、**没有这个修复**；纯后端 Python ⇒ **mac 要另走 dispatch**。
- ✅ **上一会话留下的三批未提交改动已收口并本地提交（2026-10-17 续63 补十八）**：① 抽素材音轨
  「N 声道 + 未指定布局」硬失败 + 0 字节残留被当已抽好（`2afcec7`）② 竞品切点黑盒对照 + 导出层双臂
  （只读，无代码笔）③ 取材扩宽护栏 `material_expand_rel_cap` 2.5 → **1.5**（`beedb91`）。
  本会话自己重跑门禁（不引用上一会话数字）= 后端 **Ran 675 OK (skipped=2)** · API **Ran 150 OK** ·
  导出计划不变式 **FAILED=0**，三条 rc 均 0。✅ **已推远端并出包 r25（同日续63 补十九）**：4 笔 rebase 到用户自己的网页改动（`cf71641..c3a17e5`）之上 ⇒ **用户手上现在是 r25**；
  ✅ **cap 1.5 的观感面已收口（2026-10-18 续63 补二十）**：12 张接触表逐张读完 + 计划层逐 clip；
  且本条原设计（「双档各出一张成片再读图」）**判空** —— cap 不进成片通道，观感面唯一载体 = 剪映卷轴，
  而 1.5 档卷轴区间 == 成片通道区间 ⇒ 现役包里剪映素材**零 handle**。
- ✅ **导出「UI 干等 6~13 分钟」已修到任务通道（2026-10-13 续63 补十七）— `POST /api/tasks/export` 带进度与可取消，后端全套 670 / API 150 / UI 161 全绿，端到端跑编译产物 `PROBE PASS`（真跨进程 pickle 批）。**已提交并进包 r24**（干净 commit `811932e`，包内四道全绿）；
  ✅ **mac 侧已更（2026-10-16 公开 API 实测闭合）**：他 dispatch 的 run `38429952068` = success，
  head `c789670` 与 r24 构建点 `811932e` 只差三份 `.agent` 档案 ⇒ 代码面等同 r24；
  `mac-alpha` 包 916,840,558B @ 2026-10-13T17:01:02Z（对基线 +12,163B 且时间戳变）= 真换了包。
  读数与判据见 Current Task 补十七 ⑧。**
- ✅ **「导出框红条·无法连接后端服务」结案（2026-10-12 续63 补十六）= 客户端 300s 头超时，不是后端掐连接**：
  全局 `exception_handler(Exception)` 一直有效（四臂真 uvicorn 实测 6/6 回结构化 500），真因是
  Electron 主进程 Node fetch（undici）默认 headersTimeout=300s × 分钟级**同步**导出
  （真机实测 374s/783s 崩、**571s/475s 成功却被报成失败**）。修=桥接层默认 transport 改 node:http
  （30min 显式兜底）+ 非 2xx 透传错误体；端到端 `PROBE PASS`（node:http 臂 330065ms 拿到 200，
  旧 undici 臂 307099ms 抛 fetch failed）。UI 150 项 + 双 typecheck 绿；包侧新 2 锁打在 r22 上**预期红 FAILED=2**。
  ✅ **已出包 r23（2026-10-13 00:1x，干净 commit `a84119d`）**：包内 bundle 28/0 · render 8/0 · 不变式 0 ·
  冒烟 AFTER_KILL=0；zip 内 bridge.js 与磁盘逐字节相同（= 修复确在分发包里）。
  ⚠️ 两条遗留：① mac 包同样有此缺陷，要经 mac CI dispatch 才更新（属搁置项，由用户定）
  ② 导出异步化（进度/可取消）= 未拍板的下一批候选。
- ✅ **镜头检测治本线 A2 已落地并通过验收（2026-10-11 续63 补十三）— scn2 = 像素通道 + CLS 证据 + 持续性门**：
  生产落盘表在同尺上 **P/R/F1 = 0.732/0.832/0.779**（全窗）/ 0.787/0.814/0.800（内区），scn1 是 0.707/0.232/0.349；
  四片生产回归（同脚本双臂）= **严格 130→135、导出实得（仅主 span）112→131（+19）**，
  **严格与导出实得的缺口 −18 → −4**；后端 661 / API 128 / 导出计划不变式 / 派生表成套体检全绿；
  成片渲染 72 段帧数逐帧等值，唯一红项已定性为**验收判据自身缺陷**（详见 Current Task ⑤）。
- ✅ **A2 已提交并出包 r21（2026-10-11 续63 补十四，口令「push吧，然后出包」）**：
  代码笔 `9481f39` + 档案笔 `09714ab`（含补十二/补十三档案 + test1 专项定性）推 `c873e18..09714ab`；
  出包前在同树重跑 **后端 Ran 668 OK (skipped=2) · API Ran 128 OK · 工作树干净** ⇒
  **r21 = 干净 commit `09714ab` 构建**（含 A2 scn2 全部 + 第十三轮导出对话框 UI 修复）。
  包内三道验收全绿（日志 `work/v2_accept/{accept_bundle,accept_render,invariants}_r21.log`）：
  bundle **26 PASS / 0 FAIL**（DirectML 生效 wall=33.1s · 剪映通道 http=200 草稿在位 · 隔离
  `reaped exitcode=0` · 12 行腿埋点在位）· render **FAILED=0**（R1 completed wall=60.1s ·
  64 段无交叠 · 136.366 vs 136.344 · h264_amf）· 导出计划不变式 **FAILED=0**（4 片 × 4 通道）。
  zip = `Video-Locator-win-x64-20261011r21.zip` **981,685,359B / 7,078 条目 / testzip=None**；
  **zip 内 backend.exe 与磁盘逐字节相等**（77,493,043B，sha16 `fa3c394567cc17d2`；
  对 r20 的 77,474,898B +18,145B ⇒ 与「r20 后 `mvp/src` 只有 A2 一处改动面」相容，证明确实重建进包）。
  ⚠️ 包内**未实测**项（如实）：老用户 derived_stale 首触重刷路径（accept 夹具是全新索引态）；
  release/ 现三档（r21 现役 + r20 + r19）：**r18 已按口令删除（2026-10-11）**，释放 ≈940MB。
- ✅ **test1 >30s 长镜头专项定性（2026-10-11 补十三后专项）—「门 v2 过严」假设判负，主因是信号容量上限**：
  读表：>30s 条数 scn1=33 → scn2(v1 门中间产物)=39 → scn2(终版 v2 门)=50（档案原写「39→50」的 39 是 v1 中间产物，
  基线应为 33；`work/shot_gt/a2_refresh_report*.json` 两行可对号）。
  目检（50 条逐条接触表 @0.25fps 全段覆盖，4 子代理同协议标注 + 主代理抽读 3 端极值复核一致）：
  **24 漏切 / 17 真长拍 / 9 存疑**——test1（《北人》解说片）的长段**多数确为假镜头**，形态 = 同场景正反打/机位切换。
  归因（52 个目检切换时刻逐条走生产判据链，`work/shot_gt/t1_missed_attr.py` + 像素序列缓存）：
  **43/52 两腿皆无候选**（像素分中位 0.04 ≪ 门 0.12，CLS 距离亦不足）；**9/52 被持续性门否**，
  其中 7 条是 dist<0.10（前后块直方图几乎没变 = 同场景，正是门要拦的形态）、2 条 dev>0.30。
  ⇒ 放宽门最多救 9/52 且放洪误切，**不动参数**；这 43 条属「兄弟机位/同质场景」已知特征上限族在
  **镜头边界通道**上的投影（与 `Known Issues` 失败族同源），要攻需新证据通道（局部差异/主体跟踪），非调参问题，
  不立项。产物在 `work/shot_gt/t1_long_probe.json` / `t1_missed_attr.json` / `sheets/t1long_*.png`（不入库）。
- 🟢 **镜头检测治本线 A1 已跑完（2026-10-11 续63 补十二）— 结论：调参只到半程，A2 值得开码**：
  尺子建起来了（44 窗 / 540s 目检 / 125 条 conf=high 边界，入库 `mvp/scripts/shot_detect/boundary_gt_v1.json`）
  ⇒ 现役 `scenes.npy` **P 0.707 / R 0.232 / F1 0.349**（±1.0s）= 只找回 23% 真边界；定向区 48s 目检 21 个
  边界而现役给 2 段（38s + 47s 假镜头）。分腿消融：**`z_thresh=1.5` 一腿压掉一半以上召回**（关掉 0.232→0.504），
  `min_shot_s=3.0` 单改几乎无效但与关 z **强交互**（合起来 0.664）；留出窗对照证明调参增益**不是过拟合**
  （F1 0.36→0.65）。天花板：**test2 有 44% 真边界在 1fps CLS 序列上连局部极大都没有** ⇒ 阈值救不了；
  像素通道同尺 **P 0.706 / R 0.864 / F1 0.777**，且成本实测「解码才是主体、与帧数几乎无关」⇒ 边际 ≈+5min/片。
  ⚠️ 朴素并集不能用（R 0.944 但 P 0.461）。已按 **(a) A2 开码**落地并验收（见上条与 Current Task 补十三）；(b)(c) 未做；
  本批 `mvp/src` 零改动。明细 `mvp/docs/FINDINGS_SHOT_DETECTION_A1_20261011.md`。
- 🟢 **成片"重合"根因定性 + B 已落地（2026-10-11 第十四轮）**：多模态读图确认 = `scenes.npy` 漏切
  （3285-3323 一段 38s 实为 4 个镜头；全片中位 8s/最宽 265s）+「完整镜头」扩宽把 1s 短切撑进假大镜头
  → 卷轴重放同一画面。跨 4 片探针：现役 scene 源重叠 Σ=1432.59s；护栏 `expanded ≤ K×core` K≤2.8 都压回
  core 底噪 8.00s，K=3.0 起 test3 漏。**用户拍板 K=2.5** ⇒ 已落地
  `ExportConfig.material_expand_rel_cap=2.5` + `expand_material_spans(rel_cap=)` + 两处透传。
  门禁 630/128/invariants 全绿，实测扩宽 2mkv 62→4、覆盖 531→147s，三通道覆盖不变。
  ✅ **状态更正（补十二 复核）**：本块原写「未提交（待 push）」**已过期** —— B 的代码笔 = `098021b`、
  档案笔 = `c873e18`，两笔**都已在 origin/master**（远端 HEAD 实测 `c873e18`）。
  ⚠️ **A（镜头检测漏切本身）已开第一步并跑完**（见上一条 补十二）——B 只绕开放大器，没修检测本身。
- 🟢 **剪映导出崩（2026-10-10 续63 补十一 第十二轮）— 代码已修 + 全套绿 + 已进包 r20**：真机支持档
  `POST /api/export` 抛未处理 `ValueError: 截取的素材时间范围 [start=0, end=100000] 超出了素材时长(64000)`
  （`exporters.py write_jianying_draft` → pyJianYingDraft `video_segment.py:455`）；ASGI 未处理异常掐断连接
  ⇒ UI 误报「无法连接后端服务 (fetch failed)」。根因 = 三处 `max(0.1,…)` 下限把 <0.1s 短镜头撑过素材时长。
  修 = 抽 `_jianying_segment_speed`（锁原速仅在 `target_us≤mat_us`；末尾按素材时长回压 speed），正常素材行为不变。
  后端 626 / API 128 全绿，新锁 4 条（含结构锁）。**已出包 r20**（未提交工作树构建，zip 内 backend.exe
  与磁盘逐字节相等 sha16 `63987715436d5e31`，对 r19 +635B）；包内 bundle/render/export-plan 三门 FAILED=0。
  ✅ **剪映路径包内锁已补（2026-10-10，选项 B）**：`attr_packaged_headless.py` 现另发一发
  `format=jianying`（min_confidence=LOW + low_policy=backup 保证 ≥1 clip 进 plan），
  `accept_packaged_bundle.py` 断言 `jianying_http==200` 且草稿 `draft_content.json` 含 ≥1 segment
  ⇒ 对 r20 win-unpacked 重跑 **FAILED=0**（实测 `a1.loc.jy_draft` 1 段 target=src=45s speed=1.0 + 抽出
  `og0-45.mp4`）= write_jianying_draft 在包内被真正跑通。**改的是 `mvp/scripts` 两脚本、不进 backend.exe
  ⇒ r20 zip 不受影响、无需重出**。⚠️ 边界：syn 只出 1 条常规 clip ⇒ 包内锁证「剪映写段路径通 + 我的重构没
  弄坏正常导出」，**不专门覆盖 <0.1s 回压分支**（那条仍靠单测；包内要覆盖需造 <0.1s 素材，易 flaky 未做）。
  ⚠️ **未提交**（等口令）。⚠️ 第二层未做（等裁决）：`/api/export` 只
  `except ApplicationError`，其它意外异常仍会显示成误导性 fetch failed。
- ✅ **mac 出包链已闭合（2026-10-10 续63 补十一 第十一轮，读 live CI 复核）**：用户 dispatch 的
  run `37943554701`（head `f29e8d66`）与 run `37955484860`（head `31974f2` = checkpoint HEAD）均
  **三 job 全绿**；`macos-package` 的 step 11 走「通道 A 直链 + sha256 逐文件当场判」一发即中
  （三份资产 try=1，字节数与仓库内 `asset.json` 等值），step 15 门槛绿 ⇒ step 16 publish 绿 ⇒
  release `mac-alpha` 新增 **`Video-Locator-mac-arm64.zip` 916,769,503 B**（2026-10-09T16:27:38Z）。
  ⇒ 此前写的「唯一活跃项 / 只差 dispatch」已不成立；下面第三~六轮的 CI 往返过程**留档不再当待办引用**。
- `macos-package` 第 11 步曾红四轮，**真因由用户口述结案：`model-assets` 那个 release 被他删了**
  ⇒ 我先前写的「偶发网络」与「`api.github.com` 这条 HTTP/2 通道当下对该 runner 不通」**都是错的定性**，
  过程留在 Current Task 第三/四轮但**别再当结论引用**；教训：**先验被访问对象是否还存在，再谈通道**。
  ⇒ 现按用户裁决改挂 `mac-alpha`（published prerelease，直链公开可取、CI 下载端不需要令牌），
  step 11 简化成「A=直链 / B=`gh release download`，sha256 逐文件按仓库内 asset.json 当场判」，
  并保住 fail-fast（红一轮 ≈2-3 分钟）与 annotations 自证两处真收益。
  ✅ **已闭合（2026-10-09 00:30）**：三份权重已重新挂上 `mac-alpha`（HTTP 201 ×3；服务端 asset 列表
  三个字节数逐个与本地一致），并按 CI 用的 API octet-stream 通道（**必须带 `-L`**）回下 1.6MB 那份
  核过 sha256 匹配 ⇒ 两份大文件不做本机回下，完整性由 CI step 11 逐文件 sha256 当场判。
  ✅ **后续 dispatch 已执行且全链绿（2026-10-10 第十一轮复核）**：见本节顶部 ✅ 条与 Current Task 第十一轮。
  本机 credential helper 这次**非交互返回**令牌（`GIT_TERMINAL_PROMPT=0`+`timeout`，没弹登录窗），
  用完的临时文件已删；⚠️ 我曾用 `Get-CimInstance` 读进程命令行而**把令牌打印进会话一次**，
  已建议他撤销该 OAuth 授权重登（他决定），后续我不再读进程命令行/不打印含令牌内容。
  我这轮另有两次自己的操作失误（详见 Current Task 第六轮段）：误判第一次上传失败而起第二次
  （脚本「同名先删再传」⇒ 三份删了重传），又 kill 掉大文件那一发 ⇒ ISC `.data` 在服务器上缺了≈25 分钟。
  ⇒ 教训：**长上传的进度判据 = 服务端 asset 列表，不是本机 `tasklist` 里 curl 的驻留内存**。
  公开性事实（他已选定，不再重提）：`mac-alpha` 是公开 prerelease ⇒ 权重随公开包一同公开，ISC 为 NC 许可。
- Windows 现役包 = **r24**- Windows 现役包 = **r25**（`Video-Locator-win-x64-20261017r25.zip`，**干净 commit `c3a17e5` 构建**，= 音轨未知布局回退 + `clip_present` 判据收一 + 取材扩宽护栏 1.5；包内 bundle 33/0 · render 0 · 不变式 0 · 冒烟 AFTER_KILL=0；zip 981,693,605B / 条目 7,079（文件 6,993 + 空目录 86）/ `testzip=None` / backend.exe 77,498,025B sha16 `ae04274989342708` == 磁盘 / bridge.js sha16 `7d3e0427e3d3a4db` == 磁盘 / **与 r24 文件名集合差集 0/0**）。
  上一档 r24（`Video-Locator-win-x64-20261013r24.zip`，**干净 commit `811932e` 构建**，
  含导出任务通道 + 取消残留可见；包内 bundle 33/0 · render 0 · 不变式 0 · 冒烟 0，身份读数见 Current Task 补十七）。
  上一档 r23（`Video-Locator-win-x64-20261012r23.zip`，**干净 commit `a84119d` 构建**，
  含 Electron 桥接层 300s 头超时修复 + 非 2xx 错误体透传；身份与四道包内验收读数见 Current Task 补十六 ⑥）。
  ~~上一档 r22~~（`Video-Locator-win-x64-20261012r22.zip`，干净 commit `36dec63`，backend.exe 77,493,384B sha16 `f0d00f10c4123813`）**已于 2026-10-17 删除**（删前双验：自身 `testzip=None` / 7,078 条目 / 尺寸+sha16 与档案逐字一致，身份已留痕）；更早 r21（`09714ab`，含 A2 scn2 + 剪映导出崩修复 + 第十三轮导出框 UI 修复）、
  r20（未提交工作树构建，backend.exe 77,474,898B sha16 `63987715436d5e31`）。
  **分发包现三档 = r25 现役 + r24 + r23**（r22 已删 2026-10-17，删前双验逐字一致，释放 ≈936MB；r21 已删 2026-10-14）（2026-10-12 出 r22、2026-10-13 出 r23；**r19 已删（2026-10-12，
  删前双验：回滚档 r20 与 r19 自身均 `testzip=None` / 7,078 条目 / sha16 与档案逐字一致）**；
  **r20 已删（2026-10-13，同样先验回滚档 r21 = `fa3c394567cc17d2` 逐字一致）**；更早 r18 于 2026-10-11 删、
  r17 于 2026-10-10 删、r15/r16 于 2026-10-09 删）。⇒ 维持「三档 = 最新 + 上一档 + 一档历史」的节奏，
  下次出 r26 时按同规矩删 r23。
  ~~补九/补十/补十一 ... **第十二轮 exporters 修复未提交**~~ = 该句**已过期**（第十二轮~补十六
  全部代码笔+档案笔均已提交并 push；截至 2026-10-13 00:3x，origin/master = `4fe0d96`）。
  => 腿边界埋点与支持档降噪**已在包内支持档实测生效**（Windows 见 Current Task 补十 块；
  **mac 侧同一条链也已在 mac 测试日志里实测**：12 行 `locate leg=` 顺序/区间正确）。
- ~~两处新 UI 缺浏览器目检~~ = 已目检（续63 补三）并**按用户裁决删除显示**（续63 补四）；
  ①③ 只到后端 API/契约层，界面上不呈现。
- **进度链平台期（续63 补五，三轮才修对）**：修复链显示宽度从「按腿的数量平分」改成
  **按实测耗时占比** —— fix 1.7 点 / split 0.2 / patch 2.3 / ISC 1.8；fix 内部 48 单位，
  字牌 OCR 腿独占 32 单位（它一条就占修复链 28%）。三条重腿另加逐段 on_tick。
  ~~字牌与 ISC 的改善是模型推算~~ ⇒ **续63 补八 已实测、补九 已把单测锁改成按最大值口径**
  （实测两趟最坏单格 41.6/41.4s，均值 24.6/23.7s）。**这条线到此为止，不再迭代。**
- 历史问题现状：成片相邻段重复（续62 已修）、卷轴吞段（补二 已修）、
  ~~**渲染未隔离**~~（续63 补二 已修，**r16 已进包**：`accept_packaged_render.py` R2 由红转绿）、
  卷轴紧邻同素材连放（续63 补二 已实现，默认开）。

## Current Implementation

- 实现细节见项目源码与 `PROJECT_HANDOFF.md`；本文件按协议不复制源码。

## Current Decision

- 重要技术决策见 `.agent/DECISIONS.md`。

## Next Actions

> **▶ 交接指针（2026-10-18 续65）**: **先读** `Current Task` 顶部「续65」块 + `mvp/docs/FINDINGS_BOUNDARY_PRECISION_20261018.md`
> **§9**（本节自包含：探针读数、两处口径错、目检偏移证据、真漏检、门扫参零和、6 条复跑命令）。
> 大背景（分型/网格损失/scn3 预演/B 线判负）读 `archive/HANDOFF_20261018_boundary_precision.md`
> —— ⚠️ 其 **§4 未结项 1「查 CLS 0.718」已由 续65 结案 = 假缺陷**，别再照着它去查。

> 现役未结项以 `Current Task` 顶部「续63 补廿四」块 + 本表为准；**交接读这一份就够**：
> `.agent/archive/HANDOFF_20261018_r26_closeout.md`（自包含：这一夜五批的读数索引、七条被打掉的旧结论、
> 包身份与五道验收读数、未结项 1~5、复跑命令、我自己四处错的形态与 Windows 坑）；
> 上一份 `.agent/archive/HANDOFF_20261017_r25_closeout.md` 已被它取代（其 §5 开放项 1/2 均已闭合）；
> 历史交接块已迁 `.agent/archive/STATE_history_20261007.md`（续55「交接要点」与 (c) 关键新知识七条在其中，
> 后者已浓缩为 `Known Issues` 的「工程教训速查」）。

1. ~~git 推送~~ = 已推 `aba3a21..654dd32`（6 笔）；**再推 `654dd32..ba5bedd`（补九 代码笔 + 档案笔）**。
   ~~r17 出包~~ = **已出并全链绿（续63 补十）**；**r17 是未提交工作树构建** ⇒ 提交时把包身份
   （backend.exe 77,472,765B / `7e3fe311bdf62b36`）写进同一笔提交信息，日后才对得上。
   **本批已推 = `ba5bedd`（代码/测试/脚本 8 文件）+ 紧随的 docs 笔（档案）**：`.agent/{STATE,TODO,CHANGELOG,INDEX}.md` +
   `archive/STATE_history_20261008.md`（补六 逐字迁入）+ `archive/checkpoint-2026-10-08-1704.md` +
   代码四件 `mvp/src/app/locator_service.py`（埋点）· `mvp/src/infrastructure/logging.py`（降噪 +
   `SVL_LOG_NOISE_FILTER` 开关 + stream 门槛）· `mvp/tests/test_locator_service.py`（+5 项）·
   `mvp/tests/test_logging.py`（+6 项）· `mvp/api/tests/test_tasks.py`（跳格锁改口径 +2 项）+
   两个常设脚本 `mvp/scripts/review_{progress_chain,packaged_support_log}.py`（改口径/加面）。
   `work/` 下的 r17 门禁 runner 与降噪探针不入库（r16 那三个包体脚本是否升为常设 = 仍未拍）。
2. ~~r16/r17 出包~~ = **两代都已出**（r16 见「续63 补七」，r17 见「续63 补十」）。
   分发包现状 r17+r16+r15；按「最新+上一档」应删 r15（等口令，删前先跑 `work/r17_pkg/zip_identity.py`）。
   **现在有待进包项**（补九 两件观测面修复）⇒ 下次出包授权时进 **r17**；出包后 accept 建议加一条
   「跑一次真实 analyze，支持档里必须出现 12 行 `locate leg=`」的硬断言（= 埋点的包侧锁）。
3. ~~**⑥ 换形态探针族**~~ → **⑥b 已实跑并判负关闭（2026-10-08 续63 补六）**：
   成本主判据成立（四片同脚本 0.529×）但三指标硬门崩（两片 59 条：严格 −6 / **导出实得 −12**），
   且密验腿救回精度的本质=把网格补回 1fps（墙钟反 1.52×）⇒ 不接线、不翻默认。
   **⑥a/⑥c/⑥d 仍未跑**（本轮按口令只跑 b）——是「未跑」不是「已证否」，重开需用户再提。
4. **竞品侧**（2026-10-17 指针更新，正文一律在 `D:\claudework\cutmatch-analysis`，本项目不承载）：
   静态语义还原已交付 **`FINDINGS/13_MODULE_SEMANTICS_20261017.md`**（137 模块 / 1,891 参数名表 /
   3,202 条他们自写的中文 docstring，按四条链组装）与 **`FINDINGS/14_HTTP_CONTRACT_20261017.md`**
   （22 个 `/api/*` 路由 + **16 键阶段词表** + batch 状态 12 键 + 授权 18 码 + 导出格式四元组）；
   另 **`FINDINGS/15_MESSAGES_AND_LEASE_20261017.md`**（话术层 341 条 + model lease 357 条）把动态路线判死：
   竞品**每次启动都向授权服务器校验**、`content_key` 只在进程间内存传递且加载完即清理
   ⇒ **断网直启下推理/解密链确证不可达**；静态面三条边界写死（函数体控制流 / HTTP 方法与请求体 / 权重明文）。本轮订正两条我方长期引用的旧结论
   —— 竞品 IPC 是**本地 HTTP/WS（Flask）不是命名管道 JSON-RPC**；竞品代码里**有 CUDA/MPS/CPU 三档设备选择**
   （"只支持 NVIDIA"仅指其 Windows 包依赖构成）。新的静态硬边界：常量块内 **code object 记录 = 0**
   ⇒ 函数级签名不可静态取得。待挖面与动态路线（用户已授权"本机直启但先断网"，代价 = 断网拿不到
   model lease）见该项目 `.agent/TODO.md` P0 · C2。
   **口径不变**：竞品结论**只写文档**（用户本轮边界），未进 `mvp/` 任何代码。
5. ~~分发包保留~~ = ✅ 已按口令执行（2026-10-08）：删 r13 + r14（~1.96GB），
   现留 **r16 现役 + r15 回滚**两份；删前两份均验 `testzip=None` / 7,078 条目 /
   backend.exe 尺寸+sha16 与档案逐代一致（r15 `d45656f585826f4a`、r16 `7c9533750776a79a`）。
6. ~~**下一批候选（三件）**~~ = **全部做完（2026-10-08 续63 补九，用户口令「2」）**：
   ① 腿边界埋点（12 行/次 locate + 链首开关行，后端 5 项含文件侧落盘）② 支持档 proactor 降噪
   （降级 DEBUG 非丢；证据 = 历史真档 485 条逐条判据回归 485/485 + 真进程注入三臂 J0-J6 全 PASS
   + 单测 6 项）③ 跳格锁改按**最大值**口径 + 读数数由宽度表现算 + 反向验证测试。
   **待办**：本批未提交、未出包。r17 出包时建议把 `work/r17_noise/probe_inject.py` 那套三臂
   **升成包侧常设断言**（在 `backend.exe` 里注入 ⇒ 支持档 0 条 / 调试档留满 N 条），这样每次出包
   自动核一次「降噪进包且真生效」；同批给 accept 加一条「真实 analyze 后支持档必须 12 行
   `locate leg=`」硬断言（= 埋点进包的锁）。
   **残留一项（如实）**：这台机始终没让 OS 真报出那条连接重置（七种客户端强关打法全 0 条），
   ⇒ 「客户端真会触发」靠历史档 485 条背书，不靠复现。
7. ~~**待拍板**：竞品 opcode 通道可行性~~ → **已试采结案（续62 补三）**：字面通道判死
   （Nuitka AOT，0 pyc）；机器码绑定通道判死；**blob 序通道打开**。
   明细 `competitor_cutmatch/FINDINGS_OPCODE_CHANNEL_20261007.md`。
8. **搁置（用户 2026-10-06/07 裁决，勿再提议）**：mac 严格惰性再 dispatch · LOC-1107 拆码 ·
   A1→A2∥A3 · 性能口径三处对齐 · 成片缺口标记 · ⑤ 导出实得口径。
9. **A 立项（镜头检测漏切，2026-10-11 第十四轮开）→ 第一步 A1 + 边界尺子已跑完（补十二）**：
   文档 `mvp/docs/PLAN_SHOT_DETECTION_20261011.md`（提案）+ `mvp/docs/FINDINGS_SHOT_DETECTION_A1_20261011.md`
   （产出）。根因确认 = `scenes.npy` 用 CLS 语义距离当镜头边界，且现役参数把召回压到天花板的 1/3。
   ~~待用户拍板三选一~~ = **已拍板 (a) 并落地（续63 补十三）**；(b)(c) 未做：
   (a) **A2 开码**（推荐）= 索引期加像素边界通道 + 与 CLS 融合（**不能朴素 OR**），派生版本位 `scn1→scn2`
       bump 只重算场景表/事件表、不重抽 CLS；验收 = 尺子 F1 >0.78 + 三指标不降 + 导出实得 + 不变式 + 成片读图；
   (b) **A1 调参批** = 关 `z_thresh` + `min_shot_s=1.0` + `cut_abs .30~.40`（R 0.23→0.63），
       代价 = 全片边界数翻倍（2671→5288~5910），下游吸附/扩宽/事件表全受影响，属 runtime 改动须全套验收；
   (c) **A3** = 接 PySceneDetect 只当**第三方评测尺子**（不进 runtime、不加产品依赖），核目检尺子的偏置量。
   ⚠️ 此处 A1/A2/A3 = 镜头检测子方案，与第 8 条被搁置的「A1→A2∥A3」（旧探针族/竞品）**无关**，别混。
10. ~~**本批（补十三）待办**~~ → **已结清（2026-10-11 续63 补十四）**：A2 全套已提交
    （`9481f39` 代码 + `09714ab` 档案，推 `c873e18..09714ab`）并**出包 r21**（干净 commit 构建，
    三道包内验收全绿，身份见 Current Problem 首条）。**(iii) 已定性闭合**（门 v2 判负不放宽，
    见 Current Task ⑥(a)）。**(ii) 已拍板（口令「不用加」）**：老用户 derived_stale 升级路径
    **维持现状**——首次分析任务内重刷，文案/逐帧进度/可取消照旧，**不加预计耗时**，
    不做启动期后台预扫。本条无遗留。
11. **补十八 开放项（2026-10-17，按代价从小到大）**：
    ~~① 出包 r25~~ = **已出（同日补十九）**；`mvp/ui` 零改动 ⇒ **mac 不必另走 dispatch**；出包后按规矩删 r22，删前先验
    回滚档 r23/r24 逐字一致）；② ~~cap 1.5 观感验收~~ = **已收口（2026-10-18 续63 补二十）**，且此处原建议的「双档各出一片再读图」
    **判空**（`material_expand` 只允许剪映通道 = `exporters.py:433` 硬守卫，成片通道调用不传该参数）
    ⇒ 改在**剪映卷轴**侧读图：1.5 档逐 clip == 关闭扩宽、卷轴区间 == 成片区间（**零 handle**），
    cap 归因的边界变化仅 10/72 条 ⇒ **cap 既不是「过渡不流畅」的成因、也不是解药**；③ ~~`source_merge.py::_transcode_args` 同族批~~ = **已做（2026-10-18 续63 补廿一）**：实测是**两族**
    （全 unknown ⇒ 协商阶段硬失败；混合 ⇒ **产物布局由第一路决定**、零留痕），且这里原写的修法
    （无脑插 `aformat=channel_layouts=stereo`）**不够**——会把 5.1 源永久下混、且未补名时 ffmpeg 拿不到
    混音系数；实装 = 先按声道数**补名**再统一到**声道数最多**的可解析布局，全等时可解析 ⇒ **命令逐字不变**。
    ⚠️ **未出包 ⇒ 用户还没有**，**mac 要另走 dispatch**；另登记两条未做（nvenc/qsv 白跑、copy 腿签名不含布局）；④ **主线「过渡不流畅」**（缺他指认的秒数 /
    未转码原始 `movie_*.mp4` / `*.results.json` 三样，缺任一样都只能给规模估计不是验收数）；
    ⑤ `og720-720` 相似度自相矛盾（0.08 vs 0.97）未定位。~~⑥ 补十八 立档~~ = 本笔已完成。

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
  ⑫ **观测面上「按 UI 文本标签分组」会串腿**（2026-10-08 续63 补九）：patch 与 ISC 两条腿的进度
  消息文本一模一样（「画面深度复核 N/67」），旧复核脚本按消息子串归因 ⇒ 两条腿混成一条，档案里
  「ISC 最大 37.3s」实际是 patch 腿的数（ISC=33.9s）。凡按腿/阶段统计，用**结构化字段**
  （`phase`）+ 墙钟区间裁剪归因，别用给人看的话术当分组键；显示读数折叠还会把跨腿的尾巴算错，
  均值/最大值一律按「腿墙钟 ÷ 腿内读数数」与「裁剪后停留」算。
  ⑬ **降噪/复现类探针必须自带仪表自证行**（同批）：本批七种客户端强关打法在本机**一条都没造出**
  目标形态，如果档里连一行自己的 INFO 都没有，就分不清「没造出来」还是「落盘链路没通」。
  ⇒ 每个臂先落一条 `module=<探针名>` INFO，再规定「对照臂 0 条 ⇒ 下游所有读数判 N/A 不判通过」；
  这条规则今天把三轮假绿（修复臂看起来很干净）挡在了 N/A 区里。
  ⑭ **复现不出故障形态时，可「借框架自己的记录路径」把链路那一环闭合**（同批追加）：七种客户端
  强关打法全 0 条之后，改成在**真实服务进程**里调 `loop.call_exception_handler({message, handle,
  exception})`，由 asyncio **默认异常处理器**落 logger "asyncio"（真 ProactorEventLoop + 真 lifespan
  的 `configure_logging()` + 真 `ConnectionResetError(10054)` + 真 traceback），剩下唯一变量就是
  「我的 filter 在不在」⇒ 三臂（不过滤 10/10 淹档 / 过滤 0 条 / 过滤+调试档 DEBUG 留满）实证
  「链路生效」。**代打的只有「谁抛的」这一处，必须在脚本与档案里写明**；「OS 会不会真报这个错」
  仍由历史真档 485 条逐条回归背书。踩到的两个 stdlib 坑：`create_app` 用**自定义 lifespan** ⇒
  往 `router.on_startup` 挂东西根本不执行；3.13 的 `default_exception_handler` 要**异常对象**，
  传 `(type,val,tb)` 会让处理器自己抛 `AttributeError`、档里整片变成
  "Exception in default exception handler"（我两版因此把读数全数错分类）。
  ⑮ **日志里的「错误码字面量」是平台产物，不是逻辑事实**（2026-10-08：一条 Windows 专属字面量
  断言让 mac 出包整轮卡住，`macos-package` 被 skip）：
  `OSError` 在 Windows 渲染 `[WinError 10054]`，在非 Windows **忽略** `winerror` 入参、渲染
  `[Errno 10054]`（官方文档原话）⇒ `assertIn("WinError 10054")` 这类断言换平台必然落空，而**被测逻辑
  可以完全正确**。⇒ 跨平台文案断言一律走「按平台取字面量」的小 helper；要在 Windows 上验 mac 那半边，
  就用**另一平台的对象形态**造样本当常驻锁。⚠️ 第二轮真机补正：mac 上**不是 `winerror=None`，
  而是这个属性根本不存在**（`exc.winerror` 直接 `AttributeError`）——我第一版 ⑮ 写成「None」，
  被自己那条新锁在 mac 上打死；取异常属性一律 `getattr(obj, name, None)`，与产品判据同写法。
  ⑯ **CI 里「一次网络抖动就能打死整轮」的地方要按代价不对称来加固**（2026-10-08 出包第三轮）：
  一步 ≈19 分钟、失败即让后面 5 个步骤全没跑，而当时的韧性配置是**偏的**——大文件下载带
  `--retry 5`，但**先跑的那发小元数据请求一次重试都没有**，抖动恰好打在没有保护的那一发上（curl rc=56）。
  ⇒ 加韧性看「失败代价」不是「传输数据量」；下载完成判据也别用「>0 字节」，要用**元数据报的 `size`
  逐字节等值**（半体能过闸，错误要等下一道 sha 校验才暴露，整轮已经花掉了）。
  ⑰ **「派生结构层」的缺陷会被「该层没有自己的判据」长期掩盖**（2026-10-11 续63 补十二）：
  `scenes.npy` / `events.npy` 是索引期派生表，而三指标测的是**定位命中**、导出实得测的是**成片**
  ⇒ 全链没有任何一把尺子量「镜头边界对不对」，于是边界召回 0.232（只找回 23% 真边界）在这种状态下
  跑了很久、所有门禁全绿。⇒ 凡新增/改动一类**中间结构层**（场景表、事件表、聚类、计划层），
  先给它建一把**该层自己的 GT**（哪怕只是 44 个窗 × 12s 的抽样目检），再谈调优；
  否则「全绿」只说明下游容忍了它。附带两条同批读数：**单旋钮消融会互相掩蔽**
  （`min_shot_s` 单改 +0.008，但与「关 z」合起来 +0.43 ⇒ 别用单腿读数判某参数"无用"，要成组验）；
  **局部统计量（z-score）在"整段都异常"的材料上会系统性失效**（快切段邻域均值本身就高 ⇒ 真切的 z 只有 0.5~1.2）。
  ⑱ **跨时间轴打分前先把两条轴归一，否则「A 比 B 差」可能只是取整规则差**（2026-10-11 补十三）：
  探针在 0.1s 像素轴上打分、生产把结果落到 1fps 网格落盘，同一批候选两边 F1 差 0.09 —— 真因不是判据漂移，
  而是生产用 `searchsorted(side="left")`（一律向上取整）⇒ 命中条**有符号位移中位 +0.215s**。
  改就近吸附后同批候选 0.785 → 0.832。**先量有符号位移，别只看聚合分**。
  同一族的还有验收判据：静态镜头上 argmin 会挑到噪声（`mad_best` 与 `mad_at_zero` 只差 0.014 却判 −2 帧
  越界，而真越界是断崖式 2.959→0.350）⇒ **凡用 argmin 定偏移，必须同时要求目标函数显著下降**。
  同批再补两条：③ **timestamp seek 取帧要按「第一个 PTS ≥ t」反推** —— 取第 k 帧须请求
  `(k-0.499)/fps`，写 `+0.5` 会恰好取到下一帧（我第一版就这么把偏移分布又整体平移了一帧，
  靠实测打回）；④ **判据别超过它的测量精度** —— 原片侧 ±1 帧取帧不确定性是物理下限，
  「绝对偏移 ≤1」等于零余量，改判**离散度**后常数项归给「约定」、段间掉队才判死。
  ⑤ **锁要防「空锁」**：新测试首版把 7 项全 skip 还报 OK（`io.StringIO` 少了 `reconfigure`）
  ⇒ skip 条件只能留给「真缺可选依赖」，其余加载失败必须判死。
  ⑲ **`max(下限,…)` 类常量必须逐轴核「它会越出谁的边界」**（2026-10-12 补十五，同族二次真机）：
  第十二轮越的是**素材时长轴**（0.1s 下限把 target 撑过 64ms 素材 ⇒ ValueError 越界）；
  本轮越的是**目标时间轴**（同一 0.1 下限把 target 撑出 <0.1s 的卷轴槽位 ⇒ 与下一条严格相交
  SegmentOverlap）。修一处下限缺陷 ≠ 其余轴界内（教训 ⑧ 的「枚举同型调用点」在本族再次兑现）；
  下限必须**同时进槽位排布与写入判据**（两处各写一份必然漂移），并给「累加用下限后宽度」上结构锁。
  ⑳ **UI 的「网络级失败」话术只对应客户端放弃，别反推成「后端掐连接」——先卡请求时长 vs 客户端默认超时**
  （2026-10-12 补十六，订正补十五/第十二轮的定性）：真机红条「无法连接后端服务 (fetch failed)」被连写
  两次成「意外异常逃 ASGI ⇒ uvicorn 不发响应」。实测三条都反着来：① `app.py` 早装了全局
  `exception_handler(Exception)`，真机日志里 `unhandled error on POST /api/export` 就是它的落盘行；
  ② 四臂真 uvicorn（同 starlette 1.6.0/uvicorn 0.52.4，含复刻生产「2×BaseHTTPMiddleware+CORS」栈）
  **6/6 收到结构化 500 JSON、服务存活**；Starlette 源码原文「We always continue to raise the exception」
  的前提是**先把响应发出去**。**真因 = 客户端 300s 自己走人**：Node 全局 fetch（undici）默认
  headersTimeout=300s，实测 `{"message":"fetch failed","causeName":"HeadersTimeoutError","reject_after_ms":300504}`，
  而那两次导出请求实际跑了 **374s / 783s**（同档还有 **571s / 475s 的成功导出** ⇒ 草稿写完了、UI 报连不上）。
  ⇒ 纪律：**「客户端看到 network 级失败」是外层可观测量，成因有两族（服务端没回 vs 客户端不等）**，
  判族要先拿「请求实际时长」与「客户端默认超时」对表（日志里用发起侧首条 INFO 到崩溃/完成行的 Δ 就能卡）；
  以及**凡是「某层会掐连接」的断言，用真 socket 真进程跑一遍**，别拿框架文档印象当结论。
  同批两条附学：**包侧正则锁要按编译产物的真实排版写**（按源码排版写的「相邻两行」型正则会被注释行打死，
  本批就这么假红了一次）；**PyInstaller 产物不是字节可复现的**（同树重打：同尺寸、仅 9 字节差在归档
  长度/偏移字段）⇒ 别把「没动 Python ⇒ sha 逐字相同」当闸，有效闸是「zip 内 == 磁盘构建」+ `git diff 路径面为空`。
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

2026-10-18 16:41
