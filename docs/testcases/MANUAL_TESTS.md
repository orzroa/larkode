# 手动测试文档

本目录包含需要人工验证的手动测试脚本。

## 测试文件

| 文件 | 说明 |
|------|------|
| `n008_manual_test.py` | N008 长内容文件发送功能手动测试 |
| `n009_manual_test.py` | N009 PermissionRequest 卡片功能手动测试 |
| `run_manual_tests.sh` | 一键运行所有手动测试 |

## 与其他测试的区别

| 类型 | 示例文件 | 用途 |
|------|---------|------|
| **手动测试** | `n008_manual_test.py` | 需要在飞书中手动验证消息内容 |
| **单元测试** | `test_*.py` (除 manual) | 自动化测试，自动验证结果 |
| **Hook 代理** | `test_hook_interaction_scenarios.py` | 配置到 `~/.claude/settings.json`，用于记录 hook 事件 |

## 前置条件

在运行测试之前，请确保：

1. 已配置 `.env` 文件，包含以下配置：
   ```
   FEISHU_APP_ID=cli_xxxxx
   FEISHU_APP_SECRET=xxxxx
   FEISHU_HOOK_NOTIFICATION_USER_ID=ou_xxxxx  # 必须设置此项
   FEISHU_MESSAGE_DOMAIN=FEISHU_DOMAIN
   USE_FILE_FOR_LONG_CONTENT=true
   UPLOAD_DIR=./uploads
   ```

2. 已安装 Python 依赖：
   ```bash
   uv pip install -r requirements.txt
   ```

## 运行测试

### 方式一：运行所有手动测试

```bash
./tests/run_manual_tests.sh
```

### 方式二：单独运行 N008 手动测试

```bash
uv run tests/n008_manual_test.py
```

### 方式三：单独运行 N009 手动测试

```bash
uv run tests/n009_manual_test.py
```

## 测试说明

### N008 手动测试

验证长内容处理功能的三种场景：

- **测试1**：发送短消息（低于阈值），预期不生成文件
- **测试2**：发送长消息（高于阈值），启用文件模式，预期生成文件并发送文件消息
- **测试3**：发送长消息（高于阈值），禁用文件模式，预期截断不生成文件

**预期结果**：
- 收到 3 条飞书消息
- 第一条：短消息卡片，内容完整，无文件
- 第二条：长消息卡片（截断显示）+ 文件消息
- 第三条：长消息卡片（截断显示），无文件

### N009 手动测试

验证 PermissionRequest 卡片的三种格式：

- **测试1**：Bash 交互请求卡片
  - 显示 JSON 格式命令
  - 显示 3 个选项：yes / always / no

- **测试2**：AskUserQuestion 单选卡片
  - 显示问题
  - 显示编号选项
  - 标识为 (单选)

- **测试3**：AskUserQuestion 多选卡片
  - 显示问题
  - 显示编号选项
  - 标识为 (多选)

**预期结果**：
- 收到 3 条橙色"交互请求"卡片
- 卡片标题和内容符合预期
- 消息编号连续且格式正确

## 手动验证

测试运行后，请到飞书中手动验证：

1. 消息数量是否正确（N008: 3条，N009: 3条）
2. 卡片标题是否正确
3. 卡片内容格式是否符合预期
4. 消息编号是否连续
5. N008 测试2的文件消息是否包含完整内容
6. N008 测试3的内容是否截断且无文件

## 关于 test_hook_interaction_scenarios.py

`test_hook_interaction_scenarios.py` 是一个 **Hook 交互场景测试脚本**，用于：

1. **目的**：配置到 `~/.claude/settings.json` 中作为 hook 脚本，用于记录和分析 Claude Code 的各种 hook 事件结构

2. **测试场景**：
   - 权限确认场景
   - 选项选择场景（单选/多选）
   - Yes/No 确认场景
   - Escape 选项测试

3. **使用方式**：
   ```bash
   # 配置到 ~/.claude/settings.json
   {
     "hooks": {
       "UserPromptSubmit": "/path/to/test_hook_interaction_scenarios.py",
       "Stop": "/path/to/test_hook_interaction_scenarios.py",
       "Notification": "/path/to/test_hook_interaction_scenarios.py"
     }
   }
   ```

它与我们手动测试不同：
- 手动测试：独立运行的脚本，直接调用 Feishu API，需要人工验证结果
- `test_hook_interaction_scenarios.py`：Hook 代理脚本，被 Claude Code 调用，用于记录事件结构
