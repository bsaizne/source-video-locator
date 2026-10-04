# D 盘空间清理候选清单（2026-10-02 续44，实测尺寸；~~只列不删~~ **A 档已于同日经用户授权执行**）

> **执行留痕（2026-10-02 用户拍板：「a3只删r5，D:\cm可以直接删了，剩下的再仔细确认一遍」）**：
> 删前逐项复核（r6/r7 zip 在位、ISC pth 冗余副本 420,418,996 字节在位、parts 内含证据 PNG 只删
> mkv、无进程占用 win-unpacked/dist_backend），**直删**（不走 trash——每项均已验证可再生或冗余，
> 旧包直删沿用 r3/r4 先例）：A1 旧 trash 5.7G + A2 D:\cm 5.4G + A3 仅 r5 zip 1.67G（r6 保留）+
> A4 win-unpacked 1.6G + A5 dist_backend/build_backend_work 1.14G + A6 parts 夹具 mkv ≈1.1G
> （tl_*.png 证据保留）+ A8 LOCALAPPDATA merged 1.9G ≈ **18.5GB**。A7 pth **保留**（与 A1 二选一
> 中选了留 work 副本）。删后复核：r6/r7/ISC 权重 ONNX/parts PNG/全部档案完好。D:\claudework
> 46G→20G，benchmark 24G→19G。B 档未动（待拍板）。
>
> **追加执行（同日用户拍板「老时代证据图可以删」）**：B1 的 9 个目录**只删图片**（2683 张
> jpg/png，4.4G→1.6M），**72 个数据文件全保留**（52 json 含 GT 草案/评审记录、16 md、2 py、
> 2 html——git 追踪的图片为 0，无版本库损失）。B2（work 证据图族 ≈3.0G）仍待拍板。

> 背景：D 盘被本项目相关内容占用 ≈47GB（benchmark 24G + 前次 trash 5.7G + 竞品逆向工作区
> 13G + 竞品安装 D:\cm 5.4G + 测试素材 D:\ProjectXIXI 8.8G + D:\video 1.3G + venv 3.2G）。
> 本清单在 PROJECT_AUDIT_20260928 §1/§2/§9 基础上用 2026-10-02 实测复核，并修正两条过时判定
> （见「禁删」C-1/C-2）。B 档删除仍一律等用户拍板。

## A. 建议删除（可再生构建产物 / 已判死的缓存，零项目影响）≈ 15.1GB

| # | 路径 | 实测 | 依据 |
|---|---|---|---|
| A1 | `benchmark_trash_20260928/`（整个） | **5.7G** | 前次清理的 trash（ViT-B/orb/isc 旧缓存 + datasets/2.mkv 副本 1G），还原窗口已过。⚠️ 唯一价值 = `tier2/work/isc21_weights/isc_ft_v107.pth.tar`（已恢复副本在 `work/isc21_weights_ortho_probe/`，二选一即可） |
| A2 | `D:\cm`（竞品安装目录） | **5.4G** | 续24 已确认无引用（逆向用 D:\cm 安装目录的提取产物已归档 cutmatch-analysis + sha256 溯源），当时已答复可删 |
| A3 | r5/r6 两个旧分发包 zip | **3.36G** | `mvp/ui/release/Video-Locator-win-x64-20261001r5.zip` + `...20261002r6.zip`；现役包 = r7，两旧包删除此前已多次登记待拍板 |
| A4 | `mvp/ui/release/win-unpacked/` | **1.6G** | electron-builder 产物，`build-release.ps1` 一键重建（zip 内含同内容） |
| A5 | `mvp/scripts/dist_backend/` + `build_backend_work/` | **1.14G** | PyInstaller 中间产物，`build_backend.py` 重建（审计 §1 🔴）；`build-release.ps1` 自己会调它 |
| A6 | `work/merge_accept/parts/` | **1.1G** | 合并验收夹具视频（2.mkv 切半+合并产物），accept 脚本重生成；目录内小证据 json/log **保留** |
| A7 | `work/isc21_weights_ortho_probe/isc_ft_v107.pth.tar` | **420M** | ONNX 已导出且与 torch 逐位一致（cos=1.0）；pth 仅再导出用，与 A1 的 trash 原件二选一（建议删 trash 留这份） |
| A8 | `%LOCALAPPDATA%\SourceVideoLocator\merged/` | **1.9G** | 产品合并产物缓存（审计 §9 🟡），copy 流复制分钟级重算 |

