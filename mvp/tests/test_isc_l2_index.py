# -*- coding: utf-8 -*-
"""L2 源片 ISC 索引宽扫单测（2026-10-04 续52 接线）。合成向量，无 GPU。

覆盖：默认旋钮关（回归锁）· L2 分支正确切换到真峰（result_id `-iscw`）· 与现役宽扫同向 ·
margin 不足不切 · L2 开时粗扫不走 grab_grid（matmul 代替网格抓帧）。
"""
import shutil
import unittest
from pathlib import Path

import numpy as np

from domain.enums import ConfidenceLevel
from domain.models import Confidence, Result, TimeSpan
from engine.localization import isc_l2_index
from engine.localization.isc_refine import apply_isc_refine
from infrastructure.config import load_config


def _shutil_rmtree(p):
    shutil.rmtree(p, ignore_errors=True)


def _onehot(i, n=3):
    v = np.zeros(n, dtype=np.float64)
    v[i] = 1.0
    return v


def _mk_result(**kw):
    d = dict(edited=TimeSpan(0.0, 4.0), original=TimeSpan(100.0, 104.0),
             confidence=Confidence(ConfidenceLevel.HIGH, 0.9))
    d.update(kw)
    return Result(**d)


def _lib():
    lib_t = np.arange(90.0, 131.0, 1.0)
    feats = np.stack([
        _onehot(0) if 99 <= t <= 102 else (_onehot(1) if 112 <= t <= 116 else _onehot(2))
        for t in lib_t])
    return lib_t, feats


V_Q = np.array([1.0, 0.0])
V_LOW = np.array([0.60, -0.80]) / np.linalg.norm([0.60, -0.80])
V_HIGH = np.array([0.62, 0.785]) / np.linalg.norm([0.62, 0.785])


def _make_isc(mode):
    """mode='switch': E2 区=q 本体(sim 1.0) 其余 V_LOW；mode='small': E2=V_HIGH(0.62)。"""
    def _isc_vec(marker):
        t = float(marker)
        if 0 <= t <= 4:
            return V_Q
        if 112 <= t <= 116:
            return V_Q if mode == "switch" else V_HIGH
        return V_LOW
    return _isc_vec


def _src_index(mode):
    """源侧 1s 索引（truepts 语义：标签 t 的特征 = 该时刻画面嵌入）。"""
    lib_t = np.arange(90.0, 131.0, 1.0)
    vec = _make_isc(mode)
    feats = np.stack([np.asarray(vec(float(t), ), dtype=np.float64) for t in lib_t])
    return lib_t, feats


class IscL2IndexTest(unittest.TestCase):
    def _run(self, *, l2_index, isc_mode="switch", margin=0.05, grab_grid=None):
        lib_t, lib_f = _lib()

        def grab(path, t):
            return float(t)

        def embed_cls(marker):
            t = float(marker)
            if 0 <= t <= 4:
                return _onehot(1)          # CLS 查询指向 E2（候选/门不拦）
            if 99 <= t <= 102:
                return _onehot(0)
            if 112 <= t <= 116:
                return _onehot(1)
            return _onehot(2)

        grabbed = {"grid": 0}

        def counting_grid(path, ts):
            grabbed["grid"] += 1
            return grab_grid(path, ts) if grab_grid else {float(t): float(t) for t in ts}

        out = apply_isc_refine(
            [_mk_result()], edited_path="x", source_path="y", grab_frame=grab,
            embed_isc=_make_isc(isc_mode), embed_cls=embed_cls, lib_times=lib_t,
            lib_feats=lib_f, margin=margin, scan_radius_s=90.0,
            grab_frames=None, grab_grid=counting_grid, l2_index=l2_index)
        return out[0], grabbed

    def test_default_knob_on(self):
        # 回归锁：L2 索引宽扫默认开（2026-10-05 续53 用户拍板翻默认；证据链见 config 注释
        # —— 四片 A/B 1.44× 三指标零回退 + 常态链等价 + 建表性能结案 5.01×）。
        # 回退路径 = config 置 False（逐位回现役 v2 宽扫）。
        self.assertTrue(load_config().pipeline.isc_l2_index_enabled)

    def test_l2_switches_to_true_peak(self):
        r, _ = self._run(l2_index=_src_index("switch"))
        self.assertTrue(r.result_id.endswith("-iscw"))
        mid = (r.original.start + r.original.end) / 2
        self.assertGreaterEqual(mid, 110.5)
        self.assertLessEqual(mid, 117.5)

    def test_l2_same_direction_as_legacy(self):
        rl, _ = self._run(l2_index=None)          # 现役宽扫
        r2, _ = self._run(l2_index=_src_index("switch"))
        ml = (rl.original.start + rl.original.end) / 2
        m2 = (r2.original.start + r2.original.end) / 2
        # 两者都应切到 E2 真峰附近（后缀可异：CLS 候选 -isc / 宽扫 -iscw，胜者按分数+距离裁决）
        for r in (rl, r2):
            self.assertTrue(r.result_id.endswith(("-isc", "-iscw")))
            self.assertGreaterEqual((r.original.start + r.original.end) / 2, 110.5)
            self.assertLessEqual((r.original.start + r.original.end) / 2, 117.5)
        self.assertLess(abs(ml - m2), 1.6)         # 网格密度差 ≤ 一格

    def test_l2_no_switch_when_margin_not_met(self):
        r, _ = self._run(l2_index=_src_index("small"), isc_mode="small")
        self.assertFalse(r.result_id.endswith("-iscw"))

    def test_l2_skips_grid_grab(self):
        # L2 开 ⇒ 粗排 = matmul，粗扫网格抓帧不应被调用（细化走 grab_frames/grab_frame）
        def boom(path, ts):
            raise AssertionError("grab_grid must not be called when l2_index is set")
        r, grabbed = self._run(l2_index=_src_index("switch"), grab_grid=boom)
        self.assertEqual(grabbed["grid"], 0)
        self.assertTrue(r.result_id.endswith("-iscw"))


