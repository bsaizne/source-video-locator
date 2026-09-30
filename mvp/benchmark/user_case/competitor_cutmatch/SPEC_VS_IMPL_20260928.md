# 我方规格 vs 实现 断链清单（2026-09-28）

> **GT 版本**：不涉及（本文是实现对齐，不做召回评估）。
> **判据**：每条都核到 `文件:行号`；**子代理初报的结论凡与我实测不符的，本文以实测为准并标注更正**。
> 背景：用户质疑「是不是漏了功能没接入」。竞品侧对齐见同目录
> `FINDINGS_CAPABILITY_MAP_20260928.md`；本文管**我方自己规格承诺过但没接通**的部分。

## 一、本轮已修（Track A，2026-09-28 续16）

| # | 断链 | 真实性质（实测更正后） | 证据 | 修法 |
|---|---|---|---|---|
| A1 | 模型资产无完整性校验；`torch.load` 无 `weights_only` | `asset.json` 只有 name/opset/shape；三处裸 load | `directml_backend.py:56`、`cpu_backend.py:79`、`mps_backend.py:79` | 导出写 `sha256`/`size_bytes` + `verify_asset()` 不符即 `DeviceError`（legacy 放行留痕）+ `weights_only=True`；生产资产已就地回填并备份 `.bak-pre-a1` |
| A2 | `preprocess_sha` 失效判据 | 子代理报「完全缺失」**不准确**：字段存在（`domain/index.py:22`），但 `IndexMeta.extractor` 用 `default_factory` 且 `create_index` 从不填值 ⇒ **恒为空串的空壳**，`validate()` 也不比对 | `domain/index.py:54`、`feature_store.py:117-128` | 摘要 = hash(feature_version+fps+dim+normalize 标记 + **真实 `_imagenet_preprocess` 行为指纹**)；`validate` 不符判 INVALID；历史空值**一次性回填放行**（实测四片索引保持 VALID、零重建） |
| A3 | 结果会话不恢复 | 子代理报「后端缺失」**不准确**：`service.load_results()` 早就有，缺的是 **HTTP 端点** | `locator_service.py:1006`、`api/routes/results.py`（原只有 4 个 POST）、`HttpServiceAdapter.ts:254` | 新增 `POST /api/results/load` + 前端 `loadResults` 接通（恢复后 `/api/export` 可直接用） |
| A4 | 导出策略写死 | 后端与适配器**本就支持**四项覆盖，只是页面硬编码 `MEDIUM/exclude/snap=true` | `api/schemas.py:43-46`、`exporters.py:93-121`、`ResultsPage.vue:156-157` | 导出面板暴露置信门槛/低置信处理(exclude｜备用轨)/边界吸附；**默认值与旧行为逐字一致** |
| A5 | dev 模式静默跑 Mock | 生产构建已于 09-22 `83c73e1` 修复，**开发模式仍默认 Mock** 且界面无提示 | `resolveService.ts:11-23` | `serviceIsMock()` + App 顶部常驻黄条 |

## 二、仍未修（按产品影响排序）

| # | 断链 | 证据 | 不做的后果 |
|---|---|---|---|
| G1 | **Confirm / 批量确认 / 跳过当前结果** 无入口（规格 §4/§8.7/§8.8 承诺） | `ResultsPage.vue` 只有"不导出此段"排除 | 工作流退化为"全导出"，与规格语义不符 |
| G2 | **性能基准表空缺 vs 对外承诺** | `MVP_ROADMAP §4/§7` 要求 10/60/120min 实测表，档案内从无；`PRODUCT_INTRO:51` 已写「2 小时影片约 7~12 分钟」 | 宣传与证据倒挂（本轮已启动实测补此洞，见 §三） |
| G3 | **置信阈值未标定** | `CONFIDENCE_DESIGN §6` 自认"结构占位未标定"；`DECISIONS 2026-09-01` 保留「不标定占位」护栏 | HIGH 档可能虚高（2026-09-01 原型实测 HIGH 精度仅 5/13）；产品「宁缺勿滥」承诺无数据支撑 |
| G4 | 前端假数据 | `HomePage.vue:28,33`、`ProjectsPage.vue:16` 写死 `movie.mkv` / `Interstellar (2014).mkv`；项目「时长」恒 0（无 metadata 端点） | 第一印象即假值 |
| G5 | WS 进度未实现 | `api/routes/tasks.py:6-8` 自述占位；前端 800ms 轮询 | 仅体验损耗，非阻断 |
| G6 | 导出 `filename` 模板 | `HttpServiceAdapter.ts:207 void opts?.filename`；后端**仅 json 落盘通道**有 filename，工程导出通道无 | 需先定口径（补后端参数 or 从规格删除该承诺），**不应擅自实现** |
| G7 | `MediaLibrary` 页不存在（规格 §10 列了 7 页，实际 6 页） | `ui/src/pages/` | 素材管理无独立入口 |
| G8 | 项目/会话仅存 localStorage | `stores/projects.ts:20-36`，后端无 projects | 换机器/清缓存即丢项目列表 |
| G9 | `ROCmBackend` 规格要求但被 DirectML 取代，无 `AMD_GPU_BACKEND_BLOCKED` 归档判定 | `DEVICE_BACKEND_SPEC §2` vs `src/device/` | 规格与实现口径不一致（应更新规格，非补代码） |

## 三、本轮同时启动的实测（Track B）

`mvp/scripts/bench_perf_tiers.py`：10 / 60 / 128 min 三档 × 建索引 wall/吞吐/峰值 RSS/索引体积
+ 128min 真实配对（2.mkv + 1.mp4）首次与缓存复跑定位。结果落地后填 `MVP_ROADMAP §7` 表，
并核对 `PRODUCT_INTRO:51-52` 的「索引 7~12 分钟 / 复定位 2~4 分钟」是否成立。

⚠️ 脚本首版踩坑已修（并写入 CHANGELOG 教训）：隔离 `SVL_DATA_DIR` 会**连带**把 ONNX 资产查找一起隔离，
导致 `resolve_backend` 静默 fallback CPU —— 那样测出的数字**不能**用来验证「GPU 加速」承诺。
现显式指向生产资产并**硬断言**后端必须是 `DirectMLBackend`，不是就中止。

## 四、顺带更正的两条档案错判

1. **续13 全项目审计的「0 死旋钮」不成立**：`SeqAlignConfig.vectorized` 全仓无消费点；
   `ConfidenceConfig.nreps_dispersed`/`max_similar`/`scene_div_montage` 只被**孤儿路径**
   （`ConfidenceEngine.assess()` ← `engine/localization/pipeline.localize_segment`，无生产调用者）消费。
   → 2026-09-28 经用户拍板**已删除**（见 `DECISIONS.md` 同日条）。
2. **`scripts/smoke_locator_service.py` 在本次清理之前就已损坏**：它 patch
   `app.locator_service.produce_candidates` / `.localize_segment`，而 locator_service 早已不导入二者
   （生产走 `EvidenceLocalizer`）。⇒ 教训：**smoke 脚本不在 unittest discover 范围内 = 没有回归保护**，
   坏了没人知道。同类风险：`mvp/scripts/smoke_*.py` 其余几个同样无自动执行。
3. 保留待拍板：`engine/candidates.produce_candidates` 同属该孤儿链，本轮**未删**——
   删它会连带删掉 `test_retrieval_ranking` 对 ranking 层的唯一覆盖。
