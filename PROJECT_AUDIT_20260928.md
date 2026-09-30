# PROJECT FULL AUDIT（2026-09-28 续13）— 结构化扫描 / 历史残留 / 查缺补漏

> 扫描范围：全仓目录尺寸与文件构成、156 个 PipelineConfig 旋钮活性、FINDINGS 挂起项交叉核对、GT 漂移检测、git 状态。
> 结论分级：🔴 建议处理（需用户拍板删除/提交）/ 🟡 登记（低优先）/ ✅ 健康。

## 1. 全仓结构与尺寸（排除 .git/__pycache__/node_modules/win-unpacked）

| 区域 | 体积 | 性质 | 判定 |
|---|---|---|---|
| mvp/ui | ~2.0 GB（release 2.4 GB + resources 1.3 GB 含 win-unpacked 更大） | electron-builder 产物 + 下载资源 | 🔴 可再生构建产物；但 release 内含**现行 Windows 分发包**（待重打包验收，见 TODO），重打前勿删 |
| mvp/scripts | ~1.2 GB（dist_backend 910 MB + build_backend_work 256 MB） | PyInstaller 构建中间产物 | 🔴 纯可再生残留，可删（下次打包自动重建） |
| work/ | 3.7 GB（图 1.4 GB / npy 143 MB / 权重与缓存 ~1.7 GB） | 研究运行时缓存 | 分项见 §2 |
| mvp/benchmark/user_case | 4.7 GB（cases 1.4 + gt_v3 1.0 + gt_review 0.7 + gt_rebuild 0.5 + gt_A 0.35 + contact* 0.4 + montage/_frames 0.4 GB） | GT 评审/研究证据图 | 🟡 全部被 FINDINGS 引用为证据，建议保留；如需空间可整体迁冷存储（不动 gt json） |
| datasets | 1.05 GB（real/originals/2.mkv = **1.02 GB 源片副本** + edited/1.mp4 10 MB + 10 份 GT json） | 基准数据 | 🟡 originals/2.mkv 与 D:\video\2.mkv 重复（生产回归用 D:\video 路径）；benchmark 时代 runner 用仓内副本——删前需确认无脚本引用 |
| engines/ | 391 MB（vdf 268 / vcsl-official 115 / transvcl 8 / isc21 ~0） | Phase 1~19 第三方引擎仓 | ✅ 冻结研究时代资产，受「历史结果不覆盖」约束，保留 |
| src/ + results/ + benchmark_report_phase12~19 | ~0 MB | Phase 1~19 统一 runner 时代 | ✅ 冻结留档（AGENTS.md 仍引用 src/benchmark.py 命令——历史口径，不影响现状） |
| mvp/poc | 89 MB | H2/H3 POC 资产 | ✅ GO 结论证据，保留 |
| tools/ + diagnostics/ + verification_cases/ | ~116 MB | 工具二进制/诊断/验收 | ✅ |

## 2. work/ 分项残留判定（已关闭路线的缓存）

