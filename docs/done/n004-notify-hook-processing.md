# Notify Hook 数据处理流程详解

**文档版本:** 1.0.0
**创建日期:** 2026-02-26
**适用场景:** Notification Hook（elicitation_dialog/permission_prompt/idle_prompt）

---

## 概述

本文档详细说明 Notification Hook 从读取 JSONL 文件到发出飞书消息的完整数据处理流程，以语言选择为例。

---

## 流程概览

```
用户发送语言选择命令
    ↓
Claude Code 触发 idle_prompt Notification event
    ↓
Hook 接收到 stdin 数据（包含 session_id、transcript_path、notification_type）
    ↓
根据 notification_type 选择不同的数据读取方法
    ↓
从 .claude/projects/[session_id].jsonl 读取数据
    ↓
格式化消息内容并添加 ESC 选项
    ↓
构建飞书交互式卡片
    ↓
发送到 Feishu 用户
```

---

## 详细处理流程

### 1. Hook 触发阶段

**触发条件：**
- Claude Code 使用 `AskUserQuestion` 工具（elicitation_dialog/permission_prompt）
- 或 Claude 等待用户输入（idle_prompt）

**触发示例：**
用户发送："我刚刚没发ping。你是不是看错了"

### 2. stdin 数据接收

Hook 通过标准输入接收数据（JSON 格式）：

```json
{
  "session_id": "ac5097c2-ef84-4d6c-a164-d1d2ad37a101",
  "transcript_path": "/home/user/.claude/projects/-home-user-Workspaces-github-larkode/ac5097c2-ef84-4d6c-a164-d1d2ad37a101.jsonl",
  "cwd": "/path/to/larkode",
  "hook_event_name": "Notification",
  "message": "Claude is waiting for your input",
  "notification_type": "idle_prompt"
}
```

**关键参数：**
- `session_id`: 会话 ID
- `transcript_path`: transcript 文件路径
- `notification_type`: 通知类型（elicitation_dialog/permission_prompt/idle_prompt）
- `message`: Claude 提示信息

### 3. 数据分流处理

在 `main()` 函数中：

```python
if hook_event == "Notification" and data.get("stdin_parsed"):
    notification_type = data["stdin_parsed"].get("notification_type")
    if notification_type in ["elicitation_dialog", "permission_prompt", "idle_prompt"]:
        session_id = data["stdin_parsed"].get("session_id", "")
        transcript_path = data["stdin_parsed"].get("transcript_path", "")

        # 根据类型选择读取方法
        if notification_type == "idle_prompt":
            ask_data = read_latest_assistant_message(transcript_path, session_id)
        else:
            ask_data = read_latest_ask_user_question(transcript_path, session_id)

        if ask_data:
            send_feishu_question_notification(ask_data, hook_event, notification_type)
```

### 4. 数据读取阶段

#### 4.1 idle_prompt 类型（语言选择示例）

使用 `read_latest_assistant_message()` 函数：

```python
def read_latest_assistant_message(transcript_path: str, session_id: str) -> dict:
    """读取最新的 assistant 消息"""
    try:
        with open(transcript_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        return None

    # 从后往前遍历，找到最新的 assistant 消息
    for line in reversed(lines):
        try:
            entry = json.loads(line.strip())

            # 检查是否是 assistant 消息
            if entry.get('type') == 'assistant':
                message_content = entry.get('message', [])
                if not isinstance(message_content, list):
                    continue

                # 提取所有 text 块
                message_parts = []
                for msg in message_content:
                    if msg.get('type') == 'text':
                        message_parts.append(msg.get('text', ''))

                if message_parts:
                    message = '\n'.join(message_parts)
                    return {
                        'title': '',  # assistant 消息没有 title
                        'message': message,
                        'session_id': session_id
                    }
        except json.JSONDecodeError:
            continue

    return None
```

