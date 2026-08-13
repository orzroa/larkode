import asyncio
import threading

import pytest

from src.agent.approval import CodexApprovalBroker


@pytest.mark.asyncio
async def test_approval_can_be_resolved_from_callback_thread():
    broker = CodexApprovalBroker()
    approval_id, future = broker.create("ou_1")

    thread = threading.Thread(
        target=lambda: broker.resolve(approval_id, "ou_1", "accept")
    )
    thread.start()
    thread.join()

    assert await asyncio.wait_for(future, timeout=1) == "accept"


@pytest.mark.asyncio
async def test_approval_rejects_another_user():
    broker = CodexApprovalBroker()
    approval_id, future = broker.create("ou_owner")

    assert broker.resolve(approval_id, "ou_other", "accept") is False
    assert future.done() is False
    broker.cancel(approval_id)


@pytest.mark.asyncio
async def test_approval_rejects_decision_not_offered_by_server():
    broker = CodexApprovalBroker()
    approval_id, future = broker.create("ou_owner", {"decline"})

    assert broker.resolve(approval_id, "ou_owner", "accept") is False
    assert future.done() is False
    assert broker.resolve(approval_id, "ou_owner", "decline") is True
    assert await asyncio.wait_for(future, timeout=1) == "decline"
