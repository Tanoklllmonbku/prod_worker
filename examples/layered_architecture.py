"""
Example: Using multi-layered architecture

Demonstrates:
1. Core - Base classes ✅
2. Workers - Connectors ✅
3. Interfaces - Strategy pattern for switching workers ✅
4. Container - Manages interfaces with observer pattern ✅
5. Factories - Create everything from config ✅
"""
import asyncio
from core.base_class import ServiceContainer


async def main():
    """Example: Using the complete layered architecture"""

    print("=" * 60)
    print("Multi-layered Architecture Example")
    print("=" * 60)

    # 5. Factory creates container from config
    print("\n[5] Creating container from config (Factory)...")
    container = await ServiceContainer.from_config(
        auto_initialize=True,
        enable_logging=True,
        enable_metrics=True,
        enable_tracing=True,
    )

    # 4. Container manages interfaces
    print("\n[4] Container managing interfaces...")
    print(f"Available interfaces: {list(container._interfaces.keys())}")

    # 3. Interfaces provide Strategy pattern
    print("\n[3] Using interfaces (Strategy pattern)...")

    # LLM Interface
    llm_interface = container.get_llm("llm")
    print(f"LLM Interface: {llm_interface.name}")
    print(f"  Worker: {llm_interface.worker.name}")

    # Example: Switching worker (Strategy pattern)
    # This demonstrates how interfaces allow switching between workers
    # without changing business logic
    print("\n  Example: Strategy pattern - switching workers")
    print(f"  Current worker: {llm_interface.worker.name}")
    # Future: llm_interface.switch_worker(new_openai_worker)
    #         llm_interface.switch_worker(new_anthropic_worker)

    # 2. Workers (connectors) do the actual work
    print("\n[2] Workers executing operations...")

    # Use interface (which delegates to worker)
    response = await llm_interface.chat("What is 2+2?")
    print(f"  LLM Response: {response.get('response', 'N/A')[:100]}...")

    # DB Interface
    if "db" in container._interfaces:
        db_interface = container.get_db("db")
        print(f"\nDB Interface: {db_interface.name}")
        print(f"  Worker: {db_interface.worker.name}")

        # Example query
        # users = await db_interface.select("SELECT COUNT(*) FROM users")
        # print(f"  Users count: {users}")

    # Storage Interface
    if "storage" in container._interfaces:
        storage_interface = container.get_storage("storage")
        print(f"\nStorage Interface: {storage_interface.name}")
        print(f"  Worker: {storage_interface.worker.name}")

    # Queue Interface
    if "queue" in container._interfaces:
        queue_interface = container.get_queue("queue")
        print(f"\nQueue Interface: {queue_interface.name}")
        print(f"  Worker: {queue_interface.worker.name}")

    # Observer pattern - metrics
    print("\n[Observer] Metrics collected:")
    metrics = container.get_metrics()
    if metrics:
        for operation, stats in list(metrics.items())[:5]:
            print(f"  {operation}:")
            print(f"    Count: {stats['count']}")
            print(f"    Avg: {stats['avg_ms']:.2f}ms")
            print(f"    Min: {stats['min_ms']:.2f}ms")
            print(f"    Max: {stats['max_ms']:.2f}ms")

    # Health checks
    print("\n[Health Checks]")
    health = await container.health_check_all()
    for name, healthy in health.items():
        status = "✅" if healthy else "❌"
        print(f"  {status} {name}: {healthy}")

    # Graceful shutdown
    print("\n[Shutdown]")
    await container.shutdown_all()
    print("All interfaces shut down successfully!")


async def strategy_pattern_example():
    """
    Example: Strategy pattern in action
    Shows how interfaces allow switching between different worker implementations
    """
    from core.base_class import ServiceContainer
    from interface.llm import LLMInterface
    from connectors.gigachat_connector import GigaChatConnector
    from core.base_class.factories import create_llm_connector
    from core.config import get_config

    config = get_config()
    container = await ServiceContainer.from_config(auto_initialize=False)

    # Get interface
    llm_interface = container.get_llm("llm")

    print(f"Current worker: {llm_interface.worker.name}")

    # Strategy pattern: Switch to different worker
    # In future, you could do:
    # new_worker = create_openai_connector(config)
    # llm_interface.switch_worker(new_worker)
    # print(f"New worker: {llm_interface.worker.name}")

    # Business logic stays the same!
    # response = await llm_interface.chat("Hello")
    # Works with any worker implementation


if __name__ == "__main__":
    asyncio.run(main())

