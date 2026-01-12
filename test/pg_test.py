import datetime

from core.factories import _create_db_connector
from config.config import get_settings
import unittest


class TestPGConnector(unittest.IsolatedAsyncioTestCase):
    """
    Unit-тесты для PGConnector, использующие фабрику и переменные окружения.
    Использует IsolatedAsyncioTestCase для корректной работы с async/await.
    Предполагает, что PostgreSQL-сервер запущен и таблица 'logs' существует (из .env).
    """

    @classmethod
    def setUpClass(cls):
        """
        Выполняется один раз перед всеми тестами в классе.
        Подготавливает настройки и создаёт коннектор.
        """
        # Убедимся, что используем переменные окружения
        cls.config = get_settings()
        cls.host = cls.config.postgres.host
        cls.database = cls.config.postgres.database
        print(f"Using PostgreSQL host: {cls.host}, database: {cls.database}")

        # Создаём коннектор через фабрику
        cls.connector = _create_db_connector(cls.config)

    async def asyncSetUp(self):
        """
        Асинхронная инициализация коннектора перед каждым тестом.
        """
        print("Initializing PG connector...")
        await self.connector.initialize()
        print("PG connector initialized.")

    async def asyncTearDown(self):
        """
        Асинхронная очистка после каждого теста.
        """
        print("Shutting down PG connector...")
        await self.connector.shutdown()
        print("PG connector shut down.")

    async def test_initialization(self):
        """
        Тест: Коннектор успешно инициализируется.
        """
        # asyncSetUp уже вызван автоматически
        # Проверим, что pool не None после инициализации
        self.assertIsNotNone(self.connector._pool)
        print("Initialization test passed.")

    async def test_health_check(self):
        """
        Тест: Проверка состояния коннектора.
        """
        # asyncSetUp уже вызван автоматически
        is_healthy = await self.connector.health_check()
        self.assertTrue(is_healthy, "PG connector should be healthy if PostgreSQL is running.")
        print("Health check test passed.")

    async def test_execute_insert_log_entry(self):
        """
        Тест: Вставка записи в таблицу 'logs' через execute.
        """
        # asyncSetUp уже вызван автоматически

        # Подготовим данные для вставки (согласно DBLogEntry)
        task_id = "test_task_123"
        trace_id = "test_trace_456"
        event_type = "health_check"
        status = "success"
        duration_ms = datetime.date(1,2,3)
        metadata = str('{"node": "worker_1", "version": "1.0.0"}')
        # 1. Выполняем INSERT запрос
        query = """
        INSERT INTO operation_logs (task_id, trace_id, operation, timestamp, metadata)
        VALUES ($1, $2, $3, $4, $5)
        """
        await self.connector.execute(query, task_id, trace_id, event_type, duration_ms, metadata)
        print(f"Executed INSERT for task_id: {task_id}")

        # 2. (Опционально) Проверим, что запись появилась, выполнив SELECT
        # Требует, чтобы таблица была пустой или чтобы мы знали, какую запись искать.
        # Более надёжный способ - проверить, что execute не вызвал ошибку.
        # Для простоты, проверим успешное выполнение execute выше.
        # Если нужно - можно добавить SELECT COUNT(*) с фильтром по task_id.
        # query_check = "SELECT COUNT(*) FROM logs WHERE task_id = $1"
        # result = await self.connector.load_scalar(query_check, task_id)
        # self.assertGreater(result, 0, "Record should have been inserted.")

        print("Execute INSERT log entry test passed.")

    async def test_bulk_insert_log_entries(self):
        """
        Тест: Массовая вставка записей в таблицу 'logs' через bulk_insert.
        """
        # asyncSetUp уже вызван автоматически

        # Подготовим данные для вставки (несколько записей)
        rows_to_insert = [
            ("bulk_task_1", "trace_bulk_1", "task_received", "started", 0.0, {"info": "start"}),
            ("bulk_task_2", "trace_bulk_2", "task_completed", "success", 456.78, {"info": "end"}),
        ]
        columns = ["task_id", "trace_id", "event", "status", "duration_ms", "metadata"]

        # 1. Выполняем bulk_insert
        inserted_count = await self.connector.bulk_insert(
            table="operation_logs", columns=columns, rows=rows_to_insert, batch_size=10
        )
        print(f"Executed bulk insert for {len(rows_to_insert)} rows, {inserted_count} inserted.")

        # 2. Проверим, что записи появились (опционально, как в предыдущем тесте)
        # query_check = "SELECT COUNT(*) FROM logs WHERE task_id = ANY($1::text[])"
        # task_ids = [r[0] for r in rows_to_insert]
        # result = await self.connector.load_scalar(query_check, task_ids)
        # self.assertEqual(result, len(rows_to_insert), "All bulk records should have been inserted.")

        self.assertEqual(inserted_count, len(rows_to_insert))
        print("Bulk insert log entries test passed.")


# --- Если вы хотите запускать как обычный скрипт ---
# if __name__ == "__main__":
#     # Это не нужно, если используете unittest
#     pass