**示例数据（语言选择）：**
```json
{
  "title": "",
  "message": "我看到了！您刚刚发送的是 \"我刚刚没发ping。你是不是看错了\"，这是一个普通的 UserPromptSubmit 事件，不会触发 Notification hook。

如果您想让我发送语言选择卡片到飞书，需要触发 Notification hook（elicitation_dialog 或 idle_prompt）。但简单地回复这个消息不会触发。

**语言选择 / Language Selection**

请选择您希望我创建架构文档的语言（回复数字）：

1. **简体中文**（Simplified Chinese）
2. **英语**（English）
3. **日语**（日本語）
4. **韩语**（한국어）
5. **法语**（Français）
6. **德语**（Deutsch）
7. **意大利语**（Italiano）
8. **西班牙语**（Español）
9. **葡萄牙语**（Português）
10. **俄语**（Русский）
11. **阿拉伯语**（العربية）

例如：回复 \"1\" 我将用简体中文创建架构文档

请回复数字 1-11 中的任意一个。",
  "session_id": "ac5097c2-ef84-4d6c-a164-d1d2ad37a101"
}
```

#### 4.2 elicitation_dialog/permission_prompt 类型

使用 `read_latest_ask_user_question()` 函数：

```python
def read_latest_ask_user_question(transcript_path: str, session_id: str) -> dict:
    """读取最新的 AskUserQuestion 工具调用"""
    try:
        with open(transcript_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        return None

    for line in reversed(lines):
        try:
            entry = json.loads(line.strip())

            if entry.get('type') == 'assistant':
                message_content = entry.get('message', [])
                if not isinstance(message_content, list):
                    continue

                for msg in message_content:
                    if msg.get('type') == 'tool_use':
                        tool_name = msg.get('name', '')

                        # 检查是否是 AskUserQuestion
                        if tool_name in ['AskUserQuestion', 'askUserQuestion']:
                            tool_input = msg.get('input', {})
                            title = tool_input.get('title', '')
                            options_text = tool_input.get('question', '')
                            message = tool_input.get('message', options_text)

                            return {
                                'title': title,
                                'message': message,
                                'session_id': session_id
                            }
        except json.JSONDecodeError:
            continue

    return None
```

### 5. 消息格式化阶段

使用 `send_feishu_question_notification()` 函数：

```python
def send_feishu_question_notification(data: dict, event_name: str = "Notification", notification_type: str = "") -> bool:
    """发送飞书问题通知"""
    try:
        # 获取数据
        title = data.get("title", "")
        message = data.get("message", "")

        # 标题处理（idle_prompt 使用默认值）
        if title:
            display_title = title
        else:
            display_title = "📋 需要您选择"

        # 解析选项并添加 ESC
        md_content = format_options_with_esc(message)

        # 构建卡片
        card = {
            "schema": "2.0",
            "config": {
                "wide_screen_mode": True
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": display_title
                },
                "template": "orange"  # 选择类卡片使用橙色
            },
            "body": {
                "elements": [
                    {
                        "tag": "markdown",
                        "content": f"🕒 `{timestamp}`\n\n{md_content}"
                    }
                ]
            }
        }
```

#### 5.1 format_options_with_esc 函数

```python
def format_options_with_esc(message: str) -> str:
    """格式化选项并添加 ESC 选项"""
    if not message:
        return message

    lines = message.strip().split('\n')
    formatted_lines = []
    has_options = False

    for line in lines:
        stripped = line.strip()
        # 检测是否是选项行
        if stripped and (
            stripped[0].isdigit() or  # 数字开头，如 "1. 选项"
            stripped.startswith('-') or  # 短横线开头
            stripped.startswith('*') or  # 星号开头
            stripped.startswith('•') or  # 圆点开头
            stripped.startswith('│') or  # 竖线开头（表格）
            stripped.startswith('|')   # 竖线开头（表格）
        ):
            formatted_lines.append(stripped)
            has_options = True
        elif stripped:
            # 普通文本行，保留
            formatted_lines.append(stripped)

    # 添加 ESC 选项
    if has_options:
        formatted_lines.append("ESC. 退出/什么都不选")

    return '\n'.join(formatted_lines)
```

**示例输出：**
```
我看到了！您刚刚发送的是 "我刚刚没发ping。你是不是看错了"

**语言选择 / Language Selection**

请选择您希望我创建架构文档的语言（回复数字）：

1. **简体中文**（Simplified Chinese）
2. **英语**（English）
3. **日语**（日本語）
4. **韩语**（한국어）
5. **法语**（Français）
6. **德语**（Deutsch）
7. **意大利语**（Italiano）
8. **西班牙语**（Español）
9. **葡萄牙语**（Português）
10. **俄语**（Русский）
11. **阿拉伯语**（العربية）

例如：回复 "1" 我将用简体中文创建架构文档

请回复数字 1-11 中的任意一个。
ESC. 退出/什么都不选
```

