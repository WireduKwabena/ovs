"""Tests for dataset preparation utilities."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import importlib.util
import unittest

_HAS_DATASET_BUILDER_DEPS = all(
    importlib.util.find_spec(dep) is not None
    for dep in ("cv2", "numpy")
)

if _HAS_DATASET_BUILDER_DEPS:
    import cv2
    import numpy as np
else:  # pragma: no cover - optional ML extras
    cv2 = None
    np = None
from django.test import SimpleTestCase

if _HAS_DATASET_BUILDER_DEPS:
    from ai_ml_services.datasets.create_dataset import DocumentDatasetCreator
    from ai_ml_services.datasets.create_midv500_metadata import (
        build_midv500_metadata,
        normalize_midv_label,
    )
    from ai_ml_services.datasets.create_resume_metadata import (
        build_resume_metadata,
        normalize_resume_label,
    )
    from ai_ml_services.datasets.create_rvl_cdip_metadata import (
        build_rvl_cdip_metadata,
        normalize_rvl_label,
    )


_HAS_CV2_NUMPY = bool(cv2 is not None and np is not None and _HAS_DATASET_BUILDER_DEPS)
_CV2_NUMPY_MISSING_REASON = "Optional dependency missing for dataset builder tests: cv2/numpy"


@unittest.skipUnless(_HAS_CV2_NUMPY, _CV2_NUMPY_MISSING_REASON)
class CoverageDatasetBuilderTests(SimpleTestCase):
    def _write_image(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        image = np.full((32, 32, 3), 180, dtype=np.uint8)
        cv2.imwrite(str(path), image)

    def test_collect_coverage_documents_labels_pairs(self):
        with TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            source = tmp_root / "COVERAGE" / "image"
            self._write_image(source / "1.tif")
            self._write_image(source / "1t.tif")
            self._write_image(source / "2.tif")
            self._write_image(source / "noise.tif")

            creator = DocumentDatasetCreator(output_dir=str(tmp_root / "out"))
            counts = creator.collect_coverage_documents([str(tmp_root / "COVERAGE")])

            self.assertEqual(counts["authentic"], 2)
            self.assertEqual(counts["forged"], 1)
            self.assertGreaterEqual(counts["skipped"], 1)


@unittest.skipUnless(_HAS_CV2_NUMPY, _CV2_NUMPY_MISSING_REASON)
class ResumeMetadataBuilderTests(SimpleTestCase):
    def test_normalize_resume_label_collapses_variants(self):
        self.assertEqual(normalize_resume_label("Accountant resumes"), "accountant")
        self.assertEqual(normalize_resume_label("DataScience"), "data science")
        self.assertEqual(normalize_resume_label("HR"), "human resources")

    def test_build_resume_metadata_generates_expected_columns(self):
        with TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            src = tmp_root / "Resumes PDF"
            (src / "Accountant resumes").mkdir(parents=True, exist_ok=True)
            (src / "DataScience").mkdir(parents=True, exist_ok=True)
            (src / "Data Science").mkdir(parents=True, exist_ok=True)

            (src / "Accountant resumes" / "a.pdf").write_bytes(b"%PDF-1.4\n%")
            (src / "DataScience" / "b.pdf").write_bytes(b"%PDF-1.4\n%")
            (src / "Data Science" / "c.pdf").write_bytes(b"%PDF-1.4\n%")

            output_dir = tmp_root / "processed"
            df = build_resume_metadata(
                source_dir=src,
                output_dir=output_dir,
                val_ratio=0.0,
                test_ratio=0.0,
                random_seed=42,
            )

            self.assertEqual(len(df), 3)
            self.assertIn("label_raw", df.columns)
            self.assertIn("label", df.columns)
            self.assertIn("label_id", df.columns)
            self.assertIn("split", df.columns)
            self.assertTrue((output_dir / "metadata.csv").exists())
            self.assertTrue((output_dir / "labels.csv").exists())
            self.assertTrue((output_dir / "raw_to_normalized_labels.csv").exists())

            normalized_labels = set(df["label"].tolist())
            self.assertIn("accountant", normalized_labels)
            self.assertIn("data science", normalized_labels)


@unittest.skipUnless(_HAS_CV2_NUMPY, _CV2_NUMPY_MISSING_REASON)
class RVLCDIPMetadataBuilderTests(SimpleTestCase):
    def test_normalize_rvl_label(self):
        self.assertEqual(normalize_rvl_label("News Article"), "news_article")
        self.assertEqual(normalize_rvl_label("scientific-publication"), "scientific_publication")

    def test_build_rvl_cdip_metadata_generates_expected_columns(self):
        with TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            src = tmp_root / "RVL-CDIP"
            (src / "news_article").mkdir(parents=True, exist_ok=True)
            (src / "resume").mkdir(parents=True, exist_ok=True)

            (src / "news_article" / "a.tif").write_bytes(b"fake")
            (src / "news_article" / "b.tif").write_bytes(b"fake")
            (src / "resume" / "c.tif").write_bytes(b"fake")

            output_dir = tmp_root / "processed"
            df = build_rvl_cdip_metadata(
                source_dir=src,
                output_dir=output_dir,
                val_ratio=0.0,
                test_ratio=0.0,
                random_seed=42,
            )

            self.assertEqual(len(df), 3)
            self.assertIn("label_raw", df.columns)
            self.assertIn("label", df.columns)
            self.assertIn("label_id", df.columns)
            self.assertIn("split", df.columns)
            self.assertTrue((output_dir / "metadata.csv").exists())
            self.assertTrue((output_dir / "labels.csv").exists())
            self.assertTrue((output_dir / "raw_to_normalized_labels.csv").exists())
            self.assertIn("news_article", set(df["label"].tolist()))
            self.assertIn("resume", set(df["label"].tolist()))


@unittest.skipUnless(_HAS_CV2_NUMPY, _CV2_NUMPY_MISSING_REASON)
class MIDV500MetadataBuilderTests(SimpleTestCase):
    def test_normalize_midv_label(self):
        self.assertEqual(normalize_midv_label("01_alb_id"), "alb_id")
        self.assertEqual(normalize_midv_label("47_usa_bordercrossing"), "usa_bordercrossing")

    def test_build_midv500_metadata_generates_expected_columns(self):
        with TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            src = tmp_root / "midv500"

            class_dir = src / "01_alb_id"
            (class_dir / "images" / "CA").mkdir(parents=True, exist_ok=True)
            (class_dir / "ground_truth" / "CA").mkdir(parents=True, exist_ok=True)
            (class_dir / "images" / "01_alb_id.tif").write_bytes(b"fake")
            (class_dir / "images" / "CA" / "CA01_01.tif").write_bytes(b"fake")
            (class_dir / "images" / "CA" / "CA01_02.tif").write_bytes(b"fake")
            (class_dir / "ground_truth" / "01_alb_id.json").write_text("{}", encoding="utf-8")
            (class_dir / "ground_truth" / "CA" / "CA01_01.json").write_text(
                json.dumps({"quad": [[0, 0], [1, 0], [1, 1], [0, 1]]}),
                encoding="utf-8",
            )

            class_dir_2 = src / "02_aut_id"
            (class_dir_2 / "images" / "TS").mkdir(parents=True, exist_ok=True)
            (class_dir_2 / "ground_truth" / "TS").mkdir(parents=True, exist_ok=True)
            (class_dir_2 / "images" / "02_aut_id.tif").write_bytes(b"fake")
            (class_dir_2 / "images" / "TS" / "TS02_01.tif").write_bytes(b"fake")

            output_dir = tmp_root / "processed_midv"
            df = build_midv500_metadata(
                source_dir=src,
                output_dir=output_dir,
                val_ratio=0.0,
                test_ratio=0.0,
                random_seed=42,
                include_templates=True,
                include_frames=True,
                parse_quads=True,
            )

            self.assertEqual(len(df), 5)
            self.assertIn("source_type", df.columns)
            self.assertIn("sequence_id", df.columns)
            self.assertIn("annotation_path", df.columns)
            self.assertIn("quad_points", df.columns)
            self.assertIn("group_id", df.columns)
            self.assertIn("split", df.columns)
            self.assertTrue((output_dir / "metadata.csv").exists())
            self.assertTrue((output_dir / "labels.csv").exists())
            self.assertTrue((output_dir / "raw_to_normalized_labels.csv").exists())
            self.assertIn("alb_id", set(df["label"].tolist()))
            self.assertIn("aut_id", set(df["label"].tolist()))

            frame_rows = df[df["source_type"] == "frame"]
            self.assertGreaterEqual(int(frame_rows["has_annotation"].sum()), 1)
