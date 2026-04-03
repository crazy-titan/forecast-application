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

# Expands PORT from environment, defaults to 8000
ENV PORT=8000
EXPOSE 8000

# Optimized for Render (512MB-1GB RAM):
# --workers 1: Reduces memory footprint (statsforecast is memory-heavy)
# --threads 1: Minimal overhead for very low-power CPUs
# --timeout 300: Gives extra time for heavy initial imports/setup
# (No --preload): Allows the master process to bind port before heavy app loading
CMD gunicorn -w 1 --threads 1 --timeout 300 -k uvicorn.workers.UvicornWorker backend.main:app --bind 0.0.0.0:${PORT}