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
    """mode='switch': 真峰区(139-141)=q 本体(sim 1.0) 其余 V_LOW；
    mode='small': 真峰区=V_HIGH(0.62)。

    真峰放在 CLS 库（90..131）之外的 139-141：`_clusters` 的零分区候选 mid 可能落在
    任何零分区行上（跨平台平局顺序不同），真峰若在库内，taken（候选+2s 排除带）有
    概率盖住全部峰行 ⇒ -iscw 采纳与否随平局顺序漂移（macOS CI 3 失败根因，续58）。
    库外峰值行距一切可能 taken ≥8s ⇒ 采纳决策与平局顺序无关。"""
    def _isc_vec(marker):
        t = float(marker)
        if 0 <= t <= 4:
            return V_Q
        if 139 <= t <= 141:
            return V_Q if mode == "switch" else V_HIGH
        return V_LOW
    return _isc_vec


def _src_index(mode):
    """源侧 1s 索引（truepts 语义：标签 t 的特征 = 该时刻画面嵌入）。
    时间轴延伸到 145：真峰区 139-141 必须在索引里（见 _make_isc 注释）。"""
    lib_t = np.arange(90.0, 146.0, 1.0)
    vec = _make_isc(mode)
    feats = np.stack([np.asarray(vec(float(t), ), dtype=np.float64) for t in lib_t])
    return lib_t, feats


class IscL2IndexTest(unittest.TestCase):
    def _run(self, *, l2_index, isc_mode="switch", margin=0.05, grab_grid=None,
             refine_grid=False):
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
            grab_frames=None, grab_grid=counting_grid, l2_index=l2_index,
            refine_grid=refine_grid)
        return out[0], grabbed

    def test_default_knob_on(self):
        # 回归锁：L2 索引宽扫默认开（2026-10-05 续53 用户拍板翻默认；证据链见 config 注释
        # —— 四片 A/B 1.44× 三指标零回退 + 常态链等价 + 建表性能结案 5.01×）。
        # 回退路径 = config 置 False（逐位回现役 v2 宽扫）。
        self.assertTrue(load_config().pipeline.isc_l2_index_enabled)

    def test_grid_refine_knob_default_off(self):
        # 回归锁（2026-10-05 续54）：精扫细化窗网格抽取默认关
        self.assertFalse(load_config().pipeline.isc_refine_grid_refine)

    def test_grid_refine_off_keeps_legacy_grab(self):
        # 默认关：L2 精扫细化窗不走 grab_grid（逐位回现役路径）
        _r, grabbed = self._run(l2_index=_src_index("switch"), refine_grid=False)
        self.assertEqual(grabbed["grid"], 0)

    def test_grid_refine_on_uses_grid_for_fine_ts(self):
        # 开：精扫细化窗（fine_ts 1s 网格）走 grab_grid，且选中峰与旧路径一致
        r_off, _ = self._run(l2_index=_src_index("switch"), refine_grid=False)
        r_on, grabbed = self._run(l2_index=_src_index("switch"), refine_grid=True)
        self.assertGreaterEqual(grabbed["grid"], 1)
        self.assertTrue(r_on.result_id.endswith("-iscw"))          # 同判（result_id 含随机批次 UUID，只比后缀）
        self.assertEqual(r_on.original, r_off.original)

    def test_l2_switches_to_true_peak(self):
        r, _ = self._run(l2_index=_src_index("switch"))
        self.assertTrue(r.result_id.endswith("-iscw"))
        mid = (r.original.start + r.original.end) / 2
        self.assertGreaterEqual(mid, 138.0)
        self.assertLessEqual(mid, 142.0)

    def test_l2_same_direction_as_legacy(self):
        rl, _ = self._run(l2_index=None)          # 现役宽扫
        r2, _ = self._run(l2_index=_src_index("switch"))
        ml = (rl.original.start + rl.original.end) / 2
        m2 = (r2.original.start + r2.original.end) / 2
        # 两者都应切到 E2 真峰附近（后缀可异：CLS 候选 -isc / 宽扫 -iscw，胜者按分数+距离裁决）
        for r in (rl, r2):
            self.assertTrue(r.result_id.endswith(("-isc", "-iscw")))
            self.assertGreaterEqual((r.original.start + r.original.end) / 2, 138.0)
            self.assertLessEqual((r.original.start + r.original.end) / 2, 142.0)
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


