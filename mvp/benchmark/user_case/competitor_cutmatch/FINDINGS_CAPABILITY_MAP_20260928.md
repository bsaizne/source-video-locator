# 竞品 137 模块 × 我方实现 全量对齐表（2026-09-28）

> **GT 版本**（2026-10-01 补登记，批量执行）：不适用——竞品 103 叶子模块能力对照 + 我方实现映射；文内引用我方基线 117/139 为当时口径，文内引用的旧基线属当时现役口径、现已过时，引用数字须注明口径代际（现行基线见 .agent/STATE.md）。

> **为什么有这份文档**：此前我方对竞品的认知全部经过 `FINDINGS_*.md` 的「可行动项」小节这一层过滤，
> 而竞品逆向工作区 `D:\claudework\cutmatch-analysis` 里的 `FINDINGS/01~08`（安装器/技术栈/模型保护/
> 开放问题/模型识别）与 `data/cutmatch_module_map.txt`（137 模块权威枚举）**从未被逐一对齐过**。
> 用户质疑「是不是漏了功能没接入」后补做本表。判据 = 我方代码里有无对应实现（文件:行），
> 不是"文档提过"。
>
> **定级纪律**：竞品能力来自静态逆向（不运行其程序），标注「确证级别」；
> 「缺失」不等于「应该做」——本表只负责让决策有据，取舍见文末与 `.agent/TODO.md` 续15/续16。

## 表 A · 模块族对齐（竞品 137 模块按族聚合）

