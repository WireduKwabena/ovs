"""
Document Authenticity Detection - CNN Model Architecture
=========================================================

Academic Note:
--------------
This module implements a ResNet-based CNN for detecting forged or altered documents.

Research Background:
- Document forgery detection is a binary classification problem
- Key features: texture patterns, noise signatures, compression artifacts
- Challenge: Distinguish between legitimate variations and malicious alterations

Model Architecture:
- Base: ResNet-18 (pretrained on ImageNet)
- Custom classifier head for binary classification
- Input: 224x224 RGB images
- Output: Authenticity probability (0-1)

Training Strategy:
- Transfer learning from ImageNet
- Fine-tuning on document-specific features
- Data augmentation to simulate real-world variations
- Class balancing to handle imbalanced datasets

Performance Targets:
- Accuracy: >90%
- Precision: >85% (minimize false positives)
- Recall: >90% (catch most forgeries)
- F1-Score: >87%
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import models, transforms
from torch.utils.data import Dataset, DataLoader
import numpy as np
from PIL import Image
import cv2
from typing import Tuple, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class DocumentAuthenticityNet(nn.Module):
    """
    CNN for document authenticity detection.
    
    Architecture:
    - Backbone: ResNet-18 (pretrained)
    - Feature extraction: 512-dim vector
    - Classifier: 2-layer MLP with dropout
    - Output: Binary classification (authentic/forged)
    
    Academic Note:
    --------------
    ResNet architecture chosen for:
    1. Skip connections help preserve fine-grained features
    2. Pretrained weights provide good initialization
    3. Computationally efficient (18 layers vs 50+)
    4. Proven performance on texture classification tasks
    """
    
    def __init__(
        self,
        pretrained: bool = True,
        freeze_backbone: bool = False,
        dropout_rate: float = 0.5
    ):
        """
        Initialize the authenticity detection model.
        
        Args:
            pretrained: Use ImageNet pretrained weights
            freeze_backbone: Freeze ResNet layers (feature extraction only)
            dropout_rate: Dropout probability for regularization
        """
        super(DocumentAuthenticityNet, self).__init__()
        
        # Load pretrained ResNet-18
        self.backbone = models.resnet18(pretrained=pretrained)
        
        # Remove the original classifier
        num_features = self.backbone.fc.in_features
        self.backbone.fc = nn.Identity()
        
        # Optionally freeze backbone
        if freeze_backbone:
            for param in self.backbone.parameters():
                param.requires_grad = False
        
        # Custom classifier head
        self.classifier = nn.Sequential(
            nn.Linear(num_features, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout_rate),
            nn.Linear(256, 128),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout_rate),
            nn.Linear(128, 1),  # Binary output
            nn.Sigmoid()
        )
        
        # Initialize classifier weights
        self._initialize_classifier()
    
    def _initialize_classifier(self):
        """Initialize classifier weights using He initialization."""
        for m in self.classifier.modules():
            if isinstance(m, nn.Linear):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.
        
        Args:
            x: Input images (batch_size, 3, 224, 224)
        
        Returns:
            Authenticity probability (batch_size, 1)
        """
        # Extract features
        features = self.backbone(x)
        
        # Classify
        output = self.classifier(features)
        
        return output
    
    def extract_features(self, x: torch.Tensor) -> torch.Tensor:
        """
        Extract feature vectors without classification.
        
        Useful for:
        - Visualization (t-SNE, UMAP)
        - Clustering analysis
        - Transfer learning
        
        Args:
            x: Input images
        
        Returns:
            Feature vectors (batch_size, 512)
        """
        with torch.no_grad():
            features = self.backbone(x)
        return features


