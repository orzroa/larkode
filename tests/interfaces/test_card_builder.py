"""
测试卡片构建功能
测试节点：N26-N31 - 卡片构建层
"""
import pytest
import json
from typing import Dict, Any, List, Tuple

from src.interfaces.card_builder import CardBuilderInterface


class TestCardBuilder(CardBuilderInterface):
    """测试用的卡片构建器实现"""

    def _escape_special_chars(self, text: str) -> str:
        """转义飞书 Markdown 特殊字符"""
        # 如果启用了安全格式化，需要转义这些字符
        special_chars = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
        }
        for char, replacement in special_chars.items():
            text = text.replace(char, replacement)
        return text

    def escape_markdown(self, text: str) -> str:
        """转义 Markdown 特殊字符"""
        # 简单实现，保留换行
        return text.replace('\\', '\\\\').replace('`', '\\`')

    def truncate_content(self, content: str, max_length: int) -> str:
        """截断内容"""
        if len(content) <= max_length:
            return content
        return content[:max_length - 3] + '...'

    def _build_base_card(self) -> Dict[str, Any]:
        """构建基础卡片结构"""
        return {
            "config": {"wide_screen_mode": True},
            "header": {},
            "elements": []
        }

    def create_command_card(self, command: str) -> Dict[str, Any]:
        """创建命令确认卡片"""
        card = self._build_base_card()
        card["header"] = {
            "template": "yellow",
            "title": {
                "content": "📝 命令已接收",
                "tag": "plain_text"
            }
        }

        elements = [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**命令**\n`{self._escape_special_chars(command)}`\n\n"
                              f"任务已加入执行队列，请稍候..."
                }
            }
        ]

        card["elements"] = elements
        return card

    def create_result_card(self, message_number: str, title: str, content: str, status: str) -> Tuple[str, bool, str]:
        """创建结果卡片"""
        status_emojis = {"success": "✅", "error": "❌", "info": "ℹ️"}
        emoji = status_emojis.get(status, "ℹ️")

        card = self._build_base_card()
        card["header"] = {
            "template": "green" if status == "success" else ("red" if status == "error" else "blue"),
            "title": {
                "content": f"{emoji} {title}",
                "tag": "plain_text"
            }
        }

        # 测试用实现：内容超过 100 字符时触发文件模式
        need_file = len(content) > 100

        if need_file:
            file_content = content
            truncated = content[:100] + "\n... (完整内容已保存为文件)"
        else:
            file_content = ""
            truncated = self.truncate_content(content, 1500)

        elements = [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**消息编号**: `{message_number}`\n\n{self._escape_special_chars(truncated)}"
                }
            }
        ]

        card["elements"] = elements
        return (json.dumps(card, ensure_ascii=False), need_file, file_content)

    def create_status_card(self, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """创建任务状态卡片"""
        card = self._build_base_card()
        card["header"] = {
            "template": "blue",
            "title": {
                "content": "📊 任务状态",
                "tag": "plain_text"
            }
        }

        if not tasks:
            content = "暂无任务"
        else:
            status_emojis = {
                "pending": "⏳",
                "in_progress": "🔄",
                "completed": "✅",
                "failed": "❌"
            }

            lines = ["**最近任务**:\n"]
            for task in tasks:
                status = task.get("status", "pending")
                command = task.get("command", "")
                created_at = task.get("created_at", "")

                emoji = status_emojis.get(status, "❓")
                lines.append(f"{emoji} `{command}`\n   状态: {status}\n   时间: {created_at}\n")

            content = "\n".join(lines)

        elements = [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": self._escape_special_chars(content)
                }
            }
        ]

        card["elements"] = elements
        return card

    def create_select_card(self, title: str, subtitle: str, options: List[str],
                          multi: bool = False) -> Dict[str, Any]:
        """创建选择卡片"""
        card = self._build_base_card()
        card["header"] = {
            "template": "indigo",
            "title": {
                "content": title,
                "tag": "plain_text"
            }
        }

        # 生成选项列表，索引从1开始
        select_emoji = "☑️" if multi else "🔘"
        lines = [f"**{subtitle}**\n"]

        for i, option in enumerate(options, 1):
            lines.append(f"{i}. {option}")

        lines.append(f"\n**escape** (不选择)")

        elements = [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "\n".join(lines)
                }
            }
        ]

        card["elements"] = elements
        return card

    def create_error_card(self, error: str) -> Dict[str, Any]:
        """创建错误卡片"""
        card = self._build_base_card()
        card["header"] = {
            "template": "red",
            "title": {
                "content": "❌ 错误",
                "tag": "plain_text"
            }
        }

        elements = [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"```\n{self._escape_special_chars(error)}\n```"
                }
            }
        ]

        card["elements"] = elements
        return card

    def create_tmux_card(self, output: str, message_number: str = "") -> Tuple[str, bool, str]:
        """创建 tmux 输出卡片"""
        card = self._build_base_card()
        card["header"] = {
            "template": "grey",
            "title": {
                "content": "📺 Tmux 输出",
                "tag": "plain_text"
            }
        }

        # 测试用实现：内容超过 100 字符时触发文件模式
        need_file = len(output) > 100

        if need_file:
            file_content = output
            truncated = output[:100] + "\n... (完整内容已保存为文件)"
        else:
            file_content = ""
            truncated = self.truncate_content(output, 2000)

        elements = [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"```\n{self._escape_special_chars(truncated)}\n```"
                }
            }
        ]

        card["elements"] = elements
        return (json.dumps(card, ensure_ascii=False), need_file, file_content)

    def create_help_card(self, help_text: str, message_number: str = "") -> str:
        """创建帮助卡片"""
        card = self._build_base_card()
        card["header"] = {
            "template": "grey",
            "title": {
                "content": "帮助",
                "tag": "plain_text"
            }
        }

        elements = [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": self._escape_special_chars(help_text)
                }
            }
        ]

        card["elements"] = elements
        return json.dumps(card, ensure_ascii=False)

    def create_history_card(self, history_text: str, message_number: str = "") -> str:
        """创建历史记录卡片"""
        card = self._build_base_card()
        card["header"] = {
            "template": "grey",
            "title": {
                "content": "历史记录",
                "tag": "plain_text"
            }
        }

        elements = [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": self._escape_special_chars(history_text)
                }
            }
        ]

        card["elements"] = elements
        return json.dumps(card, ensure_ascii=False)

    def create_cancel_card(self, message: str, message_number: str = "") -> str:
        """创建取消确认卡片"""
        card = self._build_base_card()
        card["header"] = {
            "template": "grey",
            "title": {
                "content": "取消",
                "tag": "plain_text"
            }
        }

        elements = [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": self._escape_special_chars(message)
                }
            }
        ]

        card["elements"] = elements
        return json.dumps(card, ensure_ascii=False)

    def create_download_image_card(self, message: str, message_number: str = "") -> str:
        """创建下载图片确认卡片"""
        card = self._build_base_card()
        card["header"] = {
            "template": "grey",
            "title": {
                "content": "下载图片",
                "tag": "plain_text"
            }
        }

        elements = [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": self._escape_special_chars(message)
                }
            }
        ]

        card["elements"] = elements
        return json.dumps(card, ensure_ascii=False)