| 竞品模块族 | 干什么 | 我方对应 | 判定 |
|---|---|---|---|
| `matching.scene_detection.*`（6，TransNetV2 切分+边界精修+监督） | 学习式场景切分 | `engine/segment/segment.py` + `flash_guard.py` + `card_guard.py`（两级像素切分+白闪/卡片守卫） | **部分**（学习式切分已实测 A1 −16 不接入） |
| `matching.feature_index.*`（10，索引/存储/检索/相似/local_matcher） | 原片特征库 | `engine/feature_store/`、`retrieval/`、`localization/patch_rerank.py` | 已覆盖 |
| `matching.fast_timeline.*`（17，粗检索→密集对齐→局部精修→路径选择→置信） | 主匹配流水线 | `candidates.py` + `localization/{finloc,evidence_localize,dense_start_check,offset_vote_prior}.py` + `ranking/` + `confidence/` | 已覆盖（形态不同） |
| `matching.alignment.*`（dtw/geometry/offset_refiner/continuity/timeline） | 对齐链 | `seq_align.py` / `temporal_repair.py`；**`geometry`（AKAZE/ORB 单应）我方全无**（grep akaze/homography = 0） | 部分 |
| `matching.router`（`matching_mode='standard'` 三态） | 快/精模式路由 | **无**（config 无 mode 概念） | **缺失** |
| `matching.results.*`（models/serialization/validation） | 结果模型 + 校验门 | `domain/models.py`、`results_repo`、`IndexValidation`；**退化拒绝门已实现但实测否决维持默认关**（续19/续31），安全形态 = LOC-2002 重复认领告警默认开 | 部分 |
| `exporting.segments.builder` / `timing.video_timing` | 片段计划 + 帧/时码换算 | `app/exporters.py:93 build_export_plan`、`:223 seconds_to_frames`、`:230 timecode_ndf` | 已覆盖 |
| `exporting.jianying.fcpxml_generator` | 剪映草稿 | `exporters.py:553/568/494` | 部分（**无 C3 非 ASCII 路径别名**） |
| `exporting.premiere.xml_generator`（audio_rate 48000 / channels 2） | PR 工程 | `exporters.py:318 render_fcp7_xml` + `:268 render_edl`；**XML 无音频轨**（grep audio = 0） | 部分 |
| `exporting.rendering.video_renderer` | **真渲染 + 逐段帧数校验 + 硬编失败回退软件** | **无** | **缺失** |
| `processing.video.concat`（34 键，竞品最大非算法键族） | 原片/解说无损合并（mkvmerge/HEVC 链/HDR/>1h 超时/输出校验） | **无**（`extract_clip` 只裁） | **缺失** |
| `processing.jobs.batch`（`authorize_one`/`run_one`/`generation`） | 批量任务协调 | **无**（`api/tasks/manager.py` 单任务） | **缺失** |
| `processing.progress.tracker`（23 客户可见阶段 + heartbeat + eta） | 进度可见性 | `ProgressStage` 仅 7 阶段、零中文话术层 | 部分 |
| `processing.resources.device_events`（16 编码器/后端标识） | 推理 + **编码**设备探测 | `device/{cpu,directml,mps}_backend.py`；无编码器探测 | 部分 |
| `processing.resources.memory_safety`（`low_memory_mode`） | 低内存保护 | **无** | **缺失** |
| `web.application.native_picker` | 原生文件对话框 | `ui/electron/main.ts:66,77` | 已覆盖 |
| `web.file_api.*`（分块上传/下载/浏览） | 素材入库 | 仅 `routes/preview.py` 媒体服务 | 缺失（我方本地直读，**不必做**） |
| `web.processing_api.*`（state/batch/diagnostics） | 任务态/批量/诊断 | `routes/{tasks,progress,logs}.py`；无 batch/diagnostics | 部分 |
| `web.license_api` / `desktop.activation` / `desktop.security` | 授权与安全 | **无** | 缺失（商业化时再做） |
| `desktop.{tauri_backend,tauri_protocol,tauri_web_server}` | UI↔后端壳（**命名管道 JSON-RPC**） | `ui/electron/backend/*` + FastAPI HTTP/WS | 已覆盖（架构不同，等价能力） |
| `desktop.logging` / `shutdown` / `smoke` | 日志/进程清理/**依赖逐项自检** | `infrastructure/logging.py` + `main.ts:198` + `/api/health` | 部分（无自检） |
| `diagnostics.*`（crypto/manager/public_messages） | 加密日志 + **11 客服错误编号** + 文案 | `infrastructure/errors.py`（8 类，无编号/无脱敏） | 部分 |
| `licensing.*`（Ed25519 验签 + TPM/Secure Enclave + 模型租约） | 授权体系 | **无** | 缺失（商业化项） |
| `runtime.protected_assets`（AES-GCM 模型加密） | 模型保护 | **无**（明文 pth/ONNX；A1 后至少有 sha256 完整性校验） | 缺失 |
| `runtime.{paths,resources,tools,release_profile}` | 路径/资源/发行闸门 | `infrastructure/paths.py` + `config.py` | 部分 |

## 表 B · 我方完全无该机制的竞品键族（含"该不该做"判断）

| 键族 | 语义 | 确证级别 | 该做？ |
|---|---|---|---|
| `speed_fill_min/max_percent`=90/110 | 锚点缺口 ±10% **变速补齐**（非黑场/截断） | 字节 | **是**（用户感知最大） |
| `max_duplicate_scene_ratio`=0.8 | 重复源位置退化拒绝门 | 字节 | ~~**是**（一行可加，已批待做）~~ → **已做并结案（续19 实现 + 续31 分腿复测）**：拒识形态实测 严格 −2/场景 −1/负例 ±0 且属掷硬币 ⇒ 维持默认关；安全形态 LOC-2002 只提示不删答案已默认开。依据 `FINDINGS_DEGRADATION_LEGS_AND_DUP_CLAIM_WARN.md` |
| `commentary_scene_*`（20 键） | ED 快速分镜复核（TN 双预测 + ECC 运动校验 + 白闪） | 字节 | ~~是~~ →【2026-09-28 E3 判决探针=负，ECC/结构相关腿与已证伪帧差腿同档，不进 runtime，`FINDINGS_E3_ECC_PROBE.md`】 |
| `boundary_guard` / `_record_boundary_split` | 真实转场切点时间线展开 + 单帧片段守卫 | docstring+字节 | **是**（零指标风险） |
| `h264/hevc_{nvenc,qsv,amf,videotoolbox}` + `hwaccel` | 硬件编码器探测 + 失败回退软件 | 字节 | 若做渲染/合并才需要 |
| `.cmlog` 帧加密 + 11 客服编号 | 可诊断售后日志 | docstring+字节 | **是**（低成本高回报，售后刚需） |
| `low_memory_mode` + `memory_tier_plan` | 显存档位自适应批次 | docstring | **是**（我方 DML 管线痛点） |
| `generation`/`batch_task_generation` | 批量任务代际防串扰 | 字节 | 做批量时再要 |
| 15 授权 reason 码 / `tpm`/`secure_enclave` | 激活失败分类 + 设备密钥 | 字节/docstring | 仅商业化 |
| 分块上传（≤128 白名单）+ 磁盘预留 | 素材入库 | docstring | **否**（本地直读架构不需要） |
| `release_profile` 缺失即拒启 | 编译期发行安全闸门 | docstring | 否（但值得借鉴思路） |

## 表 C · 竞品**短板** → 我方反向项（从未被任何 FINDINGS 记载）

逆向过程中发现的竞品质量问题，对我方是**明确的差异化要求**，此前只写在 `cutmatch-analysis` 侧、
未回流到我方产品档案：

| 竞品短板 | 我方应对 | 证据 |
|---|---|---|
| 全部二进制 **NotSigned**；版本串自相矛盾（V7.1.0 vs 0.1.0）；卸载快捷方式名被混淆串污染 | 我方发布链必须**代码签名 + 版本一致性检查**（mac 侧已踩 ad-hoc 签名坑，见 STATE 2026-09-22） | `FINDINGS/02 §5.4-5.6` |
| 安装期 **deferred CustomAction 以 SYSTEM 权限静默联网下载并执行** PowerShell 拉 WebView2 引导器 | 我方安装器**不得静默联网执行**；依赖应随包分发（静态 ffmpeg 已是这么做的） | `FINDINGS/04 §2.4` |
| 自研包格式 `CUTMATCH_SINGLE_EXE_PACKAGE_V1` 存根逐文件 SHA256 自校验（202 文件清单） | 我方**运行时完整性校验缺失**（A1 已补模型资产 sha256；安装包级清单待评估） | `FINDINGS/03 §2` |
| `torch.load` 无 `weights_only` | 我方三处已补 `weights_only=True`（A1） | `FINDINGS/07 §2.1` |

## 表 D · 103 个叶子模块逐一对齐（穷举，非聚合）

> 权威枚举源 = `cutmatch-analysis/data/cutmatch_module_map.txt`：**137 个 dotted 模块**，其中
> **34 个是包级 `__init__`**（`cutmatch.exporting`、`cutmatch.matching` 等，无自身逻辑），
> **103 个叶子模块**逐个列如下表；另有 2 个叶子（`licensing.client.secure_v2` / `licensing.crypto.secure_v2`）
> 在 blob 语料里无同名条目，语义由 docstring 邻近块与键族推得，已标注。
> 证据列：**D#N** = `work/full_sweep_blobs.txt` 第 N 号 blob 的中文 docstring 原文；**K** = profile_v1 键名+值确证。
> 判定「缺失」≠「应该做」；文末给优先级。

### `desktop.*` + `diagnostics.*`（12）

| 模块 | 竞品语义 | 证据 | 我方对应 | 判定 |
|---|---|---|---|---|
| desktop.activation | 本机激活 HTTP 服务 + Legacy/V2 授权切换 | D | 无 | 缺失（商业化） |
| desktop.downloads | 保存去重编号 + **系统文件管理器揭示结果** | D#119 | `ui/electron/main.ts:61,174 shell.openPath` | 〔复核更正〕**部分**（有 openPath，无唯一名去重） |
| desktop.logging | 脱敏 URL/授权路径/本机绝对路径 | D | `infrastructure/logging.py`（明文轮转，grep redact=0） | 缺失（脱敏） |
| desktop.security | 桌面对话令牌 + 一次性处理令牌 | D | 无 | 缺失（我方本机 HTTP 无鉴权） |
| desktop.shutdown | 停线程 + terminate 全部后代进程 | D | `api/app.py:25`、`process.ts:62` | 部分（无进程树回收） |
| desktop.smoke | 打包依赖/媒体工具/模型逐项自检 | D | `scripts/smoke_*.py`（**dev 脚本，不随包**） | 部分 |
| desktop.tauri_{backend,protocol,web_server} | Tauri2 Sidecar 生命周期/握手/承载 | D | Electron + FastAPI | 不适用（架构不同） |
| desktop.web_server | 授权后本机服务（随机端口 + 令牌门禁） | D | `api/main.py` + `manager.ts` | 部分（无端口随机/门禁） |
| diagnostics.manager | 诊断旁路**有界队列 worker** + CPU/GPU 采样落盘 | D | `api/routes/logs.py:36`（明文 zip） | 部分 |
| diagnostics.public_messages | 阶段/异常 → **稳定中文客服错误码**（11 编号） | D(cjk156) | `infrastructure/errors.py`（8 类，无编号无话术） | 部分 |

### `exporting.*` + `licensing.*`（13）

| 模块 | 竞品语义 | 证据 | 我方对应 | 判定 |
|---|---|---|---|---|
| exporting.jianying.fcpxml_generator | 剪映可导入 FCPXML | D | `exporters.py:470`（写 draft_content，非 FCPXML） | 部分 |
| exporting.premiere.xml_generator | PR FCP-XML + **时间重映射变速** + 近片合并 | D | `exporters.py:318`（`:308` 注释明示不做变速） | 部分 |
| exporting.rendering.video_renderer | **渲拼接成片** + 黑场 + 进度/取消 + 硬编回退 + 逐段帧数校验 | D#138 | 〔2026-09-29 续30 已移植〕`src/media/ffmpeg/timeline_render.py` + `locator_service.render_movie` + `POST /api/tasks/render` + 结果页「渲染成片」；**口径差异**：紧凑拼接（不落地黑场腿）+ 音轨取原片区间 + 中段 PCM（实测结论，见 FINDINGS §3） | ✅ 已落地（真机复核待打包授权） |
| exporting.segments.builder | 导出前**碎片化稳定性告警**（"N 个单帧片段 → 闪烁视频"） | D#139 | `exporters.py:93 build_export_plan` 无该守卫 | **缺失** |
| exporting.timing.video_timing | **有理帧率**避免长视频帧→秒累计误差 + 双 seek | D | 〔2026-09-29 续30〕成片渲染侧已用 `Fraction`（`timeline_render.fps_fraction/fps_text/expected_frames`）；`ffprobe.py:28` 展示路径仍是 float（未改，非缺陷） | 部分 |
| licensing.{client,client.legacy,client.secure_v2,constants,crypto.*,device_keys.*}（8） | Ed25519 验签 + TPM/NCrypt(Win) + Secure Enclave(mac) + P-256 ECDH 模型租约 + 内存解封 | D#145/#149/#150/#153/#154 + **表 F** | 无 | 缺失（商业化；**架构细节见文末表 F，本行原为漏扫**） |

### `matching.*`（41，算法主链）

| 模块族 | 竞品语义要点 | 证据 | 我方对应 | 判定 |
|---|---|---|---|---|
| `alignment.{continuity,dtw,geometry,offset_refiner,timeline}` | 锚点质量决定 TopK-DTW 复查 / 子序列 DTW / AKAZE+RANSAC 单应 / offset 精排回写 / 镜头路径 DP | D#189 等 | `seq_align.py`、`offset_vote_prior.py`、`patch_rerank.py`；**AKAZE 几何全无**（仅 `scripts/research_phase24_1.py:128` 探针，2026-09-01 已证伪关闭） | 部分 |
| `fast_timeline.boundary_guard` | 开头串镜修正 + 尾部跨镜同镜头优先 | D | `segment/{card_guard,flash_guard}.py` | 部分 |
| `fast_timeline.{cache,source_index}` | matching_fast 命名空间缓存 / 原片 1fps 全局索引 + **硬解并行分片 + 预读重叠** | D | `feature_store/`、`engine/common/pipeline.py`（有解码/forward 流水线，**无并行分片**） | 部分 |
| `fast_timeline.capture` | 硬件优先、失败回退 CPU 的视频读取 | D | `ffmpeg_io.py`（grep hwaccel = 0；`scale=` 参数存在但**生产从不调用**） | 部分 |
| `fast_timeline.coarse_retrieval` | 全局相似 + **时间偏移投票**生成候选 | D | `retrieval/` + `offset_vote_prior.py`（已移植，默认关） | 部分 |
| `fast_timeline.commentary_sampler` | 解说 3fps 采样 + 亮度/对比/清晰度**质量权重** | D | `feature_store`（2fps 均匀，无质量权重） | 部分 |
| `fast_timeline.commentary_scenes` | SceneRuntime 双预测低分辨率切点复核 | D | `segment.py`（CLS 余弦两级切分） | 不适用（架构不同；A1 实测替换 −16） |
| `fast_timeline.confidence` | 采样/偏移支持/局部一致性/候选差距四项加权 | K | `engine/confidence/confidence_v2.py` | **已覆盖但实测不移植**（231 段仅 1 段有效降档，见 `FINDINGS_CONF_V2_PORT.md`） |
| `fast_timeline.dense_alignment` | 10fps 密集起点搜索 + 5fps 粗扫两阶段 | D | `dense_start_check.py`（已移植，默认关，实测生产零增益） | 部分 |
| `fast_timeline.local_refiner` | 局部窗口移动起点 + 多帧 patch 精排 | D | `patch_rerank.py` | 部分 |
| `fast_timeline.ordered_search` | 沿已确认位置**增量向后检索** + 主线锁定/解锁 | D#173,K | **无** | ~~**缺失**（机制本体未测，参数全集已绑定）~~ →〔2026-09-29 续28〕**M0 复现判负关闭**：full=102/raw=106/基线=105，顺序性零独家救回（`FINDINGS_ORDERED_SEARCH_M0.md`） |
| `fast_timeline.path_selection` | 邻接候选传播 + DP 压制孤立跳点 | D | `ranking/`（静态排序，无传播 DP） | 部分（DP 下沉已实测 −8 有害） |
| `fast_timeline.performance` | 设备自适应执行计划 + 无副作用性能计数 + 分片 | D | `device/*`、`cpu_backend.py:110` | 部分（无分片并发） |
| `fast_timeline.{results,runner,options}` | 结果模型（含 1 倍速片段）/ 全流程编排 / 选项闭区间规范 | D,K#172 | `domain/models.py`、`locator_service.py`、`config.py` | 部分 |
| `feature_index.{builder,cache,retrieval,sampling,similarity,storage,models,frame_reader,local_matcher}` | 批量提特征写缓存 / **未命中给精确原因** / 长镜头局部 probe / 每场景 5 关键帧 + 长镜头按秒加密 / patch top-16 聚合 + FAISS 后端 / **memmap + 事务提交** / 低内存 memmap store / **读帧停滞看门狗 + 双 worker** | D#185-194 | `feature_store.py:113/279`（**全内存 np.load，无 mmap_mode**）、`edited_cache.py:120`（单文件 os.replace）、`retrieval.py:12`（明确无 FAISS）、`ffmpeg_io.py:57` | 部分；`models`(memmap) 与 `local_matcher`(AKAZE) **缺失** |
| `feature_extraction.{batching,extractor,models,offline_paths,worker}` | CPU 张量 **LIFO 缓冲池** / 显存二分 + global&patch 批量 / 离线权重解析**拒绝联网回退** / **spawn 子进程隔离推理 + 超时终止** | D#179/#184 | `device/base.py`、`cpu_backend.py:21 resolve_dinov2_weights`（env>仓库，无联网回退风险） | 部分；`batching`(缓冲池) 与 `worker`(子进程隔离) **缺失** |
| `matching.router` | 精确 runner 与快速 runner **双路隔离**，非法模式报错 | D#202 | 无（单档） | **缺失**（客户无"秒级预览档"） |
| `pipeline.{options,runner}` | 管线默认选项集中维护 / 分阶段进度编排 | D#196/#197 | `config.py:340`、`locator_service.py:725` | 已覆盖 |
| `results.{models,serialization,validation}` | 锚点拆分/**变速补齐**/重叠修正 / 固定键序序列化 / **候选空或覆盖不足或重复率退化 → 硬停** | D#199-201 | `domain/models.py`、`results_repo.py:28`、`locator_service.py:1306`（降级为"未定位"仍出结果） | 部分（~~`max_duplicate_scene_ratio` 类硬门缺失 = 已批待做项 #8~~ → 续19 已实现、续31 分腿复测后**拒识形态维持默认关**，`min_scene_coverage` 与碎片告警同族；重复认领改由 LOC-2002 提示） |
| `scene_detection.{boundary,boundary_refiner,decode,models,predictions}` | 低分辨率帧差复查漏切 / **入点后移 1 帧**避免上镜尾帧进 XML / 48×27 微缩帧流式解码 / 左闭右开区间 / 阈值→激活组中点 | D#203-210 | `locator_service.py:689`、`exporters.py:178 snap_clips_to_scenes`（±1s 吸附非逐帧差判）、`segment.py:75` | 部分 |
| `scene_detection.{detector,input_preparation,scene_engine_runtime,supervisor}` | 固定 SceneRuntime / **生成低分辨率 CFR 代理避免直读 4K** / 受保护模型多后端加载 + CPU 回退 / **独立 GPU 工作进程监督 + 显存档位自适应批次 + 超时重启** | D#207-212 | `segment.py:120`、**无代理管线**、`device/`（有 CPU 回退，无受保护模型）、**无监督进程** | `input_preparation` 与 `supervisor` **缺失** |

