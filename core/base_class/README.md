# Registry-based DI + Config-driven Factories

Production-ready dependency injection system for connectors with type safety, async support, and config-driven initialization.

## Features

✅ **Type-safe** - Protocol-based abstractions for IDE support and type checking  
✅ **High-performance** - O(1) lookup, connection pooling, async-native  
✅ **Configurable** - Environment-driven configuration via `core.config`  
✅ **Testable** - Easy to mock with registry injection  
✅ **Scalable** - Ready for monolith → microservices migration  
✅ **Production-ready** - Health checks, graceful shutdown, error handling

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    ServiceContainer                      │
│  (High-level API for application code)                  │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│                    DIContainer                           │
│  (Multi-type registry: LLM, Queue, Storage, DB)        │
└──────────────────┬──────────────────────────────────────┘
                   │
       ┌───────────┼───────────┐
       │           │           │
┌──────▼───┐ ┌────▼────┐ ┌───▼────┐ ┌───▼────┐
│ Connector│ │Connector│ │Connector│ │Connector│
│ Registry │ │Registry │ │Registry │ │Registry │
│  (LLM)   │ │(Queue)  │ │(Storage)│ │  (DB)   │
└──────────┘ └─────────┘ └─────────┘ └─────────┘
```

## Usage

### Basic Usage

```python
from core.base_class import ServiceContainer

# Initialize on application startup
container = await ServiceContainer.from_config(auto_initialize=True)

# Use in handlers/services
llm = container.get_llm("gigachat")
response = await llm.chat("Hello, world!")

db = container.get_db("postgres")
users = await db.load("SELECT * FROM users")

# Graceful shutdown
await container.shutdown_all()
```

### Advanced Usage

```python
from core.base_class import ServiceContainer, ConnectorType

# Manual registration and initialization
container = ServiceContainer()
await container.register_all()
await container.initialize_all()

# Health checks
health = await container.health_check_all()
print(health)  # {ConnectorType.LLM: {"gigachat": True}, ...}

# Direct container access
llm_connector = container.container.get(ConnectorType.LLM, "gigachat")
```

### Testing

```python
import pytest
from core.base_class import ServiceContainer, reset_container

@pytest.fixture
async def test_container():
    # Use test config
    from core.config import Config
    test_config = Config(...)
    
    container = await ServiceContainer.from_config(
        config=test_config,
        auto_initialize=False
    )
    
    yield container
    await reset_container()
```

### Factory Functions

```python
from core.base_class.factories import (
    create_llm_connector,
    create_db_connector,
)
from core.config import get_config

config = get_config()

# Create individual connectors
llm = create_llm_connector(config)
db = create_db_connector(config)

# Initialize manually
await llm.initialize()
await db.initialize()
```

## Configuration

All connectors respect environment variables and feature flags:

```bash
# LLM (always enabled)
GIGACHAT_MODEL=GigaChat-Max
GIGACHAT_SCOPE=GIGACHAT_API_B2B

# Queue (optional)
ENABLE_KAFKA=true
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# Storage (optional)
ENABLE_MINIO=true
MINIO_ENDPOINT=localhost:9000
MINIO_BUCKET=my-bucket

# Database (optional)
ENABLE_DATABASE=true
DB_HOST=localhost
DB_PORT=5432
```

## Protocol-based Typing

Use protocols for type hints without tight coupling:

```python
from core.base_class.protocols import ILLMConnector

def process_with_llm(llm: ILLMConnector, prompt: str):
    # Type-checked, but accepts any LLM implementation
    return await llm.chat(prompt)
```

## Lifecycle Management

```python
# Initialization order
container = ServiceContainer.from_config()
await container.register_all()      # Create instances
await container.initialize_all()    # Initialize connections

# Runtime usage
llm = container.get_llm("gigachat")
# ... use connectors ...

# Shutdown
await container.shutdown_all()      # Clean shutdown
```

## Error Handling

```python
try:
    connector = container.get_llm("gigachat")
except KeyError:
    # Connector not registered
    pass

# Health checks
health = await container.health_check_all()
if not health[ConnectorType.LLM]["gigachat"]:
    # Handle unhealthy connector
    pass
```

## Migration Guide

### Before (manual instantiation)

```python
from connectors.gigachat_connector import GigaChatConnector
from core.logging import get_logger

logger = get_logger("1.0.0")
connector = GigaChatConnector(get_logger=lambda: logger, ...)
await connector.initialize()
```

### After (DI container)

```python
from core.base_class import ServiceContainer

container = await ServiceContainer.from_config()
llm = container.get_llm("gigachat")  # Already initialized
```

## Performance

- **Lookup**: O(1) dictionary access
- **Initialization**: Parallel initialization of all connectors
- **Health checks**: Concurrent health checks across all connectors
- **Memory**: Single instance per connector (singleton pattern via registry)

## Best Practices

1. **Use ServiceContainer** for application code
2. **Use factories directly** for custom initialization
3. **Use protocols** for type hints in service functions
4. **Check health** before critical operations
5. **Shutdown gracefully** on application exit

