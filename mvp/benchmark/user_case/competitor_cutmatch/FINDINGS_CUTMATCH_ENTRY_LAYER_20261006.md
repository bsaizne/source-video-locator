# FINDINGS — 竞品入口/资源层整值读完（2026-10-06 续60 后续）

> **触发**：续60 会话清点发现续37「竞品全量重挖」的 `KEEP` 只覆盖 `cutmatch.matching` +
> `exporting.segments/timing`（9,850 值 / 26.6%），第一方另有 **10,721 值 / 74 模块从未读**
> （`work/cm_redig/inventory_20261006.md`）。本档 = 把入口/资源层 17 模块 3,634 值整值读完的总账。
> **方法**：`work/cm_redig/dump_entry.py` → 逐值 `work/cm_redig/entry/<module>.txt` +
> 可读视图 `work/cm_redig/entry_view_20261006.md`（数值 / 结构化对象 / 长文本三段）。
> 引证格式 = `view:行号`（指 `entry_view_20261006.md`）。纪律不变：只读 Nuitka 常量池，
> **不运行竞品、不碰授权与受保护模型**；读不到指令序列（opcode），故本档只陈述"存在什么旗标/结构"，
> 不推断分支顺序。
> **零 `mvp/src` 改动，`feature_version` 零变更。**

## 0. 结论（三句）

1. **精度侧仍然没肉**：入口层不含任何新的打分/锚定/门控机制，与续37 总账一致。
2. **工程/UX/售后侧有 9 条可落地形态**，且其中 4 条正好对着我方已登记但未做的待办
   （大文件鲁棒性四件、UX-P1 进度、UI-P3 徽标误标、mac 包中文路径）。
3. **续37 那句"竞品侧已无可挖的精度杠杆"在它自己范围内成立**（matching 整族 58 模块全覆盖），
   但"竞品侧已空"不成立——本次一次性补出了 9 条。

## 1. 口径类（把反推变成直证）

| 项 | 证据 | 意义 |
|---|---|---|
| 竞品默认 `matching_mode = "standard"` | view:308, 861, 930, 933（`{"matching_mode": "standard"}` 出现在默认 dict、state 默认快照、single 参数默认） | 续37 总账第 22 行的"竞品默认 = standard 精确管线"此前是从 matching 内部常量**反推**，现入口层**直证** |
| `matching_v2_options` + `normalize_matching_mode` 在入口层归一后透传 | view:538, 553, 723, 734, 860 | 我方 config 的对应物 = `pipeline.*` 旋钮组；竞品把"模式→具体选项"的展开放在 web 层，不在算法层 |
| `use_proxy` / `xml_only` / `merge_gap` / `concat_mode` 都是**调用方可传参数** | view:553（默认 dict `num_workers=8, merge_gap=20, matching_mode=standard`）, 656, 659, 660, 862 | 我方 `merge_gap` 对应物（同镜合并/`consecutive_offsets`）**没有可配面**；竞品默认 20（单位 = 帧，配合 `timeline_frame_count` 语境，view:543） |

## 2. 九条可落地形态（按对我方的价值排）

1. **代理视频 = 720p + 帧精确门禁 + 默认关**
   `generate_proxy_video` / `is_proxy_frame_accurate`（view:870, 915-916, 920）；话术链
   「已开启 720p 视频加速，正在检查加速素材…」（876）→「正在生成 720p 代理视频…」（882）→
   「720p 代理生成完成」（884）/「原视频已是 720p 或更低，无需代理」（885）；processor 侧
   「使用 720p 代理视频加速 V2 分析」（view:534）；`use_proxy` 默认 **false**（656）。
   ⇒ 对我方「大文件鲁棒性四件 · CFR 代理」：竞品的成立条件不是"生成代理"，而是
   **生成后校验代理是否帧精确**，不精确就回退原片——我方此前没做这一步，直接上代理会引入切点漂移。
2. **内存收缩 batch（我方 memmap 项的竞品形态）**
   `memory_safety` 全链 varnames：`requested_batch_size / frame_width / frame_height /
   raw_frame_bytes / inflight_batch_count / estimated_per_frame / reserve / usable /
   memory_batch_size / max_prefetch_batches / available_bytes / limited_by_system_memory`
   （view:372-373, 391）；读 Windows `GlobalMemoryStatusEx` + `SC_PHYS_PAGES/SC_AVPHYS_PAGES`
   （376, 380-381, 389）；**13 条 OOM 文本族**含中文「页面文件太小」「虚拟内存不足」「内存不足」、
   `winerror 1455`、`errno 12`（384）；`low_memory_mode` + `fallback_stage` 作为状态字段上报
   （705, 707, 755, 789, 930）。
   ⇒ 竞品做法 = **按可用内存同时收缩 batch 与预取批数**，并把"当前处于低内存档"显示给用户；
   我方停滞看门狗/memmap 立项时应对齐这个可观测面（不是静默降载）。
