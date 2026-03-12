"""
AI 进程健康检查和自动重启
"""
import time
from pathlib import Path
from typing import Optional

from src.config.settings import get_settings

# 优先使用新的日志工具，失败则回退到标准 logging
try:
    from src.logging_utils import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class ProcessMonitor:
    """AI 进程健康检查和自动重启"""

    def __init__(self):
        # 自动重启配置
        self._auto_restart_enabled = get_settings().AI_AUTO_RESTART_ENABLED
        self._max_restart_attempts = get_settings().AI_MAX_RESTART_ATTEMPTS
        self._restart_delay = get_settings().AI_RESTART_DELAY
        self._crash_detection_interval = get_settings().AI_CRASH_DETECTION_INTERVAL
        self._restart_count = 0
        self._last_health_check_time = 0

    @property
    def auto_restart_enabled(self) -> bool:
        return self._auto_restart_enabled

    @property
    def max_restart_attempts(self) -> int:
        return self._max_restart_attempts

    @property
    def restart_delay(self) -> int:
        return self._restart_delay

    @property
    def restart_count(self) -> int:
        return self._restart_count

    @restart_count.setter
    def restart_count(self, value: int):
        self._restart_count = value

    def check_health(self, check_func) -> bool:
        """检查进程健康状态

        Args:
            check_func: 回调函数，用于实际检查进程是否存在

        Returns:
            bool: True 表示健康（进程存在），False 表示崩溃（进程不存在）
        """
        return check_func()

    def should_restart(self) -> bool:
        """检查是否应该重启

        Returns:
            bool: True 表示应该尝试重启
        """
        if not self._auto_restart_enabled:
            return False

        if self._restart_count >= self._max_restart_attempts:
            logger.error(f"AI 崩溃次数达到上限 ({self._max_restart_attempts})，停止自动重启")
            return False

        return True

    def attempt_restart(self, restart_func) -> bool:
        """尝试重启 AI

        Args:
            restart_func: 回调函数，用于执行实际的重启操作

        Returns:
            bool: True 表示重启成功
        """
        if not self.should_restart():
            return False

        logger.warning(f"检测到 AI 进程崩溃，尝试重启（第 {self._restart_count + 1}/{self._max_restart_attempts} 次）")
        time.sleep(self._restart_delay)

        if restart_func():
            self._restart_count += 1
            logger.info(f"AI 进程重启成功（第 {self._restart_count} 次）")
            return True
        else:
            logger.error("AI 进程重启失败")
            return False

    def reset_restart_count(self):
        """重置重启计数"""
        self._restart_count = 0
