"""
接口定义包

包含所有抽象接口定义
"""
from src.interfaces.websocket_client import (
    IWebSocketClient,
    WebSocketClient,
    MockWebSocketClient,
    WebSocketStatus,
    EventType,
    WebSocketEvent,
)
from src.interfaces.tmux_executor import (
    TmuxExecutorInterface,
    TmuxExecutor,
    MockTmuxExecutor,
    TmuxExecutorConfig,
    TmuxExecutorManager,
    TmuxOperationError,
)
from src.interfaces.im_platform import (
    IIMPlatform,
    IIMCardBuilder,
    MessageType,
    NormalizedMessage,
    NormalizedUser,
    NormalizedCard,
    PlatformConfig,
)
from src.interfaces.ai_assistant import (
    IAIAssistantInterface,
    ISessionManager,
    IAIAssistantExecutor,
    AssistantType,
    SessionStatus,
    AssistantConfig,
    SessionInfo,
)
from src.interfaces.hook_handler import (
    IHookHandler,
    ClaudeHookHandler,
    IFlowHookHandler,
    HookEventType,
    HookContext,
    detect_handler,
)

__all__ = [
    # WebSocket
    "IWebSocketClient",
    "WebSocketClient",
    "MockWebSocketClient",
    "WebSocketStatus",
    "EventType",
    "WebSocketEvent",
    # Tmux Executor
    "TmuxExecutorInterface",
    "TmuxExecutor",
    "MockTmuxExecutor",
    "TmuxExecutorConfig",
    "TmuxExecutorManager",
    "TmuxOperationError",
    # IM Platform
    "IIMPlatform",
    "IIMCardBuilder",
    "MessageType",
    "NormalizedMessage",
    "NormalizedUser",
    "NormalizedCard",
    "PlatformConfig",
    # AI Assistant
    "IAIAssistantInterface",
    "ISessionManager",
    "IAIAssistantExecutor",
    "AssistantType",
    "SessionStatus",
    "AssistantConfig",
    "SessionInfo",
    # Hook Handler
    "IHookHandler",
    "ClaudeHookHandler",
    "IFlowHookHandler",
    "HookEventType",
    "HookContext",
    "detect_handler",
]