class MultiScaleAuthenticityNet(nn.Module):
    """
    Advanced multi-scale CNN for capturing forgeries at different scales.
    
    Academic Note:
    --------------
    Forgeries often leave artifacts at multiple scales:
    - Macro: Layout inconsistencies, alignment issues
    - Micro: Compression artifacts, resampling traces
    
    This architecture processes images at multiple resolutions
    and combines features for robust detection.
    """
    
    def __init__(self, num_scales: int = 3):
        super(MultiScaleAuthenticityNet, self).__init__()
        
        self.num_scales = num_scales
        
        # Separate backbone for each scale
        self.backbones = nn.ModuleList([
            models.resnet18(pretrained=True)
            for _ in range(num_scales)
        ])
        
        # Remove classifiers
        for backbone in self.backbones:
            backbone.fc = nn.Identity()
        
        # Fusion layer
        total_features = 512 * num_scales
        self.fusion = nn.Sequential(
            nn.Linear(total_features, 512),
            nn.ReLU(inplace=True),
            nn.Dropout(0.5),
            nn.Linear(512, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(0.5),
            nn.Linear(256, 1),
            nn.Sigmoid()
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass with multi-scale processing.
        
        Args:
            x: Input image (batch_size, 3, 224, 224)
        
        Returns:
            Authenticity probability
        """
        batch_size = x.size(0)
        features_list = []
        
        # Process at different scales
        for i, backbone in enumerate(self.backbones):
            # Downsample for smaller scales
            scale_factor = 2 ** i
            if scale_factor > 1:
                scaled_x = F.interpolate(
                    x,
                    scale_factor=1.0/scale_factor,
                    mode='bilinear',
                    align_corners=False
                )
                scaled_x = F.interpolate(
                    scaled_x,
                    size=(224, 224),
                    mode='bilinear',
                    align_corners=False
                )
            else:
                scaled_x = x
            
            # Extract features
            features = backbone(scaled_x)
            features_list.append(features)
        
        # Concatenate multi-scale features
        combined_features = torch.cat(features_list, dim=1)
        
        # Final classification
        output = self.fusion(combined_features)
        
        return output


class DocumentTransforms:
    """
    Data augmentation and preprocessing transforms.
    
    Academic Note:
    --------------
    Augmentation strategy:
    1. Geometric: Rotation, scaling (simulate scanning variations)
    2. Color: Brightness, contrast (simulate lighting conditions)
    3. Noise: Gaussian noise (simulate sensor noise)
    4. Compression: JPEG artifacts (simulate real-world degradation)
    
    Important: Don't augment in ways that create fake forgeries!
    """
    
    @staticmethod
    def get_train_transforms() -> transforms.Compose:
        """Training transforms with augmentation."""
        return transforms.Compose([
            transforms.Resize((256, 256)),
            transforms.RandomCrop(224),
            transforms.RandomHorizontalFlip(p=0.3),
            transforms.RandomRotation(degrees=5),  # Small rotations only
            transforms.ColorJitter(
                brightness=0.2,
                contrast=0.2,
                saturation=0.1
            ),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],  # ImageNet stats
                std=[0.229, 0.224, 0.225]
            )
        ])
    
    @staticmethod
    def get_val_transforms() -> transforms.Compose:
        """Validation/test transforms (no augmentation)."""
        return transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            )
        ])
    
    @staticmethod
    def get_tta_transforms() -> list:
        """
        Test-time augmentation transforms.
        
        Academic Note:
        --------------
        TTA improves robustness by:
        1. Making predictions on multiple augmented versions
        2. Averaging predictions for final result
        3. Typically improves accuracy by 1-2%
        """
        return [
            transforms.Compose([
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[0.485, 0.456, 0.406],
                    std=[0.229, 0.224, 0.225]
                )
            ]),
            transforms.Compose([
                transforms.Resize((224, 224)),
                transforms.RandomHorizontalFlip(p=1.0),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[0.485, 0.456, 0.406],
                    std=[0.229, 0.224, 0.225]
                )
            ]),
            transforms.Compose([
                transforms.Resize((224, 224)),
                transforms.ColorJitter(brightness=0.1),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[0.485, 0.456, 0.406],
                    std=[0.229, 0.224, 0.225]
                )
            ]),
        ]


class ForgeryAugmentor:
    """
    Create synthetic forgeries for training data augmentation.
    
    Academic Note:
    --------------
    Since real forgery datasets are limited, we synthesize forgeries using:
    1. Copy-move forgery (duplicate regions)
    2. Splicing (combine parts from different documents)
    3. Inpainting (remove/add content)
    4. Resampling (resize and paste back)
    
    This significantly expands training data while simulating real attacks.
    """
    
    @staticmethod
    def copy_move_forgery(image: np.ndarray, region_size: int = 50) -> np.ndarray:
        """
        Create copy-move forgery by duplicating a region.
        
        Args:
            image: Input image (H, W, 3)
            region_size: Size of region to copy
        
        Returns:
            Forged image
        """
        h, w = image.shape[:2]
        forged = image.copy()
        
        # Random source region
        src_x = np.random.randint(0, w - region_size)
        src_y = np.random.randint(0, h - region_size)
        
        # Random destination (different from source)
        dst_x = np.random.randint(0, w - region_size)
        dst_y = np.random.randint(0, h - region_size)
        
        # Ensure not overlapping
        while abs(dst_x - src_x) < region_size and abs(dst_y - src_y) < region_size:
            dst_x = np.random.randint(0, w - region_size)
            dst_y = np.random.randint(0, h - region_size)
        
        # Copy region
        region = image[src_y:src_y+region_size, src_x:src_x+region_size]
        forged[dst_y:dst_y+region_size, dst_x:dst_x+region_size] = region
        
        return forged
    
    @staticmethod
    def resampling_forgery(image: np.ndarray, scale_factor: float = 0.7) -> np.ndarray:
        """
        Create resampling forgery by resizing a region.
        
        Academic Note:
        --------------
        Resampling leaves statistical traces that CNNs can detect.
        """
        h, w = image.shape[:2]
        forged = image.copy()
        
        # Random region
        region_h = int(h * 0.3)
        region_w = int(w * 0.3)
        x = np.random.randint(0, w - region_w)
        y = np.random.randint(0, h - region_h)
        
        # Extract, resize, and paste back
        region = image[y:y+region_h, x:x+region_w]
        resized = cv2.resize(region, (region_w, region_h))
        forged[y:y+region_h, x:x+region_w] = resized
        
        return forged
    
    @staticmethod
    def jpeg_compression_attack(image: np.ndarray, quality: int = 50) -> np.ndarray:
        """
        Apply JPEG compression to simulate forgery concealment.
        
        Academic Note:
        --------------
        Forgers often apply compression to hide manipulation traces.
        Training on compressed images improves robustness.
        """
        # Convert to PIL for JPEG compression
        pil_image = Image.fromarray(image)
        
        # Save with compression and reload
        import io
        buffer = io.BytesIO()
        pil_image.save(buffer, format='JPEG', quality=quality)
        buffer.seek(0)
        compressed = Image.open(buffer)
        
        return np.array(compressed)


def create_model(
    architecture: str = 'resnet18',
    pretrained: bool = True,
    num_classes: int = 1
) -> nn.Module:
    """
    Factory function to create authenticity detection models.
    
    Args:
        architecture: Model architecture ('resnet18', 'multiscale')
        pretrained: Use pretrained weights
        num_classes: Number of output classes (1 for binary)
    
    Returns:
        Initialized model
    """
    if architecture == 'resnet18':
        model = DocumentAuthenticityNet(pretrained=pretrained)
    elif architecture == 'multiscale':
        model = MultiScaleAuthenticityNet(num_scales=3)
    else:
        raise ValueError(f"Unknown architecture: {architecture}")
    
    logger.info(f"Created {architecture} model with pretrained={pretrained}")
    
    return model


if __name__ == "__main__":
    # Test model creation
    model = create_model('resnet18', pretrained=True)
    
    # Test forward pass
    dummy_input = torch.randn(4, 3, 224, 224)
    output = model(dummy_input)
    
    print(f"Model output shape: {output.shape}")
    print(f"Total parameters: {sum(p.numel() for p in model.parameters()):,}")
    print(f"Trainable parameters: {sum(p.numel() for p in model.parameters() if p.requires_grad):,}")
