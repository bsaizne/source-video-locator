# Phase 11 最终技术选型 — 视频片段反向定位引擎

> 生成日期：2026-08-24
> 数据来源：`benchmark_results.json`、`benchmark_report.md`（synthetic + real 实测），全部为本机实际运行结果，非 README 推断。
> 平台：仅 Windows 11 Pro 实测；macOS 未实测，涉及 macOS 的结论标注"推断"。
> 本文件是 STEP 1 交付物；STEP 2/3（改进候选再测 + 更新 ARCHITECTURE_ANALYSIS/README/报告）待后续。

---

## 1. 实测数据回顾（打分依据）

### 1.1 汇总表（来自 benchmark_report.md §总体对比）

| Dataset | Engine | Precision | Recall | IoU@0.5 | IoU@0.7 | ±1s Acc | Avg Runtime(s) |
|---|---:|---:|---:|---:|---:|---:|
| synthetic | VDF | 46.2% | 46.2% | 0.46 | 0.31 | 23.1% | 1.2 |
| synthetic | TransVCL | 0.0% | 0.0% | 0.00 | 0.00 | 0.0% | 5.0 |
| synthetic | VCSL | 25.5% | 76.2% | 0.76 | 0.48 | 60.7% | 0.7 |
| real | VDF | error（无可用重复组） | — | — | — | — | — |
| real | TransVCL | 0.0% | 0.0% | 0.00 | 0.00 | 0.0% | 5.0 |
| real | VCSL | 0.0% | 0.0% | 0.00 | 0.00 | 0.0% | 0.7 |

### 1.2 按变换类型的命中情况（synthetic）

| 变换 | VDF | TransVCL | VCSL |
|---|---:|---:|---:|
| a1 直接裁剪 | ✅ | ❌ | ❌ |
| a2 缩放 | ❌ | ❌ | ✅ |
| a3 竖屏裁切 | ❌ | ❌ | ✅ |
| a4 字幕 | ❌ | ❌ | ✅ |
| a5 Logo | ❌ | ❌ | ✅ |
| a6 调色 | ✅ | ❌ | ✅ |
| a7 重编码 | ❌ | ❌ | ✅ |
| a8 变速 0.8/1.2/1.5x | ✅✅✅ | ❌ | ✅✅✅ |
| a9 镜像 | error | ❌ | ❌ |
| a10 多片段拼接 | ❌ | ❌ | ✅(67%) |
| a11 转场 | ❌ | ❌ | ✅ |
| a12 组合攻击 | ✅ | ❌ | ❌ |

### 1.3 real 数据集（2.mkv 原片 + 1.mp4 解说，GT 7 段）

- **VDF**：error（音频指纹对"解说套电影"失效——解说叠加人声/重混音，无法与原片音频指纹匹配）。
- **VCSL**：recall=0（32x32 灰度特征在竖屏嵌入+黑边下系统性失效，FP 3 个，全 miss）。ORB 特征人工核对确认有效。
- **TransVCL**：recall=0（特征不匹配，同 synthetic）。

### 1.4 重要背景事实

- **TransVCL 的 0 分是"特征喂错"导致的预期失败**，不是引擎真实能力上限。本项目用 ORB-BOW 特征喂入，与官方 ISC/VCSL 预训练分布严重不匹配，输出全为低置信度噪声（conf 0.035~0.066）。论文宣称 65%+ 是在官方特征下。**要真实评估 TransVCL 需升级为稠密 CNN 特征**（复杂度高，本轮未做，用户决策：如实记录负面结果）。
- **VCSL 的 76% recall 是"本地最小实验实现"**（32x32 灰度 + 余弦 + Hough voting），非官方 VCSL/VTA 完整 benchmark。Precision 仅 25%，59 预测中 46 个 FP。
- **VDF 是官方实现**（vdf-cli 4.1.x 音频指纹 partial-clip detection），AI 匹配未开。
- **real 数据集三引擎全部失效**——这是本 benchmark 最重要的负面结论，说明当前任何单一方案都不能直接用于真实电影解说素材，需特征升级。

