"""
测试 TmuxSessionManager 中的依赖服务检查集成
"""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestTmuxSessionDependencies:
    def teardown_method(self):
        """清理全局状态"""
        from src.dependency_checker import DependencyChecker
        DependencyChecker._instance = None

    def test_ensure_dependencies_calls_checker(self):
        """_ensure_dependencies 应调用 DependencyChecker"""
        from src.dependency_checker import DependencyCheckSummary
        mock_summary = DependencyCheckSummary(results=[])
        mock_summary.skipped = False

        with patch("src.dependency_checker.get_dependency_checker") as mock_get:
            mock_checker = MagicMock()
            mock_checker.ensure_services_running_sync.return_value = mock_summary
            mock_get.return_value = mock_checker

            from src.ai_executor.tmux_session import TmuxSessionManager
            with patch.object(TmuxSessionManager, "__init__", lambda self: None):
                mgr = TmuxSessionManager()
                mgr.workspace = Path("/tmp/test")
                mgr._tmux_session = "test_session"
                mgr._ensure_dependencies()

        # 验证 ensure_services_running_sync 被以 force=True 调用
        mock_checker.ensure_services_running_sync.assert_called_once_with(force=True)

    def test_ensure_dependencies_logs_start(self):
        """启动成功的服务应被记录"""
        from src.dependency_checker import (
            DependentService, ServiceCheckResult,
        )
        svc = DependentService(name="ccr", start_cmd="c", status_cmd="c")
        result = ServiceCheckResult(service=svc, running=True, started=True)
        mock_summary = MagicMock()
        mock_summary.skipped = False
        mock_summary.results = [result]

        with patch("src.dependency_checker.get_dependency_checker") as mock_get:
            mock_checker = MagicMock()
            mock_checker.ensure_services_running_sync.return_value = mock_summary
            mock_get.return_value = mock_checker

            from src.ai_executor.tmux_session import TmuxSessionManager
            with patch.object(TmuxSessionManager, "__init__", lambda self: None):
                mgr = TmuxSessionManager()
                mgr.workspace = Path("/tmp/test")
                mgr._tmux_session = "test_session"
                # 调用不抛异常即验证通过
                mgr._ensure_dependencies()

    def test_ensure_dependencies_no_exception_on_error(self):
        """依赖检查本身抛异常时不应中断 tmux 启动"""
        with patch("src.dependency_checker.get_dependency_checker") as mock_get:
            mock_get.side_effect = RuntimeError("checker boom")

            from src.ai_executor.tmux_session import TmuxSessionManager
            with patch.object(TmuxSessionManager, "__init__", lambda self: None):
                mgr = TmuxSessionManager()
                mgr.workspace = Path("/tmp/test")
                mgr._tmux_session = "test_session"
                # 不应抛异常
                mgr._ensure_dependencies()

    def test_ensure_dependencies_skipped(self):
        """节流跳过时不感知 results"""
        mock_summary = MagicMock()
        mock_summary.skipped = True

        with patch("src.dependency_checker.get_dependency_checker") as mock_get:
            mock_checker = MagicMock()
            mock_checker.ensure_services_running_sync.return_value = mock_summary
            mock_get.return_value = mock_checker

            from src.ai_executor.tmux_session import TmuxSessionManager
            with patch.object(TmuxSessionManager, "__init__", lambda self: None):
                mgr = TmuxSessionManager()
                mgr.workspace = Path("/tmp/test")
                mgr._tmux_session = "test_session"
                mgr._ensure_dependencies()
