# LLM Service - Dockerized Service

LLM Service - многопоточный сервис для обработки задач через Kafka с LLM (GigaChat), MinIO хранилищем и PostgreSQL логированием.

Сборка: docker build -t llm-service .
Команда запуска: docker run -d   --name llm-service --network document-flow-network  --env-file .env   -v $(pwd)/logs:/app/logs   llm-service

## Быстрый старт

### 1. Подготовка окружения

```bash
# Скопируй .env файл и заполни значения
cp .env.example .env

# Соберите и запустите все сервисы через Docker Compose
docker-compose up --build -d
```

### 2. Запуск только сервиса в Docker

```bash
# Сборка образа
docker build -t llm-service .

# Запуск с .env файлом
docker run -d --env-file .env llm-service
```

### 3. Запуск в development режиме

```bash
# Установка зависимостей
pip install -r requirements.txt

# Запуск напрямую
python main.py
```

Сервис автоматически:
- Инициализирует ServiceContainer
- Подключается ко всем сервисам (Kafka, MinIO, PostgreSQL, GigaChat)
- Начинает слушать входящие сообщения в Kafka топике `tasks_llm`
- Обрабатывает задачи параллельно (макс 10 одновременно)
- Отправляет результаты обратно в Kafka топик `tasks_llm`
- Использует очередь дедупликации для предотвращения обработки дубликатов задач
- Имеет автоматический перезапуск при неудачном bootstrap

## Архитектура

```
┌─────────────────────┐
│   API Gateway       │ (пишет другой спец)
│ (sends tasks)       │
└──────────┬──────────┘
           │ Kafka topic: tasks_llm
           ↓
┌──────────────────────────────────────┐
│   Docker Container: LLM Service     │
│                                      │
│  ┌──────────────────────────────┐   │
│  │  ServiceContainer (DI)       │   │
│  │  - LLMInterface (GigaChat)   │   │
│  │  - QueueInterface (Kafka)    │   │
│  │  - StorageInterface (MinIO)  │   │
│  │  - DBInterface (PostgreSQL)  │   │
│  └──────────────────────────────┘   │
│                                      │
│  ┌──────────────────────────────┐   │
│  │  LLM Service                 │   │
│  │  - Task Deduplication Queue │   │
│  │  - Retry + Circuit Breaker  │   │
│  │  - Bootstrap Retry Logic    │   │
│  │  - Graceful Shutdown        │   │
│  │  - Observability            │   │
│  └──────────────────────────────┘   │
└──────────────────────────────────────┘
           │
           ├─→ Kafka (results)
           ├─→ PostgreSQL (logs)
           ├─→ MinIO (storage)
           └─→ GigaChat API
```

## Docker контейнеризация

### Dockerfile особенности

- Использует Python 3.14 slim образ
- Устанавливает зависимости из requirements.txt
- Копирует только необходимые файлы
- Запускает сервис через python main.py
- Поддерживает graceful shutdown
- Использует non-root пользователя для безопасности

### docker-compose.yml сервисы

- `llm-service` - основной сервис обработки задач
- `kafka` - сообщения между сервисами
- `minio` - хранилище файлов
- `postgres` - логирование операций
- `zookeeper` - зависимость для Kafka

## MVP Features

### ✅ Реализовано

1. **Graceful Shutdown**
   - SIGTERM/SIGINT handlers
   - Ждет завершения активных задач (30s timeout)
   - Корректно закрывает все соединения

2. **Retry + Circuit Breaker**
   - Exponential backoff для LLM-запросов
   - Circuit breaker открывается после 5 ошибок подряд на 30s
   - Автоматическое восстановление

3. **Task Deduplication Queue**
   - Отслеживает последние 50 задач
   - Предотвращает обработку дубликатов
   - Удаляет задачи после завершения обработки

4. **Bootstrap Retry Logic**
   - 5 попыток при неудачном bootstrap
   - 5 секунд задержка между попытками
   - Критическая ошибка после всех попыток

5. **Явный Kafka Commit**
   - Commit ТОЛЬКО после успешной обработки
   - При ошибке сообщение переобрабатывается
   - Гарантирует "at-least-once" обработку

6. **Observability**
   - Структурированное логирование с trace_id
   - EventPublisher для метрик и логирования
   - Операции логируются в PostgreSQL

7. **Docker Ready**
   - Готов к запуску в контейнерах
   - Поддерживает environment variables
   - Совместим с orchestration системами

## Конфигурация

### Environment Variables

Все параметры читаются из `.env` файла через `Settings` (Pydantic).

**Ключевые переменные:**

```
# GigaChat
GIGACHAT_ACCESS_TOKEN=...
GIGACHAT_MODEL=GigaChat-Max
GIGACHAT_SCOPE=GIGACHAT_API_B2B

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_GROUP_ID=llm-worker-group

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_BUCKET_NAME=documents

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_DATABASE=llm_worker

# Worker
WORKER_MAX_CONCURRENT_TASKS=10
LLM_MAX_RETRIES=3
```

