# MVP Architecture — Source Video Locator

> 阶段：MVP Design（Stage 0）。定义分层架构、模块结构、模块→现有研究代码映射（REUSE/REFACTOR/REWRITE/RESEARCH_ONLY）、核心接口、数据流、以及从 GT 驱动 benchmark 到无 GT 产品运行时的关键落差点。

## 1. 分层架构（自上而下）

```
+----------------------------+
| UI (PySide6)               |  Home / Index / Results / Export
+----------------------------+
| Application Service        |  用例编排、持久化 Result、会话状态
+----------------------------+
| Localization Engine        |  edited 切分 → retrieval → clustering → rerank → finloc → confidence
+----------------------------+
| Feature Store              |  Original 索引 create/load/validate/invalidate/delete
+----------------------------+
| Device Backend             |  CPU / ROCm / MPS（+未来 CUDA），统一推理接口
+----------------------------+
| FFmpeg (media/ffmpeg)      |  metadata / seek / 抽帧(dec帧) / clip 提取（生产级）
+----------------------------+
```

**UI 不允许直接接触** torch、numpy、FFmpeg subprocess、feature cache、model files。一切经 Application Service → Engine → FeatureStore → DeviceBackend / FFmpeg。

## 2. 模块结构（建议树）

```
mvp/src/
├── app/            # Qt 视图(View) + ViewModel，无业务逻辑
├── domain/         # 纯数据模型: Result/Candidate/Confidence/IndexMeta/Enums; 无 IO
├── engine/
│   ├── segment/    # 【新增产品胶水】edited shot 切分(无GT时定义查询单元)
│   ├── retrieval/  # Global Candidate Retrieval  (REUSE core)
│   ├── clustering/ # Candidate Clustering 连续性  (REUSE core)
│   ├── ranking/    # ExpA n_reps rerank v2_score (REUSE core)
│   ├── localization/ # finloc: longest_run + montage 检测分支 (REUSE core)
│   ├── confidence/   # ConfidenceEngine  (REWRITE/NEW, 产品核心)
│   └── feature_store/ # FeatureStore  (REFACTOR)
├── device/         # CPUBackend/ROCmBackend/MPSBackend (+CUDA future)
├── media/ffmpeg/   # FFmpegIO: metadata/seek/frame/clip_extract  (REWRITE)
├── infrastructure/ # 持久化、配置、日志、错误模型、路径解析
└── main.py
```

## 3. 核心接口（接口签名，非最终实现）

### DeviceBackend（见 DEVICE_BACKEND_SPEC.md）
```python
class DeviceBackend(Protocol):
    def is_available(self) -> bool: ...
    def device_name(self) -> str: ...          # "cpu" / "cuda:0" / "mps" / "rocm:0" / "AMD_GPU_BACKEND_BLOCKED"
    def memory_info(self) -> dict: ...
    def load_feature_model(self) -> Any: ...    # 返回 DinoV2Small (eval, 已放 device)
    def embed_frames(self, bgr_frames: list[np.ndarray], batch_size: int) -> np.ndarray: ...
    def cleanup(self) -> None: ...
```

### FeatureStore（见 INDEX_SPEC.md）
```python
class FeatureStore:
    def create_index(self, original_video: Path, backend: DeviceBackend, progress=None) -> IndexMeta: ...
    def load_index(self, original_video: Path) -> tuple[IndexMeta, np.ndarray]: ...
    def validate_index(self, original_video: Path) -> IndexValidation: ...  # hash/duration/size/model/version
    def invalidate_index(self, original_video: Path) -> None: ...
    def get_metadata(self, original_video: Path) -> IndexMeta: ...
    def delete_index(self, original_video: Path) -> None: ...
```

### Localization Engine
```python
class LocalizationEngine:
    def locate(self, original_meta: IndexMeta, orig_feats: np.ndarray,
               edited_video: Path, cfg: PipelineConfig) -> list[Result]: ...
# 内部: analyze(edited) -> shot_segments; per_segment -> retrieve -> cluster -> rerank
#        -> finloc(longest_run|montage branch) -> confidence -> Result
```

### Domain models（domain/）
```python
@dataclass
class Candidate: start, end, width, peak_sim, mean_sim, consistency, hit_count, n_reps, qcov, sim_std, rank_score, best_cover
@dataclass
class Confidence: level: Literal["HIGH","MEDIUM","LOW"], score: float, reasons: list[str]
@dataclass
class Result: edited_segment, original, confidence, candidate_rank, alternatives, source, manual_override, montage_flag, extracted_path
```

