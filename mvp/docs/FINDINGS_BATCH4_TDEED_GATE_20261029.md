# FINDINGS — 批次4 可行性闸门：T-DEED 能不能当修复链的新腿（2026-10-29）

> 来源：调研 v2 批次4「T-DEED（arturxe2/T-DEED）可当修复链新腿；监督形式抄 UniVTG soft 边界标签」。
> 按项目纪律先做门槛（权重/环境/领域/数据），不先写代码。

## 结论

**不可落地。** 三道门同时不过：**权重不可达**（只在 Google Drive）、**环境冲突**（锁 torch 2.3.1 + CUDA）、
**领域与数据量不匹配**（体育赛事事件 spotting，无自然视频权重；我们只有 150 条 GT、CPU-only）。
⇒ 不作为修复链新腿，**关闭该候选**。可复用的是它的**监督形式思路**，但那需要自训模型（见 §5）。

## 逐门证据

| 门 | 检查 | 结果 |
|---|---|---|
| **权重** | 仓库 README 给的 checkpoints 链接（Google Drive） | `curl: (28) Failed to connect to drive.google.com:443`（21s 超时）⇒ 不可达 |
| | GitHub Releases（v1.0 / v2.0） | 两个 release **均无 assets** |
| | `checkpoints/` 目录 | 只有 `FineDiving/` 空占位，无权重文件 |
| | HuggingFace 镜像 | `huggingface.co` 不可达；`hf-mirror.com` 上搜索无 T-DEED 官方权重 |
| **环境** | `requirements.txt` | `torch==2.3.1` + `nvidia-cuda-*` 全套（CUDA 12.1 wheel），`torchvision==0.18.1` |
| | 本项目 venv | `torch 2.13.0+cpu`（DML 走 onnxruntime，**无 CUDA**）⇒ 装它等于在冻结环境里降级 torch，不可接受；另建 venv 也没有权重可跑 |
| **领域** | 仓库/论文覆盖数据集 | FigureSkatingComp/Perf、FineDiving、FineGym、Tennis、SoccerNet、SoccerNetBall —— 全是**体育事件 spotting**（"事件瞬间"），不是"编辑片段→原片起点"的定位任务 |
| **数据/算力** | 我们可训练的量 | GT 150 行（四片），无独立验证集；本机仅 CPU 推理（AMD 无 CUDA）⇒ 微调 T-DEED 量级不成立 |
| 许可 | repo license | **GPL-3.0**（属性记录；按 2026-10-24 非商业化裁定不作排除条件，但与产品分发相关） |

## 为什么"权重不可达"是决定性的

T-DEED 的价值来自在**大规模标注数据集**上预训练的时序编码器-解码器；
没有权重，它退化为"在 150 条 GT 上从零训一个小模型"——既没有它的方法优势，
也远低于我们现役手工修复链（12 条腿 + XFeat + 稀疏候选）的成熟度。

## 5. 残余可选项（未做，需拍板）

1. **抄监督形式**：把 UniVTG 的 soft boundary label 用在**我们自己的**候选打分头上
   （不引入 T-DEED 权重）。数据量仍是 150 行 ⇒ 只能做留一片交叉验证，
   预期收益低（我们已有 mAP@δ 尺子可当场判负）。**不建议**。
2. **再等权重**：若作者后续把 checkpoint 放到 GitHub Release / HF，本结论需重评
   （届时仍需解决 CUDA 环境与领域迁移两道门）。

## 复现

```bash
curl -sS -L "https://api.github.com/repos/arturxe2/T-DEED/releases"          # 0 assets
curl -sS -L "https://api.github.com/repos/arturxe2/T-DEED/contents/checkpoints"  # 仅空目录
curl -sS -o /dev/null -w "%{http_code}\n" https://drive.google.com/drive/folders/1sxZalU_hCwL8ITZCU9VqSWE8dB94lJty  # 000
curl -sS -L "https://raw.githubusercontent.com/arturxe2/T-DEED/main/requirements.txt"  # torch==2.3.1 + cuda wheels
```
