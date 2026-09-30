# FINDINGS — 多原片合并（video.concat）移植（2026-09-29 续27, 用户拍板「继续偷」起手项）

> **GT 口径**: 本文对照批 = `ground_truth_v4.json`（2mkv 片）; 基线批 =
> `work/fastglobal_default_2mkv.results.json`（生产现役默认态, 严格口径含 fast_global 开）。
> **runtime 改动**：新增 `media/ffmpeg/source_merge.py` + `app/locator_service.merge_originals` +
> API `original_paths`/`POST /api/source/merge` + `SourceMergeConfig` 4 旋钮（**默认开**，
> 单原片输入永不触发 ⇒ 对现役 127/139 基线零影响）。

## 1. 竞品语义（挖穿结论, D#221/#240 + catalog, 全部 docstring/字节级确证）

竞品「多原片」= **入库前物理拼接成单文件**，非多索引并行匹配（表 D 判读属实）：

| 竞品机制 | 确证级别 | 我方形态 |
|---|---|---|
| 输入解析：目录当前层扫描/自然排序/排除隐藏与既有合并产物；单视频直接用；多视频验证或创建**稳定命名合并文件** | docstring | `merge_originals(paths≥2)`；文件夹扫描**未移植**（属素材入库工具面差集） |
| 稳定文件名 = 数量+12 位 MD5(name\|size\|mtime\|mode)+模式+扩展名；无效缓存删除重建 | docstring | `merge_output_name()` 同构，产物落 `<appdata>/merged/`（竞品写素材目录旁） |
| 签名比对「选择主媒体规格」→ `direct_copy`/`normalized_copy`/转码 | docstring | `file_signature()`（codec/宽高/pix_fmt/色彩四项/fps/SAR/音频）全等→copy，否则转码 |
| 转码尝试链：硬件加速→硬件编码→CPU 高质量；nvenc/qsv/amf/videotoolbox→libx265 最后兜底，中文回退话术 | docstring+字节(编码器名) | `encoder_chain()` 同构；`_HW_QUALITY_ARGS` 为**工程先验**（竞品各档参数未字节确证） |
| libx265 medium / CRF 18 | 字节 | `SourceMergeConfig.crf=18` |
| HDR/高位深 → 硬件 p010le / libx265 yuv420p10le / 普通 yuv420p；色彩元数据透传；x265-params repeat-headers+hdr-opt | docstring | `pick_pix_fmt/color_args/x265_params` 同构 |
| mkvmerge 无损（全 MKV）：`+` 追加输入、`progress: N%` 解析 | docstring+字节 | **未移植**（我方发行物无 MKVToolNix）；等价路径=concat demuxer `-c copy`（实测 2GB 片 5.7s） |
| 运行监护：`-progress` 管道、>1h 超时、terminate→kill、取消、无输出 5s 心跳、失败详情单行限长、输出校验 | docstring | `_run()` 全项移植；输出校验=存在+视频流+时长∈±max(1s,2%) |
| 进度阶段「原片合并/解说合并」（progress.tracker 23 阶段） | 字节 | `ProgressStage.MERGE_SOURCES`（映射进 INDEXING 0-12 区间，UI 阶段枚举不动） |

## 2. 我方落点（架构约束决定）

- **单原片假设**在 API 层（`original_path: str`），domain/索引/导出天然单路径 ⇒ 合并只在
  入口做一次，产物回写 `task.original_path`，下游零改动（与竞品形态同构）。
- 合并文件是新文件 → 走既有 FeatureStore 建索引（无缓存可骗）；索引目录名带 sha256(path) 前 8 位，
  与原片索引天然隔离。
- 剪映/EDL 导出引用合并片路径——语义正确（素材真身已变），无需特判。

## 3. 实测（本批）

- 单测：后端 `mvp/tests/test_source_merge.py` **25** 项（纯函数 17 + 真实 ffmpeg E2E 5 +
  service 分支 3）；API `mvp/api/tests/test_source_merge.py` **8** 项。
- 全套：后端 **388 全绿**（363+25, skipped=2 均为既有 MPS 平台类）· API **89**（81+8）·
  前端零改动（vitest 95/typecheck 基线不受影响）。
