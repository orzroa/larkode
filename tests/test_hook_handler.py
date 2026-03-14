"""
测试 Hook Handler 主模块
"""
import os
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestIsTestUser:
    """测试 _is_test_user 函数"""

    def test_is_test_user_true(self):
        """测试包含 test 的用户 ID"""
        from src.hook_handler import _is_test_user
        assert _is_test_user("test_user") is True
        assert _is_test_user("user_test_123") is True
        assert _is_test_user("TEST_USER") is True

    def test_is_test_user_false(self):
        """测试不包含 test 的用户 ID"""
        from src.hook_handler import _is_test_user
        assert _is_test_user("prod_user") is False
        assert _is_test_user("user123") is False
        assert _is_test_user("admin") is False


class TestRecordHookMessage:
    """测试 record_hook_message 函数"""

    def test_record_hook_message_success(self):
        """测试成功记录 Hook 消息"""
        from src.hook_handler import record_hook_message

        with patch('src.hook_handler.db') as mock_db:
            mock_db.save_message = Mock()
            record_hook_message("user_123", "test message", "notification", "msg_456")

            mock_db.save_message.assert_called_once()
            call_args = mock_db.save_message.call_args[0][0]
            assert call_args.user_id == "user_123"
            assert call_args.content == "test message"

    def test_record_hook_message_with_card_id(self):
        """测试带 card_id 记录消息"""
        from src.hook_handler import record_hook_message

        with patch('src.hook_handler.db') as mock_db:
            mock_db.save_message = Mock()
            record_hook_message("user_123", "test message", "stop", "msg_789", card_id=42)

            mock_db.save_message.assert_called_once()
            call_args = mock_db.save_message.call_args[0][0]
            assert call_args.card_id == 42

    def test_record_hook_message_exception(self):
        """测试记录消息异常处理"""
        from src.hook_handler import record_hook_message

        with patch('src.hook_handler.db') as mock_db:
            mock_db.save_message.side_effect = Exception("DB error")

            # 应该不抛出异常
            record_hook_message("user_123", "test message")


class TestCollectAllData:
    """测试 collect_all_data 函数"""

    def test_collect_all_data_basic(self):
        """测试收集基本数据"""
        from src.hook_handler import collect_all_data
        from src.interfaces.hook_handler import ClaudeHookHandler, HookContext, HookEventType

        handler = ClaudeHookHandler()
        context = HookContext(event_type=HookEventType.USER_PROMPT_SUBMIT)
        stdin_data = '{"test": "data"}'

        data = collect_all_data(handler, context, stdin_data)

        assert "timestamp" in data
        assert data["handler"] == "default"
        assert data["hook_event"] == "UserPromptSubmit"
        assert "hostname" in data
        assert data["stdin"] == stdin_data

    def test_collect_all_data_with_environment(self):
        """测试收集环境变量"""
        from src.hook_handler import collect_all_data
        from src.interfaces.hook_handler import ClaudeHookHandler, HookContext, HookEventType

        handler = ClaudeHookHandler()
        context = HookContext(event_type=HookEventType.STOP)
        stdin_data = '{}'

        with patch.dict(os.environ, {
            "CLAUDE_SESSION_ID": "test-session",
            "FEISHU_APP_ID": "test-app",
            "HOME": "/home/test"
        }):
            data = collect_all_data(handler, context, stdin_data)

            assert "environment" in data
            assert data["environment"]["CLAUDE_SESSION_ID"] == "test-session"
            assert data["environment"]["FEISHU_APP_ID"] == "test-app"
            assert data["environment"]["HOME"] == "/home/test"


