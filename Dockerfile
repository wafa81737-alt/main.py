FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libdbus-1-3 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 \
    libasound2 libatspi2.0-0 libexpat1 libfontconfig1 libfreetype6 \
    libx11-6 libxcb1 libxext6 fonts-liberation ca-certificates wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN python -m playwright install chromium && \
    python -m playwright install chromium-headless-shell && \
    python -m playwright install-deps chromium || true

COPY . .
CMD ["python", "main.py"]
