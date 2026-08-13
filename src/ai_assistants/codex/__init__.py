"""Codex Agent 适配器。"""

import asyncio
import time
from pathlib import Path
from typing import AsyncGenerator, Awaitable, Callable, Dict, Optional

from src.agent.codex_app_server import CodexAppServerClient, CodexAppServerError
from src.agent.models import AgentCapabilities
from src.interfaces.ai_assistant import AssistantConfig, IAIAssistantInterface

try:
    from src.logging_utils import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class CodexAIInterface(IAIAssistantInterface):
    """将 Codex App Server thread/turn 映射到现有助手接口。"""

    def __init__(self, config: AssistantConfig):
        from src.config.settings import get_settings

        settings = get_settings()
        self.config = config
        self.client = CodexAppServerClient(
            cli_path=config.cli_path or settings.codex_cli_path,
            request_timeout=settings.codex_request_timeout,
        )
        self._threads: Dict[str, str] = {}
        self._active_thread_id: Optional[str] = None
        self._active_turn_id: Optional[str] = None
        self._is_running = False
        self._lock = asyncio.Lock()
        self._server_request_task: Optional[asyncio.Task] = None
        self._server_request_handler: Optional[
            Callable[[dict, str], Awaitable[Optional[dict]]]
        ] = None
        self._current_user_id: Optional[str] = None
        self._client_generation = 0
        self._request_tasks: Dict[tuple[int, int], asyncio.Task] = {}
        self._catalog_cache: tuple[float, list[dict]] = (0.0, [])
        self._catalog_lock = asyncio.Lock()
        self._last_outcome = "success"
        self._last_error = ""
        self._items: Dict[tuple[str, str, str], dict] = {}
        self._item_ready: Dict[tuple[str, str, str], asyncio.Event] = {}

    def set_server_request_handler(
        self, handler: Callable[[dict, str], Awaitable[Optional[dict]]]
    ) -> None:
        """设置由 IM 层实现的审批/用户输入处理器。"""
        self._server_request_handler = handler

    @staticmethod
    def _is_runtime_failure(text: str) -> bool:
        """识别 App Server/沙箱基础设施失败，避免把失败说明标成成功回复。"""
        lowered = text.lower()
        return any(
            marker in lowered
            for marker in (
                "bwrap:",
                "rtm_newaddr",
                "sandbox startup failed",
                "operation not permitted",
                "rejected(\"rejected by user\")",
            )
        )

    @property
    def capabilities(self) -> AgentCapabilities:
        return AgentCapabilities(
            streaming=True,
            cancellation=True,
            approvals=True,
            user_input=False,
            model_selection=True,
            session_resume=True,
            structured_tool_events=False,
        )

    async def start(self) -> None:
        await self.client.start()
        if self._client_generation != self.client.generation:
            await self._cancel_request_tasks()
            self._threads.clear()
            self._items.clear()
            self._item_ready.clear()
            self._client_generation = self.client.generation
        if not self._server_request_task or self._server_request_task.done():
            self._server_request_task = asyncio.create_task(self._handle_server_requests())

    async def stop(self) -> None:
        if self._server_request_task and not self._server_request_task.done():
            self._server_request_task.cancel()
            await asyncio.gather(self._server_request_task, return_exceptions=True)
        await self._cancel_request_tasks()
        await self.client.stop()

    async def _cancel_request_tasks(self, generation: Optional[int] = None) -> None:
        selected = [
            (key, task) for key, task in self._request_tasks.items()
            if generation is None or key[0] == generation
        ]
        for _, task in selected:
            task.cancel()
        if selected:
            await asyncio.gather(*(task for _, task in selected), return_exceptions=True)
        for key, task in selected:
            if self._request_tasks.get(key) is task:
                self._request_tasks.pop(key, None)

    async def get_model_catalog(self) -> list[dict]:
        """读取当前账号实际可用的 Codex 模型及 Think 等级。"""
        expires_at, cached = self._catalog_cache
        if cached and time.monotonic() < expires_at:
            return cached
        async with self._catalog_lock:
            expires_at, cached = self._catalog_cache
            if cached and time.monotonic() < expires_at:
                return cached
            await self.start()
            result = await self.client.request(
                "model/list", {"limit": 100, "includeHidden": False}
            )
            models = result.get("data", [])
            self._catalog_cache = (time.monotonic() + 60.0, models)
            return models

    async def _handle_server_requests(self) -> None:
        """把服务端交互请求转给 IM；不可处理时安全拒绝。"""
        try:
            while self.client.running:
                request = await self.client.next_server_request()
                method = request.get("method", "")
                if method == "larkode/connectionClosed":
                    generation = (request.get("params") or {}).get("generation")
                    await self._cancel_request_tasks(generation)
                    return
                request_id = request.get("id")
                if request_id is None:
                    continue
                generation = request.get("_generation", self.client.generation)
                key = (generation, request_id)
                task = asyncio.create_task(self._process_server_request(request, generation))
                self._request_tasks[key] = task
                task.add_done_callback(
                    lambda done, task_key=key: (
                        self._request_tasks.pop(task_key, None)
                        if self._request_tasks.get(task_key) is done else None
                    )
                )
        except asyncio.CancelledError:
            # 给刚创建的轻量响应任务一次调度机会，再取消仍在等待用户的审批。
            await asyncio.sleep(0)
            for task in list(self._request_tasks.values()):
                if not task.done():
                    task.cancel()
            await asyncio.gather(*self._request_tasks.values(), return_exceptions=True)
            raise

    async def _process_server_request(self, request: dict, generation: int) -> None:
        """并发处理单个服务端请求，避免一项审批阻塞后续审批。"""
        method = request.get("method", "")
        request_id = request.get("id")
        result = None
        try:
            params = dict(request.get("params") or {})
            item_key = (
                params.get("threadId", ""),
                params.get("turnId", ""),
                params.get("itemId", ""),
            )
            if method == "item/fileChange/requestApproval" and item_key not in self._items:
                ready = self._item_ready.setdefault(item_key, asyncio.Event())
                try:
                    await asyncio.wait_for(ready.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    logger.warning("文件审批缺少完整变更详情，安全拒绝")
                    await self.client.respond(
                        request_id, {"decision": "decline"},
                        expected_generation=generation,
                    )
                    return
            if item_key in self._items:
                request = {**request, "params": {**params, "_item": self._items[item_key]}}
            if self._server_request_handler and self._current_user_id:
                try:
                    result = await self._server_request_handler(
                        request, self._current_user_id
                    )
                except Exception:
                    logger.exception(f"处理 Codex 用户交互失败: {method}")
            if result is not None:
                await self.client.respond(
                    request_id, result, expected_generation=generation
                )
                return

            logger.warning(f"Codex 用户交互无法处理，安全拒绝: {method}")
            if method in {
                "item/commandExecution/requestApproval",
                "item/fileChange/requestApproval",
            }:
                available = set(params.get("availableDecisions") or ["accept", "decline"])
                safe_decision = "decline" if "decline" in available else (
                    "cancel" if "cancel" in available else None
                )
                if safe_decision:
                    await self.client.respond(
                        request_id, {"decision": safe_decision},
                        expected_generation=generation,
                    )
                else:
                    await self.client.respond_error(
                        request_id, -32000, "No supported safe approval decision",
                        expected_generation=generation,
                    )
            elif method == "item/tool/requestUserInput":
                await self.client.respond(
                    request_id, {"answers": {}}, expected_generation=generation
                )
            elif method == "item/permissions/requestApproval":
                await self.client.respond(
                    request_id, {"permissions": {}}, expected_generation=generation
                )
            elif method == "mcpServer/elicitation/request":
                await self.client.respond(
                    request_id, {"action": "decline", "content": None},
                    expected_generation=generation,
                )
            else:
                await self.client.respond_error(
                    request_id, -32601, "Method not supported",
                    expected_generation=generation,
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error(f"响应 Codex 用户交互失败: {method}: {exc}", exc_info=True)

    def _workspace(self) -> Path:
        from src.workspace_manager import get_workspace_manager

        workspace = get_workspace_manager().get_current_workspace()
        return Path(workspace) if workspace else Path.cwd()

    async def _ensure_thread(self, workspace: Path) -> str:
        key = str(workspace.resolve())
        if key in self._threads:
            return self._threads[key]

        from src.config.settings import get_settings
        from src.storage import db
        settings = get_settings()
        params = {
            "cwd": key,
            "approvalPolicy": settings.codex_approval_policy,
            "sandbox": settings.codex_sandbox,
            "serviceName": "larkode",
        }
        if settings.codex_model:
            params["model"] = settings.codex_model
        stored_thread_id = db.get_agent_session("codex", key)
        if stored_thread_id:
            try:
                result = await self.client.request(
                    "thread/resume", {"threadId": stored_thread_id, **params}
                )
                thread_id = result.get("thread", {}).get("id")
                if thread_id:
                    self._threads[key] = thread_id
                    return thread_id
            except CodexAppServerError as exc:
                message = str(exc).lower()
                recoverable = any(
                    marker in message
                    for marker in ("not found", "unknown thread", "does not exist", "invalid thread")
                )
                if not recoverable:
                    raise
                logger.warning(f"已保存的 Codex thread 不存在，将创建新 thread: {stored_thread_id}: {exc}")
        result = await self.client.request("thread/start", params)
        thread_id = result.get("thread", {}).get("id")
        if not thread_id:
            raise CodexAppServerError("thread/start 未返回 thread.id")
        self._threads[key] = thread_id
        db.save_agent_session("codex", key, thread_id)
        return thread_id

    async def execute_command(
        self, command: str, user_id: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        if not command.strip():
            yield "错误: 命令不能为空"
            return

        async with self._lock:
            self._is_running = True
            self._current_user_id = user_id
            self._last_outcome = "success"
            self._last_error = ""
            turn_started = False
            terminal_received = False
            turn_generation: Optional[int] = None
            try:
                await self.start()
                workspace = self._workspace()
                thread_id = await self._ensure_thread(workspace)
                params = {
                    "threadId": thread_id,
                    "input": [{"type": "text", "text": command}],
                    "cwd": str(workspace.resolve()),
                }
                from src.config.settings import get_settings
                settings = get_settings()
                if settings.codex_model:
                    params["model"] = settings.codex_model
                if settings.codex_reasoning_effort:
                    params["effort"] = settings.codex_reasoning_effort

                result = await self.client.request("turn/start", params)
                turn_generation = self.client.generation
                turn = result.get("turn", {})
                self._active_thread_id = thread_id
                self._active_turn_id = turn.get("id")
                turn_started = bool(self._active_turn_id)

                had_text = False
                deadline = time.monotonic() + settings.streaming_timeout
                while True:
                    if self.client.generation != turn_generation:
                        raise CodexAppServerError("Codex App Server 已重连，当前任务已终止")
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise asyncio.TimeoutError
                    try:
                        event = await self.client.next_event(timeout=min(1.0, remaining))
                    except asyncio.TimeoutError:
                        continue
                    method = event.get("method")
                    event_params = event.get("params", {})
                    if method == "larkode/connectionClosed":
                        raise CodexAppServerError(event_params.get("message", "连接已关闭"))
                    if method == "serverRequest/resolved":
                        request_id = event_params.get("requestId") or event_params.get("id")
                        task = self._request_tasks.get((turn_generation, request_id))
                        if task:
                            task.cancel()
                        continue
                    if method in {"item/started", "item/completed"}:
                        item = event_params.get("item") or {}
                        item_id = item.get("id") or event_params.get("itemId")
                        if item_id:
                            key = (
                                event_params.get("threadId") or thread_id,
                                event_params.get("turnId") or self._active_turn_id or "",
                                item_id,
                            )
                            self._items[key] = item
                            self._item_ready.setdefault(key, asyncio.Event()).set()
                            if len(self._items) > 500:
                                self._items.pop(next(iter(self._items)))
                    event_thread_id = event_params.get("threadId")
                    if event_thread_id and event_thread_id != thread_id:
                        continue
                    event_turn_id = event_params.get("turnId")
                    if (
                        event_turn_id
                        and self._active_turn_id
                        and event_turn_id != self._active_turn_id
                    ):
                        continue

                    if method == "item/agentMessage/delta":
                        delta = event_params.get("delta", "")
                        if delta:
                            had_text = True
                            if self._is_runtime_failure(delta):
                                self._last_outcome = "error"
                                self._last_error = delta
                            yield delta
                    elif method == "turn/completed":
                        completed = event_params.get("turn", {})
                        if self._active_turn_id and completed.get("id") != self._active_turn_id:
                            continue
                        status = completed.get("status")
                        terminal_received = True
                        if status == "failed":
                            error = completed.get("error") or {}
                            self._last_outcome = "error"
                            self._last_error = error.get("message", "Codex turn failed")
                            yield self._last_error
                        elif status == "interrupted":
                            self._last_outcome = "cancelled"
                            yield "已取消"
                        break
                    elif method == "error":
                        error = event_params.get("error", event_params)
                        message = error.get("message", str(error)) if isinstance(error, dict) else str(error)
                        self._last_outcome = "error"
                        self._last_error = message
                        yield message

                if self._last_outcome == "success" and not had_text:
                    yield "Codex 已完成，未返回文本内容"
            except asyncio.TimeoutError:
                self._last_outcome = "error"
                self._last_error = "Codex 响应超时"
                yield self._last_error
            except Exception as exc:
                self._last_outcome = "error"
                self._last_error = str(exc)
                logger.error(f"Codex 执行失败: {exc}", exc_info=True)
                yield self._last_error
            finally:
                if (
                    turn_started and not terminal_received and self.client.running
                    and self.client.generation == turn_generation
                ):
                    try:
                        await self.client.request(
                            "turn/interrupt",
                            {"threadId": self._active_thread_id, "turnId": self._active_turn_id},
                        )
                    except Exception as exc:
                        logger.warning(f"清理未结束 Codex turn 失败: {exc}")
                self._is_running = False
                self._active_turn_id = None
                self._current_user_id = None

    async def cancel_async(self) -> bool:
        if not self._active_thread_id or not self._active_turn_id or not self.client.running:
            return False
        try:
            await self.client.request(
                "turn/interrupt",
                {"threadId": self._active_thread_id, "turnId": self._active_turn_id},
            )
            return True
        except Exception as exc:
            logger.warning(f"取消 Codex turn 失败: {exc}")
            return False

    def cancel(self) -> bool:
        if not self._active_thread_id or not self._active_turn_id or not self.client.running:
            return False
        try:
            asyncio.get_running_loop().create_task(self.cancel_async())
            return True
        except RuntimeError:
            return False

    def get_status(self) -> dict:
        return {
            "assistant_type": "codex",
            "is_running": self._is_running,
            "server_running": self.client.running,
            "thread_id": self._active_thread_id,
            "turn_id": self._active_turn_id,
            "last_outcome": self._last_outcome,
            "last_error": self._last_error,
            "capabilities": self.capabilities.__dict__,
        }


def register_codex_assistant() -> None:
    from src.factories.assistant_factory import AIAssistantFactory
    from src.interfaces.ai_assistant import AssistantType

    AIAssistantFactory.register_assistant(AssistantType.CODEX, CodexAIInterface)
