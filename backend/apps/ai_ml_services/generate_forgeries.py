"""
Synthetic Forgery Generator
============================

Automatically create forged documents from authentic ones.

Usage:
    python generate_forgeries.py \
        --input data/authentic \
        --output data/forged \
        --num_per_image 3 \
        --forgery_types all

This will create 3 forged versions of each authentic document.
"""

import cv2
import numpy as np
from pathlib import Path
from PIL import Image
import argparse
from tqdm import tqdm
import random
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ForgeryGenerator:
    """Generate synthetic forgeries from authentic documents."""
    
    @staticmethod
    def copy_move_forgery(image: np.ndarray, num_regions: int = 1) -> np.ndarray:
        """Create copy-move forgery by duplicating regions."""
        h, w = image.shape[:2]
        forged = image.copy()
        
        for _ in range(num_regions):
            region_h = random.randint(int(h * 0.1), int(h * 0.3))
            region_w = random.randint(int(w * 0.1), int(w * 0.3))
            
            src_x = random.randint(0, w - region_w)
            src_y = random.randint(0, h - region_h)
            dst_x = random.randint(0, w - region_w)
            dst_y = random.randint(0, h - region_h)
            
            while (abs(dst_x - src_x) < region_w and 
                   abs(dst_y - src_y) < region_h):
                dst_x = random.randint(0, w - region_w)
                dst_y = random.randint(0, h - region_h)
            
            region = image[src_y:src_y+region_h, src_x:src_x+region_w]
            forged[dst_y:dst_y+region_h, dst_x:dst_x+region_w] = region
        
        return forged
    
    @staticmethod
    def resampling_forgery(image: np.ndarray) -> np.ndarray:
        """Create resampling forgery by resizing regions."""
        h, w = image.shape[:2]
        forged = image.copy()
        
        region_h = random.randint(int(h * 0.2), int(h * 0.4))
        region_w = random.randint(int(w * 0.2), int(w * 0.4))
        x = random.randint(0, w - region_w)
        y = random.randint(0, h - region_h)
        
        region = image[y:y+region_h, x:x+region_w]
        scale = random.uniform(0.6, 0.9)
        resized = cv2.resize(region, 
                           (int(region_w * scale), int(region_h * scale)))
        padded = cv2.resize(resized, (region_w, region_h))
        forged[y:y+region_h, x:x+region_w] = padded
        
        return forged
    
    @staticmethod
    def jpeg_compression_attack(image: np.ndarray, quality: int = None) -> np.ndarray:
        """Apply JPEG compression."""
        if quality is None:
            quality = random.randint(60, 85)
        
        pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        
        import io
        buffer = io.BytesIO()
        pil_image.save(buffer, format='JPEG', quality=quality)
        buffer.seek(0)
        compressed = Image.open(buffer)
        
        return cv2.cvtColor(np.array(compressed), cv2.COLOR_RGB2BGR)


def generate_forgeries(input_dir: str, output_dir: str, num_per_image: int = 3):
    """Generate synthetic forgeries."""
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    generator = ForgeryGenerator()
    
    image_files = []
    for ext in ['*.jpg', '*.jpeg', '*.png']:
        image_files.extend(list(input_path.glob(ext)))
    
    logger.info(f"Found {len(image_files)} authentic images")
    
    for img_file in tqdm(image_files, desc="Generating"):
        image = cv2.imread(str(img_file))
        if image is None:
            continue
        
        for i in range(num_per_image):
            forgery_type = random.choice(['copy_move', 'resampling', 'jpeg'])
            
            if forgery_type == 'copy_move':
                forged = generator.copy_move_forgery(image)
            elif forgery_type == 'resampling':
                forged = generator.resampling_forgery(image)
            else:
                forged = generator.jpeg_compression_attack(image)
            
            output_file = output_path / f"{img_file.stem}_forged_{i}.jpg"
            cv2.imwrite(str(output_file), forged)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--num_per_image', type=int, default=3)
    
    args = parser.parse_args()
    generate_forgeries(args.input, args.output, args.num_per_image)
