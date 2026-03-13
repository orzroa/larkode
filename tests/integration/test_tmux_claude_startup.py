"""
集成测试：TMUX + Claude 启动验证

测试场景：
1. 创建 tmux 会话 ccui（在 /tmp/claude_integration_test 目录）
2. 拉起 TMUX 会话并启动 Claude
3. 发送测试命令 (1+1)
4. 发送 /quit 退出
5. 验证基本流程正常
"""
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

import pytest

# 测试配置
TEST_SESSION_NAME = "ccui"
TEST_WORKSPACE = Path("/tmp/claude_integration_test")
TEST_COMMAND = "1+1"

# 从 .env 读取 Claude CLI 路径
def _get_claude_cli_path() -> str:
    """从 .env 读取 Claude CLI 路径"""
    project_root = Path(__file__).parent.parent.parent
    env_file = project_root / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                if line.startswith("CLAUDE_CODE_CLI_PATH="):
                    return line.split("=", 1)[1].strip()
    return "claude"  # 默认值


def _is_claude_available() -> bool:
    """检查 Claude CLI 是否可用"""
    import shutil
    # 使用 shutil.which 检查 claude 是否在 PATH 中
    return shutil.which("claude") is not None


class TestTmuxClaudeStartup:
    """测试 TMUX + Claude 完整启动流程"""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """测试前后清理"""
        self._kill_session(TEST_SESSION_NAME)

        # 清理测试目录
        if TEST_WORKSPACE.exists():
            import shutil
            shutil.rmtree(TEST_WORKSPACE)

        yield

        # 测试后清理
        self._kill_session(TEST_SESSION_NAME)

        if TEST_WORKSPACE.exists():
            import shutil
            shutil.rmtree(TEST_WORKSPACE)

    def _kill_session(self, session_name: str):
        """Kill tmux session if exists"""
        try:
            subprocess.run(
                ["tmux", "kill-session", "-t", session_name],
                capture_output=True,
                timeout=5
            )
        except Exception:
            pass

    def _create_workspace(self) -> Path:
        """创建测试工作目录"""
        TEST_WORKSPACE.mkdir(parents=True, exist_ok=True)
        return TEST_WORKSPACE

    def _create_claude_settings(self, workspace_dir: Path, hook_script_path: str) -> Path:
        """为临时目录创建 Claude 设置文件（配置 hook 并设置环境变量）"""
        claude_dir = workspace_dir / ".claude"
        claude_dir.mkdir(exist_ok=True)

        settings_file = claude_dir / "settings.json"

        # 获取项目根目录
        project_root = Path(__file__).parent.parent.parent

        # 构建 hook 命令，包含 PYTHONPATH 环境变量设置
        # 这样 hook_handler.py 就能找到项目模块
        hook_cmd = f'PYTHONPATH={project_root}:$PYTHONPATH python3 {hook_script_path}'

        settings = {
            "hooks": {
                "UserPromptSubmit": [
                    {"hooks": [{"type": "command", "command": hook_cmd, "timeout": 30}]}
                ],
                "Stop": [
                    {"hooks": [{"type": "command", "command": hook_cmd, "timeout": 30}]}
                ],
                "PermissionRequest": [
                    {"hooks": [{"type": "command", "command": hook_cmd, "timeout": 30}]}
                ]
            }
        }

        with open(settings_file, "w") as f:
            json.dump(settings, f, indent=2)

        return settings_file

    def _create_tmux_session(self, session_name: str, workspace_dir: Path, cli_path: str = "claude") -> bool:
        """创建 tmux session 并启动 Claude"""
        try:
            cmd = [
                "tmux", "new-session", "-d",
                "-s", session_name,
                "-n", "ai",
                f"mkdir -p {workspace_dir} && cd {workspace_dir} && {cli_path}"
            ]

            # 打印整个cmd
            print(cmd)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                print(f"创建 session 失败: {result.stderr}")
                return False

            print(f"tmux session {session_name} 已创建")
            return True
        except Exception as e:
            print(f"创建 tmux session 失败: {e}")
            return False

    def _send_command_to_session(self, session_name: str, command: str):
        """发送命令到 tmux session"""
        try:
            # 先 C-u 清除当前输入行
            subprocess.run(
                ["tmux", "send-keys", "-t", session_name, "C-u"],
                capture_output=True,
                timeout=5
            )

            # 发送命令
            subprocess.run(
                ["tmux", "send-keys", "-t", session_name, command],
                capture_output=True,
                timeout=5
            )

            # 发送 Enter
            time.sleep(0.5)
            subprocess.run(
                ["tmux", "send-keys", "-t", session_name, "C-m"],
                capture_output=True,
                timeout=5
            )

            print(f"已发送命令: {command}")
        except Exception as e:
            print(f"发送命令失败: {e}")

    def _send_quit(self, session_name: str):
        """发送 /quit 退出 Claude"""
        try:
            time.sleep(1)
            # 清除当前输入
            subprocess.run(
                ["tmux", "send-keys", "-t", session_name, "C-u"],
                capture_output=True,
                timeout=5
            )

            # 发送 /quit
            subprocess.run(
                ["tmux", "send-keys", "-t", session_name, "/quit"],
                capture_output=True,
                timeout=5
            )

            # 发送 Enter
            time.sleep(0.5)
            subprocess.run(
                ["tmux", "send-keys", "-t", session_name, "C-m"],
                capture_output=True,
                timeout=5
            )

            print("已发送 /quit 命令")
        except Exception as e:
            print(f"发送 /quit 失败: {e}")

    def _wait_for_claude_ready(self, session_name: str, timeout: int = 30) -> bool:
        """等待 Claude 启动完成"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                result = subprocess.run(
                    ["tmux", "capture-pane", "-p", "-t", session_name],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                output = result.stdout
                # 检查是否有提示符或响应（Claude 启动完成的标志）
                if ">" in output or "You" in output or "claude" in output.lower():
                    time.sleep(2)  # 额外等待确保完全初始化
                    return True
            except Exception:
                pass
            time.sleep(1)

        print("等待 Claude 启动超时")
        return False

    def _get_hook_log_path(self) -> Path:
        """获取 hook 日志文件路径"""
        project_root = Path(__file__).parent.parent.parent
        return project_root / "logs" / "hook_events.jsonl"

    def _get_session_hook_events(self, workspace_dir: Path) -> list:
        """从 hook 日志中获取特定 workspace 的事件"""
        log_path = self._get_hook_log_path()
        events = []

        if not log_path.exists():
            return events

        workspace_str = str(workspace_dir)
        with open(log_path, "r") as f:
            for line in f:
                try:
                    event = json.loads(line.strip())
                    # 过滤出工作目录匹配的事件
                    stdin_parsed = event.get("stdin_parsed") or {}
                    # 优先使用 cwd 字段（Claude Code 新版）
                    working_dir = stdin_parsed.get("cwd", "") or ""
                    if workspace_str in working_dir:
                        events.append(event)
                except (json.JSONDecodeError, AttributeError):
                    continue

        return events

    @pytest.mark.skipif(
        not _is_claude_available(),
        reason="Claude Code CLI (claude or ccr) not found in PATH"
    )
    def test_tmux_claude_startup_with_session_start_hook(self):
        """
        测试 TMUX + Claude 启动流程

        测试步骤：
        1. 创建测试工作目录 /tmp/claude_integration_test
        2. 创建 tmux session ccui 并启动 Claude
        3. 等待 Claude 初始化
        4. 发送计算命令 (1+1)
        5. 发送 /quit 退出
        6. 验证基本流程正常

        注：由于 Claude Code 新版本的 hook 配置格式变化（需要 matchers），
        暂时不验证 hook 日志，待格式稳定后再添加。
        """
        # 1. 创建测试工作目录
        workspace_dir = self._create_workspace()
        print(f"创建测试工作目录: {workspace_dir}")

        # 2. 创建 tmux session 并启动 Claude
        success = self._create_tmux_session(TEST_SESSION_NAME, workspace_dir, _get_claude_cli_path())
        assert success, f"创建 tmux session {TEST_SESSION_NAME} 失败"

        # 3. 等待 Claude 启动
        print("等待 Claude 启动...")
        ready = self._wait_for_claude_ready(TEST_SESSION_NAME, timeout=30)
        assert ready, "Claude 启动超时或失败"

        # 捕获启动后的输出
        result = subprocess.run(
            ["tmux", "capture-pane", "-p", "-t", TEST_SESSION_NAME, "-e"],
            capture_output=True,
            text=True,
            timeout=5
        )
        print(f"Claude 启动后输出: {result.stdout[:500]}")

        # 4. 发送计算命令
        print(f"发送命令: {TEST_COMMAND}")
        self._send_command_to_session(TEST_SESSION_NAME, TEST_COMMAND)

        # 等待命令执行
        time.sleep(10)

        # 5. 发送 /quit 退出
        print("发送 /quit 退出...")
        self._send_quit(TEST_SESSION_NAME)

        # 等待退出完成和 hook 写入
        time.sleep(8)

        # 6. 检查 tmux session 是否还存在
        result = subprocess.run(
            ["tmux", "has-session", "-t", TEST_SESSION_NAME],
            capture_output=True,
            timeout=5
        )

        # 如果 session 存在，手动结束它
        if result.returncode == 0:
            print("Session 仍然存在，强制结束")
            self._kill_session(TEST_SESSION_NAME)

        # 7. 验证 hook 日志
        print("验证 hook 日志...")
        events = self._get_session_hook_events(workspace_dir)

        print(f"获取到 {len(events)} 条事件:")
        for event in events:
            hook_event = event.get("hook_event", "unknown")
            cwd = event.get("stdin_parsed", {}).get("cwd", "") or ""
            print(f"  - {hook_event}: {cwd}")

        # 验证包含 UserPromptSubmit 事件（发送了 1+1 命令）
        prompt_events = [e for e in events if e.get("hook_event") == "UserPromptSubmit"]
        assert len(prompt_events) > 0, "Hook 日志中应该包含 UserPromptSubmit 事件"

        print(f"验证通过: 捕获到 {len(prompt_events)} 条 UserPromptSubmit 事件")
        print("TMUX + Claude 启动流程验证完成!")

    @pytest.mark.skipif(
        not _is_claude_available(),
        reason="Claude Code CLI (claude or ccr) not found in PATH"
    )
    def test_multiple_sessions(self):
        """
        测试多个会话场景（可选）

        验证不同 session 名称的事件能正确区分
        """
        # 这个测试可以扩展为测试多个会话
        # 但基本逻辑与上面相同，这里略过
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
