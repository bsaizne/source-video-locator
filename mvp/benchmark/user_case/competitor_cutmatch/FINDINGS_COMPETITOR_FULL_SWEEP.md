# FINDINGS — CutMatch 逆向数据最终全量扫穿（282 blob + 1563 键目录 + 943 键 profile 对账）

> 输入：`work/full_sweep_blobs.txt`（282 个 Nuitka 常量 blob 全量摘要，已完整读取）；
> `cutmatch-analysis/data/cutmatch_option_catalog.json`（1563 键 / 4101 出现位）；
> `cutmatch-analysis/data/competitor_profile_v1.json`（943 键）。
> 对照基线：FINDINGS_DOCSTRING_BREAKTHROUGH / CUTMATCH_POSTPROCESS_REPLAY / CAPABILITY_GAP + 目录内其余 21 份 FINDINGS/REVIEW 文档。
> 日期：2026-09-27。证据分级：**字节级确证**（blob 偏移+值可复现）/ **docstring 语义**（中文 docstring 原文）/ **推断**。

---

## 1. 完整性矩阵（按竞品自有模块族）

blob 区段拓扑：#0–#115 + #253–#280 为第三方库；#116–#252 为竞品自有代码（全部含中文 docstring，语义全可读）；#281 为内嵌桌面资源。

| 模块族 | blob（编号区间 / 数量） | 语义可读度 | 已挖（既有 FINDINGS） | 本轮新增 |
|---|---|---|---|---|
| **desktop/激活与安全** | #117–#127（11） | docstring 全可读 | 部分（CAPABILITY_GAP 提及授权存在） | 激活/授权体系全貌：AC-/AC2- 双代码、回环 HTTP 激活会话、Legacy/V2 双客户端、`401AutoClip` 配置目录名、15 个授权失败 reason 码（§2-A） |
| **diagnostics** | #128–#131（4） | 全可读 | 无 | `.cmlog` 加密诊断日志完整格式（P-256+HKDF+AES-256-GCM 帧）、stdout/stderr 全接管脱敏、客服错误编号族（§2-B） |
| **exporting** | #132–#142（11） | 全可读 | G7 输出粒度（部分） | 短镜头兜底展开、变速补齐 speed_fill 90–110%、ASCII 媒体别名、真实转场切点展开记录、黑场空档渲染+帧数校验（§2-C/E） |
| **licensing** | #143–#154（12） | 全可读 | 无 | 设备指纹采集链（PS→WMIC/ioreg/machine-id）、V2 设备密钥（TPM/Secure Enclave）、Ed25519 验签、模型租约解封（§2-A） |
| **matching/alignment** | #155–#160（6） | 全可读 | G5/G6 + BREAKTHROUGH §1/§2/§9（**已挖尽**） | 仅统计字段名族（dtw 回退原因枚举 17 个）；无新算法语义 |
| **matching/fast_timeline** | #169–#178（10，含 options/runner） | 全可读 | G5 §1c/1d、BREAKTHROUGH §2 | 机制层已挖尽；本轮补齐**参数值**：ordered_search 全 18 键、path_* 全 8 键、confidence 四权重、A1/A2 分镜复核全 20 键（§2-D，重点） |
| **matching/feature_extraction** | #179–#185（7） | 全可读 | G1/G3（模型/特征面） | 隔离子进程推理监督（60–90s 自适应超时）、批次缓冲池、显存二分拆批（§2-F） |
| **matching/feature_index** | #186–#194（9） | 全可读 | G3/G4 + PATCH_FUSION | 缓存内容指纹+事务化低内存存储形态、FAISS IndexFlatIP+macOS OpenMP 避让、patch top-16-token 平均公式的函数级确证（§2-F） |
| **matching/pipeline** | #195–#204（10） | 全可读 | G5/G6 + BOUNDARY_REFINER_COMPARISON | 验证门退化判据（max_duplicate_scene_ratio=0.8）、respect_source_scene_end=false、结果模型锚点合并/变速补齐语义（§2-E） |
| **scene_detection** | #205–#212（8） | 全可读 | TRANSNETV2_SEGMENTATION（48x27 已确证） | 100 帧滑窗/50 帧步长、预测缓存、TF→TensorRuntime 权重自动转换、场景模型授权租约强制、显存档位自适应批次（§2-G） |
| **processing** | #213–#223（11） | 全可读 | 无 | 串行批量协调、进度 tracker 阶段全集 23 个、拼接 HEVC 编码器链+HDR 检测+1h 超时（§2-H，低优先） |
| **runtime/resources** | #224–#230（7） | 全可读 | 部分（代理/工具路径） | 受保护资源 AES-GCM 格式、编译期发行配置"缺失拒绝启动"、smoke 自检（§2-H，低优先） |
| **web/api** | #231–#252（22） | 全可读 | 无 | 分块上传、720p 代理帧号校验、受控删除清单（原片永不删）、授权阶段延迟心跳（§2-H，低优先） |
| **第三方库** | #0–#115、#253–#280（144） | 无竞品语义 | — | cffi/click/cryptography/colorama/packaging/janus 等常量；#10 为中文字符频率表（输入法/编码用）；#253–#280 为小空 __init__ 常量块 |
| **desktop_build_assets** | #281（705KB） | 无 | — | Nuitka 编译期内嵌 Tauri 资源，仅 1 条字符串，无算法语义 |

