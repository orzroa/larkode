"""
文本工具单元测试
"""
import pytest
import sys
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.text_utils import (
    clean_ansi_codes,
    clean_ansi_codes_extended,
    clean_tmux_output,
)


class TestCleanAnsiCodes:
    """测试 ANSI 转义序列清理"""

    def test_clean_simple_color_codes(self):
        """测试清理简单的颜色代码"""
        text = "\x1b[31mRed Text\x1b[0m"
        result = clean_ansi_codes(text)
        assert result == "Red Text"

    def test_clean_multiple_color_codes(self):
        """测试清理多个颜色代码"""
        text = "\x1b[31mRed\x1b[0m \x1b[32mGreen\x1b[0m"
        result = clean_ansi_codes(text)
        assert result == "Red Green"

    def test_clean_bold_code(self):
        """测试清理粗体代码"""
        text = "\x1b[1mBold Text\x1b[0m"
        result = clean_ansi_codes(text)
        assert result == "Bold Text"

    def test_clean_no_codes(self):
        """测试没有 ANSI 代码的文本"""
        text = "Normal text without codes"
        result = clean_ansi_codes(text)
        assert result == text

    def test_clean_empty_string(self):
        """测试空字符串"""
        result = clean_ansi_codes("")
        assert result == ""

    def test_clean_complex_sequence(self):
        """测试复杂的 ANSI 序列"""
        text = "\x1b[1;31;42mBold Red on Green\x1b[0m"
        result = clean_ansi_codes(text)
        assert result == "Bold Red on Green"


class TestCleanAnsiCodesExtended:
    """测试扩展 ANSI 转义序列清理"""

    def test_clean_extended_codes(self):
        """测试清理扩展 ANSI 代码"""
        text = "\x1b[?2004hSome text\x1b[?2004l"
        result = clean_ansi_codes_extended(text)
        # 扩展版本应该处理更多序列
        assert "\x1b" not in result or result == text.replace("\x1b[?2004h", "").replace("\x1b[?2004l", "")

    def test_clean_simple_codes(self):
        """测试清理简单 ANSI 代码"""
        text = "\x1b[31mRed\x1b[0m"
        result = clean_ansi_codes_extended(text)
        assert result == "Red"


class TestCleanTmuxOutput:
    """测试 tmux 输出清理"""

    def test_clean_ansi_in_tmux_output(self):
        """测试清理 tmux 输出中的 ANSI 代码"""
        output = "\x1b[31mError:\x1b[0m Something went wrong"
        result = clean_tmux_output(output)
        assert result == "Error: Something went wrong"

    def test_clean_tmux_markers(self):
        """测试清理 tmux 特有标记"""
        output = "Some output\x1b[?2004lMore output"
        result = clean_tmux_output(output)
        assert "\x1b[?2004l" not in result

    def test_clean_x0f_character(self):
        """测试清理 x0f 字符"""
        output = "Text\x0fMore Text"
        result = clean_tmux_output(output)
        assert "\x0f" not in result

    def test_clean_strips_whitespace(self):
        """测试清理后去除首尾空白"""
        output = "  \x1b[31mText\x1b[0m  "
        result = clean_tmux_output(output)
        assert result == "Text"

    def test_clean_combined(self):
        """测试组合清理"""
        output = "\x1b[1m\x1b[31m\x1b[?2004lError\x0f\x1b[0m"
        result = clean_tmux_output(output)
        assert result == "Error"

    def test_clean_empty_output(self):
        """测试空输出"""
        result = clean_tmux_output("")
        assert result == ""

    def test_clean_plain_text(self):
        """测试纯文本输出"""
        output = "Just plain text\nNo codes"
        result = clean_tmux_output(output)
        assert "Just plain text" in result