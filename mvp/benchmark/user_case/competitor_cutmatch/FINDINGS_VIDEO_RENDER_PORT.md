# FINDINGS — 成片渲染移植（竞品 `exporting.rendering.video_renderer`）

日期：2026-09-29（续30）。批次 = 用户拍板「先下批偷向吧」→ 按档案排序取竞品差集 **TOP1 唯一未消化项**。
证据源：`work/full_sweep_blobs.txt` BLOB #138（`cutmatch.exporting.rendering.video_renderer`，
527 常量 / 75 条中文 docstring）+ #139/#140（`exporting.segments.builder` 碎片告警）+
#141/#142（`exporting.timing.video_timing` 帧率换算）+ `competitor_cutmatch/FINDINGS_CAPABILITY_MAP_20260928.md` 表 D/结论。

---

## 1. 竞品形态确证

### 1.1 入口与契约（docstring 原文，确证级）

```
渲染输出视频
    参数:
        source_video: 原片视频路径
        match_data: V2 匹配数据，必须包含 segments
        output_video: 输出视频路径
        output_dir: 输出目录
        progress_callback: 进度回调函数
        check_cancelled: 取消检查函数
    返回:
        成功返回输出路径，失败返回 None
```
+ 模块定位 docstring「阶段4: 视频渲染模块 / 根据匹配结果从原片提取片段并合并」
+ 「V4 输出只接受 Matching V2 生成的 segments」→ 渲染消费**定位结果段**，不接受其它来源。

### 1.2 逐段渲染（字节确证：命令片段常量在位）

| 机制 | 竞品常量/函数名（blob #138） |
| --- | --- |
| 有理帧率 → FFmpeg 分数字符串 | `_rate_text` / `numerator` / `denominator` |
| 单段恒定帧率 + 时长对齐 | `fps=fps=`、`trim=start_frame=`、`:end_frame=`、`:start_time=0:round=near`、`setpts=(…)*N/(…*TB)` |
| 精确 seek 窗口 | `-accurate_seek`、`seek_window_for_frame`、`offset_frames`、`rough_time`、`-ss` |
| 帧数硬上限 | `-frames:v`、`-t` |
| 音频对齐 | `[0:a:0]atrim=start=…:duration=…`、`asetpts=PTS-STARTPTS[a]`、`_audio_speed_filter` + `atempo=`（`.8f`）、`_command_with_progress_output` |
| 黑场空档（我方不落地） | `color=c=black:s=…x…:r=…:d=…`、`anullsrc=channel_layout=…:sample_rate=…`、`_black_audio_layout`（`mono`/`stereo`/`5.1`）、`-c:a pcm_s24le` |
| 进度/监护 | `-progress` `pipe:1`、`-nostats`、`ffmpeg-progress-reader` 线程、`queue.Queue`、`last_progress_at`、`_render_stall_timeout_seconds`、`FFmpeg rendering stalled for %.1f seconds; terminating command`、terminate→wait→kill |
| 编码器回退 | `_run_ffmpeg_with_encoder_fallback`、`software_encoder_command`、`_DISABLED_HARDWARE_ENCODERS`、`has_hardware_video_encoder`、`log_hardware_encoder_fallback`、`actual_encoder`、`_reset_disabled_hardware_encoders_for_tests` |
| 帧数校验 | `_probe_video_frame_count`、`stream=nb_frames`（快速）/ `stream=nb_read_frames`（`-count_frames` 严格）、文案「帧数错误: 第 N 段预期 X，实际 Y」 |
| 并发与保序 | `render_workers`、`_run_render_jobs`、`concurrent.futures`、`_write_concat_list`（按原始索引顺序）、「并发渲染失败，已回退串行」 |
| 合并 | `_final_concat_copy_command`（`-f concat -safe 0 -map 0:v:0 -c:v copy -an -avoid_negative_ts make_zero -movflags +faststart -sn -dn`）→ 失败 `_final_concat_reencode_command`（`-vf _cfr_concat_filter -r … -fps_mode cfr`） |
| 产物/流程 | 稳定命名、`尽力删除已有输出或临时文件`、`合并相近片段: N (合并了 M 个)`、进度区间数值 `45/57/67/75/85/90`、**渲染失败仍出 XML**（「合并失败；XML 已生成」） |
| 在位数值 | `1920`、`1080`、`48000`、`1800.0`、`120.0`、`2`、`6`、`0.001`、`0.1`、`1000`、`20`、`60`、`100`、`12` |

### 1.3 导出前守卫（blob #139/#140，本批只做口径登记）

