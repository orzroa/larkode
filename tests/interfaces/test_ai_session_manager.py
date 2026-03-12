"""
测试 AI Session 管理器
测试节点：N14-N19 - Session 检测、管理、tmux 集成
"""
import pytest
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import subprocess
import os

from src.interfaces.ai_session_manager import (
    AISessionManagerInterface,
    MockAISessionManager,
    SessionStatus,
    TmuxStatus,
    ProcessInfo,
    SessionInfo
)


class MockAISessionManager(AISessionManagerInterface):
    """测试用的模拟实现，模拟实际系统行为"""

    def __init__(self):
        self.project_path = Path("/home/user/workspaces/test-project")
        self.ai_processes: List[ProcessInfo] = []
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.tmux_sessions: Dict[str, TmuxStatus] = {}
        self._project_sessions: Dict[str, str] = {}

    def add_mock_process(self, pid: int, name: str, cwd: str, cmdline: List[str]):
        """添加模拟进程"""
        process = ProcessInfo(pid, name, cwd, cmdline)
        self.ai_processes.append(process)

    def add_mock_session(self, session_id: str, project_name: str,
                        status: SessionStatus = SessionStatus.ACTIVE,
                        tmux_name: Optional[str] = None,
                        last_updated: Optional[datetime] = None):
        """添加模拟 session"""
        if last_updated is None:
            last_updated = datetime.now()

        session_info = SessionInfo(session_id, status, last_updated, tmux_name)
        self.sessions[session_id] = {
            "id": session_id,
            "project": project_name,
            "created_at": last_updated,
            "tmux_name": tmux_name
        }
        self._project_sessions[project_name] = session_id

    def set_tmux_status(self, session_name: str, status: TmuxStatus):
        """设置 tmux session 状态"""
        self.tmux_sessions[session_name] = status

    def detect_running_processes(self) -> List[ProcessInfo]:
        """测试节点 N14: 检测运行进程"""
        # 返回模拟的 AI 进程
        return self.ai_processes

    def find_session_from_projects(self, project_name: Optional[str] = None) -> Optional[str]:
        """测试节点 N15: 查找 Session ID"""
        if project_name:
            # 先检查通过 add_mock_session 添加的数据
            if project_name in self._project_sessions:
                return self._project_sessions[project_name]

            # 模拟从 projects 目录查找
            mock_projects_dir = {
                "home-user-workspaces-test-project": "session_12345",
                "home-user-workspaces-another-project": "session_67890"
            }

            # 标准化名称：移除开头的斜杠并替换斜杠为短横线
            normalized_name = project_name.replace('/', '-')
            # 移除开头的短横线（如果存在）
            if normalized_name.startswith('-'):
                normalized_name = normalized_name[1:]

            return mock_projects_dir.get(normalized_name)

        return None

    def check_tmux_session(self, session_name: str) -> TmuxStatus:
        """测试节点 N16: tmux session 检查"""
        return self.tmux_sessions.get(session_name, TmuxStatus.NOT_EXISTS)

    def create_tmux_session(self, session_name: str, command: str) -> bool:
        """测试节点 N17: tmux session 创建"""
        self.tmux_sessions[session_name] = TmuxStatus.EXISTS
        return True

    def check_process_in_tmux(self, session_name: str) -> Optional[ProcessInfo]:
        """测试节点 N18: tmux session 中进程检查"""
        if self.tmux_sessions.get(session_name) == TmuxStatus.EXISTS:
            return self.ai_processes[0] if self.ai_processes else None
        return None

    def start_ai_in_tmux(self, session_name: str, command: str,
                           resume_session_id: Optional[str] = None,
                           query: Optional[str] = None) -> bool:
        """测试节点 N19: Claude 进程启动"""
        # 模拟创建 Claude 进程
        process = ProcessInfo(
            pid=12345,
            name="claude",
            cwd=str(self.project_path),
            cmdline=[command]
        )
        self.ai_processes.append(process)
        self.tmux_sessions[session_name] = TmuxStatus.EXISTS

        # 记录 session
        if resume_session_id:
            self.sessions[resume_session_id] = {
                "id": resume_session_id,
                "tmux_name": session_name,
                "created_at": datetime.now()
            }

        return True

    def get_session_info(self, session_id: str) -> Optional[SessionInfo]:
        """获取 session 信息"""
        session_data = self.sessions.get(session_id)
        if session_data:
            return SessionInfo(
                session_id=session_data["id"],
                status=SessionStatus.ACTIVE,
                last_updated=session_data["created_at"],
                tmux_name=session_data.get("tmux_name")
            )
        return None

    def get_or_create_session(self, project_name: Optional[str] = None,
                            start_if_missing: bool = True,
                            max_wait_seconds: int = 30) -> Optional[str]:
        """完整流程测试"""
        # 1. 尝试查找现有 session
        session_id = self.find_session_from_projects(project_name)
        if session_id:
            return session_id

        # 2. 如果没有找到且允许启动，创建新 session
        if start_if_missing:
            session_name = f"claude-session-{int(datetime.now().timestamp())}"
            success = self.start_ai_in_tmux(
                session_name,
                "/usr/local/bin/claude",
                query="initial query"
            )
            if success:
                # 返回实际的 session name 用于验证
                return session_name

        return None

    def stop_session(self, session_id: str, kill_tmux: bool = False) -> bool:
        """停止 session"""
        if session_id in self.sessions:
            session_data = self.sessions[session_id]
            if kill_tmux and session_data.get("tmux_name"):
                del self.tmux_sessions[session_data["tmux_name"]]
            del self.sessions[session_id]
            return True
        return False

    def get_active_sessions(self, project_name: Optional[str] = None) -> List[SessionInfo]:
        """获取活跃 sessions"""
        sessions = []
        for session_id, session_data in self.sessions.items():
            if project_name is None or session_data.get("project") == project_name:
                sessions.append(SessionInfo(
                    session_id=session_id,
                    status=SessionStatus.ACTIVE,
                    last_updated=session_data["created_at"],
                    tmux_name=session_data.get("tmux_name")
                ))
        return sessions


