"""场景表 + 事件表回填:对既有 @1_l2 索引目录补 scenes.npy/scene_feats.npy +
events.npy/event_feats.npy。

场景表由缓存 features.npy/times.npy 经 FeatureStore._build_scene_table 确定性派生,
事件表由场景表经 _build_event_table 派生(方向 A 完整阶段 2026-09-05 立项);
两者与 create_index 全量重建逐字节等价;回填同时把 index.json 的 feature_version
更新为含 +scn1+evt1 的新版本(等效于版本 bump 触发的重建,但免 GPU 重 embed)。
回填后 validate_index → VALID。

运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/backfill_scene_tables.py [idx_dir ...]
  缺省处理 App 索引根下全部 *.idx(不含 .stale)。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BENCH / "mvp" / "src"))

from engine.feature_store import FeatureStore  # noqa: E402

APP_INDEX_ROOT = Path("C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/index")


def main() -> int:
    dirs = [Path(a) for a in sys.argv[1:]] or \
        sorted(p for p in APP_INDEX_ROOT.glob("*.idx") if p.is_dir())
    import numpy as np
    for d in dirs:
        meta_p = d / "index.json"
        if not meta_p.exists() or not (d / "features.npy").exists():
            print(f"skip {d.name}: not a feature index")
            continue
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
        fps = float(meta.get("sampling_fps", 1.0))
        store = FeatureStore(None, d.parent, sampling_fps=fps)  # 只用其派生函数,不碰 ffmpeg
        fv = meta.get("feature_version", "")
        if (d / "scenes.npy").exists() and (d / "events.npy").exists() \
                and fv.endswith("+scn1+evt1"):
            print(f"skip {d.name}: scene+event tables present")
            continue
        feats = np.load(d / "features.npy")
        times = np.load(d / "times.npy")
        scenes, scene_feats = store._build_scene_table(feats, times)
        if not (d / "scenes.npy").exists():
            np.save(d / "scenes.npy", scenes)
            np.save(d / "scene_feats.npy", scene_feats)
        events, event_feats = store._build_event_table(
            np.load(d / "scenes.npy"), np.load(d / "scene_feats.npy"))
        if not (d / "events.npy").exists():
            np.save(d / "events.npy", events)
            np.save(d / "event_feats.npy", event_feats)
        meta["feature_version"] = store.feature_version
        meta_p.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        sizes = scenes[:, 1] - scenes[:, 0]
        print(f"backfilled {d.name}: {scenes.shape[0]} scenes / {events.shape[0]} events "
              f"(scene mean {sizes.mean():.0f}s median {np.median(sizes):.0f}s max {sizes.max():.0f}s)"
              f" -> {meta['feature_version']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
