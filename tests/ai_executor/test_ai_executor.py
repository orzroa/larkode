"""
测试 AI 自动重启功能
"""
import pytest
import os
import sys
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
import subprocess

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestAIAutoRestart:
    """测试 AI 自动重启功能"""

    def setup_method(self):
        """设置测试环境"""
        # 保存原始环境变量
        self.original_auto_restart = os.getenv("AI_AUTO_RESTART_ENABLED")
        self.original_max_attempts = os.getenv("AI_MAX_RESTART_ATTEMPTS")
        self.original_restart_delay = os.getenv("AI_RESTART_DELAY")
        self.original_detection_interval = os.getenv("AI_CRASH_DETECTION_INTERVAL")

        # 设置测试环境变量
        os.environ["AI_AUTO_RESTART_ENABLED"] = "true"
        os.environ["AI_MAX_RESTART_ATTEMPTS"] = "3"
        os.environ["AI_RESTART_DELAY"] = "1.0"
        os.environ["AI_CRASH_DETECTION_INTERVAL"] = "0.5"

        # 重新加载配置
        from src.config.settings import reload_settings
        reload_settings()

    def teardown_method(self):
        """清理测试环境"""
        # 恢复原始环境变量
        if self.original_auto_restart is not None:
            os.environ["AI_AUTO_RESTART_ENABLED"] = self.original_auto_restart
        elif "AI_AUTO_RESTART_ENABLED" in os.environ:
            del os.environ["AI_AUTO_RESTART_ENABLED"]

        if self.original_max_attempts is not None:
            os.environ["AI_MAX_RESTART_ATTEMPTS"] = self.original_max_attempts
        elif "AI_MAX_RESTART_ATTEMPTS" in os.environ:
            del os.environ["AI_MAX_RESTART_ATTEMPTS"]

        if self.original_restart_delay is not None:
            os.environ["AI_RESTART_DELAY"] = self.original_restart_delay
        elif "AI_RESTART_DELAY" in os.environ:
            del os.environ["AI_RESTART_DELAY"]

        if self.original_detection_interval is not None:
            os.environ["AI_CRASH_DETECTION_INTERVAL"] = self.original_detection_interval
        elif "AI_CRASH_DETECTION_INTERVAL" in os.environ:
            del os.environ["AI_CRASH_DETECTION_INTERVAL"]

    @patch('src.ai_executor.tmux_session.TmuxSessionManager._log_debug_info')
    @patch('src.ai_executor.subprocess.run')
    @patch('src.ai_executor.psutil.Process')
    def test_check_ai_process_health_healthy(self, mock_process, mock_subprocess_run, mock_log):
        """测试1：健康检查返回 True 当进程运行时"""
        from src.ai_executor import TmuxClaudeCodeExecutor

        # 模拟 tmux 相关命令
        def mock_run_side_effect(*args, **kwargs):
            result = MagicMock()
            if "list-sessions" in args[0]:
                result.stdout = "cc: 1 windows"
            elif "list-panes" in args[0]:
                result.stdout = "12345\n"
                result.returncode = 0
            else:
                result.returncode = 0
            return result

        mock_subprocess_run.side_effect = mock_run_side_effect

        # 模拟 psutil.Process 返回父进程，且 children 返回子进程列表
        mock_parent = MagicMock()
        mock_child = MagicMock()
        # 使用新的 psutil API：方法而非 .info 属性
        mock_child.name.return_value = 'claude'
        mock_child.pid = 12346
        mock_child.cmdline.return_value = ['claude']
        mock_parent.children.return_value = [mock_child]
        mock_process.return_value = mock_parent

        # 创建 executor
        executor = TmuxClaudeCodeExecutor()

        # 检查健康状态
        is_healthy = executor._check_ai_process_health()

        # 验证返回 True
        assert is_healthy, "健康检查应该返回 True 当进程运行时"

    @patch('src.ai_executor.subprocess.run')
    @patch('src.ai_executor.psutil.Process')
    def test_check_ai_process_health_crashed(self, mock_process, mock_subprocess_run):
        """测试2：健康检查返回 False 当进程崩溃时"""
        from src.ai_executor import TmuxClaudeCodeExecutor

        # 模拟 tmux session 存在
        mock_subprocess_run.return_value = MagicMock(stdout="cc: 1 windows")

        # 模拟 tmux pane 存在
        mock_subprocess_run.return_value = MagicMock(stdout="12345\n", returncode=0)

        # 模拟 psutil.Process 返回父进程，但 children 返回空列表（进程崩溃）
        mock_parent = MagicMock()
        mock_parent.children.return_value = []
        mock_process.return_value = mock_parent

        # 创建 executor
        executor = TmuxClaudeCodeExecutor()

        # 检查健康状态
        is_healthy = executor._check_ai_process_health()

        # 验证返回 False
        assert not is_healthy, "健康检查应该返回 False 当进程崩溃时"

    @patch('src.ai_executor.tmux_session.TmuxSessionManager._log_debug_info')
    @patch('src.ai_executor.subprocess.run')
    @patch('src.ai_executor.time.sleep')
    def test_monitor_and_restart_if_needed(self, mock_sleep, mock_subprocess_run, mock_log):
        """测试3：检测到崩溃时触发重启"""
        from src.ai_executor import TmuxClaudeCodeExecutor

        # 模拟 tmux session 存在
        def mock_run_side_effect(*args, **kwargs):
            result = MagicMock()
            if "list-sessions" in args[0]:
                result.stdout = "cc: 1 windows"
            elif "list-panes" in args[0]:
                result.stdout = "12345\n"
                result.returncode = 0
            else:
                result.returncode = 0
            return result

        mock_subprocess_run.side_effect = mock_run_side_effect

        # 创建 executor
        executor = TmuxClaudeCodeExecutor()

        # 模拟 _check_ai_process_health 返回 False（进程崩溃）
        with patch.object(executor, '_check_ai_process_health', return_value=False):
            # 模拟 _ensure_tmux_session 返回 (True, True)（重启成功）
            with patch.object(executor, '_ensure_tmux_session', return_value=(True, True)) as mock_ensure:
                # 调用监控和重启（不再需要 task_id 参数）
                did_restart = executor._monitor_and_restart_if_needed()

                # 验证返回 True（表示重启了）
                assert did_restart, "应该触发重启"

                # 验证 _ensure_tmux_session 被调用
                mock_ensure.assert_called_once()

                # 验证重启计数增加
                assert executor._restart_count == 1

    @patch('src.ai_executor.subprocess.run')
    def test_monitor_no_restart_when_disabled(self, mock_subprocess_run):
        """测试4：禁用自动重启时不触发重启"""
        from src.ai_executor import TmuxClaudeCodeExecutor

        # 创建 executor
        executor = TmuxClaudeCodeExecutor()

        # 直接禁用自动重启
        executor._auto_restart_enabled = False

        # 确认自动重启已禁用
        assert not executor._auto_restart_enabled

        # 模拟健康检查失败
        with patch.object(executor, '_check_ai_process_health', return_value=False):
            # 调用监控和重启（不再需要 task_id 参数）
            did_restart = executor._monitor_and_restart_if_needed()

            # 验证返回 False（没有重启）
            assert not did_restart, "禁用自动重启时不应该触发重启"

            # 验证重启计数为 0
            assert executor._restart_count == 0

    @patch('src.ai_executor.subprocess.run')
    @patch('src.ai_executor.time.sleep')
    def test_monitor_max_restart_attempts(self, mock_sleep, mock_subprocess_run):
        """测试5：达到最大重启次数后停止重启"""
        from src.ai_executor import TmuxClaudeCodeExecutor

        # 模拟 tmux session 存在
        def mock_run_side_effect(*args, **kwargs):
            result = MagicMock()
            if "list-sessions" in args[0]:
                result.stdout = "cc: 1 windows"
            elif "list-panes" in args[0]:
                result.stdout = "12345\n"
                result.returncode = 0
            else:
                result.returncode = 0
            return result

        mock_subprocess_run.side_effect = mock_run_side_effect

        # 创建 executor
        executor = TmuxClaudeCodeExecutor()

        # 模拟 _check_ai_process_health 返回 False（进程崩溃）
        with patch.object(executor, '_check_ai_process_health', return_value=False):
            # 模拟 _create_tmux_session 返回 True（重启成功）
            with patch.object(executor, '_create_tmux_session', return_value=True) as mock_create:
                # 设置当前重启次数为最大值
                executor._restart_count = 3  # MAX_RESTART_ATTEMPTS

                # 调用监控和重启（不再需要 task_id 参数）
                did_restart = executor._monitor_and_restart_if_needed()

                # 验证返回 False（没有重启）
                assert not did_restart, "达到最大重启次数时不应该重启"

                # 验证 _create_tmux_session 未被调用
                mock_create.assert_not_called()

                # 验证重启计数未增加
                assert executor._restart_count == 3

    @patch('src.ai_executor.tmux_session.TmuxSessionManager._log_debug_info')
    @patch('src.ai_executor.subprocess.run')
    def test_execute_command_calls_monitor_before_execution(self, mock_subprocess_run, mock_log):
        """测试6：execute_command 在执行前调用监控"""
        from src.ai_executor import TmuxClaudeCodeExecutor
        import asyncio

        # 模拟 tmux 相关命令
        def mock_run_side_effect(*args, **kwargs):
            result = MagicMock()
            if "list-sessions" in args[0]:
                result.stdout = "cc: 1 windows"
            elif "list-panes" in args[0]:
                result.stdout = "12345\n"
                result.returncode = 0
            elif "capture-pane" in args[0]:
                result.stdout = "test output"
                result.returncode = 0
            else:
                result.returncode = 0
            return result

        mock_subprocess_run.side_effect = mock_run_side_effect

        # 创建 executor
        executor = TmuxClaudeCodeExecutor()

        # 模拟 _ensure_tmux_session 返回 (True, False)（不需要重启）
        with patch.object(executor._session_manager, '_ensure_tmux_session', return_value=(True, False)) as mock_ensure:
            # 模拟 send_command 不 yield 任何内容
            with patch.object(executor._session_manager, 'send_command', return_value=iter([])):
                # 模拟 asyncio.sleep
                with patch('src.ai_executor.time.sleep'):
                    # 执行命令（不再需要 task_id 参数）
                    async def run_test():
                        outputs = []
                        async for output in executor.execute_command("test command"):
                            outputs.append(output)
                        return outputs

                    asyncio.run(run_test())

                    # 验证 _ensure_tmux_session 被调用
                    mock_ensure.assert_called_once()