"""
API 命令端到端测试

直接调用业务逻辑，真实发送飞书卡片：
1. #help - 帮助卡片
2. #history - 历史卡片
3. #shot 10 - 截屏卡片（10行）

运行方式：
    pytest tests/integration/test_api_commands.py -v -s

注意：
    需要在 .env 中配置 FEISHU_HOOK_NOTIFICATION_USER_ID
    测试会真实发送飞书卡片，请在飞书中查看
"""
from pathlib import Path

import pytest

from src.handlers.platform_commands import PlatformCommands
from src.im_platforms.feishu import FeishuCardBuilder
from src.task_manager import task_manager

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent


@pytest.fixture
def platform_commands(send_func):
    """创建 PlatformCommands 实例"""
    return PlatformCommands(
        task_manager=task_manager,
        card_builder=FeishuCardBuilder(),
        send_via_sender=send_func,
    )


class TestAPICommands:
    """API 命令端到端测试 - 入口直接调用，出口真实发送飞书

    顺序：帮助 → 历史 → 截屏(10行)
    """

    @pytest.mark.asyncio
    async def test_01_help(self, platform_commands, user_id):
        """测试 #help 命令"""
        print(f"\n{'='*60}")
        print(f"📤 测试 1: 发送 #help 命令")
        print(f"{'='*60}")
        
        await platform_commands.handle_command(user_id, "#help")
        
        print("   📤 已发送飞书卡片: 帮助")
        print("✅ #help 命令测试完成")

    @pytest.mark.asyncio
    async def test_02_history(self, platform_commands, user_id):
        """测试 #history 命令"""
        print(f"\n{'='*60}")
        print(f"📤 测试 2: 发送 #history 命令")
        print(f"{'='*60}")
        
        await platform_commands.handle_command(user_id, "#history")
        
        print("   📤 已发送飞书卡片: 历史")
        print("✅ #history 命令测试完成")

    @pytest.mark.asyncio
    async def test_03_shot(self, platform_commands, user_id):
        """测试 #shot 10 命令（10行截屏）"""
        print(f"\n{'='*60}")
        print(f"📤 测试 3: 发送 #shot 10 命令")
        print(f"{'='*60}")
        
        await platform_commands.handle_command(user_id, "#shot 10")
        
        print("   📤 已发送飞书卡片: 截屏(10行)")
        print("✅ #shot 10 命令测试完成")

        print(f"\n{'='*60}")
        print("🎉 端到端测试完成！")
        print("📱 请在飞书中确认收到了 3 张卡片")
        print(f"{'='*60}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
