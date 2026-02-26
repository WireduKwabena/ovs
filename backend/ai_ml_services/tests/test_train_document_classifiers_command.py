"""Tests for train_document_classifiers command behavior."""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

import cv2
import numpy as np
import pandas as pd
from django.test import SimpleTestCase, override_settings

from ai_ml_services.commands.train_document_classifiers import Command


@override_settings(BASE_DIR="C:/Project Setup/Django/OVS-Redo/backend")
class TrainDocumentClassifiersCommandTests(SimpleTestCase):
    @staticmethod
    def _write_pattern_image(path: Path, pattern: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        canvas = np.full((128, 128, 3), 245, dtype=np.uint8)
        if pattern == "horizontal":
            for y in range(12, 120, 16):
                cv2.line(canvas, (8, y), (120, y), (20, 20, 20), 2)
        elif pattern == "vertical":
            for x in range(12, 120, 16):
                cv2.line(canvas, (x, 8), (x, 120), (20, 20, 20), 2)
        else:
            cv2.circle(canvas, (64, 64), 30, (20, 20, 20), 3)
        cv2.imwrite(str(path), canvas)

    def _build_metadata(self, root: Path) -> Path:
        image_root = root / "images"
        rows = []
        counter = 0
        for label, pattern in (("invoice", "horizontal"), ("resume", "vertical")):
            for split in ("train", "train", "train", "val"):
                file_path = image_root / f"{label}_{counter:03d}.png"
                self._write_pattern_image(file_path, pattern=pattern)
                rows.append(
                    {
                        "filename": file_path.name,
                        "filepath": str(file_path.resolve()),
                        "label": label,
                        "split": split,
                    }
                )
                counter += 1

        metadata_path = root / "metadata.csv"
        pd.DataFrame(rows).to_csv(metadata_path, index=False)
        return metadata_path

    def test_dry_run_reports_summary(self):
        with TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            metadata_path = self._build_metadata(tmp_root)
            report_path = tmp_root / "report.json"
            model_path = tmp_root / "rvl.pkl"

            command = Command()
            command.stdout = StringIO()
            command.handle(
                seed=42,
                image_size=128,
                hist_bins=32,
                rvl_metadata=str(metadata_path),
                midv_metadata=str(tmp_root / "unused_midv.csv"),
                rvl_output_model=str(model_path),
                midv_output_model=str(tmp_root / "unused_midv.pkl"),
                report_path=str(report_path),
                midv_source_types=["frame", "template"],
                rvl_max_train=0,
                rvl_max_eval=0,
                midv_max_train=0,
                midv_max_eval=0,
                skip_rvl=False,
                skip_midv=True,
                dry_run=True,
            )

            output = command.stdout.getvalue()
            self.assertIn("Dry run successful.", output)
            self.assertIn("rvl_summary=", output)
            self.assertIn("rvl_output_model=", output)

    def test_train_rvl_model_writes_artifact_and_report(self):
        with TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            metadata_path = self._build_metadata(tmp_root)
            report_path = tmp_root / "report.json"
            model_path = tmp_root / "rvl.pkl"

            command = Command()
            command.stdout = StringIO()
            command.handle(
                seed=42,
                image_size=128,
                hist_bins=32,
                rvl_metadata=str(metadata_path),
                midv_metadata=str(tmp_root / "unused_midv.csv"),
                rvl_output_model=str(model_path),
                midv_output_model=str(tmp_root / "unused_midv.pkl"),
                report_path=str(report_path),
                midv_source_types=["frame", "template"],
                rvl_max_train=0,
                rvl_max_eval=0,
                midv_max_train=0,
                midv_max_eval=0,
                skip_rvl=False,
                skip_midv=True,
                dry_run=False,
            )

            self.assertTrue(model_path.exists())
            self.assertTrue(report_path.exists())

            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertIn("rvl_cdip", report)
            self.assertIn("metrics", report["rvl_cdip"])
            self.assertIn("accuracy", report["rvl_cdip"]["metrics"])
