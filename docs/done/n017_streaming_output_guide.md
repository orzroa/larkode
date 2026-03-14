# 流式输出功能使用说明

## 功能概述

流式输出功能实现了类似 ChatGPT 的"打字机效果"，让用户能够实时看到 AI 的输出过程，而不是等待任务完成后一次性显示结果。

## 核心组件

### 1. StreamingOutputManager

**文件**: `src/streaming_output.py`

负责管理流式输出的完整生命周期：
- 创建可更新的卡片实体（使用 CardKit API）
- 管理流式输出状态
- 协调卡片更新（带节流功能）
- 处理错误和降级策略

**主要方法**:
```python
# 开始流式输出
card_id = await manager.start_streaming(user_id, "正在处理...")

# 更新卡片内容（带节流）
await manager.update_content(card_id, "部分输出内容...")

# 完成流式输出
await manager.finish_streaming(card_id, "最终完整内容")

# 错误处理
await manager.handle_error(card_id, "错误信息")
```

### 2. TmuxSessionManager.monitor_output()

**文件**: `src/ai_executor/tmux_session.py`

监控 tmux 输出并实时回调：
- 使用 `tmux capture-pane` 捕获输出
- 清理 ANSI 控制字符
- 检测输出完成条件（稳定阈值）
- 通过回调函数实时报告进度

**参数**:
- `callback`: 回调函数 `(accumulated_content: str, is_last: bool) -> None`
- `poll_interval`: 轮询间隔（秒），默认 0.5
- `timeout`: 超时时间（秒），默认 300
- `stable_threshold`: 输出稳定阈值，默认 2

### 3. TmuxAIExecutor 集成

**文件**: `src/ai_executor/__init__.py`

支持流式输出参数：
```python
async def execute_command(
    self,
    command: str,
    workspace: Optional[Path] = None,
    streaming: bool = False,
    streaming_manager = None,
    user_id: Optional[str] = None
) -> AsyncGenerator[str, None]:
```

### 4. Hook 协调机制

**文件**: `src/hook_handler.py`

检测流式输出模式，避免重复发送：
- 检测环境变量 `LARKODE_STREAMING_MODE`
- 如果处于流式输出模式，Hook 不发送消息
- 清理环境变量

## 配置说明

在 `src/config/settings.py` 中添加了以下配置：

```python
# 流式输出配置
STREAMING_OUTPUT_ENABLED: bool = Field(
    default=True,
    description="是否启用流式输出"
)
STREAMING_POLL_INTERVAL: float = Field(
    default=0.5,
    description="流式输出轮询间隔（秒）"
)
STREAMING_TIMEOUT: int = Field(
    default=300,
    description="流式输出超时时间（秒）"
)
STREAMING_STABLE_THRESHOLD: int = Field(
    default=2,
    description="输出稳定阈值（连续多少次不变认为完成）"
)
```

可以通过 `.env` 文件配置：
```bash
STREAMING_OUTPUT_ENABLED=true
STREAMING_POLL_INTERVAL=0.5
STREAMING_TIMEOUT=300
STREAMING_STABLE_THRESHOLD=2
```

## 工作流程

### 正常流程

1. **用户发送消息**
   - 用户在飞书中发送消息
   - 消息通过 WebSocket 推送到服务器

2. **创建卡片实体**
   - `StreamingOutputManager.start_streaming()` 创建卡片
   - 返回 `card_id`
   - 用户立即看到"正在处理..."

3. **发送命令到 AI**
   - 命令发送到 tmux session
   - 开始监控输出

4. **实时更新卡片**
   - 每 0.5 秒捕获 tmux 输出
   - 清理 ANSI 控制字符
   - 更新卡片内容（带节流）

5. **检测完成**
   - 输出连续 2 次不变
   - 或检测到 shell 提示符
   - 或超时

6. **完成流式输出**
   - 发送最终内容
   - 设置环境变量 `LARKODE_STREAMING_MODE`
   - 清理资源

7. **Hook 处理**
   - Hook 检测到环境变量
   - 跳过发送消息（已通过流式输出显示）
   - 清理环境变量

### 降级策略

如果出现以下情况，会自动降级到传统模式：

1. **卡片创建失败**
   - CardKit API 调用失败
   - 返回 `None`
   - 使用传统一次性发送

2. **配置不完整**
   - 飞书配置缺失
   - `STREAMING_OUTPUT_ENABLED=false`
   - 使用传统模式

3. **更新失败**
   - 卡片更新失败
   - 记录日志
   - 继续尝试
   - 最终由 Hook 兜底

## 测试验证

### 单元测试

运行流式输出单元测试：
```bash
uv run pytest tests/test_streaming_output.py -v
```

测试覆盖：
- StreamingOutputManager 创建和更新卡片
- 节流机制正确性
- Sequence 递增正确性
- 错误处理和降级

### 手动测试

1. **启动服务**
   ```bash
   ./start.sh
   ```

2. **在飞书中发送消息**
   ```
   写一个 1000 字的故事
   ```

3. **观察现象**
   - 应该立即收到"正在处理..."卡片
   - 卡片内容每 0.5 秒更新一次
   - 完成后显示完整内容
   - 没有重复消息

### 性能测试

监控指标：
- API 调用频率（节流是否生效）
- 长时间输出（10000+ 字）的稳定性
- 并发用户场景

## 故障排查

### 问题 1: 卡片内容不更新

**可能原因**:
- CardKit API 调用失败
- sequence 递增错误
- 网络问题

**排查步骤**:
1. 检查日志：`tail -f logs/app.log`
2. 验证飞书配置：`FEISHU_APP_ID`, `FEISHU_APP_SECRET`
3. 检查 CardKit API 返回值

### 问题 2: Hook 重复发送消息

**可能原因**:
- 环境变量未设置
- Hook 未检测到流式模式

**排查步骤**:
1. 检查环境变量：`echo $LARKODE_STREAMING_MODE`
2. 查看 Hook 日志：`tail -f logs/hook_events.log`
3. 验证 `hook_handler.py` 的流式检测逻辑

### 问题 3: 输出检测不准确

**可能原因**:
- tmux 输出捕获不完整
- 稳定阈值设置不当

**调整配置**:
```bash
# 增加轮询间隔
STREAMING_POLL_INTERVAL=1.0

# 增加稳定阈值
STREAMING_STABLE_THRESHOLD=3

# 延长超时时间
STREAMING_TIMEOUT=600
```

## 未来改进

1. **更智能的输出检测**
   - 使用 AI 判断输出是否完成
   - 检测特定标记（如 `done`, `completed`）

2. **进度指示**
   - 显示"正在思考..."
   - 显示"正在生成..."
   - 显示进度百分比

3. **取消功能**
   - 支持用户取消正在进行的任务
   - 停止 tmux 监控
   - 清理资源

4. **多卡片支持**
   - 长输出自动分多个卡片
   - 每个卡片显示部分内容
   - 优化用户体验

## 总结

流式输出功能显著提升了用户体验，让用户能够实时看到 AI 的输出过程。通过合理的降级策略和错误处理，确保了功能的稳定性和可靠性。