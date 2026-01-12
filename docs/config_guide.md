# Руководство по конфигурации

## Обзор

Система конфигурации поддерживает:
- ✅ **JSON файлы** - основной способ конфигурации
- ✅ **Переменные окружения** - переопределяют JSON
- ✅ **Keyring** - безопасное хранение токенов/паролей
- ✅ **Типизированные конфиги** - dataclass конфиги для каждого типа коннектора
- ✅ **Обратная совместимость** - legacy параметры продолжают работать
- ✅ **Docker env vars** - поддержка переменных окружения в контейнерах

## Структура

### 1. JSON файл конфигурации

Основной файл: `config/config.json`

```json
{
  "logging": { ... },
  "api": { ... },
  "features": { ... },
  "connectors": {
    "llm": { ... },
    "db": { ... },
    "queue": { ... },
    "storage": { ... }
  }
}
```

### 2. Классы конфигурации

Все конфиги определены в `config/config.py`:

- `Settings` - основной класс конфигурации с Pydantic
- Поддерживает валидацию и типизацию
- Автоматически читает из .env файла

### 3. Загрузка конфигурации

```python
from config.config import get_settings

# Загрузка полного конфига
config = get_settings()

# Доступ к различным частям конфига
llm_config = config.gigachat
db_config = config.postgres
queue_config = config.kafka
storage_config = config.minio
```

## Общие параметры

Все коннекторы поддерживают общие параметры из `Settings`:

```json
{
  "timeout": 30.0,
  "connection_timeout": 10.0,
  "retry_count": 3,
  "retry_delay": 1.0,
  "health_check_interval": 60.0
}
```

## Конфигурация по типам коннекторов

### LLM Connector

```json
{
  "gigachat_access_token": "...",
  "gigachat_model": "GigaChat-Max",
  "gigachat_scope": "GIGACHAT_API_B2B",
  "gigachat_verify_ssl": false,
  "gigachat_request_timeout_seconds": 30,
  "gigachat_max_connections": 100
}
```

**Важно:** `gigachat_access_token` должен быть в переменной окружения или keyring:

```bash
# В .env файле
GIGACHAT_ACCESS_TOKEN=your_token_here
```

### DB Connector

```json
{
  "postgres_host": "localhost",
  "postgres_port": 5432,
  "postgres_database": "gigachat_db",
  "postgres_user": "postgres",
  "postgres_password": "password",
  "postgres_pool_min_size": 1,
  "postgres_pool_max_size": 20
}
```

**Для Docker:** используйте имя сервиса контейнера:

```bash
# В Docker Compose
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
```

### Queue Connector

```json
{
  "kafka_bootstrap_servers": "localhost:9092",
  "kafka_group_id": "llm-worker-group",
  "kafka_auto_offset_reset": "earliest",
  "kafka_consumer_poll_timeout": 1.0
}
```

**Для Docker:** используйте имя сервиса контейнера:

```bash
# В Docker Compose
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
```

### Storage Connector

```json
{
  "minio_endpoint": "localhost:9000",
  "minio_access_key": "minioadmin",
  "minio_secret_key": "minioadmin",
  "minio_bucket_name": "gigachat-files",
  "minio_use_ssl": false
}
```

**Для Docker:** используйте имя сервиса контейнера:

```bash
# В Docker Compose
MINIO_ENDPOINT=minio:9000
```

## Использование в Docker

### 1. .env файл

Создайте `.env` файл с конфигурацией:

```bash
# GigaChat
GIGACHAT_ACCESS_TOKEN=your_token_here
GIGACHAT_MODEL=GigaChat-Max

# Kafka (имена сервисов Docker)
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
KAFKA_GROUP_ID=llm-worker-group

# PostgreSQL (имя сервиса Docker)
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DATABASE=worker_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

# MinIO (имя сервиса Docker)
MINIO_ENDPOINT=minio:9000
MINIO_BUCKET_NAME=documents
```

### 2. Docker Compose override

Для production можно использовать `docker-compose.override.yml`:

```yaml
version: '3.8'

services:
  worker:
    environment:
      - GIGACHAT_ACCESS_TOKEN=${GIGACHAT_ACCESS_TOKEN}
      - KAFKA_BOOTSTRAP_SERVERS=kafka:9092
      - POSTGRES_HOST=postgres:5432
      - MINIO_ENDPOINT=minio:9000
    env_file:
      - .env
```

## Использование в фабриках

Фабрики автоматически используют конфиги из `get_settings()`:

```python
from config.config import get_settings

config = get_settings()

# Автоматически использует переменные окружения
llm_connector = create_llm_connector(config)

# Или через ServiceContainer
container = await ServiceContainer.from_config(config=config)
llm = container.get_llm()
```

## Переопределение через переменные окружения

Все параметры можно переопределить через env vars:

```bash
# Логирование
export LOG_LEVEL=DEBUG
export LOG_ENABLE_DEBUG=true

# База данных (в Docker используйте имя сервиса)
export POSTGRES_HOST=postgres
export POSTGRES_PORT=5432
export POSTGRES_PASSWORD=secret_password

# Kafka (в Docker используйте имя сервиса)
export KAFKA_BOOTSTRAP_SERVERS=kafka:9092

# MinIO (в Docker используйте имя сервиса)
export MINIO_ENDPOINT=minio:9000
```

## Безопасность

### ✅ DO (Делать)

- Хранить токены в переменных окружения
- Использовать .env файлы (не коммитить их!)
- Использовать разные .env файлы для dev/prod
- В Docker использовать secrets для production

### ❌ DON'T (Не делать)

- Хранить пароли/токены в JSON файлах
- Коммитить .env файлы в git
- Использовать одинаковые пароли в dev/prod

## Примеры

### Загрузка конфига в Docker

```python
from config.config import get_settings

# Автоматически читает из .env и переменных окружения
config = get_settings()

# В Docker контейнере:
# - Kafka будет доступна как 'kafka:9092'
# - PostgreSQL как 'postgres:5432'
# - MinIO как 'minio:9000'
```

### Проверка конфига

```python
from config.config import print_settings

# Вывести текущие настройки (полезно для дебага в Docker)
print_settings()
```

## Приоритет конфигурации

1. **Переменные окружения** (высший приоритет)
2. **.env файл** (если указан)
3. **Значения по умолчанию** (lowest priority)

## Docker специфичные особенности

### Сетевые адреса

В Docker Compose сервисы доступны по именам:

- `kafka:9092` вместо `localhost:9092`
- `postgres:5432` вместо `localhost:5432`
- `minio:9000` вместо `localhost:9000`

### Health checks

Конфигурация поддерживает health checks для Docker:

```bash
# Проверить готовность сервиса
curl http://worker:8000/health  # когда будет добавлен endpoint
```

## Миграция с legacy конфигов

Старые способы конфигурации продолжают работать:

```python
# Старый способ (все еще работает)
config = get_settings()
llm = create_llm_connector(config)  # Использует config.gigachat_model, etc.

# Новый способ (рекомендуется для Docker)
# Просто убедитесь, что переменные окружения установлены
config = get_settings()
llm = create_llm_connector(config)  # Автоматически использует env vars
```

