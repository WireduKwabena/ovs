# datasets/sources.py
DOCUMENT_DATASETS = {
    'casia_v2': {
        'name': 'CASIA Image Tampering Detection',
        'url': 'https://github.com/namtpham/casia2groundtruth',
        'size': '12,614 images',
        'types': ['authentic', 'tampered'],
        'description': 'Image forgery detection dataset'
    },
    'columbia': {
        'name': 'Columbia Uncompressed Image Splicing',
        'url': 'https://www.ee.columbia.edu/ln/dvmm/downloads/authsplcuncmp/',
        'size': '933 authentic + 912 spliced',
        'types': ['authentic', 'spliced'],
        'description': 'Image splicing detection'
    },
    'coverage': {
        'name': 'COVERAGE Dataset',
        'url': 'https://github.com/wenbihan/coverage',
        'size': '100 authentic + 100 forged',
        'types': ['authentic', 'copy-move'],
        'description': 'Copy-move forgery detection'
    },
    'rvl_cdip': {
        'name': 'RVL-CDIP',
        'url': 'https://www.cs.cmu.edu/~aharley/rvl-cdip/',
        'size': '400,000 grayscale images',
        'types': ['16 document categories'],
        'description': 'Document image classification'
    },
    'midv_500': {
        'name': 'MIDV-500',
        'url': 'http://smartengines.biz/midv-500/',
        'size': '500 video clips',
        'types': ['50 ID document types'],
        'description': 'Identity document dataset'
    }
}

# Local folder mappings for raw datasets already downloaded in this project.
# These paths are relative to `backend/ai_ml_services/datasets/raw_dataset`.
LOCAL_RAW_DATASET_LAYOUTS = {
    "casia2": {
        "root": "CASIA2",
        "authentic_dirs": ["Au"],
        "forged_dirs": ["Tp"],
    },
    "dataset_real_fake": {
        "root": "Dataset",
        "authentic_dirs": ["real"],
        "forged_dirs": ["fake"],
    },
    "imsplice": {
        "root": "ImSpliceDataset",
        "authentic_prefixes": ["Au-"],
        "forged_prefixes": ["Sp-"],
    },
    "coverage": {
        "root": "COVERAGE",
        "special_parser": "coverage_pairs",
        "notes": [
            "image/{id}.tif => authentic",
            "image/{id}t.tif => forged",
        ],
    },
    "cedar_signatures": {
        "root": "signatures",
        "authentic_dirs": ["full_org"],
        "forged_dirs": ["full_forg"],
        "mixed_dirs": ["signatures_1..signatures_55 (original_* / forgeries_*)"],
    },
    "gpds_signatures": {
        "root": "New folder (10)",
        "authentic_dirs": ["train/genuine", "test/*/genuine"],
        "forged_dirs": ["train/forge", "test/*/forge"],
        "filename_hints": ["c-*.jpg => authentic", "cf-*.jpg => forged"],
    },
    "resumes_pdf": {
        "root": "Resumes PDF",
        "special_parser": "resume_metadata",
        "notes": [
            "Folder names map to resume categories.",
            "Use create_resume_metadata.py for normalization and train/val/test split.",
        ],
    },
}