### `processing.*` / `runtime.*` / `web.*` / `v2.device`（37）

| 模块 | 竞品语义 | 证据 | 我方对应 | 判定 |
|---|---|---|---|---|
| processing.jobs.batch | 串行批量协调（≤100 组 + **代次校验进度所有权**） | D#214 | `api/tasks/manager.py:32`（有 `_lock` 但**只护字典**；`submit_analyze` 无并发准入 → 多任务会抢 GPU） | **缺失** |
| processing.progress.tracker | 阶段名归一 + 局部进度区间映射 + **ETA** | D#217 | `routes/progress.py:37`、`app/models.py:15`（7 阶段，无区间/ETA） | 部分 |
| processing.resources.device_events | 给进度打"设备已实际成功"确认标记 | D#219 | `locator_service.py:193 device_settings` fallback 位 | 部分 |
| processing.resources.memory_safety | 系统内存快照 → **自动降批次并向客户说明** | D#220 | `cpu_backend.py:109 memory_info`（仅展示） | 部分 |
| processing.video.concat | **多原片智能拼接**（mkvmerge 无损 / HEVC 硬编链 / HDR p010le / >1h 超时） | D#221,K(34 键) | 无（`ffmpeg_io.py:154` 只裁单段） | **缺失** |
| processing.video.processor | 完整流程产出输出视频 + XML | D#223 | `locator_service.py:1013 export_project`（只出工程不渲片） | 部分 |
| runtime.paths | 项目/运行数据/自带模型/工具根目录 | D#225 | `infrastructure/paths.py:22,41,51` | 已覆盖 |
| runtime.{protected_asset_format,protected_assets} | AES-GCM 版本化受保护资源 + 租约按需解密 + 密钥缓冲清零 | D#226/#227 | 无（明文权重；A1 后至少有 sha256 完整性） | 缺失（商业化） |
| runtime.release_profile | **编译期发行安全配置，缺失即拒启** | D#228 | 无 | 缺失（思路值得借鉴） |
| runtime.resources | 资源清单/大小校验 | D | 无清单级校验（A1 只覆盖模型资产） | 部分 |
| runtime.tools | 打包工具查找 + **隐藏子进程控制台** + UTF-8 解码 + nvidia-smi/WMI GPU 型号 | D#230 | `media/ffmpeg/_runner.py:23,61`（**已有 `CREATE_NO_WINDOW`**〔复核更正〕）；无 GPU 型号探测 | 部分 |
| web.application.{factory,new_factory,main} | 目录配置 + 413/507 中文错误 + 授权门禁 + 静态资源嵌入；并行"新工作台" | D#232-235 | `api/app.py:61`、`api/main.py` | 部分（new_factory 属产品策略） |
| web.application.native_picker | 跨平台系统文件选择 | D#234 | `ui/electron/main.ts:66,77` | 已覆盖 |
| web.blueprints / file_api.routes / processing_api.routes | Blueprint 绑定 | D#236/#243/#250 | `api/app.py:61` | 已覆盖 |
| web.file_api.{browser,common} | 路径校验 + 目录浏览（Windows"此电脑"盘符）+ 扩展名白名单 + 自然排序 + 磁盘预检 | D#238/#239 | 无（UI 直传路径） | **缺失** |
| web.file_api.concat | 拼接 API 层（编码器尝试链/mkvmerge 进度/HDR 判定） | D#240 | 无 | 缺失（随 concat） |
| web.file_api.downloads | **受控删除清单（原片永不删）** + 原生另存为 + 定位文件 + 唯一名 | D#242 | `routes/logs.py:36`（仅日志 zip）+ `shell.openPath` | 部分 |
| web.file_api.uploads | 普通 + 分块上传 | D#244 | 无 | 不适用（本地直读架构） |
| web.license_api.routes | 授权状态接口（有效期/宽限/失败原因） | D#246 | 无 | 缺失（商业化） |
| web.processing_api.{batch,single,state,diagnostics} | 批量校验→串行→逐项授权复核；单任务令牌 + **720p 代理生成校验**；状态唯一所有者 + **200 条环形日志** + 阶段延迟心跳；**客户/支持/调试三级日志 + 路径脱敏** | D#247-252 | `api/tasks/{models,manager,worker}.py`、`routes/{tasks,progress,logs}.py`（无令牌/无代理/无环形上限/无心跳/无脱敏） | 部分 |
| v2.device | V2 设备指纹/标识 | 仅符号名（blob 无同名条目） | 无 | 缺失（商业化） |

