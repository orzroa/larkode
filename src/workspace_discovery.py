"""
工作空间自动发现模块

像 tree 命令一样简单列出目录结构，深度优先遍历，按字母排序
"""
import json
from pathlib import Path
from typing import List, Dict

from src.config.settings import get_settings

# 优先使用新的日志工具，失败则回退到标准 logging
try:
    from src.logging_utils import get_logger
except ImportError:
    import logging

try:
    logger = get_logger(__name__)
except NameError:
    logger = logging.getLogger(__name__)


class WorkspaceDiscovery:
    """工作空间自动发现"""

    def __init__(
        self,
        root_dir: Path,
        depth: int = 1,
        exclude_patterns: List[str] = None
    ):
        """
        初始化工作空间发现器

        Args:
            root_dir: 根目录
            depth: 扫描深度
            exclude_patterns: 排除的目录模式
        """
        self.root_dir = root_dir
        self.depth = depth
        self.exclude_patterns = exclude_patterns or [
            ".git", "node_modules", "__pycache__", ".venv", "venv",
            ".pytest_cache", "htmlcov", ".idea", ".vscode", "dist", "build"
        ]

    def discover(self) -> List[Dict]:
        """
        发现工作空间，返回 [{name, path, depth}]

        深度优先遍历，按字母排序，类似 tree 命令
        """
        if not self.root_dir.exists():
            logger.error(f"工作空间根目录不存在: {self.root_dir}")
            return []

        workspaces = []
        self._scan_directory(self.root_dir, workspaces, current_depth=1)

        # 按名称排序（已经通过 iterdir + sorted 保证）
        return workspaces

    def _scan_directory(
        self,
        current_dir: Path,
        workspaces: List[Dict],
        current_depth: int,
        parent_name: str = ""
    ):
        """
        递归扫描目录（深度优先）

        Args:
            current_dir: 当前扫描的目录
            workspaces: 工作空间列表（累积）
            current_depth: 当前深度
            parent_name: 父目录名称（用于构造显示名称）
        """
        if current_depth > self.depth:
            return

        try:
            # 按字母顺序遍历子目录
            for child in sorted(current_dir.iterdir(), key=lambda p: p.name):
                if not child.is_dir():
                    continue
                if self._should_exclude(child):
                    continue

                # 构造显示名称
                if parent_name:
                    display_name = f"{parent_name}/{child.name}"
                else:
                    display_name = child.name

                # 添加到工作空间列表
                workspaces.append({
                    'name': display_name,
                    'path': str(child.resolve()),
                    'depth': current_depth
                })

                # 递归扫描子目录
                if current_depth < self.depth:
                    self._scan_directory(
                        child,
                        workspaces,
                        current_depth + 1,
                        display_name
                    )
        except PermissionError as e:
            logger.warning(f"无法访问目录 {current_dir}: {e}")
        except Exception as e:
            logger.error(f"扫描目录 {current_dir} 时出错: {e}")

    def _should_exclude(self, path: Path) -> bool:
        """
        检查是否应该排除目录

        Args:
            path: 目录路径

        Returns:
            是否排除
        """
        # 排除隐藏目录（以 . 开头）
        if path.name.startswith('.'):
            return True

        # 排除匹配模式的目录
        return path.name in self.exclude_patterns


def discover_workspaces() -> List[Dict]:
    """
    发现工作空间（便捷函数）

    从配置中读取参数，执行工作空间发现

    Returns:
        工作空间列表 [{name, path, depth}]
    """
    settings = get_settings()

    if not settings.workspace_discovery_enabled:
        logger.info("工作空间自动发现未启用")
        return []

    if not settings.workspace_root_dir:
        logger.warning("工作空间根目录未配置")
        return []

    # 解析排除模式
    try:
        exclude_patterns = json.loads(settings.workspace_exclude_patterns)
    except json.JSONDecodeError:
        logger.warning("工作空间排除模式配置格式错误，使用默认值")
        exclude_patterns = None

    discovery = WorkspaceDiscovery(
        root_dir=settings.workspace_root_dir,
        depth=settings.workspace_discovery_depth,
        exclude_patterns=exclude_patterns
    )

    return discovery.discover()