「匹配结果过于碎片化：共 N 个片段，其中 M 个是单帧片段。这通常表示画面匹配失败，
继续导出会生成闪烁视频」= 我方 **续25 展示层两件套**的单帧守卫已实现同语义
（`exporters.split_clips_at_boundaries` + `min_piece_s`），本批不重复移植。

---

## 2. 我方落地（续30）

**口径（用户 2026-09-29 拍板）**：① **紧凑拼接**（不做黑场空档腿）；② **音轨取原片对应区间**（不用解说轨）。

| 层 | 落点 |
| --- | --- |
| 渲染核心 | `mvp/src/media/ffmpeg/timeline_render.py`（纯函数命令构造 + `TimelineMovieRenderer` 监护执行） |
| 复用 | `source_merge.concat_list_text / parse_progress_seconds / error_summary / is_hdr / is_high_bit_depth`、`_runner.CREATE_NO_WINDOW / _error_tail`（不重复实现） |
| 配置 | `infrastructure/config.py::RenderConfig`（`enabled` 默认 True 但**只由显式入口触发**、crf/preset/prefer_hw/workers/stall_timeout_s/timeout_s/sample_rate/out_dir）+ `load_config` JSON 覆盖段 |
| 目录 | `infrastructure/paths.py::rendered_root()`（app data 下 `rendered/`，与 `merged/` 同族） |
| 服务 | `app/locator_service.py::render_movie()` —— 与 `export_project` **同一套 clip 计划代码**（`build_export_plan` → `snap_clips_to_scenes` → `split_clips_at_boundaries`），返回含 `clip_ranges` 的信息 dict |
| 阶段 | `app/models.py::ProgressStage.RENDER_MOVIE`（只由渲染任务发出） |
| API | `POST /api/tasks/render`（异步任务，进度/取消与定位同通道）+ `Task.kind`（`analyze`/`render`）+ `TaskManager.submit_render` + `worker.run_render_worker`；**渲染目标在提交时锁进任务**，排队期间新定位不会换批 |
| UI | `mvp/ui`：`ServiceAPI.startRenderTask` + Http/Mock 适配器 + `composables/useRenderMovie.ts`（轮询/取消/打开目录）+ 结果页导出对话框「成片渲染」区块 |

**刻意不做**：黑场空档腿、解说音轨、变速补齐（`atempo` 只在竞品用于把音频对齐时间线，我方紧凑拼接不需要）、并发>2。

---

## 3. 本机实测确立的工程结论（新发现，非竞品确证）

**中段音频不能用 AAC，必须 PCM。**

首轮真实验收（2.mkv 60 段）产出 3552 帧、逐段帧数全部通过校验，但帧 PTS 直方图显示
**59 处接缝**（60 段 - 1）帧距从 0.0417s 变成 0.0630s，成片时长比计划多 1.27s，
容器 `r_frame_rate` 被探成 `48000/1001`（源是 `24000/1001`）：

- 机制 = AAC 每帧 1024 样本（48k = 21.3ms），编码器把段尾补齐 → 中段音频恒比视频长一个 AAC 帧；
  concat demuxer 按**容器内最长流**推进下一个文件的偏移 → 视频在每个接缝被推后 21.3ms。
- 错误解法 `-shortest`：实测反而把视频截掉 3 帧（144→141）并把间隙放大到 0.103s，**已弃用**。
- 正确解法 = **中段 MOV + PCM 24bit**（采样精确），最终合并只复制视频、音频整片转一次 AAC
  （`-c:v copy -c:a aac`）。实测 3 段合成源：144 帧、帧距全部 0.0417s、零不规则接缝。
- 中段容器名进入产物稳定命名哈希，旧 AAC 形态的缓存不会被误复用。

**回归锁**（两处，都会长期跑）：
`mvp/tests/test_timeline_render.py::test_renders_movie_with_expected_frames` 断言成片帧距集合
== {1/fps}；`mvp/scripts/accept_video_render_2mkv.py` 的 `frame_delta_stats` +
`alignment_probe`（逐段中帧在原片 ±4 帧内找最优匹配，>1 帧判失败）。

---

## 4. 真实素材验收（2026-09-29，DirectML 无关：本批是 CPU/GPU 编码链）

素材 = 生产现役基线结果批 `work/fastglobal_default_2mkv.results.json`（69 条结果，
原片 `D:\video\2.mkv`）；渲染器配置 = 生产默认（`prefer_hw=True`、crf 18、preset medium、workers 2）。