---

## 2. 分项评分（权重见任务书 §36）

评分原则：**用实测数据说话**。0~10 分。

| 维度 | 权重 | VDF | 依据 | TransVCL | 依据 | VCSL | 依据 |
|---|---:|---:|---|---:|---|---:|---|
| Accuracy | 35% | 4.6 | synthetic recall 46.2%、IoU@0.5 0.46、±1s 23%；real error | 1.0 | synthetic + real 均 recall 0（特征不匹配，非真实上限，故给 1 而非 0） | 4.5 | synthetic recall 76.2% 但 precision 25%、IoU@0.5 0.76、±1s 61%；real 0 |
| Robustness | 20% | 4.0 | 变速/调色/组合攻击 robust，但缩放/竖屏/字幕/Logo/重编码/转场/多片段全失；real 彻底失效 | 1.0 | 所有变换 0%；real 0% | 6.0 | 覆盖 9/14 变换类型，但对镜像、组合攻击、real 失效 |
| Speed | 15% | 8.0 | avg 1.2s/测试，音频指纹快；但 real 报错无耗时参考 | 4.0 | avg 5.0s/测试（CPU），无 GPU 时最慢 | 8.5 | avg 0.7s/测试，最快（CPU 1fps 抽帧） |
| Long-video scaling | 10% | 6.0 | 音频指纹线性扩展、内存可控（本机未跑 10/60/120min，推断）；2.1h real 直接 error | 3.5 | 特征缓存 + CPU 推理，2.1h 原片推理 5s 完成但结果无意义；需 GPU 才实用（推断） | 5.5 | 2.1h real 跑完（0.7s）但结果错误；相似度矩阵 [Nq×Nr] 内存随时长平方增长，120min 需评估（推断） |
| Integration | 10% | 7.5 | 自包含 CLI + 现成 JSON 解析，Process.Start 子进程即可接；需捆绑 ffmpeg | 4.5 | Python 子进程 + torch（~2GB）+ 特征管线自建，模型下载受阻 | 6.5 | opencv/numpy 轻依赖，可内嵌或子进程，特征管线可复用 |
| Cross-platform | 5% | 7.0 | Windows 实测通过；macOS .NET self-contained 官方产物，推断可跑 | 4.5 | torch mac MPS 支持但模型下载受阻，本机未实测 | 6.0 | opencv/numpy 全平台一致；Windows 实测，macOS 推断可跑 |
| License | 5% | 3.0 | **AGPLv3**，闭源商业产品有传染风险（进程隔离可弱化，需法律确认） | 9.0 | MIT，宽松可闭源商用 | 9.0 | MIT，宽松可闭源商用 |

**加权总分** = Σ(分 × 权重)

- **VDF** = 4.6×0.35 + 4.0×0.20 + 8.0×0.15 + 6.0×0.10 + 7.5×0.10 + 7.0×0.05 + 3.0×0.05
  = 1.61 + 0.80 + 1.20 + 0.60 + 0.75 + 0.35 + 0.15 = **5.46**
- **TransVCL** = 1.0×0.35 + 1.0×0.20 + 4.0×0.15 + 3.5×0.10 + 4.5×0.10 + 4.5×0.05 + 9.0×0.05
  = 0.35 + 0.20 + 0.60 + 0.35 + 0.45 + 0.225 + 0.45 = **2.63**
- **VCSL** = 4.5×0.35 + 6.0×0.20 + 8.5×0.15 + 5.5×0.10 + 6.5×0.10 + 6.0×0.05 + 9.0×0.05
  = 1.575 + 1.20 + 1.275 + 0.55 + 0.65 + 0.30 + 0.45 = **6.00**

