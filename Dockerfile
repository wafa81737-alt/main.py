# بنستخدم الصورة الرسمية من Playwright اللي فيها كل المكتبات
FROM mcr.microsoft.com/playwright/python:v1.52.0-noble

# نحدد مكان الشغل
WORKDIR /app

# ننسخ ملف المكتبات ونسطبها
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ننسخ باقي الكود
COPY . .

# الأمر اللي بيشغل السكريبت بتاعك
CMD ["python", "main.py"]