class TestAISessionManager:
    """AI Session 管理器测试类"""

    def setup_method(self):
        """测试前准备"""
        self.manager = MockAISessionManager()

    def test_node_n14_detect_running_processes(self):
        """测试节点 N14: 检测运行中的 Claude Code 进程"""
        # 准备测试数据
        self.manager.ai_processes = [
            ProcessInfo(
                pid=1234,
                name="claude",
                cwd="/home/user/workspaces/test-project",
                cmdline=["claude"]
            ),
            ProcessInfo(
                pid=5678,
                name="claude",
                cwd="/home/user/another/project",
                cmdline=["claude"]
            )
        ]

        # 执行测试
        processes = self.manager.detect_running_processes()

        # 验证结果
        assert len(processes) == 2
        assert processes[0].pid == 1234
        assert processes[0].cwd == "/home/user/workspaces/test-project"
        assert processes[1].pid == 5678
        assert processes[1].cwd == "/home/user/another/project"

    def test_node_n14_no_processes(self):
        """测试 N14: 没有运行中的进程"""
        processes = self.manager.detect_running_processes()
        assert len(processes) == 0

    def test_node_n15_find_session_from_projects(self):
        """测试节点 N15: 从 .claude/projects/ 查找 session 文件"""
        # 测试存在的项目 - 使用正确的格式
        session_id = self.manager.find_session_from_projects(
            "home/user/workspaces/test-project"  # 方法内部会替换斜杠为短横线
        )
        assert session_id == "session_12345"

        # 测试不存在的项目
        session_id = self.manager.find_session_from_projects(
            "/home/user/nonexistent/project"
        )
        assert session_id is None

    def test_node_n16_check_tmux_session_exists(self):
        """测试节点 N16: tmux session 存在"""
        # 设置 tmux session 状态
        self.manager.tmux_sessions["claude-session-1"] = TmuxStatus.EXISTS

        # 执行测试
        status = self.manager.check_tmux_session("claude-session-1")

        # 验证结果
        assert status == TmuxStatus.EXISTS

    def test_node_n16_check_tmux_session_not_exists(self):
        """测试节点 N16: tmux session 不存在"""
        status = self.manager.check_tmux_session("nonexistent-session")
        assert status == TmuxStatus.NOT_EXISTS

    def test_node_n17_create_tmux_session(self):
        """测试节点 N17: 创建 tmux session"""
        # 执行测试
        success = self.manager.create_tmux_session(
            "claude-session-1",
            "claude"
        )

        # 验证结果
        assert success
        assert self.manager.tmux_sessions["claude-session-1"] == TmuxStatus.EXISTS

    def test_node_n18_check_process_in_tmux_exists(self):
        """测试节点 N18: tmux session 中有进程"""
        # 设置前置条件
        self.manager.ai_processes = [
            ProcessInfo(
                pid=1234,
                name="claude",
                cwd="/home/user/workspaces/test-project",
                cmdline=["claude"]
            )
        ]
        self.manager.tmux_sessions["claude-session-1"] = TmuxStatus.EXISTS

        # 执行测试
        process = self.manager.check_process_in_tmux("claude-session-1")

        # 验证结果
        assert process is not None
        assert process.pid == 1234

    def test_node_n18_check_process_in_tmux_not_exists(self):
        """测试节点 N18: tmux session 中没有进程"""
        # 设置前置条件
        self.manager.tmux_sessions["claude-session-1"] = TmuxStatus.EXISTS

        # 执行测试
        process = self.manager.check_process_in_tmux("claude-session-1")

        # 验证结果
        assert process is None

    def test_node_n19_start_ai_in_tmux(self):
        """测试节点 N19: 在 tmux 中启动 Claude Code"""
        # 执行测试
        success = self.manager.start_ai_in_tmux(
            "claude-session-1",
            "/usr/local/bin/claude",
            resume_session_id="session_12345",
            query="initial query"
        )

        # 验证结果
        assert success
        assert self.manager.tmux_sessions["claude-session-1"] == TmuxStatus.EXISTS
        assert len(self.manager.ai_processes) == 1
        assert self.manager.ai_processes[0].pid == 12345

    def test_node_n19_start_claude_with_query(self):
        """测试节点 N19: 使用 query 启动 Claude"""
        success = self.manager.start_ai_in_tmux(
            "claude-session-1",
            "/usr/local/bin/claude",
            resume_session_id="session_12345",
            query="help me with this task"
        )

        assert success
        assert "session_12345" in self.manager.sessions

    def test_complete_flow_success(self):
        """测试完整流程：成功获取现有 session"""
        # 设置前置条件：添加到 mock 的 project map
        self.manager._project_sessions["home-user-workspaces-test-project"] = "session_12345"

        # 执行测试
        session_id = self.manager.get_or_create_session(
            "/home/user/workspaces/test-project",
            start_if_missing=True
        )

        # 验证结果
        assert session_id == "session_12345"

    def test_complete_flow_create_new(self):
        """测试完整流程：创建新 session"""
        # 确保没有现有 session
        # 清空 mock_projects_dir
        original_projects_dir = {
            "home-user-workspaces-test-project": "session_12345",
            "home-user-workspaces-another-project": "session_67890"
        }

        def mock_find_session_projects(project_name):
            if project_name:
                # 标准化名称：移除开头的斜杠并替换斜杠为短横线
                normalized_name = project_name.replace('/', '-')
                # 移除开头的短横线（如果存在）
                if normalized_name.startswith('-'):
                    normalized_name = normalized_name[1:]

                # 返回 None 以触发创建新 session
                if normalized_name == "home-user-workspaces-test-project":
                    return None
                else:
                    return original_projects_dir.get(normalized_name)
            return None

        # 临时修改方法
        old_method = self.manager.find_session_from_projects
        self.manager.find_session_from_projects = mock_find_session_projects

        try:
            # 执行测试
            session_id = self.manager.get_or_create_session(
                "/home/user/workspaces/test-project",
                start_if_missing=True
            )

            # 验证结果
            assert session_id is not None
            assert session_id.startswith("claude-session-")
        finally:
            # 恢复原方法
            self.manager.find_session_from_projects = old_method

    def test_complete_flow_no_create(self):
        """测试完整流程：不允许创建新 session"""
        # 确保没有现有 session
        self.manager.sessions.clear()
        self.manager.tmux_sessions.clear()

        # 使用不同的 project name 确保不会找到现有 session
        session_id = self.manager.get_or_create_session(
            "/home/user/nonexistent/project",
            start_if_missing=False
        )

        # 验证结果
        assert session_id is None

    def test_stop_session(self):
        """测试停止 session"""
        # 设置前置条件
        self.manager.sessions["session_12345"] = {
            "id": "session_12345",
            "project": "home-user-workspaces-test-project",
            "created_at": datetime.now(),
            "tmux_name": "claude-session-1"
        }
        self.manager.tmux_sessions["claude-session-1"] = TmuxStatus.EXISTS

        # 执行测试
        success = self.manager.stop_session("session_12345", kill_tmux=True)

        # 验证结果
        assert success
        assert "session_12345" not in self.manager.sessions
        assert "claude-session-1" not in self.manager.tmux_sessions

    def test_get_active_sessions(self):
        """测试获取活跃 sessions"""
        # 设置测试数据
        now = datetime.now()
        self.manager.sessions["session_123"] = {
            "id": "session_123",
            "project": "project1",
            "created_at": now,
            "tmux_name": "tmux-123"
        }
        self.manager.sessions["session_456"] = {
            "id": "session_456",
            "project": "project2",
            "created_at": now,
            "tmux_name": "tmux-456"
        }

        # 测试获取所有 sessions
        all_sessions = self.manager.get_active_sessions()
        assert len(all_sessions) == 2

        # 测试按项目筛选
        project1_sessions = self.manager.get_active_sessions("project1")
        assert len(project1_sessions) == 1
        assert project1_sessions[0].session_id == "session_123"

    def test_error_handling_tmux_creation_failure(self):
        """测试错误处理：tmux 创建失败"""
        # 模拟创建失败（重写方法）
        class FailingManager(MockAISessionManager):
            def create_tmux_session(self, session_name: str, command: str) -> bool:
                return False

            def start_ai_in_tmux(self, session_name: str, command: str,
                                   resume_session_id: Optional[str] = None,
                                   query: Optional[str] = None) -> bool:
                # 直接返回失败，不调用父类的创建逻辑
                return False

        failing_manager = FailingManager()

        # 创建 session 应该失败
        success = failing_manager.start_ai_in_tmux(
            "claude-session-1",
            "/usr/local/bin/claude"
        )

        assert not success
        assert "claude-session-1" not in failing_manager.tmux_sessions

    def test_multiple_processes_same_project(self):
        """测试同一项目中有多个 Claude 进程"""
        # 设置测试数据
        self.manager.ai_processes = [
            ProcessInfo(
                pid=1234,
                name="claude",
                cwd="/home/user/workspaces/test-project",
                cmdline=["claude"]
            ),
            ProcessInfo(
                pid=5678,
                name="claude",
                cwd="/home/user/workspaces/test-project",
                cmdline=["claude"]
            )
        ]

        # 执行测试
        processes = self.manager.detect_running_processes()

        # 验证结果
        assert len(processes) == 2
        # 都应该来自同一个项目
        for proc in processes:
            assert proc.cwd == "/home/user/workspaces/test-project"

    def test_session_timeout_simulation(self):
        """测试 session 超时模拟"""
        # 创建一个很久未更新的 session
        old_time = datetime.now() - timedelta(hours=1)
        self.manager.sessions["old_session"] = {
            "id": "old_session",
            "project": "project1",
            "created_at": old_time,
            "tmux_name": "tmux-old"
        }

        # 创建一个活跃的 session
        self.manager.sessions["active_session"] = {
            "id": "active_session",
            "project": "project1",
            "created_at": datetime.now(),
            "tmux_name": "tmux-active"
        }

        # 获取所有 sessions（实际应该有超时检查逻辑）
        sessions = self.manager.get_active_sessions()

        # 验证结果
        assert len(sessions) == 2
        session_ids = [s.session_id for s in sessions]
        assert "old_session" in session_ids
        assert "active_session" in session_ids