class TestLogEvent:
    """测试 log_event 函数"""

    def test_log_event_basic(self):
        """测试基本日志记录"""
        from src.hook_handler import log_event

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "hook_events.log"
            json_file = Path(tmpdir) / "hook_events.jsonl"

            with patch('src.hook_handler.LOG_FILE', log_file):
                with patch('src.hook_handler.JSON_LOG_FILE', json_file):
                    data = {
                        "timestamp": "2024-01-01T00:00:00",
                        "handler": "claude",
                        "hook_event": "Stop",
                        "hostname": "test-host",
                        "working_directory": "/test",
                        "stdin_parsed": {"test": "data"}
                    }

                    log_event(data, "测试步骤")

                    assert log_file.exists()
                    assert json_file.exists()

                    # 验证 JSON 文件内容
                    with open(json_file) as f:
                        json_data = json.load(f)
                    assert json_data["handler"] == "claude"
                    assert json_data["step_info"] == "测试步骤"


class TestBuildPermissionMessage:
    """测试 build_permission_message 函数"""

    def test_build_permission_message_ask_user_question(self):
        """测试 AskUserQuestion 工具消息"""
        from src.hook_handler import build_permission_message

        tool_input = {
            "questions": [
                {
                    "question": "选择一个选项?",
                    "header": "选项",
                    "options": [
                        {"label": "选项A", "description": "这是选项A"},
                        {"label": "选项B", "description": "这是选项B"}
                    ],
                    "multiSelect": False
                }
            ]
        }

        message = build_permission_message("AskUserQuestion", tool_input)

        assert "**选项**" in message
        assert "选择一个选项?" in message
        assert "选项A - 这是选项A" in message
        assert "(单选)" in message

    def test_build_permission_message_ask_user_question_multi(self):
        """测试多选 AskUserQuestion"""
        from src.hook_handler import build_permission_message

        tool_input = {
            "questions": [
                {
                    "question": "选择多个?",
                    "options": [
                        {"label": "A"},
                        {"label": "B"}
                    ],
                    "multiSelect": True
                }
            ]
        }

        message = build_permission_message("AskUserQuestion", tool_input)

        assert "(多选)" in message

    def test_build_permission_message_ask_user_question_empty(self):
        """测试空问题的 AskUserQuestion"""
        from src.hook_handler import build_permission_message

        message = build_permission_message("AskUserQuestion", {"questions": []})

        assert "需要您的选择" in message

    def test_build_permission_message_bash(self):
        """测试 Bash 工具消息"""
        from src.hook_handler import build_permission_message

        with patch('src.hook_handler.get_tmux_last_lines', return_value="tmux output"):
            message = build_permission_message("Bash", {"command": "ls"})

            assert "屏幕内容" in message
            assert "tmux output" in message

    def test_build_permission_message_with_context(self):
        """测试使用 HookContext 构建消息"""
        from src.hook_handler import build_permission_message
        from src.interfaces.hook_handler import HookContext, HookEventType

        context = HookContext(
            event_type=HookEventType.PERMISSION_REQUEST,
            tool_name="AskUserQuestion",
            tool_input={"questions": [{"question": "测试?", "options": [{"label": "A"}]}]}
        )

        message = build_permission_message(context)

        assert "测试?" in message


class TestSendEscapeToTmux:
    """测试 send_escape_to_tmux 函数"""

    def test_send_escape_skip_in_test_mode(self):
        """测试测试模式下跳过"""
        from src.hook_handler import send_escape_to_tmux

        with patch.dict(os.environ, {"PYTEST_CURRENT_TEST": "test"}):
            result = send_escape_to_tmux()
            assert result is True

    def test_send_escape_skip_with_env(self):
        """测试环境变量跳过"""
        from src.hook_handler import send_escape_to_tmux

        with patch.dict(os.environ, {"SKIP_TMUX_ESCAPE": "1"}):
            result = send_escape_to_tmux()
            assert result is True

    def test_send_escape_success(self):
        """测试成功发送 ESC"""
        from src.hook_handler import send_escape_to_tmux

        with patch.dict(os.environ, {}, clear=True):
            with patch('src.hook_handler.get_settings') as mock_settings:
                mock_settings.return_value.TMUX_SESSION_NAME = "cc"

                with patch('subprocess.run') as mock_run:
                    mock_run.return_value = Mock(returncode=0)

                    result = send_escape_to_tmux()
                    assert result is True
                    mock_run.assert_called()

    def test_send_escape_tmux_not_found(self):
        """测试 tmux 未找到"""
        from src.hook_handler import send_escape_to_tmux

        with patch.dict(os.environ, {}, clear=True):
            with patch('src.hook_handler.get_settings') as mock_settings:
                mock_settings.return_value.TMUX_SESSION_NAME = "cc"

                with patch('subprocess.run', side_effect=FileNotFoundError()):
                    result = send_escape_to_tmux()
                    assert result is False


