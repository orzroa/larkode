"""Codex App Server 的异步 stdio JSON-RPC 客户端。"""

import asyncio
import json
import os
from typing import Any, AsyncIterator, Dict, Optional

try:
    from src.logging_utils import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class CodexAppServerError(RuntimeError):
    """App Server 启动、协议或请求失败。"""


class CodexAppServerClient:
    """管理一个 ``codex app-server`` 子进程及其 JSONL 协议。"""

    def __init__(self, cli_path: str = "codex", request_timeout: float = 30.0):
        self.cli_path = cli_path
        self.request_timeout = request_timeout
        self._process: Optional[asyncio.subprocess.Process] = None
        self._reader_task: Optional[asyncio.Task] = None
        self._stderr_task: Optional[asyncio.Task] = None
        self._pending: Dict[int, asyncio.Future] = {}
        self._events: asyncio.Queue = asyncio.Queue()
        self._server_requests: asyncio.Queue = asyncio.Queue()
        self._request_id = 0
        self._write_lock = asyncio.Lock()
        self._lifecycle_lock = asyncio.Lock()
        self._owner_loop: Optional[asyncio.AbstractEventLoop] = None
        self._generation = 0

    @property
    def running(self) -> bool:
        return self._process is not None and self._process.returncode is None

    @property
    def generation(self) -> int:
        """连接代次；每次启动新 App Server 都递增。"""
        return self._generation

    async def start(self) -> None:
        self._assert_owner_loop()
        async with self._lifecycle_lock:
            if self.running:
                return
            self._drain_runtime_queues()
            self._generation += 1
            generation = self._generation
            process = await asyncio.create_subprocess_exec(
                self.cli_path,
                "app-server",
                "--listen",
                "stdio://",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self._subprocess_env(),
                # App Server 的聚合 diff/命令输出可能显著超过 asyncio 默认 64 KiB。
                limit=8 * 1024 * 1024,
            )
            self._process = process
            self._reader_task = asyncio.create_task(
                self._read_stdout(process, generation)
            )
            self._stderr_task = asyncio.create_task(self._read_stderr(process))
            try:
                await self.request(
                    "initialize",
                    {"clientInfo": {"name": "larkode", "title": "Larkode", "version": "0.1.0"}},
                )
                await self.notify("initialized", {})
            except Exception:
                await self._stop_unlocked()
                raise

    async def stop(self) -> None:
        self._assert_owner_loop()
        async with self._lifecycle_lock:
            await self._stop_unlocked()

    async def _stop_unlocked(self) -> None:
        process = self._process
        self._process = None
        if process and process.returncode is None:
            try:
                process.terminate()
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
        tasks = [task for task in (self._reader_task, self._stderr_task) if task]
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._reader_task = None
        self._stderr_task = None
        self._fail_pending(CodexAppServerError("Codex App Server 已停止"))

    async def request(self, method: str, params: Optional[dict] = None) -> dict:
        self._assert_owner_loop()
        if not self.running:
            raise CodexAppServerError("Codex App Server 未运行")
        self._request_id += 1
        request_id = self._request_id
        future = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        try:
            await self._send({"method": method, "id": request_id, "params": params or {}})
            response = await asyncio.wait_for(future, timeout=self.request_timeout)
        except Exception:
            self._pending.pop(request_id, None)
            raise
        if "error" in response:
            error = response["error"]
            raise CodexAppServerError(f"{method} 失败: {error.get('message', error)}")
        return response.get("result", {})

    async def notify(self, method: str, params: Optional[dict] = None) -> None:
        self._assert_owner_loop()
        await self._send({"method": method, "params": params or {}})

    async def respond(
        self, request_id: int, result: Any, expected_generation: Optional[int] = None
    ) -> None:
        self._assert_owner_loop()
        await self._send(
            {"id": request_id, "result": result},
            expected_generation=expected_generation,
        )

    async def respond_error(
        self,
        request_id: int,
        code: int,
        message: str,
        expected_generation: Optional[int] = None,
    ) -> None:
        self._assert_owner_loop()
        await self._send(
            {"id": request_id, "error": {"code": code, "message": message}},
            expected_generation=expected_generation,
        )

    async def next_event(self, timeout: Optional[float] = None) -> dict:
        if timeout is None:
            return await self._events.get()
        return await asyncio.wait_for(self._events.get(), timeout=timeout)

    async def next_server_request(self, timeout: Optional[float] = None) -> dict:
        if timeout is None:
            return await self._server_requests.get()
        return await asyncio.wait_for(self._server_requests.get(), timeout=timeout)

    async def events(self) -> AsyncIterator[dict]:
        while self.running or not self._events.empty():
            yield await self.next_event()

    async def _send(
        self, message: dict, expected_generation: Optional[int] = None
    ) -> None:
        if expected_generation is not None and expected_generation != self._generation:
            raise CodexAppServerError("Codex App Server 连接已变更，拒绝发送旧请求响应")
        if not self._process or not self._process.stdin:
            raise CodexAppServerError("Codex App Server stdin 不可用")
        payload = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
        async with self._write_lock:
            if expected_generation is not None and expected_generation != self._generation:
                raise CodexAppServerError("Codex App Server 连接已变更，拒绝发送旧请求响应")
            self._process.stdin.write((payload + "\n").encode("utf-8"))
            await self._process.stdin.drain()

    async def _read_stdout(
        self,
        process: Optional[asyncio.subprocess.Process] = None,
        generation: Optional[int] = None,
    ) -> None:
        process = process or self._process
        generation = self._generation if generation is None else generation
        assert process
        assert process.stdout
        try:
            while True:
                raw = await process.stdout.readline()
                if not raw:
                    break
                try:
                    message = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    logger.warning("忽略 Codex App Server 非 JSON 输出")
                    continue
                message_id = message.get("id")
                if message_id in self._pending and ("result" in message or "error" in message):
                    future = self._pending.pop(message_id)
                    if not future.done():
                        future.set_result(message)
                elif message_id is not None and message.get("method"):
                    await self._server_requests.put({**message, "_generation": generation})
                elif message.get("method"):
                    await self._events.put(message)
        except (ValueError, asyncio.LimitOverrunError) as exc:
            logger.error(f"Codex App Server 输出帧过大或损坏: {exc}")
        finally:
            if generation == self._generation:
                error = CodexAppServerError("Codex App Server 连接已关闭")
                self._fail_pending(error)
                if self._process is process:
                    self._process = None
                signal = {
                    "method": "larkode/connectionClosed",
                    "params": {"message": str(error), "generation": generation},
                }
                await self._events.put(signal)
                await self._server_requests.put(signal)
                if process.returncode is None and hasattr(process, "terminate"):
                    try:
                        process.terminate()
                    except ProcessLookupError:
                        pass
                    try:
                        await asyncio.wait_for(process.wait(), timeout=2)
                    except asyncio.TimeoutError:
                        process.kill()
                        await process.wait()

    async def _read_stderr(self, process: asyncio.subprocess.Process) -> None:
        assert process.stderr
        while True:
            raw = await process.stderr.readline()
            if not raw:
                break
            line = raw.decode("utf-8", errors="replace").rstrip()
            if line:
                logger.debug(f"codex app-server: {line[:2000]}")

    def _assert_owner_loop(self) -> None:
        loop = asyncio.get_running_loop()
        if self._owner_loop is None:
            self._owner_loop = loop
        elif loop is not self._owner_loop:
            raise CodexAppServerError("Codex App Server 被跨事件循环调用")

    def _drain_runtime_queues(self) -> None:
        for queue in (self._events, self._server_requests):
            while not queue.empty():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

    @staticmethod
    def _subprocess_env() -> dict[str, str]:
        """只向 Codex 传递运行所需的非业务环境，避免泄露飞书等服务密钥。"""
        exact = {
            "HOME", "PATH", "USER", "LOGNAME", "LANG", "LC_ALL", "LC_CTYPE",
            "TERM", "TMPDIR", "CODEX_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME",
            "XDG_DATA_HOME", "SSL_CERT_FILE", "SSL_CERT_DIR",
        }
        return {
            key: value
            for key, value in os.environ.items()
            if key in exact or key.startswith("LC_")
        }

    def _fail_pending(self, error: Exception) -> None:
        pending, self._pending = self._pending, {}
        for future in pending.values():
            if not future.done():
                future.set_exception(error)
