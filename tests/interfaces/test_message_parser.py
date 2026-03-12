"""
测试消息解析功能
测试节点：N6 - 消息解析, N7 - 斜杠命令识别, N8 - 命令参数解析
"""
import pytest
import json
from unittest.mock import patch
from typing import Dict, Any, Optional

# 导入待测试的类
from src.interfaces.message_parser import MessageParserInterface


class TestMessageParser(MessageParserInterface):
    """测试用的消息解析器实现"""

    def parse_message(self, event_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """实现消息解析方法"""
        event = event_data.get("event", {})
        sender = event.get("sender", {})
        message = event.get("message", {})

        user_id = sender.get("sender_id", {}).get("open_id")
        message_id = message.get("message_id")
        content_data = message.get("content")

        if content_data:
            try:
                content_json = json.loads(content_data)
                text = content_json.get("text", "").strip()
            except json.JSONDecodeError:
                text = content_data.strip()
        else:
            text = ""

        if not user_id or not text:
            return None

        return {
            "user_id": user_id,
            "message_id": message_id,
            "content": text,
            "raw_event": event_data
        }

    def is_slash_command(self, content: str) -> bool:
        """实现斜杠命令判断"""
        return content.startswith("/") and len(content) > 1

    def parse_command(self, command: str) -> Dict[str, Any]:
        """实现命令解析"""
        if not self.is_slash_command(command):
            return {
                "command": "",
                "args": "",
                "full_command": command
            }

        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        return {
            "command": cmd,
            "args": args,
            "full_command": command
        }


class TestMessageParserNode:
    """测试消息解析节点"""

    def setup_method(self):
        """设置测试环境"""
        self.parser = TestMessageParser()

    def test_node_n6_parse_message_valid(self):
        """测试 N6: 消息解析 - 有效数据"""
        # 模拟飞书消息事件
        event_data = {
            "type": "im.message.receive_v1",
            "event": {
                "sender": {
                    "sender_id": {
                        "open_id": "ou_1234567890"
                    }
                },
                "message": {
                    "message_id": "om_1234567890",
                    "content": json.dumps({"text": "Hello, world!"})
                }
            }
        }

        result = self.parser.parse_message(event_data)

        assert result is not None
        assert result["user_id"] == "ou_1234567890"
        assert result["message_id"] == "om_1234567890"
        assert result["content"] == "Hello, world!"

    def test_node_n6_parse_message_invalid(self):
        """测试 N6: 消息解析 - 无效数据"""
        # 缺少用户ID
        event_data1 = {
            "type": "im.message.receive_v1",
            "event": {
                "message": {
                    "message_id": "om_1234567890",
                    "content": json.dumps({"text": "Hello"})
                }
            }
        }

        # 缺少消息内容
        event_data2 = {
            "type": "im.message.receive_v1",
            "event": {
                "sender": {
                    "sender_id": {
                        "open_id": "ou_1234567890"
                    }
                }
            }
        }

        # 内容为空
        event_data3 = {
            "type": "im.message.receive_v1",
            "event": {
                "sender": {
                    "sender_id": {
                        "open_id": "ou_1234567890"
                    }
                },
                "message": {
                    "message_id": "om_1234567890",
                    "content": json.dumps({"text": ""})
                }
            }
        }

        assert self.parser.parse_message(event_data1) is None
        assert self.parser.parse_message(event_data2) is None
        assert self.parser.parse_message(event_data3) is None

    def test_node_n7_is_slash_command(self):
        """测试 N7: 斜杠命令识别"""
        test_cases = [
            ("/status", True),
            ("/help", True),
            ("/select arg", True),
            ("normal message", False),
            ("", False),
            ("/", False),  # 只有斜杠不是有效命令
            (" /status", False),  # 前面有空格
        ]

        for text, expected in test_cases:
            assert self.parser.is_slash_command(text) == expected

    def test_node_n8_parse_command(self):
        """测试 N8: 命令参数解析"""
        test_cases = [
            ("/status", {
                "command": "/status",
                "args": "",
                "full_command": "/status"
            }),
            ("/select English", {
                "command": "/select",
                "args": "English",
                "full_command": "/select English"
            }),
            ("/cancel om_1234567890", {
                "command": "/cancel",
                "args": "om_1234567890",
                "full_command": "/cancel om_1234567890"
            }),
            ("normal message", {
                "command": "",
                "args": "",
                "full_command": "normal message"
            })
        ]

        for cmd, expected in test_cases:
            result = self.parser.parse_command(cmd)
            assert result == expected

    def test_integration_full_command_flow(self):
        """集成测试：完整的命令处理流程"""
        # 模拟完整的飞书事件
        event_data = {
            "type": "im.message.receive_v1",
            "event": {
                "sender": {
                    "sender_id": {
                        "open_id": "ou_04a4d9817a57c5b2a3ab43dc8c5b60a0"
                    }
                },
                "message": {
                    "message_id": "om_1234567890",
                    "content": json.dumps({"text": "/select English"})
                }
            }
        }

        # 1. 解析消息
        parsed = self.parser.parse_message(event_data)
        assert parsed is not None
        assert parsed["content"] == "/select English"

        # 2. 判断是否斜杠命令
        assert self.parser.is_slash_command(parsed["content"])

        # 3. 解析命令
        command_info = self.parser.parse_command(parsed["content"])
        assert command_info["command"] == "/select"
        assert command_info["args"] == "English"

        print(f"\n✅ 完整流程测试通过:")
        print(f"   - 用户ID: {parsed['user_id']}")
        print(f"   - 消息内容: {parsed['content']}")
        print(f"   - 命令: {command_info['command']}")
        print(f"   - 参数: {command_info['args']}")