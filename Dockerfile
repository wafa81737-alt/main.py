FROM python:3.13-slim

# ══════════════════════════════════════════════════════════════
#  System dependencies (Playwright + Chromium + Xvfb)
# ══════════════════════════════════════════════════════════════
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libdbus-1-3 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 \
    libasound2 libatspi2.0-0 libexpat1 libfontconfig1 libfreetype6 \
    libx11-6 libxcb1 libxext6 \
    xvfb x11-utils \
    fonts-liberation fonts-noto-color-emoji \
    ca-certificates wget curl unzip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN python -m playwright install chromium && \
    python -m playwright install-deps chromium

COPY . .

ENV DISPLAY=:99

# ✅ تشغيل Xvfb + البوت في نفس الـ shell — مع انتظار نظيف
CMD ["sh", "-c", "Xvfb :99 -screen 0 540x1170x24 -ac +extension GLX +render -noreset & sleep 2 && exec python main.py"]
