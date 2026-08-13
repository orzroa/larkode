from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.handlers.codex_commands import CodexCommands


CATALOG = [{
    "model": "gpt-test",
    "displayName": "GPT Test",
    "isDefault": True,
    "defaultReasoningEffort": "medium",
    "supportedReasoningEfforts": [
        {"reasoningEffort": "low", "description": "Fast"},
        {"reasoningEffort": "medium", "description": "Balanced"},
    ],
}]

LUNA_CATALOG = [{
    "model": "gpt-5.6-luna",
    "displayName": "GPT-5.6 Luna",
    "defaultReasoningEffort": "high",
    "supportedReasoningEfforts": [
        {"reasoningEffort": "low"},
        {"reasoningEffort": "medium"},
        {"reasoningEffort": "high"},
        # 即使异常目录带出 max，Luna 也不能展示或接受它。
        {"reasoningEffort": "max"},
    ],
}]


@pytest.fixture
def commands():
    assistant = Mock()
    assistant.get_model_catalog = AsyncMock(return_value=CATALOG)
    manager = Mock(ai_assistant=assistant)
    return CodexCommands(manager)


@pytest.mark.asyncio
async def test_model_card_uses_app_server_catalog(commands):
    sender = AsyncMock()
    settings = Mock(codex_model="", codex_reasoning_effort="")

    with patch("src.handlers.codex_commands.get_settings", return_value=settings):
        await commands.show_model_option_card("ou_1", sender)

    card = sender.await_args.kwargs["card"]
    assert card["header"]["title"]["content"] == "🤖 Codex 模型"
    assert "GPT Test" in str(card)


@pytest.mark.asyncio
async def test_think_card_uses_current_model_effort_options(commands):
    sender = AsyncMock()
    settings = Mock(codex_model="gpt-test", codex_reasoning_effort="")

    with patch("src.handlers.codex_commands.get_settings", return_value=settings):
        await commands.show_effort_option_card("ou_1", sender)

    card = sender.await_args.kwargs["card"]
    assert card["header"]["title"]["content"] == "🧠 Codex Think 等级"
    assert "low" in str(card)
    assert "medium" in str(card)


@pytest.mark.asyncio
async def test_effort_selection_is_validated_and_applied_to_current_process(commands):
    sender = AsyncMock()
    settings = Mock(codex_model="gpt-test", codex_reasoning_effort="")

    with patch("src.handlers.codex_commands.get_settings", return_value=settings):
        await commands.handle_effort_select("ou_1", "medium", sender)

    settings.set_codex_session_preferences.assert_called_once_with(reasoning_effort="medium")
    assert sender.await_count == 1
    assert sender.await_args.kwargs["card"]["header"]["title"]["content"] == "✅ Codex Think 等级已切换"


@pytest.mark.asyncio
async def test_model_selection_sends_result_card(commands):
    sender = AsyncMock()
    settings = Mock()

    with patch("src.handlers.codex_commands.get_settings", return_value=settings):
        await commands.handle_model_select("ou_1", "gpt-test", sender)

    settings.set_codex_session_preferences.assert_called_once_with(
        model="gpt-test", reasoning_effort="medium"
    )
    assert sender.await_count == 1
    assert sender.await_args.kwargs["card"]["header"]["title"]["content"] == "✅ Codex 模型已切换"


@pytest.mark.asyncio
async def test_invalid_effort_is_rejected(commands):
    settings = Mock(codex_model="gpt-test")
    with patch("src.handlers.codex_commands.get_settings", return_value=settings):
        with pytest.raises(ValueError, match="不支持"):
            await commands.handle_effort_select("ou_1", "xhigh", AsyncMock())


@pytest.mark.asyncio
async def test_luna_does_not_show_or_accept_max_effort():
    assistant = Mock()
    assistant.get_model_catalog = AsyncMock(return_value=LUNA_CATALOG)
    commands = CodexCommands(Mock(ai_assistant=assistant))
    sender = AsyncMock()
    settings = Mock(codex_model="gpt-5.6-luna", codex_reasoning_effort="max")

    with patch("src.handlers.codex_commands.get_settings", return_value=settings):
        await commands.show_effort_option_card("ou_1", sender)
        card = sender.await_args.kwargs["card"]
        assert "max" not in str(card)
        with pytest.raises(ValueError, match="不支持"):
            await commands.handle_effort_select("ou_1", "max", sender)