class TestSendFeishuNotification:
    """测试 send_feishu_notification 函数"""

    @pytest.mark.asyncio
    async def test_send_notification_missing_config(self):
        """测试缺少配置"""
        from src.hook_handler import send_feishu_notification

        with patch.dict(os.environ, {}, clear=True):
            result = await send_feishu_notification("test message", "stop")
            assert result == ""

    @pytest.mark.asyncio
    async def test_send_notification_streaming_mode(self):
        """测试流式模式"""
        from src.hook_handler import send_feishu_notification

        with patch.dict(os.environ, {
            "FEISHU_HOOK_NOTIFICATION_USER_ID": "user_123",
            "FEISHU_APP_SECRET": "secret",
            "LARKODE_STREAMING_MODE": "card_123"
        }):
            with patch('src.hook_handler.get_settings') as mock_settings:
                mock_settings.return_value.FEISHU_APP_ID = "app_id"

                with patch('src.hook_handler.FeishuAPI') as mock_api:
                    mock_api_instance = Mock()
                    mock_api.return_value = mock_api_instance
                    mock_api_instance.send_interactive_message = AsyncMock(return_value="msg_id")

                    with patch('src.hook_handler.CardDispatcher') as mock_dispatcher:
                        dispatcher_instance = Mock()
                        mock_dispatcher.return_value = dispatcher_instance
                        dispatcher_instance.send_card = AsyncMock(return_value=("msg_id", None))

                        result = await send_feishu_notification("test message", "stop")

                        # 应该删除流式模式环境变量
                        assert "LARKODE_STREAMING_MODE" not in os.environ

    @pytest.mark.asyncio
    async def test_send_notification_exception(self):
        """测试发送通知异常"""
        from src.hook_handler import send_feishu_notification

        with patch.dict(os.environ, {
            "FEISHU_HOOK_NOTIFICATION_USER_ID": "user_123",
            "FEISHU_APP_SECRET": "secret"
        }):
            with patch('src.hook_handler.get_settings') as mock_settings:
                mock_settings.return_value.FEISHU_APP_ID = "app_id"

                with patch('src.hook_handler.FeishuAPI', side_effect=Exception("API error")):
                    result = await send_feishu_notification("test message", "stop")
                    assert result == ""


