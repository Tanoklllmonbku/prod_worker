# Руководство по конфигурации

## Обзор

Система конфигурации поддерживает:
- ✅ **JSON файлы** - основной способ конфигурации
- ✅ **Переменные окружения** - переопределяют JSON
- ✅ **Keyring** - безопасное хранение токенов/паролей
- ✅ **Типизированные конфиги** - dataclass конфиги для каждого типа коннектора
- ✅ **Обратная совместимость** - legacy параметры продолжают работать

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

Все конфиги определены в `core/connector_configs.py`:

- `CommonConnectorConfig` - общие параметры для всех коннекторов
- `LLMConnectorConfig` - конфиг для LLM коннекторов
- `DBConnectorConfig` - конфиг для БД коннекторов
- `QueueConnectorConfig` - конфиг для очередей
- `StorageConnectorConfig` - конфиг для хранилищ
- `ConnectorsConfig` - контейнер для всех конфигов

### 3. Загрузка конфигурации

```python
from core.config import get_config
from core.connector_configs import load_connectors_config

# Загрузка полного конфига
config = get_config()

# Доступ к конфигам коннекторов
if config.connectors_config:
    llm_config = config.connectors_config.llm
    db_config = config.connectors_config.db
```

## Общие параметры

Все коннекторы поддерживают общие параметры из `CommonConnectorConfig`:

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
  "llm": {
    "model": "GigaChat-Max",
    "scope": "GIGACHAT_API_B2B",
    "verify_ssl": false,
    "timeout": 30.0,
    "max_connections": 100,
    "retry_count": 3,
    "retry_delay": 1.0
  }
}
```

**Важно:** `auth_key` должен быть в keyring:

```bash
keyring set_password myapp gigachat_token YOUR_TOKEN
```

### DB Connector

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

### Queue Connector

```json
{
  "queue": {
    "bootstrap_servers": ["localhost:9092", "localhost:9093"],
    "default_format": "json",
    "consumer_poll_timeout": 1.0,
    "auto_offset_reset": "earliest",
    "timeout": 30.0
  }
}
```

### Storage Connector

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

## Использование в фабриках

Фабрики автоматически используют конфиги из `config.connectors_config`:

```python
# Автоматически использует config.connectors_config.llm
llm_connector = create_llm_connector(config)

# Или можно передать конфиг явно
from core.connector_configs import LLMConnectorConfig

custom_config = LLMConnectorConfig(
    model="GigaChat-Pro",
    timeout=60.0,
)
llm_connector = create_llm_connector(config, connector_config=custom_config)
```

## Переопределение через переменные окружения

Все параметры можно переопределить через env vars:

```bash
# Логирование
export LOG_LEVEL=DEBUG
export LOG_ENABLE_DEBUG=true

# База данных
export DB_HOST=production-db.example.com
export DB_PORT=5432
export DB_PASSWORD=secret_password

# И т.д.
```

## Безопасность

### ✅ DO (Делать)

- Хранить токены в keyring
- Использовать переменные окружения для паролей
- Коммитить только `.example` файлы
- Использовать разные конфиги для dev/prod

### ❌ DON'T (Не делать)

- Хранить пароли/токены в JSON файлах
- Коммитить `config.json` с секретами в git
- Использовать одинаковые пароли в dev/prod

## Примеры

### Создание конфига программно

```python
from core.connector_configs import (
    ConnectorsConfig,
    LLMConnectorConfig,
    DBConnectorConfig,
)

# Создание конфига
connectors_config = ConnectorsConfig(
    llm=LLMConnectorConfig(
        model="GigaChat-Max",
        timeout=30.0,
    ),
    db=DBConnectorConfig(
        host="localhost",
        port=5432,
        database="mydb",
    ),
)

# Использование
config.connectors_config = connectors_config
llm = create_llm_connector(config)
```

### Загрузка из JSON

```python
from core.connector_configs import ConnectorsConfig

# Загрузка из файла
config = ConnectorsConfig.from_json_file("config/connectors.json")

# Или через Config
from core.config import get_config
config = get_config()  # Автоматически загружает из config/config.json
```

## Приоритет конфигурации

1. **Переменные окружения** (высший приоритет)
2. **JSON файл** (`config/config.json`)
3. **Значения по умолчанию** (lowest priority)

## Миграция с legacy конфигов

Старые способы конфигурации продолжают работать:

```python
# Старый способ (все еще работает)
config = get_config()
llm = create_llm_connector(config)  # Использует config.gigachat_model, etc.

# Новый способ (рекомендуется)
# Просто создайте config/config.json с нужными параметрами
config = get_config()
llm = create_llm_connector(config)  # Автоматически использует config.connectors_config.llm
```

