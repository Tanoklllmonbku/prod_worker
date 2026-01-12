"""
Example usage of Registry-based DI container.

This demonstrates the recommended way to use connectors in your application.
"""

import asyncio

from core.service_container import ServiceContainer
from models.prompt_model import PromptService


async def main():
    """Example: Basic container usage"""

    # 1. Initialize container (reads from config, initializes all connectors)
    print("Initializing service container...")
    container = await ServiceContainer.from_config(auto_initialize=True)

    # 2. Use connectors via container
    print("\n=== Using LLM Connector ===")
    llm = container.get_llm("llm")
    prompt = PromptService().get_prompt_by_id(3)
    with open("doc09704620250910124751.pdf", "rb") as f:
        file = await llm.upload_file(f)
    response = await llm.chat(prompt=prompt, file_ids=[file])
    print(f"LLM Response: {response}")

    # 3. Use database connector (if enabled)
    if container.config.enable_database:
        print("\n=== Using DB Connector ===")
        db = container.get_db("db")
        # Example query
        # users = await db.load("SELECT id, name FROM users LIMIT 5")
        # print(f"Found {len(users)} users")

    # 4. Use storage connector (if enabled)
    if container.config.enable_minio:
        print("\n=== Using Storage Connector ===")
        storage = container.get_storage("storage")
        # Example download
        # data = await storage.download("my-file.pdf")
        # print(f"Downloaded {len(data)} bytes")

    # 5. Use queue connector (if enabled)
    if container.config.enable_kafka:
        print("\n=== Using Queue Connector ===")
        queue = container.get_queue("queue")
        # Example publish
        # await queue.publish(
        #     topic="events",
        #     datagram_id="123",
        #     data={"event": "user_created"}
        # )

    # 6. Health checks
    print("\n=== Health Checks ===")
    health = await container.health_check_all()
    for conn_type, statuses in health.items():
        for name, healthy in statuses.items():
            status = "✅" if healthy else "❌"
            print(f"{status} {conn_type.value}/{name}: {healthy}")

    # 7. Graceful shutdown
    print("\nShutting down...")
    await container.shutdown_all()
    print("Done!")


async def advanced_example():
    """Example: Manual registration and initialization"""

    from config.config import get_config
    from core.service_container import ServiceContainer

    config = get_config()
    container = ServiceContainer(config)

    # Manual registration
    await container.register_all()

    # Manual initialization with error handling
    init_results = await container.initialize_all()
    for conn_type, statuses in init_results.items():
        for name, success in statuses.items():
            if not success:
                print(f"⚠️ Failed to initialize {conn_type.value}/{name}")

    # Use connectors
    llm = container.get_llm("gigachat")

    # Cleanup
    await container.shutdown_all()


if __name__ == "__main__":
    asyncio.run(main())