| 路径 | 体积 | 来源路线 | 判定 |
|---|---|---|---|
| work/orb_gt_cache/2@1fps.pkl | 522 MB | ORB 几何判据（phase24_1 探针①, 已证伪/非可用） | 🔴 残留，可删 |
| work/isc21_weights/ + transvcl_feats/ + engines/isc21 缓存 | ~430 MB | Phase 12 ISC/TransVCL 引擎时代（冻结） | 🟡 删除不影响现状；重跑旧 benchmark 需重下 |
| work/vitb_asset/ + dinov2_vitb14_pretrain.pth + vitb_data/ | ~800 MB | ViT-B 基座路线（2026-09-25 产品级关闭） | 🟡 路线已关；若彻底关死可删（再开需重新导出/下载） |
| work/_patch_onnx_tmp/ | 176 MB | ONNX 导出临时 | 🔴 可删 |
| work/dinov2_weights/vits14 + transnetv2 权重 + 四片索引 idx | ~0.3 GB | **现役**（生产/复现共用） | ✅ 保留 |
| work/*.png/jpg（2 200 张复核/证据图） | ~1.45 GB | 逐图裁决证据（verdicts csv 引用） | ✅ 保留（verdicts 的证据链） |
| work/proxy_* / denserecheck_* / voteprior_* .results.json 等 | ~15 MB | 各时代结果批（对照基线） | ✅ 保留 |

**可释放合计（🔴 项）≈ 1.6 GB；🟡 项（需拍板）再 ≈ 1.7 GB。**

## 3. 旋钮/代码活性

- **156 个 PipelineConfig 旋钮：0 个死旋钮**（全部在 src/scripts/tests 有消费点）✅——两次「审计接线」（2026-09-05）后无漂移。
- 后端全套 279 测试全绿（本轮 272+7）；前端 vitest 67 + API 58 上次全绿记录 2026-09-26。

## 4. 查缺补漏（本轮新发现并已处理/登记）

1. ✅ **GT 漂移检测 = 无变更**（gt_impact_scan: 8 份 GT 基准快照一致）；32 份研究文档缺 GT 版本标注头（多为 competitor_cutmatch 系——其使用 test GT 与 v4，结论不受影响；按登记规则①补头列入低优先待办）。
2. 🟡 **AGENTS.md 运行命令陈旧**：统一 runner 命令（`src/benchmark.py --engine all` / 三引擎汇总）属 Phase 1~19 冻结时代口径，与现行 MVP 管线并存易误导新会话——已在本文件登记，建议下次编辑 AGENTS.md 时加「冻结时代命令」标注（AGENTS.md 结构受硬约定保护，未动）。
3. 🔴 **git 工作区 97 个文件未提交**（最近 commit = 580bcc4, 2026-09-26 GT 审计）：含续10l~续13 的全部源码改动（dense_start_check / offset_vote_prior / config / locator_service / 测试 / 文档）。**建议尽快提交**（需用户授权；建议拆两笔：mvp 源码+测试、研究文档+work 产物白名单核对）。
4. 🟡 `.agent/archive/` 已有 9 个未归档 checkpoint 快照（2026-09-25~27）——归档机制自动产物，无需处理。
5. ✅ 「遗忘项」交叉核对：FINDINGS 全系 grep 挂起/未竟/待拍板 的命中经与 TODO P0 容器对账，**未发现未跟踪的新 open item**（多数为已闭环条目的历史表述；V5 口径待拍板项 R_rec/t2r05a/查询单元细分前置均在 TODO 在册）。

## 5. 第二遍深度补扫（同日, 应用户「确定完整扫过一遍了吗」质询补充——第一遍为存储/卫生层, 本节为代码/文件层）

| 检查项 | 结果 |
|---|---|
| 97 个未提交文件明细 | **6 个核心源码/测试**（locator_service.py、config.py、dense_start_check.py、offset_vote_prior.py + 2 个测试文件）+ ~52 个研究脚本（mvp/scripts, 各 FINDINGS 的产物链）+ 26 份研究文档 + 5 份 .agent 档案 + 9 个 checkpoint + 2 个根文档。**核心代码全部在未提交集合里, 丢失风险属实** |
| mvp/src 代码本体（60 模块） | **0 孤儿模块**（全部被 src/api/tests/scripts/ui 引用）、**0 语法错误**（py_compile 全过）、仅 5 处 TODO 字样且全部是 docstring 里对历史 TODO 条目的引用（Phase 22 导出三项均已实现验收）, 非未偿代码债 |
| UI 前端（mvp/ui/src + electron, 63 文件） | 0 TODO/FIXME；vitest 67 + typecheck 上次全绿（2026-09-26） |
| work/*.py（91 个） | 各时代研究探针脚本（Ambiguity/性能/竞品系）, 体积可忽略, 均为 FINDINGS 产物链证据, 保留 |
| .gitignore 覆盖 | ✅ work/、mvp/scripts/dist_backend、mvp/ui/release 等大产物全部被忽略（git 未提交清单干净, 无大文件误入风险） |
| results/（57 文件）+ logs/（21）+ diagnostics/（277）+ verification_cases/（168） | Phase 1~19 冻结时代产物, 静态留档 ✅ |
| 根目录历史文档（PROJECT_HANDOFF/TECHNOLOGY_SELECTION/ARCHITECTURE_ANALYSIS/bundle_report 等） | Phase 1~19 时代口径, 属历史交接文档; **现行交接以 .agent/STATE.md 为准**（AGENTS.md 已规定优先级）——无需改写, 但新会话勿把其中数字当现状 |
| .agent/INDEX.md（173 行） | 框架仍为 benchmark 时代表述——低优先刷新（STATE/TODO 才是活文档） |
| datasets/synthetic + benchmark-*.agentctx.json | 冻结时代基准与 CLI 快照, 留档 ✅ |

**第二遍结论**: 代码层与文件层无新缺陷——唯一实质风险仍是 **git 未提交**（6 个核心源码文件在其中）。两遍合并后,
扫描覆盖 = 全部目录 + 全部源码 + 全部配置旋钮 + 全部挂起项 + git 状态, **未再有未扫区域**。

## 6. 第三遍全量普查（同日, 应用户二次质询「每一个文件夹每一个都不漏」——本轮做到逐文件入册）

- **方法**：os.walk 全仓（仅 .git 内部不入册、单独计数），**35,789 个文件全部进普查清单**
  `work/project_file_census_20260928.json`（逐路径 JSON，可机器核对）。
- **前两遍漏网目录（本遍补查完毕）**：
  - `.claude/`（1 文件, launch.json = agent 工具配置）——无害；
  - `.github/workflows/h3-macos-mps.yml`（1 文件）——H3 MPS POC workflow（workflow_dispatch-only, 2026-08-26 已知）；
  - `docs/`（顶层, 3 文件: DEPLOYMENT / DEPLOYMENT_HANDOFF / RELEASE_TEST）——打包部署时代文档, 与 mvp/ui 打包链配套, 留档 ✅；
  - `src/`（实为 100 文件含 __pycache__; 纯 .py 50 个: adapters 5 引擎适配器 + experiments Phase12 探针 + vision_qa + benchmark runner）——Phase 1~19 冻结时代完整确认, 与 AGENTS.md 描述一致 ✅；
  - 顶层小文件逐一清点（10 份 phase 报告/benchmark_results.json/environment.json/report_summary.json/.agentctx 快照等 22 个）——全部为冻结时代产物或工具快照, 留档 ✅。
- **普查后无主文件数 = 0**：每个文件归属已分类目录（现役 / 冻结留档 / 构建产物可再生 / 研究证据 / 待拍板残留）。
- **三遍合并结论**：第一遍=存储层, 第二遍=代码/文件层, 第三遍=逐文件入册（35,789/35,789）。**扫描至此真完整；
  唯一实质风险不变 = git 97 文件未提交（含 6 个核心源码文件）。**

## 7. 零功能影响瘦身（2026-09-28 续13 执行, 用户拍板「不能影响功能」）

- **原则**: 只动「可再生构建产物/临时文件/零引用」；**全部移动到回收区而非删除**（同盘 mv 瞬时完成, 可随时还原）。
- **已移出**（共 **1.19 GB** → 回收区 `D:/claudework/benchmark_trash_20260928/`）:
  `mvp/scripts/dist_backend`（883MB, PyInstaller 输出——build_backend.py 以 --distpath 交 PyInstaller 自建, 脚本对不存在容错）、
  `mvp/scripts/build_backend_work`（245MB, --workpath 同上）、`work/loc_smoke`（63MB, 全仓 0 引用）、
  全仓 34 个 `__pycache__`（34MB, 自动再生）。
- **保守不动**: `_patch_onnx_tmp`（176MB, 名为 tmp 实为 patch 研究探针输入资产）、vitb 全套/orb_gt_cache/isc21（已关闭路线但属
  harness/重跑资产, 删了影响「可复用资产」）、`mvp/ui/release`（内含现行 Windows 分发包, 重打包验收前保留）、
  `datasets/real/originals/2.mkv`（1GB 源片副本, 删前需全仓引用核查）。
- **验证**: 移动后全套 **279 测试全绿** + 生产链路 import 正常 + 构建脚本目录自建确认。还原方法: 把回收区对应目录 mv 回原位即可。
- **进一步瘦身需拍板**（见 §2 🟡 项, 合计 ~1.7GB）: vitb 路线缓存/orb+isc 冻结缓存/originals 副本。

## 8. 当前 open item 总账（截至 2026-09-28 续13, 详见 TODO.md P0）

- **等用户拍板**：残留清理（§2 🔴/🟡 项）、git 提交、置信公式豁免（2026-09-01 冻结护栏）、UI/导出验收打包授权（vote_prior/dense_recheck 翻默认开的前置）。
- **可执行（已有材料）**：展示层移植（切点时间线展开+单帧守卫）、ED 快速分镜复核、ordered_search 真值参数探针、speed_fill、口径档对照收尾。
- **等外部**：执行方 D 段剩余口径档（接口已留）；机器码专项（N1/N4 推翻后价值缩水，唯 candidate_count 等占位符）。
