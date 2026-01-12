import asyncio
import datetime
import json
import unittest
import uuid
from typing import Any, Dict

from config.config import get_settings
from core.factories import create_all_interfaces
from models.kafka_model import (
    KafkaHeaders,
    KafkaMessage,
    KafkaValueConsumer,
    TaskStatus,
)
from models.prompt_model import PromptService


class FullWorkflowTest(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        """
        Выполняется один раз перед всеми тестами в классе.
        Подготавливает настройки и создаёт интерфейсы.
        """
        # Убедимся, что используем переменные окружения
        cls.config = get_settings()

        # Создаём интерфейсы через фабрику
        cls.interfaces = create_all_interfaces(cls.config)
        cls.llm_interface = cls.interfaces.get("GigaChat")
        cls.db_interface = cls.interfaces.get("Postgres")
        cls.queue_interface = cls.interfaces.get("Kafka")
        cls.storage_interface = cls.interfaces.get("Minio")

    def test_getting_interfaces(self):
        print(f"Interfaces:")
        print(self.interfaces.get("GigaChat"))
        print(self.interfaces.get("Postgres"))
        print(self.interfaces.get("Kafka"))
        print(self.interfaces.get("Minio"))

    async def test_initialize(self):
        await self.llm_interface.initialize()
        await self.db_interface.initialize()
        await self.queue_interface.initialize()
        await self.storage_interface.initialize()

    async def test_kafka_monitor(self):
        """Тест полного рабочего процесса LLM сервиса"""
        await self.queue_interface.initialize()
        await self.storage_interface.initialize()

        is_healthy = await self.queue_interface.health_check()
        self.assertTrue(
            is_healthy, "Kafka connector should be healthy if Kafka is running."
        )
        print("Health check test passed.")

        topic = "tasks_llm"
        group_id = self.config.kafka.group_id
        await self.queue_interface.subscribe(
            topics=[topic],
            group_id=group_id
            + "_test_"
            + str(int(datetime.datetime.now().timestamp())),
            auto_offset_reset="latest",  # читаем только новые сообщения
        )

        processed_count = 0
        max_messages = 20  # Обрабатываем максимум 20 сообщений

        while processed_count < max_messages:
            message = await self.queue_interface.consume()

            if message:
                # Получаем task_id из ключа сообщения
                task_id = message.get(
                    "kafka_key"
                )  # task_id - это ключ сообщения из Kafka

                # Извлекаем полезную нагрузку и заголовки
                payload = message.get("payload", {})
                kafka_headers = message.get("kafka_headers", {})

                # Статус находится в kafka_headers, а не в payload
                status = kafka_headers.get("status")  # статус из kafka_headers

                # Если статус отсутствует или не равен "1", пропускаем сообщение
                if status != "1":
                    print(
                        f"Skipping message with status {status or 'missing'} for task {task_id}"
                    )
                    # Просто подтверждаем сообщение и продолжаем, чтобы не обрабатывать старые сообщения
                    try:
                        await self.queue_interface.commit(message)
                        print(f"Skipped message committed for task {task_id}")
                    except Exception as e:
                        print(
                            f"Failed to commit skipped message for task {task_id}: {str(e)}"
                        )
                    continue  # Переходим к следующему сообщению

                print(
                    f"Processing PENDING message with status {status} for task {task_id}"
                )

                # Извлекаем необходимые данные
                # storage_path находится в payload, а trace_id и другие данные в kafka_headers
                trace_id = kafka_headers.get("trace_id", str(uuid.uuid4()))
                storage_path = payload.get("storage_path")  # storage_path в payload
                prompt_id = kafka_headers.get(
                    "prompt_id", "3"
                )  # prompt_id в заголовках (если есть)

                print(
                    f"Extracted trace_id: {trace_id}, storage_path: {storage_path} for task {task_id}"
                )

                processing_start_time = datetime.datetime.now()

                # Отправляем статус "PROCESSING" (2) с тем же ключом (task_id)
                await self.queue_interface.publish(
                    topic=topic,
                    key=task_id,
                    data={},  # пустой payload для статуса PROCESSING
                    headers={
                        "status": "2",
                        "trace_id": trace_id,
                        "worker_id": "LLM_service_1",  # worker_id из пула воркеров
                        "timestamp": datetime.datetime.now().isoformat(),
                    },
                )
                print(f"Status 'PROCESSING' sent for task {task_id}")

                # Проверяем, есть ли storage_path
                if not storage_path:
                    print(f"No storage_path found in message for task {task_id}")
                    # Отправляем статус "FAILED" (4) при ошибке
                    error_data = {
                        "error_message": "No storage_path found in message"
                    }  # отправляем только error_message в value
                    await self.queue_interface.publish(
                        topic=topic,
                        key=task_id,
                        data=error_data,
                        headers={
                            "status": "4",
                            "trace_id": trace_id,
                            "worker_id": "LLM_service_1",
                            "timestamp": datetime.datetime.now().isoformat(),
                        },
                    )
                    print(
                        f"Status 'FAILED' sent for task {task_id} due to missing storage_path"
                    )
                    # Подтверждаем обработку сообщения
                    try:
                        await self.queue_interface.commit(message)
                        print(f"Message committed for task {task_id}")
                    except Exception as e:
                        print(f"Failed to commit message for task {task_id}: {str(e)}")
                    continue

                file_id = None  # Инициализируем переменную для очистки
                error_occurred = False

                try:
                    # Загружаем файл из хранилища
                    file_data = await self.storage_interface.get_file(storage_path)

                    # Загружаем файл в LLM
                    file_id = await self.llm_interface.upload_file(
                        file_data=file_data,
                        filename=storage_path.split("/")[-1],
                        timeout=30.0,
                    )

                    # Получаем промпт для обработки
                    # prompt_id уже извлечен из kafka_headers выше
                    prompt_service = PromptService()
                    prompt = prompt_service.get_prompt_by_id(int(prompt_id))

                    if not prompt:
                        print(f"Prompt with id {prompt_id} not found")
                        # Отправляем статус "FAILED" (4) при ошибке
                        error_data = {
                            "error_message": f"Prompt with id {prompt_id} not found"
                        }  # отправляем только error_message в value
                        await self.queue_interface.publish(
                            topic=topic,
                            key=task_id,
                            data=error_data,
                            headers={
                                "status": "4",
                                "trace_id": trace_id,
                                "worker_id": "LLM_service_1",
                                "timestamp": datetime.datetime.now().isoformat(),
                            },
                        )
                        print(
                            f"Status 'FAILED' sent for task {task_id} due to missing prompt"
                        )
                    else:
                        # Отправляем запрос в LLM
                        response = await self.llm_interface.chat(
                            prompt=prompt, file_ids=[file_id] if file_id else []
                        )

                        # Проверяем статус ответа
                        # GigaChat connector возвращает: {"response": content, "tokens_used": ..., ...}
                        response_content = response.get("response", "")

                        # Проверяем, содержит ли ответ валидный JSON результат
                        try:
                            # Пробуем распарсить ответ как JSON, чтобы проверить, успешен ли он
                            import json

                            parsed_response = (
                                json.loads(response_content)
                                if response_content
                                and response_content.strip().startswith("{")
                                else {}
                            )

                            # Проверяем, есть ли статус в JSON ответе
                            status_in_response = parsed_response.get(
                                "Статус", parsed_response.get("status", "")
                            )

                            if status_in_response in [
                                "Успешно",
                                "Success",
                                "success",
                                "SUCCESS",
                            ]:
                                # Отправляем статус "SUCCESS" (3) с результатом
                                result_json = json.dumps(
                                    parsed_response, ensure_ascii=False
                                )  # конвертируем dict в JSON строку
                                result_data = {
                                    "result": result_json
                                }  # отправляем только result в value
                                await self.queue_interface.publish(
                                    topic=topic,
                                    key=task_id,
                                    data=result_data,
                                    headers={
                                        "status": "3",
                                        "trace_id": trace_id,
                                        "worker_id": "LLM_service_1",
                                        "timestamp": datetime.datetime.now().isoformat(),
                                    },
                                )
                                print(f"Status 'SUCCESS' sent for task {task_id}")
                            else:
                                # Отправляем статус "FAILED" (4) с сообщением об ошибкой
                                error_data = {
                                    "error_message": f"GigaChat returned invalid response format or error status: {status_in_response}"
                                }  # отправляем только error_message в value
                                await self.queue_interface.publish(
                                    topic=topic,
                                    key=task_id,
                                    data=error_data,
                                    headers={
                                        "status": "4",
                                        "trace_id": trace_id,
                                        "worker_id": "LLM_service_1",
                                        "timestamp": datetime.datetime.now().isoformat(),
                                    },
                                )
                                print(
                                    f"Status 'FAILED' sent for task {task_id} due to invalid response format"
                                )
                        except json.JSONDecodeError:
                            # Если не удалось распарсить как JSON, считаем что ошибка
                            error_data = {
                                "error_message": f"GigaChat response is not valid JSON: {response_content[:200]}..."
                            }  # отправляем только error_message в value
                            await self.queue_interface.publish(
                                topic=topic,
                                key=task_id,
                                data=error_data,
                                headers={
                                    "status": "4",
                                    "trace_id": trace_id,
                                    "worker_id": "LLM_service_1",
                                    "timestamp": datetime.datetime.now().isoformat(),
                                },
                            )
                            print(
                                f"Status 'FAILED' sent for task {task_id} due to invalid JSON response"
                            )

                except Exception as e:
                    print(f"Error processing task {task_id}: {str(e)}")
                    # Отправляем статус "FAILED" (4) при ошибке
                    error_data = {
                        "error_message": str(e)
                    }  # отправляем только error_message в value
                    await self.queue_interface.publish(
                        topic=topic,
                        key=task_id,
                        data=error_data,
                        headers={
                            "status": "4",
                            "trace_id": trace_id,
                            "worker_id": "LLM_service_1",
                            "timestamp": datetime.datetime.now().isoformat(),
                        },
                    )
                    print(f"Status 'FAILED' sent for task {task_id} due to exception")
                finally:
                    # Удаляем файл из LLM (очистка)
                    if file_id:
                        try:
                            await self.llm_interface.delete_file(file_id)
                            print(f"File {file_id} deleted from LLM")
                        except Exception as e:
                            print(f"Failed to delete file {file_id}: {str(e)}")

                # Подтверждаем обработку сообщения
                try:
                    await self.queue_interface.commit(message)
                    print(f"Message committed for task {task_id}")
                except Exception as e:
                    print(f"Failed to commit message for task {task_id}: {str(e)}")

                # Увеличиваем счетчик обработанных сообщений
                processed_count += 1
                print(f"Processed {processed_count}/{max_messages} messages")

                # Если обработали нужное количество сообщений, выходим
                if processed_count >= max_messages:
                    break
            else:
                print("No message received for processing")
                # Если нет сообщений, ждем немного перед следующей итерацией
                await asyncio.sleep(0.1)
                continue
