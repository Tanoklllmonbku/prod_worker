# Руководство по логированию

## Конфигурация

Логирование настраивается через переменные окружения в `core/config.py`:

```bash
# Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL=INFO

# Путь к файлу логов
LOG_FILE=logs/system.log

# Включить DEBUG логи (переопределяет LOG_LEVEL, устанавливает DEBUG)
LOG_ENABLE_DEBUG=false
```

## Использование

### В коннекторах (воркерах)

Коннекторы получают logger через фабрики:

```python
# В factories.py автоматически используется
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
from core.logging import get_logger_from_config
from core.config import get_config

config = get_config()
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

### Изменить файл логов

```bash
LOG_FILE=logs/my_app.log
```

## Структура логов

### Формат

```
{version} - {class} - {function} - {timestamp} - {logger_name} - {level} - {message}
```

### Примеры

**INFO уровень:**
```
1.0.0 - ServiceContainer - initialize_all - 2024-01-15 10:30:45 - gigachatAPI - INFO - Initialized interface: llm
```

**DEBUG уровень (дополнительно):**
```
1.0.0 - LLMInterface - chat - 2024-01-15 10:30:46 - gigachatAPI - DEBUG - [operation_started] llm::chat
1.0.0 - LLMInterface - chat - 2024-01-15 10:30:47 - gigachatAPI - INFO - [operation_completed] llm::chat - OK (1234.56ms)
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

