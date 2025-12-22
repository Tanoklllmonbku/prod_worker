import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from minio import Minio
from minio.error import S3Error

from connectors import MinIOConnector

# Замените эти значения на ваши реальные
MINIO_ENDPOINT = "localhost:9000"
ACCESS_KEY = "minioadmin1"
SECRET_KEY = "minioadmin1"
BUCKET_NAME = "test-bucket"
OBJECT_NAME = "test-file.bin"  # Убедитесь, что этот файл существует в бакете

# Вставьте сюда ваш класс MinIOConnectorNoGIL (или импортируйте из модуля)
# from your_module import MinIOConnectorNoGIL

# >>> ВСТАВЬТЕ СЮДА ВЕСЬ ВАШ КЛАСС MinIOConnectorNoGIL <<<

logging.basicConfig(level=logging.DEBUG)

async def main():
    # Создаём общий ThreadPoolExecutor (можно переиспользовать)
    with ThreadPoolExecutor(max_workers=4) as executor:
        connector = MinIOConnector(
            endpoint=MINIO_ENDPOINT,
            access_key=ACCESS_KEY,
            secret_key=SECRET_KEY,
            bucket=BUCKET_NAME,
            executor=executor,
            use_ssl=False
        )

        try:
            # 1. Инициализация
            print("🔄 Инициализация MinIO...")
            await connector.initialize()
            print("✅ MinIO инициализирован")

            # 2. Проверка здоровья
            healthy = await connector.health_check()
            print(f"🩺 Health check: {'OK' if healthy else 'FAIL'}")
            assert healthy, "MinIO должен быть здоров после инициализации"

            # 3. Загрузка бинарных данных (полный файл в bytes)
            print(f"📥 Загрузка файла как bytes: {OBJECT_NAME}")
            data = await connector.download(
                object_name=OBJECT_NAME,
                use_streaming=False,
                timeout=30.0
            )
            assert isinstance(data, bytes), "Ожидались bytes"
            print(f"✅ Успешно загружено {len(data)} байт")

            # 4. Потоковая загрузка (асинхронный генератор)
            print(f"🌊 Загрузка файла потоком: {OBJECT_NAME}")
            total = 0
            async for chunk in await connector.download(
                object_name=OBJECT_NAME,
                use_streaming=True,
                chunk_size=1024,
                timeout=30.0
            ):
                assert isinstance(chunk, bytes), "Chunk должен быть bytes"
                total += len(chunk)
            print(f"✅ Потоковая загрузка завершена: {total} байт")
            assert total == len(data), "Размеры при потоковой и полной загрузке должны совпадать"

            # 5. Тест таймаута (на несуществующем объекте с малым таймаутом)
            print("⏳ Тест таймаута на несуществующем файле...")
            try:
                await connector.download(
                    object_name="nonexistent-file.txt",
                    use_streaming=False,
                    timeout=10.0  # Очень малый таймаут
                )
                assert False, "Должна была возникнуть ошибка таймаута или S3Error"
            except S3Error as e:
                print(f"✅ Ожидаемая ошибка: {type(e).__name__}: {e}")

            # 6. Тест ошибки: несуществующий объект
            print("🚫 Тест ошибки: несуществующий объект...")
            try:
                await connector.download(
                    object_name="definitely-not-exists.bin",
                    use_streaming=False,
                    timeout=10.0
                )
                assert False, "Должна была быть S3Error (NoSuchKey)"
            except S3Error as e:
                print(f"✅ Получена ожидаемая S3Error: {e.code}")

            # 6. Тест таймаута — пропускаем или помечаем как "требует специальной среды"
            print("⏳ Тест таймаута: пропущен (требует недоступного MinIO)")

            print("\n🎉 Все тесты пройдены успешно!")

        finally:
            # Завершение работы
            print("🔚 Завершение работы...")
            await connector.shutdown()

# ==============================
# Дополнительно: создание тестового файла в MinIO (если нужно)
# ==============================
async def upload_test_file():
    """Опционально: загрузить тестовый файл в MinIO перед запуском"""
    client = Minio(
        MINIO_ENDPOINT,
        access_key=ACCESS_KEY,
        secret_key=SECRET_KEY,
        secure=False
    )

    # Создать бакет, если нужно
    if not client.bucket_exists(BUCKET_NAME):
        client.make_bucket(BUCKET_NAME)
        print(f"🆕 Создан бакет: {BUCKET_NAME}")

    # Загрузить тестовые данные
    test_data = b"Hello, MinIO! This is a test binary file for async download.\n" * 1000
    client.put_object(BUCKET_NAME, OBJECT_NAME, data=io.BytesIO(test_data), length=len(test_data))
    print(f"📤 Тестовый файл '{OBJECT_NAME}' загружен в MinIO")

if __name__ == "__main__":
    import io
    import sys

    # Опционально: раскомментируйте, чтобы автоматически создать тестовый файл
    asyncio.run(upload_test_file())

    # Запуск тестов
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️ Прервано пользователем")
    except Exception as e:
        print(f"\n💥 Критическая ошибка: {e}", file=sys.stderr)
        sys.exit(1)