- 真实素材验收（`mvp/scripts/accept_source_merge_2mkv.py` → `work/merge_accept/`，
  时间线 14:51 切分 → 15:07 定位完成，全链 ≈16 min）：
  - 切分：2.mkv（hevc 10bit 1280x688, 7667.5s, 1.0GB）在关键帧 t≈3837.04s 处 `-c copy`
    两半：part1=3837.04s / part2=3833.91s（和=7670.95s）。
  - 合并：mode=**copy**，5.7s 完成 1.0GB；产物时长 7671.04s vs 原 7667.54s（**+3.5s, 0.046%**，
    GOP 时间戳延续所致，在 ±2% 容差内）；二次调用 **reused=True** 同路径同字节。
  - 接缝出图：`grab_frame` 于切点 ±1s 正常出 688x1280 帧。
  - 定位（DirectMLBackend 硬断言通过 + 出厂默认配置）：合并片全新建索引 ≈8.6 min
    （与 128min 档实测 562.7s 同量级），69 段（与基线批段数一致）。
  - **对照基线批 `fastglobal_default_2mkv`：严格 36/39 · 场景 39/39 · 负例 FP 3/4 —— 逐 ID
    零翻转（pos_flips=[]、neg_flips=[]）**。分集原片经合并后与整片定位结论完全等价（本素材）。

## 4. 裁决与边界

- 默认 `source_merge.enabled=True`：多路径是新入口，单路径行为逐字节不变——**无需翻默认拍板**，
  但发分发包需重打（待用户授权，「打包需授权」在案）。
- **不解决**「跨原片并行索引」（如 分集 各自建索引+结果标注来源）——竞品也没做，其形态就是先合并。
- 已知取舍留痕：字幕轨（2.mkv 46 条 subrip）copy 时**丢弃**（`-map 0:v:0 0:a?`）；匹配不消费字幕，
  但导出给 NLE 的素材无字幕——后续若做「素材入库工具面」一并处理。
- 音频有无混用输入 → 转码降纯视频（竞品未确证该边界，我方工程取舍已留痕 `plan.reason`）。
- UI（多选原片入口/合并进度展示）**已接线（2026-09-29 续29）**：Electron `openFiles` 多选桥 +
  详情页「源片库」列表（顺序＝合并顺序、可删单项、支持一次拖入多段）+「立即合并/重新合并/取消合并结果」
  （`POST /api/source/merge`）+ 未合并时分析页按钮改「合并并分析」并带 `original_paths`（worker 侧合并）。
  进度展示沿用后端既有口径：`MERGE_SOURCES` 映射进 INDEXING 区间 → UI 管线仍显示「准备原片索引」，
  task.message 带合并文案，**UI 阶段枚举零改动**。项目卡/详情页对已合并项目显示产物路径 + `mode/reused` 徽标。
  vitest 118（新增 21）+ 双 typecheck 干净；**真机（打包 exe + 原生对话框多选）复核待打包授权**。

## 5. 产物

- 代码：`mvp/src/media/ffmpeg/source_merge.py`、`app/locator_service.py::merge_originals`、
  `infrastructure/config.py::SourceMergeConfig`、`infrastructure/paths.py::merged_source_root`、
  `api/routes/source.py`、`api/routes/tasks.py`(+original_paths)、`api/tasks/{models,manager,worker}.py`、
  `api/schemas.py`、`app/models.py::ProgressStage.MERGE_SOURCES`
- 测试：`mvp/tests/test_source_merge.py`(25)、`mvp/api/tests/test_source_merge.py`(8)
- UI 接线（续29）：`mvp/ui/electron/{main.ts:app:openFiles,preload.ts}`、`src/types/electron.d.ts`、
  `src/services/{types.ts:SourceMergeJson,ServiceAPI.ts,HttpServiceAdapter.ts,MockServiceAdapter.ts,mockData.ts}`、
  `src/stores/{projects.ts:sourceVideos/merge,analysis.ts}`、`src/pages/{ProjectDetailPage,AnalysisPage}.vue`、
  `src/components/ProjectCard.vue`；测试 `src/stores/__tests__/projectsSourceLib.test.ts`(15)、
  `src/services/__tests__/sourceMerge.test.ts`(8) + `scripts/mock-contract-test.ts` 合并契约段
- 验收：`mvp/scripts/accept_source_merge_2mkv.py` → `work/merge_accept/{parts/,merged_probe.json,
  source_merge_2mkv.results.json,source_merge_vs_baseline.json}` +
  `%LOCALAPPDATA%\SourceVideoLocator\merged\merged_2_1f8777435eff_copy.mkv`（及其索引
  `index/merged_2_1f8777435eff_copy__313bdda8.idx`）
- 基线对照：`work/fastglobal_default_2mkv.results.json`（未覆盖，历史结果只读）
