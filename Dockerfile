# ---- Base image ----
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps needed by Pillow for image processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo \
    zlib1g \
    && rm -rf /var/lib/apt/lists/*

# ---- Install Python deps first (better layer caching) ----
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- Copy application code ----
COPY app ./app
COPY assets ./assets
COPY demo ./demo
RUN mkdir -p outputs

# Download Noto Sans (full Unicode coverage) at build time so the non-root
# runtime user doesn't need write access to assets/fonts/.
RUN python -c "\
import urllib.request; \
url = 'https://github.com/google/fonts/raw/main/ofl/notosans/NotoSans%5Bwdth%2Cwght%5D.ttf'; \
urllib.request.urlretrieve(url, 'assets/fonts/regular.ttf'); \
import shutil; shutil.copy('assets/fonts/regular.ttf', 'assets/fonts/bold.ttf')" \
 || echo "Font download failed – cards will use PIL fallback font."

# Run as non-root user
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