| 判据 | 结果 |
| --- | --- |
| 实际编码器 | `h264_amf`（本机 AMD 硬件 H.264 在位且成功，无需回退） |
| 成片 | `work/render_accept/movie_2_9e72eb168e51.mp4`，60 段 / **3552 帧** / 148.169s |
| 帧数校验 | 计划 3552 == 容器 `nb_frames` == `-count_frames` 严格计数 |
| 帧率 | 成片 `24000/1001` == 原片（修复前被探成 48000/1001） |
| 接缝规则性 | 3552 帧、**irregular = 0**（修复前 59 处） |
| 音轨 | `aac / 48000 / 2ch`（原片对应区间音频） |
| 与工程同计划 | EDL 60 段 vs 成片 60 段，源片区间逐段差 ≤0.06s ⇒ 同计划 |
| 逐段对齐 | 8 段抽样：最优偏移 0 或 −1 帧（MAD 噪声底 0.32-0.47）⇒ 时间线正确；注意**测量脚本自身的时间轴累加必须按帧精确**，用名义秒会假跑出 4 帧漂移 |
| 逐张读图 | `work/render_accept/review/clip{00,05,10,20,31,35,43,52,59}_sheet.jpg` 左右画面同景同人同动作 |
| 耗时 | 60 段首跑 54.7s（≈0.9s/段）；二次调用命中稳定命名缓存 = 0.2s 复用 |
| HDR 口径 | `hdr_downgraded=True`（2.mkv 高位深源 → 成片降 8bit SDR，工程仍指原片） |

产物：`work/render_accept/{movie_*.mp4, 1.loc.edl, render_accept_summary.json, review/*.jpg}`。

### 4.1 成片性质度量（决定"能不能直接交付"，不是质量缺陷而是形态）

| 度量 | 实测（2.mkv 生产基线批） |
| --- | --- |
| 段数 / 总时长 | 60 段 / 148.0s |
| 单段时长 | min 1.0s · 中位 2.0s · max 9.94s |
| 源片覆盖范围 | 87s ~ 2417s（原片 7667s） |
| **播放顺序**源片起点倒序对 | 236/1770 = **13%** |
| 相邻回跳 | **8 次**（其中跨度 >60s 的 5 次）；开头即 2417 → 1579 → 1580 → 1005 → 1034… |

⇒ 当前成片形态 = **审片带 / 素材堆**（按解说时间轴把定位段拼起来，来回跳），
**不是**可直接对外交付的叙事片。这是"紧凑拼接"口径的必然结果，不是实现缺陷。
判据更正留痕：我一度用「源片起点是否单调递增」当验收项，实为**先排序再比较 = 恒真**的
口径错误，已换成"按播放顺序数倒序对/回跳"。

### 4.2 验收覆盖的诚实边界

- 逐张读图 = **9/60 张**对照图（首/中/尾 + 可疑段），其余 51 张靠帧距规则性 + 8 段 MAD
  对齐度量兜底，未逐张目视。
- 打包 exe 内「渲染成片」按钮 / 进度 / 打开目录**未真机点过**（需授权）。
- 解说视频（`D:\video\1.mp4` 侧）的音轨未进成片（用户口径 = 取原片音频），
  所以成片听感是原片现场声，与解说文案不对应。

---

## 5. 测试与基线

- 后端 `mvp/tests`：**388 → 433**（`test_timeline_render.py` 29 + `test_render_movie_service.py` 16），全套 OK（skipped=2 = 既有 MPS 平台类）。
- API `mvp/api/tests`：**89 → 99**（`test_render_task.py` 10），全套 OK。
- 前端 vitest：**118 → 127**（`renderTask.test.ts` 9）+ 双 typecheck 干净 + `test:mock` 契约 PASS（含渲染段）。
- 生产基线**不变**：严格 127/139 · 场景 137 · 负例 4/9 · 截等长 105（渲染是显式新入口，定位/文本导出链路零改动，无 `feature_version` 变更）。

## 6. 边界与尾巴

1. **打包 exe 真机复核未做**（需授权）：结果页「渲染成片」按钮 + 进度 + 打开目录只在 Mock/vitest 与浏览器态结构验证过，未在发行包内点过。
2. 渲染产物目前**不进残留清理清单**（`rendered/` 与 `merged/` 同族，需随「残留清理二级」一并登记）。
3. 竞品「相近片段合并」「渲染失败仍出 XML」两条流程语义我方未复刻：我方失败即抛 `MediaError`（对外话术 + LOC 码），由 UI 显示错误条幅——与既有导出告警口径一致，是否改成"仍出工程 + 附告警"待拍板。
4. 并发默认 2（竞品在位常量 2/6）；本机 amf 硬件编码下 workers=2 与 =1 的耗时差未测，属后续性能小项。