Полный список в `.env.example`.

## Структура задачи (Kafka message)

### Входящее сообщение (topic: `tasks_llm`)

```json
{
  "task_id": "uuid-or-task-id",
  "storage_path": "documents/file.pdf",
  "prompt_id": 3,
  "trace_id": "trace-uuid",
  "created_at": "2025-12-23T21:45:00Z",
  "status": "1"
}
```

### Исходящее сообщение (topic: `tasks_llm`)

**При успехе (status=3):**

```json
{
  "task_id": "uuid-or-task-id",
  "result": { "extracted_data": "..." },
  "tokens_used": 1250,
  "processing_time_ms": 3450.5
}
```

**При ошибке (status=4):**

```json
{
  "task_id": "uuid-or-task-id",
  "error": "Circuit breaker OPEN - LLM service unavailable",
  "tokens_used": 0,
  "processing_time_ms": 125.0
}
```

## Логирование

### В PostgreSQL (operation_logs таблица)

Каждая операция логируется с метаданными:

```
task_id | trace_id | operation | metadata | timestamp
--------|----------|-----------|----------|----------
123     | trace-1  | task_received | {storage_path: ...} | 2025-12-23 21:45:00
123     | trace-1  | file_loaded | {filename: file.pdf, size_bytes: 2048} | ...
123     | trace-1  | llm_processing_success | {tokens_used: 1250, ...} | ...
```

### В консоль (структурированные логи)

```
[2025-12-23 21:45:00] [INFO] [trace-1] Processing task: 123
[2025-12-23 21:45:05] [INFO] [trace-1] Task 123 completed: 1250 tokens
```

## Обработка ошибок

### Случаи, при которых НЕ коммитится сообщение

1. Ошибка при загрузке файла из MinIO
2. Ошибка при отправке в LLM (даже после retries)
3. Ошибка при отправке результата в Kafka

→ Сообщение остается в очереди и будет переобработано

### Circuit Breaker механизм

```
CLOSED ──(5 errors)──→ OPEN ──(30s timeout)──→ HALF_OPEN ──(success)──→ CLOSED
                                   ↑
                                   └─(error)──┘
```

## Docker Deployment

### Пример docker-compose.override.yml для production

```yaml
version: '3.8'

services:
  llm-service:
    image: llm-service:latest
    environment:
      - GIGACHAT_ACCESS_TOKEN=${GIGACHAT_ACCESS_TOKEN}
      - KAFKA_BOOTSTRAP_SERVERS=kafka:9092
      - POSTGRES_HOST=postgres:5432
      - MINIO_ENDPOINT=minio:9000
    deploy:
      replicas: 3
      resources:
        limits:
          memory: 1G
          cpus: '0.5'
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
    depends_on:
      - kafka
      - postgres
      - minio
```

## Troubleshooting

### Сервис не запускается

```bash
# Проверь логи
docker logs <llm-service-container>

# Проверь переменные окружения
docker exec <llm-service-container> env | grep -E "(KAFKA|MINIO|GIGACHAT|POSTGRES)"
```

### Сервис не подключается к Kafka

```bash
# Проверь связь с Kafka из контейнера
docker exec <llm-service-container> ping kafka

# Проверь переменные окружения в контейнере
docker exec <llm-service-container> env | grep KAFKA
```

### GigaChat ошибки аутентификации

```bash
# Проверь что API ключи установлены
docker exec <llm-service-container> env | grep GIGACHAT

# Проверь логи сервиса для деталей ошибки
docker logs <llm-service-container>
```

### PostgreSQL connection failed

```bash
# Проверь что БД поднялась
docker ps | grep postgres

# Проверь доступность из сервис контейнера
docker exec <llm-service-container> ping postgres
```

## Production Readiness

### Критичные доделки перед production

- [ ] HTTP endpoints (`/health`, `/ready`) для K8s probes
- [ ] Настроить логирование в ELK/Loki
- [ ] Добавить metrics в Prometheus
- [ ] Использовать secrets management (Vault/K8s Secrets)
- [ ] Настроить сертификаты для HTTPS
- [ ] Добавить rate limiting

### Опциональные улучшения

- [ ] Distributed tracing (OpenTelemetry + Jaeger)
- [ ] Advanced monitoring dashboard (Grafana)
- [ ] Batch logging в БД
- [ ] Multi-worker coordination (если нужны зависимости между воркерами)
- [ ] Auto-scaling based on queue size

## Контакты / Поддержка

При возникновении проблем:
1. Проверь логи сервиса: `docker logs <container_name>`
2. Убедись, что все сервисы (Kafka, MinIO, PostgreSQL) поднялись: `docker ps`
3. Проверь конфигурацию в `.env`
4. Включи DEBUG логирование: `LOG_LEVEL=DEBUG`
5. Обратись к документации по поддержке: `docs/support_guide.md`