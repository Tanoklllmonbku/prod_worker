"""
GigaChat API Connector for Python 3.14 no-GIL
Uses httpx for async HTTP, no SDK dependency
Optimized for concurrent file operations and chat
Auth key stored securely in keyring
"""
import asyncio
import logging
import json
import uuid
import keyring
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, List, Dict, AsyncIterator, Any
from datetime import datetime, timedelta

import httpx

from core.base_class.connectors import LLMConnector


class GigaChatConnector(LLMConnector):
    """GigaChat REST API wrapper using httpx (no SDK)"""

    # Базовые эндпоинты GigaChat API из документации
    BASE_URL = "https://gigachat.devices.sberbank.ru"
    API_VERSION = "api/v1"

    # OAuth для получения токена доступа
    OAUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"

    # Model constants
    MODEL_GIGA_CHAT_MAX = "GigaChat-Max"
    MODEL_GIGA_CHAT_PRO = "GigaChat-Pro"
    MODEL_GIGA_CHAT = "GigaChat"

    # Scope constants
    SCOPE_B2B = "GIGACHAT_API_B2B"
    SCOPE_PERS = "GIGACHAT_API_PERS"

    # Keyring storage
    KEYRING_SERVICE = "gigachat"
    KEYRING_USERNAME = "auth_key"

    # MIME type mapping
    MIME_TYPES = {
        ".pdf": "application/pdf",
        ".txt": "text/plain",
        ".doc": "application/msword",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xls": "application/vnd.ms-excel",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".ppt": "application/vnd.ms-powerpoint",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
        ".bmp": "image/bmp",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".m4a": "audio/mp4",
        ".flac": "audio/flac",
        ".aac": "audio/aac",
        ".mp4": "video/mp4",
        ".avi": "video/x-msvideo",
        ".mkv": "video/x-matroska",
        ".mov": "video/quicktime",
        ".wmv": "video/x-ms-wmv",
        ".flv": "video/x-flv",
        ".zip": "application/zip",
        ".tar": "application/x-tar",
        ".gz": "application/gzip",
        ".7z": "application/x-7z-compressed",
        ".rar": "application/x-rar-compressed",
        ".json": "application/json",
        ".xml": "application/xml",
        ".html": "text/html",
        ".css": "text/css",
        ".sql": "text/sql",
        ".py": "text/plain",
        ".java": "text/plain",
        ".cpp": "text/plain",
        ".go": "text/plain",
        ".rs": "text/plain",
    }

    def __init__(
        self,
        get_logger,
        executor: Optional[ThreadPoolExecutor] = None,
        auth_key: Optional[str] = None,
        access_token: Optional[str] = None,
        model: str = MODEL_GIGA_CHAT_MAX,
        scope: str = SCOPE_B2B,
        verify_ssl: bool = False,
        timeout: float = 30.0,
        max_connections: int = 100,
    ):
        super().__init__(name="gigachat")
        self.logger = get_logger()
        self.model = model
        self.scope = scope
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.max_connections = max_connections
        self.executor = executor or ThreadPoolExecutor(max_workers=10)

        # Token management
        self._token_expires_at: Optional[datetime] = None
        self._token_lock = asyncio.Lock()

        # HTTP client (created on initialize)
        self._client: Optional[httpx.AsyncClient] = None

        # Auth key handling
        if auth_key:
            # Если передан явно — сохраняем в keyring
            self.auth_key = auth_key
            self._save_auth_key(auth_key)
        else:
            # Иначе читаем из keyring
            self.auth_key = self._load_auth_key()

        self.access_token = access_token

    def _save_auth_key(self, auth_key: str) -> None:
        """Save auth_key to keyring"""
        try:
            keyring.set_password(self.KEYRING_SERVICE, self.KEYRING_USERNAME, auth_key)
            self.logger.debug("Auth key saved to keyring")
        except Exception as e:
            self.logger.warning(f"Failed to save auth_key to keyring: {e}")

    def _load_auth_key(self) -> Optional[str]:
        """Load auth_key from keyring"""
        try:
            auth_key = keyring.get_password(self.KEYRING_SERVICE, self.KEYRING_USERNAME)
            if auth_key:
                self.logger.debug("Auth key loaded from keyring")
                return auth_key
        except Exception as e:
            self.logger.warning(f"Failed to load auth_key from keyring: {e}")
        return None

    def _get_mime_type(self, filename: str) -> str:
        """Get MIME type from filename"""
        filename_lower = filename.lower()
        for ext, mime_type in self.MIME_TYPES.items():
            if filename_lower.endswith(ext):
                return mime_type
        return "application/octet-stream"

    async def initialize(self) -> None:
        """Initialize async HTTP client"""
        try:
            limits = httpx.Limits(
                max_connections=self.max_connections,
                max_keepalive_connections=self.max_connections // 2,
            )
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                timeout=self.timeout,
                verify=self.verify_ssl,
                limits=limits,
            )

            # Получаем access_token, если не передан напрямую
            if not self.access_token and self.auth_key:
                await self._refresh_access_token()

            self._set_health(True)
            self.logger.info(
                f"GigaChat initialized with model {self.model}, "
                f"scope {self.scope}"
            )
        except Exception as e:
            self.logger.error(f"Failed to initialize GigaChat: {e}")
            self._set_health(False)
            raise

    async def shutdown(self) -> None:
        """Shutdown async HTTP client"""
        if self._client:
            try:
                await self._client.aclose()
                self.logger.info("GigaChat HTTP client closed")
            except Exception as e:
                self.logger.error(f"Error closing HTTP client: {e}")

    async def _refresh_access_token(self) -> None:
        """Refresh access token using OAuth 2.0"""
        if not self.auth_key:
            raise ValueError("auth_key required for token refresh")

        async with self._token_lock:
            # Double-check pattern
            if (
                self._token_expires_at
                and datetime.now() < self._token_expires_at - timedelta(minutes=1)
            ):
                return

            try:
                rq_uid = str(uuid.uuid4())
                headers = {
                    "Authorization": f"Basic {self.auth_key}",
                    "RqUID": rq_uid,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                }

                payload = f"scope={self.scope}"

                async with httpx.AsyncClient(verify=self.verify_ssl, timeout=self.timeout) as client:
                    response = await client.post(
                        self.OAUTH_URL,
                        headers=headers,
                        content=payload,
                    )

                if response.status_code >= 400:
                    self.logger.error("Token response status=%d body: %s", response.status_code, response.text)
                response.raise_for_status()

                token_data = response.json()
                self.access_token = token_data["access_token"]
                expires_in = token_data.get("expires_in", 1800)
                self._token_expires_at = datetime.now() + timedelta(seconds=expires_in)

                self.logger.info(f"Access token refreshed, expires in {expires_in}s")
            except Exception as e:
                self.logger.error(f"Failed to refresh access token: {e}")
                raise

    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authorization headers"""
        if not self.access_token:
            raise ValueError("Access token not available")
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }

    async def _ensure_valid_token(self) -> None:
        """Ensure access token is valid, refresh if needed"""
        if not self.access_token:
            raise ValueError("No access token available")

        if self._token_expires_at and datetime.now() >= self._token_expires_at:
            if self.auth_key:
                await self._refresh_access_token()
            else:
                raise ValueError("Token expired and no auth_key for refresh")

    async def upload_file(
        self,
        file_data: Any,
        filename: Optional[str] = None,
        mime_type: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Optional[str]:
        """
        Upload file to GigaChat storage
        Returns file_id for use in chat requests

        Args:
            file_data: File bytes OR file-like object (with read() method)
            filename: Filename for storage (required if passing bytes, auto-detected from file object)
            mime_type: MIME type (auto-detected if not provided)
            timeout: Request timeout in seconds

        Supported MIME types:
        - Documents: PDF, TXT, DOC, DOCX, XLS, XLSX, PPT, PPTX, ODT, ODS, ODP
        - Images: JPG, PNG, GIF, WebP, SVG, BMP
        - Audio: MP3, WAV, M4A, FLAC, AAC
        - Video: MP4, AVI, MKV, MOV, WMV, FLV
        - Archives: ZIP, TAR, GZ, 7Z, RAR
        - Code/Markup: Python, Java, C++, Go, Rust, JSON, XML, HTML, CSS, SQL
        """
        if not self._client:
            raise RuntimeError("GigaChat client not initialized")

        try:
            await self._ensure_valid_token()

            timeout = timeout or self.timeout

            # Handle file-like objects (BufferedReader, etc.)
            if hasattr(file_data, 'read'):
                # Try to get filename from file object if not provided
                if not filename and hasattr(file_data, 'name'):
                    filename = file_data.name
                    # Extract just the filename if it's a full path
                    if '/' in filename:
                        filename = filename.split('/')[-1]
                    if '\\' in filename:
                        filename = filename.split('\\')[-1]

                file_data = file_data.read()

            # Filename is required at this point
            if not filename:
                filename = f"file_{uuid.uuid4().hex[:8]}"

            # Auto-detect MIME type if not provided
            if mime_type is None:
                mime_type = self._get_mime_type(filename)
                self.logger.debug(f"Auto-detected MIME type: {mime_type} for {filename}")

            headers = self._get_auth_headers()
            files = {
                "file": (filename, file_data, mime_type),
            }
            data = {"purpose": "general"}

            self.logger.debug(
                f"Uploading file: {filename} ({len(file_data)} bytes, MIME: {mime_type})"
            )

            response = await asyncio.wait_for(
                self._client.post(
                    f"/{self.API_VERSION}/files",
                    headers=headers,
                    files=files,
                    data=data,
                ),
                timeout=timeout,
            )
            if response.status_code >= 400:
                self.logger.error("Upload response body: %s", response.text)
            response.raise_for_status()

            result = response.json()
            file_id = result.get("id")

            self.logger.info(f"File uploaded successfully: {file_id}")
            return file_id

        except asyncio.TimeoutError:
            self.logger.error(f"Upload timeout after {timeout}s")
            raise TimeoutError(f"Upload exceeded {timeout} seconds")
        except Exception as e:
            self.logger.error(f"Error uploading file: {e}", exc_info=True)
            raise

    async def upload_files_concurrent(
        self,
        files: List[Dict[str, Any]],
        timeout: Optional[float] = None,
    ) -> List[str]:
        """
        Upload multiple files concurrently (leverages no-GIL)
        Each dict should have: {'data': bytes, 'filename': str, 'mime_type': str}
        """
        timeout = timeout or self.timeout

        tasks = [
            self.upload_file(
                file_data=f["data"],
                filename=f.get("filename"),
                mime_type=f.get("mime_type", "application/octet-stream"),
                timeout=timeout,
            )
            for f in files
        ]

        self.logger.info(f"Uploading {len(files)} files concurrently")
        results = await asyncio.gather(*tasks, return_exceptions=False)

        successfully_uploaded = [r for r in results if r]
        self.logger.info(
            f"Successfully uploaded {len(successfully_uploaded)}/{len(files)} files"
        )
        return successfully_uploaded

    async def chat(
        self,
        prompt: str,
        file_ids: Optional[List[str]] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
        stream: bool = False,
    ) -> Any:
        """
        Chat with file attachments
        If stream=False -> returns Dict
        If stream=True  -> returns AsyncIterator[str]
        """
        if not self._client:
            raise RuntimeError("GigaChat client not initialized")

        await self._ensure_valid_token()

        timeout = timeout or self.timeout

        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        user_message = {"role": "user", "content": prompt}

        # attachments должен быть массивом идентификаторов файлов
        if file_ids:
            user_message["attachments"] = file_ids
            self.logger.debug(f"Adding {len(file_ids)} attachments to message")

        messages.append(user_message)

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens

        headers = self._get_auth_headers()
        headers["Content-Type"] = "application/json"

        self.logger.debug(
            f"Chat request: model={self.model}, "
            f"files={len(file_ids or [])}, stream={stream}"
        )

        if stream:
            async def _gen() -> AsyncIterator[str]:
                async for chunk in self._chat_stream(
                    payload, headers, timeout, len(file_ids or [])
                ):
                    yield chunk

            return _gen()
        else:
            return await self._chat_complete(
                payload, headers, timeout, len(file_ids or [])
            )

    async def _chat_complete(
            self,
            payload: Dict,
            headers: Dict,
            timeout: float,
            num_files: int,
    ) -> Dict:
        """Non-streaming chat completion with detailed JSON logging"""
        import json as json_lib

        # Логируем точный JSON перед отправкой
        payload_json = json_lib.dumps(payload, ensure_ascii=False, indent=2)
        self.logger.debug(f"Chat request payload:\n{payload_json}")

        try:
            response = await asyncio.wait_for(
                self._client.post(
                    f"/{self.API_VERSION}/chat/completions",
                    json=payload,
                    headers=headers,
                ),
                timeout=timeout,
            )

            if response.status_code >= 400:
                self.logger.error("Chat response status=%d body: %s", response.status_code, response.text)

                # Дополнительная диагностика для 400
                if response.status_code == 400:
                    self.logger.error("400 Bad Request - Invalid JSON syntax detected")
                    self.logger.error("Payload was:\n%s", payload_json)

            response.raise_for_status()

            result = response.json()
            message_content = result["choices"][0]["message"]["content"]
            usage = result.get("usage", {})

            self.logger.info(
                f"Chat completed: "
                f"completion_tokens={usage.get('completion_tokens', 0)}, "
                f"files={num_files}"
            )

            return {
                "response": message_content,
                "tokens_used": usage.get("completion_tokens", 0),
                "tokens_total": usage.get("total_tokens", 0),
                "model": self.model,
                "usage": usage,
            }

        except asyncio.TimeoutError:
            self.logger.error(f"Chat timeout after {timeout}s")
            raise TimeoutError(f"Chat exceeded {timeout} seconds")
        except Exception as e:
            self.logger.error(f"Error in chat: {e}", exc_info=True)
            raise

    async def _chat_stream(
        self,
        payload: Dict,
        headers: Dict,
        timeout: float,
        num_files: int,
    ) -> AsyncIterator[str]:
        """Streaming chat completion with Server-Sent Events"""
        async with self._client.stream(
            "POST",
            f"/{self.API_VERSION}/chat/completions",
            json=payload,
            headers=headers,
            timeout=timeout,
        ) as response:
            if response.status_code >= 400:
                text = await response.aread()
                self.logger.error("Chat stream error body: %s", text.decode("utf-8", "ignore"))
            response.raise_for_status()

            self.logger.debug(f"Chat stream started (files={num_files})")

            async for line in response.aiter_lines():
                if not line:
                    continue
                if line.startswith("data: "):
                    data_str = line[6:]
                else:
                    data_str = line

                if data_str.strip() == "[DONE]":
                    self.logger.debug("Chat stream completed")
                    break

                try:
                    data = json.loads(data_str)
                    choices = data.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {}) or choices[0].get("message", {})
                    content = delta.get("content", "")
                    if content:
                        yield content
                except json.JSONDecodeError:
                    self.logger.warning(f"Failed to parse stream line: {data_str}")

    async def get_file_info(self, file_id: str) -> Dict:
        """Get file information from storage"""
        if not self._client:
            raise RuntimeError("GigaChat client not initialized")

        try:
            await self._ensure_valid_token()

            headers = self._get_auth_headers()

            response = await asyncio.wait_for(
                self._client.get(
                    f"/{self.API_VERSION}/files/{file_id}",
                    headers=headers,
                ),
                timeout=self.timeout,
            )
            if response.status_code >= 400:
                self.logger.error("Get file info body: %s", response.text)
            response.raise_for_status()

            file_info = response.json()
            self.logger.debug(f"Retrieved file info: {file_id}")

            return {
                "file_id": file_info.get("id"),
                "filename": file_info.get("filename"),
                "size": file_info.get("size"),
                "created_at": file_info.get("created_at"),
                "purpose": file_info.get("purpose"),
                "status": "uploaded",
            }

        except Exception as e:
            self.logger.error(f"Error getting file info: {e}")
            raise

    async def list_files(self) -> List[Dict]:
        """List all uploaded files"""
        if not self._client:
            raise RuntimeError("GigaChat client not initialized")

        try:
            await self._ensure_valid_token()

            headers = self._get_auth_headers()

            response = await asyncio.wait_for(
                self._client.get(
                    f"/{self.API_VERSION}/files",
                    headers=headers,
                ),
                timeout=self.timeout,
            )
            if response.status_code >= 400:
                self.logger.error("List files body: %s", response.text)
            response.raise_for_status()

            result = response.json()
            files = result.get("data", [])

            self.logger.info(f"Retrieved {len(files)} files from storage")

            return [
                {
                    "file_id": f.get("id"),
                    "filename": f.get("filename"),
                    "size": f.get("size"),
                    "created_at": f.get("created_at"),
                }
                for f in files
            ]

        except Exception as e:
            self.logger.error(f"Error listing files: {e}")
            raise

    async def delete_file(self, file_id: str) -> bool:
        """Delete file from storage"""
        if not self._client:
            raise RuntimeError("GigaChat client not initialized")

        try:
            await self._ensure_valid_token()

            headers = self._get_auth_headers()

            response = await asyncio.wait_for(
                self._client.post(
                    f"/{self.API_VERSION}/files/{file_id}/delete",
                    headers=headers,
                ),
                timeout=self.timeout,
            )
            if response.status_code >= 400:
                self.logger.error("Delete file body: %s", response.text)
            response.raise_for_status()

            self.logger.info(f"File deleted: {file_id}")
            return True

        except Exception as e:
            self.logger.error(f"Error deleting file: {e}")
            raise

    async def delete_files_concurrent(self, file_ids: List[str]) -> Dict:
        """Delete multiple files concurrently"""
        self.logger.info(f"Deleting {len(file_ids)} files concurrently")

        tasks = [self.delete_file(fid) for fid in file_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successful = sum(1 for r in results if r is True)
        failed = sum(1 for r in results if isinstance(r, Exception))

        self.logger.info(f"Deleted {successful}/{len(file_ids)} files ({failed} failed)")

        return {
            "total": len(file_ids),
            "successful": successful,
            "failed": failed,
        }

    async def health_check(self) -> bool:
        """Check GigaChat API connectivity"""
        if not self._client:
            return False

        try:
            await self._ensure_valid_token()

            headers = self._get_auth_headers()
            response = await asyncio.wait_for(
                self._client.get(
                    f"/{self.API_VERSION}/models",
                    headers=headers,
                ),
                timeout=5.0,
            )
            if response.status_code >= 400:
                self.logger.error("Health check body: %s", response.text)
            response.raise_for_status()

            self._health_status = True
            self.logger.debug("Health check passed")
            return True

        except Exception as e:
            self.logger.warning(f"Health check failed: {e}")
            self._health_status = False
            return False

    def is_healthy(self) -> bool:
        """Get health status (non-blocking)"""
        return self._health_status

    async def batch_chat(
        self,
        prompts: List[str],
        system_prompt: Optional[str] = None,
        file_ids: Optional[List[str]] = None,
        temperature: float = 0.1,
        timeout: Optional[float] = None,
    ) -> List[Dict]:
        """
        Process multiple chat requests concurrently (no-GIL optimization)
        Returns list of responses in order
        """
        timeout = timeout or self.timeout

        tasks = [
            self.chat(
                prompt=prompt,
                file_ids=file_ids,
                system_prompt=system_prompt,
                temperature=temperature,
                timeout=timeout,
                stream=False,
            )
            for prompt in prompts
        ]

        self.logger.info(f"Processing {len(prompts)} chat requests concurrently")
        results = await asyncio.gather(*tasks, return_exceptions=False)

        self.logger.info(f"Batch chat completed: {len(results)} responses")
        return results