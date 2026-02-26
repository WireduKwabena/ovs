"""Shared helpers for metadata builders."""

from __future__ import annotations

import random
from typing import Sequence

import pandas as pd


def normalize_extensions(extensions: Sequence[str]) -> set[str]:
    return {ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in extensions}


def assign_stratified_splits(
    df: pd.DataFrame,
    val_ratio: float,
    test_ratio: float,
    random_seed: int,
    label_col: str = "label",
) -> pd.DataFrame:
    if val_ratio < 0 or test_ratio < 0:
        raise ValueError("val_ratio and test_ratio must be >= 0.")
    if val_ratio + test_ratio >= 1:
        raise ValueError("val_ratio + test_ratio must be < 1.")
    if label_col not in df.columns:
        raise ValueError(f"DataFrame does not contain label column `{label_col}`.")

    result = df.copy()
    result["split"] = "train"
    rng = random.Random(random_seed)

    for label in sorted(result[label_col].unique()):
        label_indices = result.index[result[label_col] == label].tolist()
        if len(label_indices) < 2:
            continue

        rng.shuffle(label_indices)
        val_count = int(round(len(label_indices) * val_ratio))
        test_count = int(round(len(label_indices) * test_ratio))
        while val_count + test_count >= len(label_indices):
            if test_count > 0:
                test_count -= 1
            elif val_count > 0:
                val_count -= 1
            else:
                break

        val_indices = label_indices[:val_count]
        test_indices = label_indices[val_count : val_count + test_count]
        if val_indices:
            result.loc[val_indices, "split"] = "val"
        if test_indices:
            result.loc[test_indices, "split"] = "test"

    return result
