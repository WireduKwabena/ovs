# datasets/pytorch_loaders.py
import torch
from torch.utils.data import Dataset, DataLoader
import pandas as pd
import cv2
from pathlib import Path
import logging

from .augmentation import DocumentAugmentor

logger = logging.getLogger(__name__)

class DocumentAuthenticityDataset(Dataset):
    """PyTorch Dataset for document authenticity detection"""

    def __init__(self, metadata_df: pd.DataFrame, target_size=(224, 224), augment: bool = False):
        self.metadata = metadata_df
        self.augment = augment
        self.target_size = target_size

        if self.augment:
            self.augmentor = DocumentAugmentor(target_size=self.target_size)
        else:
            # For validation/test, use only resize and normalize/ToTensorV2
            self.augmentor = DocumentAugmentor(target_size=self.target_size) # Will use val_transform internally

    def __len__(self):
        return len(self.metadata)

    def __getitem__(self, idx):
        row = self.metadata.iloc[idx]

        # Use the 'filepath' column which was added in create_dataset.py
        img_path = Path(row['filepath'])

        # Load image
        image = cv2.imread(str(img_path))
        if image is None:
            logger.warning(f"Could not read image: {img_path}. Returning dummy data.")
            # Return a black image and dummy label if image cannot be loaded
            # This might need more robust handling depending on requirements
            dummy_image = torch.zeros(3, self.target_size[0], self.target_size[1], dtype=torch.float32)
            label = 0 # Default to forged or handle as an error case
            return dummy_image, label, row['filename']

        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB) # Convert to RGB for albumentations

        # Apply transformations (resizing, augmentation, normalization, ToTensorV2)
        # The augmentor now handles all these steps
        image_tensor = self.augmentor.augment_image(image, is_training=self.augment)

        # Label (1 = authentic, 0 = forged)
        label = 1 if row['label'] == 'authentic' else 0

        return image_tensor, label, row['filename']

def create_data_loaders(metadata_file: str, batch_size: int = 32, num_workers: int = 4, target_size=(224, 224)):
    """Create train and validation data loaders"""
    metadata = pd.read_csv(metadata_file)

    # Split metadata into train and validation DataFrames
    train_meta = metadata[metadata['split'] == 'train'].reset_index(drop=True)
    val_meta = metadata[metadata['split'] == 'val'].reset_index(drop=True)

    logger.info(f"Train samples: {len(train_meta)}, Validation samples: {len(val_meta)}")

    # Create datasets, passing DataFrames directly
    train_dataset = DocumentAuthenticityDataset(
        metadata_df=train_meta,
        target_size=target_size,
        augment=True
    )

    val_dataset = DocumentAuthenticityDataset(
        metadata_df=val_meta,
        target_size=target_size,
        augment=False # No augmentation for validation set, only resize and normalize
    )

    # Create loaders
    train_loader = DataLoader(
        train_dataset, batch_size=batch_size, shuffle=True,
        num_workers=num_workers, pin_memory=True
    )

    val_loader = DataLoader(
        val_dataset, batch_size=batch_size, shuffle=False,
        num_workers=num_workers, pin_memory=True
    )

    return train_loader, val_loader
