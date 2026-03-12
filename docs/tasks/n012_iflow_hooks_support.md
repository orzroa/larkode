# N012: iFlow CLI Hooks 支持

## 任务概述

修改 `hook_handler.py` 以支持 iFlow CLI 的 Hooks 机制，处理 `UserPromptSubmit`、`Stop`、`Notification` 三种事件。

## 架构设计

```
src/interfaces/hook_handler.py    # 接口定义
├── IHookHandler                  # 抽象接口
├── ClaudeHookHandler             # Claude Code 实现
├── IFlowHookHandler              # iFlow CLI 实现
└── detect_handler()              # 自动检测环境

src/hook_handler.py                   # 主入口
├── main()                        # 自动检测处理器
├── handle_event()                # 统一事件处理
└── send_feishu_notification()    # 飞书通知（共用）
```

## iFlow CLI 配置方法

### 1. 创建 settings.json

在项目目录 `.iflow/settings.json` 或用户目录 `~/.iflow/settings.json`：

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/larkode/src/hook_handler.py",
            "timeout": 10
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/larkode/src/hook_handler.py",
            "timeout": 10
          }
        ]
      }
    ],
    "Notification": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/larkode/src/hook_handler.py",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

### 2. 环境变量配置

确保 `.env` 文件中有飞书配置：

```bash
FEISHU_APP_ID=your_app_id
FEISHU_APP_SECRET=your_app_secret
FEISHU_HOOK_NOTIFICATION_USER_ID=your_user_id
```

### 3. stdin 数据格式

iFlow CLI 传递给 Hook 的 JSON 格式：

```json
{
  "session_id": "xxx",
  "hook_event_name": "UserPromptSubmit",
  "cwd": "/path/to/project",
  "user_prompt": "用户输入内容",
  "notification_message": "通知内容",
  "last_assistant_message": "AI 最后回复"
}
```

## Hook 事件处理

| Hook 类型 | 触发时机 | 行为 |
|-----------|---------|------|
| UserPromptSubmit | 用户提交提示前 | 发送用户提问通知到飞书 |
| Stop | 会话结束 | 发送完成通知到飞书 |
| Notification | 发送通知时 | 发送通知卡片到飞书 |

## 环境变量对照

| Claude Code | iFlow CLI |
|-------------|-----------|
| CLAUDE_SESSION_ID | IFLOW_SESSION_ID |
| CLAUDE_CODE_DIR | IFLOW_CWD |
| sys.argv[1] | IFLOW_HOOK_EVENT_NAME |

## 实现状态

- [x] 创建 `IHookHandler` 接口
- [x] 实现 `ClaudeHookHandler`
- [x] 实现 `IFlowHookHandler`
- [x] 实现 `detect_handler()` 自动检测
- [x] 重构 `hook_handler.py` 使用接口
- [ ] 测试 iFlow CLI 环境下的 Hook 触发

## 相关文件

- `src/interfaces/hook_handler.py` - 接口定义
- `src/hook_handler.py` - Hook 处理入口
- `.iflow/settings.json` - iFlow CLI 配置
