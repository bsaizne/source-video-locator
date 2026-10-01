# FINDINGS — 打包态定位慢 2.6~3.9x 的根因 = patch 精排器静默回退 CPU torch

> **GT 版本**：不适用——纯性能归因 + 零语义验证（跨运行形态结果批逐位一致），不改任何判定数字。

**日期**：2026-10-01（续36）
**上游**：续35 归因第一步（`CHANGELOG` 「续35 归因」）判「环境罚 ≈2.69x，问题在环境层非代码层」，
下批候选 = 打包态关干扰单变量复跑。本批即该复跑，结论把「环境层」这一步拆到底并定位到**具体资产缺失**。

---

## 1. 三臂 + E2E 对照（同素材 test2、同优化代码、同索引复用、两旋钮默认开）

| 臂 | 切分+逐段主循环 | 后处理（shot_split+patch_refine） | 总计 | 产物 |
|---|---|---|---|---|
| 打包整包 E2E（UI+预览+计算机操控观察在场，r3 包） | 1245s | 2512s | **3756.7s** | `%APPDATA%/Video Locator AI/logs/video_locator.log` 逐分钟复原 |
| 打包 backend.exe **headless**（无 Electron/无预览/无观察，r4 包） | 1150s | 2475s | **3625.0s** | `work/pkg_attr/armA_packaged_cpu_reranker.*` |
| 源码树 venv 直跑（续35 复跑） | ~450s | ~950s | **1396.7s** | `work/spl_patch_arms/on_test2.results.json` |

**读数一：UI/预览/CUA 观察无罪。** 把整包 UI 与自动化观察全部去掉，打包后端自己是 60 分钟级
（3625 vs 3757，差 3.5%）。续35 猜的「Electron 同机资源 + 用户预览 + CUA 观察干扰」**不成立**。
阶段级也一致：逐段主循环每段 22.0s（E2E）vs 21.0s（headless）。

**读数二：罚在冻结包本体。** 打包 headless vs 源码树直跑 = 2.60x；且分布均匀（主循环 1150/450=2.6x、
后处理 2475/950=2.6x），说明是运行态整体变慢，不是某一段算法被额外触发。

## 2. 根因（一条日志行）

包内后端日志：`patch reranker device=cpu`；源码树同一行 = `device=dml`。

`mvp/src/engine/localization/patch_rerank.py:157 resolve_patch_onnx()` 的解析顺序是
显式配置 → `SVL_PATCH_ONNX` → **相对源码树** `work/_patch_onnx_tmp/dinov2_cls_patch.onnx`。
PyInstaller 冻结包里没有 `work/`，Electron 也没注入 `SVL_PATCH_ONNX`（只注入了 `SVL_DML_MODEL`），
于是 `PatchReranker._try_onnx()` 直接 False → `_try_torch()` 用 CPU torch 跑 ViT-S 出 1369 个 patch 特征。
重排器被**逐段近场重排**与 **patch_refine** 两条热路径共用，故全链均匀变慢。

`locator_service.py:1751` 原本把这件事记成一条 `info`（`device=cpu` 也在正常输出里），
打包验收只看「起得来、跑得完」，所以瞒了约两周。

## 3. 双向验证（合成素材 a1.mp4 × source.mp4，同一 headless harness，20s 量级即可复现）

| 运行形态 | wall |
|---|---|
| 打包 backend.exe（无 `SVL_PATCH_ONNX`） | 78.5s |
| 打包 backend.exe + `SVL_PATCH_ONNX` 指向图 | **20.2s** |
| 源码树 run_backend.py（同 harness） | 20.1s |

⇒ 只补一个环境变量就把打包态拉回源码树水平（3.9x），机制闭环，无需重打包即可验证。

**大素材验证（Arm D）**：打包 backend.exe + `SVL_PATCH_ONNX`，test2 全片、两旋钮开、索引复用、
DirectML 硬断言通过、日志 `patch reranker device=dml` —— **wall=1400.5s**：

| 臂 | 总计 | vs venv |
|---|---|---|
| venv 直跑（续35） | 1396.7s | 1.00 |
| 打包 + patch 图（Arm D） | **1400.5s** | **1.003** |
| 打包 无 patch 图（Arm A） | 3625.0s | 2.60 |
| 打包整包 E2E（Arm A 同形态 + UI） | 3756.7s | 2.69 |

