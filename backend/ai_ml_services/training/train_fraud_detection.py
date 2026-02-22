# training/train_fraud_detection.py
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    classification_report, confusion_matrix, roc_auc_score,
    roc_curve, auc, precision_recall_curve
)
import matplotlib.pyplot as plt
try:
    import seaborn as sns
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    sns = None
import joblib
import os
import argparse
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FraudDetectionTrainer:
    """Train fraud detection models"""

    def __init__(self, model_output_dir='models', plot_output_dir='training_plots'):
        self.scaler = StandardScaler()
        self.models = {}
        self.best_model = None
        self.best_score = 0
        self.feature_names = None

        self.model_output_dir = Path(model_output_dir)
        self.model_output_dir.mkdir(parents=True, exist_ok=True)
        self.plot_output_dir = Path(plot_output_dir)
        self.plot_output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"FraudDetectionTrainer initialized. Models to {self.model_output_dir}, plots to {self.plot_output_dir}")


    def load_data(self, train_path: str, test_path: str):
        """Load training and test data"""
        logger.info(f"Loading data from {train_path} and {test_path}...")
        try:
            train_df = pd.read_csv(train_path)
            test_df = pd.read_csv(test_path)
        except FileNotFoundError as e:
            logger.error(f"Data file not found: {e}. Please ensure data is generated.")
            raise

        # Separate features and labels
        feature_cols = [col for col in train_df.columns
                       if col not in ['application_id', 'is_fraud']]

        X_train = train_df[feature_cols].values
        y_train = train_df['is_fraud'].values

        X_test = test_df[feature_cols].values
        y_test = test_df['is_fraud'].values

        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        self.feature_names = feature_cols
        logger.info(f"Data loaded. Train samples: {len(X_train)}, Test samples: {len(X_test)}")
        logger.info(f"Features used: {self.feature_names}")

        return X_train_scaled, X_test_scaled, y_train, y_test

    def train_random_forest(self, X_train, y_train, n_estimators=200, max_depth=15, min_samples_split=10, min_samples_leaf=4, class_weight='balanced'):
        """Train Random Forest classifier"""
        logger.info("\nTraining Random Forest...")

        rf_model = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            min_samples_split=min_samples_split,
            min_samples_leaf=min_samples_leaf,
            class_weight=class_weight,
            random_state=42,
            n_jobs=-1
        )

        rf_model.fit(X_train, y_train)

        # Cross-validation
        cv_scores = cross_val_score(rf_model, X_train, y_train, cv=5,
                                   scoring='f1', n_jobs=-1)

        logger.info(f"RF CV F1 Scores: {cv_scores}")
        logger.info(f"RF Mean CV F1: {cv_scores.mean():.4f} (+/- {cv_scores.std() * 2:.4f})")

        self.models['random_forest'] = rf_model
        return rf_model, cv_scores.mean()

    def train_gradient_boosting(self, X_train, y_train, n_estimators=200, learning_rate=0.1, max_depth=5, min_samples_split=10, min_samples_leaf=4, subsample=0.8):
        """Train Gradient Boosting classifier"""
        logger.info("\nTraining Gradient Boosting...")

        gb_model = GradientBoostingClassifier(
            n_estimators=n_estimators,
            learning_rate=learning_rate,
            max_depth=max_depth,
            min_samples_split=min_samples_split,
            min_samples_leaf=min_samples_leaf,
            subsample=subsample,
            random_state=42
        )

        gb_model.fit(X_train, y_train)

        # Cross-validation
        cv_scores = cross_val_score(gb_model, X_train, y_train, cv=5,
                                   scoring='f1', n_jobs=-1)

        logger.info(f"GB CV F1 Scores: {cv_scores}")
        logger.info(f"GB Mean CV F1: {cv_scores.mean():.4f} (+/- {cv_scores.std() * 2:.4f})")

        self.models['gradient_boosting'] = gb_model
        return gb_model, cv_scores.mean()

    def train_all_models(self, X_train, y_train, rf_params: dict, gb_params: dict):
        """Train all models and select best"""
        logger.info("Training all models...")
        results = {}

        rf_model, rf_score = self.train_random_forest(X_train, y_train, **rf_params)
        results['random_forest'] = rf_score

        gb_model, gb_score = self.train_gradient_boosting(X_train, y_train, **gb_params)
        results['gradient_boosting'] = gb_score

        # Select best
        best_model_name = max(results, key=results.get)
        self.best_model = self.models[best_model_name]
        self.best_score = results[best_model_name]

        logger.info(f"\n✓ Best model: {best_model_name} (F1: {self.best_score:.4f})")

        return results

    def evaluate(self, X_test, y_test):
        """Comprehensive evaluation"""
        if self.best_model is None:
            logger.error("No model trained yet!")
            raise ValueError("No model trained yet!")

        y_pred = self.best_model.predict(X_test)
        y_proba = self.best_model.predict_proba(X_test)[:, 1]

        logger.info("\n" + "="*60)
        logger.info("TEST SET EVALUATION")
        logger.info("="*60)

        # Classification report
        logger.info("\nClassification Report:")
        logger.info(classification_report(y_test, y_pred,
                                   target_names=['Legitimate', 'Fraud']))

        # Confusion matrix
        cm = confusion_matrix(y_test, y_pred)
        logger.info("\nConfusion Matrix:\n" + str(cm))

        # ROC-AUC
        auc_score = roc_auc_score(y_test, y_proba)
        logger.info(f"\nROC-AUC Score: {auc_score:.4f}")

        # Plot visualizations
        self.plot_feature_importance()
        self.plot_confusion_matrix(cm)
        self.plot_roc_curve(y_test, y_proba)

        return {
            'y_pred': y_pred,
            'y_proba': y_proba,
            'auc_score': auc_score,
            'confusion_matrix': cm
        }

    def plot_feature_importance(self):
        """Plot feature importance"""
        if self.feature_names is None:
            logger.warning("Feature names not available for plotting importance.")
            return

        if hasattr(self.best_model, 'feature_importances_'):
            importances = self.best_model.feature_importances_
            indices = np.argsort(importances)[::-1]

            plt.figure(figsize=(12, 8))
            plt.title('Feature Importance')
            plt.bar(range(len(importances)), importances[indices])
            plt.xticks(range(len(importances)),
                      [self.feature_names[i] for i in indices],
                      rotation=45, ha='right')
            plt.ylabel('Importance')
            plt.tight_layout()
            plot_path = self.plot_output_dir / 'fraud_feature_importance.png'
            plt.savefig(plot_path)
            plt.close()
            logger.info(f"Feature importance plot saved to {plot_path}")

            logger.info("\nTop 5 Most Important Features:")
            for i in range(min(5, len(importances))):
                idx = indices[i]
                logger.info(f"{i+1}. {self.feature_names[idx]}: {importances[idx]:.4f}")
        else:
            logger.warning("Selected model does not have 'feature_importances_' attribute for plotting.")


    def plot_confusion_matrix(self, cm):
        """Plot confusion matrix"""
        plt.figure(figsize=(8, 6))
        if sns is not None:
            sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                       xticklabels=['Legitimate', 'Fraud'],
                       yticklabels=['Legitimate', 'Fraud'])
        else:
            plt.imshow(cm, interpolation='nearest', cmap='Blues')
            for row in range(cm.shape[0]):
                for col in range(cm.shape[1]):
                    plt.text(col, row, str(cm[row, col]), ha='center', va='center')
            plt.xticks([0, 1], ['Legitimate', 'Fraud'])
            plt.yticks([0, 1], ['Legitimate', 'Fraud'])
        plt.title('Confusion Matrix - Fraud Detection')
        plt.ylabel('True Label')
        plt.xlabel('Predicted Label')
        plt.tight_layout()
        plot_path = self.plot_output_dir / 'fraud_confusion_matrix.png'
        plt.savefig(plot_path)
        plt.close()
        logger.info(f"Confusion matrix plot saved to {plot_path}")


    def plot_roc_curve(self, y_test, y_proba):
        """Plot ROC curve"""
        fpr, tpr, _ = roc_curve(y_test, y_proba)
        roc_auc = auc(fpr, tpr)

        plt.figure(figsize=(8, 6))
        plt.plot(fpr, tpr, color='darkorange', lw=2,
                label=f'ROC curve (AUC = {roc_auc:.2f})')
        plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--')
        plt.xlim([0.0, 1.0])
        plt.ylim([0.0, 1.05])
        plt.xlabel('False Positive Rate')
        plt.ylabel('True Positive Rate')
        plt.title('ROC Curve - Fraud Detection')
        plt.legend(loc="lower right")
        plt.grid(alpha=0.3)
        plt.tight_layout()
        plot_path = self.plot_output_dir / 'fraud_roc_curve.png'
        plt.savefig(plot_path)
        plt.close()
        logger.info(f"ROC curve plot saved to {plot_path}")


    def save_model(self):
        """Save trained model and scaler"""
        model_path = self.model_output_dir / 'fraud_detector.pkl'
        scaler_path = self.model_output_dir / 'fraud_scaler.pkl'

        joblib.dump(self.best_model, model_path)
        joblib.dump(self.scaler, scaler_path)

        logger.info(f"\n✓ Best model saved to {model_path}")
        logger.info(f"✓ Scaler saved to {scaler_path}")


