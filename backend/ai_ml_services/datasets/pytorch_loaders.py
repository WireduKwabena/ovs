import logging
from pathlib import Path

import cv2
import pandas as pd
import torch
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader, Dataset

from .augmentation import DocumentAugmentor

logger = logging.getLogger(__name__)

REQUIRED_METADATA_COLUMNS = {"filepath", "label"}


class DocumentAuthenticityDataset(Dataset):
    """PyTorch Dataset for document authenticity detection"""

    def __init__(
        self,
        metadata_df: pd.DataFrame,
        target_size=(224, 224),
        augment: bool = False,
        fail_on_missing: bool = False,
    ):
        missing_cols = REQUIRED_METADATA_COLUMNS.difference(metadata_df.columns)
        if missing_cols:
            raise ValueError(f"metadata_df missing required columns: {sorted(missing_cols)}")

        self.metadata = metadata_df.reset_index(drop=True)
        self.augment = augment
        self.target_size = target_size
        self.fail_on_missing = fail_on_missing

        if self.augment:
            self.augmentor = DocumentAugmentor(target_size=self.target_size)
        else:
            # For validation/test, use only resize and normalize/ToTensorV2
            self.augmentor = DocumentAugmentor(target_size=self.target_size)  # Uses val_transform internally

    def __len__(self):
        return len(self.metadata)

    def __getitem__(self, idx):
        row = self.metadata.iloc[idx]

        img_path = Path(str(row["filepath"]))

        image = cv2.imread(str(img_path))
        if image is None:
            message = f"Could not read image: {img_path}"
            if self.fail_on_missing:
                raise FileNotFoundError(message)
            logger.warning("%s. Returning dummy tensor.", message)
            dummy_image = torch.zeros(3, self.target_size[0], self.target_size[1], dtype=torch.float32)
            label = 1 if str(row["label"]).strip().lower() == "authentic" else 0
            return dummy_image, label, str(row.get("filename", img_path.name))

        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        image_tensor = self.augmentor.augment_image(image, is_training=self.augment)
        label = 1 if str(row["label"]).strip().lower() == "authentic" else 0

        return image_tensor, label, str(row.get("filename", img_path.name))


def _split_if_needed(metadata: pd.DataFrame, random_seed: int = 42) -> tuple[pd.DataFrame, pd.DataFrame]:
    split_col = metadata["split"].astype(str).str.lower() if "split" in metadata.columns else None
    if split_col is not None and (split_col == "val").any():
        train_meta = metadata[split_col == "train"].reset_index(drop=True)
        val_meta = metadata[split_col == "val"].reset_index(drop=True)
        return train_meta, val_meta

    labels = metadata["label"].astype(str).str.lower().values
    if len(metadata) < 2:
        return metadata.reset_index(drop=True), metadata.reset_index(drop=True)
    idx_train, idx_val = train_test_split(
        list(range(len(metadata))),
        test_size=0.2,
        random_state=random_seed,
        stratify=labels if len(set(labels)) > 1 else None,
    )
    train_meta = metadata.iloc[idx_train].reset_index(drop=True)
    val_meta = metadata.iloc[idx_val].reset_index(drop=True)
    return train_meta, val_meta


def _drop_missing_files(metadata: pd.DataFrame) -> pd.DataFrame:
    exists_mask = metadata["filepath"].map(lambda value: Path(str(value)).exists())
    dropped = int((~exists_mask).sum())
    if dropped > 0:
        logger.warning("Dropping %d rows with missing filepaths before DataLoader creation.", dropped)
    return metadata[exists_mask].reset_index(drop=True)


def create_data_loaders(
    metadata_file: str,
    batch_size: int = 32,
    num_workers: int = 4,
    target_size=(224, 224),
    random_seed: int = 42,
    drop_missing_files: bool = True,
    fail_on_missing: bool = False,
):
    """Create train and validation data loaders from metadata CSV."""
    metadata = pd.read_csv(metadata_file)
    missing_cols = REQUIRED_METADATA_COLUMNS.difference(metadata.columns)
    if missing_cols:
        raise ValueError(f"metadata file missing required columns: {sorted(missing_cols)}")

    if drop_missing_files:
        metadata = _drop_missing_files(metadata)
    if metadata.empty:
        raise ValueError("No metadata rows available after filtering.")

    train_meta, val_meta = _split_if_needed(metadata, random_seed=random_seed)

    logger.info("Train samples: %d, Validation samples: %d", len(train_meta), len(val_meta))

    train_dataset = DocumentAuthenticityDataset(
        metadata_df=train_meta,
        target_size=target_size,
        augment=True,
        fail_on_missing=fail_on_missing,
    )

    val_dataset = DocumentAuthenticityDataset(
        metadata_df=val_meta,
        target_size=target_size,
        augment=False,
        fail_on_missing=fail_on_missing,
    )

    pin_memory = torch.cuda.is_available()
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        pin_memory=pin_memory,
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=pin_memory,
    )

    return train_loader, val_loader
