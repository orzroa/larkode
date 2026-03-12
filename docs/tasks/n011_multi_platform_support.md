# N011: 多 IM 平台接入与广播模式

## 任务概述

实现多 IM 平台并发接入与广播模式，支持同时接入飞书、Slack、钉钉等多个平台，并提供统一的消息广播和路由机制。

## 背景分析

### 核心需求
- **多平台并发接入**：服务同时接入多个 IM 平台（飞书、Slack、钉钉等）
- **消息快速转发**：IM 层收到消息后立即抛给 AI 处理，不等待其他平台
- **AI 助手单一实例**：只有一个 AI 助手实例，按顺序处理来自多个平台的消息
- **响应广播**：AI 响应需要发送给所有接入的 IM 平台

### 设计决策

#### 发送策略分层
| 模式 | 复杂度 | 发送策略 | 适用场景 |
|------|---------|---------|---------|
| Hooks 类 | 低（宽松） | 配置什么就发什么（静态配置） | hook_handler.py 通知 |
| WebSocket 类 | 高（需要管理） | 现在接入哪些就发哪些（动态接入） | 实时消息接收 |

## 实现内容

### 1. MultiPlatformManager
**文件**: `src/im_platforms/multi_platform_manager.py`

**功能**:
- 管理多个 IM 平台的注册和连接状态
- 区分已注册平台和已连接平台
- 提供广播方法（消息、卡片）
- 提供定向发送方法（指定平台）

**关键方法**:
```python
register_platform(name, platform)          # 注册平台
get_connected_platforms()                # 获取已连接平台
broadcast_message(user_id, content)      # 广播消息
send_to_platform(platform_name, ...)     # 定向发送
```

### 2. NotificationSender 抽象层
**文件**: `src/im_platforms/notification_sender.py`

**类层次**:
- `INotificationSender` - 抽象基类
- `StaticNotificationSender` - 静态配置模式（Hooks）
- `DynamicBroadcastSender` - 动态广播模式（WebSocket）
- `PlatformTargetedSender` - 平台定向发送
- `MultiPlatformTargetedSender` - 多平台定向发送

### 3. 多平台配置支持
**文件**: `config/settings.py`, `.env.example`

**新增配置**:
```bash
# 多平台配置（逗号分隔）
ENABLED_IM_PLATFORMS=feishu,slack

# 各平台开关
FEISHU_ENABLED=true
SLACK_ENABLED=true
DINGTALK_ENABLED=false
```

**新增方法**:
```python
get_enabled_platforms()         # 获取启用的平台列表
is_platform_enabled(name)        # 检查平台是否启用
get_platform_config(name)        # 获取平台配置
```

### 4. MessageHandler 更新
**文件**: `src/message_handler.py`

**新增功能**:
- 接受 `MultiPlatformManager` 和 `NotificationSender` 参数
- 跟踪消息来源平台
- 统一发送接口 `_send_via_sender`
- 任务元数据中存储来源平台

### 5. main.py 多平台初始化
**文件**: `main.py`

**新增功能**:
- 初始化 `MultiPlatformManager` 实例（全局可用）
- 动态加载启用的平台
- 为每个平台启动 WebSocket 客户端
- 管理多个平台的连接状态

### 6. Slack 平台存根
**文件**: `src/im_platforms/slack/__init__.py`

**实现内容**:
- `SlackPlatform` - 实现所有 `IIMPlatform` 接口（存根）
- `SlackCardBuilder` - 实现卡片格式转换（存根）
- `register_slack_platform()` - 注册函数

**TODO**: 实际集成 Slack Bolt SDK

## 架构流程

```
┌─────────────────────────────────────────────────────┐
│            多平台管理层                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐     │
│  │  飞书   │  │  Slack  │  │  钉钉   │     │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘     │
│       │             │             │              │
└───────┼─────────────┼─────────────┼──────────────┘
        │             │             │
        └─────────────┼─────────────┘
                      ↓
            MessageHandler
            (跟踪来源平台)
                      ↓
            TaskManager
            (存储平台信息)
                      ↓
            AI Assistant
            (单一实例，顺序处理)
                      ↓
            NotificationSender
            (广播/定向)
                      ↓
         MultiPlatformManager
            (分发到各平台)
                      ↓
        ┌─────────────┼─────────────┐
        ↓             ↓             ↓
      飞书          Slack        钉钉
```


- 默认配置仍使用单平台（飞书）模式
- 保持原有 API 不变
- 新增参数均为可选
- 平台注册失败不影响其他平台

## 测试建议

1. **单平台测试**：验证原有飞书功能不受影响
2. **多平台注册测试**：验证多个平台可同时注册
3. **广播测试**：验证消息可广播到多个平台
4. **连接状态测试**：验证平台上下线处理
5. **Slack 存根测试**：验证存根实现可用

## 后续工作

- [ ] 实现 Slack 平台完整功能
- [ ] 实现钉钉平台
- [ ] 平台会话隔离（防止上下文混合）
- [ ] 单元测试覆盖
- [ ] 文档更新

## 相关文件

- `src/im_platforms/multi_platform_manager.py`
- `src/im_platforms/notification_sender.py`
- `src/im_platforms/slack/__init__.py`
- `config/settings.py`
- `.env.example`
- `src/message_handler.py`
- `main.py`