---

## 2. 本轮新发现清单（此前 FINDINGS 未记载）

### A. 授权/激活体系全貌（docstring 语义，低优先·产品行为）
- **A1 产品原代号 `401AutoClip`**：#144 `返回当前操作系统中保存授权状态的 401AutoClip 配置目录` —— 竞品内部/前身产品名首次出土。
- **A2 双代激活码**：#117 `AC-... 或 AC2-...`；`这是旧版激活码，请使用旧版客户端或更换 AC2 激活码`。激活走本机回环 HTTP（随机端口 + 一次性 session token + HttpOnly cookie 门禁，#117/#126/#127）。
- **A3 设备指纹链**（#144，docstring）：Windows 采 MachineGuid/CPU/主板/BIOS/系统UUID/磁盘序列号（PowerShell 优先、WMIC 回退）；macOS ioreg；Linux machine-id/DMI。V1 salt SHA-256 兼容指纹 + V2 逐组件摘要档案。
- **A4 V2 授权**（#145/#150/#151/#153/#154，docstring）：Ed25519 授权响应验签（排序紧凑 JSON 为签名材料，核对 nonce+设备指纹）；设备密钥 = macOS Secure Enclave/Keychain helper、Windows TPM 优先回退 Software KSP（NCrypt，CNG ECCPUBLICBLOB）；模型租约 = ECDH P-256 解封内容密钥，绑定设备+时效。
- **A5 15 个授权失败 reason 码**（字节级，catalog：licensing.client.legacy + desktop.tauri_backend）：`device_limit / rate_limited / revoked / expired / hardware_mismatch / hardware_incomplete / missing_device_key / device_key_mismatch / legacy_client_required / v2_client_required / unsupported_client_build / not_activated / unknown_license / license_network_error / license_proxy_error`。
- **A6 授权协议内部版本**：#147 `授权协议共享常量；值必须与 V4 基线保持一致` —— 当前发行是 V4 基线 + V2 安全客户端双轨。

### B. 诊断日志加密格式 `.cmlog`（docstring 语义，#128–#130）
- 混合加密：客户端只持 P-256 公钥，后台持私钥；文件头 ECDH 包装会话密钥（HKDF-SHA256，文件标识作盐）；正文逐帧 AES-256-GCM，记录 AAD 含大端帧序号 → **可检测篡改/截断/重排**。
- 客户模式写加密 `.cmlog`，密钥异常降级为"安全摘要"明文，绝不向处理线程抛异常。
- stdout/stderr 被完全接管：只记录"出现过输出"这一事实，原始载荷不进客户日志（#120）；技术术语替换+绝对路径隐藏（#130）。
- **客服错误编号族**（字节级，catalog diagnostics）：`AUTH-001 / COMP-001 / DISK-001 / DISK-002 / GPU-001 / GPU-002 / MEDIA-001 / MEDIA-002 / MEM-001 / NET-001 / PROC-001`。

### C. 导出/渲染层补充（docstring 语义，#134–#142）
- **C1 变速补齐 speed_fill**（字节级确证值）：precise `speed_fill_enabled=true, min_percent=90.0, max_percent=110.0` —— 片段时间线缺口用 ≤±10% 变速填充（#199 `结果模型变速补齐：在允许速度范围内扩展锚点片段的时间线长度`），而非黑场。
- **C2 短镜头兜底展开**：#176 `在短镜头兜底切点处展开为两个无缝的一倍速导出片段`。
- **C3 剪映兼容 ASCII 别名**：#134 为非 ASCII 媒体路径生成稳定英文名并在输出目录创建别名；FCPXML rational seconds（如 100/24s）。
- **C4 真实转场切点展开**：#162 `记录需要在剪映和 Premiere 时间线展开的真实转场切点`（快速模式边界保护产出）。
- **C5 渲染校验**：#138 逐片段帧数校验（`帧数错误: 第 N 段预期 X，实际 Y`）、黑场空档+静音轨渲染、硬件编码失败自动回退软件、FFmpeg 无进展超时监控。

