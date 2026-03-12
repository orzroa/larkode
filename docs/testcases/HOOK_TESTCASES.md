# Hook 测试案例

本文档包含 Claude Code Hook 的三种核心事件测试样本。

## 概述

Hook 事件用于追踪 AI 交互过程，当前支持的三个核心事件：

| 事件类型 | 说明 | 触发时机 |
|---------|------|---------|
| UserPromptSubmit | 用户提问 | 用户发送消息给 AI |
| Stop | AI 完成响应 | AI 完成一次对话 |
| PermissionRequest | 权限请求 | AI 需要执行敏感操作 |

---

## 1. UserPromptSubmit（用户提问）

### 用途
当用户向 AI 发送消息时触发，用于发送用户提问通知到飞书。

### stdin 样本

```json
{
  "session_id": "9238a715-434b-4107-9fbc-eaa3ec683680",
  "transcript_path": "/home/sc/.claude/projects/-home-sc-Workspaces-github-claude-feishu/9238a715-434b-4107-9fbc-eaa3ec683680.jsonl",
  "cwd": "/home/sc/Workspaces/github/claude-feishu",
  "permission_mode": "default",
  "hook_event_name": "UserPromptSubmit",
  "prompt": "帮我分析一下项目结构"
}
```

### 关键字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `prompt` | string | 用户输入的问题内容 |
| `session_id` | string | 会话唯一标识 |
| `cwd` | string | 当前工作目录 |

### 处理逻辑
```python
# 发送飞书通知
await send_feishu_notification(prompt, "prompt", "UserPromptSubmit")
```

### 预期飞书卡片
- 标题：用户提问
- 颜色：蓝色
- 内容：用户的问题 + 消息编号 + 时间戳

---

## 2. Stop（AI 完成响应）

### 用途
当 AI 完成一次对话响应时触发，用于发送完成通知到飞书。

### stdin 样本

```json
{
  "session_id": "cb184412-45b1-476b-a061-3fc249ecd3cc",
  "transcript_path": "/home/sc/.claude/projects/-home-sc-Workspaces-github-claude-feishu/cb184412-45b1-476b-a061-3fc249ecd3cc.jsonl",
  "cwd": "/home/sc/Workspaces/github/claude-feishu",
  "permission_mode": "default",
  "hook_event_name": "Stop",
  "stop_hook_active": false,
  "last_assistant_message": "项目结构分析完成..."
}
```

### 关键字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `last_assistant_message` | string | AI 的最后一条回复 |
| `stop_hook_active` | bool | 是否激活 stop hook |

### 处理逻辑
```python
# 发送飞书通知
message = last_assistant_message or "已完成响应"
await send_feishu_notification(message, "stop", "Stop")
```

### 预期飞书卡片
- 标题：回复完成
- 颜色：绿色
- 内容：AI 的回复 + 消息编号 + 时间戳

---

## 3. PermissionRequest（权限请求）

### 用途
当 AI 需要执行敏感操作时触发，用于发送权限请求到飞书，让用户确认。

### stdin 样本

#### 3.1 Bash 命令权限

```json
{
  "session_id": "1198cb83-ed15-4668-a802-a02827a837ec",
  "transcript_path": "/home/ubuntu/.claude/projects/-home-ubuntu-Workspaces-github-claude-feishu/1198cb83-ed15-4668-a802-a02827a837ec.jsonl",
  "cwd": "/home/ubuntu/Workspaces/github/claude-feishu",
  "permission_mode": "default",
  "hook_event_name": "PermissionRequest",
  "tool_name": "Bash",
  "tool_input": {
    "command": "rm -rf /home/ubuntu/Workspaces/github/claude-feishu/abc",
    "description": "删除 abc 目录及其所有内容"
  }
}
```

#### 3.2 AskUserQuestion（用户选择）

```json
{
  "session_id": "xxx",
  "cwd": "/home/ubuntu/project",
  "permission_mode": "default",
  "hook_event_name": "PermissionRequest",
  "tool_name": "AskUserQuestion",
  "tool_input": {
    "questions": [
      {
        "question": "请选择您喜欢的编程语言",
        "header": "语言选择",
        "options": [
          {"label": "Python", "description": "简洁优雅"},
          {"label": "JavaScript", "description": "Web 开发"},
          {"label": "Rust", "description": "高性能"}
        ],
        "multiSelect": false
      }
    ]
  }
}
```

#### 3.3 ExitPlanMode（退出计划模式）

```json
{
  "session_id": "xxx",
  "cwd": "/home/ubuntu/project",
  "permission_mode": "plan",
  "hook_event_name": "PermissionRequest",
  "tool_name": "ExitPlanMode",
  "tool_input": {
    "plan": "# 实施计划\n\n## 步骤\n1. 第一步\n2. 第二步\n3. 第三步"
  }
}
```

### 关键字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `tool_name` | string | 工具名称（Bash/AskUserQuestion/ExitPlanMode） |
| `tool_input` | object | 工具输入参数 |
| `permission_mode` | string | 权限模式（default/plan/bypassPermissions） |

### 处理逻辑

```python
if tool_name == "AskUserQuestion":
    # 构建选项列表
    message = build_ask_user_question_message(tool_input)
    # 发送 ESC 取消等待
    send_escape_to_tmux()
elif tool_name == "ExitPlanMode":
    # 显示 Plan 内容
    message = build_exit_plan_mode_message(tool_input)
else:
    # Bash 等工具，显示 tmux 输出
    message = get_tmux_output()

await send_feishu_notification(message, "permission", "PermissionRequest")
```

### 预期飞书卡片
- 标题：交互请求
- 颜色：橙色
- 内容：根据 tool_name 显示不同内容

---

## 测试方法

### 单元测试

```bash
# 运行 Hook 测试
python3 -m pytest tests/test_hook_from_log.py -v

# 运行特定测试
python3 -m pytest tests/test_hook_from_log.py::TestHookSimulatedEvents -v
```

### 手动测试

```python
from src.log_hook import _build_permission_content

# 测试 AskUserQuestion
tool_input = {
    "questions": [{
        "question": "请选择",
        "options": [{"label": "A"}, {"label": "B"}],
        "multiSelect": False
    }]
}
message = _build_permission_content("AskUserQuestion", tool_input)
print(message)
```

---

## 数据来源

这些测试样本来自 `logs/hook_events.jsonl` 中的真实事件记录。

### 提取方法

```bash
# 从日志中提取最新样本
python3 tests/generate_hook_fixtures.py --count 10
```

---

## 变更历史

| 日期 | 变更内容 |
|------|---------|
| 2026-03-07 | 初始版本，包含三种核心事件样本 |