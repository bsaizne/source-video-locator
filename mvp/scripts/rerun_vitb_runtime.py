"""ViT-B/14 全量索引 + 四片 runtime 回归(研究侧 harness; 零 mvp/src 改动)。

目的: 「该不该换更大基座(ViT-S→ViT-B)」的**产品级定论** —— feature_upgrade_v4 探针只做了
局部窗口嵌入(ViT-B 侧非全片索引), 无法回答「ViT-B 全量索引 + 生产管线」下四片三指标的变化。

做法(全部通过 env + config + 研究侧 monkey-patch, 不改 mvp/src):
  * SVL_DATA_DIR → work/vitb_data(完全隔离: 索引/编辑缓存/导出都在此, 不碰产品与历史索引);
  * device.onnx_model → work/vitb_asset/dinov2_cls_768.onnx; dml_batch_size=1(实测 7.0fps 最优);
  * FeatureStore 子类: feature_version = handwritten_vitb14_cls_768d@1_l2+scn1+evt1,
    create 后把 index.json 的 feature_model 修正为 dinov2_vitb14, validate 接受 768d/ViT-B;
  * 其余全走生产 SourceLocatorService.locate(默认 config: 两级切分+白闪守卫、patch v2 重排、事件扩池等)。

诚实边界:
  - patch 重排仍是 **ViT-S patch** 资产(产品目录无 patch ONNX → CPU torch ViT-S 回退), 即
    CLS=ViT-B / patch=ViT-S 的混合口径; 与基线批(rerun_*_perfopt, 全 ViT-S)对照时须记此差异,
    但该差异对两侧"是否换基座"的结论不构成偏置(基线同配置)。
  - 本 harness 不修改 mvp/src; 若结论支持 ViT-B, 正式接入需另做 dim 参数化(索引 schema/validate)
    与其回归测试。

运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/rerun_vitb_runtime.py [case]
  (case ∈ 2mkv|test1|test2|test3; 省略=四片全跑; SVL_FORCE_RERUN=1 强制重跑)
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

BENCH = Path(r"D:\claudework\benchmark")
DATA = BENCH / "work" / "vitb_data"
ONNX = BENCH / "work" / "vitb_asset" / "dinov2_cls_768.onnx"
VITB_FV = "handwritten_vitb14_cls_768d@1_l2+scn1+evt1"

os.environ["SVL_DATA_DIR"] = str(DATA)
os.environ["SVL_DML_MODEL"] = str(ONNX)
os.environ["MEDIA_FFMPEG"] = str(BENCH / "tools" / "ffmpeg.exe")
os.environ["MEDIA_FFPROBE"] = (r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages"
                               r"\static_ffmpeg\bin\win32\ffprobe.exe")

sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp"))
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))

import engine.feature_store.feature_store as fsmod  # noqa: E402
from domain import IndexMeta, IndexValidation, IndexValidationStatus  # noqa: E402
import app.locator_service as ls  # noqa: E402
from app.locator_service import SourceLocatorService  # noqa: E402
from infrastructure.config import load_config  # noqa: E402

CASES = {
    "2mkv":  {"edited": r"D:\video\1.mp4", "original": r"D:\video\2.mkv"},
    "test1": {"edited": r"D:\ProjectXIXI\test1\test1-ed.mp4",
              "original": r"D:\ProjectXIXI\test1\test1-om.mkv"},
    "test2": {"edited": r"D:\ProjectXIXI\test2\tset2-ed.mp4",
              "original": r"D:\ProjectXIXI\test2\test2-om.mp4"},
    "test3": {"edited": r"D:\ProjectXIXI\test3\test3-ed.mp4",
              "original": r"D:\ProjectXIXI\test3\test3-om.mp4"},
}


class ViTBFeatureStore(fsmod.FeatureStore):
    """ViT-B 索引生命周期: 独立 feature_version + 接受 768d/dinov2_vitb14 的 validate。"""

    def __init__(self, *a, **kw):
        kw.setdefault("feature_version", VITB_FV)
        super().__init__(*a, **kw)

    def create_index(self, original_video, backend, progress=None):
        meta = super().create_index(original_video, backend, progress=progress)
        p = self.index_dir(original_video) / "index.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        d["feature_model"] = "dinov2_vitb14"
        d["feature_version"] = VITB_FV
        p.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
        return IndexMeta.from_dict(d)

    def validate_index(self, original_video):
        v = super().validate_index(original_video)
        if v.status is IndexValidationStatus.VALID or v.reason != "feature model changed":
            return v
        try:
            meta = self._read_meta(self.index_dir(original_video))
        except Exception:
            return v
        if not (meta.feature_model == "dinov2_vitb14" and meta.feature_dim == 768
                and meta.feature_version == self.feature_version):
            return v
        if meta.sampling_fps != self.sampling_fps:
            return IndexValidation(IndexValidationStatus.INVALID, "sampling fps changed")
        cur = "sha256:" + self.ffmpeg.hash_file(Path(original_video))
        if cur != meta.file_hash:
            return IndexValidation(IndexValidationStatus.INVALID, "content hash changed")
        return IndexValidation(IndexValidationStatus.VALID)


ls.FeatureStore = ViTBFeatureStore


class _Progress:
    def __init__(self):
        self.t_last = 0.0
        self.stage = None

    def __call__(self, ev):
        now = time.monotonic()
        stage = getattr(getattr(ev, "stage", None), "value", "?")
        if stage != self.stage or now - self.t_last > 15:
            self.stage = stage
            self.t_last = now
            print("    [%s] %s %s/%s %s" % (stage, getattr(ev, "message", ""),
                                            getattr(ev, "current", 0),
                                            getattr(ev, "total", 0) or "?", ""), flush=True)


def main() -> int:
    only = sys.argv[1] if len(sys.argv) > 1 else None
    if not ONNX.exists():
        print("MISSING ViT-B ONNX: %s (run export_dml_model_vitb.py)" % ONNX)
        return 1
    DATA.mkdir(parents=True, exist_ok=True)

    cfg = load_config()
    cfg.data_dir = str(DATA)
    cfg.device.preferred = "directml"
    cfg.device.onnx_model = str(ONNX)
    cfg.device.dml_batch_size = 1
    print("cfg: data_dir=%s" % cfg.data_dir, flush=True)
    print("cfg: onnx=%s batch=%s preferred=%s index_fps=%s patch_v2=%s"
          % (cfg.device.onnx_model, cfg.device.dml_batch_size, cfg.device.preferred,
             cfg.pipeline.index_sampling_fps, cfg.pipeline.patch_v2_enabled), flush=True)

    srv = SourceLocatorService(config=cfg)
    b = srv.backend
    print("BACKEND_SELECTED type=%s device=%s dtype=%s model=%s"
          % (type(b).__name__, getattr(b, "device_name", lambda: "?")(),
             getattr(b, "device_type", lambda: "?")(),
             getattr(getattr(b, "model_path", None), "name", "?")), flush=True)
    if not isinstance(srv.store, ViTBFeatureStore):
        print("WARNING: store is not ViTBFeatureStore (%s)" % type(srv.store))
        return 1

    for name, paths in CASES.items():
        if only and name != only:
            continue
        out = BENCH / "work" / ("vitb_%s.results.json" % name)
        if out.exists() and not os.environ.get("SVL_FORCE_RERUN"):
            print("  %s: skip (result exists)" % name, flush=True)
            continue
        print("\n=== %s : ViT-B full index + locate ===" % name, flush=True)
        t0 = time.monotonic()
        try:
            batch = srv.locate(paths["edited"], paths["original"],
                               on_progress=_Progress())
            out.write_text(json.dumps(batch.to_dict(), ensure_ascii=False, indent=1),
                           encoding="utf-8")
            n_high = sum(1 for r in batch.results
                         if getattr(getattr(r, "confidence", None), "level", None) is not None
                         and r.confidence.level.value == "HIGH")
            meta = srv.store.get_metadata(paths["original"])
            print("  %s: %d 段 HIGH=%d elapsed=%.1fs | index frames=%d dim=%d model=%s"
                  % (name, len(batch.results), n_high, time.monotonic() - t0,
                     meta.num_frames, meta.feature_dim, meta.feature_model), flush=True)
        except Exception as exc:
            import traceback
            print("  %s FAILED: %s: %s" % (name, type(exc).__name__, exc), flush=True)
            traceback.print_exc()
    print("\nALL DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
