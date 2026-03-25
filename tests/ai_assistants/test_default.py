"""
测试 Default AI 助手实现
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path
from datetime import datetime

import sys
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestDefaultSessionManager:
    """测试 Default Session 管理器"""

    @pytest.fixture
    def mock_config(self):
        """创建模拟配置"""
        from src.interfaces.ai_assistant import AssistantConfig, AssistantType
        return AssistantConfig(
            assistant_type=AssistantType.DEFAULT,
            workspace=Path("/tmp/test"),
            cli_path="claude"
        )

    @pytest.fixture
    def session_manager(self, mock_config):
        """创建 Session 管理器实例"""
        from src.ai_assistants.default import DefaultSessionManager
        with patch('src.ai_assistants.default.AISessionManager'):
            return DefaultSessionManager(mock_config)

    def test_init(self, mock_config):
        """测试初始化"""
        with patch('src.ai_assistants.default.AISessionManager'):
            from src.ai_assistants.default import DefaultSessionManager
            manager = DefaultSessionManager(mock_config)
            assert manager.config == mock_config

    def test_find_running_session_success(self, session_manager):
        """测试查找运行中的会话 - 成功"""
        session_manager._session_manager.find_running_session = Mock(return_value="session_123")

        with patch('src.workspace_manager.get_workspace_manager') as mock_wm:
            mock_wm.return_value.get_current_workspace.return_value = "/tmp/test"

            result = session_manager.find_running_session()

            assert result is not None
            assert result.session_id == "session_123"

    def test_find_running_session_no_session(self, session_manager):
        """测试查找运行中的会话 - 无会话"""
        session_manager._session_manager.find_running_session = Mock(return_value=None)

        result = session_manager.find_running_session()

        assert result is None

    def test_find_running_session_exception(self, session_manager):
        """测试查找运行中的会话 - 异常"""
        session_manager._session_manager.find_running_session = Mock(
            side_effect=Exception("test error")
        )

        result = session_manager.find_running_session()

        assert result is None

    def test_ensure_session_success(self, session_manager):
        """测试确保会话 - 成功"""
        session_manager._session_manager.get_session = Mock(return_value="session_123")

        with patch('src.workspace_manager.get_workspace_manager') as mock_wm:
            mock_wm.return_value.get_current_workspace.return_value = "/tmp/test"

            result = session_manager.ensure_session()

            assert result is not None
            assert result.session_id == "session_123"

    def test_ensure_session_no_session(self, session_manager):
        """测试确保会话 - 无会话"""
        session_manager._session_manager.get_session = Mock(return_value=None)

        result = session_manager.ensure_session()

        assert result is None

    def test_ensure_session_exception(self, session_manager):
        """测试确保会话 - 异常"""
        session_manager._session_manager.get_session = Mock(
            side_effect=Exception("test error")
        )

        result = session_manager.ensure_session()

        assert result is None


class TestDefaultAIInterface:
    """测试 Default AI 接口"""

    @pytest.fixture
    def mock_config(self):
        """创建模拟配置"""
        from src.interfaces.ai_assistant import AssistantConfig, AssistantType
        return AssistantConfig(
            assistant_type=AssistantType.DEFAULT,
            workspace=Path("/tmp/test"),
            cli_path="claude"
        )

    @pytest.fixture
    def ai_interface(self, mock_config):
        """创建 AI 接口实例"""
        with patch('src.ai_assistants.default.TmuxAIExecutor'), \
             patch('src.ai_assistants.default.AISessionManager'), \
             patch('src.ai_assistants.default.get_settings') as mock_settings:
            mock_settings.return_value.STREAMING_OUTPUT_ENABLED = False
            from src.ai_assistants.default import DefaultAIInterface
            return DefaultAIInterface(mock_config)

    def test_init(self, mock_config):
        """测试初始化"""
        with patch('src.ai_assistants.default.TmuxAIExecutor'), \
             patch('src.ai_assistants.default.AISessionManager'), \
             patch('src.ai_assistants.default.get_settings') as mock_settings:
            mock_settings.return_value.STREAMING_OUTPUT_ENABLED = False
            from src.ai_assistants.default import DefaultAIInterface
            interface = DefaultAIInterface(mock_config)
            assert interface.config == mock_config

    def test_init_with_tmux_disabled(self, mock_config):
        """测试初始化 - 禁用 tmux"""
        with patch('src.ai_assistants.default.TmuxAIExecutor') as mock_executor, \
             patch('src.ai_assistants.default.AISessionManager'), \
             patch('src.ai_assistants.default.get_settings') as mock_settings:
            mock_settings.return_value.STREAMING_OUTPUT_ENABLED = False
            from src.ai_assistants.default import DefaultAIInterface
            interface = DefaultAIInterface(mock_config, use_tmux_executor=False)
            assert interface.use_tmux_executor is False

    @pytest.mark.asyncio
    async def test_execute_command_success(self, ai_interface):
        """测试执行命令 - 成功"""
        ai_interface.executor.execute_command = MagicMock()
        ai_interface.executor.execute_command.return_value = AsyncMock()

        async def mock_gen():
            yield "output1"
            yield "output2"

        ai_interface.executor.execute_command.return_value = mock_gen()

        results = []
        async for output in ai_interface.execute_command("test command"):
            results.append(output)

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_execute_command_with_streaming(self, ai_interface):
        """测试执行命令 - 带流式输出"""
        with patch('src.ai_assistants.default.get_settings') as mock_settings, \
             patch('src.streaming_output.create_streaming_manager') as mock_create:
            mock_settings.return_value.STREAMING_OUTPUT_ENABLED = True
            mock_create.return_value = Mock()

            async def mock_gen():
                yield "output"

            ai_interface.executor.execute_command = Mock(return_value=mock_gen())

            results = []
            async for output in ai_interface.execute_command("test command", "user_123"):
                results.append(output)

            assert len(results) == 1

    @pytest.mark.asyncio
    async def test_execute_command_exception(self, ai_interface):
        """测试执行命令 - 异常"""
        async def mock_gen():
            yield "output1"
            raise Exception("test error")

        ai_interface.executor.execute_command = Mock(return_value=mock_gen())

        results = []
        async for output in ai_interface.execute_command("test command"):
            results.append(output)

        # 应该有输出和错误消息
        assert len(results) >= 1
        assert "执行出错" in results[-1]

    def test_cancel_success(self, ai_interface):
        """测试取消 - 成功"""
        ai_interface.executor.cancel_task = Mock(return_value=True)

        result = ai_interface.cancel()

        assert result is True

    def test_cancel_exception(self, ai_interface):
        """测试取消 - 异常"""
        ai_interface.executor.cancel_task = Mock(side_effect=Exception("test error"))

        result = ai_interface.cancel()

        assert result is False

    def test_get_status_success(self, ai_interface):
        """测试获取状态 - 成功"""
        from src.interfaces.ai_assistant import SessionInfo, SessionStatus
        mock_session = SessionInfo(
            session_id="session_123",
            status=SessionStatus.ACTIVE,
            workspace=Path("/tmp/test")
        )
        ai_interface.session_manager.find_running_session = Mock(return_value=mock_session)

        with patch('src.workspace_manager.get_workspace_manager') as mock_wm:
            mock_wm.return_value.get_current_workspace.return_value = "/tmp/test"

            status = ai_interface.get_status()

            assert status["assistant_type"] == "default"
            assert "workspace" in status

    def test_get_status_exception(self, ai_interface):
        """测试获取状态 - 异常"""
        ai_interface.session_manager.find_running_session = Mock(
            side_effect=Exception("test error")
        )

        status = ai_interface.get_status()

        assert "error" in status


class TestRegisterDefaultAssistant:
    """测试注册 Default 助手"""

    def test_register_default_assistant(self):
        """测试注册助手"""
        from src.ai_assistants.default import register_default_assistant
        from src.factories.assistant_factory import AIAssistantFactory, AssistantType

        # 先清理可能已存在的注册
        AIAssistantFactory.unregister_assistant(AssistantType.DEFAULT)
        AIAssistantFactory.unregister_assistant(AssistantType.CLAUDE_CODE)

        register_default_assistant()

        assert AIAssistantFactory.is_assistant_registered(AssistantType.DEFAULT)
        assert AIAssistantFactory.is_assistant_registered(AssistantType.CLAUDE_CODE)


class TestImportFallback:
    """测试导入回退"""

    def test_import_fallback_logging(self):
        """测试日志导入回退"""
        # 这个测试验证当 src.logging_utils 不可用时的回退
        import importlib
        import sys

        # 保存原始模块
        original_logging_utils = sys.modules.get('src.logging_utils')

        try:
            # 移除模块以触发回退
            if 'src.logging_utils' in sys.modules:
                del sys.modules['src.logging_utils']

            # 重新导入应该触发回退
            import src.ai_assistants.default as default_module
            importlib.reload(default_module)

            # 如果到达这里说明回退成功
            assert True

        finally:
            # 恢复原始模块
            if original_logging_utils:
                sys.modules['src.logging_utils'] = original_logging_utils