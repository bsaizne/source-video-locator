"""Unit tests for mvp.domain and mvp.infrastructure.

Run with the venv python:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" -m unittest mvp.tests.test_domain_infrastructure -v
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # -> mvp/src

from domain import (Alternative, Candidate, Confidence, ConfidenceLevel,
                    ExtractorConfig, IndexMeta, IndexValidation, IndexValidationStatus,
                    Result, ResultSource, TimeSpan)
from infrastructure import (AppConfig, ApplicationError, ConfigError, DeviceError,
                            FeatureExtractionError, IndexError, LocalizationError,
                            LocatorError, MediaConfig, PipelineConfig, load_config,
                            public_error)
# media.ffmpeg only imported for the error-model check; infra must not import it
from media.ffmpeg import MediaError, FFmpegIO


class DomainModelTest(unittest.TestCase):
    def test_time_span(self):
        ts = TimeSpan(10.0, 14.0)
        self.assertEqual(ts.width, 4.0)
        self.assertEqual(ts.to_dict(), {"start": 10.0, "end": 14.0})

    def test_candidate_to_dict(self):
        c = Candidate(0, 5, 5.0, 0.9, 0.8, 0.7, 4, 3, 0.9, 0.05, 1.0, 0.85)
        d = c.to_dict()
        self.assertEqual(d["best_cover"], 0.85)
        self.assertEqual(d["n_reps"], 3)

    def test_confidence(self):
        conf = Confidence(ConfidenceLevel.HIGH, 0.87, ("rank1", "high_query_coverage"))
        d = conf.to_dict()
        self.assertEqual(d["confidence"], "HIGH")
        self.assertEqual(d["confidence_score"], 0.87)
        self.assertEqual(d["reasons"], ["rank1", "high_query_coverage"])

    def test_result_to_dict_matches_spec(self):
        r = Result(
            result_id="abc",
            edited=TimeSpan(0.0, 5.0),
            original=TimeSpan(1234.5, 1250.5),
            confidence=Confidence(ConfidenceLevel.HIGH, 0.87, ("rank1",)),
            candidate_rank=1,
            alternatives=[Alternative(TimeSpan(1300.0, 1310.0), ConfidenceLevel.MEDIUM, 0.6)],
            source=ResultSource.AUTO,
        )
        d = r.to_dict()
        self.assertEqual(d["edited_segment"], {"start": 0.0, "end": 5.0})
        self.assertEqual(d["original"], {"candidate_start": 1234.5, "candidate_end": 1250.5})
        self.assertEqual(d["confidence"], "HIGH")
        self.assertEqual(d["confidence_score"], 0.87)
        self.assertEqual(d["candidate_rank"], 1)
        self.assertEqual(d["alternatives"][0]["confidence"], "MEDIUM")
        self.assertEqual(d["source"], "auto")
        self.assertFalse(d["manual_override"])

    def test_result_manual_keeps_auto(self):
        auto = Result(result_id="a1", edited=TimeSpan(0, 5), original=TimeSpan(10, 15),
                      confidence=Confidence(ConfidenceLevel.HIGH, 0.9))
        manual = Result(result_id="m1", edited=TimeSpan(0, 5), original=TimeSpan(11, 16),
                        confidence=Confidence(ConfidenceLevel.LOW, 0.4),
                        source=ResultSource.MANUAL, manual_override=True,
                        auto_result=auto, manual_timestamp="2026-08-25T12:00:00Z")
        d = manual.to_dict()
        self.assertTrue(d["manual_override"])
        self.assertEqual(d["source"], "manual")
        self.assertEqual(d["auto_result"]["result_id"], "a1")

    def test_index_meta(self):
        meta = IndexMeta("C:/videos/original.mkv", 1020168298, 7667.535, "sha256:deadbeef",
                         extractor=ExtractorConfig(preprocess_sha="ab12"))
        self.assertEqual(meta.feature_model, "dinov2_vits14")
        self.assertEqual(meta.feature_dim, 384)
        d = meta.to_dict()
        self.assertEqual(d["source_file"], "C:/videos/original.mkv")
        self.assertEqual(d["extractor"]["preprocess_sha"], "ab12")

    def test_index_validation(self):
        v = IndexValidation(IndexValidationStatus.INVALID, "hash changed")
        self.assertEqual(v.to_dict(), {"status": "INVALID", "reason": "hash changed"})


class InfrastructureTest(unittest.TestCase):
    def test_default_config(self):
        cfg = load_config()
        self.assertEqual(cfg.pipeline.index_sampling_fps, 1.0)   # 索引密度升级（召回/精度）
        self.assertEqual(cfg.pipeline.retrieval_top_k, 28)        # 向召回侧
        self.assertEqual(cfg.pipeline.seg_z_thresh, 1.7)          # 更细切分（平衡点）
        self.assertEqual(cfg.pipeline.seg_cut_abs, 0.26)
        self.assertEqual(cfg.pipeline.montage_min_frames, 2)      # 蒙太奇向召回侧（平衡点）
        self.assertEqual(cfg.pipeline.montage_cluster_gap_s, 15.0)
        self.assertEqual(cfg.pipeline.ranking_alpha, 0.5)
        # 2026-10-03（续51）：宽扫粗扫网格抽取翻默认（零语义 + 1.27~1.30×，见 config 注释验收证据）
        self.assertTrue(cfg.pipeline.grab_grid_decode)
        self.assertTrue(cfg.pipeline.grab_window_decode)
        # 2026-10-05（续54 补二）：patch 精排窗网格抽取 = 新旋钮，待四片 A/B 前维持默认关
        self.assertFalse(cfg.pipeline.patch_refine_grid)
        # 2026-10-06（续55 下一刀）：主循环重排窗（patch v2 近场池/字牌锚定源窗）网格抽取
        # = 新旋钮，默认关（待 test1 双臂 A/B + 三片回归再拍板）
        self.assertFalse(cfg.pipeline.rerank_grid_grab)
        # 2026-10-05（续55）：簇间并发解码默认 1 = 现役串行（待同脚本双臂 A/B 再定）
        self.assertEqual(cfg.media.cluster_workers, 1)
        self.assertEqual(cfg.media.timeout_s, 600.0)

    def test_config_json_override(self):
        raw = {
            "media": {"ffmpeg_path": "C:/ff/ffmpeg.exe", "timeout_s": 120},
            "pipeline": {"retrieval_top_k": 50, "index_sampling_fps": 0.5},
            "confidence": {"high_threshold": 0.8, "weights": [0.1, 0.1, 0.1, 0.1, 0.1, 0.5]},
            "data_dir": "C:/data",
        }
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "cfg.json"
            p.write_text(json.dumps(raw), encoding="utf-8")
            cfg = load_config(p)
        self.assertEqual(cfg.media.ffmpeg_path, "C:/ff/ffmpeg.exe")
        self.assertEqual(cfg.media.timeout_s, 120)
        self.assertEqual(cfg.pipeline.retrieval_top_k, 50)
        self.assertEqual(cfg.pipeline.confidence.high_threshold, 0.8)
        self.assertEqual(cfg.data_dir, "C:/data")

    def test_config_missing_file_raises(self):
        with self.assertRaises(ConfigError):
            load_config("C:/nonexistent/cfg.json")

    def test_error_codes_are_stable_and_unique(self):
        """T1-2：对外码只增不改；每个可归类异常有自己的码与用户话术。"""
        expected = {
            ConfigError: "LOC-1101", DeviceError: "LOC-1102", IndexError: "LOC-1103",
            FeatureExtractionError: "LOC-1104", LocalizationError: "LOC-1105",
            ApplicationError: "LOC-1106", LocatorError: "LOC-1000",
        }
        for cls, code in expected.items():
            body = public_error(cls("boom"))
            self.assertEqual(body["code"], code, cls.__name__)
            self.assertTrue(body["message"], cls.__name__)
            self.assertNotIn("boom", body["message"])   # 话术不外泄技术细节
        self.assertEqual(len(set(expected.values())), len(expected), "对外码不得重复")

    def test_subsystem_errors_carry_codes(self):
        from media.ffmpeg._runner import MediaError
        self.assertEqual(public_error(MediaError("x"))["code"], "LOC-1107")
        from engine.feature_store import FeatureStoreError
        self.assertEqual(public_error(FeatureStoreError("x"))["code"], "LOC-1103")

    def test_unknown_exception_falls_back(self):
        body = public_error(ValueError("boom"))
        self.assertEqual(body["code"], "LOC-9999")
        self.assertEqual(body["error"], "ValueError")
        self.assertIn("boom", body["detail"])

    def test_media_error_is_locator_error(self):
        # 统一错误模型：media 失败可被基础异常捕获
        self.assertTrue(issubclass(MediaError, LocatorError))
        with self.assertRaises(LocatorError):
            raise MediaError("boom")

    def test_ffmpegio_constructor_missing_ffprobe(self):
        # resolve_binaries should raise LocatorError (via MediaError) for a bad path
        with self.assertRaises(MediaError):
            FFmpegIO(ffmpeg="C:/nope/ffmpeg.exe", ffprobe="C:/nope/ffprobe.exe")


if __name__ == "__main__":
    unittest.main(verbosity=2)