## 表 E · 修正记录（子代理/首版结论被本人复核推翻的条目）

| 原结论 | 复核后 | 证据 |
|---|---|---|
| `desktop.downloads` 我方"缺失，档案 0 提及" | **部分**：已有 `shell.openPath` 打开目录 | `ui/electron/main.ts:61,174`、`preload.ts:20` |
| `runtime.tools` 我方"无控制台隐藏" | **已有** `CREATE_NO_WINDOW` 并用于每个子进程 | `src/media/ffmpeg/_runner.py:23,61` |
| `TaskManager` "无互斥，并发会抢 GPU" | 措辞不准：**有 `_lock` 但只护字典**，`submit_analyze` 确无并发准入 ⇒ 结论实质成立 | `api/tasks/manager.py:30,32-38` |
| `ffmpeg_io` "无 scale" | API 有 `scale=` 参数，但**生产路径从不调用**（`src/app`/`src/engine` grep = 0），且 docstring 明示特征路径刻意不缩放 | `ffmpeg_io.py:11,82,132` |
| 「竞品 137 模块全部可比对」 | 其中 **34 个是包级 `__init__`**（无自身逻辑），2 个叶子在 blob 语料无同名条目 ⇒ 真实可逐文件比对 = **101/103** | `data/cutmatch_module_map.txt` + `work/module_blob_index.txt` |
| 〔2026-09-29 销项更正〕表 D `desktop.logging`「缺失（脱敏）, grep redact=0」 | 续19-T1-2 已落地路径/token 脱敏（`redact_text`/`RedactingFilter`/异常格式化），竞品「三级分层视图」仍未做 | `src/infrastructure/logging.py:50-133` |
| 〔2026-09-29 销项更正〕表 D `desktop.security`/`web_server`「我方本机 HTTP 无鉴权」 | 续19-T1-3 已落地发行门禁：`SVL_BUILD_CHANNEL=release` 强制会话令牌（fail-closed，放行清单只增不改）；随机端口未做 | `api/session.py:8,35-40,85`、`ui/electron/main.ts:50`、DECISIONS 2026-09-28 |
| 〔2026-09-29 销项更正〕续17 §3「状态文件 fsync 可补」 | `edited_cache` 已做 fsync+目录 fsync(Windows 静默跳)+原子 replace；`results_repo/settings_repo` 仍普通 write_text | `src/app/edited_cache.py:149-172` vs `infrastructure/results_repo.py:34` |
| 〔2026-09-29 销项更正〕表 D `processing.video.concat`/`web.file_api.concat`「缺失」 | 续27 已移植（物理合并/copy→HEVC 链/HDR/稳定命名缓存/监护；mkvmerge 路由与目录扫描除外），验收=2.mkv 切两半合并后定位逐 ID 零翻转；**续29 UI 入口接线**（Electron `openFiles` 多选桥 + 详情页源片库/立即合并 + 分析页「合并并分析」走 `original_paths`），vitest 118+双 typecheck，真机复核待打包授权 | `src/media/ffmpeg/source_merge.py`、`mvp/ui/src/stores/projects.ts`、`FINDINGS_SOURCE_MERGE_PORT.md`、`work/merge_accept/` |
| 〔2026-09-29 续30 销项〕表 D `exporting.rendering.video_renderer`「缺失」= 差集 TOP1 | **成片渲染已移植并真实验收**：60 段 / 3552 帧 / 148.17s，逐段与终片帧数校验通过、**接缝不规则帧距 0 处**、8 段抽样对齐 ≤1 帧、EDL 与成片同计划、`h264_amf` 硬件编码在位、二次调用命中稳定命名缓存（54.3s→0.2s） | `src/media/ffmpeg/timeline_render.py`、`FINDINGS_VIDEO_RENDER_PORT.md`、`work/render_accept/`、后端 433/API 99/vitest 127 |

