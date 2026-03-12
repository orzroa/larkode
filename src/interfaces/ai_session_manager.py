"""
AI Session 管理器接口定义
负责检测运行中的 AI 进程，获取或创建 session
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime


class SessionStatus(Enum):
    """Session 状态枚举"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    UNKNOWN = "unknown"


class TmuxStatus(Enum):
    """Tmux session 状态枚举"""
    EXISTS = "exists"
    NOT_EXISTS = "not_exists"
    ERROR = "error"


class ProcessInfo:
    """进程信息类"""
    def __init__(self, pid: int, name: str, cwd: str, cmdline: List[str]):
        self.pid = pid
        self.name = name
        self.cwd = cwd
        self.cmdline = cmdline

    def to_dict(self) -> Dict[str, Any]:
        return {
            'pid': self.pid,
            'name': self.name,
            'cwd': self.cwd,
            'cmdline': self.cmdline
        }


class SessionInfo:
    """Session 信息类"""
    def __init__(self, session_id: str, status: SessionStatus, last_updated: datetime,
                 tmux_name: Optional[str] = None, process_info: Optional[ProcessInfo] = None):
        self.session_id = session_id
        self.status = status
        self.last_updated = last_updated
        self.tmux_name = tmux_name
        self.process_info = process_info

    def to_dict(self) -> Dict[str, Any]:
        return {
            'session_id': self.session_id,
            'status': self.status.value,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None,
            'tmux_name': self.tmux_name,
            'process_info': self.process_info.to_dict() if self.process_info else None
        }


class AISessionManagerInterface(ABC):
    """AI Session 管理器接口"""

    @abstractmethod
    def detect_running_processes(self) -> List[ProcessInfo]:
        """
        检测当前目录中的 AI 进程 (Node N14)

        Returns:
            List[ProcessInfo]: 运行中的 AI 进程列表
        """
        pass

    @abstractmethod
    def find_session_from_projects(self, project_name: Optional[str] = None) -> Optional[str]:
        """
        从 .claude/projects/ 查找 session 文件 (Node N15)

        Args:
            project_name: 项目名称，如果为 None 使用当前工作目录

        Returns:
            str: Session ID，如果没有找到返回 None
        """
        pass

    @abstractmethod
    def check_tmux_session(self, session_name: str) -> TmuxStatus:
        """
        检查 tmux session 是否存在 (Node N16)

        Args:
            session_name: tmux session 名称

        Returns:
            TmuxStatus: tmux session 状态
        """
        pass

    @abstractmethod
    def create_tmux_session(self, session_name: str, command: str) -> bool:
        """
        创建新的 tmux session (Node N17)

        Args:
            session_name: tmux session 名称
            command: 在 session 中执行的命令

        Returns:
            bool: 是否成功创建
        """
        pass

    @abstractmethod
    def check_process_in_tmux(self, session_name: str) -> Optional[ProcessInfo]:
        """
        检查 tmux session 中是否有 Claude 进程 (Node N18)

        Args:
            session_name: tmux session 名称

        Returns:
            ProcessInfo: Claude 进程信息，如果没有找到返回 None
        """
        pass

    @abstractmethod
    def start_ai_in_tmux(self, session_name: str, command: str,
                           resume_session_id: Optional[str] = None,
                           query: Optional[str] = None) -> bool:
        """
        在 tmux 中启动 AI 进程 (Node N19)

        Args:
            session_name: tmux session 名称
            command: 要执行的命令（完整路径）
            resume_session_id: 要恢复的 session ID
            query: 可选的初始查询

        Returns:
            bool: 是否成功启动
        """
        pass

    @abstractmethod
    def get_session_info(self, session_id: str) -> Optional[SessionInfo]:
        """
        获取 session 详细信息

        Args:
            session_id: Session ID

        Returns:
            SessionInfo: Session 信息对象
        """
        pass

    @abstractmethod
    def get_or_create_session(self, project_name: Optional[str] = None,
                            start_if_missing: bool = True,
                            max_wait_seconds: int = 30) -> Optional[str]:
        """
        获取或创建 AI session (完整流程)

        Args:
            project_name: 项目名称
            start_if_missing: 如果没有找到，是否启动新的
            max_wait_seconds: 等待 session 初始化的最大秒数

        Returns:
            str: Session ID，失败返回 None
        """
        pass

    @abstractmethod
    def stop_session(self, session_id: str, kill_tmux: bool = False) -> bool:
        """
        停止指定的 session

        Args:
            session_id: Session ID
            kill_tmux: 是否同时停止 tmux session

        Returns:
            bool: 是否成功停止
        """
        pass

    @abstractmethod
    def get_active_sessions(self, project_name: Optional[str] = None) -> List[SessionInfo]:
        """
        获取所有活跃的 sessions

        Args:
            project_name: 项目名称

        Returns:
            List[SessionInfo]: 活跃 session 列表
        """
        pass


