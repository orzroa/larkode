"""
工作空间切换验证测试 - 真实 AI 执行

切换到两个工作空间，让 Claude 读取文件，验证 stop 卡片内容

运行方式：
    pytest tests/integration/test_workspace_switch_verify.py -v -s

注意：
    需要在 .env 中配置 FEISHU_HOOK_NOTIFICATION_USER_ID
    测试会真实发送飞书卡片，Claude 会真实执行命令
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
        env["TEST_MODE_ENABLED"] = "true"
        # 配置测试工作空间
        env["WORKSPACE_DISCOVERY_ENABLED"] = "True"
        env["WORKSPACE_ROOT_DIR"] = str(PROJECT_ROOT / "docs/testcases/workspace_switch_test")
        env["WORKSPACE_DEFAULT_DIR"] = str(PROJECT_ROOT / "docs/testcases/workspace_switch_test/workspace_alpha")

        self.process = subprocess.Popen(
            [sys.executable, str(PROJECT_ROOT / "larkode.py")],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            cwd=str(PROJECT_ROOT)
        )

        if not self._wait_for_service():
            self.stop()
            raise RuntimeError("服务启动失败")

        print(f"✅ 服务已启动，PID: {self.process.pid}")

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
                print(f"❌ 进程已退出: {stderr.decode()}")
                return False

            time.sleep(1)

        return False

    def stop(self):
        """停止服务"""
        if self.process:
            print(f"\n🛑 正在停止服务，PID: {self.process.pid}")
            try:
                self.process.terminate()
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            print("✅ 服务已停止")


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
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=300)) as session:
        yield session


@pytest.fixture(scope="module")
def user_id():
    """获取飞书用户 ID"""
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")

    uid = os.getenv("FEISHU_HOOK_NOTIFICATION_USER_ID")
    if not uid:
        pytest.skip("❌ 未配置 FEISHU_HOOK_NOTIFICATION_USER_ID，跳过端到端测试")
    return uid


class TestWorkspaceSwitchVerify:
    """工作空间切换验证测试 - 真实 AI 执行

    测试流程：
    1. 切换到 workspace_alpha
    2. 让 Claude 读取 README.md
    3. 收到 stop 卡片，验证内容是 "Content from Alpha workspace"

    4. 切换到 workspace_beta
    5. 让 Claude 读取 README.md
    6. 收到 stop 卡片，验证内容是 "Content from Beta workspace"

    7. 切换回 workspace_alpha
    8. 让 Claude 再次读取 README.md
    9. 收到 stop 卡片，验证内容是 "Content from Alpha workspace"

    10. 人工确认结果
    """

    @pytest.mark.asyncio
    async def test_01_switch_to_alpha(self, service, http_session, user_id):
        """步骤1: 切换到 workspace_alpha"""
        print(f"\n" + "="*60)
        print(f"📤 步骤1: 切换到 workspace_alpha")
        print("="*60)

        async with http_session.post(
            f"{API_BASE_URL}/api/test-command",
            json={"user_id": user_id, "command": "#ws 1"}
        ) as resp:
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "processed"

        print("✅ 切换命令已发送")
        print("📱 请在飞书中查看切换成功卡片")
        await asyncio.sleep(2)

    @pytest.mark.asyncio
    async def test_02_read_file_in_alpha(self, service, http_session, user_id):
        """步骤2: 在 alpha 工作空间读取文件"""
        print(f"\n" + "="*60)
        print(f"📤 步骤2: 让 Claude 读取 test_file.txt（Alpha 工作空间）")
        print("="*60)

        async with http_session.post(
            f"{API_BASE_URL}/api/test-command",
            json={"user_id": user_id, "command": "读取 test_file.txt 文件内容"}
        ) as resp:
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "processed"

        print("✅ 命令已发送，Claude 正在执行...")
        print("⏳ 等待 Claude 完成执行（预计 10-30 秒）")
        print("📱 完成后你将收到 stop 卡片")
        print("🎯 预期内容：'Content from Alpha workspace'")

        # 等待 Claude 执行完成
        await asyncio.sleep(30)

    @pytest.mark.asyncio
    async def test_03_switch_to_beta(self, service, http_session, user_id):
        """步骤3: 切换到 workspace_beta"""
        print(f"\n" + "="*60)
        print(f"📤 步骤3: 切换到 workspace_beta")
        print("="*60)

        async with http_session.post(
            f"{API_BASE_URL}/api/test-command",
            json={"user_id": user_id, "command": "#ws 2"}
        ) as resp:
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "processed"

        print("✅ 切换命令已发送")
        print("📱 请在飞书中查看切换成功卡片")
        await asyncio.sleep(2)

    @pytest.mark.asyncio
    async def test_04_read_file_in_beta(self, service, http_session, user_id):
        """步骤4: 在 beta 工作空间读取文件"""
        print(f"\n" + "="*60)
        print(f"📤 步骤4: 让 Claude 读取 test_file.txt（Beta 工作空间）")
        print("="*60)

        async with http_session.post(
            f"{API_BASE_URL}/api/test-command",
            json={"user_id": user_id, "command": "读取 test_file.txt 文件内容"}
        ) as resp:
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "processed"

        print("✅ 命令已发送，Claude 正在执行...")
        print("⏳ 等待 Claude 完成执行（预计 10-30 秒）")
        print("📱 完成后你将收到 stop 卡片")
        print("🎯 预期内容：'Content from Beta workspace'")

        # 等待 Claude 执行完成
        await asyncio.sleep(30)

    @pytest.mark.asyncio
    async def test_05_switch_back_to_alpha(self, service, http_session, user_id):
        """步骤5: 切换回 workspace_alpha"""
        print(f"\n" + "="*60)
        print(f"📤 步骤5: 切换回 workspace_alpha")
        print("="*60)

        async with http_session.post(
            f"{API_BASE_URL}/api/test-command",
            json={"user_id": user_id, "command": "#ws 1"}
        ) as resp:
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "processed"

        print("✅ 切换命令已发送")
        print("📱 请在飞书中查看切换成功卡片")
        await asyncio.sleep(2)

    @pytest.mark.asyncio
    async def test_06_read_file_in_alpha_again(self, service, http_session, user_id):
        """步骤6: 在 alpha 工作空间再次读取文件"""
        print(f"\n" + "="*60)
        print(f"📤 步骤6: 让 Claude 再次读取 test_file.txt（Alpha 工作空间）")
        print("="*60)

        async with http_session.post(
            f"{API_BASE_URL}/api/test-command",
            json={"user_id": user_id, "command": "读取 test_file.txt 文件内容"}
        ) as resp:
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "processed"

        print("✅ 命令已发送，Claude 正在执行...")
        print("⏳ 等待 Claude 完成执行（预计 10-30 秒）")
        print("📱 完成后你将收到 stop 卡片")
        print("🎯 预期内容：'Content from Alpha workspace'（验证切回 alpha 成功）")

        # 等待 Claude 执行完成
        await asyncio.sleep(30)

    @pytest.mark.asyncio
    async def test_07_human_verification(self, service, user_id):
        """步骤7: 人工确认结果"""
        print(f"\n" + "="*60)
        print(f"✅ 所有命令已发送完成！")
        print("="*60)
        print("\n📱 请在飞书中确认收到的卡片：")
        print("\n1️⃣  切换到 Alpha 成功卡片（绿色）")
        print("    标题：[workspace_alpha] 成功")

        print("\n2️⃣  Alpha 工作空间的 stop 卡片")
        print("    内容应包含：'Content from Alpha workspace'")
        print("    （这是 Claude 读取 test_file.txt 的结果）")

        print("\n3️⃣  切换到 Beta 成功卡片（绿色）")
        print("    标题：[workspace_beta] 成功")

        print("\n4️⃣  Beta 工作空间的 stop 卡片")
        print("    内容应包含：'Content from Beta workspace'")
        print("    （这是 Claude 读取 test_file.txt 的结果）")

        print("\n5️⃣  切换回 Alpha 成功卡片（绿色）")
        print("    标题：[workspace_alpha] 成功")

        print("\n6️⃣  Alpha 工作空间的 stop 卡片（第二次）")
        print("    内容应包含：'Content from Alpha workspace'")
        print("    （验证切回 alpha 后确实在 alpha 工作空间）")

        print("\n" + "="*60)
        print("🔍 验证要点：")
        print("="*60)
        print("✅ 三个 stop 卡片的内容应该遵循：Alpha -> Beta -> Alpha 的顺序")
        print("✅ Alpha 的 stop 卡片内容：'Content from Alpha workspace'")
        print("✅ Beta 的 stop 卡片内容：'Content from Beta workspace'")
        print("✅ 切回 Alpha 后的 stop 卡片内容：'Content from Alpha workspace'")
        print("✅ 这证明了工作空间切换功能完全正常")
        print("="*60)
        print("="*60)

        print("\n⏳ 测试完成，服务将继续运行 5 分钟...")
        print("   你可以在飞书中查看所有卡片")
        await asyncio.sleep(5)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])