def main():
    parser = argparse.ArgumentParser(description="Train Fraud Detection Models.")
    parser.add_argument('--train_data_path', type=str, default='data/fraud_detection/train.csv',
                        help='Path to the training data CSV.')
    parser.add_argument('--test_data_path', type=str, default='data/fraud_detection/test.csv',
                        help='Path to the test data CSV.')
    parser.add_argument('--model_output_dir', type=str, default='models',
                        help='Directory to save the trained model and scaler.')
    parser.add_argument('--plot_output_dir', type=str, default='training_plots',
                        help='Directory to save evaluation plots.')
    parser.add_argument('--n_samples_generate', type=int, default=10000,
                        help='Number of synthetic samples to generate if data not found.')
    parser.add_argument('--fraud_ratio_generate', type=float, default=0.15,
                        help='Fraud ratio for synthetic data generation if data not found.')

    # Random Forest Hyperparameters
    parser.add_argument('--rf_n_estimators', type=int, default=200, help='RF: Number of trees.')
    parser.add_argument('--rf_max_depth', type=int, default=15, help='RF: Max depth of trees.')
    parser.add_argument('--rf_min_samples_split', type=int, default=10, help='RF: Min samples to split node.')
    parser.add_argument('--rf_min_samples_leaf', type=int, default=4, help='RF: Min samples per leaf.')
    parser.add_argument('--rf_class_weight', type=str, default='balanced', help='RF: Class weight.')

    # Gradient Boosting Hyperparameters
    parser.add_argument('--gb_n_estimators', type=int, default=200, help='GB: Number of boosting stages.')
    parser.add_argument('--gb_learning_rate', type=float, default=0.1, help='GB: Learning rate.')
    parser.add_argument('--gb_max_depth', type=int, default=5, help='GB: Max depth of individual estimators.')
    parser.add_argument('--gb_min_samples_split', type=int, default=10, help='GB: Min samples to split node.')
    parser.add_argument('--gb_min_samples_leaf', type=int, default=4, help='GB: Min samples per leaf.')
    parser.add_argument('--gb_subsample', type=float, default=0.8, help='GB: Subsample ratio.')


    args = parser.parse_args()

    # Initialize trainer
    trainer = FraudDetectionTrainer(
        model_output_dir=args.model_output_dir,
        plot_output_dir=args.plot_output_dir
    )

    # Attempt to load data, generate if not found
    try:
        X_train, X_test, y_train, y_test = trainer.load_data(
            args.train_data_path,
            args.test_data_path
        )
    except FileNotFoundError:
        logger.info("Data files not found. Generating synthetic data...")
        from ai_ml_services.datasets.fraud_data_generator import FraudDatasetGenerator
        generator = FraudDatasetGenerator()
        train_df, test_df = generator.generate_application_data(
            n_samples=args.n_samples_generate,
            fraud_ratio=args.fraud_ratio_generate
        )
        generator.save_dataset(train_df, test_df, output_dir=Path(args.train_data_path).parent)
        
        X_train, X_test, y_train, y_test = trainer.load_data(
            args.train_data_path,
            args.test_data_path
        )

    logger.info(f"Train samples: {len(X_train)}")
    logger.info(f"Test samples: {len(X_test)}")
    logger.info(f"Fraud ratio (train): {y_train.mean():.2%}")
    logger.info(f"Fraud ratio (test): {y_test.mean():.2%}")

    # Define model parameters from args
    rf_params = {
        'n_estimators': args.rf_n_estimators,
        'max_depth': args.rf_max_depth,
        'min_samples_split': args.rf_min_samples_split,
        'min_samples_leaf': args.rf_min_samples_leaf,
        'class_weight': args.rf_class_weight
    }
    gb_params = {
        'n_estimators': args.gb_n_estimators,
        'learning_rate': args.gb_learning_rate,
        'max_depth': args.gb_max_depth,
        'min_samples_split': args.gb_min_samples_split,
        'min_samples_leaf': args.gb_min_samples_leaf,
        'subsample': args.gb_subsample
    }

    # Train models
    logger.info("\nTraining models...")
    results = trainer.train_all_models(X_train, y_train, rf_params, gb_params)

    # Evaluate
    logger.info("\nEvaluating on test set...")
    eval_results = trainer.evaluate(X_test, y_test)

    # Save model
    trainer.save_model()

    logger.info("\n✓ Training complete!")

if __name__ == "__main__":
    main()