class MockAISessionManager(AISessionManagerInterface):
    """测试用的模拟 Session 管理器实现"""

    def __init__(self):
        self._processes: List[ProcessInfo] = []
        self._sessions: Dict[str, SessionInfo] = {}
        self._tmux_sessions: Dict[str, TmuxStatus] = {}
        self._project_sessions: Dict[str, str] = {}

    def add_mock_process(self, pid: int, name: str, cwd: str, cmdline: List[str]):
        """添加模拟进程"""
        process = ProcessInfo(pid, name, cwd, cmdline)
        self._processes.append(process)

    def add_mock_session(self, session_id: str, project_name: str,
                        status: SessionStatus = SessionStatus.ACTIVE,
                        tmux_name: Optional[str] = None,
                        last_updated: Optional[datetime] = None):
        """添加模拟 session"""
        if last_updated is None:
            last_updated = datetime.now()

        session = SessionInfo(session_id, status, last_updated, tmux_name)
        self._sessions[session_id] = session
        self._project_sessions[project_name] = session_id

    def set_tmux_status(self, session_name: str, status: TmuxStatus):
        """设置 tmux session 状态"""
        self._tmux_sessions[session_name] = status

    # 实现接口方法
    def detect_running_processes(self) -> List[ProcessInfo]:
        return self._processes

    def find_session_from_projects(self, project_name: Optional[str] = None) -> Optional[str]:
        if project_name and project_name in self._project_sessions:
            return self._project_sessions[project_name]
        return None

    def check_tmux_session(self, session_name: str) -> TmuxStatus:
        return self._tmux_sessions.get(session_name, TmuxStatus.NOT_EXISTS)

    def create_tmux_session(self, session_name: str, command: str) -> bool:
        self._tmux_sessions[session_name] = TmuxStatus.EXISTS
        return True

    def check_process_in_tmux(self, session_name: str) -> Optional[ProcessInfo]:
        if session_name in self._tmux_sessions:
            return self._processes[0] if self._processes else None
        return None

    def start_ai_in_tmux(self, session_name: str, command: str,
                           resume_session_id: Optional[str] = None,
                           query: Optional[str] = None) -> bool:
        self._tmux_sessions[session_name] = TmuxStatus.EXISTS
        return True

    def get_session_info(self, session_id: str) -> Optional[SessionInfo]:
        return self._sessions.get(session_id)

    def get_or_create_session(self, project_name: Optional[str] = None,
                            start_if_missing: bool = True,
                            max_wait_seconds: int = 30) -> Optional[str]:
        if project_name and project_name in self._project_sessions:
            return self._project_sessions[project_name]

        if start_if_missing:
            # 创建新 session
            session_id = f"session_{int(datetime.now().timestamp())}"
            project_name = project_name or "mock_project"
            self.add_mock_session(session_id, project_name)
            return session_id

        return None

    def stop_session(self, session_id: str, kill_tmux: bool = False) -> bool:
        if session_id in self._sessions:
            if kill_tmux and self._sessions[session_id].tmux_name:
                del self._tmux_sessions[self._sessions[session_id].tmux_name]
            del self._sessions[session_id]
            return True
        return False

    def get_active_sessions(self, project_name: Optional[str] = None) -> List[SessionInfo]:
        if project_name:
            session_id = self._project_sessions.get(project_name)
            if session_id and session_id in self._sessions:
                return [self._sessions[session_id]]
        return list(self._sessions.values())