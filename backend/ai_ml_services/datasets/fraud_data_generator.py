# datasets/fraud_data_generator.py
from pathlib import Path
import pandas as pd
import numpy as np
import argparse
import logging

logger = logging.getLogger(__name__)

class FraudDatasetGenerator:
    """Generate synthetic fraud detection training data"""

    def generate_application_data(self, n_samples: int = 10000, fraud_ratio: float = 0.15):
        """Generate synthetic application data based on real-world patterns"""
        np.random.seed(42)

        n_fraud = int(n_samples * fraud_ratio)
        n_legitimate = n_samples - n_fraud

        data = []

        # Generate legitimate applications
        for i in range(n_legitimate):
            app = self._generate_legitimate_application(i)
            data.append(app)

        # Generate fraudulent applications
        for i in range(n_fraud):
            app = self._generate_fraudulent_application(i + n_legitimate)
            data.append(app)

        df = pd.DataFrame(data)
        df = df.sample(frac=1).reset_index(drop=True)  # Shuffle

        # Split
        train_size = int(0.8 * len(df))
        train_df = df[:train_size]
        test_df = df[train_size:]

        return train_df, test_df

    def _generate_legitimate_application(self, idx: int):
        """Generate a legitimate application with normal patterns"""
        return {
            'application_id': f'APP_{idx:06d}',
            'num_documents': np.random.randint(3, 8),
            'avg_ocr_confidence': np.random.uniform(0.85, 0.98),
            'avg_authenticity_score': np.random.uniform(0.88, 0.99),
            'consistency_score': np.random.uniform(0.82, 0.97),
            'submission_hour': np.random.choice(range(8, 18)),  # Business hours
            'form_completeness': np.random.uniform(0.9, 1.0),
            'word_count_normalized': np.random.uniform(0.3, 0.8),
            'special_char_ratio': np.random.uniform(0.05, 0.15),
            'has_metadata_ratio': np.random.uniform(0.7, 1.0),
            'email_suspicious': 0,
            'processing_time': np.random.uniform(120, 600),
            'previous_applications': np.random.poisson(0.5),
            'is_fraud': 0
        }

    def _generate_fraudulent_application(self, idx: int):
        """Generate fraudulent application with suspicious patterns"""
        fraud_type = np.random.choice(['low_quality', 'mass_submission', 'fake_docs', 'stolen_identity'])

        base = {
            'application_id': f'APP_{idx:06d}',
            'is_fraud': 1
        }

        if fraud_type == 'low_quality':
            base.update({
                'num_documents': np.random.randint(1, 4),
                'avg_ocr_confidence': np.random.uniform(0.3, 0.6),
                'avg_authenticity_score': np.random.uniform(0.4, 0.7),
                'consistency_score': np.random.uniform(0.3, 0.6),
                'submission_hour': np.random.choice(range(0, 24)),
                'form_completeness': np.random.uniform(0.5, 0.8),
                'word_count_normalized': np.random.uniform(0.1, 0.4),
                'special_char_ratio': np.random.uniform(0.2, 0.4),
                'has_metadata_ratio': np.random.uniform(0.0, 0.4),
                'email_suspicious': np.random.choice([0, 1], p=[0.3, 0.7]),
                'processing_time': np.random.uniform(30, 120),
                'previous_applications': 0
            })
        elif fraud_type == 'mass_submission':
            base.update({
                'num_documents': np.random.randint(2, 5),
                'avg_ocr_confidence': np.random.uniform(0.7, 0.85),
                'avg_authenticity_score': np.random.uniform(0.65, 0.82),
                'consistency_score': np.random.uniform(0.5, 0.75),
                'submission_hour': np.random.choice(range(0, 6)),  # Late night
                'form_completeness': np.random.uniform(0.6, 0.9),
                'word_count_normalized': np.random.uniform(0.2, 0.5),
                'special_char_ratio': np.random.uniform(0.1, 0.25),
                'has_metadata_ratio': np.random.uniform(0.3, 0.6),
                'email_suspicious': 1,
                'processing_time': np.random.uniform(20, 90),
                'previous_applications': np.random.randint(3, 10)
            })
        elif fraud_type == 'fake_docs':
            base.update({
                'num_documents': np.random.randint(3, 7),
                'avg_ocr_confidence': np.random.uniform(0.75, 0.9),
                'avg_authenticity_score': np.random.uniform(0.3, 0.65),  # Low
                'consistency_score': np.random.uniform(0.4, 0.7),
                'submission_hour': np.random.choice(range(0, 24)),
                'form_completeness': np.random.uniform(0.8, 0.95),
                'word_count_normalized': np.random.uniform(0.3, 0.7),
                'special_char_ratio': np.random.uniform(0.15, 0.3),
                'has_metadata_ratio': np.random.uniform(0.1, 0.5),  # Stripped
                'email_suspicious': np.random.choice([0, 1], p=[0.4, 0.6]),
                'processing_time': np.random.uniform(60, 300),
                'previous_applications': np.random.poisson(1)
            })
        else:  # stolen_identity
            base.update({
                'num_documents': np.random.randint(4, 8),
                'avg_ocr_confidence': np.random.uniform(0.85, 0.95),  # Good quality
                'avg_authenticity_score': np.random.uniform(0.8, 0.95),  # Real docs
                'consistency_score': np.random.uniform(0.4, 0.65),  # Inconsistent info
                'submission_hour': np.random.choice(range(0, 24)),
                'form_completeness': np.random.uniform(0.7, 0.95),
                'word_count_normalized': np.random.uniform(0.3, 0.8),
                'special_char_ratio': np.random.uniform(0.08, 0.18),
                'has_metadata_ratio': np.random.uniform(0.6, 0.9),
                'email_suspicious': 1,
                'processing_time': np.random.uniform(100, 400),
                'previous_applications': np.random.randint(0, 3)
            })

        return base

    def save_dataset(self, train_df: pd.DataFrame, test_df: pd.DataFrame, output_dir: str = 'data/fraud_detection'):
        """Save datasets to CSV"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        train_df.to_csv(output_path / 'train.csv', index=False)
        test_df.to_csv(output_path / 'test.csv', index=False)

        logger.info(f"Saved training set: {len(train_df)} samples to {output_path / 'train.csv'}")
        logger.info(f"Saved test set: {len(test_df)} samples to {output_path / 'test.csv'}")
        logger.info(f"Fraud ratio (train): {train_df['is_fraud'].mean():.2%}")
        logger.info(f"Fraud ratio (test): {test_df['is_fraud'].mean():.2%}")

def main():
    parser = argparse.ArgumentParser(description="Generate synthetic fraud detection training data.")
    parser.add_argument('--n_samples', type=int, default=10000,
                        help='Number of total samples to generate.')
    parser.add_argument('--fraud_ratio', type=float, default=0.15,
                        help='Ratio of fraudulent samples in the dataset.')
    parser.add_argument('--output_dir', type=str, default='data/fraud_detection',
                        help='Directory to save the generated CSV files.')
    
    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    generator = FraudDatasetGenerator()
    train_df, test_df = generator.generate_application_data(
        n_samples=args.n_samples,
        fraud_ratio=args.fraud_ratio
    )
    generator.save_dataset(train_df, test_df, output_dir=args.output_dir)

if __name__ == "__main__":
    main()