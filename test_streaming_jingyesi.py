#!/usr/bin/env python3
"""
真实流式卡片输出 - 静夜思
"""
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# 加载环境变量
load_dotenv(PROJECT_ROOT / ".env")

from src.streaming_output import create_streaming_manager
from src.config.settings import get_settings


async def main():
    """发送静夜思的流式卡片"""

    # 配置日志
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s'
    )

    # 静夜思诗句
    poems = [
        "床前明月光，",
        "疑是地上霜。",
        "举头望明月，",
        "低头思故乡。"
    ]

    # 获取配置
    settings = get_settings()
    user_id = os.getenv("FEISHU_HOOK_NOTIFICATION_USER_ID")

    if not user_id:
        print("❌ 错误: 未配置 FEISHU_HOOK_NOTIFICATION_USER_ID")
        return

    print(f"📱 目标用户: {user_id}")
    print(f"🔧 流式输出启用: {settings.STREAMING_OUTPUT_ENABLED}")
    print(f"⏱️  轮询间隔: {settings.STREAMING_POLL_INTERVAL}秒")
    print(f"⏱️  节流间隔: 0.5秒")
    print()

    # 创建流式输出管理器
    streaming_manager = create_streaming_manager()

    if not streaming_manager:
        print("❌ 无法创建流式输出管理器")
        return

    print("✅ 流式输出管理器已创建")
    print()

    # 1. 创建卡片
    print("📝 创建卡片...")
    card_id = await streaming_manager.start_streaming(
        user_id=user_id,
        initial_message="准备输出静夜思...",
        title="古诗欣赏",
        template_color="blue"
    )

    if not card_id:
        print("❌ 创建卡片失败")
        return

    print(f"✅ 卡片已创建: {card_id}")
    print()

    # 2. 逐句发送诗句
    print("📜 开始发送诗句...")
    accumulated_content = ""

    for i, verse in enumerate(poems, 1):
        accumulated_content += verse + "\n"

        # 重置 last_update_time 以避免节流（测试用）
        streaming_manager._update_states[card_id]["last_update_time"] = 0

        # 更新卡片内容
        print(f"  第 {i} 句: {verse}")
        success = await streaming_manager.update_content(card_id, accumulated_content.strip())

        if success:
            print(f"    ✅ 发送成功")
        else:
            print(f"    ❌ 发送失败")
            break

        # 模拟延迟（每句间隔 1 秒）
        await asyncio.sleep(1)

    print()

    # 3. 完成流式输出
    print("🎯 发送最终内容...")
    final_content = "**静夜思**\n\n" + accumulated_content.strip() + "\n\n—— 李白"
    success = await streaming_manager.finish_streaming(card_id, final_content)

    if success:
        print("✅ 流式输出完成")
        print()
        print(final_content)
    else:
        print("❌ 完成失败")

    print()
    print("="*50)
    print("🎉 静夜思已发送到飞书！")
    print("="*50)


if __name__ == "__main__":
    asyncio.run(main())