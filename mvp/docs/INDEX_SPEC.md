# Index Spec — Original Video 特征索引与 FeatureStore

> 阶段：MVP Design（Stage 0）。定义 FeatureStore 抽象、索引生命周期、落盘格式、metadata schema、失效判定、长视频性能考量。禁止把 numpy/npy/npz/cache 路径直接暴露给 UI——一切经 FeatureStore。

## 1. FeatureStore 抽象

```python
class FeatureStore:                 # engine/feature_store
    def create_index(self, original_video: Path, backend: DeviceBackend,
                     progress: Callable[[IndexProgress], None] | None = None) -> IndexMeta
    def load_index(self, original_video: Path) -> IndexBundle          # (meta, feats[T,384])
    def validate_index(self, original_video: Path) -> IndexValidation  # VALID / INVALID(reason) / MISSING
    def invalidate_index(self, original_video: Path) -> None
    def get_metadata(self, original_video: Path) -> IndexMeta
    def delete_index(self, original_video: Path) -> None
```

未来允许 CPU / AMD GPU / macOS MPS 共享同一接口（backend 参数注入；见 DEVICE_BACKEND_SPEC.md）。

## 2. 索引落盘格式（建议目录结构）

```
<index_root>/<original_stem>.idx/
├── index.json        # IndexMeta (见 §3)
├── features.npy      # [T, 384] float32 L2-normalized CLS, 每行 = 一帧 @0.5fps
└── times.npy         # [T] 每帧绝对时间(s) —— 与 features 行对齐，供定位/预览换算
```

- `index_root`：用户数据目录（默认在 app_data/索引缓存），**非 work/**（研究临时路径）。
- `index.json` 保存全部 metadata；`features.npy`/`times.npy` 为二进制特征与时间轴。
- 一个 Original Video 对应一个独立索引目录；**重名冲突 → 额外 hash 后缀**。

## 3. Metadata schema（index.json）

```json
{
  "index_version": 1,
  "source_file": "C:/videos/original.mkv",
  "file_size": 5368709120,
  "duration": 7667.0,
  "file_hash": "sha256:<hex>",
  "feature_model": "dinov2_vits14",
  "feature_version": "handwritten_vits14_cls_384d@0.5fps_l2",
  "sampling_fps": 0.5,
  "feature_dim": 384,
  "num_frames": 3833,
  "backend": "cpu",
  "created_at": "2026-08-25T12:00:00Z",
  "device_machine_id": "<host-id>",
  "extractor": { "normalize": "l2", "resize": "518x518", "mean_std": "imagenet",
                  "preprocess_sha": "<hash of the exact preprocessing/config>" }
}
```

`feature_version` 是语义化运行版本号，加 `extractor.preprocess_sha` 以精确捕捉预处理配置。**任何一处变化都应触发索引失效**（见 §4）。

## 4. 失效判定（validate_index）

首次用同 Original 时 `load_index` 前必须 `validate_index`。**任一条件不满足 → INVALID**：

| 判据 | 对比 | 说明 |
|---|---|---|
| hash | 文件 sha256 | 内容变化（最硬校验） |
| duration | metadata.duration | 时长变化 |
| file_size | metadata.file_size | 文件大小变化 |
| model | feature_model | backbone 变化 |
| feature_version | feature_version | 特征/预处理/采样/归一化变化 |
| feature_dim | feature_dim | 维度变化 |
| extractor.preprocess_sha | 预处理哈希 | 归一化/尺寸/mean_std 变化 |
| sampling_fps | sampling_fps | 采样率变化 |

- 结果三态：`MISSING`（无索引→需 create）、`VALID`（直接 load）、`INVALID(reason)`（需重新 create，或提示）。**绝不在 INVALID 情况下复用旧特征。**
- 失效后旧索引：默认进入隔离命名空间（改名 .stale）或丢弃，由 H1 定；不能静默覆盖可用索引。

## 5. 生命周期与复用（禁止重复扫描原片）

```
首次: validate_index → MISSING → create_index(抽帧 0.5fps + embed + 落盘)
之后: validate_index → VALID  → load_index（秒级加载，不再重扫）
变化: validate_index → INVALID → create_index（重建成新版本）
```

**禁止每次都重新扫描完整原片**。UI 的 Index 页反映状态：Index Status / Build / Reuse / Progress。

## 6. 长视频性能考量（10 / 60 / 120 min）

- 0.5fps：120min → 3600 帧 → [3600,384] float32 ≈ 5.5 MB（特征）+ 时间轴。内存/磁盘可控。
- 建索引瓶颈在**抽帧 + DINOv2 推理**（CPU）。需测：Index Build Time、Feature Extraction Time、Localization Time、Total Time、RAM、Disk、CPU utilization（见 MVP_ROADMAP 性能基准）。
- 索引加载：numpy mmap 或整体载入，避免重复 I/O。
- **原片 seek/decode 必须走 FFmpeg**（见 media/ffmpeg），不得用 cv2.CAP_PROP_POS_MSEC。

## 7. 关键约束

- 索引按**绝对时间**（秒）存，不存帧号随意语义；`times.npy` 与 `features.npy` 行完全对齐。
- 特征必须 L2 归一化，与冻结管线一致（`cover=sim.max(axis=0)` 依赖归一化余弦）。
- 相似度定义、coverage 定义在**所有 backend** 上一致（CPU/AMD/MPS 数值一致性，见 DEVICE_BACKEND_SPEC）。
- 索引目录与产品数据目录分离；`.idx` 不放研究 `work/`，不放视频源目录。