## 4. 现有代码 → 产品映射（REUSE / REFACTOR / REWRITE / RESEARCH_ONLY）

> 依据：`src/experiments/*` 实际代码（我已在设计前核对）。研究代码与结果**保留不删**，但**不得进入 MVP 默认执行链路**。

| 现有文件 | 关键内容 | 标记 | 处理方式 |
|---|---|---|---|
| `src/experiments/dinov2_features.py` | 手写 ViT-S/14（`DinoV2Small` + `_PatchEmbed/_Mlp/_Block/_Attention`）、`_imagenet_preprocess`、`extract_dinov2_features`、`_get_model` | **REUSE**（模型+预处理+前向）/ **REFACTOR**（推理入 DeviceBackend） | 模型与前向是冻结 backbone，**不得改**；`_get_model`/`extract_*` 重写进 `device/`；残基沿用，改 device 注入 + 进度回调 |
| `src/experiments/dinov2_features.py: sample_frames` | cv2.VideoCapture 按 fps 步进采样 | **REWRITE** → `media/ffmpeg` | 生产级随机定位禁用 cv2.CAP_PROP_POS_MSEC（MKV 可致从头解码）；改用 FFmpeg seek/decode |
| `src/experiments/fine_localization.py: longest_run` | cont 覆盖率最长 run | **REUSE** | 纯 numpy、冻结 finloc 基线 #8；拷入 `engine/localization`（去研究依赖） |
| `src/experiments/fine_localization.py: narrow` | sim→cover.max(axis=0)→±1平滑→mask→longest_run→traj | **REFACTOR** | 定位**流程**沿用；解耦 TransVCL JSON/gid/GT；候选窗来自 retrieval/clustering；`_dp_path` 未用为主信号 |
| `src/experiments/ta.py: cosine_similarity` | 余弦相似度 | **REUSE** | 检索/定位相似度定义，冻结。拷入公共 util |
| `src/experiments/ta.py: _dp_path` | DP 单调对齐（TA） | **RESEARCH_ONLY** | 不进默认 runtime；align=dinov2_ta 已 blocked，留研究 |
| `src/experiments/candidate_retrieval_14a.py` | 全局 Top-K 检索 + 时间近邻聚簇候选窗 | **REUSE**（检索算法）+ **REFACTOR**（IO/工作流） | 检索逻辑沿用；去掉 per-GT/gid/硬编码路径；改为"入力 edited 段+索引→candidates" |
| `src/experiments/candidate_clustering_14a1.py` | 连续性修正 + 无巨窗（≤60s） | **REUSE**（聚类算法）+ **REFACTOR**（IO） | 连续性判据沿用；去 benchmark 全局 |
| `src/experiments/phase16b_rerank.py: v2_score` | `mean*sqrt(hit)*(0.5+0.5*cons)*n_reps^alpha` | **REUSE（公式）/ REFACTOR（实验壳）** | 冻结 ranking 基线 #6；从 harness 提出为 `engine/ranking` |
| `src/experiments/query_density_14c.py` | 管线驱动器（pad/query 密度/检索+finloc） | **RESEARCH_ONLY** | 整体是 GT 驱动实验脚本；其编排的**步骤**被 Engine 复用；脚本本身不产 |
| `src/experiments/phase19_cut_coverage.py` 等 17A/18/19 | 已证伪 finloc 变体 | **RESEARCH_ONLY** | 保留溯源，不进 runtime |
| `src/experiments/patch_features.py / phase16b_patch / phase16b_multiscale` | patch / multi-scale 特征 | **RESEARCH_ONLY** | 已证伪，不进 runtime |
| `src/adapters/vdf.py` 等 | VDF 音频指纹（AGPL） | **RESEARCH_ONLY / 不入 MVP** | 见 THIRD_PARTY_NOTICES，MVP 规避 VDF AGPL |

**必须从 benchmark 去掉再进产品的**：benchmark-oriented globals、硬编码 gid、实验临时路径（`work/`、`datasets/real/...`）、测试专用参数（pad、GT 窗口、thresh 常量）、GT 驱动查询区间假设。

## 5. 关键落差点：GT 驱动 benchmark → 无 GT 产品运行时

**benchmark 用 GT 窗口（±0.5s query 裁剪 + pad±4s）定义"编辑查询段"**；产品运行时**没有 GT**，必须自定查询单元。这是本阶段最大的真实工程点：

