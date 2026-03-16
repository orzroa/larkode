"""
AI Executor 更多测试 - 提升覆盖率
"""
import os
import subprocess
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock

import pytest

from src.ai_executor import TmuxAIExecutor


class TestTmuxAIExecutorWorkspace:
    """测试工作空间获取逻辑"""

    def test_get_current_workspace_from_workspace_manager(self):
        """测试从 WorkspaceManager 获取工作空间"""
        executor = TmuxAIExecutor()

        with patch('src.workspace_manager.get_workspace_manager') as mock_get_wm:
            mock_wm = Mock()
            mock_wm.get_current_workspace.return_value = "/home/user/project"
            mock_get_wm.return_value = mock_wm

            workspace = executor._get_current_workspace()

            assert workspace == Path("/home/user/project")

    def test_get_current_workspace_empty_from_manager(self):
        """测试 WorkspaceManager 返回空值"""
        executor = TmuxAIExecutor()

        with patch('src.workspace_manager.get_workspace_manager') as mock_get_wm:
            mock_wm = Mock()
            mock_wm.get_current_workspace.return_value = None
            mock_get_wm.return_value = mock_wm

            workspace = executor._get_current_workspace()

            # 应该使用当前工作目录
            assert workspace == Path.cwd()

    def test_get_current_workspace_manager_error(self):
        """测试 WorkspaceManager 抛出异常"""
        executor = TmuxAIExecutor()

        with patch('src.workspace_manager.get_workspace_manager') as mock_get_wm:
            mock_get_wm.side_effect = Exception("WorkspaceManager error")

            workspace = executor._get_current_workspace()

            # 应该使用当前工作目录
            assert workspace == Path.cwd()

    def test_get_current_workspace_with_initial_workspace(self):
        """测试使用初始化时的工作空间"""
        executor = TmuxAIExecutor(workspace=Path("/initial/workspace"))

        with patch('src.workspace_manager.get_workspace_manager') as mock_get_wm:
            mock_wm = Mock()
            mock_wm.get_current_workspace.return_value = None
            mock_get_wm.return_value = mock_wm

            workspace = executor._get_current_workspace()

            # 应该使用初始化时的工作空间
            assert workspace == Path("/initial/workspace")


class TestTmuxAIExecutorSessionMethods:
    """测试 session 相关方法"""

    def test_check_tmux_session(self):
        """测试检查 tmux session"""
        executor = TmuxAIExecutor()

        with patch.object(executor, '_get_session_manager') as mock_get_sm:
            mock_sm = Mock()
            mock_sm._check_tmux_session.return_value = True
            mock_get_sm.return_value = mock_sm

            result = executor._check_tmux_session()

            assert result is True

    def test_check_ai_running_in_session(self):
        """测试检查 AI 是否运行"""
        executor = TmuxAIExecutor()

        with patch.object(executor, '_get_session_manager') as mock_get_sm:
            mock_sm = Mock()
            mock_sm._check_ai_running_in_session.return_value = True
            mock_get_sm.return_value = mock_sm

            result = executor._check_ai_running_in_session()

            assert result is True

    def test_create_tmux_session(self):
        """测试创建 tmux session"""
        executor = TmuxAIExecutor()

        with patch.object(executor, '_get_session_manager') as mock_get_sm:
            mock_sm = Mock()
            mock_sm._create_tmux_session.return_value = True
            mock_get_sm.return_value = mock_sm

            result = executor._create_tmux_session()

            assert result is True

    def test_ensure_tmux_session(self):
        """测试确保 tmux session 存在"""
        executor = TmuxAIExecutor()

        with patch.object(executor, '_get_session_manager') as mock_get_sm:
            mock_sm = Mock()
            mock_sm._ensure_tmux_session.return_value = (True, False)
            mock_get_sm.return_value = mock_sm

            success, just_started = executor._ensure_tmux_session()

            assert success is True
            assert just_started is False

    def test_start_ai_in_existing_session(self):
        """测试在现有 session 中启动 AI"""
        executor = TmuxAIExecutor()

        with patch.object(executor, '_get_session_manager') as mock_get_sm:
            mock_sm = Mock()
            mock_sm._start_ai_in_existing_session.return_value = True
            mock_get_sm.return_value = mock_sm

            result = executor._start_ai_in_existing_session()

            assert result is True


