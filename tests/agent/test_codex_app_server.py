import asyncio
import json
from types import SimpleNamespace

import pytest

from src.agent.codex_app_server import CodexAppServerClient, CodexAppServerError


@pytest.mark.asyncio
async def test_reader_routes_responses_events_and_server_requests():
    client = CodexAppServerClient()
    reader = asyncio.StreamReader()
    client._process = SimpleNamespace(stdout=reader, returncode=None)

    future = asyncio.get_running_loop().create_future()
    client._pending[7] = future
    task = asyncio.create_task(client._read_stdout())

    messages = [
        {"id": 7, "result": {"ok": True}},
        {"method": "turn/started", "params": {"threadId": "thr_1"}},
        {
            "id": 9,
            "method": "item/commandExecution/requestApproval",
            "params": {"threadId": "thr_1"},
        },
    ]
    for message in messages:
        reader.feed_data((json.dumps(message) + "\n").encode())
    reader.feed_eof()
    await task

    assert (await future)["result"] == {"ok": True}
    assert (await client.next_event())["method"] == "turn/started"
    assert (await client.next_server_request())["id"] == 9


@pytest.mark.asyncio
async def test_stale_generation_response_is_rejected():
    client = CodexAppServerClient()
    client._generation = 2

    with pytest.raises(CodexAppServerError, match="连接已变更"):
        await client.respond(1, {"decision": "accept"}, expected_generation=1)


def test_subprocess_environment_excludes_service_secrets(monkeypatch):
    monkeypatch.setenv("HOME", "/tmp/home")
    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setenv("FEISHU_APP_SECRET", "do-not-leak")
    monkeypatch.setenv("MINIMAX_API_KEY", "do-not-leak")

    env = CodexAppServerClient._subprocess_env()

    assert env["HOME"] == "/tmp/home"
    assert env["PATH"] == "/usr/bin"
    assert "FEISHU_APP_SECRET" not in env
    assert "MINIMAX_API_KEY" not in env