- 方案：**新增 `engine/segment` 轻量 shot 切分**——对 edited 视频抽帧 @2fps → 用同一 DINOv2 CLS 相邻帧余弦距离做**编辑侧 shot 边界检测**，得到一批 edited 查询段（每段即一个查询单元）。
- 每段走冻结管线：retrieval（Top-K）→ clustering → n_reps rerank → finloc(longest_run / montage 分支) → confidence。
- **产品胶水**：edited shot 段本身**非冻结基线**，是新写的产品化代码（复用 cosine + 现有特征），但**不改变冻结算法**（detachment 仅在"定义查询单元"这一层；相似度/检索/排序/定位/置信语义不变）。

> 说明：shot 切分阈值是产品化参数（非冻结 finloc 阈值），需在 Stage 1 用真实 edited 视频标定，与算法研究分开。

## 6. 关键落差点：montage 分支（只检测到才激活）

finloc 主定位 = `longest_run`（冻结 #8），**全局保留**，供连续镜头段（s0–s3/s6）。新增**并行分支**：

```
finloc(候选窗):
  runs = 阈值化 per-orig coverage(SMOOTH) 得到所有高匹配 run 列表 + 其间 gap
  montage_suspicion = 多岛(multiple runs) 且 query 覆盖分散 且 margin 低
  if montage_suspicion:
      输出候选窗范围 + alternatives + LOW CONFIDENCE + montage_flag=true
      # 不输出虚假精确单边界
  else:
      用 longest_run 输出精确边界 + Confidence
```

> 二级 sequence-level 定位（VTA/DTW）**不是 MVP 默认 runtime**；只有未来真实数据证明 montage 错误率显著影响产品价值，才单独开启（见 §向 Future）。MVP 的 montage 处理是"检测 + 降级 + 人工"，不是"精确自动解 montage"。

## 7. 数据流（端到端）

```
Original Video ──(FFmpeg metadata)──> IndexMeta(hash,duration,size)
     │
     └─(media.ffmpeg 抽帧 @0.5fps)─> DeviceBackend.embed_frames ─> [T,384] L2-norm
          └─(FeatureStore.create_index)─> index 落盘(.npy + index.json)

Edited Video ──(engine.segment shot 切分)─> [Seg0, Seg1, ...]
   per Seg: Retrieval(Top-K) → Clustering(≤60s) → n_reps rerank → finloc → Confidence → Result

Result ──(App Service)──> domain.Result ──(infrastructure 持久化 json/sqlite)
     └─(用户确认/手修)──> manual_override / alternatives
          └─(media.ffmpeg.clip_extract)──> 原片片段
```

## 8. 冻结基线（不可在产品中随意改动）

1. DINOv2 ViT-S/14 CLS 384D（手写模型 + 预处理 + L2 归一）
2. Original 0.5fps 特征索引
3. Edited 特征提取
4. Global Candidate Retrieval
5. Candidate Clustering
6. ExpA n_reps Candidate Rerank（alpha=0.5）
7. per-original max-over-query coverage
8. longest_run Fine Localization
9. Confidence Engineering（见 CONFIDENCE_DESIGN.md）
10. FFmpeg Clip Extraction

**明确不进入默认 runtime**：ORB-BOW、TransVCL+ORB-BOW、pooled patch、CLS+patch multi-scale、per-query argmax multi-segment、per-query neighborhood voting 作为主定位信号、cut-aware coverage localization、继续调 finloc threshold/gap/cut threshold、大规模参数 sweep、新增视觉 backbone、新增 VLM/LLM runtime inference。

## 9. 研究代码处理原则

- `experiments/`、`diagnostics/` 保持**不动**，仅作研究追溯（REUSE 的只取函数/公式，不搬脚本）。
- 产品代码与研究代码**物理隔离**（mvp/src 不 import benchmark/src/experiments；REUSE 通过"提取函数到 engine/，删除研究依赖"实现）。
- GT 驱动的查询窗口假设与产品无关；产品运行时按 §5 自定查询段。

## 10. DeviceBackend 运行时一致性

GPU 仅加速，**不得改变算法逻辑**。CPU/AMD/MPS 必须产出一致的 feature dim、similarity 语义、retrieval、ranking、localization、confidence。若出现明显数值差异必须记录（见 DEVICE_BACKEND_SPEC.md §一致性与验收）。
