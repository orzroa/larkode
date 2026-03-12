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
Hook 通知集成测试

从 typical_events.json 读取典型报文数据（完整 stdin 格式），
直接调用 log_hook 的处理流程，实现完全仿真测试。

发送 5 条真实消息到飞书：
1. UserPromptSubmit - 用户提问（蓝色卡片）
2. Stop - AI 完成响应（绿色卡片）
3. PermissionRequest 单选 - 橙色卡片
4. PermissionRequest 多选 - 橙色卡片
5. PermissionRequest 其他（Bash等） - 橙色卡片

运行方式：
    pytest tests/integration/test_hook_notifications.py -v
    python3 tests/integration/test_hook_notifications.py
"""
import asyncio
import json
import os
import sys
from pathlib import Path

# 设置测试环境变量（必须在导入业务代码之前）
os.environ["SKIP_TMUX_ESCAPE"] = "1"

import pytest
import pytest_asyncio

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 设置项目根目录为当前工作目录
os.chdir(PROJECT_ROOT)

from src.interfaces.hook_handler import DefaultHookHandler, HookContext
from src.hook_handler import handle_event, collect_all_data, log_event


def load_typical_events():
    """加载典型报文数据"""
    fixture_path = PROJECT_ROOT / "tests" / "hook_fixtures" / "typical_events.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        return json.load(f)["events"]


TYPICAL_EVENTS = load_typical_events()


def build_context_from_stdin(stdin_data: dict) -> HookContext:
    """从 stdin 数据构建 HookContext"""
    return HookContext.from_dict(stdin_data)


@pytest.fixture(scope="module")
def user_id():
    """获取飞书用户 ID"""
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")

    uid = os.getenv("FEISHU_HOOK_NOTIFICATION_USER_ID")
    if not uid:
        pytest.skip("未配置 FEISHU_HOOK_NOTIFICATION_USER_ID，跳过集成测试")
    return uid


class TestHookNotifications:
    """Hook 通知测试类 - 使用完整 stdin 报文，直接调用 log_hook 处理流程"""

    @pytest.mark.asyncio
    async def test_user_prompt_submit(self, user_id):
        """测试用户提问通知（蓝色卡片）- 完整流程仿真"""
        print("\n" + "=" * 60)
        print("测试 1/5: UserPromptSubmit（用户提问）")
        print("=" * 60)

        event = TYPICAL_EVENTS["user_prompt_submit"]
        stdin_data = event["stdin"]

        print(f"报文来源: typical_events.json")
        print(f"stdin: {json.dumps(stdin_data, ensure_ascii=False, indent=2)}")

        # 构建上下文和数据（完全仿真 log_hook.main() 的处理流程）
        handler = DefaultHookHandler()
        context = build_context_from_stdin(stdin_data)
        data = collect_all_data(handler, context, json.dumps(stdin_data))

        # 调用 handle_event 发送飞书通知
        await handle_event(handler, context, data)

        print("✅ 发送成功！请检查飞书是否收到蓝色'用户提问'卡片")
        await asyncio.sleep(0.5)

    @pytest.mark.asyncio
    async def test_stop(self, user_id):
        """测试 AI 完成响应（绿色卡片）- 完整流程仿真"""
        print("\n" + "=" * 60)
        print("测试 2/5: Stop（AI 完成响应）")
        print("=" * 60)

        event = TYPICAL_EVENTS["stop"]
        stdin_data = event["stdin"]

        print(f"报文来源: typical_events.json")
        print(f"last_assistant_message: {stdin_data.get('last_assistant_message', '')[:50]}...")

        # 构建上下文和数据
        handler = DefaultHookHandler()
        context = build_context_from_stdin(stdin_data)
        data = collect_all_data(handler, context, json.dumps(stdin_data))

        # 调用 handle_event 发送飞书通知
        await handle_event(handler, context, data)

        print("✅ 发送成功！请检查飞书是否收到绿色'回复完成'卡片")
        await asyncio.sleep(0.5)

    @pytest.mark.asyncio
    async def test_permission_single_select(self, user_id):
        """测试 AskUserQuestion 单选（橙色卡片）- 完整流程仿真"""
        print("\n" + "=" * 60)
        print("测试 3/5: AskUserQuestion 单选卡片")
        print("=" * 60)

        event = TYPICAL_EVENTS["permission_single_select"]
        stdin_data = event["stdin"]

        print(f"报文来源: typical_events.json")
        print(f"tool_name: {stdin_data.get('tool_name')}")
        print(f"multiSelect: {stdin_data['tool_input']['questions'][0]['multiSelect']}")

        # 构建上下文和数据
        handler = DefaultHookHandler()
        context = build_context_from_stdin(stdin_data)
        data = collect_all_data(handler, context, json.dumps(stdin_data))

        # 调用 handle_event 发送飞书通知
        await handle_event(handler, context, data)

        print("✅ 发送成功！请检查飞书是否收到橙色'交互请求'卡片（单选）")
        await asyncio.sleep(0.5)

    @pytest.mark.asyncio
    async def test_permission_multi_select(self, user_id):
        """测试 AskUserQuestion 多选（橙色卡片）- 完整流程仿真"""
        print("\n" + "=" * 60)
        print("测试 4/5: AskUserQuestion 多选卡片")
        print("=" * 60)

        event = TYPICAL_EVENTS["permission_multi_select"]
        stdin_data = event["stdin"]

        print(f"报文来源: typical_events.json")
        print(f"tool_name: {stdin_data.get('tool_name')}")
        print(f"multiSelect: {stdin_data['tool_input']['questions'][0]['multiSelect']}")

        # 构建上下文和数据
        handler = DefaultHookHandler()
        context = build_context_from_stdin(stdin_data)
        data = collect_all_data(handler, context, json.dumps(stdin_data))

        # 调用 handle_event 发送飞书通知
        await handle_event(handler, context, data)

        print("✅ 发送成功！请检查飞书是否收到橙色'交互请求'卡片（多选）")
        await asyncio.sleep(0.5)

    @pytest.mark.asyncio
    async def test_permission_other(self, user_id):
        """测试 Bash 权限请求（橙色卡片）- 完整流程仿真"""
        print("\n" + "=" * 60)
        print("测试 5/5: PermissionRequest 其他（Bash 权限）")
        print("=" * 60)

        event = TYPICAL_EVENTS["permission_bash"]
        stdin_data = event["stdin"]

        print(f"报文来源: typical_events.json")
        print(f"tool_name: {stdin_data.get('tool_name')}")
        print(f"command: {stdin_data['tool_input'].get('command')}")

        # 构建上下文和数据
        handler = DefaultHookHandler()
        context = build_context_from_stdin(stdin_data)
        data = collect_all_data(handler, context, json.dumps(stdin_data))

        # 调用 handle_event 发送飞书通知
        await handle_event(handler, context, data)

        print("✅ 发送成功！请检查飞书是否收到橙色'交互请求'卡片（Bash 权限）")


def main():
    """直接运行时的入口函数"""
    print("\n" + "=" * 60)
    print("Hook 通知集成测试 - 发送 5 条消息到飞书")
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
    print(f"报文来源: tests/hook_fixtures/typical_events.json")
    print("测试模式: 完整流程仿真（stdin -> HookContext -> handle_event）")
    print("将发送 5 条消息到飞书...\n")

    # 运行测试
    results = []

    async def run_tests():
        # 测试 1: UserPromptSubmit
        try:
            await TestHookNotifications().test_user_prompt_submit(user_id)
            results.append(("UserPromptSubmit", True))
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            results.append(("UserPromptSubmit", False))
        await asyncio.sleep(0.5)

        # 测试 2: Stop
        try:
            await TestHookNotifications().test_stop(user_id)
            results.append(("Stop", True))
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            results.append(("Stop", False))
        await asyncio.sleep(0.5)

        # 测试 3: Permission 单选
        try:
            await TestHookNotifications().test_permission_single_select(user_id)
            results.append(("Permission-Single", True))
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            results.append(("Permission-Single", False))
        await asyncio.sleep(0.5)

        # 测试 4: Permission 多选
        try:
            await TestHookNotifications().test_permission_multi_select(user_id)
            results.append(("Permission-Multi", True))
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            results.append(("Permission-Multi", False))
        await asyncio.sleep(0.5)

        # 测试 5: Permission 其他
        try:
            await TestHookNotifications().test_permission_other(user_id)
            results.append(("Permission-Bash", True))
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            results.append(("Permission-Bash", False))

    asyncio.run(run_tests())

    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    for name, success in results:
        status = "✅ 成功" if success else "❌ 失败"
        print(f"{name}: {status}")
    print("=" * 60)

    success_count = sum(1 for _, s in results if s)
    print(f"\n总计: {success_count}/5 成功")

    if success_count == 5:
        print("\n🎉 所有测试通过！请检查飞书是否收到 5 条卡片消息：")
        print("  1. 蓝色卡片 - 用户提问")
        print("  2. 绿色卡片 - 回复完成")
        print("  3-5. 橙色卡片 - 交互请求（单选、多选、Bash）")
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())