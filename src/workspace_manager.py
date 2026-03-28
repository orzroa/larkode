"""
工作空间管理器

管理工作空间的发现、运行状态检测、切换等功能
"""
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from src.ai_executor.tmux_session import TmuxSessionManager
from src.config.settings import get_settings
from src.workspace_discovery import discover_workspaces

# 优先使用新的日志工具，失败则回退到标准 logging
try:
    from src.logging_utils import get_logger
except ImportError:
    import logging

try:
    logger = get_logger(__name__)
except NameError:
    logger = logging.getLogger(__name__)


class WorkspaceManager:
    """工作空间管理器"""

    def __init__(self):
        """初始化工作空间管理器"""
        # 当前工作空间路径（全局，单用户）
        self._current_workspace: Optional[str] = None

    def get_workspaces(self) -> List[Dict]:
        """
        获取工作空间列表（实时扫描）

        Returns:
            工作空间列表 [{name, path, depth, is_running, is_default, is_current}]
        """
        # 发现工作空间
        discovered = discover_workspaces()

        # 获取运行中的工作空间
        running_paths = self._get_running_workspaces()

        # 获取默认工作空间
        settings = get_settings()
        default_path = str(settings.workspace_default_dir) if settings.workspace_default_dir else None

        # 获取当前工作空间（可能是默认工作空间）
        current_path = self.get_current_workspace()

        # 构造结果
        workspaces = []
        for ws in discovered:
            path = ws['path']

            workspaces.append({
                'name': ws['name'],
                'path': path,
                'depth': ws['depth'],
                'is_running': path in running_paths,
                'is_default': path == default_path,
                'is_current': path == current_path
            })

        return workspaces

    def get_current_workspace(self) -> Optional[str]:
        """
        获取当前工作空间路径

        优先级：
        1. 内存中保存的当前工作空间（用户通过 #ws 命令主动切换的）
        2. 从当前 tmux session 检测（通过 $TMUX 环境变量，仅服务进程在 tmux 中时有效）
        3. 默认工作空间

        Returns:
            当前工作空间路径，未找到返回 None
        """
        # 1. 优先使用内存中保存的当前工作空间（用户主动切换的状态）
        if self._current_workspace:
            logger.debug(f"使用内存缓存的工作空间: {self._current_workspace}")
            return self._current_workspace

        # 2. 尝试从当前 tmux session 检测（仅服务进程在 tmux 中时有效）
        try:
            import os
            tmux_env = os.environ.get('TMUX', '')
            logger.debug(f"TMUX 环境变量: '{tmux_env}'")
            if tmux_env:
                # TMUX 环境变量格式：/tmp/tmux-1000/default,12345,0
                # 只有在 tmux 环境中才尝试检测
                result = subprocess.run(
                    ["tmux", "display-message", "-p", "#{session_name}"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    stderr=subprocess.DEVNULL  # 忽略错误输出
                )
                if result.returncode == 0:
                    session_name = result.stdout.strip()
                    logger.info(f"检测到当前 tmux session: {session_name}")
                    # 从 session 名称解析工作空间路径
                    workspace_path = self._session_name_to_path(session_name)
                    if workspace_path and Path(workspace_path).exists():
                        # 更新内存中的当前工作空间
                        self._current_workspace = workspace_path
                        logger.info(f"从 tmux session 解析到工作空间: {workspace_path}")
                        return workspace_path
                    else:
                        logger.warning(f"无法从 session 名称解析有效路径: {session_name} -> {workspace_path}")
                        if workspace_path:
                            logger.warning(f"路径存在性检查: {Path(workspace_path).exists()}")
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            # tmux 命令不存在或超时，记录警告
            logger.debug(f"检测 tmux session 失败 (系统错误): {e}")
        except Exception as e:
            # 其他异常也记录，不影响主流程
            logger.debug(f"检测 tmux session 时出错: {e}")

        # 3. 返回默认工作空间
        settings = get_settings()
        if settings.workspace_default_dir:
            logger.debug(f"使用默认工作空间: {settings.workspace_default_dir}")
            return str(settings.workspace_default_dir)

        return None

    def switch_workspace(self, workspace_path: str) -> tuple[bool, str]:
        """
        切换到指定工作空间

        Args:
            workspace_path: 工作空间路径

        Returns:
            (success, message): 是否成功和消息
        """
        settings = get_settings()

        # 验证路径是否存在
        if not Path(workspace_path).exists():
            return False, f"工作空间路径不存在: {workspace_path}"

        # 更新当前工作空间
        self._current_workspace = workspace_path

        # 使用 TmuxSessionManager 管理 session
        session_name = self._get_session_name(workspace_path)
        session_manager = TmuxSessionManager(
            workspace=Path(workspace_path),
            session_name=session_name
        )

        # 检查 session 是否存在
        if session_manager._check_tmux_session():
            # session 存在，设置环境变量（确保 hook 进程能获取正确的工作空间）
            try:
                subprocess.run(
                    ["tmux", "set-environment", "-t", session_name,
                     "AI_WORKSPACE_DIR", workspace_path],
                    check=True
                )
                logger.info(f"已更新环境变量 AI_WORKSPACE_DIR={workspace_path}")
            except Exception as e:
                logger.warning(f"设置环境变量失败: {e}")

            # attach
            logger.info(f"工作空间 {workspace_path} 已有运行中的 session: {session_name}")
            try:
                subprocess.run(
                    ["tmux", "attach", "-t", session_name],
                    timeout=10
                )
                logger.info(f"已 attach 到 session: {session_name}")
            except subprocess.TimeoutExpired:
                logger.warning(f"attach 到 session {session_name} 超时")
            except Exception as e:
                logger.error(f"attach 到 session {session_name} 失败: {e}")
            return True, f"已切换到工作空间（已存在 session）: {workspace_path}"
        else:
            # session 不存在，创建新的
            logger.info(f"为工作空间 {workspace_path} 创建新 session: {session_name}")
            success = session_manager._create_tmux_session()
            if success:
                try:
                    subprocess.run(
                        ["tmux", "attach", "-t", session_name],
                        timeout=10
                    )
                    logger.info(f"已 attach 到 session: {session_name}")
                except subprocess.TimeoutExpired:
                    logger.warning(f"attach 到 session {session_name} 超时")
                except Exception as e:
                    logger.error(f"attach 到 session {session_name} 失败: {e}")
                return True, f"已启动并切换到工作空间: {workspace_path}"
            else:
                return False, f"创建工作空间 session 失败: {workspace_path}"

    def _get_running_workspaces(self) -> set:
        """
        获取运行中的工作空间路径

        Returns:
            运行中的工作空间路径集合
        """
        try:
            # 列出所有 tmux sessions
            result = subprocess.run(
                ["tmux", "list-sessions", "-F", "#{session_name}:#{session_path}"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                logger.debug("没有找到 tmux sessions")
                return set()

            # 过滤 cc- 开头的 session 或 cc session，解析路径
            running_paths = set()
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue

                parts = line.split(':', 1)
                if len(parts) != 2:
                    continue

                session_name, session_path = parts

                # 支持两种格式的 session 名称：
                # 1. cc-home-user-Workspaces-github-larkode (新格式)
                # 2. cc (旧格式，需要从 session_path 获取路径)
                if session_name.startswith('cc-'):
                    # 新格式：从 session 名称解析路径
                    path = self._session_name_to_path(session_name)
                    if path:
                        running_paths.add(path)
                elif session_name == 'cc':
                    # 旧格式：使用 session 的工作目录
                    if session_path:
                        running_paths.add(session_path)

            return running_paths

        except subprocess.TimeoutExpired:
            logger.warning("获取 tmux sessions 超时")
            return set()
        except Exception as e:
            logger.error(f"获取运行中的工作空间失败: {e}")
            return set()

    def _get_session_name(self, workspace_path: str) -> str:
        """
        根据工作空间路径生成 tmux session 名称

        Args:
            workspace_path: 工作空间路径

        Returns:
            session 名称（如 cc-larkode 或 cc-github-larkode）
        """
        settings = get_settings()

        # 尝试使用相对于 workspace_root_dir 的路径
        if settings.workspace_root_dir and str(settings.workspace_root_dir) != ".":
            try:
                workspace = Path(workspace_path)
                root = Path(settings.workspace_root_dir)
                # 计算相对路径
                rel_path = workspace.relative_to(root)
                # cc-larkode 或 cc-github-larkode（只保留项目名）
                path_str = str(rel_path)
                if path_str and path_str != ".":
                    return f"cc-{path_str.replace('/', '-')}"
            except ValueError:
                # workspace_path 不在 root 内，回退到下面的逻辑
                pass

        # 回退策略：只使用最后 2 级路径（如 github/larkode -> github-larkode）
        path_parts = Path(workspace_path).parts
        # 过滤掉根目录 '/'
        path_parts = tuple(p for p in path_parts if p != '/')

        if len(path_parts) >= 2:
            # 取最后 2 级（转换为小写确保一致性）
            short_path = "-".join(part.lower() for part in path_parts[-2:])
        elif len(path_parts) == 1:
            # 只有 1 级
            short_path = path_parts[0].lower()
        else:
            # 空路径，使用默认
            short_path = "default"

        return f"cc-{short_path}"

    def _session_name_to_path(self, session_name: str) -> Optional[str]:
        """
        从 session 名称解析工作空间路径

        Args:
            session_name: session 名称

        Returns:
            工作空间路径，解析失败返回 None
        """
        if not session_name.startswith('cc-'):
            return None

        settings = get_settings()
        path_part = session_name[3:]  # 去掉 'cc-'

        # 尝试使用 workspace_root_dir 还原完整路径
        if settings.workspace_root_dir and str(settings.workspace_root_dir) != ".":
            # cc-larkode -> /root/dir/larkode
            # cc-github-larkode -> /root/dir/github/larkode
            full_path = Path(settings.workspace_root_dir) / path_part.replace('-', '/')
            if full_path.exists():
                return str(full_path)

        # 无法还原完整路径时返回 None
        # 这是因为简短的 session 名称（如 cc-larkode）无法唯一确定完整路径
        return None


# 全局单例
_workspace_manager: Optional[WorkspaceManager] = None


def get_workspace_manager() -> WorkspaceManager:
    """
    获取全局工作空间管理器实例（单例模式）

    Returns:
        WorkspaceManager 实例
    """
    global _workspace_manager
    if _workspace_manager is None:
        _workspace_manager = WorkspaceManager()
    return _workspace_manager