class TestTmuxAIExecutorCheckHealth:
    """测试进程健康检查"""

    def test_check_ai_process_health_no_process(self):
        """测试没有进程时的健康检查"""
        executor = TmuxAIExecutor()

        with patch.object(executor, '_get_session_manager') as mock_get_sm:
            mock_sm = Mock()
            mock_sm.session_name = "test-session"
            mock_sm._check_ai_running_in_session.return_value = False
            mock_get_sm.return_value = mock_sm

            result = executor._check_ai_process_health()

            assert result is False

    def test_check_ai_process_health_process_running(self):
        """测试进程正在运行的健康检查"""
        executor = TmuxAIExecutor()

        with patch.object(executor, '_get_session_manager') as mock_get_sm:
            mock_sm = Mock()
            mock_sm.session_name = "test-session"
            mock_sm._check_tmux_session.return_value = True
            mock_sm._check_ai_running_in_session.return_value = True
            mock_get_sm.return_value = mock_sm

            result = executor._check_ai_process_health()

            # tmux session 存在且 AI 正在运行，返回 True
            assert result is True

    def test_monitor_and_restart_disabled(self):
        """测试自动重启未启用"""
        executor = TmuxAIExecutor()

        with patch('src.ai_executor.get_settings') as mock_settings:
            mock_settings.return_value.AI_AUTO_RESTART_ENABLED = False

            result = executor._monitor_and_restart_if_needed()

            assert result is False

    def test_monitor_and_restart_health_process(self):
        """测试进程健康时重启"""
        executor = TmuxAIExecutor()

        with patch('src.ai_executor.get_settings') as mock_settings:
            mock_settings.return_value.AI_AUTO_RESTART_ENABLED = True

            with patch.object(executor, '_check_ai_process_health', return_value=True):
                result = executor._monitor_and_restart_if_needed()

                # 进程健康，重置重启计数
                assert result is False
                assert executor._restart_count == 0

    def test_monitor_and_restart_max_attempts(self):
        """测试达到最大重启次数"""
        executor = TmuxAIExecutor()
        executor._restart_count = 10  # Set to max

        with patch('src.ai_executor.get_settings') as mock_settings:
            mock_settings.return_value.AI_AUTO_RESTART_ENABLED = True

            with patch.object(executor, '_check_ai_process_health', return_value=False):
                result = executor._monitor_and_restart_if_needed()

                assert result is False

    def test_monitor_and_restart_success(self):
        """测试重启成功"""
        executor = TmuxAIExecutor()
        executor._restart_count = 0

        with patch('src.ai_executor.get_settings') as mock_settings:
            mock_settings.return_value.AI_AUTO_RESTART_ENABLED = True

            with patch.object(executor, '_check_ai_process_health', return_value=False):
                with patch.object(executor, '_ensure_tmux_session', return_value=(True, True)):
                    with patch('src.ai_executor.time.sleep'):
                        result = executor._monitor_and_restart_if_needed()

                        assert result is True
                        assert executor._restart_count == 1

    def test_monitor_and_restart_failure(self):
        """测试重启失败"""
        executor = TmuxAIExecutor()
        executor._restart_count = 0

        with patch('src.ai_executor.get_settings') as mock_settings:
            mock_settings.return_value.AI_AUTO_RESTART_ENABLED = True

            with patch.object(executor, '_check_ai_process_health', return_value=False):
                with patch.object(executor, '_ensure_tmux_session', return_value=(False, False)):
                    with patch('src.ai_executor.time.sleep'):
                        result = executor._monitor_and_restart_if_needed()

                        assert result is False


class TestTmuxAIExecutorCancelAndStatus:
    """测试取消和状态检查"""

    def test_cancel_task(self):
        """测试取消任务"""
        executor = TmuxAIExecutor()

        result = executor.cancel_task("test-task-id")

        # tmux 模式下返回 False
        assert result is False

    def test_is_task_running(self):
        """测试任务是否在运行"""
        executor = TmuxAIExecutor()

        result = executor.is_task_running("test-task-id")

        # tmux 模式下返回 False
        assert result is False


