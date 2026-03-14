# N009 - 飞书交互式消息支持

## 背景问题

Claude Code 执行过程中需要用户交互（如权限确认、选项选择等），但飞书是单向消息推送，需要将交互请求展示给用户。

## 最终方案：PermissionRequest 展示卡片

### 方案概述

- 当 Claude Code 触发 `PermissionRequest` hook 时，发送展示卡片给用户
- 卡片仅展示信息，不交互
- 用户在飞书中手动输入文字回复
- 回复作为新的 UserPromptSubmit 发送给 Claude Code

### Hook 事件类型

| 事件 | 作用 |
|------|------|
| `PermissionRequest` | 交互请求核心事件，包含完整的交互数据 |
| `PreToolUse` | 工具使用前置事件（用于记录 tool 信息） |
| `Notification` | 通知事件（触发时机后于 PermissionRequest） |

### Hook 报文结构示例

**Bash 交互请求：**
```json
{
  "tool_name": "Bash",
  "tool_input": {
    "command": "rm -rf /path/to/larkode/abc",
    "description": "删除 abc 目录及其所有内容"
  },
  "permission_suggestions": [...]
}
```

**AskUserQuestion 请求：**
```json
{
  "tool_name": "AskUserQuestion",
  "tool_input": {
    "questions": [{
      "question": "请选择需要重构的范围（可多选）：",
      "header": "重构范围",
      "options": [
        {"label": "src/ 大文件", "description": "..."},
        {"label": "src/ 根目录", "description": "..."}
      ],
      "multiSelect": true
    }]
  }
}
```

### 卡片内容规范

| tool_name | 标题 | 内容 | template |
|-----------|------|------|----------|
| `Bash`, `Write`, 其他 | PermissionRequest | tool_input 美化 JSON 格式展示 + `1. yes  2. always  3. no` | orange |
| `AskUserQuestion` | PermissionRequest | 问题 + 所有选项（编号列表）+ (多选/单选) | orange |

**卡片格式：**
```
Header: "PermissionRequest" (orange)
Body:
  📨 消息编号: xxx
  🕒 2026-03-01 13:24:23
  [内容...]
```

**Bash 示例：**
```
📨 消息编号: 120
🕒 2026-03-01 13:24:23

```json
{
  "command": "rm -rf /path/to/larkode/abc",
  "description": "删除 abc 目录及其所有内容"
}
```

请回复：
1. yes
2. always
3. no
```

**AskUserQuestion 示例：**
```
📨 消息编号: 121
🕒 2026-03-01 13:30:07

请选择需要重构的范围（可多选）：

1. src/ 大文件 - hook_handler.py (1077行) + feishu/__init__.py (1301行) + claude/__init__.py (714行) - 职责混杂的大文件
2. src/ 根目录 - message_handler.py (364行) + 根目录重复文件 - 根目录混杂问题
3. src/interfaces/ - 接口与实现混淆，与根目录有重复类定义
4. config/ + tests/ - config/settings.py 硬编码 + tests/ 测试覆盖不完整

(多选)
```

### 用户交互流程

```
Claude Code 需要交互
    ↓
触发 PermissionRequest hook
    ↓
服务端发送展示卡片到飞书
    ↓
用户在飞书中看到卡片和选项
    ↓
用户输入文字回复（如 "yes", "1", "1,2"）
    ↓
回复作为新的 UserPromptSubmit 发送给 Claude Code
    ↓
Claude Code 继续执行
```

### 注意事项

1. **permission_suggestions 不展示**：只展示核心交互内容
2. **所有卡片都有编号**：和其他卡片保持一致
3. **Bash 显示完整命令**：不简化
4. **不使用交互式卡片组件**：只用展示卡片，用户手动输入回复

## 实现位置

- `src/hook_handler.py`：添加 `PermissionRequest` hook 处理
- 参考 `send_feishu_notification()` 的卡片格式

## 相关文件

- N008: 长内容文件发送功能（已实现）
- 当前文档: N009（本文档）

## Hook 样例报文

（保留原始样例报文，用于参考）

