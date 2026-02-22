"""Tests for dataset preparation utilities."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import cv2
import numpy as np
from django.test import SimpleTestCase

from ai_ml_services.datasets.create_dataset import DocumentDatasetCreator
from ai_ml_services.datasets.create_resume_metadata import (
    build_resume_metadata,
    normalize_resume_label,
)


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
