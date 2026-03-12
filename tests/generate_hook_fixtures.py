#!/usr/bin/env python3
"""
从日志文件中提取 Hook 报文并生成测试 fixture 文件

使用方法：
1. 提取最新的 Hook 事件并保存为 JSON 文件
   python3 tests/generate_hook_fixtures.py

2. 指定提取数量
   python3 tests/generate_hook_fixtures.py --count 20

3. 指定日志文件路径
   HOOK_LOG_PATH=/path/to/hook_events.jsonl python3 tests/generate_hook_fixtures.py

生成的文件可以用于：
- 离线测试（不需要实际触发 Hook）
- 回归测试（使用真实的生产数据）
- 性能测试（批量处理多个事件）
"""
import argparse
import json
import os
from datetime import datetime
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"
FIXTURES_DIR = PROJECT_ROOT / "tests" / "hook_fixtures"


def extract_hook_events(log_path, count=10):
    """从日志文件中提取 Hook 事件"""
    if not Path(log_path).exists():
        print(f"错误：日志文件不存在：{log_path}")
        return []

    events = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                events.append(event)
            except json.JSONDecodeError as e:
                print(f"解析 JSON 失败：{e}")
                continue

    print(f"从日志文件中读取了 {len(events)} 个事件")
    return events[-count:] if count > 0 else events


def categorize_events(events):
    """按事件类型分类"""
    categorized = {
        "UserPromptSubmit": [],
        "Stop": [],
        "PermissionRequest": [],
        "Notification": [],
        "other": [],
    }

    for event in events:
        hook_event = event.get("hook_event", "")
        if hook_event in categorized:
            categorized[hook_event].append(event)
        else:
            categorized["other"].append(event)

    return categorized


def generate_fixture_file(events, output_path):
    """生成 fixture 文件"""
    fixture = {
        "generated_at": datetime.now().isoformat(),
        "count": len(events),
        "events": []
    }

    for event in events:
        stdin_parsed = event.get("stdin_parsed", {})
        fixture["events"].append({
            "hook_event": event.get("hook_event", ""),
            "timestamp": event.get("timestamp", ""),
            "tool_name": stdin_parsed.get("tool_name", ""),
            "tool_input": stdin_parsed.get("tool_input", {}),
            "prompt": stdin_parsed.get("prompt", ""),
            "last_assistant_message": stdin_parsed.get("last_assistant_message", ""),
            "session_id": stdin_parsed.get("session_id", ""),
            "cwd": stdin_parsed.get("cwd", ""),
        })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(fixture, f, ensure_ascii=False, indent=2)

    print(f"已生成 fixture 文件：{output_path}")
    return output_path


def generate_test_file(fixture_path):
    """根据 fixture 文件生成测试代码"""
    with open(fixture_path, "r", encoding="utf-8") as f:
        fixture = json.load(f)

    test_lines = [
        "#!/usr/bin/env python3",
        f'"""',
        f"自动生成的 Hook 测试 - 基于 {fixture['generated_at']} 的数据",
        f"",
        f"包含 {fixture['count']} 个事件",
        f'"""',
        "import json",
        "import pytest",
        "from pathlib import Path",
        "",
        "# 加载 fixture 数据",
        f"FIXTURE_PATH = Path(__file__).parent / \"{Path(fixture_path).name}\"",
        "with open(FIXTURE_PATH, 'r', encoding='utf-8') as f:",
        "    FIXTURE = json.load(f)",
        "",
        "# 导入被测试的函数",
        "from src.log_hook import _build_permission_content",
        "",
        "",
        "class TestGeneratedHookEvents:",
        '    """自动生成的 Hook 事件测试"""',
        "",
    ]

    # 为每个事件生成测试方法
    for i, event in enumerate(fixture["events"]):
        hook_event = event.get("hook_event", "unknown")
        tool_name = event.get("tool_name", "")

        # 生成方法名
        method_name = f"test_event_{i:03d}_{hook_event.lower()}"
        if tool_name:
            method_name += f"_{tool_name.lower()}"

        # 清理方法名中的非法字符
        method_name = method_name.replace(" ", "_").replace("-", "_")

        # 生成测试代码
        test_lines.extend([
            f"    def {method_name}(self):",
            f'        """测试 {hook_event} 事件"""',
            f"        event = FIXTURE['events'][{i}]",
        ])

        if hook_event == "UserPromptSubmit":
            test_lines.extend([
                f"        prompt = event.get('prompt', '')",
                f"        assert len(prompt) > 0, 'prompt 不能为空'",
                f"        print(f'Prompt: {{prompt[:100]}}...')",
            ])
        elif hook_event == "Stop":
            test_lines.extend([
                f"        message = event.get('last_assistant_message', '')",
                f"        assert len(message) > 0, 'message 不能为空'",
                f"        print(f'Stop message: {{message[:100]}}...')",
            ])
        elif hook_event == "PermissionRequest":
            test_lines.extend([
                f"        tool_name = event.get('tool_name', '')",
                f"        tool_input = event.get('tool_input', {{}})",
                f"        message = _build_permission_content(tool_name, tool_input)",
                f"        assert message, '消息不能为空'",
                f"        print(f'Permission message: {{message[:100]}}...')",
            ])
        else:
            test_lines.extend([
                f"        # 其他事件类型",
                f"        print(f'Event {{i}}: {{event}}')",
            ])

        test_lines.append("")

    # 写入文件
    test_path = output_dir / f"test_hook_events_{timestamp}.py"
    with open(test_path, "w", encoding="utf-8") as f:
        f.write("\n".join(test_lines))

    print(f"已生成测试文件：{test_path}")
    return test_path


def main():
    parser = argparse.ArgumentParser(description="从日志文件中提取 Hook 报文并生成测试 fixture")
    parser.add_argument("--count", "-c", type=int, default=10, help="提取的事件数量")
    parser.add_argument("--log-path", "-l", type=str, default=None, help="日志文件路径")
    parser.add_argument("--output-dir", "-o", type=str, default=str(FIXTURES_DIR), help="输出目录")
    parser.add_argument("--skip-test-gen", action="store_true", help="跳过测试文件生成")

    args = parser.parse_args()

    # 确定日志文件路径
    log_path = args.log_path or os.getenv("HOOK_LOG_PATH", str(LOGS_DIR / "hook_events.jsonl"))

    # 确保输出目录存在
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 提取事件
    print(f"从日志文件提取事件：{log_path}")
    events = extract_hook_events(log_path, args.count)

    if not events:
        print("没有提取到任何事件")
        return 1

    # 分类统计
    categorized = categorize_events(events)
    print("\n事件统计:")
    for event_type, event_list in categorized.items():
        if event_list:
            print(f"  {event_type}: {len(event_list)}")

    # 生成 fixture 文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    fixture_filename = f"hook_events_{timestamp}.json"
    fixture_path = output_dir / fixture_filename

    # 生成 fixture 文件
    generate_fixture_file(events, fixture_path)

    # 生成测试文件
    if not args.skip_test_gen:
        generate_test_file(fixture_path)

    print(f"\n完成！生成了 {len(events)} 个事件的 fixture 文件")
    return 0


if __name__ == "__main__":
    exit(main())
