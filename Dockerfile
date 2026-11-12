FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

# ══════════════════════════════════════════════════════════════
#  Xvfb + Fonts
# ══════════════════════════════════════════════════════════════
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb x11-utils \
    fonts-liberation fonts-noto-color-emoji \
    ca-certificates wget curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ══════════════════════════════════════════════════════════════
#  Python dependencies
# ══════════════════════════════════════════════════════════════
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ══════════════════════════════════════════════════════════════
#  Playwright Chromium
# ══════════════════════════════════════════════════════════════
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN python -m playwright install chromium

# ══════════════════════════════════════════════════════════════
#  Copy app
# ══════════════════════════════════════════════════════════════
COPY . .
RUN chmod +x start.sh

# ══════════════════════════════════════════════════════════════
#  Run
# ══════════════════════════════════════════════════════════════
ENV DISPLAY=:99
ENV HEADLESS=false

CMD ["./start.sh"]
