"""
选项卡（OptionCard）构建器

针对 100+ 选项列表场景，提供可点击按钮 + 翻页的飞书卡片 V2 schema。

V2 schema 约束：
- 顶层 elements 不再支持 tag: "action"
- 多按钮横向并排需用 column_set 包裹，每个按钮独占一列
- 每个 column 内 width="weighted", weight=N 控制宽度

按钮元素结构：
    {
        "tag": "button",
        "text": {"tag": "plain_text", "content": "..."},
        "type": "primary" | "default",
        "value": {...}
    }

回调由 InteractionManager 统一分发。
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


_BUTTONS_PER_ROW = 5
_ITEMS_PER_PAGE = 20


@dataclass
class OptionItem:
    """单个可选项"""
    key: str
    label: str
    description: Optional[str] = None
    is_current: bool = False


@dataclass
class OptionCardData:
    """选项卡数据"""
    title: str
    category: str  # 回调时用于分发：ws / model / ...
    items: List[OptionItem]
    page: int = 1
    page_size: int = _ITEMS_PER_PAGE
    template_color: str = "blue"
    header_note: str = ""
    max_label_len: int = 18

    @property
    def total_pages(self) -> int:
        if not self.items:
            return 1
        return (len(self.items) + self.page_size - 1) // self.page_size

    @property
    def page_clamped(self) -> int:
        if self.page < 1:
            return 1
        if self.page > self.total_pages:
            return self.total_pages
        return self.page

    def page_items(self) -> List[OptionItem]:
        start = (self.page_clamped - 1) * self.page_size
        end = start + self.page_size
        return self.items[start:end]


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def _make_button(value: Dict[str, Any], text: str, button_type: str = "default") -> Dict[str, Any]:
    return {
        "tag": "button",
        "text": {"tag": "plain_text", "content": text},
        "type": button_type,
        "value": value,
    }


def _make_button_row(buttons: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    V2 schema 一行按钮：column_set + N 个 column，每个 column 装一个按钮。
    """
    columns = []
    for btn in buttons:
        columns.append({
            "tag": "column",
            "width": "weighted",
            "weight": 1,
            "elements": [btn],
        })
    return {
        "tag": "column_set",
        "flex_mode": "stretch",
        "columns": columns,
    }


def build_option_card(data: OptionCardData) -> Dict[str, Any]:
    """
    构建选项卡的卡片 JSON（V2 schema）。

    Returns:
        完整的卡片 JSON dict，可直接通过 send_message 发送。
    """
    items = data.page_items()
    elements: List[Dict[str, Any]] = []

    # 顶部说明
    if data.header_note:
        elements.append({"tag": "markdown", "content": data.header_note})
        elements.append({"tag": "hr"})

    # 摘要
    total = len(data.items)
    summary = f"共 **{total}** 项 · 第 **{data.page_clamped} / {data.total_pages}** 页"
    if not items:
        summary += "\n\n_暂无选项_"
    elements.append({"tag": "markdown", "content": summary})
    elements.append({"tag": "hr"})

    # 选项按钮：每行 5 个（column_set）
    if items:
        row: List[Dict[str, Any]] = []
        for idx, item in enumerate(items):
            global_no = (data.page_clamped - 1) * data.page_size + idx + 1
            text = f"{global_no}. {_truncate(item.label, data.max_label_len)}"
            button_type = "primary" if item.is_current else "default"
            value = {
                "opt": "select",
                "cat": data.category,
                "key": item.key,
                "page": data.page_clamped,
            }
            row.append(_make_button(value, text, button_type))
            if len(row) >= _BUTTONS_PER_ROW:
                elements.append(_make_button_row(row))
                row = []
        if row:
            elements.append(_make_button_row(row))

    # 翻页
    if data.total_pages > 1:
        elements.append({"tag": "hr"})
        prev_page = max(1, data.page_clamped - 1)
        next_page = min(data.total_pages, data.page_clamped + 1)
        elements.append(_make_button_row([
            _make_button(
                {"opt": "page", "cat": data.category, "page": prev_page},
                "← 上一页",
                "default" if data.page_clamped == 1 else "primary",
            ),
            _make_button(
                {"opt": "noop", "cat": data.category},
                f"{data.page_clamped}/{data.total_pages}",
                "default",
            ),
            _make_button(
                {"opt": "page", "cat": data.category, "page": next_page},
                "下一页 →",
                "default" if data.page_clamped == data.total_pages else "primary",
            ),
        ]))

    return {
        "schema": "2.0",
        "config": {"update_multi": True},
        "header": {
            "title": {"tag": "plain_text", "content": data.title},
            "template": data.template_color,
        },
        "body": {"elements": elements},
    }


def parse_action_value(raw: Any) -> Optional[Dict[str, Any]]:
    """
    解析 action.value。飞书可能传 dict、str、空等。
    返回 dict 或 None。
    """
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        import json
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None
    return None