## 表 F · 授权体系架构（来源 `D:\dsh-work`，**仅设计要素，不含漏洞利用路径**）

> 我此前完全漏扫 `D:\dsh-work`（竞品授权体系逆向工作区）与第三个路径 `D:\dsh-work` 分析对象
> `D:\cm`（竞品安装后真实程序目录，当前仍在盘上），导致表 D 里 `licensing.*` 8 行只写了
> "缺失（商业化）"一句话。本表按用户 2026-09-28 拍板**只归档架构部分**：
> 攻击路径排序、漏洞清单（V-02~V-07）、内存扫描证据与破解待办**一律不纳入本方档案**。
> 原始出处：`D:\dsh-work\CutMatch_授权体系逆向分析报告.md` §2、`CutMatch_授权逆向_阶段一结论.md` §2。

| 组成 | 竞品做法（可作我方商业化设计参照） |
|---|---|
| 卡密格式 | `AC2-XXXX-…`（V2）与 `AC-XXXX-…`（Legacy）双代际并存，代际由客户端版本决定（返回码含 `v2_client_required`/`legacy_client_required`） |
| 授权服务器 | 编译期 base64 内嵌 URL + 两个端点（`/v1/licenses/activate`、`/v1/licenses/validate`） |
| 签名协议 | **六步顺序校验**：① 服务器签名存在性 → ② 签名版本支持 → ③ 签名算法支持 → ④ 签名有效性 → ⑤ `request_nonce` 匹配（防重放）→ ⑥ 设备指纹匹配；每步有独立错误文案 |
| 签名材料构造 | 移除 `sig` 字段 → 按 key 排序的紧凑 JSON → 作为签名材料（规范化序列化，避免字段序歧义） |
| 验签密钥 | ECDSA **P-256** 公钥（SPKI DER，91 字节），随包内嵌 |
| 设备绑定 | 提供器分层 = TPM(Windows) / Secure Enclave(macOS) / Keychain / software KSP；ECDH 协商共享秘密 + 设备公钥序列化 → 设备指纹 |
| 降级策略 | **已绑定硬件密钥的设备，禁止在无用户确认时降级为软件密钥**（返回码 `hardware_mismatch`/`hardware_incomplete`/`missing_device_key`/`device_key_mismatch`） |
| 授权状态文件 | `%APPDATA%\401AutoClip\{license-v2.json｜license.json}` + `license-v2-early-backup.json`；写入 = 先写 `.candidate-<token_hex>` → `fsync` 文件 → **`fsync` 目录** → 原子 `replace` → `chmod`；读回校验 candidate missing/invalid/mismatch |
| 本机服务门禁 | Flask @ `127.0.0.1:<随机端口>`（bind 探测空闲口）；会话令牌经 URL + `X-Desktop-Session` 头 + Cookie + Origin 四路校验，比较用 `hmac.compare_digest`（常量时间）；另有独立"处理令牌"带 TTL（默认 180s）与 `/_desktop/health` |
| 返回码分类学 | 14 个稳定码（`missing_fields`/`unknown_license`/`revoked`/`expired`/`device_limit`/`not_activated`/`hardware_mismatch`/`hardware_incomplete`/`rate_limited`/`v2_client_required`/`legacy_client_required`/`missing_device_key`/`device_key_mismatch`/`unsupported_client_build`）→ 与我方 `errors.py` 8 类无码可比 |
| 发行闸门 | `ReleaseProfile` 集中五开关：`desktop_gate_required` / `signed_license_required` / `protected_models_required` / `allow_model_path_overrides` / `development_entrypoint_allowed`；设计意图 = **发行包缺编译期安全配置即拒绝启动** |
| 交付物完整性 | `cutmatch-sidecar.manifest.json` = **202 条 `{path, sha256}`**（覆盖根目录 `.pyd/.dll/.exe`）。⚠️ `dsh-work 阶段一 §1` 记的"208 文件"是**错值**，本人实数 `D:\cm\cutmatch-sidecar.manifest.json` → `files len=202`，与 `cutmatch-analysis FINDINGS/03` 一致 |
| 模型保护 | `resources/runtime/a01.bin`(29MB) / `a02.bin`(84MB) = AES-GCM 密文 + `manifest.json`（nonce + 明文/密文 SHA256）；内容密钥走服务器模型租约（P-256 ECDH + HKDF），按需解密且密钥缓冲可清零 |
| 技术栈事实 | 安装包 3.13GB Inno Setup 单文件存根（Go 写）；外壳 Rust/Tauri 2.11.5；业务体 `cutmatch-sidecar.exe` 408MB = **Nuitka 编译的 CPython 3.13**（故无法反编译回 Python）；依赖含 PyTorch+CUDA / OpenCV / Flask / cryptography / **faiss** |

