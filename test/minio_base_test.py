from core.factories import _create_storage_connector
from config.config import get_settings
import unittest


class TestMinIOConnector(unittest.IsolatedAsyncioTestCase):
    """
    Unit-тесты для MinIOConnector, использующие фабрику и переменные окружения.
    Использует IsolatedAsyncioTestCase для корректной работы с async/await.
    Предполагает, что MinIO-сервер запущен (из .env).
    """

    @classmethod
    def setUpClass(cls):
        """
        Выполняется один раз перед всеми тестами в классе.
        Подготавливает настройки и создаёт коннектор.
        """
        # Убедимся, что используем переменные окружения
        cls.config = get_settings()
        cls.endpoint = cls.config.minio.endpoint
        cls.bucket_name = cls.config.minio.bucket_name
        print(f"Using MinIO endpoint: {cls.endpoint}, bucket: {cls.bucket_name}")

        # Создаём коннектор через фабрику
        # Executor нужен для инициализации
        from concurrent.futures import ThreadPoolExecutor
        cls.executor = ThreadPoolExecutor(max_workers=5)
        cls.connector = _create_storage_connector(cls.config, executor=cls.executor)

    async def asyncSetUp(self):
        """
        Асинхронная инициализация коннектора перед каждым тестом.
        """
        print("Initializing MinIO connector...")
        await self.connector.initialize()
        print("MinIO connector initialized.")

    async def asyncTearDown(self):
        """
        Асинхронная очистка после каждого теста.
        """
        print("Shutting down MinIO connector...")
        await self.connector.shutdown()
        print("MinIO connector shut down.")

    async def test_initialization(self):
        """
        Тест: Коннектор успешно инициализируется.
        """
        # asyncSetUp уже вызван автоматически
        # Проверим, что client не None после инициализации
        self.assertIsNotNone(self.connector.client)
        print("Initialization test passed.")

    async def test_health_check(self):
        """
        Тест: Проверка состояния коннектора.
        """
        # asyncSetUp уже вызван автоматически
        is_healthy = await self.connector.health_check()
        self.assertTrue(is_healthy, "MinIO connector should be healthy if MinIO is running.")
        print("Health check test passed.")

    async def test_upload_and_download_bytes(self):
        """
        Тест: Загрузка и скачивание файла как байтов.
        """
        object_name = "test_file.txt"
        test_data = b"Hello, MinIO! This is a test file content."

        # asyncSetUp уже вызван автоматически

        # 1. Загружаем файл
        await self.connector.upload(object_name=object_name, data=test_data)
        print(f"Uploaded file: {object_name}")

        # 2. Скачиваем файл как байты
        downloaded_data = await self.connector.download(object_name=object_name, use_streaming=False)
        print(f"Downloaded {len(downloaded_data)} bytes.")

        # 3. Проверяем содержимое
        self.assertEqual(downloaded_data, test_data)
        print("Upload and download bytes test passed.")

    async def test_upload_and_download_stream(self):
        """
        Тест: Загрузка и скачивание файла как потока.
        """
        object_name = "test_stream_file.txt"
        test_data = b"Streaming test content for MinIO."
        chunk_size = 8 # Небольшой размер чанка для теста

        # asyncSetUp уже вызван автоматически

        # 1. Загружаем файл
        await self.connector.upload(object_name=object_name, data=test_data)
        print(f"Uploaded file for streaming: {object_name}")

        # 2. Скачиваем файл как поток
        stream_generator = await self.connector.download(object_name=object_name, use_streaming=True,
                                                         chunk_size=chunk_size)
        print(f"Got stream generator for: {object_name}")

        downloaded_chunks = []
        # Теперь итерируемся по самому генератору
        async for chunk in stream_generator:
            downloaded_chunks.append(chunk)
        print(f"Downloaded {len(downloaded_chunks)} chunks via stream.")

        # 3. Собираем чанки обратно в байты
        reconstructed_data = b"".join(downloaded_chunks)

        # 4. Проверяем содержимое
        self.assertEqual(reconstructed_data, test_data)
        print("Upload and download stream test passed.")


# --- Если вы хотите запускать как обычный скрипт ---
# if __name__ == "__main__":
#     # Это не нужно, если используете unittest
#     pass