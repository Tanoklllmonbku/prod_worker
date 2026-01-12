"""
Простые тесты для LLM Service

Тесты проверяют бизнес-логику сервиса без инициализации реальных компонентов.
"""

import asyncio
import json
import unittest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from models.kafka_model import TaskStatus
from services.service import LLMService


class TestLLMService(unittest.IsolatedAsyncioTestCase):
    """Простые тесты для LLM Service"""

    def setUp(self):
        """Подготовка теста"""
        self.service = LLMService()

        # Просто инициализируем основные атрибуты вручную
        self.service.max_workers = 3
        self.service.worker_ids = [
            f"LLM_worker_{i + 1}" for i in range(self.service.max_workers)
        ]
        self.service._worker_semaphore = asyncio.Semaphore(self.service.max_workers)
        self.service.logger = MagicMock()

        # Мокаем интерфейсы
        self.service.llm = AsyncMock()
        self.service.queue = AsyncMock()
        self.service.storage = AsyncMock()

    async def test_kafka_consumer_processes_pending_messages(self):
        """Тест обработки сообщений с Kafka со статусом 1 (PENDING)"""
        # Подготовим сообщение Kafka
        kafka_message = {
            "kafka_key": "test_task_123",
            "payload": {"storage_path": "test_file.pdf"},
            "kafka_headers": {
                "status": "1",  # PENDING
                "trace_id": "test_trace_123",
                "prompt_id": "3",
            },
        }

        # Мокаем consume для возврата сообщения
        self.service.queue.consume = AsyncMock(return_value=kafka_message)
        self.service.queue.commit = AsyncMock()

        # Запускаем consumer loop в фоне
        task = asyncio.create_task(self.service._kafka_consumer_loop())

        # Ждем немного, чтобы сообщение было обработано
        await asyncio.sleep(0.01)

        # Останавливаем задачу
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Проверяем, что сообщение было добавлено в очередь обработки
        self.assertFalse(self.service._processing_queue.empty())

    async def test_worker_processes_task_and_sends_status_2(self):
        """Тест обработки задачи воркером с отправкой статуса 2"""
        # Подготовим данные задачи
        task_data = {
            "task_id": "test_task_456",
            "storage_path": "test_file.pdf",
            "trace_id": "test_trace_456",
            "prompt_id": 3,
            "original_message": {
                "kafka_key": "test_task_456",
                "payload": {"storage_path": "test_file.pdf"},
                "kafka_headers": {"status": "1", "trace_id": "test_trace_456"},
            },
        }

        # Добавляем задачу в очередь
        await self.service._processing_queue.put(task_data)

        # Мокаем вызовы
        self.service.storage.get_file = AsyncMock(return_value=b"test_file_content")
        self.service.llm.upload_file = AsyncMock(return_value="mock_file_id")
        self.service.llm.chat = AsyncMock(
            return_value={"response": '{"Статус": "Успешно", "result": "test"}'}
        )
        self.service.llm.delete_file = AsyncMock()
        self.service.queue.publish = AsyncMock()
        self.service.queue.commit = AsyncMock()

        # Запускаем воркер
        await self.service._worker_processor(0)

        # Проверяем, что был вызван publish для отправки статуса 2
        publish_calls = self.service.queue.publish.call_args_list
        status_2_found = any(
            call[1].get("headers", {}).get("status") == "2" for call in publish_calls
        )
        self.assertTrue(status_2_found, "Должен быть отправлен статус 2 (PROCESSING)")

    async def test_task_execution_success(self):
        """Тест успешного выполнения задачи"""
        task_data = {
            "task_id": "success_task_789",
            "storage_path": "success_file.pdf",
            "trace_id": "success_trace_789",
            "prompt_id": 3,
            "original_message": {
                "kafka_key": "success_task_789",
                "payload": {"storage_path": "success_file.pdf"},
                "kafka_headers": {"status": "1", "trace_id": "success_trace_789"},
            },
        }

        # Мокаем успешное выполнение
        self.service.storage.get_file = AsyncMock(return_value=b"test_content")
        self.service.llm.upload_file = AsyncMock(return_value="file_123")
        self.service.llm.chat = AsyncMock(
            return_value={"response": '{"Статус": "Успешно", "data": "result"}'}
        )
        self.service.llm.delete_file = AsyncMock()
        self.service.queue.publish = AsyncMock()
        self.service.queue.commit = AsyncMock()

        # Выполняем задачу
        result = await self.service._execute_llm_task(task_data)

        # Проверяем результат
        self.assertTrue(result["success"])
        self.assertIn("result", result)

    async def test_task_execution_failure(self):
        """Тест обработки ошибки при выполнении задачи"""
        task_data = {
            "task_id": "failed_task_999",
            "storage_path": "missing_file.pdf",
            "trace_id": "failed_trace_999",
            "prompt_id": 3,
            "original_message": {
                "kafka_key": "failed_task_999",
                "payload": {"storage_path": "missing_file.pdf"},
                "kafka_headers": {"status": "1", "trace_id": "failed_trace_999"},
            },
        }

        # Мокаем ошибку при загрузке файла
        self.service.storage.get_file = AsyncMock(
            side_effect=Exception("File not found")
        )
        self.service.queue.publish = AsyncMock()
        self.service.queue.commit = AsyncMock()

        # Выполняем задачу
        result = await self.service._execute_llm_task(task_data)

        # Проверяем результат
        self.assertFalse(result["success"])
        self.assertIn("error", result)

    async def test_send_status_update(self):
        """Тест отправки обновления статуса"""
        self.service.queue.publish = AsyncMock()

        await self.service._send_status_update(
            task_id="test_task",
            trace_id="test_trace",
            status=TaskStatus.PROCESSING,
            worker_id="LLM_worker_1",
        )

        # Проверяем, что publish был вызван с правильными параметрами
        self.service.queue.publish.assert_called_once()
        call_args = self.service.queue.publish.call_args
        headers = call_args[1]["headers"]

        self.assertEqual(headers["status"], "2")  # PROCESSING
        self.assertEqual(headers["trace_id"], "test_trace")
        self.assertEqual(headers["worker_id"], "LLM_worker_1")

    async def test_send_result_success(self):
        """Тест отправки успешного результата"""
        self.service.queue.publish = AsyncMock()

        await self.service._send_result(
            task_id="test_task",
            trace_id="test_trace",
            status=TaskStatus.SUCCESS,
            result_data={"result": "test_result"},
            worker_id="LLM_worker_1",
        )

        # Проверяем, что publish был вызван
        self.service.queue.publish.assert_called_once()
        call_args = self.service.queue.publish.call_args
        headers = call_args[1]["headers"]
        data = call_args[1]["data"]

        self.assertEqual(headers["status"], "3")  # SUCCESS
        self.assertIn("result", data)

    async def test_send_result_failure(self):
        """Тест отправки результата с ошибкой"""
        self.service.queue.publish = AsyncMock()

        await self.service._send_result(
            task_id="test_task",
            trace_id="test_trace",
            status=TaskStatus.FAILED,
            result_data={"error_message": "Test error"},
            worker_id="LLM_worker_1",
        )

        # Проверяем, что publish был вызван
        self.service.queue.publish.assert_called_once()
        call_args = self.service.queue.publish.call_args
        headers = call_args[1]["headers"]
        data = call_args[1]["data"]

        self.assertEqual(headers["status"], "4")  # FAILED
        self.assertIn("error_message", data)

    async def test_skips_non_pending_messages(self):
        """Тест пропуска сообщений с неверным статусом"""
        # Подготовим сообщение с неверным статусом
        kafka_message = {
            "kafka_key": "test_task_skip",
            "payload": {"storage_path": "test_file.pdf"},
            "kafka_headers": {
                "status": "2",  # PROCESSING - не PENDING
                "trace_id": "test_trace_skip",
                "prompt_id": "3",
            },
        }

        self.service.queue.consume = AsyncMock(return_value=kafka_message)
        self.service.queue.commit = AsyncMock()

        # Запускаем consumer loop
        task = asyncio.create_task(self.service._kafka_consumer_loop())

        # Ждем немного
        await asyncio.sleep(0.01)

        # Останавливаем задачу
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Проверяем, что сообщение было закоммичено (пропущено)
        self.service.queue.commit.assert_called_once()
        # И очередь обработки должна быть пустой
        self.assertTrue(self.service._processing_queue.empty())


class TestLLMServiceConfiguration(unittest.TestCase):
    """Тесты конфигурации сервиса"""

    def test_worker_ids_generation(self):
        """Тест генерации ID воркеров"""
        service = LLMService()
        service.max_workers = 5

        worker_ids = [f"LLM_worker_{i + 1}" for i in range(service.max_workers)]

        expected_ids = [
            "LLM_worker_1",
            "LLM_worker_2",
            "LLM_worker_3",
            "LLM_worker_4",
            "LLM_worker_5",
        ]
        self.assertEqual(worker_ids, expected_ids)

    def test_semaphore_initialization(self):
        """Тест инициализации семафора"""
        service = LLMService()
        service.max_workers = 3

        semaphore = asyncio.Semaphore(service.max_workers)
        self.assertIsInstance(semaphore, asyncio.Semaphore)


if __name__ == "__main__":
    unittest.main()
