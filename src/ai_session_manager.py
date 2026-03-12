"""
AI Session 管理器
负责检测运行中的 AI 进程，获取 session
"""
import psutil
from pathlib import Path
from typing import Optional
from datetime import datetime

from src.config.settings import Config, get_settings

# 优先使用新的日志工具，失败则回退到标准 logging
try:
    from src.logging_utils import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class AISessionManager:
    """AI Session 管理器"""

    # 可配置的 AI projects 目录路径
    AI_PROJECTS_DIR = Path.home() / ".claude" / "projects"

    def __init__(self, projects_dir: Optional[Path] = None):
        self._workspace = Path.cwd()
        self._projects_dir = projects_dir or self.AI_PROJECTS_DIR

    def find_running_session(self) -> Optional[str]:
        """
        查找当前工作目录中运行中的 AI session

        Returns:
            str: Session ID，如果没有找到返回 None
        """
        # 1. 查找最近修改的 session 文件
        project_dir = self._projects_dir / self._get_project_name()
        if not project_dir.exists():
            logger.warning(f"项目目录不存在: {project_dir}")
            return None

        # 获取所有 .jsonl 文件
        session_files = list(project_dir.glob("*.jsonl"))
        if not session_files:
            logger.warning(f"没有找到 session 文件: {project_dir}")
            return None

        # 按修改时间排序，获取最新的
        latest_file = max(session_files, key=lambda f: f.stat().st_mtime)

        # 检查最近修改时间（10分钟内认为是活跃的）
        mtime = datetime.fromtimestamp(latest_file.stat().st_mtime)
        age_minutes = (datetime.now() - mtime).total_seconds() / 60

        max_age_minutes = get_settings().SESSION_MAX_AGE_MINUTES
        if age_minutes > max_age_minutes:
            logger.info(f"最新的 session 文件 {latest_file.name} 已超过{max_age_minutes}分钟未更新")

        session_id = latest_file.stem
        logger.info(f"找到 session ID: {session_id} (最后更新: {age_minutes:.1f}分钟前)")
        return session_id

    def _get_project_name(self) -> str:
        """获取项目名称（用于 projects 路径）"""
        # 将路径转换为 AI 助手使用的格式
        # 例如: /path/to/larkode -> -home-user-Workspaces-github-larkode
        path_str = str(self._workspace)
        # 移除开头的 /
        if path_str.startswith('/'):
            path_str = path_str[1:]
        # 将 / 替换为 -
        # AI 助手在路径前添加一个 - 作为前缀
        return '-' + path_str.replace('/', '-')

    def is_ai_running(self) -> bool:
        """
        检查当前工作目录中是否有运行中的 AI 进程

        Returns:
            bool: 是否有运行中的进程
        """
        process_name = get_settings().get_process_name()
        workspace_str = str(self._workspace)

        for proc in psutil.process_iter(['pid', 'name', 'cwd', 'cmdline']):
            try:
                # 查找对应的进程
                if proc.info['name'] and process_name in proc.info['name'].lower():
                    # 检查工作目录是否匹配
                    cwd = proc.info.get('cwd')
                    if cwd and cwd == workspace_str:
                        logger.info(f"找到运行中的 {process_name} 进程: PID {proc.info['pid']}")
                        return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        return False

    def get_session(self) -> Optional[str]:
        """
        获取 AI session

        Returns:
            str: Session ID，如果没有找到返回 None
        """
        # 查找现有 session
        session_id = self.find_running_session()
        if session_id:
            logger.info(f"使用现有 session: {session_id}")
            return session_id

        logger.warning("没有找到活跃 session")
        return None


# 全局实例
session_manager = AISessionManager()


def is_claude_running(self):
    """：使用 is_ai_running"""
    return self.is_ai_running()


# 为 AISessionManager 添加方法
AISessionManager.is_claude_running = is_claude_running

# 别名
ClaudeSessionManager = AISessionManager