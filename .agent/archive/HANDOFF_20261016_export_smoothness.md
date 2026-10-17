# 交接 2026-10-16 — 成片「过渡不流畅」诊断（**未结案**）

> 本条按用户要求**不并入 `.agent/` 文档**（STATE / TODO / CHANGELOG / DECISIONS 均未更新），
> 仅作跨窗口交接用。探针与中间产物全部在 `work/trans_smooth_20261016/`（`work/` 不入库）。

## 0. 接手时的项目状态（与本诊断无关）
- 现役包 **r24**（干净 commit `811932e`），包内四道全绿；`origin/master` = 本地 `master` = `995cc9a`。
- mac 侧：run `38429952068` = success，`mac-alpha` 包 **916,840,558B @ 2026-10-13T17:01:02Z**
  （对基线 +12,163B 且时间戳变化）；`git diff --name-only 811932e..c789670` 仅 `.agent` 三份档案
  ⇒ mac 代码面等同 r24。**该核验结论已写进 STATE/TODO/CHANGELOG（未提交）**。
- 工作树：仅 `.agent/{STATE,TODO,CHANGELOG}.md` 有改动（就是上面那条 mac 核验），`mvp/` **零改动**。

## 1. 用户报的问题
「导出的视频片段与片段之间过渡有点不流畅，总感觉有延迟一样」。
素材（均经微信传来，**不是原始导出文件**）：
- `D:\xwechat_files\...\2026-10\1.mp4` = 软件导出成片，1280x544 @ **30.000**，64.20s / 1926 帧
- `D:\xwechat_files\...\2026-10\2.mp4` = 源剪辑片（竖屏 TikTok 解说，带德语字幕），576x832 @30，66.07s
- `C:\Users\Bsaizne\Downloads\clips\clips\og*.mp4` = **35 段剪映腿素材**，1920x806 @ **23.976**
- `draft_meta_info.json` = 剪映自己的草稿元数据，**全空、无区间信息**，没用

## 2. 已排除（都有读数，别再重测）
| 候选 | 判据 | 结果 |
|---|---|---|
| 编码器 hold 帧 | 全分辨率精确重复帧 | 仅 3 帧，无 ≥3 连 |
| 接缝拉伸 / 时间轴异常 | 逐帧 PTS | 1925 个间隔**全 = 1/30s**；音频 2764 个全 = 1024 采样 |
| A/V 漂移 | 双流时长 | 64.200 vs 64.201 |
| 跨边界画面重播 | 20 硬切跨侧最近邻匹配 | cos>0.93 = **0 条** |
| 转码插帧 judder | 近零差分帧 mod-5 相位 | 1.mp4 **无锁定**(17–23%)；**2.mp4 才有**(50.7%) |
| snap 头尾 pre-roll | 未匹配帧归属 | 头 0.40s + 尾 0.33s（全片合计 0.73s） |
| 取材扩宽 | 剪映腿合计 66.11s vs 成片 64.20s | 仅 +1.91s ≈ 0.06s/段 |
| `extract_clip` 切分不忠实 | 高运动窗口 t=900s 对照源直解 | 帧数 47=47、首差 0.60 vs 0.62 ⇒ **忠实** |
| 段间源区间重叠 / 重复认领 | 35 段两两比对 | 重叠 **0 对**；仅 1 对内容距离<6（是同一切开的镜头） |
| 成片内部重复画面 | 1.mp4 帧对 cos>0.99 | 只有 14.8–17.2s 那个**静止镜头自相似** |

## 3. 唯一站得住的观察（内容层，非机械层）
逐帧 CLS 对齐（产品同款 DINOv2 ViT-S/14 CLS-384 @DML，中心方裁消除竖屏/宽幅形状差）：
- 两视频**互覆盖 87–89%**（正向 89.1% / 反向 87.0%），是同一批内容。
- 成片 64.2s 归类：**A 同步 69.0% / B 拖长 17.3% / C 解说里没有 10.9% / D 压缩 2.9%**。
- B 高度集中：**3/35 段占 75%**（`og3005-3008` 3.09s 源画面 vs 解说仅 0.04s 等）。
- 目检确证两例：成片 13.8–17.2s 给 3.4s 柱廊大厅全景（解说只用一瞬，同画面在解说 22.0s）；
  成片 39.8–41.8s 给外景跑向大门，解说同期已切室内机位。
- 代码侧：成片通道**不吃** `material_expand`（`locator_service.py:1676`），但吃
  `snap_scenes` + `snap_tolerance_s=1.0`（`config.py:480`、`exporters.py:184`）；
  28/35 段边界落在 **0.5s 网格** ⇒ 吸的是 `scenes.npy` 的网格边界，不是帧级真实切点。

