"""
pytest 配置 - 设置全局测试模式
"""
import os
import subprocess

import pytest


# 已知用户使用的 tmux sessions（不应该被清理）
KNOWN_SESSIONS = {
    "cc-home-sc-Workspaces-github-aiTermLark",
    "cc-home-sc-Workspaces-github-larkode",
}


def pytest_configure(config):
    """pytest 启动时设置测试模式"""
    os.environ["TEST_MODE_ENABLED"] = "true"


def pytest_unconfigure(config):
    """pytest 结束时清除测试模式"""
    os.environ.pop("TEST_MODE_ENABLED", None)


@pytest.fixture(autouse=True)
def cleanup_after_test():
    """每个测试后恢复 settings 并清理 tmux sessions"""
    yield
    # 测试结束后重新加载 settings
    try:
        from src.config.settings import reload_settings
        reload_settings()
    except Exception:
        pass

    # 清理测试可能创建的 tmux sessions（除了已知用户 sessions）
    try:
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            sessions = result.stdout.strip().split('\n')
            for session in sessions:
                if session and session not in KNOWN_SESSIONS:
                    subprocess.run(
                        ["tmux", "kill-session", "-t", session],
                        capture_output=True,
                        timeout=5
                    )
    except Exception:
        pass
