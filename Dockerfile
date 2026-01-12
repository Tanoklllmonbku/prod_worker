# ============================================
# Стадия сборки (создание бинарника)
# ============================================
FROM python:3.14-slim AS builder

# Устанавливаем зависимости для сборки
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем PyInstaller для создания бинарника
RUN pip install pyinstaller

# Устанавливаем зависимости проекта
WORKDIR /build
COPY requirements.txt .
RUN pip install -r requirements.txt

# Копируем исходный код
COPY . .

# Создаём бинарник с помощью PyInstaller
RUN pyinstaller --onefile --name llm-service main.py

# ============================================
# Базовый образ runtime
# ============================================
FROM python:3.14-slim AS base

# Устанавливаем runtime зависимости
RUN apt-get update && apt-get install -y \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Создаём пользователя без прав root
RUN useradd -m -u 1000 appuser

# Копируем бинарник из builder
COPY --from=builder /build/dist/llm-service .

# Устанавливаем права на бинарник
RUN chmod +x llm-service

# Переключаемся на пользователя appuser
USER appuser

# ============================================
# Prod образ
# ============================================
FROM base AS prod

# Устанавливаем переменные окружения
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expose port
EXPOSE 8000

CMD ["./llm-service"]

# ============================================
# Финальный образ (по умолчанию prod)
# ============================================
FROM prod