3. **设备确认 = 子进程打标记行**（对 UI-P3 徽标误标）
   正则 `\x1eCUTMATCH_DEVICE_CONFIRM=([a-z0-9_]+)\x1e`（view:366）+ backend→厂商映射
   `cuda/nvenc/h264_nvenc→nvidia · qsv→intel · amf→amd · mps/metal/videotoolbox→apple`
   （367）+ `software/libx264/libx265/cpu`（368）+ `split_device_confirmation`（275, 463）。
   ⇒ 我方侧栏徽标误标的根因是"配置意图当实际后端"；竞品是**让真正干活的子进程回报它用的设备**，
   UI 只显示回报值。这是可直接移植的形态（非算法）。
4. **进度防抖 + 心跳**（对 UX-P1「后处理零进度上报，92% 卡感」）
   `stage_delay_seconds` / `delayed_stages` / `_make_stage_delay_progress_callback`
   （view:872, 905, 937-946）+ `heartbeat` 字段（768, 930）+ `progress_updated_at`（928）。
   ⇒ 竞品对**会一闪而过的阶段**做延迟发布（避免进度条跳档噪声），同时用 heartbeat 证明"还在动"。
   我方续40 只解决了"有消息"，没解决"该压的阶段压一压"。
5. **客服错误码 = 一码一因 + 双段话术**（对我方 LOC-1107 的处置）
   `MEM-001 / GPU-001 / GPU-002 / DISK-001 / DISK-002 / MEDIA-001 / **MEDIA-002** / AUTH-001 /
   NET-001 / COMP-001 / PROC-001`，每条 = 现象 + 建议（view:787），其中
   **MEDIA-002 =「素材无法正常读取」→「请确认素材可以正常播放，必要时重新复制或导出后重试」**；
   另有 16 内部阶段 → 7 客户阶段的映射表（788）与 `contains_sensitive_detail` /
   `public_error_message` / `customer_error_details` 三层脱敏（784, 804）。
   ⇒ 我方现在是**一个 LOC-1107 覆盖所有 ffmpeg/ffprobe 失败**（`MediaError` 单一 user_message，
   `mvp/src/media/ffmpeg/_runner.py:39-40`），把"片尾越界""文件损坏""被占用"混成一句话术。
   本次修的 bug 恰好证明这三类需要分开——建议后续按竞品形态拆码（`errors.py` 码规则=只增不改）。
6. **合并三模式 + 输出校验**（对多原片合并的产品口径）
   `FOLDER_CONCAT_MODE_MKVTOOLNIX_LOSSLESS` / `FOLDER_CONCAT_MODE_SMART` /
   `DEFAULT_FOLDER_CONCAT_MODE` + `select_folder_concat_mode`（view:903, 892）；
   `validate_concat_output`（834）；音频图 `aresample=48000:async=1:first_pts=0` +
   `aformat=...:channel_layouts=stereo` + `alimiter=limit=0.97:latency=1`（959）；
   视频 `force_original_aspect_ratio=decrease:force_divisible_by=2`（958）；
   拼接超时 600s（488）与话术「拼接超时（超过1小时）」（445）；
   一致性指纹 = `codec_name/profile/extradata_hash/pix_fmt/time_base/sample_aspect_ratio/
   color_space/color_transfer/color_primaries/color_range/rotation`（413）；
   10bit/HDR 分支 `p010` + `arib-std-b67/smpte2084` + `bt2020`（429-431）。
   ⇒ 我方 `source_merge` 移植时对齐了"能不能合"，**没对齐 extradata_hash/三属性一致判定**
   这一层，且没有"超时后校验输出单调/时长一致"的门。