### 对我方的可执行结论（不含竞品弱点细节）

1. **`release_profile` 的"配置缺失即拒启"闸门思路应当现在就借鉴**，不必等商业化：我方 2026-09-22 发生过
   CI 缺 `.env.production` → 整包**静默跑在 Mock 上**、界面恒显"已连接"且分析永不结束（`83c73e1` 修复）。
   这与竞品的 `development_entrypoint_allowed`/发行闸门是同一类问题的同一解法：**构建期配置缺失必须拒启**。
   同类还有 A1 已做的模型资产 `sha256` 校验（对应其 manifest 思路）。
2. **返回码分类学值得照抄结构**（不是抄它的码）：我方 `infrastructure/errors.py` 只有 8 个异常类、
   无稳定对外码、无用户话术 → 与表 D 里 `diagnostics.public_messages`（11 客服编号）缺口合并处理。
3. **状态文件原子写 + fsync 目录**的做法我方 `edited_cache.py:120` 只做了单文件 `os.replace`，
   未 fsync 目录（掉电场景可能留空文件）——低成本可补。
4. **本机服务门禁**（随机端口 + 会话令牌 + 常量时间比较 + 短 TTL 处理令牌）是我方 `api/` 目前完全没有的
   一层：我方 FastAPI 监听本机端口**无任何鉴权**（表 D `desktop.security`/`web_server` 行）。
   单机工具也值得做——同机其他进程可任意调用我们的分析接口并读用户视频路径。
