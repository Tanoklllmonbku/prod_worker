"""
LLM Service - Multi-worker Kafka Consumer with Load Distribution

Architecture:
1. Single Kafka consumer continuously reading messages
2. Load distribution across up to N workers (from config)
3. Send status=2 before LLM processing
4. Process tasks with distributed workers
5. Send results back to Kafka (status=3/4)
"""

import asyncio
import json
import logging
import random
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Lock
from typing import Any, Dict, List, Optional, Set

from config.config import get_settings
from core.base_service import BaseService
from core.service_factory import register_service
from models.kafka_model import TaskStatus
from models.prompt_model import PromptService
from utils.logging import get_logger_from_config


@register_service('llm')
class LLMService(BaseService):
    """Main LLM service with multi-worker load distribution"""

    def __init__(self, config=None):
        super().__init__(name="LLMService", config=config)

        # Interfaces
        self.llm = None  # LLMInterface
        self.queue = None  # QueueInterface
        self.db = None  # DBInterface
        self.storage = None  # StorageInterface
        self.http = None # HTTPInterface

        # Configuration
        self.max_workers: int = 0
        self.worker_ids: List[str] = []

        # State management
        self._active_tasks: Dict[str, asyncio.Task] = {}
        self._consumer_running = False
        self._processing_queue = asyncio.Queue()
        self._worker_semaphore = None
        self._processed_tasks: Set[str] = set()

        # Worker management
        self._worker_tasks: List[asyncio.Task] = []

        # Token refresh management
        self._token_refresh_task: Optional[asyncio.Task] = None

    async def _initialize_service(self) -> bool:
        """
        Initialize the service components.

        Returns:
            True if initialization was successful, False otherwise
        """
        try:
            # Get configuration
            config = self.config
            self.max_workers = config.worker_max_concurrent_tasks

            # Initialize container if not already done
            if self.container is None:
                await self.initialize_container(auto_initialize=True)

            # Initialize task deduplication queue with 50 max entries
            self.container.initialize_task_deduplication_queue(max_size=50)

            # Get interfaces
            self.llm = self.container.get_llm("GigaChat")
            self.queue = self.container.get_queue("Kafka")
            self.db = self.container.get_db("Postgres")
            self.storage = self.container.get_storage("Minio")
            self.http = None

            # Initialize HTTP server
            if self.container.config.http.enabled:
                try:
                    self.http = self.container.get_http("FastApi")
                    # Инициализируем HTTP-приложение с callback'ами
                    self.http.worker.start()
                except KeyError:
                    self._logger.warning("HTTP interface 'FastApi' not found in container")
                except Exception as e:
                    self._logger.error(f"Failed to initialize HTTP interface: {e}")

            # Initialize LLM
            await self.llm.initialize()

            # Create worker IDs
            self.worker_ids = [f"LLM_worker_{i + 1}" for i in range(self.max_workers)]

            # Initialize semaphore for worker limiting
            self._worker_semaphore = asyncio.Semaphore(self.max_workers)

            # Start token refresh task
            await self._start_token_refresh_task()

            self._logger.info(
                f"LLM Service initialized with {self.max_workers} workers"
            )
            return True

        except ImportError as e:
            self._logger.critical(f"Initialization failed due to import error: {e}", exc_info=True)
            return False
        except AttributeError as e:
            self._logger.critical(f"Initialization failed due to attribute error: {e}", exc_info=True)
            return False
        except Exception as e:
            self._logger.error(f"Initialization failed: {e}", exc_info=True)
            return False

    async def _startup_impl(self) -> None:
        """
        Implementation method for service-specific startup logic.
        This overrides the method from BaseService.
        """
        # Initialize service components
        success = await self._initialize_service()
        if not success:
            raise RuntimeError("Failed to initialize LLM Service")

        self._logger.info("LLM Service started, initializing workers...")

        print("\n" + "=" * 60)
        print(f"LLM Service running with {self.max_workers} workers")
        print("Press Ctrl+C to stop.")
        print("=" * 60 + "\n")

        http_task = None
        if self.http:
            try:
                import uvicorn
                app = self.http.worker.app
                config = uvicorn.Config(
                    app=app,
                    host=self.container.config.http.host,
                    port=self.container.config.http.port,
                    log_level="warning",
                    access_log=False,
                )
                self._http_server = uvicorn.Server(config)
                http_task = asyncio.create_task(self._http_server.serve())
                self._logger.info(f"HTTP monitor started on {self.container.config.http.host}:{self.container.config.http.port}")
            except Exception as e:
                self._logger.error(f"Failed to start HTTP server: {e}")

        # Start Kafka consumer
        kafka_task = asyncio.create_task(self._kafka_consumer_loop())

        # Start worker processors
        worker_tasks = []
        for i in range(self.max_workers):
            worker_task = asyncio.create_task(self._worker_processor(i))
            worker_tasks.append(worker_task)

        # Wait for shutdown
        shutdown_task = asyncio.create_task(self.get_shutdown_event().wait())

        # Include HTTP task in wait set
        all_tasks = [kafka_task, shutdown_task] + worker_tasks
        if http_task:
            all_tasks.append(http_task)

        done, pending = await asyncio.wait(
            all_tasks,
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Cancel remaining tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def _perform_shutdown(self) -> None:
        """Perform the actual shutdown of the service."""
        self._logger.info("Shutting down LLM Service...")

        # Shutdown HTTP server first
        if hasattr(self, '_http_server') and self._http_server:
            self._http_server.should_exit = True
            self._logger.info("HTTP server shutdown initiated")

        # Wait a bit for graceful shutdown
        await asyncio.sleep(0.1)

        # Cancel all active tasks
        for task in self._active_tasks.values():
            task.cancel()

        # Wait for worker tasks to complete
        for task in self._worker_tasks:
            task.cancel()

        # Cancel token refresh task
        if self._token_refresh_task:
            self._token_refresh_task.cancel()
            try:
                await self._token_refresh_task
            except asyncio.CancelledError:
                pass

        # Shutdown interfaces
        if self.llm:
            try:
                await self.llm.shutdown()
                self._logger.info("LLM interface shutdown complete")
            except Exception as e:
                self._logger.error(f"Error shutting down LLM: {e}")

        self._logger.info("LLM Service shutdown complete")

    async def _shutdown_impl(self) -> None:
        """
        Implementation method for service-specific shutdown logic.
        This overrides the method from BaseService.
        """
        await self._perform_shutdown()

    async def _kafka_consumer_loop(self) -> None:
        """Continuously consume messages from Kafka"""
        try:
            self.logger.info("Starting Kafka consumer...")

            # Subscribe to tasks topic
            await self.queue.subscribe(
                topics=["tasks_llm"],
                group_id=self.container.config.kafka.group_id
                + f"_llm_service_{int(time.time())}",
                auto_offset_reset="latest",
            )

            self._consumer_running = True
            self.logger.info("Subscribed to Kafka topic 'tasks_llm'")

            while not self._shutdown_event.is_set():
                try:
                    # Get message from Kafka with timeout
                    message = await asyncio.wait_for(self.queue.consume(), timeout=1.0)

                    # Extract message data
                    task_id = message.get("kafka_key")
                    payload = message.get("payload", {})
                    kafka_headers = message.get("kafka_headers", {})

                    # Check status - only process PENDING (status 1)
                    status = kafka_headers.get("status")
                    if status != "1":
                        self.logger.debug(
                            f"Skipping message with status {status} for task {task_id}"
                        )
                        # Commit the message to avoid reprocessing
                        try:
                            await self.queue.commit(message)
                        except Exception as e:
                            self.logger.error(f"Failed to commit skipped message: {e}")
                        continue

                    # Check for duplicate task using deduplication queue
                    if self.container.is_task_duplicate(task_id):
                        self.logger.info(
                            f"Duplicate task detected: {task_id}, skipping..."
                        )
                        # Commit the message to avoid reprocessing
                        try:
                            await self.queue.commit(message)
                        except Exception as e:
                            self.logger.error(
                                f"Failed to commit duplicate message: {e}"
                            )
                        continue

                    # Extract required data
                    trace_id = kafka_headers.get("trace_id", str(uuid.uuid4()))
                    storage_path = payload.get("storage_path")
                    prompt_id = kafka_headers.get("prompt_id", "3")

                    self.logger.info(
                        f"[{trace_id}] Received task {task_id}, storage_path: {storage_path}"
                    )

                    # Add task to deduplication queue
                    self.container.add_task_to_deduplication_queue(task_id)

                    # Add to processing queue
                    task_data = {
                        "task_id": task_id,
                        "storage_path": storage_path,
                        "trace_id": trace_id,
                        "prompt_id": int(prompt_id) if prompt_id else 3,
                        "original_message": message,
                    }

                    await self._processing_queue.put(task_data)

                except asyncio.TimeoutError:
                    # Normal - no messages available
                    continue
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self.logger.error(
                        f"Error in Kafka consumer loop: {e}", exc_info=True
                    )
                    await asyncio.sleep(0.25)  # Brief pause before continuing

        except asyncio.CancelledError:
            self.logger.info("Kafka consumer cancelled")
        except Exception as e:
            self.logger.error(f"Kafka consumer error: {e}", exc_info=True)
            raise

    async def _worker_processor(self, worker_index: int) -> None:
        """Worker processor that handles tasks from the queue"""
        worker_id = self.worker_ids[worker_index]
        self.logger.info(f"Worker {worker_id} started")

        while not self._shutdown_event.is_set():
            try:
                # Get task from queue with timeout
                task_data = await asyncio.wait_for(
                    self._processing_queue.get(), timeout=1.0
                )

                # Process the task
                await self._process_task(task_data, worker_id)

            except asyncio.TimeoutError:
                # No tasks available, continue loop
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Worker {worker_id} error: {e}", exc_info=True)

    async def _process_task(self, task_data: Dict[str, Any], worker_id: str) -> None:
        """Process a single task with the specified worker"""
        task_id = task_data["task_id"]
        trace_id = task_data["trace_id"]
        original_message = task_data["original_message"]

        try:
            # Acquire semaphore to limit concurrent processing
            async with self._worker_semaphore:
                self.logger.info(
                    f"[{trace_id}] Processing task {task_id} with worker {worker_id}"
                )

                # Send PROCESSING status (2) immediately
                await self._send_status_update(
                    task_id=task_id,
                    trace_id=trace_id,
                    status=TaskStatus.PROCESSING,
                    worker_id=worker_id,
                )

                # Execute the actual task
                result = await self._execute_llm_task(task_data)

                # Send final status (3 for success, 4 for failure)
                if result.get("success", False):
                    await self._send_result(
                        task_id=task_id,
                        trace_id=trace_id,
                        status=TaskStatus.SUCCESS,
                        result_data=result.get("result"),
                        worker_id=worker_id,
                    )
                else:
                    await self._send_result(
                        task_id=task_id,
                        trace_id=trace_id,
                        status=TaskStatus.FAILED,
                        result_data={
                            "error_message": result.get("error", "Unknown error")
                        },
                        worker_id=worker_id,
                    )

                # Commit the original message after successful processing
                try:
                    await self.queue.commit(original_message)
                    self.logger.debug(
                        f"[{trace_id}] Message committed for task {task_id}"
                    )
                except Exception as e:
                    self.logger.error(
                        f"[{trace_id}] Failed to commit message for task {task_id}: {e}"
                    )

        except Exception as e:
            self.logger.error(
                f"[{trace_id}] Error processing task {task_id}: {e}", exc_info=True
            )

            try:
                # Send failure status
                await self._send_result(
                    task_id=task_id,
                    trace_id=trace_id,
                    status=TaskStatus.FAILED,
                    result_data={"error_message": str(e)},
                    worker_id=worker_id,
                )
            except Exception as send_error:
                self.logger.error(
                    f"[{trace_id}] Failed to send error result: {send_error}"
                )

            # Still try to commit the message to avoid infinite loop
            try:
                await self.queue.commit(original_message)
            except Exception as commit_error:
                self.logger.error(
                    f"[{trace_id}] Failed to commit failed task: {commit_error}"
                )
        finally:
            # Remove task from deduplication queue after processing (success or failure)
            try:
                dedup_queue = self.container.get_task_deduplication_queue()
                if dedup_queue:
                    dedup_queue.remove_task(task_id)
                    self.logger.debug(
                        f"[{trace_id}] Task {task_id} removed from deduplication queue"
                    )
            except Exception as e:
                self.logger.error(
                    f"[{trace_id}] Failed to remove task {task_id} from deduplication queue: {e}"
                )

    async def _execute_llm_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the actual LLM processing task"""
        task_id = task_data["task_id"]
        storage_path = task_data["storage_path"]
        trace_id = task_data["trace_id"]
        prompt_id = task_data["prompt_id"]

        start_time = time.perf_counter()

        try:
            if not storage_path:
                return {"success": False, "error": "No storage_path provided in task"}

            # Load file from storage
            self.logger.debug(f"[{trace_id}] Loading file from storage: {storage_path}")
            file_data = await self.storage.get_file(storage_path)
            filename = storage_path.split("/")[-1]

            # Upload to LLM
            self.logger.debug(f"[{trace_id}] Uploading file to LLM: {filename}")
            file_id = await self._upload_file_with_retry(file_data, filename, trace_id)

            # Get prompt
            prompt_service = PromptService()
            prompt = prompt_service.get_prompt_by_id(prompt_id)
            if not prompt:
                return {
                    "success": False,
                    "error": f"Prompt with id {prompt_id} not found",
                }

            # Process with LLM
            self.logger.info(f"[{trace_id}] Processing with LLM...")
            response = await self.llm.chat(
                prompt=prompt, file_ids=[file_id] if file_id else []
            )

            # Clean up uploaded file
            if file_id:
                try:
                    await self.llm.delete_file(file_id)
                    self.logger.debug(f"[{trace_id}] File {file_id} deleted from LLM")
                except Exception as e:
                    self.logger.warning(
                        f"[{trace_id}] Failed to delete file {file_id}: {e}"
                    )

            # Check response format
            response_content = response.get("response", "")

            # Try to parse as JSON if it looks like JSON
            if response_content and response_content.strip().startswith("{"):
                import json as json_lib

                try:
                    parsed_result = json_lib.loads(response_content)
                    status_in_response = parsed_result.get(
                        "Статус", parsed_result.get("status", "")
                    )

                    if status_in_response in [
                        "Успешно",
                        "Success",
                        "success",
                        "SUCCESS",
                    ]:
                        return {"success": True, "result": parsed_result}
                    else:
                        return {
                            "success": False,
                            "error": f"LLM returned invalid response format or error status: {status_in_response}",
                        }
                except json_lib.JSONDecodeError:
                    return {
                        "success": False,
                        "error": f"LLM response is not valid JSON: {response_content[:200]}...",
                    }
            else:
                # If not JSON, consider it as raw response
                return {"success": True, "result": {"raw_response": response_content}}

        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            processing_time = (time.perf_counter() - start_time) * 1000
            self.logger.info(
                f"[{trace_id}] Task {task_id} processed in {processing_time:.2f}ms"
            )

    async def _upload_file_with_retry(
        self, file_data: Any, filename: str, trace_id: str
    ) -> Optional[str]:
        """Upload file with retry logic and connector restart on timeout"""
        max_retries = 2  # Try original upload once + 1 retry after connector restart
        retry_count = 0

        while retry_count <= max_retries:
            try:
                file_id = await self.llm.upload_file(
                    file_data=file_data, filename=filename, timeout=30.0
                )
                return file_id
            except Exception as e:
                error_str = str(e)
                # Check if this is a timeout error
                if "timeout" in error_str.lower() or "TimeoutError" in str(type(e)):
                    self.logger.error(f"[{trace_id}] File upload timeout detected: {e}")

                    if retry_count < max_retries:
                        self.logger.info(
                            f"[{trace_id}] Restarting LLM connector due to timeout and retrying..."
                        )
                        await self._restart_llm_connector()
                        retry_count += 1
                    else:
                        raise  # Re-raise the exception if we've exhausted retries
                else:
                    # If it's not a timeout error, re-raise immediately
                    raise

    async def _restart_llm_connector(self) -> None:
        """Restart the LLM connector through the interface"""
        try:
            self.logger.info("Restarting LLM connector...")

            # Shutdown the current LLM interface
            if self.llm:
                await self.llm.shutdown()

            # Get the original connector configuration from the container
            # We need to reinitialize the LLM interface
            llm_interface = self.container.get_llm("GigaChat")
            await llm_interface.initialize()

            # Update our reference
            self.llm = llm_interface

            self.logger.info("LLM connector restarted successfully")
        except Exception as e:
            self.logger.error(f"Failed to restart LLM connector: {e}")
            raise

    async def _send_status_update(
        self, task_id: str, trace_id: str, status: TaskStatus, worker_id: str
    ) -> None:
        """Send status update to Kafka"""
        try:
            await self.queue.publish(
                topic="tasks_llm",
                key=task_id,
                data={},  # Empty payload for status updates
                headers={
                    "status": status.value,
                    "trace_id": trace_id,
                    "worker_id": worker_id,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )
            self.logger.debug(
                f"[{trace_id}] Status {status.value} sent for task {task_id}"
            )
        except Exception as e:
            self.logger.error(f"[{trace_id}] Failed to send status update: {e}")

    async def _send_result(
        self,
        task_id: str,
        trace_id: str,
        status: TaskStatus,
        result_data: Dict[str, Any],
        worker_id: str,
    ) -> None:
        """Send final result to Kafka"""
        try:
            # Prepare the payload based on status
            if status == TaskStatus.SUCCESS:
                payload = {
                    "result": json.dumps(result_data, ensure_ascii=False)
                    if isinstance(result_data, dict)
                    else result_data
                }
            else:
                payload = {
                    "error_message": result_data.get("error_message", "Unknown error")
                    if isinstance(result_data, dict)
                    else str(result_data)
                }

            await self.queue.publish(
                topic="tasks_llm",
                key=task_id,
                data=payload,
                headers={
                    "status": status.value,
                    "trace_id": trace_id,
                    "worker_id": worker_id,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )
            self.logger.info(
                f"[{trace_id}] Result sent for task {task_id}, status: {status.value}"
            )
        except Exception as e:
            self.logger.error(f"[{trace_id}] Failed to send result: {e}")

    async def _start_token_refresh_task(self) -> None:
        """Start background task to refresh GigaChat token every 5-15 minutes"""
        self._token_refresh_task = asyncio.create_task(self._token_refresh_worker())

    async def _token_refresh_worker(self) -> None:
        """Background worker to refresh token periodically"""
        while not self._shutdown_event.is_set():
            try:
                # Wait for a random time between 5-15 minutes (300-900 seconds)
                wait_time = random.randint(300, 900)  # 5-15 minutes
                self.logger.info(f"Token refresh scheduled in {wait_time} seconds")

                # Wait for the specified time or until shutdown event
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(), timeout=wait_time
                    )
                    # If we reach here, shutdown was requested
                    break
                except asyncio.TimeoutError:
                    # Timeout means it's time to refresh the token
                    pass

                # Refresh the token by calling the connector's refresh method
                if self.llm and hasattr(self.llm, "worker"):
                    try:
                        # Access the underlying connector and refresh its token
                        connector = self.llm.worker
                        if hasattr(connector, "_refresh_access_token"):
                            await connector._refresh_access_token()
                            self.logger.info("GigaChat token refreshed successfully")
                        else:
                            self.logger.warning(
                                "Connector does not have _refresh_access_token method"
                            )
                    except Exception as e:
                        self.logger.error(f"Failed to refresh GigaChat token: {e}")

            except asyncio.CancelledError:
                self.logger.info("Token refresh task cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error in token refresh worker: {e}")
                # Continue the loop despite errors

    async def shutdown(self) -> None:
        """Graceful shutdown"""
        self._logger.info("Shutting down LLM Service...")

        # Signal shutdown
        self.get_shutdown_event().set()

        # Shutdown HTTP server first
        if hasattr(self, '_http_server') and self._http_server:
            self._http_server.should_exit = True
            self._logger.info("HTTP server shutdown initiated")

        # Wait a bit for graceful shutdown
        await asyncio.sleep(0.1)

        # Cancel all active tasks
        for task in self._active_tasks.values():
            task.cancel()

        # Wait for worker tasks to complete
        for task in self._worker_tasks:
            task.cancel()

        # Cancel token refresh task
        if self._token_refresh_task:
            self._token_refresh_task.cancel()
            try:
                await self._token_refresh_task
            except asyncio.CancelledError:
                pass

        # Shutdown interfaces
        if self.llm:
            try:
                await self.llm.shutdown()
                self._logger.info("LLM interface shutdown complete")
            except Exception as e:
                self._logger.error(f"Error shutting down LLM: {e}")

        if self.container:
            await self.container.shutdown_all()
            self._logger.info("Service container shutdown complete")

        self._logger.info("LLM Service shutdown complete")

    async def _http_health_callback(self) -> dict:
        """Callback для HTTP health-check."""
        if self.get_shutdown_event().is_set():
            return {"status": "shutting_down"}
        if not self.container or not self.llm or not self.queue:
            return {"status": "degraded"}
        return {"status": "ok"}
    
    async def _http_status_callback(self) -> dict:
        """Callback для HTTP status."""
        if not self.container:
            return {"error": "not_bootstrapped"}
        
        queue_size = self._processing_queue.qsize()
        active_workers = self.max_workers - self._worker_semaphore._value
        dedup_queue = self.container.get_task_deduplication_queue()
        dedup_size = len(dedup_queue) if dedup_queue else 0
        
        return {
            "service": "LLMService",
            "workers": {
                "max": self.max_workers,
                "active": active_workers,
            },
            "queues": {
                "processing": queue_size,
                "deduplication": dedup_size,
            },
            "bootstrap_success": True,
            "shutdown_in_progress": self._shutdown_event.is_set(),
        }