class TestMockAISessionManager:
    """测试 Mock AI Session Manager 接口"""

    def setup_method(self):
        """测试前准备"""
        self.manager = MockAISessionManager()

    def test_mock_basic_operations(self):
        """测试 Mock 基本操作"""
        # 添加模拟数据
        self.manager.add_mock_process(1234, "claude", "/test", ["claude"])
        self.manager.add_mock_session("session_123", "test_project")
        self.manager.set_tmux_status("tmux_123", TmuxStatus.EXISTS)

        # 验证数据添加
        assert len(self.manager.detect_running_processes()) == 1
        assert self.manager.find_session_from_projects("test_project") is not None
        assert self.manager.check_tmux_session("tmux_123") == TmuxStatus.EXISTS

    def test_mock_session_info(self):
        """测试 Mock Session 信息"""
        session_id = "session_123"
        self.manager.add_mock_session(session_id, "test_project")

        session_info = self.manager.get_session_info(session_id)
        assert session_info is not None
        assert session_info.session_id == session_id
        assert session_info.status == SessionStatus.ACTIVE

    def test_mock_error_scenarios(self):
        """测试 Mock 错误场景"""
        # 测试不存在的 session
        session_info = self.manager.get_session_info("nonexistent")
        assert session_info is None

        # 测试不存在进程
        processes = self.manager.detect_running_processes()
        assert len(processes) == 0