### 6. 飞书卡片构建

构建最终的飞书交互式卡片：

```python
card = {
    "schema": "2.0",
    "config": {
        "wide_screen_mode": True
    },
    "header": {
        "title": {
            "tag": "plain_text",
            "content": "📋 需要您选择"
        },
        "template": "orange"  # 选择类卡片使用橙色
    },
    "body": {
        "elements": [
            {
                "tag": "markdown",
                "content": "🕒 `2026-02-26 09:01:22`\n\n我看到了！您刚刚发送的是 \"我刚刚没发ping。你是不是看错了\"..."
            }
        ]
    }
}
```

### 7. API 发送

使用 lark_oapi SDK 发送消息：

```python
# 初始化客户端
client = lark.Client.builder() \
    .app_id(app_id) \
    .app_secret(app_secret) \
    .domain(domain) \
    .log_level(lark.LogLevel.WARNING) \
    .build()

# 构建请求
request = lark.api.im.v1.CreateMessageRequest.builder() \
    .receive_id_type("open_id") \
    .request_body(
        lark.api.im.v1.CreateMessageRequestBody.builder()
        .msg_type("interactive")
        .receive_id(user_id)
        .content(json.dumps(card, ensure_ascii=False))
        .build()
    ) \
    .build()

# 发送消息
response = client.im.v1.message.create(request)
```

### 8. 完整参数传递链

```
原始事件: UserPromptSubmit (用户发送语言选择命令)
    ↓
Transcript JSONL: 包含 assistant 消息（带语言选项文本）
    ↓
Notification Hook: notification_type = "idle_prompt"
    ↓
read_latest_assistant_message(): 返回 {title: "", message: "...语言选项..."}
    ↓
format_options_with_esc(): 添加 "ESC. 退出/什么都不选"
    ↓
send_feishu_question_notification(): 构建橙色选择卡片
    ↓
飞书 API: 发送到用户
    ↓
用户看到: 语言选择卡片，可点击 1-11 或 ESC
```

---

## 关键区别

### elicitation_dialog vs idle_prompt

| 特性 | elicitation_dialog | idle_prompt |
|------|------------------|-------------|
| 数据来源 | AskUserQuestion 工具调用 | 普通 assistant 消息 |
| title 字段 | 有（来自 tool_input.title） | 空（设为默认值） |
| message 内容 | tool_input.question | assistant 的 text 消息 |
| 触发条件 | Claude 使用 AskUserQuestion | Claude 等待用户输入 |

### 飞书卡片颜色

| 通知类型 | 卡片颜色 | 用途 |
|---------|---------|------|
| elicitation_dialog | orange | 选择对话框 |
| permission_prompt | orange | 权限确认 |
| idle_prompt | orange | 选择或等待输入 |

---

## 注意事项

1. **路径问题**: transcript_path 从 .claude/projects/ 读取，不是 hooks/logs/
2. **编码处理**: 所有文件读写使用 UTF-8 编码
3. **错误处理**: 每个环节都有完善的错误处理和日志记录
4. **长度限制**: 卡片内容超过 29000 字符会被截断
5. **ESC 选项**: 仅当检测到选项格式时才添加，避免普通消息也添加

---

## 故障排查

### 常见问题

1. **不发送卡片**
   - 检查 notification_type 是否正确
   - 确认 transcript_path 文件存在
   - 验证数据读取返回非 None

2. **内容乱码**
   - 确保 JSONL 文件编码正确
   - 检查特殊字符处理

3. **ESC 选项不显示**
   - 检查消息格式是否包含选项列表
   - 验证 format_options_with_esc 正确识别选项

---

## 结论

Notification Hook 通过精心设计的数据处理流程，能够准确地将 Claude Code 的交互意图转换为飞书用户友好的选择卡片。idle_prompt 的引入使得即使用户直接回复消息，也能正确触发语言选择等功能。