class TestHandleEvent:
    """测试 handle_event 函数"""

    @pytest.mark.asyncio
    async def test_handle_event_user_prompt_disabled(self):
        """测试用户提问卡片禁用"""
        from src.hook_handler import handle_event
        from src.interfaces.hook_handler import ClaudeHookHandler, HookContext, HookEventType

        handler = ClaudeHookHandler()
        context = HookContext(event_type=HookEventType.USER_PROMPT_SUBMIT, user_prompt="test prompt")
        data = {"timestamp": "2024-01-01"}

        with patch('src.hook_handler.get_settings') as mock_settings:
            mock_settings.return_value.SHOW_USER_PROMPT_CARD = False

            with patch('src.hook_handler.send_feishu_notification', new_callable=AsyncMock) as mock_send:
                await handle_event(handler, context, data)

                mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_event_stop(self):
        """测试 Stop 事件"""
        from src.hook_handler import handle_event
        from src.interfaces.hook_handler import ClaudeHookHandler, HookContext, HookEventType

        handler = ClaudeHookHandler()
        context = HookContext(
            event_type=HookEventType.STOP,
            last_assistant_message="完成"
        )
        data = {"timestamp": "2024-01-01"}

        with patch('src.hook_handler.send_feishu_notification', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = "msg_id"
            with patch('src.hook_handler.log_event'):
                await handle_event(handler, context, data)

                mock_send.assert_called_once_with("完成", "stop", "Stop")

    @pytest.mark.asyncio
    async def test_handle_event_pre_tool_use(self):
        """测试 PreToolUse 事件"""
        from src.hook_handler import handle_event
        from src.interfaces.hook_handler import ClaudeHookHandler, HookContext, HookEventType

        handler = ClaudeHookHandler()
        context = HookContext(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="AskUserQuestion",
            tool_input={"questions": [{"question": "测试?", "options": [{"label": "A"}]}]}
        )
        data = {"timestamp": "2024-01-01"}

        with patch('src.hook_handler.send_feishu_notification', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = "msg_id"
            with patch('src.hook_handler.send_escape_to_tmux', return_value=True) as mock_escape:
                with patch('src.hook_handler.log_event'):
                    await handle_event(handler, context, data)

                    mock_escape.assert_called_once()
                    mock_send.assert_called()

    @pytest.mark.asyncio
    async def test_handle_event_notification(self):
        """测试 Notification 事件"""
        from src.hook_handler import handle_event
        from src.interfaces.hook_handler import ClaudeHookHandler, HookContext, HookEventType

        handler = ClaudeHookHandler()
        context = HookContext(
            event_type=HookEventType.NOTIFICATION,
            notification_message="通知消息"
        )
        data = {"timestamp": "2024-01-01"}

        with patch('src.hook_handler.send_feishu_notification', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = "msg_id"
            with patch('src.hook_handler.log_event'):
                await handle_event(handler, context, data)

                mock_send.assert_called_once_with("通知消息", "permission", "Notification")


class TestBuildPermissionRequestMessage:
    """测试 build_permission_request_message 函数"""

    def test_build_permission_request_message_basic(self):
        """测试基本权限请求消息"""
        from src.hook_handler import build_permission_request_message

        with patch('src.hook_handler.get_tmux_last_lines', return_value="output"):
            message = build_permission_request_message("Bash", {"command": "ls"})

            assert "屏幕内容" in message


class TestUploadAndSendFile:
    """测试 _upload_and_send_file 函数"""

    @pytest.mark.asyncio
    async def test_upload_and_send_file_success(self):
        """测试上传发送文件成功"""
        from src.hook_handler import _upload_and_send_file

        mock_feishu = Mock()
        mock_feishu.upload_file = AsyncMock(return_value="file_key_123")
        mock_feishu.send_file_message = AsyncMock(return_value=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.hook_handler.PROJECT_ROOT', Path(tmpdir)):
                with patch('src.hook_handler.get_settings') as mock_settings:
                    mock_settings.return_value.FILE_UPLOAD_TYPE = "stream"

                    await _upload_and_send_file(mock_feishu, "user_123", "file content")

                    mock_feishu.upload_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_and_send_file_upload_error(self):
        """测试上传文件错误"""
        from src.hook_handler import _upload_and_send_file
        from src.feishu.exceptions import FeishuAPIError

        mock_feishu = Mock()
        mock_feishu.upload_file = AsyncMock(side_effect=FeishuAPIError("upload failed"))

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.hook_handler.PROJECT_ROOT', Path(tmpdir)):
                with patch('src.hook_handler.get_settings') as mock_settings:
                    mock_settings.return_value.FILE_UPLOAD_TYPE = "stream"

                    # 应该不抛出异常
                    await _upload_and_send_file(mock_feishu, "user_123", "file content")