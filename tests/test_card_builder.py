"""
测试统一卡片构建器 (UnifiedCardBuilder)
"""
import pytest
from src.card_builder import UnifiedCardBuilder


class TestUnifiedCardBuilder:
    """测试统一卡片构建器"""

    def test_build_command_card(self):
        """测试构建命令确认卡片"""
        result = UnifiedCardBuilder.build_command_card("test command")
        assert "test command" in result
        assert "命令:" in result
        assert "开始处理" in result

    def test_build_output_card(self):
        """测试构建输出显示卡片"""
        output = "这是输出内容"
        result = UnifiedCardBuilder.build_output_card(output)
        assert output in result
        assert "输出:" in result
        assert "```" in result

    def test_build_output_card_with_title(self):
        """测试构建带标题的输出卡片"""
        output = "测试输出"
        title = "截屏"
        result = UnifiedCardBuilder.build_output_card(output, title)
        assert title in result
        assert output in result

    def test_build_error_card(self):
        """测试构建错误卡片"""
        error = "发生错误"
        result = UnifiedCardBuilder.build_error_card(error)
        assert error in result
        assert "错误:" in result

    def test_build_text_card(self):
        """测试构建文本卡片"""
        text = "这是一段文本"
        result = UnifiedCardBuilder.build_text_card(text)
        assert result == text

    def test_build_help_card(self):
        """测试构建帮助卡片"""
        help_text = "这是帮助信息"
        result = UnifiedCardBuilder.build_help_card(help_text)
        assert result == help_text

    def test_build_history_card(self):
        """测试构建历史记录卡片"""
        history_text = "历史记录内容"
        result = UnifiedCardBuilder.build_history_card(history_text)
        assert result == history_text

    def test_build_cancel_card(self):
        """测试构建取消确认卡片"""
        message = "操作已取消"
        result = UnifiedCardBuilder.build_cancel_card(message)
        assert result == message

    def test_build_download_image_card(self):
        """测试构建下载图片确认卡片"""
        message = "图片下载完成"
        result = UnifiedCardBuilder.build_download_image_card(message)
        assert result == message

    def test_build_download_voice_card(self):
        """测试构建下载语音确认卡片"""
        message = "语音下载完成"
        result = UnifiedCardBuilder.build_download_voice_card(message)
        assert result == message

    def test_build_file_notification_card(self):
        """测试构建文件通知卡片"""
        file_name = "test_file.txt"
        result = UnifiedCardBuilder.build_file_notification_card(file_name)
        assert file_name in result
        assert "完整内容已保存为文件" in result

    def test_build_tmux_card(self):
        """测试构建截屏卡片"""
        output = "tmux 输出内容"
        result = UnifiedCardBuilder.build_tmux_card(output)
        assert output in result
        assert "屏幕内容:" in result
        assert "```" in result

    def test_build_status_card_with_tasks(self):
        """测试构建状态卡片（有任务）"""
        task_dicts = [
            {"command": "test1", "status": "running", "created_at": "2026-03-12"},
            {"command": "test2", "status": "completed", "created_at": "2026-03-11"}
        ]
        result = UnifiedCardBuilder.build_status_card(task_dicts)
        assert "最近任务状态" in result
        assert "test1" in result
        assert "running" in result
        assert "test2" in result
        assert "completed" in result

    def test_build_status_card_no_tasks(self):
        """测试构建状态卡片（无任务）"""
        result = UnifiedCardBuilder.build_status_card([])
        assert "没有正在运行的任务" in result

    def test_build_status_card_empty_tasks(self):
        """测试构建状态卡片（空任务列表）"""
        task_dicts = []
        result = UnifiedCardBuilder.build_status_card(task_dicts)
        assert "没有正在运行的任务" in result


class TestConvenienceFunctions:
    """测试便捷函数"""

    def test_create_command_card(self):
        """测试 create_command_card 便捷函数"""
        from src.card_builder import create_command_card
        result = create_command_card("test")
        assert "test" in result
        assert "命令:" in result

    def test_create_output_card(self):
        """测试 create_output_card 便捷函数"""
        from src.card_builder import create_output_card
        result = create_output_card("output")
        assert "output" in result

    def test_create_error_card(self):
        """测试 create_error_card 便捷函数"""
        from src.card_builder import create_error_card
        result = create_error_card("error")
        assert "error" in result

    def test_create_help_card(self):
        """测试 create_help_card 便捷函数"""
        from src.card_builder import create_help_card
        result = create_help_card("help")
        assert result == "help"

    def test_create_history_card(self):
        """测试 create_history_card 便捷函数"""
        from src.card_builder import create_history_card
        result = create_history_card("history")
        assert result == "history"

    def test_create_cancel_card(self):
        """测试 create_cancel_card 便捷函数"""
        from src.card_builder import create_cancel_card
        result = create_cancel_card("cancel")
        assert result == "cancel"

    def test_create_download_image_card(self):
        """测试 create_download_image_card 便捷函数"""
        from src.card_builder import create_download_image_card
        result = create_download_image_card("image")
        assert result == "image"

    def test_create_download_voice_card(self):
        """测试 create_download_voice_card 便捷函数"""
        from src.card_builder import create_download_voice_card
        result = create_download_voice_card("voice")
        assert result == "voice"

    def test_create_tmux_card(self):
        """测试 create_tmux_card 便捷函数"""
        from src.card_builder import create_tmux_card
        result = create_tmux_card("output")
        assert "output" in result

    def test_create_status_card(self):
        """测试 create_status_card 便捷函数"""
        from src.card_builder import create_status_card
        task_dicts = [{"command": "test", "status": "done", "created_at": "now"}]
        result = create_status_card(task_dicts)
        assert "test" in result
        assert "done" in result