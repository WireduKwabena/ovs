# training/hyperparameter_tuning.py
from sklearn.model_selection import GridSearchCV, RandomizedSearchCV
from scipy.stats import randint, uniform
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
import joblib
import os
import argparse
import logging
import pandas as pd
import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)

# Assuming fraud_data_generator is available for dummy data
try:
    from ai_ml_services.datasets.fraud_data_generator import FraudDatasetGenerator
except ImportError:
    logger.warning("Could not import FraudDatasetGenerator. Dummy data will be used if main is run.")
    class FraudDatasetGenerator:
        def generate_application_data(self, n_samples=100, fraud_ratio=0.1):
            return pd.DataFrame(np.random.rand(n_samples, 10), columns=[f'feature_{i}' for i in range(10)]), \
                   pd.DataFrame(np.random.randint(0, 2, n_samples), columns=['is_fraud'])
        def save_dataset(self, *args):
            pass

class HyperparameterTuner:
    """Hyperparameter optimization for scikit-learn models"""

    def __init__(self, output_dir='tuned_models'):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Tuned models will be saved to {self.output_dir}")

    def grid_search_rf(self, X_train, y_train, cv=5, param_grid=None):
        """Grid search for Random Forest"""
        if param_grid is None:
            param_grid = {
                'n_estimators': [100, 200, 300],
                'max_depth': [10, 15, 20, None],
                'min_samples_split': [2, 5, 10],
                'min_samples_leaf': [1, 2, 4],
                'class_weight': ['balanced', 'balanced_subsample']
            }

        rf = RandomForestClassifier(random_state=42)

        grid_search = GridSearchCV(
            rf, param_grid,
            cv=cv,
            scoring='f1',
            n_jobs=-1,
            verbose=2
        )

        logger.info("Starting Grid Search for RandomForestClassifier...")
        grid_search.fit(X_train, y_train)

        logger.info(f"\nBest parameters: {grid_search.best_params_}")
        logger.info(f"Best F1 score: {grid_search.best_score_:.4f}")

        best_estimator_path = self.output_dir / 'best_random_forest.joblib'
        joblib.dump(grid_search.best_estimator_, best_estimator_path)
        logger.info(f"Best RandomForestClassifier saved to {best_estimator_path}")

        return grid_search.best_estimator_

    def random_search_gb(self, X_train, y_train, cv=5, n_iter=50, param_dist=None):
        """Random search for Gradient Boosting"""
        if param_dist is None:
            param_dist = {
                'n_estimators': randint(100, 500),
                'learning_rate': uniform(0.01, 0.3),
                'max_depth': randint(3, 10),
                'min_samples_split': randint(2, 20),
                'min_samples_leaf': randint(1, 10),
                'subsample': uniform(0.6, 0.4)
            }

        gb = GradientBoostingClassifier(random_state=42)

        random_search = RandomizedSearchCV(
            gb, param_dist,
            n_iter=n_iter,
            cv=cv,
            scoring='f1',
            n_jobs=-1,
            verbose=2,
            random_state=42
        )

        logger.info("Starting Random Search for GradientBoostingClassifier...")
        random_search.fit(X_train, y_train)

        logger.info(f"\nBest parameters: {random_search.best_params_}")
        logger.info(f"Best F1 score: {random_search.best_score_:.4f}")

        best_estimator_path = self.output_dir / 'best_gradient_boosting.joblib'
        joblib.dump(random_search.best_estimator_, best_estimator_path)
        logger.info(f"Best GradientBoostingClassifier saved to {best_estimator_path}")

        return random_search.best_estimator_

def main():
    parser = argparse.ArgumentParser(description="Perform hyperparameter tuning for scikit-learn models.")
    parser.add_argument('--model_type', type=str, choices=['rf', 'gb'], default='rf',
                        help='Type of model to tune: Random Forest (rf) or Gradient Boosting (gb).')
    parser.add_argument('--n_samples', type=int, default=1000,
                        help='Number of synthetic samples to generate for tuning.')
    parser.add_argument('--fraud_ratio', type=float, default=0.15,
                        help='Fraud ratio for synthetic data generation.')
    parser.add_argument('--cv_folds', type=int, default=5,
                        help='Number of cross-validation folds.')
    parser.add_argument('--n_iter_random', type=int, default=50,
                        help='Number of iterations for RandomizedSearchCV (only for gb).')
    parser.add_argument('--output_dir', type=str, default='tuned_models',
                        help='Directory to save the best tuned models.')

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    logger.info("Generating synthetic fraud data for hyperparameter tuning...")
    fraud_gen = FraudDatasetGenerator()
    train_df, _ = fraud_gen.generate_application_data(n_samples=args.n_samples, fraud_ratio=args.fraud_ratio)

    # Assuming 'is_fraud' is the target column
    X_train = train_df.drop('is_fraud', axis=1)
    # Drop non-numeric columns like 'application_id' if present
    X_train = X_train.select_dtypes(include=np.number)
    y_train = train_df['is_fraud']

    tuner = HyperparameterTuner(output_dir=args.output_dir)

    if args.model_type == 'rf':
        tuner.grid_search_rf(X_train, y_train, cv=args.cv_folds)
    elif args.model_type == 'gb':
        tuner.random_search_gb(X_train, y_train, cv=args.cv_folds, n_iter=args.n_iter_random)

    logger.info("\nHyperparameter tuning complete.")
    logger.info("Note: For PyTorch models, consider using libraries like Optuna or Ray Tune for hyperparameter optimization.")

if __name__ == "__main__":
    main()

