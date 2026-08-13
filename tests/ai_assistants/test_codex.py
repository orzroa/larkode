import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.ai_assistants.codex import CodexAIInterface
from src.interfaces.ai_assistant import AssistantConfig, AssistantType


def make_adapter():
    return CodexAIInterface(
        AssistantConfig(
            assistant_type=AssistantType.CODEX,
            cli_path="codex",
        )
    )


@pytest.mark.asyncio
async def test_execute_streams_agent_delta_until_turn_completed():
    adapter = make_adapter()
    adapter.start = AsyncMock()
    adapter._workspace = lambda: Path("/tmp")
    adapter._ensure_thread = AsyncMock(return_value="thr_1")
    adapter.client.request = AsyncMock(
        return_value={"turn": {"id": "turn_1", "status": "inProgress"}}
    )
    adapter.client.next_event = AsyncMock(
        side_effect=[
            {
                "method": "item/agentMessage/delta",
                "params": {"threadId": "thr_1", "delta": "你好"},
            },
            {
                "method": "turn/completed",
                "params": {
                    "threadId": "thr_1",
                    "turn": {"id": "turn_1", "status": "completed"},
                },
            },
        ]
    )

    output = [part async for part in adapter.execute_command("测试")]

    assert output == ["你好"]
    adapter.client.request.assert_awaited_once()


@pytest.mark.asyncio
async def test_ensure_thread_resumes_persisted_session():
    adapter = make_adapter()
    adapter.client.request = AsyncMock(
        return_value={"thread": {"id": "thr_saved"}}
    )

    with patch("src.storage.db.get_agent_session", return_value="thr_saved"):
        thread_id = await adapter._ensure_thread(Path("/tmp"))

    assert thread_id == "thr_saved"
    adapter.client.request.assert_awaited_once_with(
        "thread/resume",
        {
            "threadId": "thr_saved",
            "cwd": "/tmp",
            "approvalPolicy": "on-request",
            "sandbox": "workspace-write",
            "serviceName": "larkode",
            "model": "gpt-5.6-terra",
        },
    )


@pytest.mark.asyncio
async def test_server_approval_is_delegated_to_im_handler():
    adapter = make_adapter()
    adapter._current_user_id = "ou_1"
    adapter.client._process = type("Process", (), {"returncode": None})()
    adapter.client.next_server_request = AsyncMock(side_effect=[
        {
            "id": 9,
            "method": "item/commandExecution/requestApproval",
            "params": {"command": "git status"},
        },
        asyncio.CancelledError(),
    ])
    adapter.client.respond = AsyncMock()
    handler = AsyncMock(return_value={"decision": "accept"})
    adapter.set_server_request_handler(handler)

    with pytest.raises(asyncio.CancelledError):
        await adapter._handle_server_requests()

    handler.assert_awaited_once()
    adapter.client.respond.assert_awaited_once_with(
        9, {"decision": "accept"}, expected_generation=0
    )


@pytest.mark.asyncio
async def test_unsupported_approval_decisions_fail_closed_with_protocol_error():
    adapter = make_adapter()
    adapter.client.respond = AsyncMock()
    adapter.client.respond_error = AsyncMock()

    await adapter._process_server_request({
        "id": 10,
        "method": "item/commandExecution/requestApproval",
        "params": {"availableDecisions": ["acceptWithExecpolicyAmendment"]},
    }, generation=3)

    adapter.client.respond.assert_not_awaited()
    adapter.client.respond_error.assert_awaited_once_with(
        10, -32000, "No supported safe approval decision", expected_generation=3
    )


@pytest.mark.asyncio
async def test_get_model_catalog_uses_app_server_model_list():
    adapter = make_adapter()
    adapter.start = AsyncMock()
    adapter.client.request = AsyncMock(return_value={"data": [{"model": "gpt-test"}]})

    catalog = await adapter.get_model_catalog()

    assert catalog == [{"model": "gpt-test"}]
    adapter.client.request.assert_awaited_once_with(
        "model/list", {"limit": 100, "includeHidden": False}
    )


def test_codex_capabilities_are_structured():
    capabilities = make_adapter().capabilities

    assert capabilities.streaming is True
    assert capabilities.approvals is True
    assert capabilities.session_resume is True


@pytest.mark.asyncio
async def test_failed_turn_has_error_outcome_without_success_fallback():
    adapter = make_adapter()
    adapter.start = AsyncMock()
    adapter._workspace = lambda: Path("/tmp")
    adapter._ensure_thread = AsyncMock(return_value="thr_1")
    adapter.client.request = AsyncMock(
        return_value={"turn": {"id": "turn_1", "status": "inProgress"}}
    )
    adapter.client.next_event = AsyncMock(return_value={
        "method": "turn/completed",
        "params": {
            "threadId": "thr_1",
            "turn": {"id": "turn_1", "status": "failed", "error": {"message": "boom"}},
        },
    })

    output = [part async for part in adapter.execute_command("测试")]

    assert output == ["boom"]
    assert adapter.get_status()["last_outcome"] == "error"


@pytest.mark.asyncio
async def test_active_turn_stops_when_app_server_generation_changes():
    adapter = make_adapter()
    adapter.start = AsyncMock()
    adapter._workspace = lambda: Path("/tmp")
    adapter._ensure_thread = AsyncMock(return_value="thr_1")
    adapter.client.request = AsyncMock(
        return_value={"turn": {"id": "turn_1", "status": "inProgress"}}
    )

    async def reconnect_during_wait(*_args, **_kwargs):
        adapter.client._generation += 1
        return {"method": "irrelevant", "params": {}}

    adapter.client.next_event = AsyncMock(side_effect=reconnect_during_wait)

    output = [part async for part in adapter.execute_command("测试")]

    assert output == ["Codex App Server 已重连，当前任务已终止"]
    assert adapter.get_status()["last_outcome"] == "error"


def test_sandbox_runtime_failure_is_not_success():
    assert CodexAIInterface._is_runtime_failure(
        "bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted"
    )
    assert not CodexAIInterface._is_runtime_failure("正常完成")
