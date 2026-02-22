"""
Document Authenticity Detection - Training Pipeline
====================================================

Academic Note:
--------------
Complete training pipeline including:
1. Dataset preparation and loading
2. Training loop with validation
3. Learning rate scheduling
4. Early stopping
5. Model checkpointing
6. Performance metrics tracking
7. Experiment logging

Training Strategy:
- Loss: Binary Cross-Entropy with class weighting
- Optimizer: Adam with weight decay
- LR Schedule: ReduceLROnPlateau
- Batch size: 32 (adjust based on GPU memory)
- Epochs: 50 with early stopping
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.utils.data import DataLoader
from torch.optim.lr_scheduler import ReduceLROnPlateau
import numpy as np
from pathlib import Path
import logging
from typing import Dict, Optional
from tqdm import tqdm
import matplotlib.pyplot as plt
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score
)
try:
    import wandb  # Optional: for experiment tracking
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    wandb = None

from ai_ml_services.authenticity.cnn_detector import create_model
from ai_ml_services.datasets.pytorch_loaders import create_data_loaders

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)





class Trainer:
    """
    Training manager for document authenticity model.
    
    Academic Note:
    --------------
    Implements best practices:
    1. Early stopping to prevent overfitting
    2. Learning rate scheduling for convergence
    3. Model checkpointing to save best weights
    4. Comprehensive metrics tracking
    5. Experiment reproducibility
    """
    
    def __init__(
        self,
        model: nn.Module,
        train_loader: DataLoader,
        val_loader: DataLoader,
        device: str = 'cuda',
        learning_rate: float = 1e-4,
        weight_decay: float = 1e-5,
        class_weights: Optional[torch.Tensor] = None,
        checkpoint_dir: str = 'checkpoints',
        use_wandb: bool = False
    ):
        """
        Initialize trainer.
        
        Args:
            model: PyTorch model
            train_loader: Training data loader
            val_loader: Validation data loader
            device: Device to train on ('cuda' or 'cpu')
            learning_rate: Initial learning rate
            weight_decay: L2 regularization strength
            class_weights: Weights for class imbalance
            checkpoint_dir: Directory to save checkpoints
            use_wandb: Use Weights & Biases for logging
        """
        self.model = model.to(device)
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.device = device
        
        # Keep BCE loss and apply optional class-balanced sample weights per batch.
        self.class_weights = class_weights.to(device) if class_weights is not None else None
        self.criterion = nn.BCELoss()
        
        # Optimizer
        self.optimizer = optim.Adam(
            model.parameters(),
            lr=learning_rate,
            weight_decay=weight_decay
        )
        
        # Learning rate scheduler
        self.scheduler = ReduceLROnPlateau(
            self.optimizer,
            mode='min',
            factor=0.5,
            patience=5,
            verbose=True
        )
        
        # Checkpoint management
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        # Tracking
        self.best_val_loss = float('inf')
        self.best_val_f1 = 0.0
        self.history = {
            'train_loss': [],
            'val_loss': [],
            'val_accuracy': [],
            'val_precision': [],
            'val_recall': [],
            'val_f1': [],
            'val_auc': []
        }
        
        # Weights & Biases
        self.use_wandb = bool(use_wandb and wandb is not None)
        if use_wandb and wandb is None:
            logger.warning("`wandb` is not installed; disabling experiment tracking.")
        if self.use_wandb:
            wandb.init(project="document-authenticity", config={
                "learning_rate": learning_rate,
                "weight_decay": weight_decay,
                "batch_size": train_loader.batch_size,
            })

    def _compute_loss(self, outputs: torch.Tensor, labels: torch.Tensor) -> torch.Tensor:
        if self.class_weights is None:
            return self.criterion(outputs, labels)

        neg_weight = self.class_weights[0]
        pos_weight = self.class_weights[1]
        sample_weights = torch.where(labels > 0.5, pos_weight, neg_weight)
        return F.binary_cross_entropy(outputs, labels, weight=sample_weights)
    
    def train_epoch(self) -> float:
        """Train for one epoch."""
        self.model.train()
        total_loss = 0.0
        
        pbar = tqdm(self.train_loader, desc="Training")
        for batch in pbar:
            if len(batch) == 3:
                images, labels, _ = batch
            else:
                images, labels = batch[:2]
            images = images.to(self.device)
            labels = labels.to(self.device).float().unsqueeze(1)
            
            # Forward pass
            outputs = self.model(images)
            loss = self._compute_loss(outputs, labels)
            
            # Backward pass
            self.optimizer.zero_grad()
            loss.backward()
            self.optimizer.step()
            
            total_loss += loss.item()
            pbar.set_postfix({'loss': loss.item()})
        
        avg_loss = total_loss / len(self.train_loader)
        return avg_loss
    
    def validate(self) -> Dict[str, float]:
        """Validate model."""
        self.model.eval()
        total_loss = 0.0
        all_predictions = []
        all_labels = []
        all_probabilities = []
        
        with torch.no_grad():
            for batch in tqdm(self.val_loader, desc="Validation"):
                if len(batch) == 3:
                    images, labels, _ = batch
                else:
                    images, labels = batch[:2]
                images = images.to(self.device)
                labels = labels.to(self.device).float().unsqueeze(1)
                
                # Forward pass
                outputs = self.model(images)
                loss = self._compute_loss(outputs, labels)
                
                total_loss += loss.item()
                
                # Collect predictions
                predictions = (outputs > 0.5).float()
                all_predictions.extend(predictions.cpu().numpy())
                all_labels.extend(labels.cpu().numpy())
                all_probabilities.extend(outputs.cpu().numpy())
        
        # Calculate metrics
        all_predictions = np.array(all_predictions).flatten()
        all_labels = np.array(all_labels).flatten()
        all_probabilities = np.array(all_probabilities).flatten()
        
        auc = roc_auc_score(all_labels, all_probabilities) if len(np.unique(all_labels)) > 1 else 0.5
        metrics = {
            'loss': total_loss / len(self.val_loader),
            'accuracy': accuracy_score(all_labels, all_predictions),
            'precision': precision_score(all_labels, all_predictions, zero_division=0),
            'recall': recall_score(all_labels, all_predictions, zero_division=0),
            'f1': f1_score(all_labels, all_predictions, zero_division=0),
            'auc': auc
        }
        
        return metrics
    
    def train(
        self,
        num_epochs: int = 50,
        early_stopping_patience: int = 10,
        save_best_only: bool = True
    ):
        """
        Complete training loop.
        
        Args:
            num_epochs: Maximum number of epochs
            early_stopping_patience: Stop if no improvement for N epochs
            save_best_only: Only save best model
        """
        logger.info(f"Starting training for {num_epochs} epochs")
        
        epochs_without_improvement = 0
        
        for epoch in range(num_epochs):
            logger.info(f"\nEpoch {epoch+1}/{num_epochs}")
            
            # Train
            train_loss = self.train_epoch()
            
            # Validate
            val_metrics = self.validate()
            
            # Update history
            self.history['train_loss'].append(train_loss)
            self.history['val_loss'].append(val_metrics['loss'])
            self.history['val_accuracy'].append(val_metrics['accuracy'])
            self.history['val_precision'].append(val_metrics['precision'])
            self.history['val_recall'].append(val_metrics['recall'])
            self.history['val_f1'].append(val_metrics['f1'])
            self.history['val_auc'].append(val_metrics['auc'])
            
            # Log metrics
            logger.info(
                f"Train Loss: {train_loss:.4f} | "
                f"Val Loss: {val_metrics['loss']:.4f} | "
                f"Val Acc: {val_metrics['accuracy']:.4f} | "
                f"Val F1: {val_metrics['f1']:.4f} | "
                f"Val AUC: {val_metrics['auc']:.4f}"
            )
            
            if self.use_wandb:
                wandb.log({
                    "train_loss": train_loss,
                    "val_loss": val_metrics['loss'],
                    "val_accuracy": val_metrics['accuracy'],
                    "val_f1": val_metrics['f1'],
                    "val_auc": val_metrics['auc']
                })
            
            # Learning rate scheduling
            self.scheduler.step(val_metrics['loss'])
            
            # Save best model
            if val_metrics['f1'] > self.best_val_f1:
                self.best_val_f1 = val_metrics['f1']
                self.save_checkpoint(epoch, val_metrics, is_best=True)
                epochs_without_improvement = 0
                logger.info(f"New best F1: {self.best_val_f1:.4f}")
            else:
                epochs_without_improvement += 1
                if not save_best_only:
                    self.save_checkpoint(epoch, val_metrics, is_best=False)
            
            # Early stopping
            if epochs_without_improvement >= early_stopping_patience:
                logger.info(f"Early stopping after {epoch+1} epochs")
                break
        
        logger.info("Training completed!")
        self.plot_training_history()
    
    def save_checkpoint(self, epoch: int, metrics: Dict, is_best: bool = False):
        """Save model checkpoint."""
        checkpoint = {
            'epoch': epoch,
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'scheduler_state_dict': self.scheduler.state_dict(),
            'metrics': metrics,
            'history': self.history
        }
        
        if is_best:
            checkpoint_path = self.checkpoint_dir / 'best_model.pth'
            logger.info(f"Saving best model to {checkpoint_path}")
        else:
            checkpoint_path = self.checkpoint_dir / f'checkpoint_epoch_{epoch}.pth'
        
        torch.save(checkpoint, checkpoint_path)
    
    def plot_training_history(self):
        """Plot training history."""
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        
        # Loss
        axes[0, 0].plot(self.history['train_loss'], label='Train Loss')
        axes[0, 0].plot(self.history['val_loss'], label='Val Loss')
        axes[0, 0].set_xlabel('Epoch')
        axes[0, 0].set_ylabel('Loss')
        axes[0, 0].legend()
        axes[0, 0].set_title('Training and Validation Loss')
        
        # Accuracy
        axes[0, 1].plot(self.history['val_accuracy'], label='Accuracy')
        axes[0, 1].set_xlabel('Epoch')
        axes[0, 1].set_ylabel('Accuracy')
        axes[0, 1].legend()
        axes[0, 1].set_title('Validation Accuracy')
        
        # F1 Score
        axes[1, 0].plot(self.history['val_f1'], label='F1 Score')
        axes[1, 0].set_xlabel('Epoch')
        axes[1, 0].set_ylabel('F1 Score')
        axes[1, 0].legend()
        axes[1, 0].set_title('Validation F1 Score')
        
        # AUC
        axes[1, 1].plot(self.history['val_auc'], label='AUC-ROC')
        axes[1, 1].set_xlabel('Epoch')
        axes[1, 1].set_ylabel('AUC')
        axes[1, 1].legend()
        axes[1, 1].set_title('Validation AUC-ROC')
        
        plt.tight_layout()
        plt.savefig(self.checkpoint_dir / 'training_history.png')
        logger.info(f"Training history saved to {self.checkpoint_dir / 'training_history.png'}")


def main():
    """Main training script."""
    # Configuration
    config = {
        'data_dir': 'data/documents',
        'batch_size': 32,
        'num_epochs': 50,
        'learning_rate': 1e-4,
        'weight_decay': 1e-5,
        'device': 'cuda' if torch.cuda.is_available() else 'cpu',
        'checkpoint_dir': 'models/checkpoints',
        'use_wandb': False
    }
    
    logger.info(f"Using device: {config['device']}")
    
    # Use create_data_loaders to get train and validation loaders
    train_loader, val_loader = create_data_loaders(
        metadata_file=f"{config['data_dir']}/metadata.csv",
        batch_size=config['batch_size'],
        num_workers=4,
        target_size=(224, 224) # Assuming 224x224 input
    )
    
    # Create model
    model = create_model('resnet18', pretrained=True)
    
    # Calculate class weights from the train_loader's dataset (DocumentAuthenticityDataset)
    # This assumes DocumentAuthenticityDataset has a get_class_weights method, 
    # which it doesn't currently. This needs to be added to DocumentAuthenticityDataset
    # or calculated here manually from the labels.
    # For simplicity, I will calculate it manually here for now, 
    # assuming the labels are available from the train_loader.dataset.
    labels_list = []
    for sample in train_loader.dataset:
        label = sample[1] if isinstance(sample, (tuple, list)) and len(sample) > 1 else sample
        if torch.is_tensor(label):
            label = label.item()
        labels_list.append(int(label))
    
    labels_array = np.array(labels_list)
    n_samples = len(labels_array)
    n_classes = 2
    
    weights = []
    for c in [0, 1]:
        n_class = np.sum(labels_array == c)
        weight = n_samples / (n_classes * n_class) if n_class > 0 else 0
        weights.append(weight)
    
    class_weights = torch.FloatTensor(weights)
    logger.info(f"Class weights: {class_weights}")
    
    # Create trainer
    trainer = Trainer(
        model=model,
        train_loader=train_loader,
        val_loader=val_loader,
        device=config['device'],
        learning_rate=config['learning_rate'],
        weight_decay=config['weight_decay'],
        class_weights=class_weights,
        checkpoint_dir=config['checkpoint_dir'],
        use_wandb=config['use_wandb']
    )
    
    # Train
    trainer.train(
        num_epochs=config['num_epochs'],
        early_stopping_patience=10
    )


if __name__ == "__main__":
    main()
