"""
ProcessMonitor 测试
"""
import pytest
from unittest.mock import MagicMock, patch


class TestProcessMonitor:
    """进程监控器测试"""

    @pytest.fixture
    def mock_settings(self):
        """模拟配置"""
        with patch("src.ai_executor.process_monitor.get_settings") as mock:
            settings = MagicMock()
            settings.AI_AUTO_RESTART_ENABLED = True
            settings.AI_MAX_RESTART_ATTEMPTS = 3
            settings.AI_RESTART_DELAY = 1
            settings.AI_CRASH_DETECTION_INTERVAL = 60
            mock.return_value = settings
            yield mock

    @pytest.fixture
    def monitor(self, mock_settings):
        """创建测试监控器"""
        from src.ai_executor.process_monitor import ProcessMonitor
        return ProcessMonitor()

    def test_init(self, monitor):
        """测试初始化"""
        assert monitor._auto_restart_enabled is True
        assert monitor._max_restart_attempts == 3
        assert monitor._restart_delay == 1
        assert monitor._crash_detection_interval == 60
        assert monitor._restart_count == 0

    def test_auto_restart_enabled_property(self, monitor):
        """测试 auto_restart_enabled 属性"""
        assert monitor.auto_restart_enabled is True

    def test_max_restart_attempts_property(self, monitor):
        """测试 max_restart_attempts 属性"""
        assert monitor.max_restart_attempts == 3

    def test_restart_delay_property(self, monitor):
        """测试 restart_delay 属性"""
        assert monitor.restart_delay == 1

    def test_restart_count_property(self, monitor):
        """测试 restart_count 属性"""
        assert monitor.restart_count == 0
        monitor.restart_count = 2
        assert monitor.restart_count == 2

    def test_check_health_healthy(self, monitor):
        """测试健康检查 - 健康"""
        check_func = MagicMock(return_value=True)
        result = monitor.check_health(check_func)
        assert result is True
        check_func.assert_called_once()

    def test_check_health_crashed(self, monitor):
        """测试健康检查 - 崩溃"""
        check_func = MagicMock(return_value=False)
        result = monitor.check_health(check_func)
        assert result is False
        check_func.assert_called_once()

    def test_should_restart_enabled(self, monitor):
        """测试应该重启 - 已启用"""
        assert monitor.should_restart() is True

    def test_should_restart_disabled(self, mock_settings):
        """测试应该重启 - 已禁用"""
        mock_settings.return_value.AI_AUTO_RESTART_ENABLED = False
        from src.ai_executor.process_monitor import ProcessMonitor
        monitor = ProcessMonitor()
        assert monitor.should_restart() is False

    def test_should_restart_max_attempts_reached(self, monitor):
        """测试应该重启 - 达到最大尝试次数"""
        monitor._restart_count = 3
        assert monitor.should_restart() is False

    def test_attempt_restart_success(self, monitor):
        """测试尝试重启 - 成功"""
        restart_func = MagicMock(return_value=True)
        result = monitor.attempt_restart(restart_func)
        assert result is True
        assert monitor.restart_count == 1
        restart_func.assert_called_once()

    def test_attempt_restart_failed(self, monitor):
        """测试尝试重启 - 失败"""
        restart_func = MagicMock(return_value=False)
        result = monitor.attempt_restart(restart_func)
        assert result is False
        assert monitor.restart_count == 0

    def test_attempt_restart_disabled(self, mock_settings):
        """测试尝试重启 - 已禁用"""
        mock_settings.return_value.AI_AUTO_RESTART_ENABLED = False
        from src.ai_executor.process_monitor import ProcessMonitor
        monitor = ProcessMonitor()
        restart_func = MagicMock(return_value=True)
        result = monitor.attempt_restart(restart_func)
        assert result is False
        restart_func.assert_not_called()

    def test_attempt_restart_max_attempts(self, monitor):
        """测试尝试重启 - 达到最大尝试次数"""
        monitor._restart_count = 3
        restart_func = MagicMock(return_value=True)
        result = monitor.attempt_restart(restart_func)
        assert result is False
        restart_func.assert_not_called()

    def test_reset_restart_count(self, monitor):
        """测试重置重启计数"""
        monitor._restart_count = 2
        monitor.reset_restart_count()
        assert monitor.restart_count == 0

    def test_multiple_restarts(self, monitor):
        """测试多次重启"""
        restart_func = MagicMock(return_value=True)

        # 第一次重启
        result = monitor.attempt_restart(restart_func)
        assert result is True
        assert monitor.restart_count == 1

        # 第二次重启
        result = monitor.attempt_restart(restart_func)
        assert result is True
        assert monitor.restart_count == 2

        # 第三次重启
        result = monitor.attempt_restart(restart_func)
        assert result is True
        assert monitor.restart_count == 3

        # 第四次应该被拒绝
        result = monitor.attempt_restart(restart_func)
        assert result is False
        assert monitor.restart_count == 3


class TestProcessMonitorImportFallback:
    """测试 import 回退逻辑"""

    def test_import_fallback(self):
        """测试日志工具 import 失败时回退"""
        with patch.dict(
            "sys.modules",
            {"src.logging_utils": None, "src.logging_utils.get_logger": None}
        ):
            # 强制重新导入模块
            import importlib
            import src.ai_executor.process_monitor as pm
            importlib.reload(pm)
            # 模块应该正常加载，使用标准 logging
            assert hasattr(pm, 'ProcessMonitor')