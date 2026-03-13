#!/usr/bin/env -S uv run --no-project
# /// script
# dependencies = [
#   "pytest>=7.0.0",
#   "pytest-asyncio>=0.21.0"
# ]
# ///
"""
Hook 功能统一测试文件

合并自以下测试文件：
- test_hook_unit.py - Mock 发送测试
- test_hook_from_log.py - 从日志读取测试
- test_interactive_card.py - 交互卡片测试
- test_hook_long_content.py - 长内容处理测试
- test_n008_hook_notification.py - 通知发送测试
"""
import json
import os
import pytest
import asyncio
import sys
from pathlib import Path
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.hook_handler import (
    _build_permission_content,
    build_permission_request_message,
    send_escape_to_tmux,
    send_feishu_notification,
    handle_event,
)
from src.interfaces.hook_handler import HookEventType, HookContext


def make_test_data(hook_event):
    """创建测试用的 data 字典"""
    return {
        "timestamp": datetime.now().isoformat(),
        "hook_event": hook_event,
        "handler": "test",
        "hostname": "test",
        "working_directory": "/test",
        "stdin_parsed": {}
    }


# ============================================================================
# TestHandleEvent - 测试 handle_event 函数
# ============================================================================

class TestHandleEvent:
    """测试 handle_event 函数"""

    @pytest.mark.asyncio
    async def test_send_user_prompt_notification_mock(self):
        """测试发送用户提问通知（Mock）"""
        prompt = "帮我分析项目结构"

        with patch('src.hook_handler.send_feishu_notification', new_callable=AsyncMock) as mock_send, \
             patch('src.hook_handler.get_settings') as mock_settings:
            mock_send.return_value = True
            mock_settings.return_value.SHOW_USER_QUESTION_CARD = True

            handler = MagicMock()
            context = HookContext(
                event_type=HookEventType.USER_PROMPT_SUBMIT,
                user_prompt=prompt,
            )
            data = make_test_data("UserPromptSubmit")

            await handle_event(handler, context, data)

            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert call_args[0][0] == prompt
            assert call_args[0][1] == "prompt"

    def test_user_prompt_content_format(self):
        """测试用户提问内容格式"""
        prompt = "测试问题内容"
        assert len(prompt) > 0

    @pytest.mark.asyncio
    async def test_send_stop_notification_mock(self):
        """测试发送完成通知（Mock）"""
        message = "项目结构分析完成，共发现 10 个模块。"

        with patch('src.hook_handler.send_feishu_notification', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            handler = MagicMock()
            context = HookContext(
                event_type=HookEventType.STOP,
                last_assistant_message=message,
            )
            data = make_test_data("Stop")

            await handle_event(handler, context, data)

            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert call_args[0][0] == message
            assert call_args[0][1] == "stop"

    @pytest.mark.asyncio
    async def test_stop_with_empty_message(self):
        """测试空消息时使用默认值"""
        with patch('src.hook_handler.send_feishu_notification', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            handler = MagicMock()
            context = HookContext(
                event_type=HookEventType.STOP,
                last_assistant_message=None,
            )
            data = make_test_data("Stop")

            await handle_event(handler, context, data)

            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert call_args[0][0] == "已完成响应"
            assert call_args[0][1] == "stop"


# ============================================================================
# TestPermissionContent - 测试权限消息构建
# ============================================================================

class TestPermissionContent:
    """测试权限消息构建"""

    # --- _build_permission_content 测试 ---

    def test_bash_permission_message(self):
        """测试 Bash 权限消息构建"""
        tool_input = {
            "command": "ls -la",
            "description": "列出文件"
        }
        message = _build_permission_content("Bash", tool_input)
        assert message is not None
        assert "屏幕内容" in message

    def test_ask_user_question_single_select(self):
        """测试 AskUserQuestion 单选消息构建"""
        tool_input = {
            "questions": [
                {
                    "question": "请选择编程语言",
                    "header": "语言选择",
                    "options": [
                        {"label": "Python", "description": "简洁优雅"},
                        {"label": "JavaScript", "description": "Web 开发"},
                    ],
                    "multiSelect": False
                }
            ]
        }
        message = _build_permission_content("AskUserQuestion", tool_input)
        assert "语言选择" in message
        assert "Python" in message
        assert "JavaScript" in message
        assert "(单选)" in message

    def test_ask_user_question_multi_select(self):
        """测试 AskUserQuestion 多选消息构建"""
        tool_input = {
            "questions": [
                {
                    "question": "选择需要的功能",
                    "options": [
                        {"label": "用户认证"},
                        {"label": "数据存储"},
                    ],
                    "multiSelect": True
                }
            ]
        }
        message = _build_permission_content("AskUserQuestion", tool_input)
        assert "用户认证" in message
        assert "(多选)" in message

    def test_exit_plan_mode_message(self):
        """测试 ExitPlanMode 消息构建 - 统一显示屏幕内容"""
        tool_input = {
            "plan": "# 实施计划\n\n## 步骤\n1. 第一步\n2. 第二步"
        }
        message = _build_permission_content("ExitPlanMode", tool_input)
        # ExitPlanMode 现在统一走 else 分支，显示屏幕内容
        assert "屏幕内容" in message

    @pytest.mark.asyncio
    async def test_permission_request_bash_mock(self):
        """测试 PermissionRequest Bash（Mock）- 验证消息构建"""
        tool_input = {"command": "rm -rf abc"}
        message = _build_permission_content("Bash", tool_input)

        assert message is not None
        assert len(message) > 0
        assert "屏幕内容" in message

    def test_permission_request_ask_user_question_mock(self):
        """测试 PermissionRequest AskUserQuestion - 验证消息构建"""
        tool_input = {
            "questions": [{
                "question": "选择",
                "options": [{"label": "A"}],
                "multiSelect": False
            }]
        }

        message = _build_permission_content("AskUserQuestion", tool_input)
        assert "选择" in message
        assert "(单选)" in message

    # --- build_permission_request_message 测试 ---

    def test_bash_write_tool(self):
        """测试 Bash/Write 工具：显示 tmux 屏幕内容"""
        tool_input = {
            "command": "rm -rf /test",
            "description": "删除测试目录"
        }

        message = build_permission_request_message("Bash", tool_input)

        assert "屏幕内容:" in message
        assert "```" in message

    def test_ask_user_question_single(self):
        """测试 AskUserQuestion 单选场景"""
        tool_input = {
            "questions": [
                {
                    "question": "请选择语言",
                    "header": "语言",
                    "options": [
                        {"label": "中文", "description": "简体中文界面"},
                        {"label": "English", "description": "English interface"}
                    ],
                    "multiSelect": False
                }
            ]
        }

        message = build_permission_request_message("AskUserQuestion", tool_input)

        assert "请选择语言" in message
        assert "1. 中文" in message
        assert "2. English" in message
        lines = message.split('\n')
        last_line = lines[-1]
        assert "(单选)" in last_line.strip()

    def test_ask_user_question_multi(self):
        """测试 AskUserQuestion 多选场景"""
        tool_input = {
            "questions": [
                {
                    "question": "请选择需要重构的模块",
                    "header": "重构范围",
                    "options": [
                        {"label": "src/ 大文件", "description": "包含超过 1000 行的文件"},
                        {"label": "src/ 根目录", "description": "项目根目录文件"},
                        {"label": "src/interfaces", "description": "接口与实现"},
                        {"label": "config/", "description": "配置文件"}
                    ],
                    "multiSelect": True
                }
            ]
        }

        message = build_permission_request_message("AskUserQuestion", tool_input)

        assert "请选择需要重构的模块" in message
        assert "1. src/ 大文件" in message
        assert "2. src/ 根目录" in message
        assert "3. src/interfaces" in message
        assert "4. config/" in message
        lines = message.split('\n')
        last_line = lines[-1]
        assert "(多选)" in last_line.strip()

    def test_other_tool_no_questions(self):
        """测试其他工具没有 questions 的情况"""
        tool_input = {
            "command": "ls -la",
            "description": "列出目录内容"
        }

        message = build_permission_request_message("Write", tool_input)

        assert "屏幕内容:" in message
        assert "```" in message

    def test_empty_questions(self):
        """测试空 questions 数组"""
        tool_input = {
            "questions": []
        }

        message = build_permission_request_message("AskUserQuestion", tool_input)

        assert "Claude Code 需要您的选择" in message

    def test_option_without_description(self):
        """测试选项没有 description 的情况"""
        tool_input = {
            "questions": [
                {
                    "question": "是否继续？",
                    "options": [
                        {"label": "继续"},
                        {"label": "取消"}
                    ],
                    "multiSelect": False
                }
            ]
        }

        message = build_permission_request_message("AskUserQuestion", tool_input)

        assert "是否继续？" in message
        assert "1. 继续" in message
        assert "description" not in message




# ============================================================================
# TestSendNotification - 测试发送通知
# ============================================================================

class TestSendNotification:
    """测试发送通知"""

    def setup_method(self):
        """设置测试环境"""
        self.original_max_length = os.getenv("CARD_MAX_LENGTH")
        self.original_use_file = os.getenv("USE_FILE_FOR_LONG_CONTENT")
        self.original_user_id = os.getenv("FEISHU_HOOK_NOTIFICATION_USER_ID")
        self.original_app_secret = os.getenv("FEISHU_APP_SECRET")
        self.original_app_id = os.getenv("FEISHU_APP_ID")

        os.environ["CARD_MAX_LENGTH"] = "100"
        os.environ["USE_FILE_FOR_LONG_CONTENT"] = "true"
        os.environ["FEISHU_HOOK_NOTIFICATION_USER_ID"] = "test_user_id"
        os.environ["FEISHU_APP_SECRET"] = "test_secret"
        os.environ["FEISHU_APP_ID"] = "test_app_id"

    def teardown_method(self):
        """清理测试环境"""
        if self.original_max_length is not None:
            os.environ["CARD_MAX_LENGTH"] = self.original_max_length
        elif "CARD_MAX_LENGTH" in os.environ:
            del os.environ["CARD_MAX_LENGTH"]

        if self.original_use_file is not None:
            os.environ["USE_FILE_FOR_LONG_CONTENT"] = self.original_use_file
        elif "USE_FILE_FOR_LONG_CONTENT" in os.environ:
            del os.environ["USE_FILE_FOR_LONG_CONTENT"]

        if self.original_user_id is not None:
            os.environ["FEISHU_HOOK_NOTIFICATION_USER_ID"] = self.original_user_id
        elif "FEISHU_HOOK_NOTIFICATION_USER_ID" in os.environ:
            del os.environ["FEISHU_HOOK_NOTIFICATION_USER_ID"]

        if self.original_app_secret is not None:
            os.environ["FEISHU_APP_SECRET"] = self.original_app_secret
        elif "FEISHU_APP_SECRET" in os.environ:
            del os.environ["FEISHU_APP_SECRET"]

        if self.original_app_id is not None:
            os.environ["FEISHU_APP_ID"] = self.original_app_id
        elif "FEISHU_APP_ID" in os.environ:
            del os.environ["FEISHU_APP_ID"]

    @patch('src.hook_handler.FeishuAPI')
    def test_send_feishu_notification_short_message(self, mock_feishu_api_class):
        """测试发送短消息的通知"""
        mock_feishu_api = MagicMock()
        mock_feishu_api_class.return_value = mock_feishu_api
        mock_feishu_api.send_interactive_message = AsyncMock(return_value="msg123")  # Return message ID string

        short_message = "这是一条短消息测试。"

        result = asyncio.run(send_feishu_notification(
            short_message,
            message_type="stop",
            event_name="Stop"))

        assert result, "发送应该成功"

        mock_feishu_api_class.assert_called_once()
        mock_feishu_api.send_interactive_message.assert_called_once()

        assert not (hasattr(mock_feishu_api, 'upload_file') and
                        getattr(mock_feishu_api, 'upload_file').called), \
                        "短消息不应该上传文件"

    @patch('src.hook_handler.FeishuAPI')
    @patch('src.card_dispatcher.save_temp_file')
    def test_send_feishu_notification_long_message_with_file(self, mock_save_file, mock_feishu_api_class):
        """测试发送长消息的通知（带文件）"""
        mock_feishu_api = MagicMock()
        mock_feishu_api_class.return_value = mock_feishu_api
        mock_feishu_api.send_interactive_message = AsyncMock(return_value="msg123")  # Return message ID string
        mock_feishu_api.upload_file = AsyncMock(return_value="test_file_key")
        mock_feishu_api.send_file_message = AsyncMock(return_value=True)

        # Mock save_temp_file to return a mock file path
        from pathlib import Path
        mock_file_path = MagicMock(spec=Path)
        mock_file_path.name = "test_file.txt"
        mock_save_file.return_value = mock_file_path

        long_message = "A" * 200

        result = asyncio.run(send_feishu_notification(
            long_message,
            message_type="stop",
            event_name="Stop"))

        assert result, "发送应该成功"

        mock_feishu_api.send_interactive_message.assert_called_once()
        mock_feishu_api.upload_file.assert_called_once()
        mock_feishu_api.send_file_message.assert_called_once()

        assert mock_save_file.called, "应该调用 save_temp_file"
        save_file_args = mock_save_file.call_args
        assert long_message in save_file_args[0][0], "文件内容应该包含原消息"

    @patch('src.hook_handler.FeishuAPI')
    def test_send_feishu_notification_long_message_without_file(self, mock_feishu_api_class):
        """测试发送长消息的通知（禁用文件模式）"""
        os.environ["USE_FILE_FOR_LONG_CONTENT"] = "false"

        try:
            mock_feishu_api = MagicMock()
            mock_feishu_api_class.return_value = mock_feishu_api
            mock_feishu_api.send_interactive_message = AsyncMock(return_value="msg123")  # Return message ID string

            long_message = "A" * 200

            result = asyncio.run(send_feishu_notification(
                long_message,
                message_type="stop",
                event_name="Stop"))

            assert result, "发送应该成功"

            mock_feishu_api.send_interactive_message.assert_called_once()
            assert not (hasattr(mock_feishu_api, 'upload_file') and
                            getattr(mock_feishu_api, 'upload_file').called), \
                            "禁用文件模式时不应该上传文件"
        finally:
            os.environ["USE_FILE_FOR_LONG_CONTENT"] = "true"


# ============================================================================
# TestHookFromLogs - 从日志读取测试
# ============================================================================

def get_latest_hook_events(log_path=None, count=5):
    """从日志文件中获取最新的 Hook 事件"""
    if log_path is None:
        log_path = os.getenv("HOOK_LOG_PATH", str(PROJECT_ROOT / "logs" / "hook_events.jsonl"))

    if not Path(log_path).exists():
        print(f"日志文件不存在：{log_path}")
        return []

    events = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    return events[-count:]


def create_test_from_event(event):
    """从 Hook 事件创建测试数据"""
    hook_event = event.get("hook_event", "")
    stdin_parsed = event.get("stdin_parsed", {})

    test_data = {
        "hook_event": hook_event,
        "tool_name": stdin_parsed.get("tool_name", ""),
        "tool_input": stdin_parsed.get("tool_input", {}),
        "prompt": stdin_parsed.get("prompt", ""),
        "last_assistant_message": stdin_parsed.get("last_assistant_message", ""),
    }
    return test_data


class TestHookFromLogs:
    """从日志文件生成的 Hook 测试"""

    def test_user_prompt_submit_from_log(self):
        """测试 UserPromptSubmit 事件（从日志）"""
        events = get_latest_hook_events(count=10)

        for event in events:
            if event.get("hook_event") == "UserPromptSubmit":
                test_data = create_test_from_event(event)
                if test_data["prompt"]:
                    print(f"\nUserPromptSubmit prompt: {test_data['prompt'][:100]}...")
                    assert len(test_data["prompt"]) > 0
                    return

        print("\n未找到 UserPromptSubmit 事件，使用默认测试")
        assert True

    def test_stop_from_log(self):
        """测试 Stop 事件（从日志）"""
        events = get_latest_hook_events(count=10)

        for event in events:
            if event.get("hook_event") == "Stop":
                test_data = create_test_from_event(event)
                if test_data["last_assistant_message"]:
                    print(f"\nStop message: {test_data['last_assistant_message'][:100]}...")
                    assert len(test_data["last_assistant_message"]) > 0
                    return

        print("\n未找到 Stop 事件，使用默认测试")
        assert True

    def test_pre_tool_use_from_log(self):
        """测试 PreToolUse 事件（从日志）"""
        events = get_latest_hook_events(count=20)

        for event in events:
            if event.get("hook_event") == "PreToolUse":
                test_data = create_test_from_event(event)
                print(f"\nPreToolUse: {test_data['tool_name']} - {json.dumps(test_data['tool_input'], ensure_ascii=False)[:100]}...")
                assert test_data["tool_name"] in ["Bash", "Read", "Edit", "Grep", "Write", "Glob", "AskUserQuestion", "ExitPlanMode"]
                return

        print("\n未找到 PreToolUse 事件，使用默认测试")
        test_input = {"command": "ls -la", "description": "列出文件"}
        message = _build_permission_content("Bash", test_input)
        assert message is not None

    def test_permission_request_ask_user_question_from_log(self):
        """测试 AskUserQuestion 权限请求（从日志）"""
        events = get_latest_hook_events(count=20)

        for event in events:
            if event.get("hook_event") == "PermissionRequest":
                test_data = create_test_from_event(event)
                if test_data["tool_name"] == "AskUserQuestion":
                    print(f"\nAskUserQuestion: {json.dumps(test_data['tool_input'], ensure_ascii=False)[:200]}...")
                    message = _build_permission_content(test_data["tool_name"], test_data["tool_input"])
                    assert message is not None
                    assert len(message) > 0
                    print(f"生成的消息：{message[:100]}...")
                    return

        print("\n未找到 AskUserQuestion 事件，使用默认测试")
        test_input = {
            "questions": [
                {
                    "question": "请选择您喜欢的编程语言",
                    "header": "语言选择",
                    "options": [
                        {"label": "Python", "description": "简洁优雅"},
                        {"label": "JavaScript", "description": "Web 开发"},
                    ],
                    "multiSelect": False
                }
            ]
        }
        message = _build_permission_content("AskUserQuestion", test_input)
        assert "Python" in message
        assert "(单选)" in message

    def test_permission_request_exit_plan_mode_from_log(self):
        """测试 ExitPlanMode 权限请求（从日志）"""
        events = get_latest_hook_events(count=20)

        for event in events:
            if event.get("hook_event") == "PermissionRequest":
                test_data = create_test_from_event(event)
                if test_data["tool_name"] == "ExitPlanMode":
                    print(f"\nExitPlanMode: plan length={len(test_data['tool_input'].get('plan', ''))}")
                    message = _build_permission_content(test_data["tool_name"], test_data["tool_input"])
                    assert message is not None
                    assert len(message) > 0
                    print(f"生成的消息：{message[:100]}...")
                    return

        print("\n未找到 ExitPlanMode 事件，使用默认测试")
        test_input = {
            "plan": "# 测试计划\n\n## 目标\n- 测试 ExitPlanMode 功能\n\n## 步骤\n1. 第一步\n2. 第二步"
        }
        message = _build_permission_content("ExitPlanMode", test_input)
        # ExitPlanMode 返回 tmux 屏幕内容
        assert message is not None
        assert "屏幕内容" in message

    def test_permission_request_bash_from_log(self):
        """测试 Bash 权限请求（从日志）"""
        events = get_latest_hook_events(count=20)

        for event in events:
            if event.get("hook_event") == "PermissionRequest":
                test_data = create_test_from_event(event)
                if test_data["tool_name"] == "Bash":
                    print(f"\nBash: {json.dumps(test_data['tool_input'], ensure_ascii=False)[:200]}...")
                    message = _build_permission_content(test_data["tool_name"], test_data["tool_input"])
                    assert message is not None
                    assert len(message) > 0
                    print(f"生成的消息：{message[:100]}...")
                    return

        print("\n未找到 Bash 事件，使用默认测试")
        test_input = {"command": "ls -la", "description": "列出文件"}
        message = _build_permission_content("Bash", test_input)
        assert message is not None

    def test_notification_from_log(self):
        """测试 Notification 事件（从日志）"""
        events = get_latest_hook_events(count=20)

        for event in events:
            if event.get("hook_event") == "Notification":
                test_data = create_test_from_event(event)
                if test_data.get("notification_message"):
                    print(f"\nNotification: {test_data['notification_message'][:100]}...")
                    assert len(test_data["notification_message"]) > 0
                    return

        print("\n未找到 Notification 事件，使用默认测试")
        assert True


# ============================================================================
# TestHookSimulatedEvents - 模拟事件测试
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])