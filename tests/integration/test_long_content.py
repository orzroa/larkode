#!/usr/bin/env -S uv run --no-project
# /// script
# dependencies = [
#   "lark-oapi>=1.5.3",
#   "python-dotenv>=1.0.0",
#   "pydantic>=2.5.3",
#   "pydantic-settings>=2.0.0",
#   "psutil>=5.9.0",
#   "aiohttp>=3.8.0",
#   "pytest-asyncio>=0.21.0"
# ]
# ///
"""
长内容文件发送功能集成测试

测试当 Hook 通知内容超长时，系统是否正确生成文件并发送。
发送 3 条消息到飞书：
1. 短消息 - 不生成文件，直接发送卡片
2. 长消息 - 生成文件，同时发送卡片和文件
3. 长消息禁用文件模式 - 截断内容，不生成文件

运行方式：
    # 通过 pytest 运行
    pytest tests/integration/test_long_content.py -v

    # 直接运行
    python3 tests/integration/test_long_content.py
"""
import asyncio
import os
import sys
from pathlib import Path

import pytest
import pytest_asyncio

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 设置项目根目录为当前工作目录
os.chdir(PROJECT_ROOT)

from src.hook_handler import send_feishu_notification


@pytest.fixture(scope="module")
def user_id():
    """获取飞书用户 ID"""
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")

    uid = os.getenv("FEISHU_HOOK_NOTIFICATION_USER_ID")
    if not uid:
        pytest.skip("未配置 FEISHU_HOOK_NOTIFICATION_USER_ID，跳过集成测试")
    return uid


class TestLongContent:
    """长内容测试类 - 发送 3 条消息 + 1 个文件"""

    @pytest.mark.asyncio
    async def test_short_message(self, user_id):
        """测试短消息（低于阈值），预期不生成文件"""
        print("\n" + "=" * 60)
        print("测试 1/3: 短消息（预期不生成文件）")
        print("=" * 60)

        # 设置较大的阈值，确保消息不超过
        os.environ["CARD_MAX_LENGTH"] = "2000"
        os.environ["USE_FILE_FOR_LONG_CONTENT"] = "true"

        # 构建短消息（约100字符）
        short_message = "这是一条短消息测试。内容较短，应该在卡片中完整显示，不需要生成文件。"

        print(f"消息长度: {len(short_message)} 字符")
        print(f"阈值: {os.environ['CARD_MAX_LENGTH']} 字符")

        # 发送消息
        result = await send_feishu_notification(short_message, "stop", "LongContent-Short")

        assert result, "发送失败"
        print("✅ 发送成功！请检查飞书是否收到完整内容的卡片，无文件")
        await asyncio.sleep(0.5)

    @pytest.mark.asyncio
    async def test_long_message(self, user_id):
        """测试长消息（高于阈值），预期生成文件并发送"""
        print("\n" + "=" * 60)
        print("测试 2/3: 长消息（预期生成文件）")
        print("=" * 60)

        # 设置较小的阈值（100字符），确保长消息超过阈值
        os.environ["CARD_MAX_LENGTH"] = "100"
        os.environ["USE_FILE_FOR_LONG_CONTENT"] = "true"

        # 构建长消息（重复内容约300字符）
        long_message = "这是一条长消息测试。" * 10
        long_message += "\n" + "内容超长，应该生成文件。" * 5

        print(f"消息长度: {len(long_message)} 字符")
        print(f"阈值: {os.environ['CARD_MAX_LENGTH']} 字符")
        print(f"USE_FILE_FOR_LONG_CONTENT: {os.environ['USE_FILE_FOR_LONG_CONTENT']}")

        # 发送消息
        result = await send_feishu_notification(long_message, "stop", "LongContent-Long")

        assert result, "发送失败"
        print("✅ 发送成功！请检查飞书是否收到卡片消息 + 文件消息")
        await asyncio.sleep(0.5)

    @pytest.mark.asyncio
    async def test_long_message_without_file(self, user_id):
        """测试长消息禁用文件模式，预期截断不生成文件"""
        print("\n" + "=" * 60)
        print("测试 3/3: 长消息（禁用文件模式，预期截断）")
        print("=" * 60)

        # 设置较小的阈值（100字符），确保长消息超过阈值
        # 禁用文件模式
        os.environ["CARD_MAX_LENGTH"] = "100"
        os.environ["USE_FILE_FOR_LONG_CONTENT"] = "false"

        # 构建长消息（重复内容约300字符）
        long_message = "这是一条长消息测试。" * 10
        long_message += "\n" + "内容超长，应该截断但不生成文件。" * 5

        print(f"消息长度: {len(long_message)} 字符")
        print(f"阈值: {os.environ['CARD_MAX_LENGTH']} 字符")
        print(f"USE_FILE_FOR_LONG_CONTENT: {os.environ['USE_FILE_FOR_LONG_CONTENT']}")

        # 发送消息
        result = await send_feishu_notification(long_message, "stop", "LongContent-Truncated")

        assert result, "发送失败"
        print("✅ 发送成功！请检查飞书是否收到截断内容的卡片，无文件")


def main():
    """直接运行时的入口函数"""
    print("\n" + "=" * 60)
    print("长内容文件发送功能集成测试")
    print("=" * 60)

    # 检查环境变量
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")

    user_id = os.getenv("FEISHU_HOOK_NOTIFICATION_USER_ID")
    if not user_id:
        print("❌ 错误：未配置 FEISHU_HOOK_NOTIFICATION_USER_ID")
        print("请在 .env 文件中设置：FEISHU_HOOK_NOTIFICATION_USER_ID=ou_xxxxx")
        return 1

    print(f"目标用户 ID: {user_id}")
    print(f"项目目录: {PROJECT_ROOT}")
    print("将发送 3 条消息到飞书...\n")

    # 运行测试
    results = []

    async def run_tests():
        # 测试 1: 短消息
        try:
            await TestLongContent().test_short_message(user_id)
            results.append(("短消息", True))
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            results.append(("短消息", False))
        await asyncio.sleep(0.5)

        # 测试 2: 长消息
        try:
            await TestLongContent().test_long_message(user_id)
            results.append(("长消息+文件", True))
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            results.append(("长消息+文件", False))
        await asyncio.sleep(0.5)

        # 测试 3: 长消息禁用文件
        try:
            await TestLongContent().test_long_message_without_file(user_id)
            results.append(("长消息+截断", True))
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            results.append(("长消息+截断", False))

    asyncio.run(run_tests())

    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    for name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{name}: {status}")
    print("=" * 60)

    success_count = sum(1 for _, s in results if s)
    print(f"\n总计: {success_count}/3 成功")

    if success_count == 3:
        print("\n🎉 所有测试通过！请在飞书中验证：")
        print("  1. 第一条：短消息卡片，内容完整，无文件")
        print("  2. 第二条：长消息卡片（截断）+ 文件消息")
        print("  3. 第三条：长消息卡片（截断），无文件")
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())