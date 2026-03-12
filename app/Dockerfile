# 1. Суурь орчин: Python 3.10 суулгасан жижиг хэмжээтэй Linux
FROM python:3.10-slim

# 2. Ажлын хавтас: Контейнер доторх хавтасны нэр
WORKDIR /app

# 3. Хамаарлуудыг хуулах: requirements.txt-г контейнер руу хуулна
COPY requirements.txt .

# 4. Сангуудыг суулгах: Контейнер дотор pip install ажиллуулна
RUN pip install --no-cache-dir -r requirements.txt

# 5. Кодоо хуулах: Өөрийн байгаа бүх файлыг контейнер руу хуулна
COPY . .

# 6. Порт нээх: Google Cloud Run-д зориулж 8080 портыг нээнэ
EXPOSE 8080

# 7. Ажиллуулах: Серверийг асаах команд
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]