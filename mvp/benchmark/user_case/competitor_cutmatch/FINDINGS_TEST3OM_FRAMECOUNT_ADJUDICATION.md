# FINDINGS — test3-om.mp4 帧数锚点裁决（判卷侧独立复核）

- **日期**：2026-09-26（判卷侧/ benchmark 侧）
- **触发**：执行方 om 批交付（`test2-om.mp4.probs.npy` / `test3-om.mp4.probs.npy`）时帧数交叉校验失败
  `[('test3-om.mp4', 244003, 244004)]`，按任务书「任一片帧数与 §5.1 锚点不符 ⇒ 停下报告」停止（`sandbox/out/DELIVERY_NOTES.md`）。
  执行方行为**符合任务书纪律**，本文件是判卷侧对该分歧的独立裁决。
- **裁决（可直接执行）**：`test3-om.mp4` 真实可解码帧数 = **244,003**；锚点 244,004 **偏高 1 帧**（把被 DISCARD 标记的末帧计入了 packet 数）。
  **执行方交付物（probs 形状 244,003）正确，无需重跑**。将 §5.1 锚点表该格 244,004 → **244,003**（及下文「待同步位置清单」全部 7 处）后，D 段即可放行。
- **定级**：帧数为工具实测事实（非「代理复现（推断级）」），证据链如下。

---

## 1. 证据链（全部判卷侧独立实测，素材 = `D:\ProjectXIXI\test3\test3-om.mp4`，2,851,500,714 B）

| # | 检验 | 结果 | 说明 |
|---|---|---|---|
| 1 | `ffprobe -count_packets` | **244,004** | 与锚点一致——但 packet 数 ≠ 可解码帧数（见 #4） |
| 2 | 容器元数据 `nb_frames` | 244,004 | muxer 写入的估值，与 packet 数巧合相等 |
| 3 | pts 网格分析（全流 244,004 包） | 占 244,006 槽位，**2 个空洞**（尾部 slot #244002/#244004）、0 重复；**2 个包 pts 超出容器时长**（10,177.083490 / 10,177.166875 > duration 10,177.000156） | 片尾 ~0.25 s 时间戳本身不规则 |
| 4 | **DISCARD 标记盘点**（全流 flags） | `K__` 2,964 / `___` 241,039 / **`_D_` 恰好 1 个** = 最后一个包（pts 10,177.166875, dts 10,176.916667, 62 B） | 解码器按 DISCARD 标记**直接丢弃**该帧 → 244,004 − 1 = 244,003 |
| 5 | 尾部区间解码（`-show_frames -read_intervals 10176%+#200`） | 最后解码帧 pts = **10,177.083490**；pts 10,177.166875 的包**未出帧** | 机制实证（与 #4 互证） |
| 6 | **我方独立全流解码计数**（`ffprobe -count_frames` → `nb_read_frames`） | **244,003** | 与执行方管线解码数**逐片一致**；全流解码零报错（`-v error` 无输出、EXIT=0）——是「按标记丢弃」而非「解码失败」 |

**对照（test2-om.mp4，同批顺带复核）**：packet = nb_frames = 执行方解码 = **121,094**，我方独立 `nb_read_frames` = **121,094**，四方一致，无分歧。

## 2. 与对方早期探针文件不矛盾（语义澄清）

`data/four_clips_framecount_verify.json` 中 `frames_ffmpeg_demux=244004`（= packet/demux 计数）、`frames_cv2=244004`
均为**非解码计数**：`frames_cv2` 实为 cv2 `CAP_PROP_FRAME_COUNT` **容器元数据估值**——铁证是同文件 test1-om.mkv 行
`frames_cv2=197305`（正是已裁决作废的「时长×fps 估算值」，`delta_cv2_minus_ffmpeg=199`）。全流仅有的两条**真实解码**
计数（执行方 rawvideo 管线 244,003；我方 `nb_read_frames` 244,003）完全一致，无任何矛盾。

## 3. 对 D 段的影响评估 = 零

- 被丢帧是**全片最后一帧**（pts 10,177.1669 s）。解码序列 slot 0..244,001（244,002 帧）全部齐整，
  probs 下标 0..244,002 与解码帧一一对应；唯一微差 = 最后一个解码帧（pts 10,177.0835）落在下标 244,002
  而非「pts 网格」的 244,003，差 1 帧 ≈ 42 ms，仅影响最后一个下标。
- 切点为秒级口径、D 段定位容差 ≥0.5 s ⇒ **对切点与定位结果零影响**。
- 副注（时间口径，供 D 提示词「时间码双写」条款参考）：该片首帧 pts = 0.125 s（容器起点偏移），
  「下标/fps」与「容器 pts」存在 +0.125 s（头）→ +0.042 s（尾）的慢变偏差；双方统一用同一下标口径即自洽。

## 4. 锚点口径修订（runbook 应随之升级）

本项目已两次踩同一类坑，建议把锚点定义从「容器 packet 数」升级为「**解码帧数**」：

| 教训 | 旧口径 | 偏差 | 权威口径 |
|---|---|---|---|
| test1-om.mkv（2026-09-26 上午） | 时长 × fps 估算 | **+199** | packet 数 197,106 |
| test3-om.mp4（本裁决） | 容器 packet 数 | **+1**（DISCARD 末帧） | **解码帧数 `nb_read_frames` = 244,003** |

⇒ **锚点 = `ffprobe -count_frames` 的 `nb_read_frames`（解码帧数，与解码序产物对齐）；packet 数降级为交叉校验**。
另：`frames_cv2`（CAP_PROP_FRAME_COUNT）与 duration×fps 同属元数据估值，**不得用作锚点**。

## 5. 待同步位置清单（全部 244,004 → 244,003）

1. `RUNBOOK_CUTMATCH_PROXY_REPRO.md` L182（§5.1 素材表「帧数」列）
2. `RUNBOOK_CUTMATCH_PROXY_REPRO.md` L197（§5.1 交叉校验表「帧数(锚点)」列；建议同时把表头口径改为「解码帧数」）
3. `RUNBOOK_CUTMATCH_PROXY_REPRO.md` L557（§验收 2 锚点清单）
4. `PROMPT_FOR_EXECUTOR.md` L41（帧数清单）
5. `sandbox/run_scene_split.py` L49 `ANCHORS`
6. `sandbox/probe_meta.py` L51 与 `sandbox/probe_frame_counts.py` L24 `ANCHORS`
7. `sandbox/verify_proxy_output.py` L21 锚点表

（执行方已交付产物按 244,003 出的，更新锚点后 `verify_proxy_output` 应全绿，**不要求重跑 om 批**。）

## 6. 判卷侧证据文件（本仓）

- `work/_t3om_pts.txt`（全流 244,004 包 pts 转储）＋网格缺口分析结论（见 §1#3）
- `work/_decode_count_test3om.txt` / `_decode_count_test2om.txt`（首轮全解码错误扫描：零报错）
- `work/_t3om_readframes.txt` = `nb_read_frames=244003`；`work/_t2om_readframes.txt` = `nb_read_frames=121094`
- 复现命令（判卷侧，Git Bash）：
  `ffprobe -v error -select_streams v:0 -count_frames -show_entries stream=nb_read_frames -of default=nw=1 <file>`