Arm D 阶段分解：主循环 365s（vs Arm A 1150s）、后处理 1036s（vs Arm A 2475s）。
⇒ **冻结包本体没有罚**，此前测到的「环境罚 2.69x」全部来自这一处资产缺失。

## 4. 零语义确认

打包（CPU 精排，Arm A）、打包（DML 精排，Arm D）与 venv（DML 精排，续35 复跑）三方 test2 结果批：
各 67 段、**含 confidence 全字段 + 信封字段**两两差异段数 = 0（仅 `result_id` 不同）。
产物 `work/pkg_attr/armA_packaged_cpu_reranker.results.json` / `armD_packaged_dml_reranker.results.json` /
`work/spl_patch_arms/on_test2.results.json`。
⇒ 纯性能缺陷，不是质量缺陷；两旋钮翻默认开后的生产基线读数（严格 132/场景 137/负例 4）不受影响，
也不需要重跑三指标。

## 5. 落地（本批实施）

- **资产随包**：`dinov2_cls_patch.onnx`（78KB 图）入仓 `mvp/ui/resources/models/dinov2_cls_patch/`；
  其外部权重 `dinov2_cls_patch.onnx.data` 与包内已分发的 `dinov2_cls_384.onnx.data` **字节相同**
  （sha256 `5af75ca5…` 实测一致），故构建时按 ORT 要求的同名复制，分发包净增约 **88MB**（非 176MB）。
  `asset.json` 记图/权重 sha256 供构建期与验收期断言。
- **注入**：`electron/main.ts` 打包态 `spawnEnv.SVL_PATCH_ONNX = <resources>/models/dinov2_cls_patch/dinov2_cls_patch.onnx`
  （与 `SVL_DML_MODEL` 同族接法）。
- **不再静默**：`locator_service._announce_patch_reranker()` —— 特征后端非 CPU 而精排器 = CPU 时
  记 **WARNING**（含修复指引话术）。单测 3 条（`mvp/tests/test_patch_v2.py`）。
- **构建期防回归**：`mvp/ui/scripts/build-release.ps1` 装配 patch 资产（缺图 fail-fast，缺权重则从
  CLS 同名复制）+ sha256 断言，杜绝「资产没进去照样打包成功」。
- **包体验收**：新 `mvp/scripts/accept_packaged_bundle.py`（资产在位/摘要/合成冒烟 `device=dml`/
  耗时阈值/出结果），重打后必跑。

## 6. 边界与遗留

- 只测了 Windows AMD(DML) 线；macOS(MPS) 侧 `PatchReranker` 本就要求 DmlExecutionProvider，
  拿不到即 torch —— 本批改动对 mac 无收益也无害，但 mac 包会多带 88MB 死资产（H3 正式化时再裁）。
- `dinov2_cls_patch.onnx` 在仓内**没有再生成脚本**（`export_dml_model.py` 只出 CLS 图）；
  本批把 78KB 图入仓 + sha256 在册，但「可复现导出」仍是缺口，已登记 Known Issues。
- 未做杠杆3（REFINE_FPS/窗口/CLS 预筛），维持暂缓裁决。
- 单变量边界：本批只动了「patch 图在不在位」这一个变量；数据目录、ffmpeg 二进制（md5 相同）、
  numpy/OpenBLAS dll（相同）、轮询频率（p50 4ms）均逐一排除后才落到该结论。
- 复现物料命名：`attr_env_phase_table.py` 读 `work/pkg_attr/headless_test2.*`（当前落的是 Arm D）；
  Arm A 另存 `armA_packaged_cpu_reranker.*`、Arm D 另存 `armD_packaged_dml_reranker.*`，两臂都不会被覆盖。
- venv 侧阶段边界尚无带时间戳的产物（`attr_lab_arm_timestamped.py` 已备好未跑）——§1 表里源码树的两列
  是由「OFF 臂 7–8min + 总数 1396.7s + 续34 A/B 比值」推得，非实测行级时间戳；引用时注意这个精度差。
