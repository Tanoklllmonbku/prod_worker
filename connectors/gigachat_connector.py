"""
GigaChat API Connector - Pure async implementation for no-GIL
OAuth flow как в официальном SDK - ПОЛНЫЙ КОД
"""

import asyncio
import json
import uuid
from typing import Optional, List, Dict, AsyncIterator, Any
from datetime import datetime, timedelta, timezone

import httpx

from core.base_class.base_connectors import LLMConnector


class GigaChatConnector(LLMConnector):
    """GigaChat REST API wrapper using httpx (Pure async implementation)"""

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
        base_url: str,
        api_version: str,
        oauth_url: str,
        credentials: Optional[str] = None,
        model: str = "GigaChat-Max",
        scope: str = "GIGACHAT_API_B2B",
        verify_ssl: bool = False,
        timeout: float = 30.0,
        max_connections: int = 10,
    ):
        super().__init__(name="gigachat")
        self.logger = get_logger()
        self.model = model
        self.scope = scope
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.max_connections = max_connections

        # Используем переданные URL из настроек
        self.BASE_URL = base_url.rstrip("/")
        self.API_VERSION = api_version
        self.OAUTH_URL = oauth_url.rstrip("/")

        # HTTP client
        self._client: Optional[httpx.AsyncClient] = None
        self._health_status = False

        # OAuth tokens
        self.credentials = credentials
        self.access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

        # Load from keyring
        self._load_from_keyring()

    def _load_from_keyring(self) -> None:
        """Load credentials and access_token from keyring"""
        # Реализация остаётся, но не используется, если access_token передаётся напрямую
        # или если используется постоянный access_token
        pass

    def _save_credentials(self, creds: str) -> None:
        """Save credentials to keyring"""
        pass

    def _save_access_token(self, token: str) -> None:
        """Save access_token to keyring"""
        pass

    async def _refresh_access_token(self) -> None:
        """Получить access_token по credentials"""
        if not self.credentials:
            raise ValueError("No credentials available for OAuth")

        headers = {
            "Authorization": f"Basic {self.credentials}",
            "RqUID": str(uuid.uuid4()),
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        data = {"scope": self.scope}

        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=10.0) as client:
            resp = await client.post(self.OAUTH_URL, headers=headers, data=data)
            resp.raise_for_status()

        body = resp.json()
        self.access_token = body["access_token"]
        self._token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=29)
        self._save_access_token(self.access_token)
        self.logger.info("✅ Access token refreshed")

    async def _ensure_token(self) -> None:
        """Обновить токен если просрочен"""
        if (
            not self.access_token
            or not self._token_expires_at
            or datetime.now(timezone.utc) >= self._token_expires_at
        ):
            await self._refresh_access_token()

    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authorization headers"""
        if not self.access_token:
            raise ValueError("Access token not available")
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }

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
            if not self.credentials and not self.access_token:
                raise ValueError("No credentials or access_token provided")

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

            # Получаем токен при инициализации (если используем OAuth flow)
            await self._ensure_token()
            self._set_health(True)
            self.logger.info(
                f"GigaChat initialized with model {self.model}, scope {self.scope}"
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

    async def upload_file(
        self,
        file_data: Any,
        filename: Optional[str] = None,
        mime_type: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Optional[str]:
        if not self._client:
            raise RuntimeError("GigaChat client not initialized")

        await self._ensure_token()
        try:
            timeout = timeout or self.timeout

            if hasattr(file_data, "read"):
                if not filename and hasattr(file_data, "name"):
                    filename = file_data.name
                    if "/" in filename:
                        filename = filename.split("/")[-1]
                    if "\\" in filename:
                        filename = filename.split("\\")[-1]
                file_data = file_data.read()

            if not filename:
                filename = f"file_{uuid.uuid4().hex[:8]}"

            if mime_type is None:
                mime_type = self._get_mime_type(filename)
                self.logger.debug(
                    f"Auto-detected MIME type: {mime_type} for {filename}"
                )

            files = {"file": (filename, file_data, mime_type)}
            data = {"purpose": "general"}

            self.logger.debug(f"Uploading file: {filename} ({len(file_data)} bytes)")

            response = await asyncio.wait_for(
                self._client.post(
                    f"/{self.API_VERSION}/files",
                    files=files,
                    data=data,
                    headers=self._get_auth_headers(),
                ),
                timeout=timeout,
            )
            if response.status_code >= 400:
                self.logger.error("Upload response body: %s", response.text)
            response.raise_for_status()

            result = response.json()
            file_id = result.get("id")
            self.logger.info(f"✅ File uploaded successfully: {file_id}")
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
        if not self._client:
            raise RuntimeError("GigaChat client not initialized")

        timeout = timeout or self.timeout

        messages: List[Dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        user_message: Dict[str, Any] = {"role": "user", "content": prompt}
        if file_ids:
            # attachments: [[file_id1], [file_id2], ...]
            user_message["attachments"] = file_ids
        messages.append(user_message)

        payload = self._build_chat_payload(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
        )

        headers = self._get_auth_headers()
        headers["Content-Type"] = "application/json"

        self.logger.debug(
            "Chat payload:\n%s",
            json.dumps(payload, ensure_ascii=False, indent=2),
        )

        if stream:
            return self._chat_stream(payload, headers, timeout)
        return await self._chat_complete(payload, headers, timeout)

    async def _chat_complete(
        self,
        payload: Dict[str, Any],
        headers: Dict[str, str],
        timeout: float,
    ) -> Dict[str, Any]:
        import json as json_lib

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
                self.logger.error(
                    "Chat response status=%d body: %s",
                    response.status_code,
                    response.text,
                )
                if response.status_code == 400:
                    self.logger.error("400 Bad Request - Invalid JSON syntax detected")
                    self.logger.error("Payload was:\n%s", payload_json)

            response.raise_for_status()

            result = response.json()
            message_content = result["choices"][0]["message"]["content"]
            usage = result.get("usage", {})

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

    async def _chat_stream(
        self,
        payload: Dict[str, Any],
        headers: Dict[str, str],
        timeout: float,
    ) -> AsyncIterator[str]:
        async with self._client.stream(
            "POST",
            f"/{self.API_VERSION}/chat/completions",
            json=payload,
            headers=headers,
            timeout=timeout,
        ) as response:
            if response.status_code >= 400:
                text = await response.aread()
                self.logger.error(
                    "Chat stream error body: %s", text.decode("utf-8", "ignore")
                )
            response.raise_for_status()

            async for line in response.aiter_lines():
                if not line:
                    continue
                if line.startswith("data: "):
                    data_str = line[6:]
                else:
                    data_str = line
                if data_str.strip() == "[DONE]":
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
        await self._ensure_token()
        if not self._client:
            raise RuntimeError("GigaChat client not initialized")

        response = await asyncio.wait_for(
            self._client.get(
                f"/{self.API_VERSION}/files/{file_id}",
                headers=self._get_auth_headers(),
            ),
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            self.logger.error("Get file info: %s", response.text)
        response.raise_for_status()

        file_info = response.json()
        return {
            "file_id": file_info.get("id"),
            "filename": file_info.get("filename"),
            "size": file_info.get("size"),
            "created_at": file_info.get("created_at"),
            "purpose": file_info.get("purpose"),
            "status": "uploaded",
        }

    async def list_files(self) -> List[Dict]:
        await self._ensure_token()
        if not self._client:
            raise RuntimeError("GigaChat client not initialized")

        response = await asyncio.wait_for(
            self._client.get(
                f"/{self.API_VERSION}/files",
                headers=self._get_auth_headers(),
            ),
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            self.logger.error("List files: %s", response.text)
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

    async def delete_file(self, file_id: str, timeout: Optional[float] = None) -> bool:
        await self._ensure_token()
        if not self._client:
            raise RuntimeError("GigaChat client not initialized")

        # Use provided timeout or default to self.timeout
        effective_timeout = timeout if timeout is not None else self.timeout

        response = await asyncio.wait_for(
            self._client.post(
                f"/{self.API_VERSION}/files/{file_id}/delete",
                headers=self._get_auth_headers(),
            ),
            timeout=effective_timeout,
        )
        if response.status_code >= 400:
            self.logger.error("Delete file: %s", response.text)
        response.raise_for_status()

        self.logger.info(f"File deleted: {file_id}")
        return True

    async def delete_files_concurrent(self, file_ids: List[str]) -> Dict:
        self.logger.info(f"Deleting {len(file_ids)} files concurrently")
        tasks = [self.delete_file(fid) for fid in file_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successful = sum(1 for r in results if r is True)
        failed = sum(1 for r in results if isinstance(r, Exception))
        self.logger.info(
            f"Deleted {successful}/{len(file_ids)} files ({failed} failed)"
        )

        return {
            "total": len(file_ids),
            "successful": successful,
            "failed": failed,
        }

    async def health_check(self) -> bool:
        if not self._client:
            return False

        try:
            await self._ensure_token()
            response = await asyncio.wait_for(
                self._client.get(
                    f"/{self.API_VERSION}/models",
                    headers=self._get_auth_headers(),
                ),
                timeout=5.0,
            )
            if response.status_code >= 400:
                self.logger.error("Health check: %s", response.text)
            response.raise_for_status()

            self._health_status = True
            self.logger.debug("Health check passed")
            return True
        except Exception as e:
            self.logger.warning(f"Health check failed: {e}")
            self._health_status = False
            return False

    def is_healthy(self) -> bool:
        return self._health_status

    async def batch_chat(
        self,
        payload: dict[str, Optional[List[str]]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> tuple[List[Dict]]:
        timeout = timeout or self.timeout
        tasks = [
            self.chat(
                prompt=prompt,
                file_ids=file_id,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                stream=False,
            )
            for prompt, file_id in payload.items()
        ]
        self.logger.info(f"Batch chat: {len(payload)} requests")
        return await asyncio.gather(*tasks, return_exceptions=False)

    def _build_chat_payload(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        payload = {
            "function_call": "auto",
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        return payload