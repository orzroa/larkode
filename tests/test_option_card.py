"""
测试 OptionCard 构建器
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))


def _collect_buttons(card) -> list:
    """从卡片中收集所有按钮元素"""
    buttons = []
    for element in card.get("body", {}).get("elements", []):
        if element.get("tag") == "column_set":
            for column in element.get("columns", []):
                for el in column.get("elements", []):
                    if el.get("tag") == "button":
                        buttons.append(el)
    return buttons


def _collect_column_sets(card) -> list:
    return [e for e in card.get("body", {}).get("elements", []) if e.get("tag") == "column_set"]


class TestOptionCardData:
    def test_total_pages_zero_items(self):
        from src.option_card import OptionCardData, OptionItem
        d = OptionCardData(title="t", category="ws", items=[])
        assert d.total_pages == 1
        assert d.page_items() == []

    def test_total_pages_one_page(self):
        from src.option_card import OptionCardData, OptionItem
        items = [OptionItem(key=f"k{i}", label=f"l{i}") for i in range(15)]
        d = OptionCardData(title="t", category="ws", items=items)
        assert d.total_pages == 1

    def test_total_pages_exactly_one_page(self):
        from src.option_card import OptionCardData, OptionItem
        items = [OptionItem(key=f"k{i}", label=f"l{i}") for i in range(20)]
        d = OptionCardData(title="t", category="ws", items=items)
        assert d.total_pages == 1

    def test_total_pages_multiple(self):
        from src.option_card import OptionCardData, OptionItem
        items = [OptionItem(key=f"k{i}", label=f"l{i}") for i in range(105)]
        d = OptionCardData(title="t", category="ws", items=items)
        assert d.total_pages == 6  # ceil(105/20) = 6

    def test_page_clamped_below(self):
        from src.option_card import OptionCardData, OptionItem
        items = [OptionItem(key="k", label="l")]
        d = OptionCardData(title="t", category="ws", items=items, page=0)
        assert d.page_clamped == 1

    def test_page_clamped_above(self):
        from src.option_card import OptionCardData, OptionItem
        items = [OptionItem(key="k", label="l")]
        d = OptionCardData(title="t", category="ws", items=items, page=99)
        assert d.page_clamped == 1

    def test_page_items_slice(self):
        from src.option_card import OptionCardData, OptionItem
        items = [OptionItem(key=f"k{i}", label=f"l{i}") for i in range(45)]
        d = OptionCardData(title="t", category="ws", items=items, page=2)
        page = d.page_items()
        assert len(page) == 20
        assert page[0].key == "k20"
        assert page[-1].key == "k39"

    def test_page_items_partial_last_page(self):
        from src.option_card import OptionCardData, OptionItem
        items = [OptionItem(key=f"k{i}", label=f"l{i}") for i in range(25)]
        d = OptionCardData(title="t", category="ws", items=items, page=2)
        page = d.page_items()
        assert len(page) == 5
        assert page[0].key == "k20"


class TestBuildOptionCard:
    def test_basic_structure(self):
        from src.option_card import OptionCardData, OptionItem, build_option_card
        items = [OptionItem(key="a", label="alpha"), OptionItem(key="b", label="beta")]
        card = build_option_card(OptionCardData(title="测", category="ws", items=items))
        assert card["schema"] == "2.0"
        assert card["header"]["template"] == "blue"
        assert card["header"]["title"]["content"] == "测"

    def test_no_legacy_action_tag(self):
        """确保没有顶层 tag=action 元素（V2 schema 已废弃）"""
        from src.option_card import OptionCardData, OptionItem, build_option_card
        items = [OptionItem(key="a", label="alpha")]
        card = build_option_card(OptionCardData(title="t", category="ws", items=items))
        for e in card["body"]["elements"]:
            assert e["tag"] != "action", "V2 schema 不再支持 tag=action"

    def test_no_pagination_when_single_page(self):
        """单页：无翻页行，只有选项按钮行"""
        from src.option_card import OptionCardData, OptionItem, build_option_card
        items = [OptionItem(key="a", label="alpha")]
        card = build_option_card(OptionCardData(title="t", category="ws", items=items))
        column_sets = _collect_column_sets(card)
        # 只有选项按钮行（1 个 column_set）
        assert len(column_sets) == 1
        # 该 column_set 应有 1 个 column
        assert len(column_sets[0]["columns"]) == 1

    def test_pagination_when_multiple_pages(self):
        """多页：每页 20 项 ÷ 5 列/行 = 4 行 + 1 行翻页 = 5 个 column_set"""
        from src.option_card import OptionCardData, OptionItem, build_option_card
        items = [OptionItem(key=f"k{i}", label=f"l{i}") for i in range(45)]
        card = build_option_card(OptionCardData(title="t", category="ws", items=items))
        column_sets = _collect_column_sets(card)
        assert len(column_sets) == 5
        # 最后一个 column_set 是翻页（3 个按钮）
        assert len(column_sets[-1]["columns"]) == 3

    def test_button_value_format(self):
        """按钮 value 应包含 opt/cat/key/page"""
        from src.option_card import OptionCardData, OptionItem, build_option_card
        items = [OptionItem(key="foo", label="Foo")]
        card = build_option_card(OptionCardData(title="t", category="ws", items=items))
        buttons = _collect_buttons(card)
        assert len(buttons) == 1
        value = buttons[0]["value"]
        assert value["opt"] == "select"
        assert value["cat"] == "ws"
        assert value["key"] == "foo"
        assert value["page"] == 1

    def test_pagination_button_values(self):
        """翻页按钮的 value 正确"""
        from src.option_card import OptionCardData, OptionItem, build_option_card
        items = [OptionItem(key=f"k{i}", label=f"l{i}") for i in range(45)]
        card = build_option_card(OptionCardData(
            title="t", category="ws", items=items, page=2
        ))
        column_sets = _collect_column_sets(card)
        page_nav = column_sets[-1]["columns"]
        # 翻页行：3 个按钮
        assert len(page_nav) == 3
        prev_btn = page_nav[0]["elements"][0]
        noop_btn = page_nav[1]["elements"][0]
        next_btn = page_nav[2]["elements"][0]
        assert prev_btn["value"] == {"opt": "page", "cat": "ws", "page": 1}
        assert noop_btn["value"] == {"opt": "noop", "cat": "ws"}
        assert next_btn["value"] == {"opt": "page", "cat": "ws", "page": 3}

    def test_pagination_first_page(self):
        """第一页：上一页仍指向 1"""
        from src.option_card import OptionCardData, OptionItem, build_option_card
        items = [OptionItem(key=f"k{i}", label=f"l{i}") for i in range(25)]
        card = build_option_card(OptionCardData(
            title="t", category="ws", items=items, page=1
        ))
        column_sets = _collect_column_sets(card)
        page_nav = column_sets[-1]["columns"]
        prev_btn = page_nav[0]["elements"][0]
        next_btn = page_nav[2]["elements"][0]
        assert prev_btn["value"]["page"] == 1
        assert next_btn["value"]["page"] == 2

    def test_pagination_last_page(self):
        """最后一页：下一页仍指向 total_pages"""
        from src.option_card import OptionCardData, OptionItem, build_option_card
        items = [OptionItem(key=f"k{i}", label=f"l{i}") for i in range(25)]
        card = build_option_card(OptionCardData(
            title="t", category="ws", items=items, page=2
        ))
        column_sets = _collect_column_sets(card)
        page_nav = column_sets[-1]["columns"]
        next_btn = page_nav[2]["elements"][0]
        assert next_btn["value"]["page"] == 2

    def test_label_truncation(self):
        """长 label 应被截断"""
        from src.option_card import OptionCardData, OptionItem, build_option_card
        items = [OptionItem(key="x", label="很长的名字" * 5)]
        card = build_option_card(OptionCardData(
            title="t", category="ws", items=items, max_label_len=10
        ))
        buttons = _collect_buttons(card)
        assert len(buttons) == 1
        text = buttons[0]["text"]["content"]
        # 包含 "1. " 前缀 + 截断
        assert text.startswith("1. ")
        # 前缀 3 字符 + 截断 10 字符
        assert len(text) <= 3 + 10

    def test_current_item_highlighted(self):
        """当前项应为 primary 蓝，其他为 default"""
        from src.option_card import OptionCardData, OptionItem, build_option_card
        items = [
            OptionItem(key="a", label="aaa"),
            OptionItem(key="b", label="bbb", is_current=True),
        ]
        card = build_option_card(OptionCardData(title="t", category="ws", items=items))
        buttons = _collect_buttons(card)
        for btn in buttons:
            if btn["value"]["key"] == "b":
                assert btn["type"] == "primary"
            else:
                assert btn["type"] == "default"

    def test_max_buttons_per_row(self):
        """每行不超过 5 个按钮（即 column_set 最多 5 个 column）"""
        from src.option_card import OptionCardData, OptionItem, build_option_card
        items = [OptionItem(key=f"k{i}", label=f"l{i}") for i in range(20)]
        card = build_option_card(OptionCardData(title="t", category="ws", items=items))
        column_sets = _collect_column_sets(card)
        # 第一行有 5 个 button column（不是翻页行）
        for cs in column_sets[:-1]:
            assert len(cs["columns"]) <= 5

    def test_header_note_included(self):
        """header_note 应作为顶部 markdown"""
        from src.option_card import OptionCardData, OptionItem, build_option_card
        items = [OptionItem(key="a", label="a")]
        card = build_option_card(OptionCardData(
            title="t", category="ws", items=items, header_note="提示信息"
        ))
        # 第一个 markdown 元素应该是 header_note
        first = card["body"]["elements"][0]
        assert first["tag"] == "markdown"
        assert first["content"] == "提示信息"

    def test_columns_have_weighted_width(self):
        """每个 column 应有 width=weighted + weight=1"""
        from src.option_card import OptionCardData, OptionItem, build_option_card
        items = [OptionItem(key=f"k{i}", label=f"l{i}") for i in range(3)]
        card = build_option_card(OptionCardData(title="t", category="ws", items=items))
        column_sets = _collect_column_sets(card)
        for cs in column_sets:
            for column in cs["columns"]:
                assert column["width"] == "weighted"
                assert column["weight"] == 1


class TestParseActionValue:
    def test_dict_passthrough(self):
        from src.option_card import parse_action_value
        assert parse_action_value({"opt": "select"}) == {"opt": "select"}

    def test_string_json(self):
        from src.option_card import parse_action_value
        assert parse_action_value('{"opt": "page"}') == {"opt": "page"}

    def test_none(self):
        from src.option_card import parse_action_value
        assert parse_action_value(None) is None

    def test_invalid_string(self):
        from src.option_card import parse_action_value
        assert parse_action_value("not json") is None

    def test_other_type(self):
        from src.option_card import parse_action_value
        assert parse_action_value(123) is None