# PLAN — smart render 条件快路径（2026-10-26 续97 调研→设计，**实现待拍板**）

> 依据：`FINDINGS_PERF_HARDPROBLEMS_SURVEY_20261026.md` §2 + 续97 实测（时序分解 96% 在逐段编码；
> workers 2→6 已落地 ≈2.3x；d3d11va 硬解判负）。本文 = 条件快路径的实现设计。
> **动码需口令。**

## §1 已实测的事实链

1. 渲染 60s（70 段）里 **Σ 逐段编码 108s（串行口径）/ concat 仅 4.1s（已是流复制）**。
2. workers 2→6 已把全片打到 **26.3s**（2.3x，本批已进 config 默认）。
3. d3d11va 硬解**判负**：纯解码 0.48s vs CPU 0.22s/2s 窗——RX 6750 GRE 的解码回拷比 CPU 软解 HEVC10 还慢。
4. **编解码器分布（四片实测）**：2.mkv / test1 / test2 = **HEVC 10-bit**；test3 / 编辑片 1.mp4 = H.264 8-bit。
   ⇒ smart render 的「copy 段与重编段互拼」要求**同 codec/位深**，对 HEVC 源在现契约（H.264 8-bit 输出）下不成立。

## §2 方案形态：仅 H.264 8-bit CFR 源的条件快路径

**触发条件**（plan() 阶段判定，全部满足才走快路径，否则落回现役逐段重编）：
- 源视频流 = h264 + yuv420p（8-bit）+ 无 HDR；
- 源帧率与计划帧率一致（CFR，`r_frame_rate == avg_frame_rate`）；
- 音频各段可统一（现役 PCM 语义保留）。

**段策略**（对每个 clip [a,b]，GOP 索引预扫产物 = 关键帧时刻表）：
- 头：a 非关键帧 → 重编 `[a, K2)`（K2 = a 后第一个关键帧；解码自 K1 起）；a 即关键帧 → 无头段。
- 中：`[K2, K3)` 全部 GOP **流复制**（`-c copy` 进 MOV）。
- 尾：b 非关键帧 → 重编 `[K3, b)`；b 即关键帧 → 无尾段。
- 段内三件套 concat（copy）成段 MOV（PCM 音轨现役语义不变，音频本来就要重编成 PCM——不受 codec 限制）。
- 最终合并不变（现役 concat copy + 音频一次 AAC）。
- 帧数校验：copy 件 = ffprobe `nb_frames`（packet 计数），重编件走现役 `verify_segment_frames`。

**GOP 索引预扫**：`ffprobe -show_packets -select_streams v:0 -show_entries packet=pts_time,flags`
一次全片（2h 片实测量级 1-2 分钟），按源片哈希缓存到索引侧车（同 scene_strength 惯例）。

## §3 预期收益（诚实口径）

- **H.264 源（如 test3 类）**：copy 占比依赖 GOP 密度；60 段成片预计 26s → **~8-12s**（copy 件零解码零编码）。
- **HEVC 源（3/4 现有 GT 素材）**：**不适用**（除非 §4 拍板改契约）。
- 已被 workers=6 吃掉一部分（26s 已是 2.3x），增量收益比调研时预估的小。

## §4 决策点（需用户拍板）

1. **是否实现 §2**（仅 H.264 源受益，工程量 ~1 天 + 门禁全跑）。
2. **HEVC 源是否改输出契约**（成片输出 HEVC 10-bit + `hevc_amf` 重编拼缝，copy 段原生保留）：
   改变「成片恒 H.264 8-bit」的产品口径（HDR 降 SDR 留痕语义随之重审），播放兼容面需实测。
   不改则 HEVC 源维持现役路径（workers=6 已提速）。

## §5 坑清单（照抄 DeepRegular/SmartCut 的 11 条 + 自查）

开放 GOP（copy 起点落 GOP 尾部会缺参照）/ leading pictures（B 帧重排，`-copyts` 语义）/
DTS-PTS 偏移跨段累积 / POC 冲突（跨段 h264 解码器重置需 SPS/PPS 在位）/ 音画起点对齐 /
`-ss` copy 语义退化到关键帧 / MOV `hvc1/hvcC` 标签差异 / 时间戳非单调（2.mkv 实测有
`non monotonically increasing dts` 警告史）/ 拼接清单转义（现役 `concat_list_text` 复用）/
帧数校验对 copy 件的口径 / 缓存失效（源重命名/换文件同哈希碰撞）。

## §6 验收门（实现时必跑）

- `test_timeline_render.py`（帧距集合断言）+ 新增 copy 件帧数/顺序单测；
- `accept_video_render_2mkv.py` 的 `frame_delta_stats` / `alignment_probe`（逐帧等值）；
- H.264 源（test3）+ HEVC 源（2.mkv 走回退路径）双臂渲染对照；产物 ffprobe 流参数逐项对照现役。
