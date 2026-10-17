# 交接 2026-10-17 — REA 装机 + 竞品黑盒对照 + 取材扩宽护栏收紧（**三批都已落地，未提交未出包**）

> 自包含交接文档。上一会话在 2026-10-17 02:48 **按用户要求自动关机**，本文件在重启后（19:36）补写。
> 上位依据：`.agent/CHANGELOG.md` 2026-10-17 的两节（一）（二）+ 本节；`.agent/STATE.md` / `TODO.md`
> 按多会话约定**未改**（STATE 由单一方维护）。

## 0. 一句话状态

`HEAD = 995cc9a`（= origin/master）。工作树 **10 个已改文件 + 3 个未跟踪项，全部未提交、未出包**。
三条改动线都已完成并过了门禁：① 抽素材音轨回退修复；② 竞品切点的黑盒对照与导出层双臂；③ **取材扩宽护栏 2.5 → 1.5**。
静态逆向线（Ghidra 全量分析）**两次判死、已收线**。

## 1. 本轮三批改动（按落地顺序）

### ① 抽素材音轨回退 + 0 字节残留清理（`mvp/src` 3 文件 + 4 条锁）

- 缺陷（实测）：源声轨若是「N 声道 + 未指定布局」的容器，ffmpeg 原生 aac 编码器直接拒收
  （`Unsupported channel layout "6 channels"`，rc=-22，产物 0 字节）⇒ 剪映导出/预览整腿失败。
  **本产品自己抽出的 clip 天然是这种源**（源布局 `5.1(side)` 编进 MP4 后布局丢失），把 `og*.mp4` 当原片再抽一次即复现。
- 次生陷阱：失败留 0 字节文件 + 剪映腿裸 `exists()` 判据 ⇒ 第二次导出**不再报错**却把坏素材静默写进草稿。
- 修法：`extract_clip` 首跑参数**逐字不变**，仅失败后按 48k/stereo 重试一次；失败清掉半成品；
  可用性判据收成唯一来源 `app.exporters.clip_present`（剪映腿 + 草稿写入端共用）。
- 文件：`mvp/src/media/ffmpeg/ffmpeg_io.py`、`mvp/src/app/exporters.py`、`mvp/src/app/locator_service.py`、
  `mvp/tests/test_ffmpeg_io.py`(+3)、`mvp/tests/test_locator_service.py`(+1)。
- 复现/读数：`work/trans_smooth_20261016/probe_extract_clip_audio.py`（改前 A 臂 `MediaError` rc=4294967274；
  改后 A 臂 OK 447,853B；C 臂仍 rc=-22 ⇒ 判据真咬）。
- ⚠️ 同族**未改**（登记）：`media/ffmpeg/source_merge.py::_transcode_args` 也是 `concat → -c:a aac` 无布局归一，
  同形源上失败更早（`Cannot select channel layout for the link between filters auto_aresample_0 and Parsed_concat_6`，
  rc=-22、0 字节）；修法 = concat 前插 `aformat=channel_layouts=stereo`（或同款失败回退），需单独立批。

### ② 竞品（CutMatch）黑盒对照 —— 首次用同一把目检尺子量出「竞品 vs 我方」

