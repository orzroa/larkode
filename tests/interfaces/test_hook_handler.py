#!/usr/bin/env python3
"""Claude Code Hook Handler 测试。"""
import pytest
import os
import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.interfaces.hook_handler import (
    IHookHandler,
    ClaudeHookHandler,
    HookEventType,
    HookContext,
    detect_handler,
)


class TestClaudeHookHandler:
    """测试 Claude Code Hook 处理器"""

    def setup_method(self):
        """设置测试环境"""
        self.handler = ClaudeHookHandler()

    def test_name(self):
        """测试处理器名称"""
        # DefaultHookHandler 返回 "default"，向后兼容别名指向同一类
        assert self.handler.name == "default"

    def test_get_session_id_from_env(self):
        """测试从环境变量获取 session ID"""
        with patch.dict(os.environ, {"CLAUDE_SESSION_ID": "test-session-123"}):
            session_id = self.handler.get_session_id()
            assert session_id == "test-session-123"

    def test_get_session_id_empty(self):
        """测试环境变量为空时返回 None"""
        with patch.dict(os.environ, {}, clear=True):
            session_id = self.handler.get_session_id()
            assert session_id is None

    def test_get_cwd_from_env(self):
        """测试从环境变量获取工作目录"""
        with patch.dict(os.environ, {"CLAUDE_CODE_DIR": "/test/project"}):
            cwd = self.handler.get_cwd()
            assert cwd == "/test/project"

    def test_get_cwd_empty(self):
        """测试工作目录环境变量为空时返回 None"""
        with patch.dict(os.environ, {}, clear=True):
            cwd = self.handler.get_cwd()
            assert cwd is None

    def test_parse_stdin_user_prompt(self):
        """测试解析 UserPromptSubmit 事件 stdin"""
        stdin_data = json.dumps({
            "session_id": "session-abc",
            "cwd": "/workspace/project",
            "prompt": "帮我写一个函数"
        })

        with patch.object(sys, 'argv', ['hook', 'UserPromptSubmit']):
            context = self.handler.parse_stdin(stdin_data)

        assert context.event_type == HookEventType.USER_PROMPT_SUBMIT
        assert context.session_id == "session-abc"
        assert context.cwd == "/workspace/project"
        assert context.user_prompt == "帮我写一个函数"

    def test_parse_stdin_stop(self):
        """测试解析 Stop 事件 stdin"""
        stdin_data = json.dumps({
            "session_id": "session-xyz",
            "last_assistant_message": "这是助手回复"
        })

        with patch.object(sys, 'argv', ['hook', 'Stop']):
            context = self.handler.parse_stdin(stdin_data)

        assert context.event_type == HookEventType.STOP
        assert context.session_id == "session-xyz"
        assert context.last_assistant_message == "这是助手回复"

    def test_parse_stdin_empty(self):
        """测试解析空 stdin"""
        with patch.object(sys, 'argv', ['hook']):
            context = self.handler.parse_stdin("")

        # 默认使用 USER_PROMPT_SUBMIT
        assert context.event_type == HookEventType.USER_PROMPT_SUBMIT
        assert context.session_id is None

    def test_parse_stdin_invalid_event(self):
        """测试解析无效事件类型"""
        stdin_data = json.dumps({"session_id": "test"})

        with patch.object(sys, 'argv', ['hook', 'InvalidEvent']):
            context = self.handler.parse_stdin(stdin_data)

        # 无效事件应默认为 USER_PROMPT_SUBMIT
        assert context.event_type == HookEventType.USER_PROMPT_SUBMIT

    def test_should_handle_always_true(self):
        """测试 Claude 处理所有事件"""
        context = HookContext(event_type=HookEventType.USER_PROMPT_SUBMIT)
        assert self.handler.should_handle(context)

        context = HookContext(event_type=HookEventType.STOP)
        assert self.handler.should_handle(context)

        context = HookContext(event_type=HookEventType.NOTIFICATION)
        assert self.handler.should_handle(context)


class TestHookContext:
    """测试 HookContext 数据类"""

    def test_from_dict_claude_format(self):
        """测试从 Claude 格式字典创建上下文"""
        data = {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "test-session",
            "cwd": "/test",
            "prompt": "测试提示",
            "toolName": "Write",
            "toolInput": {"file_path": "test.txt"},
        }

        context = HookContext.from_dict(data)

        assert context.event_type == HookEventType.USER_PROMPT_SUBMIT
        assert context.session_id == "test-session"
        assert context.cwd == "/test"
        assert context.user_prompt == "测试提示"
        assert context.tool_name == "Write"
        assert context.tool_input == {"file_path": "test.txt"}

    def test_from_dict_alternate_field_names(self):
        """测试兼容的事件和工具字段名"""
        data = {
            "hook_event": "Notification",
            "session_id": "alternate-session",
            "notification_message": "交互请求",
            "tool_name": "Bash",
        }

        context = HookContext.from_dict(data)

        assert context.event_type == HookEventType.NOTIFICATION
        assert context.session_id == "alternate-session"
        assert context.notification_message == "交互请求"
        assert context.tool_name == "Bash"

    def test_from_dict_invalid_event(self):
        """测试无效事件类型"""
        data = {
            "hook_event_name": "UnknownEvent",
            "session_id": "test",
        }

        context = HookContext.from_dict(data)

        # 无效事件应默认为 USER_PROMPT_SUBMIT
        assert context.event_type == HookEventType.USER_PROMPT_SUBMIT

    def test_raw_data_preserved(self):
        """测试原始数据被保留"""
        data = {
            "hook_event_name": "Stop",
            "custom_field": "custom_value",
        }

        context = HookContext.from_dict(data)

        assert context.raw_data["custom_field"] == "custom_value"


class TestHookEventType:
    """测试 HookEventType 枚举"""

    def test_event_types(self):
        """测试所有事件类型定义"""
        assert HookEventType.USER_PROMPT_SUBMIT.value == "UserPromptSubmit"
        assert HookEventType.STOP.value == "Stop"
        assert HookEventType.NOTIFICATION.value == "Notification"
        assert HookEventType.PERMISSION_REQUEST.value == "PermissionRequest"

    def test_event_type_from_string(self):
        """测试从字符串创建事件类型"""
        assert HookEventType("UserPromptSubmit") == HookEventType.USER_PROMPT_SUBMIT
        assert HookEventType("Stop") == HookEventType.STOP
        assert HookEventType("Notification") == HookEventType.NOTIFICATION


class TestDetectHandler:
    """测试自动检测处理器"""

    def test_detect_claude_by_default(self):
        """测试默认检测到 Default 处理器"""
        with patch.dict(os.environ, {}, clear=True):
            handler = detect_handler()
            # 默认返回 DefaultHookHandler，name 为 "default"
            assert isinstance(handler, ClaudeHookHandler)  # 向后兼容别名
            assert handler.name == "default"

    def test_claude_env_takes_precedence(self):
        """测试 Claude 环境变量时默认使用 Claude"""
        with patch.dict(os.environ, {"CLAUDE_SESSION_ID": "claude-session"}, clear=True):
            handler = detect_handler()
            assert isinstance(handler, ClaudeHookHandler)
