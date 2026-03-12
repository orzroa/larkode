"""
API 命令端到端测试

通过 controller 触发发送 3 条命令到飞书（按顺序）：
1. #help - 帮助卡片
2. #history - 历史卡片
3. #shot 10 - 截屏卡片（10行）

运行方式：
    pytest tests/integration/test_api_commands.py -v
"""
import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import pytest
import pytest_asyncio
import aiohttp

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent
LOG_FILE = PROJECT_ROOT / "logs" / "app.log"
API_BASE_URL = "http://127.0.0.1:18080"


class APIServiceManager:
    """管理 API 服务的启动和停止"""

    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.startup_timeout = 30

    def start(self):
        """启动服务"""
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

        if LOG_FILE.exists():
            backup_file = LOG_FILE.with_suffix('.log.backup')
            LOG_FILE.rename(backup_file)

        env = os.environ.copy()
        env["PYTHONPATH"] = str(PROJECT_ROOT)
        env["TEST_MODE_ENABLED"] = "true"  # 启用测试模式（自动启动 API 服务器 + 标记消息）

        self.process = subprocess.Popen(
            [sys.executable, str(PROJECT_ROOT / "ai_term_lark.py")],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            cwd=str(PROJECT_ROOT)
        )

        if not self._wait_for_service():
            self.stop()
            raise RuntimeError("服务启动失败")

        print(f"服务已启动，PID: {self.process.pid}")

    def _wait_for_service(self) -> bool:
        """等待服务启动"""
        start_time = time.time()

        while time.time() - start_time < self.startup_timeout:
            try:
                import urllib.request
                req = urllib.request.Request(f"{API_BASE_URL}/api/health")
                with urllib.request.urlopen(req, timeout=2) as response:
                    if response.status == 200:
                        return True
            except Exception:
                pass

            if self.process.poll() is not None:
                stdout, stderr = self.process.communicate()
                print(f"进程已退出: {stderr.decode()}")
                return False

            time.sleep(1)

        return False

    def stop(self):
        """停止服务"""
        if self.process:
            print(f"正在停止服务，PID: {self.process.pid}")
            try:
                self.process.terminate()
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            print("服务已停止")


@pytest.fixture(scope="module")
def service():
    """启动和停止服务"""
    manager = APIServiceManager()
    manager.start()
    yield manager
    manager.stop()


@pytest_asyncio.fixture
async def http_session():
    """提供 aiohttp session"""
    async with aiohttp.ClientSession() as session:
        yield session


@pytest.fixture(scope="module")
def user_id():
    """获取飞书用户 ID"""
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")

    uid = os.getenv("FEISHU_HOOK_NOTIFICATION_USER_ID")
    if not uid:
        pytest.skip("未配置 FEISHU_HOOK_NOTIFICATION_USER_ID，跳过集成测试")
    return uid


class TestAPICommands:
    """API 命令端到端测试 - 发送 3 条真实消息到飞书

    顺序：帮助 → 历史 → 截屏(10行)
    """

    @pytest.mark.asyncio
    async def test_01_help(self, service, http_session, user_id):
        """测试 #help 命令"""
        async with http_session.post(
            f"{API_BASE_URL}/api/test-command",
            json={"user_id": user_id, "command": "#help"}
        ) as resp:
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "processed"

        print(f"\n✅ #help 命令已发送到飞书用户: {user_id}")
        await asyncio.sleep(0.5)

    @pytest.mark.asyncio
    async def test_02_history(self, service, http_session, user_id):
        """测试 #history 命令"""
        async with http_session.post(
            f"{API_BASE_URL}/api/test-command",
            json={"user_id": user_id, "command": "#history"}
        ) as resp:
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "processed"

        print(f"\n✅ #history 命令已发送到飞书用户: {user_id}")
        await asyncio.sleep(0.5)

    @pytest.mark.asyncio
    async def test_03_shot(self, service, http_session, user_id):
        """测试 #shot 10 命令（10行截屏）"""
        async with http_session.post(
            f"{API_BASE_URL}/api/test-command",
            json={"user_id": user_id, "command": "#shot 10"}
        ) as resp:
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "processed"

        print(f"\n✅ #shot 10 命令已发送到飞书用户: {user_id}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])