{"session_id":"1198cb83-ed15-4668-a802-a02827a837ec","transcript_path":"/home/user/.claude/projects/-home-user-Workspaces-github-larkode/1198cb83-ed15-4668-a802-a02827a837ec.jsonl","cwd":"/path/to/larkode","permission_mode":"default","hook_event_name":"PermissionRequest","tool_name":"Bash","tool_input":{"command":"rm -rf /path/to/larkode/abc","description":"删除 abc 目录及其所有内容"},"permission_suggestions":[{"type":"addDirectories","directories":["/path/to/larkode/abc"],"destination":"session"},{"type":"setMode","mode":"acceptEdits","destination":"session"}]}

{"session_id":"f8efbd38-56cf-43b0-9274-c89b3a9e3234","transcript_path":"/home/user/.claude/projects/-home-user-Workspaces-github-larkode/f8efbd38-56cf-43b0-9274-c89b3a9e3234.jsonl","cwd":"/path/to/larkode","permission_mode":"default","hook_event_name":"PermissionRequest","tool_name":"Write","tool_input":{"file_path":"/path/to/larkode/docs/todo/n009-feishu-interaction-for-claude-prompts.md","content":"# N009 - 飞书交互式消息支持\n\n## 背景问题\n\nClaude Code 执行过程中需要用户交互（如权限确认、
选项选择等），但飞书是单向消息推送，需要将交互请求展示给用户。\n\n## 最终方案：PermissionRequest 展示卡片\n\n### 方案概述\n\n- 当 Claude Code 触发 `PermissionRequest` hook 时，发送展示卡片
给用户\n- 卡片仅展示信息，不交互\n- 用户在飞书中手动输入文字回复\n- 回复作为新的 UserPromptSubmit 发送给 Claude Code\n\n### Hook 事件类型\n\n| 事件 | 作用 |\n|------|------|\n| `PermissionRequest` | 交互请求核心事件，包含完整的交互数据 |\n| `PreToolUse` | 工具使用前置事件（用于记录
 tool 信息） |\n| `Notification` | 通知事件（触发时机后于 PermissionRequest） |\n\n### Hook 报
文结构示例\n\n**Bash 交互请求：**\n```json\n{\n  \"tool_name\": \"Bash\",\n  \"tool_input\": {\n    \"command\": \"rm -rf /path/to/larkode/abc\",\n    \"description\": \"删除 abc 目录及其所有内容\"\n  },\n  \"permission_suggestions\": [...]\n}\n```\n\n**AskUserQuestion 请求：**\n```json\n{\n  \"tool_name\": \"AskUserQuestion\",\n  \"tool_input\": {\n    \"questions\": [{\n      \"question\": \"请选择需要重构的范围（可多选）：\",\n      \"header\": \"重构范围\",\n      \"options\": [\n        {\"label\": \"src/ 大文件\", \"description\": \"...\"},\n        {\"label\": \"src/ 根目录\", \"description\": \"...\"}\n      ],\n      \"multiSelect\": true\n    }]\n  }\n}\n```\n\n### 卡片内容规范\n\n| tool_name | 标题 | 内>容 | template |\n|-----------|------|------|----------|\n| `Bash`, `Write`, 其他 | PermissionRequest | tool_input 美化 JSON 格式展示 + `1. yes  2. always  3. no` | orange |\n| `AskUserQuestion` | PermissionRequest | 问题 + 所有选项（编号列表）+ (多选/单选) | orange |\n\n**卡片格式：**\n```\nHeader: \"PermissionRequest\" (orange)\nBody:\n  📨 消息编号: xxx\n  🕒 2026-03-01 13:24:23\n  [内容...]\n```\n\n**Bash 示例：**\n```\n📨 消息编号: 120\n🕒 2026-03-01 13:24:23\n\n```json\n{\n  \"command\": \"rm -rf /path/to/larkode/abc\",\n  \"description\": \"删除 abc 目录及其所有内容\"\n}\n```\n\n请回复：\n1. yes\n2. always\n3. no\n```\n\n**AskUserQuestion 示例：**\n```\n📨 消息编号: 121\n🕒 2026-03-01 13:30:07\n\n请选择
需要重构的范围（可多选）：\n\n1. src/ 大文件 - hook_handler.py (1077行) + feishu/__init__.py (1301行) + claude/__init__.py (714行) - 职责混杂的大文件\n2. src/ 根目录 - message_handler.py (364>行) + 根目录重复文件 - 根目录混杂问题\n3. src/interfaces/ - 接口与实现混淆，与根目录有重复类定
义\n4. config/ + tests/ - config/settings.py 硬编码 + tests/ 测试覆盖不完整\n\n(多选)\n```\n\n### 用户交互流程\n\n```\nClaude Code 需要交互\n    ↓\n触发 PermissionRequest hook\n    ↓\n服务端
发送展示卡片到飞书\n    ↓\n用户在飞书中看到卡片和选项\n    ↓\n用户输入文字回复（如 \"yes\", \"1\", \"1,2\"）\n    ↓\n回复作为新的 UserPromptSubmit 发送给 Claude Code\n    ↓\nClaude Code 继续执行\n```\n\n### 注意事项\n\n1. **permission_suggestions 不展示**：只展示核心交互内
容\n2. **所有卡片都有编号**：和其他卡片保持一致\n3. **Bash 显示完整命令**：不简化\n4. **不使用
交互式卡片组件**：只用展示卡片，用户手动输入回复\n\n## 实现位置\n\n- `src/hook_handler.py`：添加 `PermissionRequest` hook 处理\n- 参考 `send_feishu_notification()` 的卡片格式\n\n## 相关文件\n\n- N008: 长内容文件发送功能（已实现）\n- 当前文档: N009（本文档）\n\n## Hook 样例报文\n\n（保>留原始样例报文，用于参考）\n"},"permission_suggestions":[{"type":"setMode","mode":"acceptEdits","destination":"session"}]}

{"session_id":"1198cb83-ed15-4668-a802-a02827a837ec","transcript_path":"/home/user/.claude/projects/-home-user-Workspaces-github-larkode/1198cb83-ed15-4668-a802-a02827a837ec.jsonl","cwd":"/path/to/larkode","permission_mode":"default","hook_event_name":"PermissionRequest","tool_name":"AskUserQuestion","tool_input":{"questions":[{"question":"请选择需要重构的范围（可多选）：","header":"重构范围","options":[{"label":"src/ 大文件","description":"hook_handler.py (1077行) + feishu/__init__.py (1301行) + ai/__init__.py (714行) - 职责混杂的大文件"},{"label":"src/ 根目录","description":"message_handler.py (364行) + 根目录重复文件 - 根目录混杂问题"},{"label":"src/interfaces/","description":"接口与实现混淆，与根目录有重复类定义"},{"label":"config/ + tests/","description":"config/settings.py 硬编码 + tests/ 测试覆盖不完整"}],"multiSelect":true}]}}

{"session_id":"235b6c10-053c-433d-9d25-9c6bc51fa0f7","transcript_path":"/home/user/.claude/projects/-home-user-Workspaces-github-larkode/235b6c10-053c-433d-9d25-9c6bc51fa0f7.jsonl","cwd":"/path/to/larkode","permission_mode":"default","hook_event_name":"PermissionRequest","tool_name":"AskUserQuestion","tool_input":{"questions":[{"question":"请选择项目需要的业务模块？（可多选）","header":"业务模块","options":[{"label":"用户管理","description":"处理用户认证、登录、状态管理等用户相关功能"},{"label":"消息处理","description":"消息接收、路由、分发和持久化等消息处理功能"},{"label":"任务调度","description":"任务队列管理、调度和状态跟踪功能"},{"label":"权限控制","description":"权限控制、角色管理和访问控制等安全功能"}],"multiSelect":true},{"question":"请选择项目需要的支撑模块？（可多选）","header":"支撑模块","options":[{"label":"日志系统","description":"日志记录、分级、查询和归档等日志功能"},{"label":"缓存层","description":"Redis/Memcached缓存、缓存策略和失效机制"}],"multiSelect":true}]}}