5. 设备指纹 / TPM / Secure Enclave / 模型加密 / 租约 = **真商业化时才需要**，现在不做，但已知其完整形态，
   避免将来从零设计。

## 结论（穷举后的最终差集，按产品价值排序）

1. **成片渲染与导出前守卫**（`exporting.rendering.video_renderer` + `segments.builder` + `results.validation`）——
   竞品能自产合并视频并**在导出前硬停**（"N 个单帧片段 = 会生成闪烁视频"），我方只出时间线工程且降级仍出结果。
   ✅ **成片渲染已移植（2026-09-29 续30）**：`media/ffmpeg/timeline_render.py` + `render_movie` +
   `POST /api/tasks/render` + 结果页入口，真实 2.mkv 60 段验收通过（`FINDINGS_VIDEO_RENDER_PORT.md`）；
   ✅ **单帧片段守卫**已落地（续25 展示层两件套）；
   ✅ 已收口（2026-09-29 续31）= **退化拒绝门**：续19 实现 + 续31 分腿归因（拒识腿单独 = 严格 −2/
   场景 −1/负例 ±0，续19 的 −14 里 test2 −5 实为子 span 腿「整段清空」连带）⇒ 拒识形态维持默认关；
   同构安全形态 **LOC-2002 重复认领告警**（只提示不删答案）已默认开，四片真实导出冒烟 + 逐张读图验收。
   见 `FINDINGS_DEGRADATION_LEGS_AND_DUP_CLAIM_WARN.md`。