**加权总分排名：VCSL 思路（6.00）> VDF（5.46）> TransVCL（2.63）**

---

## 3. 回答任务书 Q1~Q6

### Q1：哪一个方案最容易找到 Edited → Original 的对应时间位置？

- **synthetic**：VCSL 最容易（recall 76.2%），VDF 次之（46.2%），TransVCL 找不出（0%）。
- **real（关键）**：三者全失败。VDF error、VCSL 0、TransVCL 0。
- **结论**：目前**没有一个方案在真实素材上可用**。VCSL 思路最接近可用（只差特征），但必须换 ORB/强特征才有希望。

### Q2：哪一个方案对加工最鲁棒？

- **VDF**（音频指纹）：对变速(0.8/1.2/1.5x)、调色、组合攻击 robust；对画面型变换（缩放/竖屏/字幕/Logo/重编码）+ 转场/多片段 全失。real（解说重混音频）彻底失效。
- **VCSL**（32x32 视觉）：覆盖 9/14 变换，最广；镜像、组合攻击、real 失效。
- **TransVCL**：0/14。
- **结论**：**VCSL 覆盖最广**；VDF 只在"音频不变"场景 robust。两者在真实素材均不足。

### Q3：哪一个方案对长原片表现最好？

- 本机未跑任务书 §19 的 10/60/120min 梯度测试；real 原片 2.1h（7667s）提供了唯一长片数据点。
- **VDF**：2.1h 直接 error，长片无法输出（音频指纹对解说失效是本质局限，非时长问题）。音频指纹本身线性扩展（推断）。
- **VCSL**：2.1h 跑完（0.7s，因 1fps 抽帧），但结果错误；相似度矩阵 [Nq×Nr] 内存随时长平方增长，120min 需评估（推断）。
- **TransVCL**：2.1h CPU 推理 5s 完成但结果无意义；需 GPU 才实用（推断）。
- **结论**：长片是**未充分验证**维度。真实素材下三引擎都失败，无优胜者；VDF 因 real error 反而最差。

### Q4：哪一个方案运行速度最快？

- **VCSL** avg 0.7s/测试（CPU 1fps 抽帧）> **VDF** avg 1.2s/测试（音频指纹）> **TransVCL** avg 5.0s/测试（CPU torch）。
- **结论**：VCSL 最快，VDF 次之，TransVCL CPU 下最慢。

### Q5：哪一个方案最容易集成进 Windows/macOS/本地 GUI？

- **VDF**：自包含 CLI（无需 .NET SDK），JSON 输出，`Process.Start` 子进程即接；官方有 GUI/Web 参考。**工程上最省事**，但 AGPL 许可风险。
- **VCSL**：opencv/numpy 轻依赖，可内嵌 Python 或子进程，特征管线可复用。跨平台一致。
- **TransVCL**：torch(~2GB) + 自建特征管线 + 模型分发受阻，集成最重。
- **结论**：**VDF 工程集成最易**（除 license）；VCSL 次之且 license 安全；TransVCL 最重。

### Q6：最终应该 A（直接用 VDF）/ B（VDF+专业定位混合）/ C（放弃 VDF，用 TransVCL/VCSL 核心）？

**实测数据不支持纯 A**：VDF 在真实素材（解说套电影）直接 error，画面型变换 recall=0，无法作为独立定位引擎。

**实测数据不支持纯 C 用 TransVCL**：本机 0 输出，特征/算力门槛高。

**C 的 VCSL 思路**方向正确（synthetic recall 76%）但需特征升级才能在 real 用。

**结论**：**B（VDF + 专业定位算法混合），且以视觉定位为主、VDF 音频指纹为辅**。具体见结论 C。

---

## 4. 三个结论

### 结论 A：最佳纯算法引擎

**没有引擎在当前特征配置下能在真实素材上准确工作**，因此本 benchmark 的诚实结论是：**当前无合格纯算法引擎**。