## 4. 三臂/两臂实测（决定下一步用）
| 臂 | 总时长 | A | B | C | 像素静止占比 |
|---|---|---|---|---|---|
| baseline | 66.11s | 47.05 | 7.92 | 6.21 | 32.2% |
| armB 帧级切点细化 | 63.48s | 45.46 (−1.59) | 7.47 | 4.88 (−1.33) | — |
| armC 段宽上限 K=2.5 取中心 | 60.19s | 46.63 (−0.42) | 4.09 | 4.42 (−1.79) | 30.7% |
| armC K=1.5 取中心 | 58.06s | 46.21 (−0.83) | 3.50 | 3.13 (−3.04) | 31.7% |

- **armB 判负**：裁 2.63s 里只有 1.33s 该裁，另 1.59s 是同步好画面。
- **armC 有效且不撞护栏**：`center` 与 `best`（解说推进最大窗）结果差 ≤0.33s ⇒ 不需要 temporal align。
- ⚠️ **B 的降幅不作证据**（裁法与判据同源，构造性自证）；A/C 的读数相对独立。
- ⚠️ 静止占比跨文件对比有 confound（竖屏裁切放大每像素运动 + 字幕条），只当方向性提示。

## 5. 我本轮撤回过的错判（**下一个人别重踩**）
1. 「解说只有 21.8% 被覆盖」→ argmax 在静止镜头塌帧；换反向覆盖是 87%。
2. 「每段多吐 2 帧 / og 帧数 12k+2 指纹」→ **我的 rawvideo 字节计数器每份恒定多 2 帧**
   （ffmpeg 把 0.083s 起始空隙用首帧填满）。packet 级实测每段帧数精确 = 理论值。
3. 「每切一刀多 2 帧」→ 同上假象。
4. 「素材开头 1 帧重复是切分造成的」→ 高运动对照下 `extract_clip` 与源直解首差一致，**不成立**。
5. 「微信 24→30 插帧 judder 导致卡顿」→ mod-5 相位检验否掉了 1.mp4 这条。
6. 「1.mp4 是剪映导出」→ 错。og 合计 66.11s ≠ 64.20s，**1.mp4 是内建成片渲染**（movie 通道）。
7. 造了 V0/V5 两组 A/B 素材让用户"去对比"→ **V0 与 V5 内容相同、且 V5 没解决任何东西**，
   等于把测量责任推给用户，被明确否掉。

## 6. 未结的问题（按优先级）
1. **没拿到用户指认的具体秒数**——所有假设都是"我猜他在看什么"。要一个秒数才能定帧号→源区间。
2. **没拿到未经微信转码的原始 `movie_*.mp4`**（1920x806@23.976）。画质/码率/帧节奏这一族
   在微信副本上**测不出来**，只能拿原文件测。
