# 直接执行器使用说明

## 概述

直接执行器（DirectClaudeCodeExecutor）允许飞书服务在同一个 Claude Code 进程中执行命令，而不是启动新的子进程。这样可以：

- 共享同一个上下文，支持持续改进
- 减少进程创建开销
- 保持会话连续性

## Session 管理

### 自动 Session 检测

系统集成了智能 Session 管理功能：

1. **ClaudeSessionManager** 自动处理 Session 生命周期
   - 检测运行中的 Claude Code 进程
   - 查找最近使用的 Session ID
   - 按需创建新的 Session

2. **Session 获取优先级**
   - 缓存的 Session ID
   - 环境变量 `CLAUDE_SESSION_ID`
   - 自动查找/创建的 Session ID

3. **进程检测**
   - 使用 `psutil` 检测运行中的进程
   - 基于工作目录匹配进程
   - 支持跨进程 Session 复用

## 启用方法

### 1. 环境变量配置

在 `.env` 文件中添加：

```bash
# Claude Code 配置

## 工作原理

### 会话管理

- Session ID 可通过环境变量配置或自动检测
- 所有命令共享同一个会话上下文
- 使用 `-r` (resume) 参数恢复已有会话
- Session 缓存机制减少重复查询

### 输出流处理

- 使用 `--output-format=stream-json` 获取实时输出
- 解析 JSON 流，提取有用的文本内容
- 支持多种消息类型（delta、text、result）

### 输出流处理

- 使用 `--output-format=stream-json` 获取实时输出
- 解析 JSON 流，提取有用的文本内容
- 支持多种消息类型（delta、text、result）

## 配置选项

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `CLAUDE_CODE_CLI` | `/path/to/your/claude` | Claude CLI 路径 |
| `CLAUDE_CODE_DIR` | 当前目录 | Claude Code 工作目录 |
| `CLAUDE_SESSION_ID` | 空 | 可选：指定固定的 Session ID |

## 注意事项

1. **会话连续性**: 所有命令共享同一个会话，历史对话会被保留
2. **内存使用**: 由于共享上下文，长时间运行的服务可能需要考虑内存使用
3. **错误处理**: 与子进程方式相比，错误处理有所不同
4. **工具访问**: Claude 可以使用所有可用的工具（Bash、Read、Edit 等）

## 性能对比

| 特性 | 子进程方式 | 直接执行器 |
|------|-----------|------------|
| 启动速度 | 慢（需要创建进程） | 快 |
| 上下文共享 | 无 | 有 |
| 内存使用 | 低 | 较高 |
| 会话连续性 | 无 | 有 |
| 错误隔离 | 好 | 需要额外处理 |

## 示例

### 基本使用

```python
from src.claude import DirectClaudeCodeExecutor

executor = DirectClaudeCodeExecutor()

# 执行命令
async for output in executor.execute_command("task-123", "list files in current directory"):
    print(output)
```

### 高级使用

```python
from src.claude import ClaudeCodeInterface
from pathlib import Path

# 指定工作目录和 Session ID
interface = ClaudeCodeInterface(
    workspace=Path("/path/to/project"),
    use_direct_executor=True,
    session_id="your-session-id-uuid"
)

# 执行复杂命令
command = """
分析这个项目的结构，并创建一个README.md文件
包含项目概述、安装步骤和使用说明
"""

# 执行命令并获取状态和结果
status, result = await interface.execute_task(task, session_id="your-session-id-uuid")
```

## Session Manager API

`ClaudeSessionManager` 提供以下方法：

```python
from src.claude_session_manager import ClaudeSessionManager

manager = ClaudeSessionManager()

# 查找运行中的 session
session_id = manager.find_running_session()

# 检查是否有运行中的进程
is_running = manager.is_claude_running()

# 启动新的 session（在 tmux 中）
session_id = manager.start_claude_session()

# 获取或创建 session
session_id = manager.get_or_create_session(start_if_missing=True)
```

## 故障排除

### 常见错误

1. **Session ID 错误**
   - 确保 UUID 格式正确
   - 检查 `-r` 参数是否正确传递
   - 尝试清空 `CLAUDE_SESSION_ID` 使用自动模式

2. **输出格式错误**
   - 确保 `--verbose` 参数已添加
   - 检查 `--output-format=stream-json` 是否正确

3. **权限错误**
   - 确保工作目录存在且有读写权限
   - 检查 Claude CLI 路径是否正确

4. **Session 检测失败**
   - 检查 `~/.claude/projects/` 目录权限
   - 确保 tmux 已安装（用于自动启动 Session）
   - 查看日志了解详细错误信息

### 调试技巧

1. 启用详细日志：
   ```python
   import logging
   logging.getLogger("src.claude").setLevel(logging.DEBUG)
   logging.getLogger("src.claude_session_manager").setLevel(logging.DEBUG)
   ```

2. 检查 Session Manager 状态：
   ```python
   from src.claude_session_manager import session_manager

   session_id = session_manager.find_running_session()
   print(f"Current session: {session_id}")

   is_running = session_manager.is_claude_running()
   print(f"Claude Code running: {is_running}")
   ```

3. 检查命令参数：
   ```python
   args = executor._prepare_command_args("your command")
   print("Command args:", args)
   ```

## 更新日志

### v1.1.0
- 添加智能 Session 管理
  - 自动检测运行中的 Claude Code 进程
  - 动态查找或创建 Session ID
  - 集成 TaskManager 实现 Session 缓存
- 支持通过 `-r` 参数恢复已有 Session
- 添加 `ClaudeSessionManager` 模块

### v1.0.0
- 初始版本
- 实现基本的直接执行功能
- 支持 JSON 流输出解析
- 添加会话管理