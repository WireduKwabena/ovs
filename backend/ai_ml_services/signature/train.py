"""Training helpers for signature authenticity model."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import cv2
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ai_ml_services.signature.features import extract_signature_features
from ai_ml_services.utils.path_rebase import infer_backend_root, rebase_moved_backend_path


def _load_matrix(
    metadata: pd.DataFrame,
    backend_root: Path,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    features: List[np.ndarray] = []
    labels: List[int] = []
    kept_indices: List[int] = []
    for index, row in enumerate(metadata.itertuples(index=False)):
        resolved_path = rebase_moved_backend_path(str(row.filepath), backend_root=backend_root)
        image = cv2.imread(str(resolved_path))
        if image is None:
            continue
        features.append(extract_signature_features(image))
        labels.append(1 if str(row.label).lower() == "authentic" else 0)
        kept_indices.append(index)
    if not features:
        raise ValueError("no readable images found for signature training")
    return (
        np.asarray(features, dtype=np.float32),
        np.asarray(labels, dtype=np.int64),
        np.asarray(kept_indices, dtype=np.int64),
    )


def train_signature_model(
    metadata_path: Path,
    output_path: Path,
    seed: int = 42,
    n_estimators: int = 300,
) -> Dict[str, float]:
    """Train and persist signature authenticity classifier from metadata CSV."""
    metadata = pd.read_csv(metadata_path)
    required = {"filepath", "label"}
    missing = required.difference(metadata.columns)
    if missing:
        raise ValueError(f"metadata missing required columns: {sorted(missing)}")

    backend_root = infer_backend_root(metadata_path)
    x_all, y_all, kept_indices = _load_matrix(metadata, backend_root=backend_root)
    if len(x_all) < 20 or len(np.unique(y_all)) < 2:
        raise ValueError(
            "insufficient signature training samples: need >=20 rows and both classes present"
        )

    if "split" in metadata.columns:
        split_mask = metadata["split"].astype(str).str.lower().values
        split_mask = split_mask[kept_indices]
        train_mask = split_mask == "train"
        val_mask = split_mask == "val"
        if train_mask.sum() >= 10 and val_mask.sum() >= 2:
            x_train, y_train = x_all[train_mask], y_all[train_mask]
            x_val, y_val = x_all[val_mask], y_all[val_mask]
        else:
            x_train, x_val, y_train, y_val = train_test_split(
                x_all,
                y_all,
                test_size=0.2,
                random_state=seed,
                stratify=y_all,
            )
    else:
        x_train, x_val, y_train, y_val = train_test_split(
            x_all,
            y_all,
            test_size=0.2,
            random_state=seed,
            stratify=y_all,
        )

    pipeline = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "classifier",
                RandomForestClassifier(
                    n_estimators=n_estimators,
                    max_depth=18,
                    min_samples_split=4,
                    min_samples_leaf=2,
                    class_weight="balanced",
                    random_state=seed,
                    n_jobs=-1,
                ),
            ),
        ]
    )
    pipeline.fit(x_train, y_train)

    probs = pipeline.predict_proba(x_val)[:, 1]
    preds = (probs >= 0.5).astype(np.int64)
    auc = float(roc_auc_score(y_val, probs)) if len(np.unique(y_val)) > 1 else 0.5
    metrics = {
        "val_f1": float(f1_score(y_val, preds, zero_division=0)),
        "val_accuracy": float(accuracy_score(y_val, preds)),
        "val_auc": auc,
        "train_samples": int(len(x_train)),
        "val_samples": int(len(x_val)),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    artifact = {
        "pipeline": pipeline,
        "label_map": {"authentic": 1, "forged": 0},
        "feature_version": "signature_v1",
        "metrics": metrics,
    }
    joblib.dump(artifact, output_path)

    return {
        **{k: round(v, 6) if isinstance(v, float) else v for k, v in metrics.items()},
        "output_path": str(output_path),
    }

