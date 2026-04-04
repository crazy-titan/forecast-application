FROM python:3.10-slim

WORKDIR /app

# Install system dependencies for statsmodels and other scientific packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    gfortran \
    libopenblas-dev \
    liblapack-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expands PORT from environment, defaults to 7860 (Hugging Face default)
ENV PORT=7860
EXPOSE 7860

# Ensure world-writable temporary directories for HF Spaces (non-root UID 1000)
ENV HOME=/tmp

# Optimized for Render/Hugging Face (512MB-16GB RAM):
# --workers 1: Reduces memory footprint
# --threads 1: Minimal overhead
# --timeout 300: Extra time for heavy models
CMD gunicorn -w 1 --threads 1 --timeout 300 -k uvicorn.workers.UvicornWorker backend.main:app --bind 0.0.0.0:${PORT}