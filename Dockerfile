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
RUN cp -r requirements /tmp/requirements \
    && sed -i 's/^torch==2\.2\.2$/torch==2.2.2+cpu/; s/^torchvision==0\.17\.2$/torchvision==0.17.2+cpu/' /tmp/requirements/base.txt /tmp/requirements/constraints.lock.txt \
    && pip install --upgrade pip \
    && pip install \
       --timeout 120 \
       --retries 20 \
       --resume-retries 20 \
       -r /tmp/requirements/${REQUIREMENTS_FILE} \
       -c /tmp/requirements/constraints.lock.txt

COPY backend/ .

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]
