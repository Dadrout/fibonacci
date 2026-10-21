FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    fonts-noto-core \
    tesseract-ocr \
    tesseract-ocr-rus \
    tesseract-ocr-kaz \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 10001 --create-home --shell /usr/sbin/nologin app

WORKDIR /app

COPY pyproject.toml constraints.txt ./
COPY app ./app
COPY worker.py gunicorn.conf.py ./

RUN pip install --no-cache-dir --upgrade pip==26.2.1 \
    && pip install --no-cache-dir -c constraints.txt gunicorn uvicorn \
    && pip install --no-cache-dir -c constraints.txt . \
    && mkdir -p /app/static /app/brain-media \
    && chown -R app:app /app

RUN pip install --no-cache-dir --upgrade setuptools==83.0.0

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["gunicorn", "-c", "gunicorn.conf.py", "app.main:app"]