### D. 快速模式参数值补齐（字节级确证，blob 0x174bb2ea = #172 options）——**本轮最高价值**
采纳文档（FINDINGS_CUTMATCH_CONSTANTS_ADOPTION）曾判定"N1 ordered_search_* / N4 path_* / A1-A2 dual/visual/structure/motion/flash 仍未绑定"；**本轮在 profile_v1 fast_options 中全部确证绑定**（94 键全量镜像）：
- **D1 confidence 公式权重**：`confidence_coarse_weight=0.3 / confidence_consistency_weight=0.2 / confidence_local_weight=0.4 / confidence_margin_weight=0.1 / min_confidence_score=0.6`。与 #168 `按采样、偏移支持、局部一致性和候选差距给出稳定置信度结论` 对应 —— 置信公式从"输入面"升级为**完整带权公式**。
- **D2 path_* 路径 DP 目标函数**：`path_local_weight=0.55 / path_coarse_weight=0.2 / path_consistency_weight=0.2 / path_support_weight=0.05 / path_backward_max_penalty=0.05 / path_transition_max_penalty=0.12 / path_transition_grace_seconds=2.0 / path_refine_radius_seconds=0.35`。与 #160 时间线镜头选路/逐帧转移评分 docstring 对应 —— BREAKTHROUGH §1d 的目标函数从此有完整系数。
- **D3 ordered_search_* 顺序检索门**（#173）：`enabled=true / window=300s / chunk=315s / backtrack=15s / expand=900s / max=1800s / lock_segments=3 / candidate_margin=0.03 / coarse_min_score=0.55 / coarse_min_support_ratio=0.35 / consistency_min_score=0.55 / refined_min_score=0.62 / context_seconds=2.0`。机制（主线锁定）已挖，**参数全集为新增**。
- **D4 A1/A2 分镜复核家族**（#167 SceneRuntime 双预测复核）：`dual_single_min=0.02 / dual_many_min=0.04 / dual_combined_min=0.08 / flash_luminance_min=0.78 / flash_luminance_jump_min=0.2 / motion_ecc_similarity_max=0.8 / motion_histogram_distance_max=0.2 / structure_distance_min=0.42 / structure_strong_distance=0.85 / visual_score_min=0.15 / visual_strong_score_min=0.2 / visual_peak_ratio_min=1.35 / visual_context_frames=3 / move_radius_frames=16 / snap_radius_frames=4 / prediction_support_radius=2 / min_side_frames=8 / max_additions_per_segment=4 / descriptor=48x27（与 SceneEngine 同尺寸）`。
- **D5 其余新绑定**：`balanced_alignment_enabled=false（默认关闭！）/ balanced_coarse_sample_fps=5.0 / balanced_local_sample_fps=10.0 / balanced_top_regions=3 / balanced_local_refine_margin=0.03 / balanced_region_radius_seconds=0.2 / actual_refine_min_score_gain=0.01 / actual_refine_query_count=3 / frame_refine_query_count=5 / frame_refine_radius_seconds=0.2 / leading_score_gain_threshold=0.03 / recovery_candidate_count=10 / recovery_local_score_threshold=0.45 / recovery_neighbor_disagreement_seconds=1.0 / dense_early_weight=1.5 / dense_anchor_disagreement_seconds=0.1 / algorithm_version='fast-timeline-v2' / cache_schema_version=1`。
- ⚠️ 保留采纳文档的告警：`ordered_search_max_seconds` 等键邻域是 `balanced_*` 限定名，属"默认 profile 还是 balanced profile"需运行期验证——但 `balanced_alignment_enabled=false` 表明 balanced 是**非默认支路**，上值大概率即默认值（推断级归属，值本身字节级）。
- precise 侧同样新绑定：`respect_source_scene_end=false / max_duplicate_scene_ratio=0.8 / patch_score_workers=2 / offset_refine_candidate_tolerance_frames=2 / low_memory_mode=false / deep_model='runtime_vision_vits14'`。

