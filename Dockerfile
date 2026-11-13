FROM mcr.microsoft.com/playwright/python:v1.65.1-noble

WORKDIR /app

# مكتبات النظام المطلوبة لـ xvfb والمتصفح
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        xvfb \
        x11-utils \
        x11-xserver-utils \
        fonts-liberation \
        fonts-noto-color-emoji \
        libatomic1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

RUN playwright install chromium

COPY . .

# نشغل تحت xvfb عشان المتصفح يشتغل headed على سيرفر بدون شاشة
CMD ["xvfb-run", "-a", "--server-args=-screen 0 1280x1024x24", "python", "main.py"]
