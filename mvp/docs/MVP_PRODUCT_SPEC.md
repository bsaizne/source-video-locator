# MVP Product Spec — Source Video Locator

> 阶段：MVP Design（Stage 0）。本文档定义产品定位、用户流程、能力边界、功能清单、数据契约、Confidence 原则与手动修正模型。**不**包含 GUI 代码实现（见 MVP_ARCHITECTURE.md / MVP_ROADMAP.md）。

## 1. 产品定位（One-liner）

**本地视频原片来源定位与提取工具**：给定完整原片（Original）与已剪辑视频（Edited），自动在 Original 中找到与 Edited 对应画面所在的时间位置，返回候选区间 + 置信度，用户确认/修正后由 FFmpeg 提取原片片段。

**明确不是**：自动电影解说生成器、自动视频编辑器、自动理解剧情的 AI、云端 AI 服务。所有处理在本机完成。

## 2. 目标用户与核心价值

- 用户：需要回查"这段剪辑来自哪部片子的哪个位置"的编辑/内容创作者、素材管理员、二创审核。
- 核心价值：把"人工肉眼找片段"变成"机器给候选 + 人确认"。**重点在可信度与可修正性，而非盲目自动化。**

## 3. 能力边界（Version 1 承诺）

软件**不承诺**"所有场景 100% 自动精确定位"。能力边界按两类声明：

### 高置信场景 = 连续镜头 / 连续片段（主能力）
自动完成：来源定位（候选窗）、起止时间、置信度、预览、提取。对应实测：连续单镜头段 IoU 0.5–0.75（s0/s1/s2/s3/s6），召回 7/7。

### 复杂场景 = 多镜头 montage / 多 source island（低置信）
**不伪装成精确自动定位**，明确标记：低置信度 / 疑似蒙太奇 / 建议人工确认。同时提供 Top candidate、Alternative candidates、Candidate time range、Manual edit。

默认行为：**宁可提示人工确认，也不输出一个虚假精确的高置信结果。**

## 4. 用户工作流

```
Home: 选 Original Video + Edited Video → Start Analysis
Index: 建立/复用 Original 索引（Index Build + Device Backend + Progress）
Results: 逐条结果（Edited 起止 / Original 起止 / Confidence / Reasons /
         Candidate rank / Alternatives / 预览 / Confirm / Manual Edit）
Export: Output folder + Export selected/all + Filename template + Progress
结束: 自动/手动结果 → FFmpeg 提取原片片段
```

## 5. 数据契约（核心结构）

### Result（每条最终结果）
```json
{
  "result_id": "uuid",
  "edited_segment": { "start": 0.0, "end": 0.0 },
  "original": { "candidate_start": 0.0, "candidate_end": 0.0 },
  "confidence": "HIGH",
  "confidence_score": 0.87,
  "reasons": ["rank1", "high_query_coverage", "stable_temporal_localization", "large_candidate_margin"],
  "candidate_rank": 1,
  "alternatives": [ { "candidate_start": 0.0, "candidate_end": 0.0, "confidence": "MEDIUM", "score": 0.6 } ],
  "source": "auto",
  "manual_override": false,
  "montage_flag": false,
  "extracted_path": null
}
```

### Candidate（检索层原始候选，内部结构）
```json
{
  "start": 0.0, "end": 0.0, "width": 0.0,
  "peak_sim": 0.0, "mean_sim": 0.0, "consistency": 0.0,
  "hit_count": 0, "n_reps": 0, "qcov": 0.0, "sim_std": 0.0,
  "rank_score": 0.0, "best_cover": 0.0
}
```
这些是工程化 Confidence 的**输入信号**（见 CONFIDENCE_DESIGN.md）。

### 手动修正后
```json
{
  "source": "manual",
  "manual_override": true,
  "original": { "candidate_start": 1237.0, "candidate_end": 1251.0 },
  "auto_result": { "original": {"candidate_start":1234.5,"candidate_end":1250.5}, "confidence": "HIGH", "confidence_score": 0.87 },
  "manual_timestamp": "2026-08-25T12:00:00Z"
}
```
**不覆盖原始自动结果**：auto result 与 manual result 都保留；`source` 记录来源；保留 modification timestamp。

## 6. Confidence Engineering（产品第一原则）

