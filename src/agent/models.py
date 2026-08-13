"""Agent 后端之间共享的领域模型。"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict


class AgentBackend(str, Enum):
    CLAUDE_CODE = "claude_code"
    CODEX = "codex"


class AgentEventKind(str, Enum):
    TURN_STARTED = "turn_started"
    TEXT_DELTA = "text_delta"
    STATUS = "status"
    APPROVAL_REQUIRED = "approval_required"
    USER_INPUT_REQUIRED = "user_input_required"
    TURN_COMPLETED = "turn_completed"
    TURN_CANCELLED = "turn_cancelled"
    ERROR = "error"


@dataclass(frozen=True)
class AgentCapabilities:
    streaming: bool = True
    cancellation: bool = True
    approvals: bool = False
    user_input: bool = False
    model_selection: bool = False
    session_resume: bool = False
    structured_tool_events: bool = False


@dataclass(frozen=True)
class AgentEvent:
    kind: AgentEventKind
    payload: Dict[str, Any] = field(default_factory=dict)
    event_id: str = ""
    occurred_at: datetime = field(default_factory=datetime.now)