### E. 匹配管线验证门与结果模型（docstring，#196–#204）
- **E1 退化拒绝判据**：#201 `V2 镜头路径退化：大量解说镜头匹配到相同原片位置 (重复率 X)，已停止` + 字节确证 `max_duplicate_scene_ratio=0.8`；`respect_source_scene_end=false`（按 scene boundary 拆分输出片段默认**关闭**，#197 有该逻辑但默认不启用）。
- **E2 锚点合并**：#199 结果模型把"同一源镜头内连续且兼容的锚点片段组"压缩为保持总时长的单一片段（含组连接判定/边界拆分/转场保护帧跳过条件）。
- **E3 边界校正细节**（#204）：入点校正比较 start-1/start、start/start+1、start+1/start+2 三段帧差，仅后移一帧，`source_boundary_refine_max_shift=2`（已有对比文档，本轮补 `source_boundary_guard_frames=0` 默认关闭）。

### F. 特征索引/检索层（docstring，#179–#194）
- **F1 patch 公式函数级确证**：#193 `取每个查询 token 的最佳源相似度，再平均最多十六个最高值` + `应用固定 top-token 聚合公式` —— PATCH_FUSION_PROBE 的推断形态获得 docstring 直证（16 = max_patch_tokens 聚合上限，与 512 token/场景不同层）。
- **F2 检索后端策略**：#193 FAISS `IndexFlatIP`；`NumPy fallback（macOS 避免 FAISS/OpenMP 冲突）` —— macOS 上显式不用 FAISS；`按强制启用、强制禁用和平台默认优先级决定是否尝试 FAISS`。
- **F3 缓存健壮性形态**：#186 内容指纹 = 文件大小 + 首中尾抽样 SHA-256 → 十位摘要；metadata 全量比对（缓存版本/源指纹/视频参数/选项）并产出**精确未命中原因**；#194 低内存存储 = 10 个正式数据文件 + 同目录 tmp/backup 事务提交（失败回滚）；#190 memmap + 帧/patch LRU 按需组装。
- **F4 隔离推理监督**（#181/#184）：DINO 推理在 spawn 子进程；等待时间按上一批耗时自适应、**钳制在 60–90s**；显存不足递归二分拆批并收紧安全批次上限、成功后逐步恢复吞吐。

### G. 场景检测层（docstring，#205–#212）
- **G1 滑窗形态**：#206 `生成 SceneRuntime 滑动窗口，每个形状为 [100, 27, 48, 3]` + 50 帧步长窗口计数 —— TransNetV2 推理批形态（100 帧窗口）为本轮新确证细节。
- **G2 预测缓存**：#208 以内容指纹命名、存两组浮点预测数组（帧级+切点级）、原子替换。
- **G3 场景模型也走授权租约**：#211 `当前发行包必须通过授权租约加载受保护场景模型`；TF SavedModel → TensorRuntime 权重首次自动转换。
- **G4 显存档位自适应批次**（#212）：`memory_tier_plan` 按总/空闲显存给（初始批次、上限、保留量、增长阶梯）；失败减半、一窗口连续失败抛 `BatchRetryExhausted`；按历史单窗口吞吐估算批次超时。

### H. 产品/工程行为（低优先登记，docstring）
- 拼接（#221/#240）：MKV 全集→mkvmerge 无损优先，失败回退智能合并；HEVC 硬件链 nvenc/qsv/amf/videotoolbox→libx265 CRF18 兜底；HDR（PQ/HLG/BT.2020）→p010le；总时长>1h 超时终止；输出时长/音轨完整性校验（#131）。
- 上传（#244/#239）：分块上传（会话 ID ≤128 字符白名单）；磁盘预留 = max(内容×2%, 512MiB)。
- 代理（#251）：720p 代理 + 代理帧号一致性验证，不可靠即重建。
- 一次性处理令牌（#121）：TTL 环境变量、下限 1s、默认 180s；绑定授权+模型租约+阶段延迟元数据。
- 打包自检（#123）：冻结运行时启动时探测 torch/媒体工具/场景模型/特征模型，结果写环境变量路径（0/1）。
- 发行安全（#228）：编译期安全配置（通道/构建号/验签开关）缺失即拒绝启动。
- 进度阶段全集（字节级，tracker #217）：`原片分析/解说分析/索引构建/原片整理/解说精排/原片精排/时间匹配/路径匹配/匹配复查/候选复查/DTW offset 精排/长镜头局部召回准备/镜头切割完成/路径选择完成/合并视频/生成 XML/…` 共 23 个客户可见阶段名。

---

## 3. option_catalog 键族对账（1563 键）

