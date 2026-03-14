# WebSocket客户端接口

## 概述

WebSocket客户端接口定义了与飞书服务器建立WebSocket连接的所有功能，包括：
- 节点N1: WebSocket连接建立
- 节点N2: 自动重连机制（指数退避）
- 节点N3: 访问令牌获取和刷新

## 文件结构

```
src/interfaces/
└── websocket_client.py          # 接口定义和实现

tests/
└── test_websocket_client_v2.py  # 单元测试（主版本）
```

## 接口设计

### IWebSocketClient（接口）

```python
class IWebSocketClient(ABC):
    """WebSocket客户端接口"""

    @abstractmethod
    async def connect(self) -> bool:
        """建立WebSocket连接"""
        pass

    @abstractmethod
    async def disconnect(self) -> bool:
        """断开WebSocket连接"""
        pass

    @abstractmethod
    async def send_message(self, message: Dict[str, Any]) -> bool:
        """发送消息"""
        pass

    @abstractmethod
    def register_handler(self, event_type: EventType, handler: Callable[[WebSocketEvent], None]):
        """注册事件处理器"""
        pass

    @abstractmethod
    def unregister_handler(self, event_type: EventType, handler: Callable[[WebSocketEvent], None]):
        """注销事件处理器"""
        pass

    @abstractmethod
    def get_status(self) -> WebSocketStatus:
        """获取连接状态"""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """检查是否已连接"""
        pass
```

### 核心类

#### MockWebSocketClient
- 用于测试的模拟WebSocket客户端
- 不依赖真实WebSocket库
- 提供模拟消息发送和接收功能
- 支持模拟连接断开和错误

#### WebSocketClient
- 真实WebSocket客户端实现
- 使用`websockets`库建立连接
- 实现自动重连机制
- 支持访问令牌管理

### 枚举和事件

#### WebSocketStatus
- `DISCONNECTED` - 未连接
- `CONNECTING` - 正在连接
- `CONNECTED` - 已连接
- `RECONNECTING` - 正在重连
- `FAILED` - 连接失败

#### EventType
- `MESSAGE` - 消息事件
- `ERROR` - 错误事件
- `CONNECT` - 连接成功事件
- `DISCONNECT` - 断开连接事件
- `RECONNECT` - 重连事件

#### WebSocketEvent
```python
class WebSocketEvent:
    def __init__(self, event_type: EventType, data: Any, timestamp: Optional[datetime] = None)
```

## 关键特性

### 1. 自动重连机制
- 使用指数退避算法
- 最大延迟限制（默认60秒）
- 最大重连次数限制（默认10次）

### 2. 访问令牌管理
- 自动获取访问令牌
- 自动检测令牌过期
- 过期后自动刷新

### 3. 事件驱动架构
- 支持多种事件类型
- 灵活的事件处理器注册
- 支持同步和异步事件处理器

### 4. 异常处理
- 连接丢失自动恢复
- 网络错误重试
- 事件处理器错误隔离

## 测试覆盖率

单元测试覆盖以下场景：

### MockWebSocketClient测试
- [x] 连接和断开操作
- [x] 消息发送和接收
- [x] 事件处理器注册和注销
- [x] 模拟消息功能
- [x] 连接状态转换

### WebSocketClient测试
- [x] 令牌获取和刷新
- [x] 指数退避计算
- [x] 重连机制
- [x] 初始状态检查

### 集成测试
- [x] 完整连接生命周期
- [x] 多事件处理器
- [x] 消息队列顺序
- [x] 错误处理

## 使用示例

```python
from src.interfaces.websocket_client import MockWebSocketClient, EventType, WebSocketEvent

# 创建客户端
client = MockWebSocketClient("test_client")

# 定义事件处理器
def on_message(event: WebSocketEvent):
    print(f"Received message: {event.data}")

# 注册处理器
client.register_handler(EventType.MESSAGE, on_message)

# 连接客户端
await client.connect()

# 发送消息
await client.send_message({"type": "hello", "data": "world"})

# 模拟接收响应
client.simulate_message({"type": "response", "data": "hello!"})

# 等待事件处理
await asyncio.sleep(0.2)

# 断开连接
await client.disconnect()
```

## 依赖

### 开发依赖
- `pytest` - 测试框架
- `pytest-asyncio` - 异步测试支持
- `websockets` - WebSocket库（可选，用于生产环境）

### 运行测试
```bash
# 安装依赖
pip install -r requirements-tests.txt

# 运行所有测试
pytest tests/test_websocket_client_v2.py -v

# 运行特定测试
pytest tests/test_websocket_client_v2.py::MockWebSocketClientTestCase::test_connect_disconnect -v
```

## 架构说明

### Node N1: WebSocket连接建立
1. 调用`connect()`方法
2. 首先获取访问令牌
3. 建立WebSocket连接
4. 启动消息接收协程
5. 启动心跳检测协程
6. 发送连接成功事件

### Node N2: 自动重连机制
1. 检测连接丢失
2. 发送断开事件
3. 开始重连计数
4. 计算重连延迟（指数退避）
5. 发送重连事件
6. 尝试重新连接
7. 达到最大次数后标记为失败

### Node N3: 访问令牌获取
1. 初始化时自动获取令牌
2. 每次接收消息前检查令牌是否过期
3. 如果过期则自动刷新
4. 刷新失败时触发重连