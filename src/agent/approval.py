"""跨事件循环传递 Codex 审批结果。"""

import asyncio
import threading
import uuid
from dataclasses import dataclass
from typing import Collection, Dict, Optional


@dataclass
class _PendingApproval:
    user_id: str
    allowed_decisions: frozenset[str]
    loop: asyncio.AbstractEventLoop
    future: asyncio.Future


class CodexApprovalBroker:
    """连接 App Server 主循环与飞书 WebSocket 回调线程。"""

    def __init__(self) -> None:
        self._pending: Dict[str, _PendingApproval] = {}
        self._lock = threading.Lock()

    def create(
        self, user_id: str, allowed_decisions: Optional[Collection[str]] = None
    ) -> tuple[str, asyncio.Future]:
        loop = asyncio.get_running_loop()
        approval_id = uuid.uuid4().hex
        future = loop.create_future()
        allowed = frozenset(
            allowed_decisions or {"accept", "acceptForSession", "decline", "cancel"}
        )
        with self._lock:
            self._pending[approval_id] = _PendingApproval(user_id, allowed, loop, future)
        return approval_id, future

    def resolve(self, approval_id: str, user_id: str, decision: str) -> bool:
        with self._lock:
            pending = self._pending.get(approval_id)
            if (
                not pending
                or pending.user_id != user_id
                or decision not in pending.allowed_decisions
            ):
                return False
            self._pending.pop(approval_id, None)

        def set_result() -> None:
            if not pending.future.done():
                pending.future.set_result(decision)

        pending.loop.call_soon_threadsafe(set_result)
        return True

    def cancel(self, approval_id: str) -> None:
        with self._lock:
            pending: Optional[_PendingApproval] = self._pending.pop(approval_id, None)
        if pending:
            pending.loop.call_soon_threadsafe(pending.future.cancel)


codex_approval_broker = CodexApprovalBroker()