- 顶层结构：1563 个键 = 常量名；4101 个出现位分布在 124 个模块。竞品自有（`cutmatch.*`）60 个模块、**644 个唯一键**；其余为第三方库（cffi 为主）。
- **自有配置键已 100% 镜像进 profile_v1**：fast_options 94 键 = fast_timeline.options 全集；precise_options 61 键 = pipeline.options 全集；另有 retrieval / strictness_maps / scene_detection / feature_extraction 等节。→ 目录与 profile 无"漏采键"，只存在"未被 FINDINGS 记载键"。
- **从未被任何 FINDINGS 记载过的自有键族**（名字+作用+确证状态）：
  1. `speed_fill_*`（3 键）— 锚点缺口 ±10% 变速补齐；字节级确证（90/110）。
  2. `confidence_*`（5 键）— 快速置信四输入加权公式；字节级确证。
  3. `path_*`（8 键）— 快速路径 DP 目标函数系数；字节级确证（采纳文档原判 N4 未绑定，本轮推翻）。
  4. `ordered_search_*`（18 键中 15 个此前未登记）— 长视频顺序检索门；字节级确证（N1 同上推翻）。
  5. `commentary_scene_*`（20 键）— fast 分镜复核双预测门（A1/A2 家族）；字节级确证。
  6. `algorithm_version='fast-timeline-v2'` / `cache_schema_version=1` — 版本锚点；字节级确证。
  7. `respect_source_scene_end=false` / `max_duplicate_scene_ratio=0.8` / `patch_score_workers=2` / `offset_refine_candidate_tolerance_frames=2` / `balanced_alignment_enabled=false` — 默认开关面；字节级确证。
  8. 非配置键族（新登记，字节级）：15 授权 reason 码、11 客服错误编号、16 编码器/设备标识（h264|hevc × nvenc|qsv|amf|videotoolbox + mps/metal）、23 tracker 阶段名。
- profile_v1 自身推断级项（对照提示）：`retrieval.patch_top_k=100`、`global_weight=0.45` 仍标"强推断"（值被去重/邻域歧义），与 G3 结论一致，未升级。

## 4. 挖穿宣告：数据段已挖穿

- **139 个中文 docstring blob = #116–#252 全部竞品自有代码，语义 100% 可读、100% 已扫**；既有 6 个关键 blob 的挖出内容与本轮扫描对账无遗漏（alignment/fast_timeline 机制层在 BREAKTHROUGH 已挖尽，本轮仅补参数值）。
- **无语义 blob 全部定界**：#0–#115+#253–#280（144 个）为第三方库（cffi/cffi.model 类型表占大头）或空 `__init__` 常量块；#10 为中文字符频率表；#281 为 705KB 内嵌 Tauri 资源（仅 1 条字符串）。无加密/不可读的竞品自有内容。
- **剩余价值 = 0**（就"数据段还有什么没读"而言）。唯一遗留不确定点：①常量绑定是否为运行期默认值（字节只能证明"常量池存在该落点"，采纳文档 B 类告警仍有效）；②`patch_top_k`/`global_weight` 两值仍属强推断。两者需运行期/动态验证，静态数据段无法再推进。

## 5. 对我方项目的可行动项（按价值排序）

1. **采纳快速路径 DP 完整系数**（D2）：`local 0.55 / coarse 0.2 / consistency 0.2 / support 0.05 / 倒退罚 0.05 / 转场罚 0.12(宽限 2s)` —— G5 机制我方已立项，系数可直接对拍；字节级确证。
2. **采纳置信四权重公式**（D1）：`0.3/0.2/0.4/0.1，门限 0.6` —— 低置信片段标记与"避免闪烁视频"验证门同构；字节级确证。
3. **speed_fill ±10% 变速补齐**（C1）：锚点缺口用轻微变速而非黑场/截断，用户感知收益最大；字节级确证（90/110）。
4. **ordered_search 长视频顺序检索门**（D3）：我方长场景检索无顺序主线锁定；参数全集（300s 窗口/15s 回退/900s 扩展/1800s 上限/锁 3 段）可作探针初值；字节级确证，profile 归属为推断。
5. **patch top-16-token 聚合公式**（F1）：我方 patch 融合若按均值/最大值聚合，应实测"每 token 最佳→取最高 16 个再平均"；docstring 直证。
6. **缓存未命中原因+内容指纹事务化**（F3）：首中尾 SHA-256 指纹、metadata 全量比对并输出精确原因 —— 直接提升我方缓存可诊断性；docstring 语义。
7. **显存档位自适应批次**（G4）：增长阶梯+失败减半+吞吐超时估计，匹配我方 DirectML 管线的稳定性需求；docstring 语义（档位数值未见，仅机制）。
8. **max_duplicate_scene_ratio=0.8 退化拒绝门**（E1）：我方结果验证缺"重复源位置退化"判据，一行可加；字节级确证。
