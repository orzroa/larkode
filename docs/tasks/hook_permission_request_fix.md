# Hook PermissionRequest 事件修复

## 问题描述

用户反馈三个 Hook（UserPromptSubmit、Stop、PermissionRequest）中，前两个正常工作，但 PermissionRequest 权限交互卡片无法显示。

## 原因分析

1. **stdin 数据解析问题**：`HookContext.from_dict()` 方法在解析 `tool_input` 字段时，如果值为空字典会返回 `None` 而不是空字典
2. **参数传递问题**：`build_permission_message(context)` 调用时没有显式传递 `tool_input` 参数

## 修复内容

### 1. `src/interfaces/hook_handler.py`

**`HookContext.from_dict()` 方法**：
```python
# 修复前
tool_name = data.get("tool_name") or data.get("toolName")
tool_input = data.get("tool_input") or data.get("toolInput")

# 修复后
tool_name = data.get("tool_name") or data.get("toolName") or ""
tool_input = data.get("tool_input") or data.get("toolInput") or {}
```

确保即使数据不存在，也返回空字符串/空字典而不是 `None`。

**`DefaultHookHandler.parse_stdin()` 方法**：
```python
# 修复前
tool_name = data.get("tool_name") or data.get("toolName")
tool_input = data.get("tool_input") or data.get("toolInput")

# 修复后
tool_name = data.get("tool_name") or data.get("toolName") or ""
tool_input = data.get("tool_input") or data.get("toolInput") or {}
```

### 2. `src/hook_handler.py`

**`handle_event()` 函数**：
```python
# 修复前
if context.event_type == HookEventType.PERMISSION_REQUEST:
    tool_name = context.tool_name or ""
    if tool_name == "AskUserQuestion":
        log_event(data, "发送 ESC 取消等待")
        send_escape_to_tmux()
    message = build_permission_message(context)

# 修复后
if context.event_type == HookEventType.PERMISSION_REQUEST:
    tool_name = context.tool_name or ""
    tool_input = context.tool_input or {}
    if tool_name == "AskUserQuestion":
        log_event(data, "发送 ESC 取消等待")
        send_escape_to_tmux()
    message = build_permission_message(context, tool_input)
```

显式获取 `tool_input` 并传递给 `build_permission_message` 函数。

## 验证方式

### 1. 单元测试验证
```bash
python3 -m pytest tests/test_hook_handler.py -v
```

### 2. 手动验证
```bash
python3 -c "
from src.interfaces.hook_handler import HookContext, HookEventType
from src.log_hook import build_permission_message

data = {
    'hook_event_name': 'PermissionRequest',
    'tool_name': 'AskUserQuestion',
    'tool_input': {
        'questions': [
            {
                'header': '确认操作',
                'question': '您想执行什么操作？',
                'options': [
                    {'label': '选项 1', 'description': '描述 1'}
                ],
                'multiSelect': False
            }
        ]
    }
}

context = HookContext.from_dict(data)
message = build_permission_message(context, context.tool_input or {})
print(message)
"
```

输出应为：
```
**确认操作**
您想执行什么操作？
1. 选项 1 - 描述 1

(单选)
```

## 相关文件

| 文件 | 修改内容 |
|------|---------|
| `src/interfaces/hook_handler.py` | 修复 `from_dict()` 和 `parse_stdin()` 的空值处理 |
| `src/hook_handler.py` | 修复 `handle_event()` 的参数传递 |

## 测试结果

- 所有 317 个测试通过
- HookContext 正确解析 `tool_name` 和 `tool_input`
- `build_permission_message` 正确构建权限请求消息
