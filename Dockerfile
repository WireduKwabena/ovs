FROM python:3.11-slim AS backend

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       gcc \
       libpq-dev \
       libgl1 \
       libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements ./requirements
ARG REQUIREMENTS_FILE=production.txt
ARG INSTALL_AI_ML_DEPS=true
RUN cp -r requirements /tmp/requirements \
    && if [ "${INSTALL_AI_ML_DEPS}" != "true" ]; then \
         sed -i -E '/^(torch|torchvision|tensorflow|scikit-learn|opencv-python|opencv-contrib-python|opencv-python-headless|mediapipe|facenet-pytorch|easyocr|pdf2image|PyPDF2|transformers|sentencepiece|tokenizers|openai-whisper|moviepy|librosa|soundfile|pandas|seaborn|scipy|joblib|albumentations|piexif|imagehash|spacy|wandb)([=;<].*)?$/d' /tmp/requirements/base.txt; \
       else \
         sed -i 's/^torch==2\.2\.2$/torch==2.2.2+cpu/; s/^torchvision==0\.17\.2$/torchvision==0.17.2+cpu/' /tmp/requirements/base.txt /tmp/requirements/constraints.lock.txt; \
       fi \
    && pip install --upgrade pip \
    && pip install \
       --timeout 120 \
       --retries 20 \
       --resume-retries 20 \
       -r /tmp/requirements/${REQUIREMENTS_FILE} \
       -c /tmp/requirements/constraints.lock.txt

COPY backend/ .

EXPOSE 8000

CMD ["gunicorn", "config.asgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]