## B. 待拍板（有内容：证据图/冷档案，删前建议压缩归档或明确放弃）≈ 16GB

| # | 路径 | 实测 | 内容与风险 |
|---|---|---|---|
| B1 | `mvp/benchmark/user_case/` 老时代帧证据 9 个目录 | **≈4.3G**（cases 1.3G/gt_v3 944M/gt_review 694M/gt_rebuild 445M/gt_A 336M/contact2 274M/montage_research 185M/_frames2 177M/contact 90M） | Phase 1~12 GT 评审/研究证据 jpg（除 montage_research 5 文件外均未入 git）。审计判定「被 FINDINGS 引用为证据，建议保留或迁冷存储」——相关结论均已定案多轮，删 = 放弃图证复核能力 |
| B2 | `work/` 视觉证据图族 | **≈3.0G**（highwrong_visual 496M/confv2_visual 364M/degradation_visual 362M/gate_flips_visual 293M/gt_tickets_visual 263M/combo_pocket_visual 252M/gt_boundary_refine* 479M/ui_accept 272M 等） | 逐张读图裁决的证据链（verdicts csv 引用）；续32 铁律后「读图」是结论依据，删 = 无法复核当时的裁决。建议 zip 压缩（png/jpg 可压 ~50%）或迁冷存储 |
| B3 | `D:\claudework\cutmatch-analysis\extracted\` | **5.69G** | 竞品解包产物；逆向已宣告挖穿（REDIG_20261001），但 data/ 的 blob 索引引用 extracted 原件——删后 blob 级复核不可行。工作区其余（FINDINGS/data/sandbox ≈7G）**保留** |
| B4 | `work/bench_src/` | **482M** | 性能基准源片（10/60min mkv，`bench_perf_tiers.py` ffmpeg 截取可再生，脚本头自注「可删」） |
| B5 | `work/dinov2_weights/dinov2_vitb14_pretrain.pth` | **≈330M** | ViT-B 路线已产品级关闭（严格 −1），仅再开路线时需重新下载 |
| B6 | `%APPDATA%\Video Locator AI\data` 的 `previews/`+`edited_cache/` | **≈30M** | 自动重建，价值低（顺手项） |

## C. 禁删（硬依赖/现役基线/证据链）

- **C-1 `work/_patch_onnx_tmp/`（169M）**——⚠️ 审计 §2 旧判定「可删」**已过时**：`resolve_patch_onnx()` 的
  默认回退路径就在这里（源码树跑 locate 时 patch 精排器 DML 生效的前提），删了会静默回退 CPU torch
  （续36 打包事故同款）。
- `work/dinov2_weights/dinov2_vits14_pretrain.pth`（vits14 本体，产品模型再导出源）；
  `mvp/ui/resources/models/`（253M，打包资产：DINOv2 + patch ONNX + asset.json）；
  `mvp/ui/resources/backend/`（1.1G，构建时重建——但下次构建前删会多花一次 backend 打包时间，可留）。
- `work/spl_patch_arms/on_*`（现役基线结果批 = r7 对照）、`work/isc_refine_arms/`（续44 验收产物）、
  `work/gt_backup_pre_ticket_20260930/`、`work/gt_backup_pre_gap_review_20261001/`（GT 改前快照）、
  `work/orthogonal_backbone*/`（今日方案B 证据）、`work/gap_gt_review_final_20261001/`。
- `datasets/real/`（GT json 体系 + edited 1.mp4）、`engines/`（390M，冻结研究资产）、`results/`、`src/`、
  `mvp/poc/`（85M，H2/H3 GO 证据）、`tools/ffmpeg.exe`、`mvp/ui/node_modules`（开发/构建需要）、
  `D:\video\`、`D:\ProjectXIXI\`（四片测试素材本体）、`D:\claudework\video-dedup-tool`（venv）。
- 全部 `.md` 档案、`.agent/`、`cutmatch-analysis` 除 extracted 外全部（逆向结论的数据依赖）。

## 汇总

- **A 档立即可释放 ≈15.1GB**（其中 A1+A2+A3 = 14.5GB 是大头）。
- **B 档拍板后可释放 ≈16GB**（建议：证据图 zip 压缩后删原件，可再省一半）。
- 保守路线（只删 A1/A2/A3/A8 四个无争议项）= **16.6GB**。
- 本次只盘点未删除任何文件；执行时逐项确认后迁 `benchmark_trash_20261002/` 观察一周再彻底删。