2. **多原片合并 `processing.video.concat` + `web.file_api.concat`**（34 键，竞品最大非算法键族）——
   我方只能对单原片建索引，用户给"分集/多段原片"即整体失效。这是**功能边界**缺口，不是优化项。
   ✅ **已闭环（2026-09-29 续27 后端 + 续29 UI 入口）**：入库前物理合并单文件 + 多选原片库/立即合并/
   「合并并分析」；余口径差异=mkvmerge 路由（发行物无 MKVToolNix）、copy 丢字幕轨、目录扫描入库（属⑧入库层）。
3. **大文件鲁棒性与内存墙**（`scene_detection.input_preparation` 低分辨率 CFR 代理 +
   `feature_index.models` memmap store + `frame_reader` 停滞看门狗 + `memory_safety` 自动降批次 +
   `scene_engine_runtime.supervisor` 独立 GPU 工作进程）——
   我方现状：全内存 `np.load`、直读原片、600s 硬超时后失败、DML 崩在主进程内。
   实测参考：128min 档索引峰值 RSS 758MB 尚可，但**定位阶段 1812MB**（`work/bench_perf_tiers.json`）。
4. **售后可诊断性**（`diagnostics.public_messages` 11 客服编号 + `manager` 加密旁路 + `wp.diagnostics` 三级日志与路径脱敏）——
   我方日志直吐明文含本机路径、无错误编号、无脱敏。客诉定位与隐私合规双重缺口，成本相对低。
5. **批量与并发治理**（`processing.jobs.batch` ≤100 组 + 代次校验；`TaskManager` 无并发准入）——
   多任务同交会抢 GPU。
6. **快/精双模式 `matching.router`**——竞品给客户"秒级预览档"，我方单档（首跑 22 分钟对轻度用户是门槛）。
7. **商业化前置**（`licensing.*` 8 项 + `runtime.protected_assets` + `release_profile` + `desktop.security/activation`）——
   已知取舍，非疏漏；但 `release_profile`"配置缺失即拒启"的**闸门思路**值得现在就借鉴（我方 09-22 曾因
   CI 缺 `.env.production` 静默跑在 Mock 上，正是同类缺陷）。
8. **素材入库工具面**（`file_api.browser/common` 盘符浏览 + 自然排序 + 白名单 + 磁盘预检）——
   与已知断链 G4/G7（假数据、无 MediaLibrary 页）同源，可一并解决。

