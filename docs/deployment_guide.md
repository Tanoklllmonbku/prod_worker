# LLM Service - Документация по развертыванию и поддержке

## Содержание
1. [Обзор сервиса](#обзор-сервиса)
2. [Архитектура](#архитектура)
3. [Требования к инфраструктуре](#требования-к-инфраструктуре)
4. [Конфигурация](#конфигурация)
5. [Развертывание](#развертывание)
6. [Мониторинг и логирование](#мониторинг-и-логирование)
7. [Устранение неполадок](#устранение-неполадок)
8. [Обновление сервиса](#обновление-сервиса)

## Обзор сервиса

LLM Service - это многопоточный сервис для обработки задач с использованием LLM (GigaChat), который:
- Принимает задачи из Kafka
- Обрабатывает файлы с помощью LLM
- Отправляет статусы и результаты обратно в Kafka
- Поддерживает до N воркеров для распределения нагрузки
- Имеет защиту от дубликатов задач

## Архитектура

### Компоненты
- **Kafka Consumer**: непрерывно читает сообщения из топика `tasks_llm`
- **Task Deduplication Queue**: отслеживает последние 50 задач для предотвращения дубликатов
- **Worker Pool**: до N воркеров для обработки задач (настраивается через `WORKER_MAX_CONCURRENT_TASKS`)
- **GigaChat Connector**: обрабатывает файлы с помощью LLM
- **MinIO Connector**: загрузка/выгрузка файлов
- **Service Container**: управление зависимостями и жизненным циклом

### Поток данных
1. Kafka Consumer получает сообщения со статусом 1 (PENDING)
2. Проверяется дубликат задачи в очереди дедупликации
3. Отправляется статус 2 (PROCESSING) в Kafka
4. Файл загружается из MinIO
5. Файл загружается в GigaChat
6. Выполняется обработка LLM
7. Отправляется статус 3 (SUCCESS) или 4 (FAILED) в Kafka
8. Задача удаляется из очереди дедупликации

## Требования к инфраструктуре

### Минимальные требования
- **CPU**: 2 ядра
- **RAM**: 4GB
- **Дисковое пространство**: 1GB свободного места

### Внешние зависимости
- **Kafka**: для обмена сообщениями
- **MinIO**: для хранения файлов
- **GigaChat API**: для обработки LLM
- **PostgreSQL**: для логирования (опционально)

### Сетевые требования
- Доступ к Kafka брокеру
- Доступ к MinIO серверу
- Доступ к GigaChat API
- Доступ к PostgreSQL (если используется)

## Конфигурация

### Основные переменные окружения

```bash
# GigaChat Configuration
GIGACHAT_ACCESS_TOKEN=your_token_here
GIGACHAT_MODEL=GigaChat-Max
GIGACHAT_SCOPE=GIGACHAT_API_B2B
GIGACHAT_VERIFY_SSL=False
GIGACHAT_REQUEST_TIMEOUT_SECONDS=30
GIGACHAT_MAX_CONNECTIONS=10
BASE_URL=https://gigachat.devices.sberbank.ru
API_VERSION=api/v1
OAUTH_URL=https://ngw.devices.sberbank.ru:9443/api/v2/oauth

# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_GROUP_ID=llm-worker-group
KAFKA_AUTO_OFFSET_RESET=earliest
KAFKA_CONSUMER_POLL_TIMEOUT=1.0

# MinIO Configuration
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_NAME=documents
MINIO_USE_SSL=False
MINIO_ENABLED=True

# PostgreSQL Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5444
POSTGRES_DATABASE=llm_worker
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_POOL_MIN_SIZE=1
POSTGRES_POOL_MAX_SIZE=20
POSTGRES_ENABLED=True

# Worker Configuration
WORKER_MAX_CONCURRENT_TASKS=10  # Количество воркеров
EXECUTOR_MAX_WORKERS=5

# Circuit breaker settings
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_TIMEOUT_SEC=30

# Retry settings
LLM_MAX_RETRIES=3
LLM_RETRY_INITIAL_DELAY=2.0
LLM_RETRY_MAX_DELAY=10.0
```

## Развертывание

### 1. Подготовка инфраструктуры

Убедитесь, что все зависимости запущены:
```bash
# Проверка Kafka
docker exec kafka_container kafka-topics --bootstrap-server localhost:9092 --list

# Проверка MinIO
curl -I http://localhost:9000/minio/health/live

# Проверка PostgreSQL
pg_isready -h localhost -p 5444 -U postgres
```

### 2. Создание топика Kafka

```bash
kafka-topics --create --topic tasks_llm --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1
```

### 3. Настройка .env файла

Создайте файл `.env` с необходимыми переменными окружения.

### 4. Запуск через Docker

Сборка образа:
```bash
docker build -t llm-service .
```

Запуск контейнера:
```bash
docker run -d \
  --env-file .env \
  --name llm-service \
  -v /path/to/logs:/app/logs \
  llm-service
```

### 5. Запуск вручную (для разработки)

```bash
# Установка зависимостей
pip install -r requirements.txt

# Запуск сервиса
python -m asyncio main.py
```

## Мониторинг и логирование

### Уровни логирования
- **INFO**: Нормальные операции, старт/стоп сервиса
- **DEBUG**: Подробная информация о процессе обработки
- **WARNING**: Потенциальные проблемы
- **ERROR**: Ошибки обработки
- **CRITICAL**: Критические ошибки, требующие вмешательства

### Местоположение логов
- `/app/logs/system.log` - основные логи
- `/app/logs/errors.log` - ошибки (если настроено)

### Метрики
Сервис автоматически собирает метрики через Observer паттерн:
- Время обработки задач
- Количество успешных/неудачных обработок
- Статусы подключений к внешним сервисам

## Устранение неполадок

### Частые проблемы

#### 1. Bootstrap неудачный
**Симптомы**: 
```
Bootstrap failed after 5 attempts
```

**Решение**:
- Проверьте доступность Kafka
- Проверьте доступность MinIO
- Проверьте корректность токена GigaChat
- Проверьте настройки подключения к PostgreSQL

#### 2. Сервис не читает сообщения из Kafka
**Симптомы**: 
- Нет логов получения задач
- Consumer не подписан на топик

**Решение**:
- Проверьте, что топик `tasks_llm` существует
- Проверьте права доступа к Kafka
- Проверьте настройки `KAFKA_GROUP_ID`

#### 3. Ошибки при обработке файлов
**Симптомы**:
- Статус 4 (FAILED) отправляется слишком часто
- Ошибки загрузки файлов

**Решение**:
- Проверьте доступность MinIO
- Проверьте существование файлов в MinIO
- Проверьте права доступа к файлам

#### 4. Превышение лимита памяти
**Симптомы**:
- OOM ошибки
- Сервис останавливается

**Решение**:
- Уменьшите `WORKER_MAX_CONCURRENT_TASKS`
- Увеличьте лимит памяти контейнера
- Проверьте размеры обрабатываемых файлов

### Диагностика

#### Проверка состояния сервиса
```bash
# Логи контейнера
docker logs llm-service

# Статус контейнера
docker ps | grep llm-service

# Ресурсы контейнера
docker stats llm-service
```

#### Проверка Kafka
```bash
# Список топиков
kafka-topics --bootstrap-server localhost:9092 --list

# Статус потребителей
kafka-consumer-groups --bootstrap-server localhost:9092 --describe --group llm-worker-group
```

#### Проверка MinIO
```bash
# Список бакетов
mc ls local

# Список файлов в бакете
mc ls local/documents
```

## Обновление сервиса

### 1. Подготовка к обновлению

Создайте резервную копию:
```bash
# Логи
docker logs llm-service > backup_logs_$(date +%Y%m%d).log

# Конфигурация
cp .env .env.backup
```

### 2. Обновление через Docker

```bash
# Остановка старого контейнера
docker stop llm-service
docker rm llm-service

# Сборка нового образа
docker build -t llm-service .

# Запуск нового контейнера
docker run -d \
  --env-file .env \
  --name llm-service \
  -v /path/to/logs:/app/logs \
  llm-service
```

### 3. Проверка обновления

```bash
# Проверка статуса
docker ps | grep llm-service

# Проверка логов
docker logs llm-service | tail -20

# Проверка обработки задач
# Отправьте тестовое сообщение в Kafka и проверьте результат
```

## Резервное копирование

### Что резервировать
- Файл конфигурации `.env`
- Логи сервиса
- Базу данных PostgreSQL (если используется для логирования)

### План восстановления
1. Восстановите конфигурацию
2. Запустите зависимости (Kafka, MinIO, PostgreSQL)
3. Запустите LLM Service
4. Проверьте обработку задач