"""
AI 助手工厂单元测试
"""
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

# 添加项目根目录到路径
import sys
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.factories.assistant_factory import AIAssistantFactory
from src.interfaces.ai_assistant import AssistantType, AssistantConfig


class MockAIAssistant:
    """Mock AI 助手实现"""

    def __init__(self, config: AssistantConfig):
        self.config = config

    def execute(self, command: str):
        return "mock result"


class TestAIAssistantFactory:
    """测试 AI 助手工厂"""

    def setup_method(self):
        """设置测试环境"""
        # 清空注册表
        AIAssistantFactory._assistants = {}

    def test_register_assistant(self):
        """测试注册助手"""
        AIAssistantFactory.register_assistant(
            AssistantType.DEFAULT,
            MockAIAssistant
        )

        assert AIAssistantFactory.is_assistant_registered(AssistantType.DEFAULT)
        assert AssistantType.DEFAULT in AIAssistantFactory._assistants

    def test_create_assistant(self):
        """测试创建助手实例"""
        AIAssistantFactory.register_assistant(
            AssistantType.DEFAULT,
            MockAIAssistant
        )

        config = AssistantConfig(
            assistant_type=AssistantType.DEFAULT,
            workspace=Path("/tmp/workspace")
        )

        assistant = AIAssistantFactory.create_assistant(
            AssistantType.DEFAULT,
            config
        )

        assert assistant is not None
        assert isinstance(assistant, MockAIAssistant)
        assert assistant.config == config

    def test_create_assistant_unregistered_type(self):
        """测试创建未注册类型的助手"""
        config = AssistantConfig(
            assistant_type=AssistantType.CLAUDE_CODE,
            workspace=Path("/tmp/workspace")
        )

        assistant = AIAssistantFactory.create_assistant(
            AssistantType.CLAUDE_CODE,  # 未注册
            config
        )

        assert assistant is None

    def test_create_assistant_by_name(self):
        """测试通过名称创建助手"""
        AIAssistantFactory.register_assistant(
            AssistantType.DEFAULT,
            MockAIAssistant
        )

        config = AssistantConfig(
            assistant_type=AssistantType.DEFAULT,
            workspace=Path("/tmp/workspace")
        )

        assistant = AIAssistantFactory.create_assistant_by_name(
            "default",
            config
        )

        assert assistant is not None

    def test_create_assistant_by_invalid_name(self):
        """测试通过无效名称创建助手"""
        config = AssistantConfig(
            assistant_type=AssistantType.DEFAULT,
            workspace=Path("/tmp/workspace")
        )

        assistant = AIAssistantFactory.create_assistant_by_name(
            "invalid_type",
            config
        )

        assert assistant is None

    def test_get_registered_assistants(self):
        """测试获取已注册的助手列表"""
        AIAssistantFactory.register_assistant(AssistantType.DEFAULT, MockAIAssistant)

        registered = AIAssistantFactory.get_registered_assistants()

        assert isinstance(registered, list)
        assert "default" in registered

    def test_is_assistant_registered_true(self):
        """测试检查已注册的助手"""
        AIAssistantFactory.register_assistant(AssistantType.DEFAULT, MockAIAssistant)

        assert AIAssistantFactory.is_assistant_registered(AssistantType.DEFAULT) is True

    def test_is_assistant_registered_false(self):
        """测试检查未注册的助手"""
        assert AIAssistantFactory.is_assistant_registered(AssistantType.CLAUDE_CODE) is False

    def test_unregister_assistant(self):
        """测试注销助手"""
        AIAssistantFactory.register_assistant(AssistantType.DEFAULT, MockAIAssistant)

        result = AIAssistantFactory.unregister_assistant(AssistantType.DEFAULT)

        assert result is True
        assert not AIAssistantFactory.is_assistant_registered(AssistantType.DEFAULT)

    def test_unregister_assistant_not_exists(self):
        """测试注销不存在的助手"""
        result = AIAssistantFactory.unregister_assistant(AssistantType.CLAUDE_CODE)

        assert result is False

    def test_register_multiple_assistants(self):
        """测试注册多个助手"""
        AIAssistantFactory.register_assistant(AssistantType.DEFAULT, MockAIAssistant)

        # 注册第二个助手
        class AnotherAssistant:
            def __init__(self, config):
                self.config = config

        AIAssistantFactory.register_assistant(AssistantType.CLAUDE_CODE, AnotherAssistant)

        registered = AIAssistantFactory.get_registered_assistants()
        assert len(registered) >= 2

    def test_create_assistant_with_exception(self):
        """测试创建助手时抛出异常"""
        class FailingAssistant:
            def __init__(self, config):
                raise RuntimeError("Failed to initialize")

        AIAssistantFactory.register_assistant(AssistantType.DEFAULT, FailingAssistant)

        config = AssistantConfig(
            assistant_type=AssistantType.DEFAULT,
            workspace=Path("/tmp/workspace")
        )

        assistant = AIAssistantFactory.create_assistant(AssistantType.DEFAULT, config)

        assert assistant is None