# 竞品原片侧切分：挖到了，答案是「他们也没有专门的」 (2026-10-19)

> 口令：「挖一下看看，可能当时挖的时候也没注意到这些，挖完就交接然后关机吧」
> **全程只读**（竞品仓零写入、`mvp/src` 零改动）。材料 = `D:\claudework\cutmatch-analysis\data\{competitor_profile_v1.json, nuitka_dict_constants.json}`。

## 0. 一句话结论

**竞品原片侧没有独立的切分算法 —— 他们的原片场景表就是 TransNetV2 的产物，和我们昨天测的完全同一套东西。**

所以「竞品在**原片侧**能精确确定边界」这个假设，**不成立**。他们的优势只在编辑侧（解说片）成立。

## 1. 证据链（四条，逐条可复现）

### ① 全 profile 里只有一套切分模型，而它**不区分**原片/编辑

`competitor_profile_v1.json` → `scene_detection`：

```
scene_detection.model                    = "TransNetV2"     (确证)
scene_detection.decode.width/height      = 48 / 27          (与 we 一致)
scene_detection.decode.window/stride     = 100 / 50         (官方口径)
scene_detection.predictions.threshold    = 0.5             (官方口径)
scene_detection.predictions.min_gap      = 8
```

**只有一份** `scene_detection` 配置，没有 "source 版" 与 "commentary 版" 之分。

### ② 参数命名里，**切分类全部是 `commentary_*`，原片侧只有两个「位移/守卫」参数**

从 `pipeline.options`（180 个叶子参数）里筛 `source|boundary|scene`：

| 参数 | 值 | 归属 |
|---|---|---|
| `commentary_scene_*` / `commentary_boundary_refine_*` | 全族 26 项 | **编辑侧**（切分+精修+守卫） |
| `source_boundary_guard_frames` | **0** | 原片侧，**关着** |
| `source_boundary_refine_max_shift` | **2** 帧 | 原片侧，**只允许挪 2 帧** |
| `respect_source_scene_end` | **false** | 原片侧，**不遵守场景末尾** |

**`nuitka_dict_constants.json` 的计数对照**：`commentary_scene` 出现 **26** 次，`source_scene` 只出现 **3** 次，
而那 3 次全是**阶段名/ETA 表/数据类名**，**没有一个是边界判据参数**。

### ③ 原片侧切分是个**独立但无参数**的阶段，且成本与编辑侧完全相同

`cutmatch.processing.progress.tracker`（ETA 表）：

```
["source_scene",      {"gpu": 220, "cpu": 75}]
["commentary_scene",  {"gpu": 220, "cpu": 75}]
["source_features",   {"gpu": 30,  "cpu": 8}]
```

- **`source_scene` 与 `commentary_scene` 的 ETA 完全相同（220s GPU / 75s CPU）** ⇒ **同一个模型跑两遍**，不是一个更重的原片侧方案。
- `source_scene` 在 `source_features` **之前** ⇒ **原片场景表确实是切分出来的，不是特征聚合出来的**。

### ④ 原片侧的「精修」存在，但被限死在 2 帧

`source_boundary_refine_max_shift = 2`（对比编辑侧 `commentary_boundary_refine_max_move_frames = 16`）。

⇒ 他们对原片边界只做 **±2 帧（约 0.08s）的微调**，不做「补漏切」。而 `respect_source_scene_end=false` 说明
**原片场景末尾在他们的定位管线里甚至不被严格遵守** —— 原片场景表在他们那儿的地位比我们想的低。

## 2. 这直接解释了我们昨天的探针结果

| 我们的发现（scn5 探针） | 竞品证据 | 是否自洽 |
|---|---|---|
| TN 原片侧只出 **375** 个切点（我方 912） | `scene_detection.threshold=0.5`、**无原片侧补充判据** | ✅ 完全自洽 |
| 15 段真漏切里只救 1 个 | 同上，且 `source_boundary_guard_frames=0`、`max_shift=2` | ✅ 完全自洽 |
| TN 对「同场景多机位」不敏感 | 他们同样无解，只能靠 `offset_refine` 在下游补 | ✅ 完全自洽 |

**他们把功夫下在别处了**：`offset_refine_*` 全族（DTW / topk rerank / start_window，共 12 个参数）
+ `long_scene_*` 全族（自适应采样/探测窗，7 个参数）。**即「场景切得粗，但定位对了再精修」**，
而不是「把场景切准」。这与我们 G5/G6 的旧结论一致，现在有了参数级确证。

## 3. 对我方路线的影响（我的判断）

**「原片侧切分不如竞品」这个担忧可以彻底关闭了。** 不是「我们没挖到」，是**他们也没有**。

顺带订正一条旧档案口径：`FINDINGS_TRANSNETV2_SEGMENTATION.md` §6.1 写的
「未测 TransNetV2 用于**原片侧**场景表/事件表（**竞品可能在原片侧用它**）」——
现在答案是：**他们确实用它，而且只用了它**。所以那个「可能」已经关闭，结论是**双方原片侧等价**。

⇒ 这 15 段漏切是**共性问题**，不是我们落后。要解决只能引入新信息源（主体/人脸/音频），
而不能靠「对标竞品」。

## 4. 可复现

```python
import json
p = json.load(open(r"D:\claudework\cutmatch-analysis\data\competitor_profile_v1.json", encoding="utf-8"))
print(p["scene_detection"]["model"])                    # TransNetV2
print(p["precise_options"]["source_boundary_refine_max_shift"]["value"])   # 2
print(p["precise_options"]["respect_source_scene_end"]["value"])          # False
k = json.load(open(r"D:\claudework\cutmatch-analysis\data\nuitka_dict_constants.json", encoding="utf-8"))
# ETA 表里 source_scene 与 commentary_scene 同值 220/75
```

## 5. 未做 / 未能证

- **没有跑竞品产品**（授权需卡密 + 模型走服务器 lease），所有结论基于静态常量/profile。
- `source_scene` 阶段用的**具体阈值是否与编辑侧相同**（都 0.5）无法从常量区分——只有一份配置，
  但运行时是否按 `sensitivity=18` 动态调整**未证**（`detect_defaults.sensitivity` 语义未定）。
- `scene_detection.detect_defaults.*`（sensitivity=18 / sample_stride=3 / max_width=320 / proxy_height=720）
  是**检测入口的默认值**，与 `predictions.threshold` 的关系未定论。**这两者是否共同作用于原片侧，未证。**
