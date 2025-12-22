import asyncio
import time
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import List, Optional
from statistics import mean, stdev
from io import BytesIO
from connectors import MinIOConnector

# === НАСТРОЙКИ ===
MINIO_ENDPOINT = "localhost:9000"
ACCESS_KEY = "minioadmin1"
SECRET_KEY = "minioadmin1"
BUCKET_NAME = "test-bucket"
OBJECT_NAME_LARGE = "large-file-150mb.bin"

FILE_SIZE_MB = 150  # Размер файла в мегабайтах
CONCURRENT_TASKS = 6
REPEAT_PER_TASK = 2
TIMEOUT = 120.0  # Увеличено для больших файлов

# Режимы теста
TEST_BINARY = True
TEST_STREAMING = True

# === ЛОГИРОВАНИЕ ===
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("concurrency_test")

# >>> ВСТАВЬТЕ СЮДА ВАШ КЛАСС MinIOConnectorNoGIL <<<
# from your_module import MinIOConnectorNoGIL


@dataclass
class TaskResult:
    task_id: int
    mode: str  # "binary" или "streaming"
    attempt: int
    success: bool
    duration_sec: float
    data_size: int = 0
    error: Optional[str] = None


def generate_large_file(size_bytes: int) -> BytesIO:
    """Генерирует псевдослучайный файл заданного размера в памяти"""
    logger.info(f"Генерация файла размером {size_bytes / (1024**2):.1f} MiB...")
    data = bytearray(size_bytes)
    # Заполняем блоками для скорости (не криптостойко, но быстро)
    block = os.urandom(64 * 1024)  # 64 KiB блок
    for i in range(0, size_bytes, len(block)):
        data[i:i + len(block)] = block[:min(len(block), size_bytes - i)]
    return BytesIO(data)


async def upload_large_file_to_minio():
    """Загружает большой файл в MinIO (выполняется один раз)"""
    from minio import Minio
    from minio.error import S3Error

    client = Minio(
        MINIO_ENDPOINT,
        access_key=ACCESS_KEY,
        secret_key=SECRET_KEY,
        secure=False
    )

    # Создать бакет
    if not client.bucket_exists(BUCKET_NAME):
        client.make_bucket(BUCKET_NAME)
        logger.info(f"Создан бакет: {BUCKET_NAME}")

    # Генерация данных
    size_bytes = FILE_SIZE_MB * 1024 * 1024
    file_obj = generate_large_file(size_bytes)

    # Загрузка
    logger.info(f"Загрузка {FILE_SIZE_MB} MiB файла в MinIO...")
    start = time.perf_counter()
    client.put_object(
        BUCKET_NAME,
        OBJECT_NAME_LARGE,
        data=file_obj,
        length=size_bytes
    )
    duration = time.perf_counter() - start
    logger.info(f"✅ Файл {OBJECT_NAME_LARGE} загружен за {duration:.2f} сек "
                f"({FILE_SIZE_MB / duration:.2f} MiB/s)")


async def worker_task(
    connector,
    task_id: int,
    results: List[TaskResult],
    mode: str
):
    """Выполняет загрузку в указанном режиме"""
    for attempt in range(REPEAT_PER_TASK):
        start = time.perf_counter()
        try:
            if mode == "streaming":
                total = 0
                async for chunk in await connector.download(
                    object_name=OBJECT_NAME_LARGE,
                    use_streaming=True,
                    chunk_size=256 * 1024,  # 256 KiB
                    timeout=TIMEOUT
                ):
                    total += len(chunk)
                duration = time.perf_counter() - start
                results.append(TaskResult(task_id, mode, attempt, True, duration, total))
            else:  # binary
                data = await connector.download(
                    object_name=OBJECT_NAME_LARGE,
                    use_streaming=False,
                    timeout=TIMEOUT
                )
                duration = time.perf_counter() - start
                results.append(TaskResult(task_id, mode, attempt, True, duration, len(data)))
        except Exception as e:
            duration = time.perf_counter() - start
            error_msg = f"{type(e).__name__}: {e}"
            results.append(TaskResult(task_id, mode, attempt, False, duration, error=error_msg))
            logger.warning(f"Task {task_id} [{mode}] attempt {attempt} failed: {error_msg}")