3. **没拿到 `<解说片名>__<hash8>.results.json`**（在 `%APPDATA%\Video Locator AI\exports\`）。
   没有它，「主 span 本身就宽」与「snap 撑宽」两者的占比**无法拆开**，armC 的引用时长只能用
   对齐代理 ⇒ 那是规模估计，不是验收数。
4. 一条独立观察未查：og 素材是 5.1 且声道布局串写作 `6 channels`（未指定布局），二次编码到
   AAC 直接被拒（要 `-ac 2`）。产品 `extract_clip` 是 `-c:a aac` 直出，**5.1 原片可能在这步就失败**。
5. 一条数据自相矛盾未定位：`og720-720`（源 720s，排在 reel 末段）与解说最后一段的相似度，
   一处算法给 0.08、另一处给 0.97 —— **两个数打架，没查是谁错**，不能拿来解释任何结论。

## 7. 候选下一步（**未拍板**）
- 导出加一条**源侧段宽 ÷ 解说引用时长**的上限（与现役 `material_expand_rel_cap=2.5` 同族），
  超限按中心收口。K=2.5 保守版：C 降 29%、A 仅损 0.42s。
  代价：切点落在镜头中间，出现半个动作的硬切 ⇒ **属产品口径裁决**（成片该给"完整原片镜头"
  还是"解说实际引用的那段"），需用户拍板，不是 bug 修复。
- 若走这条，验收须含：后端全套 + API + 导出计划不变式 + 三指标/导出实得不降。

## 8. 探针产物（`work/trans_smooth_20261016/`，不入库）
`frame_probe.py` `dup_probe.py` `replay_probe.py` `embed_align.py` `report_align.py` `align2.py`
`classify.py` `cutdetect.py` `seam_continuity.py` `seam_vs_cuts.py`(判据坏，勿引用)
`boundary_precision.py`(判据坏，勿引用) `extract_offby.py` `seam_repro.py` `seam_count.py`
`gop_check.py` `make_ab.py` `make_v5.py` `dup_claims.py` `cap_probe.py` `perclip_B.py`
`feats.npz` `og_feats.npz` `blocks.json` `align_report.json` `cuts.txt`
接触表/验证图：`FILMSTRIP_1fps_0-64.2.png`（每秒一帧、带绝对时间戳）、`exp_[A-F]_*.png`、
`src_[A-G]_*.png`、`cut_verify.png`、`firstframes.png`、`ab/V0_原样对照`、`ab/V5_双流归零`

## 9. 踩坑备忘（工具层）
- ffmpeg 过滤器里 Windows 路径的 `:` 与 `\` 会被吞：`drawtext=fontfile=` 与
  `metadata=print:file=` 都因此静默失败过。**解法：`os.chdir` 到工作目录 + 只用相对文件名。**
- 无字体配置时 `drawtext` 需显式 `fontfile=arial.ttf`（把 arial.ttf 拷到 cwd）。
- 数帧数**必须**用 `ffprobe -count_frames` 或 packet 计数；用 rawvideo 字节数除会因起始空隙补帧而虚高。
- 暗场+高运动素材上，「像素差分 > 5×中位数」会漏报真实切点（实测 4 个报 0 个）；
  改用 ffmpeg 归一化 `scene>` 判据或直接读图。

## 10. 2026-10-17 接手结果（本轮，另一会话）

### 10.1 §6.4 那条「未查的独立观察」= **真缺陷，已复现并修掉**
- 复现：把本产品抽出的 `og*.mp4`（AAC 5.1，ffprobe `channels=6 / channel_layout=unknown`）
  **当原片**再喂给 `FFmpegIO.extract_clip` ⇒ `MediaError`，ffmpeg rc=-22，
  报 `[aac] Unsupported channel layout "6 channels"`，产物 **0 字节**。
  探针 `work/trans_smooth_20261016/probe_extract_clip_audio.py`（A 臂走产品代码 / B·C 臂裸 ffmpeg 对照）。
- 机制（新查清，§6.4 当时只有猜测）：**布局 `5.1(side)`／`hexagonal` 编码进 MP4 后布局信息就丢了**
  ⇒ 第一次编码成功、**第二次编码必失败**。也就解释了 og 素材为什么是 5.1 却 `unknown`：
  它们的源片声轨布局不是能被 AAC/MP4 表达的形态。
- 次生陷阱（新发现）：失败会留下 **0 字节目标文件**，而剪映腿的判据是裸 `exists()`
  ⇒ **第二次导出不再报错**、静默把 0 字节素材写进草稿（与「媒体格式不支持/时间线空白」同族）。
- 已修（`mvp/src` 三处 + 4 条新锁，门禁全绿，明细见 `.agent/CHANGELOG.md` 2026-10-17）：
  `extract_clip` 首跑参数不变、失败后按 48k/stereo 重试；失败不留半成品；
  可用性判据收成唯一来源 `app.exporters.clip_present`（剪映腿 + 草稿写入端共用）。
- 改后重跑探针 A 臂 = OK（447,853B）；判据真咬：C 臂仍 rc=-22。

### 10.2 同族未改（登记，等拍板）
- `media/ffmpeg/source_merge.py::_transcode_args` = `concat → -c:a aac`，无布局归一 ⇒
  同形源上失败更早：`Cannot select channel layout for the link between filters
  auto_aresample_0 and Parsed_concat_6`（rc=-22、0 字节）。修法 = concat 前插
  `aformat=channel_layouts=stereo`（或同款失败回退）；属**多原片合并**那条腿，本轮未动。

### 10.3 主线（过渡不流畅）状态 = **未推进**
- 仍缺三样（§6.3/§6.6 第 1~3 条）：**他指认的具体秒数**、**未转码的原始 `movie_*.mp4`**、
  **`<解说片名>__<hash8>.results.json`**。本轮只读查证：`%APPDATA%\Video Locator AI\data\exports\`
  只有 3 份 **2026-08-27** 的旧 results（`1__ffdc13d9` / `edit10__b8fcd316` / `svl_edit__7388a6c9`），
  **不含本案** ⇒ §6.3「主 span 宽 vs snap 撑宽」仍无法拆开，armC 的验收数仍只能用对齐代理估。
- §6.5 的 `og720-720` 相似度自相矛盾（0.08 vs 0.97）本轮**未查**，仍挂账。