class TestTmuxAIExecutorExecuteStreaming:
    """测试流式执行"""

    @pytest.mark.asyncio
    async def test_execute_streaming_create_session_failure(self):
        """测试流式模式创建 session 失败"""
        executor = TmuxAIExecutor()

        with patch('src.ai_executor.get_settings') as mock_settings:
            mock_settings.return_value.AI_AUTO_RESTART_ENABLED = True

            # Mock workspace to return existing path
            with patch.object(executor, '_get_current_workspace', return_value=Path("/tmp")):
                with patch('src.ai_executor.TmuxSessionManager') as mock_tmux_class:
                    mock_sm = Mock()
                    mock_sm._ensure_tmux_session.return_value = (False, False)
                    mock_tmux_class.return_value = mock_sm

                    streaming_manager = Mock()

                    outputs = []
                    async for output in executor.execute_command(
                        "test command",
                        streaming=True,
                        streaming_manager=streaming_manager,
                        user_id="test-user"
                    ):
                        outputs.append(output)

                    # 应该有错误输出
                    assert len(outputs) > 0
                    assert "错误" in outputs[0]

    @pytest.mark.asyncio
    async def test_execute_streaming_just_started(self):
        """测试流式模式刚启动 AI"""
        executor = TmuxAIExecutor()

        with patch('src.ai_executor.get_settings') as mock_settings:
            mock_settings.return_value.AI_AUTO_RESTART_ENABLED = True
            mock_settings.return_value.streaming_timeout = 60

            # Mock workspace to return existing path
            with patch.object(executor, '_get_current_workspace', return_value=Path("/tmp")):
                with patch('src.ai_executor.TmuxSessionManager') as mock_tmux_class:
                    mock_sm = Mock()
                    mock_sm._ensure_tmux_session.return_value = (True, True)
                    mock_sm.send_command = AsyncMock(return_value=async_generator([]))
                    mock_sm.monitor_output = AsyncMock(return_value="output")
                    mock_tmux_class.return_value = mock_sm

                    streaming_manager = Mock()
                    streaming_manager.start_streaming = AsyncMock(return_value="card-id")
                    streaming_manager.update_content = AsyncMock()
                    streaming_manager.finish_streaming = AsyncMock()
                    streaming_manager.register_monitor_task = Mock()

                    outputs = []
                    async for output in executor.execute_command(
                        "test command",
                        streaming=True,
                        streaming_manager=streaming_manager,
                        user_id="test-user"
                    ):
                        outputs.append(output)

                    # 应该有启动提示
                    assert len(outputs) > 0
                    assert "自动启动" in outputs[0]

    @pytest.mark.asyncio
    async def test_execute_streaming_exception(self):
        """测试流式模式异常"""
        executor = TmuxAIExecutor()

        with patch('src.ai_executor.get_settings') as mock_settings:
            mock_settings.return_value.AI_AUTO_RESTART_ENABLED = True
            mock_settings.return_value.streaming_timeout = 60

            # Mock workspace to return existing path
            with patch.object(executor, '_get_current_workspace', return_value=Path("/tmp")):
                with patch('src.ai_executor.TmuxSessionManager') as mock_tmux_class:
                    mock_sm = Mock()
                    mock_sm._ensure_tmux_session.return_value = (True, False)
                    mock_sm.send_command = AsyncMock(side_effect=Exception("Command error"))
                    mock_tmux_class.return_value = mock_sm

                    streaming_manager = Mock()
                    streaming_manager.start_streaming = AsyncMock(return_value="card-id")

                    outputs = []
                    async for output in executor.execute_command(
                        "test command",
                        streaming=True,
                        streaming_manager=streaming_manager,
                        user_id="test-user"
                    ):
                        outputs.append(output)

                    # 应该有错误输出
                    assert len(outputs) > 0
                    assert "出错" in outputs[-1]

    @pytest.mark.asyncio
    async def test_execute_streaming_no_auto_restart(self):
        """测试流式模式无自动重启"""
        executor = TmuxAIExecutor()

        with patch('src.ai_executor.get_settings') as mock_settings:
            mock_settings.return_value.AI_AUTO_RESTART_ENABLED = False
            mock_settings.return_value.streaming_timeout = 60

            with patch('src.ai_executor.TmuxSessionManager') as mock_tmux_class:
                mock_sm = Mock()
                mock_sm.send_command = AsyncMock(return_value=async_generator([]))
                mock_sm.monitor_output = AsyncMock(return_value="output")
                mock_tmux_class.return_value = mock_sm

                streaming_manager = Mock()
                streaming_manager.start_streaming = AsyncMock(return_value="card-id")
                streaming_manager.update_content = AsyncMock()
                streaming_manager.finish_streaming = AsyncMock()
                streaming_manager.register_monitor_task = Mock()

                outputs = []
                async for output in executor.execute_command(
                    "test command",
                    streaming=True,
                    streaming_manager=streaming_manager,
                    user_id="test-user"
                ):
                    outputs.append(output)

                # 应该有输出
                assert len(outputs) > 0

    @pytest.mark.asyncio
    async def test_execute_streaming_card_creation_failed(self):
        """测试流式模式卡片创建失败"""
        executor = TmuxAIExecutor()

        with patch('src.ai_executor.get_settings') as mock_settings:
            mock_settings.return_value.AI_AUTO_RESTART_ENABLED = False

            # Mock workspace to return existing path
            with patch.object(executor, '_get_current_workspace', return_value=Path("/tmp")):
                with patch('src.ai_executor.TmuxSessionManager') as mock_tmux_class:
                    mock_sm = Mock()
                    mock_sm.send_command = AsyncMock(return_value=async_generator(["output"]))
                    mock_tmux_class.return_value = mock_sm

                    streaming_manager = Mock()
                    streaming_manager.start_streaming = AsyncMock(return_value=None)  # Card creation failed

                    outputs = []
                    async for output in executor.execute_command(
                        "test command",
                        streaming=True,
                        streaming_manager=streaming_manager,
                        user_id="test-user"
                    ):
                        outputs.append(output)

                    # 应该有输出（降级到传统模式）
                    assert len(outputs) > 0

    @pytest.mark.asyncio
    async def test_execute_streaming_success_with_card(self):
        """测试流式模式成功创建卡片"""
        executor = TmuxAIExecutor()

        async def mock_monitor_output(callback, timeout):
            """Mock monitor_output that calls the callback"""
            await callback("test output", False)
            await callback("final output", True)
            return "final output"

        with patch('src.ai_executor.get_settings') as mock_settings:
            mock_settings.return_value.AI_AUTO_RESTART_ENABLED = False
            mock_settings.return_value.streaming_timeout = 60

            # Mock workspace to return existing path
            with patch.object(executor, '_get_current_workspace', return_value=Path("/tmp")):
                with patch('src.ai_executor.TmuxSessionManager') as mock_tmux_class:
                    mock_sm = Mock()
                    mock_sm._ensure_tmux_session.return_value = (True, False)
                    mock_sm.send_command = Mock(return_value=async_generator([]))
                    mock_sm.monitor_output = mock_monitor_output
                    mock_tmux_class.return_value = mock_sm

                    streaming_manager = Mock()
                    streaming_manager.start_streaming = AsyncMock(return_value="card-123")
                    streaming_manager.update_content = AsyncMock()
                    streaming_manager.finish_streaming = AsyncMock()
                    streaming_manager.register_monitor_task = Mock()

                    outputs = []
                    async for output in executor.execute_command(
                        "test command",
                        streaming=True,
                        streaming_manager=streaming_manager,
                        user_id="test-user"
                    ):
                        outputs.append(output)

                    # 应该有输出
                    assert len(outputs) > 0
                    # 应该有命令发送提示
                    assert any("命令已发送" in output for output in outputs)


