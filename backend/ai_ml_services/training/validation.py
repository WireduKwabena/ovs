# training/validation.py
from sklearn.model_selection import StratifiedKFold, cross_validate, learning_curve
import numpy as np
import matplotlib.pyplot as plt
import logging
from pathlib import Path
import argparse

logger = logging.getLogger(__name__)

class ModelValidator:
    """
    Comprehensive model validation.
    NOTE: This class is designed for scikit-learn compatible models.
    For PyTorch models (like AuthenticityModel), you would typically need
    a scikit-learn wrapper for your PyTorch model, or implement
    cross-validation and learning curve logic directly using PyTorch.
    """

    def __init__(self, model, X, y, n_splits=5, plot_output_dir='validation_plots'):
        self.model = model
        self.X = X
        self.y = y
        self.n_splits = n_splits
        self.plot_output_dir = Path(plot_output_dir)
        self.plot_output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"ModelValidator initialized. Plots will be saved to {self.plot_output_dir}")

    def stratified_cross_validation(self):
        """Perform stratified k-fold cross-validation"""
        logger.info(f"Starting stratified {self.n_splits}-fold cross-validation...")

        # IMPORTANT: The 'model' passed to cross_validate must be scikit-learn compatible.
        # If self.model is a raw PyTorch nn.Module, this will NOT work directly.
        # You need a wrapper (e.g., skorch) or a custom implementation.
        try:
            skf = StratifiedKFold(n_splits=self.n_splits, shuffle=True, random_state=42)

            scoring = {
                'accuracy': 'accuracy',
                'precision': 'precision',
                'recall': 'recall',
                'f1': 'f1',
                'roc_auc': 'roc_auc'
            }

            cv_results = cross_validate(
                self.model, self.X, self.y,
                cv=skf,
                scoring=scoring,
                return_train_score=True,
                # n_jobs=-1 # Removed: n_jobs=-1 is problematic with non-sklearn models or custom wrappers
            )

            logger.info("\n" + "="*60)
            logger.info("CROSS-VALIDATION RESULTS")
            logger.info("="*60)

            for metric in scoring.keys():
                train_scores = cv_results[f'train_{metric}']
                test_scores = cv_results[f'test_{metric}']

                logger.info(f"\n{metric.upper()}:")
                logger.info(f"  Train: {train_scores.mean():.4f} (+/- {train_scores.std() * 2:.4f})")
                logger.info(f"  Test: {test_scores.mean():.4f} (+/- {test_scores.std() * 2:.4f})")

            return cv_results
        except Exception as e:
            logger.error(f"Error during cross-validation. Ensure your model is scikit-learn compatible: {e}", exc_info=True)
            return None

    def learning_curve_analysis(self):
        """Analyze learning curves"""
        logger.info("Starting learning curve analysis...")

        # IMPORTANT: The 'model' passed to learning_curve must be scikit-learn compatible.
        # If self.model is a raw PyTorch nn.Module, this will NOT work directly.
        # You need a wrapper (e.g., skorch) or a custom implementation.
        try:
            train_sizes, train_scores, val_scores = learning_curve(
                self.model, self.X, self.y,
                train_sizes=np.linspace(0.1, 1.0, 10),
                cv=5,
                scoring='f1',
                # n_jobs=-1 # Removed: n_jobs=-1 is problematic with non-sklearn models or custom wrappers
            )

            train_mean = train_scores.mean(axis=1)
            train_std = train_scores.std(axis=1)
            val_mean = val_scores.mean(axis=1)
            val_std = val_scores.std(axis=1)

            plt.figure(figsize=(10, 6))
            plt.plot(train_sizes, train_mean, label='Training score', color='blue')
            plt.fill_between(train_sizes, train_mean - train_std,
                            train_mean + train_std, alpha=0.2, color='blue')
            plt.plot(train_sizes, val_mean, label='Cross-validation score', color='orange')
            plt.fill_between(train_sizes, val_mean - val_std,
                            val_mean + val_std, alpha=0.2, color='orange')

            plt.xlabel('Training Size')
            plt.ylabel('F1 Score')
            plt.title('Learning Curves')
            plt.legend(loc='best')
            plt.grid(alpha=0.3)
            plt.tight_layout()
            plot_path = self.plot_output_dir / 'learning_curves.png'
            plt.savefig(plot_path)
            plt.close()
            logger.info(f"Learning curves plot saved to {plot_path}")

            return train_sizes, train_scores, val_scores
        except Exception as e:
            logger.error(f"Error during learning curve analysis. Ensure your model is scikit-learn compatible: {e}", exc_info=True)
            return None

def main():
    parser = argparse.ArgumentParser(description="Perform model validation.")
    parser.add_argument('--plot_output_dir', type=str, default='validation_plots', help='Directory to save validation plots.')
    parser.add_argument('--n_splits', type=int, default=5, help='Number of splits for stratified k-fold cross-validation.')
    # Add arguments for model, X, y if you were to run this standalone with dummy data
    # For a real scenario, you'd load a trained model and data here.

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger.info("Running validation script (Note: This script requires a scikit-learn compatible model).")

    # Example usage with dummy data (replace with your actual model and data loading)
    from sklearn.linear_model import LogisticRegression
    from sklearn.datasets import make_classification

    X_dummy, y_dummy = make_classification(n_samples=1000, n_features=20, n_classes=2, random_state=42)
    dummy_model = LogisticRegression(random_state=42)

    validator = ModelValidator(
        model=dummy_model,
        X=X_dummy,
        y=y_dummy,
        n_splits=args.n_splits,
        plot_output_dir=args.plot_output_dir
    )

    validator.stratified_cross_validation()
    validator.learning_curve_analysis()

if __name__ == "__main__":
    main()