class EnsureL2IndexServiceTest(unittest.TestCase):
    """回归锁（2026-10-05，r8 打包态 E2E 抓到的真崩溃）：service 对「**已存在的有效索引**」
    走 is_valid=True 分支时 `_isc_l2_validated.add(ck)` 必须可用——该字段曾被初始化为
    `{}`（dict），`.add` 即 AttributeError ⇒ 用户第二次分析同一部原片必崩（续52-G 起潜伏，
    因当时四片全部走「重建」分支而漏测）。fake 掉磁盘/哈希/FFmpeg 依赖，只测分支逻辑。"""

    def test_existing_valid_index_loaded_not_rebuilt(self):
        import tempfile
        import types
        from pathlib import Path as _Path

        import app.locator_service as ls_mod

        with tempfile.TemporaryDirectory() as td:
            td = _Path(td)
            src = td / "src.bin"
            src.write_bytes(b"source-bytes")
            root = td / "isc_index"
            root.mkdir()
            T = np.arange(5.0)
            F = np.zeros((5, 256), dtype=np.float32)
            idx_p = isc_l2_index.index_path_for(src, root)
            isc_l2_index.save_index(idx_p, T, F, {"schema": "isc_l2_index_v1",
                                                  "source_sha256": "cafe"})

            srv = ls_mod.SourceLocatorService.__new__(ls_mod.SourceLocatorService)
            srv._log = types.SimpleNamespace(info=lambda *a, **k: None,
                                             warning=lambda *a, **k: None)
            srv._isc_l2_cache = {}
            srv._isc_l2_validated = set()      # 回归点：必须是 set（曾是 {} ⇒ .add 崩）
            srv._isc_l2_sha = {}
            srv.config = types.SimpleNamespace(
                pipeline=types.SimpleNamespace(isc_l2_index_enabled=True,
                                               isc_l2_index_dir=str(root)))
            calls = {"sha": 0, "build": 0}

            def fake_sha(p, chunk=1 << 22):
                calls["sha"] += 1
                return "cafe"

            import infrastructure.paths as paths_mod
            orig_root = paths_mod.isc_index_root
            paths_mod.isc_index_root = lambda **kw: root      # service 模块内按名字引用
            orig_is_valid = isc_l2_index.is_valid
            orig_sha = isc_l2_index.sha256_of
            orig_build = isc_l2_index.build_tp_index
            isc_l2_index.is_valid = lambda *a, **k: True
            isc_l2_index.sha256_of = fake_sha
            isc_l2_index.build_tp_index = lambda *a, **k: calls.__setitem__(
                "build", calls["build"] + 1)
            try:
                got = srv._ensure_isc_l2_index(str(src))
            finally:
                paths_mod.isc_index_root = orig_root
                isc_l2_index.is_valid = orig_is_valid
                isc_l2_index.sha256_of = orig_sha
                isc_l2_index.build_tp_index = orig_build
            self.assertIsNotNone(got)
            self.assertTrue(np.array_equal(got[0], T))
            self.assertTrue(np.array_equal(got[1], F))
            self.assertEqual(calls["build"], 0)            # 有效索引 ⇒ 不重建
            self.assertEqual(len(srv._isc_l2_validated), 1)  # .add 生效（回归点）

    def test_validated_field_is_a_set(self):
        # 字段初始化回归锁：`_isc_l2_validated` 必须是 set（2026-10-05 曾为 {} ⇒ .add 崩）
        import app.locator_service as ls_mod
        srv = ls_mod.SourceLocatorService()
        self.assertIsInstance(srv._isc_l2_validated, set)
        self.assertIsInstance(srv._isc_l2_cache, dict)
        self.assertIsInstance(srv._isc_l2_sha, dict)


if __name__ == "__main__":
    unittest.main()