数据来源 = `D:\claudework\cutmatch-analysis\sandbox\out\`（竞品交付的 `*.probs.npy` / `groups_t0*.json` /
`scene_split_t0*.json`，只读）。尺子 = `mvp/scripts/shot_detect/boundary_gt_v1.json`（44 窗 / 125 条 conf=high）。

**(a) 切点质量（共同覆盖的 2mkv + test1）**

| 臂 | ±1.0s P/R/F1 | 2mkv F1 | test1 F1 | 切点数 |
| --- | --- | --- | --- | --- |
| 竞品 t0.50（默认） | **0.885 / 0.958 / 0.920** | 0.909 | **1.000** | 1874 / 491 |
| 我方 scn2（现役） | **0.550 / 0.917 / 0.687** | 0.778 | **0.200** | 2091 / 942 |

**(b) 后处理规则已可逐帧复现**：thr 0.5 → 连续激活分组 → 合并相邻组（min_gap 8 帧级）→ 取合并跨距中点。
用他们交付的 probs + 自己记录的参数重放：`2.mkv` 1874/1874、`test1-om.mkv` 491/491 **逐帧全等**。
⇒ **`sensitivity=18` 对切点集合无可观测作用**（判据：不含它的规则即可逐帧复现）。

**(c) 导出层双臂（把竞品切点只接进导出计划层）**

| 臂 | 导出实得（仅主 span） | 严格 |
| --- | --- | --- |
| A 我方 scn2 | **131/139** | 135/139 |
| B 竞品 TN 切点 | **130/139** | 135/139 |

⇒ **换更准的切点在导出实得上不涨（−1，噪声级）**；卷轴几何有变动（Σ素材宽 ±，位移 p50 0–0.30s / max 4.38s）。
与档案旧结论同向：切点几何更准 ≠ 定位指标更好（`FINDINGS_TN_CUT_QUALITY_VS_METRIC.md`）。
**结论：竞品优势在信号源（TN 逐帧概率），不在后处理三条（阈值/组中点/min_gap）。**

**(d) 顺带的量级事实**：竞品 sidecar `.text` = **373MB**（427MB 整包的 87%）；其常量是「RVA 表 + 运行时基址」，
静态**没有任何 RIP 相对引用**（8 modrm × 5 opcode × 8 REX 全扫 = 0）⇒ 字符串 xref → 函数体这条路在它身上不存在。

### ③ 取材扩宽护栏 `material_expand_rel_cap` 2.5 → **1.5**（导出层口径，用户 2026-10-17 拍板）

- 文件：`mvp/src/infrastructure/config.py`（值 + 注释内嵌逐档实测）、`mvp/tests/test_exporters.py`（+1 默认值锁）。
- 四片扫描（`work/expand_sweep.py`；**同口径自证**：严格 135/139、导出实得 131/139 与生产基值逐位吻合）：

| cap | Σ素材宽 | 素材宽÷记录宽 | 导出实得 | 严格 |
| --- | --- | --- | --- | --- |
| 2.5（旧默认） | 499.1s | 1.53 | 131/139 | 135/139 |
| 2.0 | 452.1s | 1.38 | 131/139 | 135/139 |
| **1.5（新默认）** | **421.7s** | **1.29** | 131/139 | 135/139 |
| 1.2 / core 不扩宽 | 419.9s | 1.28 | 131/139 | 135/139 |

- ⚠️ **口径订正（必须读）**：cap 1.5 在这批数据上 **≈ 关闭扩宽** —— 导出计划不变式里扩宽条数四片 =
  **0/0/0/1**（cap 2.5 时是 11/7/9/12），Σ素材宽 421.7s ≈ core 419.9s（只差 1 条）。
  语义 = **卷轴只给解说实际引用的核心窗，不再撑成完整镜头**。2026-10-11 的 K=2.5（保留完整镜头）是
  用户当时拍的；2026-10-17 用户认可取 1.5。**若要「温和档」应取 2.0（−9.4%，保留部分整镜头扩宽）**，
  一条数值 + 一条锁改动，重跑本批门禁即可。

## 2. 门禁（改后树，逐条取 rc；数字已入库 CHANGELOG）

- 后端全套 **Ran 675 tests OK (skipped=2)**（674→675 = 本轮新增的 cap 默认值锁）
- API **Ran 150 OK**
- 导出计划不变式 **FAILED=0（4 片 × 4 通道）**
- 导出实得复测 **131/139、严格 135/139 不变**
- 定向模块：`test_ffmpeg_io` 24 OK · `test_exporters` 53 OK · `test_locator_service`（含新 `ClipPresentTest`）OK

## 3. 环境（本轮新装，都在 D 盘）

| 路径 | 内容 | 校验 |
| --- | --- | --- |
| `D:\claudework\rea` | REA 源码（master，含 Kuna 支持）：`npm ci` + `npm run compile` 完成 | `dist/` 可用 |
| `D:\npm-global` | npm 全局前缀（已从 `%APPDATA%\npm` 改到 D:） | `D:\npm-global\rea.cmd` 6.5.0 |
| `D:\tools\ghidra\ghidra_12.1.4_PUBLIC` | Ghidra 12.1.4 | zip sha256 = 官方 `ddac49f9…` |
| `D:\tools\rizin\…` | rizin 0.9.1（原始切片可反汇编） | sha256 = asset digest |
| `D:\tools\kuna\…` | Kuna 1.833 | sha256 通过，**但 REA 在 Windows 拒绝**（`unsupported_host`）|

环境变量（User 级）：`GHIDRA_INSTALL_DIR`、`REA_KUNA_COMMAND`。JDK 23（`D:\java`）被 Ghidra 接受。
REA+Ghida `doctor` **10/10 全绿**（含 `ghidra-native_authority`；源码构建需从 npm 包拷
`native/windows/build/{manifest.json,rea-windows-x64.node}` 回去才绿）。

**网络事实**：`github.com:443` 被阻断（`api.github.com` 通）；大文件走代理分片（实测 `ghproxy.net` + 8 并发 ≈ 2MB/s）。

## 4. 静态线为什么收线（两次判死，别再重复投入）

1. **REA 的 Windows Ghidra P0 只收原生 PE**（原文：`Windows Ghidra P0 accepts native PE and explicitly selected raw 6502 targets only.`）
   ⇒ 「把 373MB 切片喂 Ghidra」被平台策略封死；rizin 能反汇编切片，但 `axt` 只覆盖已分析范围（8MB = 2%）。
2. **全量 PE 分析吃不动**：默认 `GHIDRA_HEADLESS_MAXMEM=2G`（源码 `GhidraJavaLaunch.ts:152`）→ 1h50m 后
   `java.lang.OutOfMemoryError: Java heap space`；抬到 10G 重跑 30 分钟仍无产出（日志冻结、RSS 3.9GB），已主动掐掉。
3. 结构与语义证据：竞品常量是 RVA 表（54 个 32 位 RVA 槽指向锚点字符串）而**无 RIP 相对引用**；
   `sensitivity` 已被黑盒证明无可观测作用 ⇒ 剩下的静态未知只有 `commentary_boundary_refine_*` 的「存在性」角色，
   而它的**位置**角色 2026-09-26 已实测：施加在我方 227 条边界上 97.4% 位移 ≤4 帧。

## 5. 工作树与待办（下次开机第一件事）

- **未提交**：10 个改动文件 + `.agent/archive/HANDOFF_20261016_export_smoothness.md` /
  `checkpoint-2026-10-15-221716.md` / `.agent/versions/`（未 gitignore，建议加）。
  建议拆两笔：**代码笔**（`mvp/src` 5 + `mvp/tests` 3）· **档案笔**（`.agent/{CHANGELOG,STATE,TODO}.md` + archive）。
- **未出包** ⇒ 收益还不在用户手上：要 **r25**（本轮跨平台 JS/TS 无改动 ⇒ mac 不必另走 dispatch）。
- **观感面未测**：cap 1.5 的成片接缝 / 硬切位置未做读图验收（本轮只做只读数据面）；出包后按包内 accept 补，
  并做一次成片读图对照（对照 A4？cap 2.5 vs 1.5 双包各出一片）。
- 若用户觉得 1.5 太狠 → 切 **2.0**（数值 + 锁 + 重跑门禁），判据表见 §1③。
- 主线「过渡不流畅」仍未结：仍缺 ① 他指认的秒数 ② 未转码原始 `movie_*.mp4` ③ `<解说片名>__<hash8>.results.json`
  （`%APPDATA%\Video Locator AI\data\exports\` 只有 2026-08-27 的旧 results，不含本案）。
  另一条未查：`og720-720` 相似度自相矛盾（0.08 vs 0.97，上一会话留的账）。

## 6. 探针与日志清单（`work/` 不入库）

- 音轨：`work/trans_smooth_20261016/probe_extract_clip_audio.py` + `audio_51_probe.log`
  ；改后复跑 `work/audio_51_20261017/audio_51_probe_after_fix.log`
- 门禁日志：`work/audio_51_20261017/{backend_suite_postfix,api_suite_postfix,exporters,invariants_postfix}.log`、
  `work/cap15_{backend,api,invariants,expand}.log`
- 竞品黑盒：`D:\claudework\cutmatch-analysis\sandbox\{compare_bb_vs_ours.py,bb_final.py,rule_search.py,diag_timebase.py}`
  + 同名 `.log`；我方侧 `work/{export_arm_bb.py,export_arm_gt.py,expand_sweep.py}` + `.log`
- 静态线中间产物（`D:\claudework\`）：`anchor_scan.mjs`/`ptr_scan2.mjs`/`code_ref_scan.mjs`/`blob_base_scan.mjs`/
  `rva_cand.mjs`/`metadata_scan.mjs`/`make_slice.mjs` + `cutmatch_{anchor_refs,ptr_slots,code_refs}.json` +
  `slice_0x141d95456.bin`（8MB）+ `rea_analyze_{desktop2,sidecar,sidecar2}.json`

## 7. 下一会话接手口径

1. 先读本文件 §1③+§4（这两处最容易被误用：cap 1.5 ≈ 关闭扩宽；静态线别再重开）。
2. 提交/出包要等口令；`STATE.md` 结构不要动（补八块已在顶部，按防复发纪律迁移旧块）。
3. 竞品侧数据都在 `D:\claudework\cutmatch-analysis\`（**禁止递归读 `extracted/`，8+ GB**）。