class TestTmuxAIExecutorExecuteTraditional:
    """测试传统执行模式"""

    @pytest.mark.asyncio
    async def test_execute_traditional_create_session_failure(self):
        """测试传统模式创建 session 失败"""
        executor = TmuxAIExecutor()

        with patch('src.ai_executor.get_settings') as mock_settings:
            mock_settings.return_value.AI_AUTO_RESTART_ENABLED = True

            # Mock workspace to return existing path
            with patch.object(executor, '_get_current_workspace', return_value=Path("/tmp")):
                with patch('src.ai_executor.TmuxSessionManager') as mock_tmux_class:
                    mock_sm = Mock()
                    mock_sm._ensure_tmux_session.return_value = (False, False)
                    mock_tmux_class.return_value = mock_sm

                    outputs = []
                    async for output in executor.execute_command("test command"):
                        outputs.append(output)

                    # 应该有错误输出
                    assert len(outputs) > 0
                    assert "错误" in outputs[0]

    @pytest.mark.asyncio
    async def test_execute_traditional_just_started(self):
        """测试传统模式刚启动 AI"""
        executor = TmuxAIExecutor()

        with patch('src.ai_executor.get_settings') as mock_settings:
            mock_settings.return_value.AI_AUTO_RESTART_ENABLED = True

            # Mock workspace to return existing path
            with patch.object(executor, '_get_current_workspace', return_value=Path("/tmp")):
                with patch('src.ai_executor.TmuxSessionManager') as mock_tmux_class:
                    mock_sm = Mock()
                    mock_sm._ensure_tmux_session.return_value = (True, True)
                    mock_sm.send_command = AsyncMock(return_value=async_generator(["output"]))
                    mock_tmux_class.return_value = mock_sm

                    outputs = []
                    async for output in executor.execute_command("test command"):
                        outputs.append(output)

                    # 应该有启动提示
                    assert len(outputs) > 0
                    assert "自动启动" in outputs[0]

    @pytest.mark.asyncio
    async def test_execute_traditional_long_output(self):
        """测试传统模式长输出截断"""
        executor = TmuxAIExecutor()

        with patch('src.ai_executor.TmuxSessionManager') as mock_tmux_class:
            mock_sm = Mock()
            mock_sm.send_command = AsyncMock(return_value=async_generator(["a" * 2000]))
            mock_tmux_class.return_value = mock_sm

            with patch('src.ai_executor.get_settings') as mock_settings:
                mock_settings.return_value.CARD_MAX_LENGTH = 1500

                outputs = []
                async for output in executor.execute_command("test command"):
                    outputs.append(output)

                # 应该有输出
                assert len(outputs) > 0

    @pytest.mark.asyncio
    async def test_execute_traditional_exception(self):
        """测试传统模式异常"""
        executor = TmuxAIExecutor()

        # Mock workspace to return existing path
        with patch.object(executor, '_get_current_workspace', return_value=Path("/tmp")):
            with patch('src.ai_executor.TmuxSessionManager') as mock_tmux_class:
                mock_sm = Mock()
                mock_sm.send_command = AsyncMock(side_effect=Exception("Command error"))
                mock_tmux_class.return_value = mock_sm

                outputs = []
                async for output in executor.execute_command("test command"):
                    outputs.append(output)

                # 应该有错误输出
                assert len(outputs) > 0
                assert "出错" in outputs[-1]

    @pytest.mark.asyncio
    async def test_execute_traditional_no_auto_restart(self):
        """测试传统模式无自动重启"""
        executor = TmuxAIExecutor()

        with patch('src.ai_executor.get_settings') as mock_settings:
            mock_settings.return_value.AI_AUTO_RESTART_ENABLED = False
            mock_settings.return_value.CARD_MAX_LENGTH = 1500

            with patch('src.ai_executor.TmuxSessionManager') as mock_tmux_class:
                mock_sm = Mock()
                mock_sm.send_command = AsyncMock(return_value=async_generator(["output"]))
                mock_tmux_class.return_value = mock_sm

                outputs = []
                async for output in executor.execute_command("test command"):
                    outputs.append(output)

                # 应该有输出
                assert len(outputs) > 0

    @pytest.mark.asyncio
    async def test_execute_traditional_workspace_not_exist(self):
        """测试工作空间不存在"""
        executor = TmuxAIExecutor()

        # Mock the workspace to return a nonexistent path
        with patch.object(executor, '_get_current_workspace', return_value=Path("/nonexistent/workspace")):
            outputs = []
            async for output in executor.execute_command("test command"):
                outputs.append(output)

            # 应该有错误输出
            assert len(outputs) > 0
            assert "错误" in outputs[0]


async def async_generator(items):
    """辅助函数：创建异步生成器"""
    for item in items:
        yield item