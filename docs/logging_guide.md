# Руководство по логированию

## Конфигурация

Логирование настраивается через переменные окружения в `config/config.py`:

```bash
# Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL=INFO

# Формат логов (json или text)
LOG_FORMAT=json

# Путь к файлу логов (в Docker обычно не используется)
LOG_FILE=logs/system.log

# Включить DEBUG логи (переопределяет LOG_LEVEL, устанавливает DEBUG)
LOG_ENABLE_DEBUG=false
```

## Использование

### В коннекторах (воркерах)

Коннекторы получают logger через фабрики:

```python
# В connector_factories.py автоматически используется
logger = get_logger_from_config(config)
connector = GigaChatConnector(get_logger=lambda: logger, ...)
```

### В интерфейсах

Интерфейсы используют Observer pattern для логирования через `LoggingObserver`:

```python
# Автоматически логирует все операции
container = await ServiceContainer.from_config()
# Все операции через интерфейсы логируются автоматически
```

### Прямое использование

```python
from utils.logging import get_logger_from_config
from config.config import get_settings

config = get_settings()
logger = get_logger_from_config(config)

logger.info("Info message")
logger.debug("Debug message (only if LOG_ENABLE_DEBUG=true)")
logger.error("Error message")
```

## Уровни логирования

### INFO (по умолчанию)
- Инициализация/завершение работы
- Успешные операции
- Ошибки

### DEBUG (при LOG_ENABLE_DEBUG=true)
- Все события операций (включая OPERATION_STARTED)
- Детальная информация о запросах
- Метаданные операций
- Техническая информация (MIME types, connection details, etc.)

## Примеры

### Включить DEBUG логирование

```bash
# Через переменную окружения
export LOG_ENABLE_DEBUG=true

# Или через .env файл
LOG_ENABLE_DEBUG=true
```

### Изменить уровень логирования

```bash
LOG_LEVEL=DEBUG   # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

### Изменить формат логов (для Docker рекомендуется JSON)

```bash
LOG_FORMAT=json   # json или text
```

### Изменить файл логов

```bash
LOG_FILE=logs/my_app.log
```

## Структура логов

### JSON формат (по умолчанию в Docker)

```json
{
  "version": "1.0.0",
  "class": "ServiceContainer",
  "function": "initialize_all",
  "timestamp": "2024-01-15T10:30:45.123456",
  "logger_name": "gigachatAPI",
  "level": "INFO",
  "message": "Initialized interface: llm",
  "trace_id": "abc-123"
}
```

### Текстовый формат

```
{version} - {class} - {function} - {timestamp} - {logger_name} - {level} - {message}
```

### Примеры

**INFO уровень (JSON):**
```json
{"version": "1.0.0", "class": "ServiceContainer", "function": "initialize_all", "timestamp": "2024-01-15T10:30:45.123456", "logger_name": "gigachatAPI", "level": "INFO", "message": "Initialized interface: llm", "trace_id": "abc-123"}
```

**DEBUG уровень (дополнительно):**
```json
{"version": "1.0.0", "class": "LLMInterface", "function": "chat", "timestamp": "2024-01-15T10:30:46.123456", "logger_name": "gigachatAPI", "level": "DEBUG", "message": "[operation_started] llm::chat", "trace_id": "abc-123"}
{"version": "1.0.0", "class": "LLMInterface", "function": "chat", "timestamp": "2024-01-15T10:30:47.123456", "logger_name": "gigachatAPI", "level": "INFO", "message": "[operation_completed] llm::chat - OK (1234.56ms)", "trace_id": "abc-123", "duration_ms": 1234.56}
```

## Логирование через Observer

Observer pattern автоматически логирует:

1. **OPERATION_STARTED** - начало операции (только в DEBUG)
2. **OPERATION_COMPLETED** - успешное завершение (INFO)
3. **OPERATION_FAILED** - ошибка (ERROR)
4. **CONNECTOR_INITIALIZED** - инициализация (INFO)
5. **CONNECTOR_SHUTDOWN** - завершение работы (INFO)
6. **HEALTH_CHECK** - проверка здоровья (DEBUG)

## Файловое логирование

Логи автоматически пишутся в файл (по умолчанию `logs/system.log`):

- **Ротация**: Максимальный размер 10MB, 5 бэкапов
- **Кодировка**: UTF-8
- **Формат**: Без цветов (для файла)

## Консольное логирование

Консольные логи имеют цветовую раскраску для лучшей читаемости:

- DEBUG: голубой
- INFO: зеленый
- WARNING: желтый
- ERROR: красный
- CRITICAL: ярко-красный

## Особенности Docker

### Логирование в Docker

В Docker рекомендуется использовать JSON формат для логов:

```bash
# В .env файле
LOG_FORMAT=json
LOG_FILE=          # Пустое значение - логи в stdout
```

### Docker Compose логирование

```yaml
version: '3.8'

services:
  worker:
    image: gigachat-worker:latest
    environment:
      - LOG_FORMAT=json
      - LOG_LEVEL=INFO
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### Просмотр логов в Docker

```bash
# Просмотр логов контейнера
docker logs <container_name>

# Просмотр логов с фильтрацией
docker logs <container_name> | grep ERROR

# Прослушивание логов в реальном времени
docker logs -f <container_name>

# Просмотр логов с JSON форматированием
docker logs <container_name> | jq .
```

### Логирование в Kubernetes

Для Kubernetes логи должны быть в JSON формате для совместимости с ELK/Fluentd:

```bash
# В production
LOG_FORMAT=json
LOG_LEVEL=INFO
LOG_FILE=    # Логи в stdout/stderr для Kubernetes
```

## Логирование операций в БД

Кроме логов в stdout, все операции также логируются в PostgreSQL:

- Таблица `operation_logs`
- Содержит `task_id`, `trace_id`, `operation`, `metadata`, `timestamp`
- Используется для аудита и анализа

