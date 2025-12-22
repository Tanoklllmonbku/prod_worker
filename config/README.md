# Конфигурация

Конфигурация поддерживает два формата:
1. **JSON файл** (`config/config.json`) - основной способ
2. **Переменные окружения** - переопределяют значения из JSON
3. **Keyring** - для чувствительных данных (токены, пароли)

## Структура конфигурации

### Основной файл: `config/config.json`

```json
{
  "logging": {
    "level": "INFO",
    "file": "logs/system.log",
    "enable_debug": false
  },
  "api": {
    "host": "0.0.0.0",
    "port": 8000,
    "workers": 4,
    "timeout": 30
  },
  "features": {
    "enable_minio": true,
    "enable_database": true,
    "enable_kafka": true
  },
  "connectors": {
    "llm": { ... },
    "db": { ... },
    "queue": { ... },
    "storage": { ... }
  }
}
```

### Конфигурация коннекторов

Все параметры коннекторов находятся в секции `connectors`. Каждый тип коннектора имеет свои параметры и общие параметры.

#### Общие параметры (для всех коннекторов)

```json
{
  "timeout": 30.0,
  "connection_timeout": 10.0,
  "retry_count": 3,
  "retry_delay": 1.0,
  "health_check_interval": 60.0
}
```

#### LLM Connector (GigaChat)

```json
{
  "llm": {
    "model": "GigaChat-Max",
    "scope": "GIGACHAT_API_B2B",
    "verify_ssl": false,
    "timeout": 30.0,
    "max_connections": 100,
    "retry_count": 3
  }
}
```

**Важно:** `auth_key` должен храниться в keyring, не в JSON файле!

```bash
keyring set_password myapp gigachat_token YOUR_TOKEN_HERE
```

#### DB Connector (PostgreSQL)

```json
{
  "db": {
    "host": "localhost",
    "port": 5432,
    "database": "gigachat_db",
    "user": "postgres",
    "password": "password",
    "min_pool_size": 1,
    "max_pool_size": 20,
    "timeout": 30.0
  }
}
```

#### Queue Connector (Kafka)

```json
{
  "queue": {
    "bootstrap_servers": ["localhost:9092"],
    "default_format": "json",
    "consumer_poll_timeout": 1.0,
    "auto_offset_reset": "earliest",
    "timeout": 30.0
  }
}
```

#### Storage Connector (MinIO)

```json
{
  "storage": {
    "endpoint": "localhost:9000",
    "access_key": "minioadmin",
    "secret_key": "minioadmin",
    "bucket": "gigachat-files",
    "use_ssl": false,
    "timeout": 30.0
  }
}
```

## Быстрый старт

1. Скопируйте пример конфига:

```bash
cp config/config.json.example config/config.json
```

2. Отредактируйте `config/config.json` под ваши нужды

3. Установите чувствительные данные в keyring:

```bash
keyring set_password myapp gigachat_token YOUR_GIGACHAT_TOKEN
```

4. Или используйте переменные окружения для переопределения:

```bash
export LOG_LEVEL=DEBUG
export DB_HOST=production-db.example.com
export CONFIG_FILE=config/production.json
```

## Примеры использования

### Программное использование

```python
from core.config import get_config
from core.connector_configs import ConnectorsConfig

# Загрузка из файла по умолчанию (config/config.json)
config = get_config()

# Загрузка из другого файла
config = get_config(config_file="config/production.json")

# Доступ к конфигам коннекторов
if config.connectors_config:
    llm_config = config.connectors_config.llm
    db_config = config.connectors_config.db
```

### Переопределение через переменные окружения

Все параметры можно переопределить через переменные окружения:

```bash
# Логирование
export LOG_LEVEL=DEBUG
export LOG_ENABLE_DEBUG=true

# API
export API_HOST=0.0.0.0
export API_PORT=8000

# База данных
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=mydb

# И т.д.
```

## Безопасность

**ВАЖНО:** Никогда не храните чувствительные данные (пароли, токены) в JSON файлах!

Используйте:
- **Keyring** для токенов:
  ```bash
  keyring set_password myapp gigachat_token YOUR_TOKEN
  ```

- **Переменные окружения** для паролей:
  ```bash
  export DB_PASSWORD=secret_password
  ```

- **Файлы .env** (не коммитьте в git!):
  ```
  DB_PASSWORD=secret_password
  GIGACHAT_TOKEN=secret_token
  ```

## Приоритет конфигурации

1. **Переменные окружения** (высший приоритет)
2. **JSON файл** (`config/config.json`)
3. **Значения по умолчанию** (lowest priority)