class TestCardBuilderNode:
    """测试卡片构建节点"""

    def setup_method(self):
        """设置测试环境"""
        self.builder = TestCardBuilder()

    def test_node_n26_create_command_card(self):
        """测试 N26: 命令确认卡片"""
        card = self.builder.create_command_card("ls -la")

        assert "header" in card
        assert "elements" in card
        assert card["header"]["title"]["content"] == "📝 命令已接收"

        # 检查内容
        content = card["elements"][0]["text"]["content"]
        assert "ls -la" in content

        # 验证 JSON 可序列化
        json_str = json.dumps(card)
        assert isinstance(json_str, str)

    def test_node_n27_create_result_card(self):
        """测试 N27: 结果卡片"""
        card_json, need_file, file_content = self.builder.create_result_card("1", "执行成功", "输出内容", "success")

        card = json.loads(card_json)
        assert card["header"]["title"]["content"] == "✅ 执行成功"
        assert card["header"]["template"] == "green"

        # 测试错误状态
        error_card_json, error_need_file, error_file_content = self.builder.create_result_card(
            "1", "执行失败", "错误信息", "error"
        )
        error_card = json.loads(error_card_json)
        assert error_card["header"]["template"] == "red"

    def test_node_n28_create_status_card(self):
        """测试 N28: 状态卡片"""
        tasks = [
            {"command": "ls -la", "status": "completed", "created_at": "2024-01-01"},
            {"command": "pwd", "status": "in_progress", "created_at": "2024-01-02"}
        ]

        card = self.builder.create_status_card(tasks)

        assert "📊 任务状态" in card["header"]["title"]["content"]

        # 测试空任务列表
        empty_card = self.builder.create_status_card([])
        assert "暂无任务" in empty_card["elements"][0]["text"]["content"]

    def test_node_n29_create_select_card(self):
        """测试 N29: 选择卡片"""
        options = ["English", "简体中文", "日本語"]

        # 测试单选
        single_card = self.builder.create_select_card("语言选择", "请选择语言", options, multi=False)
        content = single_card["elements"][0]["text"]["content"]
        assert "1. English" in content
        assert "2. 简体中文" in content
        assert "3. 日本語" in content
        assert "**escape** (不选择)" in content

        # 测试多选
        multi_card = self.builder.create_select_card("语言选择", "请选择语言", options, multi=True)
        assert "语言选择" in multi_card["header"]["title"]["content"]

    def test_node_n30_create_error_card(self):
        """测试 N30: 错误卡片"""
        card = self.builder.create_error_card("连接失败")

        assert card["header"]["title"]["content"] == "❌ 错误"
        assert card["header"]["template"] == "red"

        content = card["elements"][0]["text"]["content"]
        assert "连接失败" in content

    def test_node_n31_create_tmux_card(self):
        """测试 N31: tmux 输出卡片"""
        output = "some output line 1\nsome output line 2"
        card_json, need_file, file_content = self.builder.create_tmux_card(output)

        card = json.loads(card_json)
        assert card["header"]["title"]["content"] == "📺 Tmux 输出"
        assert not need_file  # 短内容不需要文件

        content = card["elements"][0]["text"]["content"]
        assert "some output" in content

        # 测试长内容触发文件模式
        long_output = "a" * 200
        long_card_json, long_need_file, long_file_content = self.builder.create_tmux_card(long_output)
        assert long_need_file  # 长内容需要文件
        assert long_file_content == long_output  # 文件内容为完整内容

    def test_truncate_content(self):
        """测试内容截断"""
        long_text = "a" * 1000
        truncated = self.builder.truncate_content(long_text, 100)
        assert len(truncated) == 100
        assert truncated.endswith("...")

        # 测试不需要截断的情况
        short_text = "hello"
        result = self.builder.truncate_content(short_text, 100)
        assert result == short_text

    def test_escape_markdown(self):
        """测试 Markdown 转义"""
        text = "code with `backticks` and \\backslashes"
        escaped = self.builder.escape_markdown(text)
        assert "\\`" in escaped
        assert "\\\\" in escaped

    def test_card_json_serializable(self):
        """测试所有卡片都可以序列化为 JSON"""
        methods = [
            ("命令卡片", self.builder.create_command_card("ls -la")),
            ("状态卡片", self.builder.create_status_card([])),
            ("选择卡片", self.builder.create_select_card("标题", "副标题", ["A", "B"], False)),
            ("错误卡片", self.builder.create_error_card("错误")),
        ]

        for name, card in methods:
            try:
                json_str = json.dumps(card, ensure_ascii=False)
                assert isinstance(json_str, str)
                print(f"\n✅ {name} JSON 序列化成功")
            except Exception as e:
                pytest.fail(f"{name} 无法序列化为 JSON: {e}")

        # 测试返回元组的方法
        tuple_methods = [
            ("结果卡片", self.builder.create_result_card("1", "成功", "内容", "success")),
            ("tmux卡片", self.builder.create_tmux_card("输出"))
        ]

        for name, (card_json, need_file, file_content) in tuple_methods:
            try:
                card = json.loads(card_json)
                assert isinstance(card, dict)
                print(f"\n✅ {name} JSON 序列化成功 (need_file={need_file})")
            except Exception as e:
                pytest.fail(f"{name} 无法序列化为 JSON: {e}")