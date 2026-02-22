"""Data augmentation utilities for authenticity training."""

import cv2
import numpy as np
import torch

try:
    import albumentations as A
    from albumentations.pytorch import ToTensorV2

    HAS_ALBUMENTATIONS = True
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    A = None
    ToTensorV2 = None
    HAS_ALBUMENTATIONS = False

class DocumentAugmentor:
    """Advanced data augmentation for document images"""

    def __init__(self, target_size=(224, 224)): # Added target_size parameter
        self.target_size = target_size

        if HAS_ALBUMENTATIONS:
            self.train_transform = A.Compose([
                A.Resize(target_size[0], target_size[1]), # Added Resize
                # Geometric transformations
                A.ShiftScaleRotate(
                    shift_limit=0.05, scale_limit=0.1, rotate_limit=5,
                    border_mode=cv2.BORDER_CONSTANT, value=255, p=0.7
                ),

                # Perspective distortion (simulate camera angle)
                A.Perspective(
                    scale=(0.05, 0.1), keep_size=True,
                    pad_mode=cv2.BORDER_CONSTANT, pad_val=255, p=0.5
                ),

                # Noise
                A.OneOf([
                    A.GaussNoise(var_limit=(10, 50), p=1.0),
                    A.ISONoise(color_shift=(0.01, 0.05), intensity=(0.1, 0.5), p=1.0),
                ], p=0.4),

                # Blur
                A.OneOf([
                    A.MotionBlur(blur_limit=3, p=1.0),
                    A.GaussianBlur(blur_limit=3, p=1.0),
                ], p=0.3),

                # Lighting and color
                A.RandomBrightnessContrast(brightness_limit=0.2, contrast_limit=0.2, p=0.5),
                A.RandomGamma(gamma_limit=(80, 120), p=0.3),

                # Image compression
                A.ImageCompression(quality_lower=75, quality_upper=100, p=0.3),

                # Shadow effects
                A.RandomShadow(
                    shadow_roi=(0, 0.5, 1, 1), num_shadows_lower=1,
                    num_shadows_upper=2, shadow_dimension=5, p=0.3
                ),

                # Normalize (mean and std for ImageNet, adjust if your dataset has different stats)
                A.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225], p=1.0),
                ToTensorV2() # Convert to PyTorch tensor and scale to [0, 1]
            ])

            self.val_transform = A.Compose([
                A.Resize(target_size[0], target_size[1]), # Added Resize
                A.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225], p=1.0),
                ToTensorV2() # Convert to PyTorch tensor and scale to [0, 1]
            ])
        else:
            self.train_transform = None
            self.val_transform = None

    def augment_image(self, image, is_training=True):
        """Apply augmentation to image"""
        if HAS_ALBUMENTATIONS:
            transform = self.train_transform if is_training else self.val_transform
            augmented = transform(image=image)
            return augmented['image']

        # Fallback path when albumentations is unavailable.
        resized = cv2.resize(image, (self.target_size[1], self.target_size[0]))
        normalized = resized.astype(np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        normalized = (normalized - mean) / std
        chw = np.transpose(normalized, (2, 0, 1))
        return torch.from_numpy(chw).float()
