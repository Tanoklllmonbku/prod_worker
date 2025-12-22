import asyncio
import logging
from connectors import PGConnector


async def main():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Инициализация
    db = PGConnector(
        host="localhost",
        port=5432,
        database="pg_test",
        user="postgres",  # ← используй superuser
        password="postgres",
        min_pool_size=5,
        max_pool_size=20,
        logger=logger,
    )

    try:
        await db.initialize()

        # 1. Проверка здоровья БД
        is_healthy = await db.health_check()
        print(f"✓ Database health: {is_healthy}")

        # 2. Создание таблицы (если не существует)
        try:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    age INTEGER
                )
            """)
            print("✓ Table 'users' created or already exists")
        except Exception as e:
            logger.warning(f"Could not create table: {e}")

        # 3. Очистить таблицу для теста
        try:
            await db.execute("TRUNCATE TABLE users CASCADE")
            print("✓ Table 'users' truncated")
        except Exception as e:
            logger.warning(f"Could not truncate table: {e}")

        # 4. Массовая вставка
        rows_to_insert = [
            ("Alice", 25),
            ("Bob", 30),
            ("Charlie", 35),
            ("Diana", 22),
            ("Eve", 28),
        ]
        try:
            inserted = await db.bulk_insert(
                "users",
                ["name", "age"],
                rows_to_insert,
                batch_size=1000
            )
            print(f"✓ Inserted {inserted} rows")
        except Exception as e:
            logger.error(f"Bulk insert failed: {e}")

        # 5. Простой SELECT
        try:
            rows = await db.load("SELECT * FROM users WHERE age > $1", 25)
            print(f"✓ Loaded {len(rows)} users with age > 25")
            for row in rows:
                print(f"  - {row}")
        except Exception as e:
            logger.error(f"Load failed: {e}")

        # 6. Загрузить одну строку
        try:
            one = await db.load_one("SELECT * FROM users WHERE name = $1", "Alice")
            print(f"✓ Loaded single row: {one}")
        except Exception as e:
            logger.error(f"Load one failed: {e}")

        # 7. Загрузить скалярное значение
        try:
            count = await db.load_scalar("SELECT COUNT(*) FROM users")
            print(f"✓ Total users: {count}")
        except Exception as e:
            logger.error(f"Load scalar failed: {e}")

        # 8. Параллельные запросы
        try:
            results = await db.load_concurrent([
                ("SELECT COUNT(*) as cnt FROM users",),
                ("SELECT AVG(age) as avg_age FROM users",),
                ("SELECT MIN(age) as min_age FROM users",),
            ])
            print(f"✓ Concurrent results:")
            for i, result in enumerate(results):
                print(f"  Query {i+1}: {result}")
        except Exception as e:
            logger.error(f"Concurrent queries failed: {e}")

        # 9. Потоком для больших результатов
        try:
            chunk_count = 0
            total_rows = 0
            async for chunk in db.load_stream(
                "SELECT * FROM users",
                chunk_size=2
            ):
                chunk_count += 1
                total_rows += len(chunk)
                print(f"✓ Stream chunk {chunk_count}: {len(chunk)} rows")
        except Exception as e:
            logger.error(f"Stream failed: {e}")

        # 10. Export to CSV
        try:
            buffer = await db.load_to_buffer(
                "SELECT * FROM users ORDER BY id",
                format="csv"
            )
            csv_content = buffer.getvalue().decode()
            print(f"✓ Exported to CSV:\n{csv_content}")
        except Exception as e:
            logger.error(f"Export to CSV failed: {e}")

        # 11. Export to JSON
        try:
            buffer = await db.load_to_buffer(
                "SELECT * FROM users ORDER BY id",
                format="json"
            )
            json_content = buffer.getvalue().decode()
            print(f"✓ Exported to JSON:\n{json_content}")
        except Exception as e:
            logger.error(f"Export to JSON failed: {e}")

        # 12. Статистика пула
        try:
            stats = await db.get_pool_stats()
            print(f"✓ Pool stats: {stats}")
        except Exception as e:
            logger.error(f"Pool stats failed: {e}")

        # 13. UPDATE
        try:
            result = await db.execute(
                "UPDATE users SET age = age + 1 WHERE name = $1",
                "Alice"
            )
            print(f"✓ Updated: {result}")
        except Exception as e:
            logger.error(f"Update failed: {e}")

        # 14. DELETE
        try:
            result = await db.execute(
                "DELETE FROM users WHERE name = $1",
                "Eve"
            )
            print(f"✓ Deleted: {result}")
        except Exception as e:
            logger.error(f"Delete failed: {e}")

        # 15. Финальный COUNT
        try:
            final_count = await db.load_scalar("SELECT COUNT(*) FROM users")
            print(f"✓ Final user count: {final_count}")
        except Exception as e:
            logger.error(f"Final count failed: {e}")

    finally:
        await db.shutdown()


if __name__ == "__main__":
    asyncio.run(main())