async def run_test_mode(connector, mode: str, all_results: List[TaskResult]):
    print(f"\n--- Тест режима: {'БИНАРНАЯ ЗАГРУЗКА' if mode == 'binary' else 'ПОТОКОВАЯ ЗАГРУЗКА'} ---")
    tasks = [
        worker_task(connector, i, all_results, mode)
        for i in range(CONCURRENT_TASKS)
    ]
    await asyncio.gather(*tasks, return_exceptions=True)


async def main():
    print("🚀 Загрузка большого файла и запуск конкурентного теста")
    print(f"   • Размер файла: {FILE_SIZE_MB} MiB")
    print(f"   • Объект: {OBJECT_NAME_LARGE}")
    print(f"   • Параллельных задач: {CONCURRENT_TASKS}")
    print(f"   • Повторов на задачу: {REPEAT_PER_TASK}")
    print(f"   • Таймаут: {TIMEOUT} сек\n")

    # 1. Загружаем большой файл в MinIO
    await upload_large_file_to_minio()

    all_results: List[TaskResult] = []

    # 2. Создаём коннектор
    with ThreadPoolExecutor(max_workers=8) as executor:
        connector = MinIOConnector(
            endpoint=MINIO_ENDPOINT,
            access_key=ACCESS_KEY,
            secret_key=SECRET_KEY,
            bucket=BUCKET_NAME,
            executor=executor,
            use_ssl=False
        )

        try:
            await connector.initialize()
            if not await connector.health_check():
                raise RuntimeError("MinIO недоступен")

            # 3. Тест бинарной загрузки
            if TEST_BINARY:
                await run_test_mode(connector, "binary", all_results)

            # 4. Тест потоковой загрузки
            if TEST_STREAMING:
                await run_test_mode(connector, "streaming", all_results)

        finally:
            await connector.shutdown()

    # --- Анализ результатов ---
    print("\n" + "="*70)
    print("📊 СВОДНАЯ СТАТИСТИКА")
    print("="*70)

    for mode in ["binary", "streaming"]:
        mode_results = [r for r in all_results if r.mode == mode]
        if not mode_results:
            continue

        successful = [r for r in mode_results if r.success]
        failed = [r for r in mode_results if not r.success]
        total_ops = len(mode_results)
        total_bytes = sum(r.data_size for r in successful)

        print(f"\nРежим: {'БИНАРНЫЙ' if mode == 'binary' else 'ПОТОКОВЫЙ'}")
        print(f"  Операций:           {total_ops}")
        print(f"  Успешно:            {len(successful)} ({100 * len(successful) / total_ops:.1f}%)")
        print(f"  Общий объём:        {total_bytes / (1024**2):.1f} MiB")
        if successful:
            avg_size = mean(r.data_size for r in successful)
            expected_mb = FILE_SIZE_MB * 1024 * 1024
            print(f"  Средний размер:     {avg_size / (1024**2):.1f} MiB "
                  f"({'✅ OK' if abs(avg_size - expected_mb) < 1024 else '❌ Размер не совпадает'})")
            avg_time = mean(r.duration_sec for r in successful)
            print(f"  Среднее время:      {avg_time:.2f} сек")
            print(f"  Пропускная способность: {avg_size / avg_time / (1024**2):.2f} MiB/s")
        if failed:
            print(f"  Ошибок:             {len(failed)}")

    # Общая проверка
    all_successful = all(r.success for r in all_results)
    if all_successful:
        print("\n✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ: коннектор корректно работает с большими файлами!")
    else:
        print(f"\n⚠️  Некоторые операции завершились с ошибкой — проверьте логи.")

if __name__ == "__main__":
    asyncio.run(main())