**不能把 cosine similarity 当置信度**——实测错误场景的 CLS 可能高于真正来源（s2 错窗 sim 0.726 > 正确区 0.558；s0/s1 正确区被暗色场景压到深 rank）。因此设计**工程化** Confidence，而非模型概率。

最低综合信号（见 CONFIDENCE_DESIGN.md 详版）：candidate rank、n_reps、candidate score、与第二候选的 margin、temporal consistency、coverage、fine localization stability、竞争性、是否疑似 montage、source window 是否异常。

输出三档：
```json
{ "confidence": "HIGH", "score": 0.87,
  "reasons": ["rank1","high_query_coverage","stable_temporal_localization","large_candidate_margin"] }
{ "confidence": "LOW", "score": 0.42,
  "reasons": ["multiple_similar_candidates","low_candidate_margin","possible_montage"] }
```

**重要**：`score` 是"工程 confidence score"，**不是**"模型概率"，禁止展示为具统计学意义的概率（UI 文案要规避百分比式概率暗示）。

## 7. 蒙太奇 / 多 source island 处理（默认行为）

检测到以下任一情况即触发降级：
- candidate 多峰、localization 不稳定、多个 source islands
- query coverage 分散、candidate margin 很低、source range 明显异常、多个高分候选相互竞争

处理：① 标记 `LOW CONFIDENCE`；② 标记 `POSSIBLE MONTAGE`（montage_flag=true）；③ 给出候选范围；④ 给出多个候选；⑤ 支持用户人工选择；⑥ 支持用户手动调整 Original start/end。

## 8. 用户手动修正（必支持）

1. 修改 Original Start
2. 修改 Original End
3. 播放 Original Preview
4. 播放 Edited Preview
5. 保存修改
6. 单独重新提取
7. 批量确认
8. 跳过当前结果
9. 选择候选 2 / 候选 3

## 9. 结果列表必须可解释

不要只显示 "Match 93%"。显示 Confidence（HIGH/MEDIUM/LOW）+ reason 列表，让用户知道**为何**软件觉得可信/不可信。

## 10. UI 页面（第一版，不复杂）

- **Home**：Original Video、Edited Video、Start Analysis。
- **Index**：Index Status、Build Index、Reuse Existing Index、Device Backend、Progress。
- **Results**：每条结果（Edited Start/End、Original Start/End、Confidence、Reasons、Candidate rank、Alternative candidates、Preview、Confirm、Manual Edit）。
- **Export**：Output folder、Export selected/all、Filename template、Progress。

## 11. 视频预览

结果页支持 Edited Preview 与 Original Preview；点击结果跳转到对应时间（Edited 00:01:32 / Original 01:23:41）。**是人工确认的基础。**

## 12. MVP 范围界定

**MVP（版本一）内**：连续镜头自动定位（主）+ 蒙太奇粗定位（标低置信、可手修、给候选范围）+ 索引复用 + Confidence 工程化 + FFmpeg 提取。

**MVP 外（增强项）**：VTA/sequence-level 二级精定位、VDF 音频指纹辅助、蒙太奇精确边界、场景身份模型（解 s0/s1 深 rank）、Windows AMD GPU、macOS Apple Silicon（见 DEVICE_BACKEND_SPEC / MVP_ROADMAP 硬件阶段）。

## 13. 已知限制（作为产品必须明示）

1. 连续镜头定位为当前主能力，非连续蒙太奇为低置信场景。
2. s4 类为当前已知困难边界案例（多-shot montage）。
3. DINOv2 CLS 对部分同类暗场景存在语义混淆（可能虚高置信，见 §6/§9 风险）。
4. Confidence 不得仅依赖 cosine。
5. Windows AMD GPU 后端可用性必须实机验证（当前设备 RX 6750 GRE 的 ROCm/Windows 支持不能假设成立）。
6. macOS Apple Silicon 必须实机验证；macOS Intel 不支持。

## 14. 产品数据结构存储

每条最终结果保存原始自动结果、手动覆盖结果、修改时间戳；`manual_override` 标记手动修正；不因覆盖而丢失自动结果。

## 15. 部署方式

本地单机。无需云服务器、账号系统、在线 API、云端上传。所有视频本地处理。