- 在 synthetic 上，VCSL 思路（76% recall）显著优于 VDF（46%）和 TransVCL（0%）。
- 在 real 上三者全失败。
- **若必须在三者中选"最有潜力"**：VCSL 思路（视觉特征 + 时间对齐方向正确，只差特征质量）。TransVCL 理论上限高（论文 65%+）但需官方特征，本轮实测无法体现其能力。

### 结论 B：最佳工程底座

**VDF 是最佳工程底座（若 license 可接受）**：
- 自包含 CLI、现成 JSON、无运行时依赖、官方跨平台产物、1.2s 快。工程成本最低。
- **但** AGPLv3 对闭源商业产品是硬约束；且它作为"定位引擎"在真实素材失效，只能当"补充指纹模块"。

**VCSL 思路是最佳自研底座（license 安全）**：
- MIT、轻依赖、全平台一致、CPU 快、方向正确。可作核心引擎继续开发。
- 代价：需投入开发（特征升级 + 对齐算法）。

### 结论 C：最佳组合架构（推荐）

```
核心：自研视觉定位引擎（VCSL 思路升级）—— MIT 安全、方向正确
  ├── 帧特征：ORB 已验证可用 → 升级 DINOv2/CLIP 稠密特征（任务书 Candidate D 思路）
  ├── 相似度矩阵 + 时间对齐（VTA: HV/DTW + temporal consistency re-ranking）
  └── SSIM/ORB 精排验证，去 False Positive（当前 46 FP 的元凶）
      ↓
辅助：VDF 音频指纹（子进程，AGPL 隔离）—— 对"音频不变"场景（变速/调色）加速与补强
      ↓
FFmpeg 提取输出原片片段
```

**实测依据**：
1. real 素材三引擎全败 → **必须自研视觉核心并升级特征**，任何现成引擎直接当核心都不行。
2. VCSL 思路 synthetic recall 76% 证明"视觉特征 + 时间对齐"方向对，**高召回低精度**（46 FP）证明**必须加验证/精排层去 FP**——这正是任务书 Candidate D（temporal consistency re-ranking）要解决的问题。
3. ORB 特征人工核对在 real 上有效（GT 建立已验证），是特征升级的起点。
4. VDF 对变速/调色/组合攻击 100%，可作为音频指纹旁路补充，**但只能当辅助**，不能当核心。
5. TransVCL 本轮无法真实评估（特征不匹配），列为"研究参考"，不作为第一版底座。

---

## 5. 决策原则对照（任务书 §43）

- "VDF 准确率已经足够高 → 直接用 VDF"：**不满足**。real error，画面型变换 recall 0。
- "TransVCL 明显更准但工程复杂 → VDF 壳 + TransVCL 核心"：**不适用**。本机 TransVCL 无有效输出。
- "VCSL/VTA 更稳定 → 自研统一 Engine + VCSL/VTA 核心"：**最接近**，但需升级特征 + 加验证层。
- "所有方案都不够准确 → 先研究局部特征 + temporal consistency + 多级候选检索，再重新设计"：**这正是当前情形**。本报告结论 C 与该原则一致。

**因此本 benchmark 的落地含义**：不进入 GUI 开发；下一步是 STEP 2——把 VCSL 特征升级为 ORB/DINOv2 + 加 temporal re-ranking，在 real 数据集上复测，直到 real recall > 0 才算核心引擎可行。

---

## 6. 遗留项 / 未验证声明

- 长视频梯度（10/60/120min）未跑，Long-video 维度为推断。
- macOS 未实测，Cross-platform 维度为推断。
- TransVCL 的真实能力未测出（特征不匹配），得分不代表其论文级上限。
- VDF 的 AI matching（--ai-matching，DINOv2）未开，可能提升画面型变换召回，待测。
- VDF a2~a5/a7 recall=0 疑为阈值问题，可降 `--partial-clip-similarity` 复查（STEP 2）。