class BuildTpIndexTest(unittest.TestCase):
    """建表循环守卫（2026-10-05）：死簇跳过防死循环 · fps≠1 簇推进 · 无 ffprobe 回退。"""

    class _FakeScorer:
        device = "cpu"

        def embed(self, frame):
            return np.full(256, float(frame), dtype=np.float32)

    class _FakeFF:
        def __init__(self, dead_cluster=None):
            self.ffprobe = "no-such-ffprobe"      # 真扫描必败 → 走容器时长回退口径
            self.dead = dead_cluster
            self.calls: dict = {}

        def metadata(self, path):
            import types
            return types.SimpleNamespace(duration=300.0)

        def grab_grid(self, src, t0, step, n, max_span_s=120.0):
            key = round(float(t0), 3)
            self.calls[key] = self.calls.get(key, 0) + 1
            if self.dead is not None and key == self.dead:
                if self.calls[key] > 500:         # 死循环守卫缺失 ⇒ 由此炸出（BaseException 穿透 except Exception）
                    raise KeyboardInterrupt(f"dead cluster {key} retried >500x")
                raise OSError("dead cluster")
            return {round(t0 + i * step, 6): t0 + i * step for i in range(n)}

    def _tmp_source(self):
        import tempfile
        td = tempfile.mkdtemp()
        src = Path(td) / "src.bin"
        src.write_bytes(b"fake-source")
        self.addCleanup(_shutil_rmtree, td)
        return str(src)

    def test_dead_cluster_skipped_not_hang(self):
        ff = self._FakeFF(dead_cluster=120.0)
        T, F, meta = isc_l2_index.build_tp_index(self._tmp_source(), ffmpeg=ff,
                                                 scorer=self._FakeScorer())
        self.assertEqual(ff.calls.get(120.0), 120)   # 裁剪到 0 后跳过（不重试整簇到死）
        self.assertTrue(np.all((T < 119.5) | (T > 239.5)))   # [120,240) 整簇缺席
        self.assertEqual(T.shape[0] + 120, 300)      # 其余目标全在
        self.assertEqual(F.shape, (T.shape[0], 256))

    def test_cluster_advance_respects_fps(self):
        # fps=2：旧写法 c0 += n_c（秒数按目标数推进，少推进 fps 倍）⇒ 只建半张表；修正后覆盖全片
        ff = self._FakeFF()
        T, _F, _m = isc_l2_index.build_tp_index(self._tmp_source(), ffmpeg=ff,
                                                scorer=self._FakeScorer(),
                                                fps=2.0, cluster_s=60.0)
        self.assertEqual(T.shape[0], 600)            # 300s × 2fps 全覆盖
        self.assertAlmostEqual(float(T[-1]), 299.5)

    def test_cap_falls_back_to_duration_without_ffprobe(self):
        # ffprobe 不可用 ⇒ 退回容器时长口径（尾部守卫交给逐簇 trim）
        from pathlib import Path
        ff = self._FakeFF()
        n = isc_l2_index._capped_target_n(ff, Path("x"), 300.0, 1.0)
        self.assertEqual(n, int((300.0 - 0.5) * 1.0) + 1)


class IscL2IndexStoreTest(unittest.TestCase):
    def test_save_load_roundtrip_and_validity(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            src = td / "src.bin"
            src.write_bytes(b"source-bytes-0123")
            T = np.arange(0.0, 10.0, 1.0)
            F = np.random.default_rng(7).random((10, 256)).astype(np.float32)
            p = isc_l2_index.index_path_for(src, td)
            self.assertEqual(p.name, "src@1.000fps.tp.isci.npz")
            isc_l2_index.save_index(p, T, F, {"schema": "isc_l2_index_v1",
                                              "source_sha256": isc_l2_index.sha256_of(src)})
            got = isc_l2_index.load_index(p)
            self.assertIsNotNone(got)
            T2, F2, meta = got
            self.assertTrue(np.array_equal(T, T2))
            self.assertTrue(np.array_equal(F, F2))
            self.assertTrue(isc_l2_index.is_valid(p, src))
            # 源片变化（sha 不匹配）→ 失效
            src.write_bytes(b"changed-bytes")
            self.assertFalse(isc_l2_index.is_valid(p, src))
            # 加载损坏文件 → None（不抛）
            p.write_bytes(b"garbage")
            self.assertIsNone(isc_l2_index.load_index(p))
            self.assertFalse(isc_l2_index.is_valid(p, src))


if __name__ == "__main__":
    unittest.main()
