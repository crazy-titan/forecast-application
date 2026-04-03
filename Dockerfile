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

# Shell form ensures $PORT expansion
CMD gunicorn -w 4 -k uvicorn.workers.UvicornWorker backend.main:app --bind 0.0.0.0:${PORT}