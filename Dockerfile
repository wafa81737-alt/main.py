# نستخدم الصورة الرسمية من Playwright بنفس الإصدار اللي الكود بيطلبه
FROM mcr.microsoft.com/playwright/python:v1.65.1-noble

# نحدد مكان الشغل
WORKDIR /app

# ننسخ ملف المكتبات الأول عشان نستفيد من الـ cache
COPY requirements.txt .

# نسطب مكتبات بايثون
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# نتأكد إن Chromium متسطب (الصورة الرسمية المفروض فيها، بس دي خطوة تأكيد)
RUN playwright install chromium

# ننسخ باقي الكود
COPY . .

# نشغل السكريبت
CMD ["python", "main.py"]
