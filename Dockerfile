FROM python:3.11-slim as builder

LABEL maintainer="LeonAchata"
LABEL description="Pipeline de procesamiento de facturas con IA"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    libfreetype6-dev \
    libjpeg-dev \
    libpng-dev \
    libopenjp2-7-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

RUN apt-get update && apt-get install -y --no-install-recommends \
    libfreetype6 \
    libjpeg62-turbo \
    libpng16-16 \
    libopenjp2-7 \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 appuser && \
    mkdir -p /app /app/temp && \
    chown -R appuser:appuser /app


USER appuser

WORKDIR /app

COPY --from=builder --chown=appuser:appuser /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder --chown=appuser:appuser /usr/local/bin /usr/local/bin

COPY --chown=appuser:appuser . .


RUN mkdir -p temp && chmod 755 temp

EXPOSE ${PORT}

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