7. **ETA 标定表（可直接复用的数字）**
   16 阶段 + 预算秒（view:277-292）与分档吞吐 `gpu/cpu`（302-303、303 续表）：
   `source_scene 220/75`、`source_features 30/8`、`source_probes 40/18`、`matching_path 80/30`、
   `source_refine 1.2/0.4`、`commentary_refine 1.5/0.5`、`matching_dtw 40/15`、
   `matching_review 20/6`（单位 = 帧/秒或秒/单位由其 `seconds_per_unit` 键定，view:248）。
   ⇒ 两点：① 竞品把 **精排吞吐标到 1.2 fps(GPU)**，与我方续55 实测"CPU 抓帧 78% / DML 18%"
   同向，佐证瓶颈在解码不在推理；② 竞品有 `source_probes` 与 `matching_dtw` **两个我方无对应物**
   的阶段（我方 probe 融在宽扫、无 DTW），这是阶段结构差异，不是精度差异。
   历史标定文件 `AUTOCLIP_PROGRESS_HISTORY_PATH` + `median` + `fixed_seconds`（239, 245, 274）
   ⇒ 竞品的 ETA 会**按本机历史中位数**收敛，我方 ETA 是静态拟合。
8. **低内存/快速档的用户可见降级**
   `fast_summary`（169, 734, 917）+ `low_memory_mode` + `xml_only`（863-864：`single` 请求里
   带 `xml_only`，且 processor 有「生成 XML」独立阶段 view:539、state 阶段名含
   「合并视频/索引构建/生成 XML/匹配帧/生成代理」931）。
   ⇒ 竞品**"只出 XML 不渲染"是一等公民开关**。我方挂着未决的「竞品渲染失败仍出 XML」语义，
   本次证据显示它更可能是"用户可选模式"而非"失败兜底"——口径拍板时按这个方向问产品。
9. **macOS 打包的中文路径坑（对刚出的 mac 包直接相关）**
   `runtime.tools` docstring 原文（view:960-963）：「macOS 打包后从 Finder 启动时，默认 locale
   可能不是 UTF-8；显式指定编码可避免 ffmpeg/ffprobe 输出中文路径、中文元数据时触发 ASCII 解码错误。」
   ⇒ 我方 mac artifact（run #23 `video-locator-mac-arm64`）**没做过这条检查**；接 H3 真机冒烟时
   第一件就该验"中文路径 + Finder 启动"。

## 3. 我方待办的对账结果（谁已被竞品回答）

| 我方登记项 | 竞品形态 | 结论 |
|---|---|---|
| 大文件鲁棒性四件（CFR 代理 / memmap / 停滞看门狗 / 独立 GPU 工作进程） | §2.1 代理帧精确门禁、§2.2 内存收缩 batch+预取 | 前两件**已有可移植形态**；看门狗与独立工作进程仍无竞品证据 |
| UX-P1 后处理阶段零进度上报 | §2.4 延迟发布 + heartbeat | 有形态，值得做（纯 UI/进度层，不动语义） |
| UI-P3 侧栏后端徽标 CPU 误标 | §2.3 子进程回报设备标记 | 有形态，且是根因级解法 |
| 「竞品渲染失败仍出 XML」语义未复刻 | §2.8 `xml_only` 是入口开关 | **口径要重问**：竞品是模式不是兜底 |
| 入库层四件（盘符浏览/自然排序/白名单/磁盘预检） | `discover_folder_videos` + `free_space/required_space`（view:809） | 磁盘预检竞品也在做，形态一致 |

## 4. 仍未穷尽的通道（诚实留白）

- **指令序列（opcode）读不到**：本层证据全部来自常量池，所以"竞品在什么顺序上调用这些旗标"
  仍是未知。这一条限制了 §2 全部结论的形态强度——**能证明"有什么"，不能证明"先做哪个"**。
- 未读的第一方剩余模块 = `cutmatch.web.file_api.*`（上传/下载 UI）、`cutmatch.desktop.*`、
  `cutmatch.licensing.*`（本次只读到入口层引用到的 `model_lease` 线索）、`cutmatch.diagnostics.*`
  本体。它们与定位精度无关，但 §2.6/§2.8 若要移植需回读 `desktop` 侧。
- `model_lease` 首轮口头猜测为"GPU 模型占用治理"是**错的**：入口层证据（view:844-849）显示它是
  **授权租约**（`verified_model_lease` / `reason=missing_model_lease` / 话术「V2 模型授权租约缺失，
  无法开始处理。」）。此处按"说错即更正"留痕。

## 5. 产物索引

- 清点：`work/cm_redig/inventory_prefixes.py` → `inventory_20261006.md` / `.json`
- 整值转储：`work/cm_redig/dump_entry.py` → `work/cm_redig/entry/<module>.txt`（17 模块 3,634 值）
  + 可读视图 `work/cm_redig/entry_view_20261006.md`（数值 132 / 结构化对象去重 970→约 780 行 / 长文本 11）
