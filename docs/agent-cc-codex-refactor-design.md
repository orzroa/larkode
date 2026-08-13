# CC / Codex Agent 适配重构与 iFlow 移除方案

> 状态：第一阶段已实现并完成安全/回归修复
> 日期：2026-08-12
> 范围：Agent 接入层、会话与交互、IM 路由、配置及 iFlow 清理

## 实施状态（2026-08-13）

第一阶段已落地：`AGENT_BACKEND=codex` 使用 App Server，Claude Code 继续使用 tmux；
`#model` / `#think` 使用进程内偏好，默认值仍由 `.env` 提供；完成、失败、取消、审批和
选择结果统一经 `CardDispatcher` 发送。飞书 SDK 回调统一投递到服务主事件循环，避免跨
loop 使用 App Server 的进程、Queue 和 Future。

安全基线同步收紧：SDK HTTP 日志不再输出 DEBUG 授权头；Larkode 明确采用单用户模型，
`FEISHU_ALLOWED_USER_ID` 只接受一个控制者且拒绝 `*`/多 ID，空值回退到
`FEISHU_HOOK_NOTIFICATION_USER_ID`，两者均为空时默认拒绝控制请求。旧变量名
`FEISHU_ALLOWED_USER_IDS` 仅保留单值迁移兼容。

终审加固同时完成：飞书入站消息通过数据库原子认领实现幂等；Codex 审批与 App Server
连接代次绑定，断线后旧审批卡不能回复新请求；Codex 子进程使用显式环境白名单；未知
`#` 命令安全拒绝；日志、数据库、上传目录和 `.env` 使用 `0700/0600` 私有权限。入站
附件采用流式限额下载并对远端文件标识取摘要，默认单文件上限为 50 MiB。

## 1. 背景与目标

Larkode 的定位是“通过手机 IM 遥控桌面 Agent”。当前代码已经具备 AI Assistant 接口、工厂、多 IM 平台接口和统一卡片等通用化基础，但运行链路仍明显绑定 Claude Code：

- `TaskManager` 曾始终创建 `DEFAULT` 助手并读取 `CLAUDE_CODE_CLI_PATH`，无法按配置选择后端。
- `TmuxSessionManager`、`WorkspaceManager`、`AISessionManager` 分别依赖 Claude/iFlow 进程名、`cc-` 会话前缀和 `~/.claude/projects`。
- 流式输出依赖 tmux 截屏，并以“连续 N 次屏幕不变”推断完成，容易在等待审批、长时间思考和静默工具调用时误判。
- Hook 入口直接构建并发送飞书卡片，Agent 事件与 IM 实现耦合。
- `#cancel`、`#model`、帮助文案等平台命令直接操作 tmux/CCR 或写死 Claude Code。
- IM 虽已标准化收发接口，但命令链路没有完整保留 `platform/chat/message` 回复目标，广播时还隐含假设不同平台共享同一个 `user_id`。
- iFlow 代码散落在配置、Hook、tmux 执行器、测试和文档中。

本次重构目标：

1. 正式支持 `claude_code` 和 `codex` 两种 Agent 后端，启动时选择一个后端。
2. Agent 差异收敛在适配器内部，核心业务和 IM 层不出现 Claude/Codex 条件分支。
3. 将输出、完成、错误、审批、用户选择、工具状态统一成可路由的领域事件。
4. Codex 使用结构化协议获得可靠的流式输出、线程恢复、取消和审批能力。
5. 完整移除 iFlow 的运行时代码、配置、测试和用户文档。
6. 保持当前“一个工作空间一段 Agent 上下文”的用户体验；暂不引入运行时多 Agent 并发切换。

## 2. 非目标

- 本次不实现 Slack、钉钉的完整产品能力，只保证核心层不再写死飞书。
- 本次不提供 `#agent` 热切换；`AGENT_BACKEND` 在进程启动时确定。
- 本次不把 Claude Code 强行改造成与 Codex 完全相同的传输协议。
- 本次不同时运行多个用户在同一工作空间的并发 Agent turn；并发请求按 session 串行化。
- 本次不迁移到云端 Agent，也不绕过 Claude Code/Codex 自身的认证、沙箱和审批策略。

## 3. 核心设计决策

### 3.1 公共的是领域协议，不是终端操作

不再让 `TmuxAIExecutor` 充当所有 Agent 的公共基类。公共层只定义“提交任务、接收事件、回复交互、取消任务、管理会话”；如何启动进程和读取输出由各适配器决定。

- Claude Code：保留交互式 CLI + tmux，Hook 作为结构化事件补充。
- Codex：使用 `codex app-server` 的 stdio JSONL 双向 JSON-RPC。
- tmux 是 Claude 适配器的实现细节，不再出现在 `PlatformCommands`、`WorkspaceManager` 或通用接口中。

不建议将 Codex 正式接入建立在 TUI 截屏上。官方 App Server 面向富客户端，提供 `thread/start`、`thread/resume`、`turn/start`、事件流、服务端审批请求和 `turn/interrupt`，与本项目的手机遥控场景直接匹配。`codex exec --json` 可用于诊断或降级验证，但每个 turn 启动一个进程、审批回传困难，不作为主路径。

### 3.2 Agent 到 IM 只传标准事件

Agent 适配器不得调用飞书 API、构建飞书卡片或依赖某个平台的用户 ID。适配器输出 `AgentEvent`，应用层将事件转换为 `OutboundMessage`，最后由 IM 平台渲染。

### 3.3 会话身份显式持久化

不再从 `cc-xxx` tmux 名反推工作空间，也不扫描某个厂商目录猜测当前 session。应用维护自己的 session registry：

```text
SessionKey = backend + canonical_workspace
```

初期保持每个 `backend + workspace` 一个会话。表中显式记录 Claude session id / Codex thread id、进程或 tmux 标识、最后回复目标和状态。

### 3.4 权限与用户选择是请求-响应协议

审批不是一条普通通知。每个请求必须有稳定的 `interaction_id`，状态必须经历：

```text
pending -> answered | expired | cancelled
```

IM 卡片回调通过 `interaction_id` 找到 Agent session，再由对应适配器回复。禁止用“最后一个交互文件”关联请求，否则并发或重复回调会串线。

### 3.5 默认回复来源会话，不默认跨平台广播

每条入站消息保留 `ReplyTarget(platform, conversation_id, user_id, message_id)`。普通输出和交互回复发送到来源目标；只有明确的系统通知才广播。

如果以后需要跨平台广播，应先建立 Larkode 用户与各平台身份的映射，不能把飞书 `open_id` 直接用于 Slack/钉钉。

## 4. 目标架构

```text
Feishu / Slack / ...
        │
        ▼
IM Adapter ──> InboundEnvelope + ReplyTarget
        │
        ▼
CommandRouter ──> 系统命令 / AgentRequest
        │
        ▼
AgentRuntime ──> SessionRegistry / InteractionStore / per-session lock
        │
        ├──────── ClaudeCodeAdapter
        │           ├─ Claude CLI in tmux
        │           └─ HookBridge (local RPC)
        │
        └──────── CodexAdapter
                    └─ codex app-server (stdio JSON-RPC)
        │
        ▼
AgentEventBus ──> Presenter ──> OutboundMessage
        │                              │
        └──── interaction response <── IM card callback
```

建议模块布局：

```text
src/agent/
├── models.py                 # AgentRequest/Event/Session/Capability
├── interface.py              # AgentAdapter 协议
├── runtime.py                # 生命周期、并发、路由、重启
├── registry.py               # session/route 持久化
├── interactions.py           # pending interaction 状态机
├── factory.py
├── claude_code/
│   ├── adapter.py
│   ├── tmux_transport.py
│   ├── hook_parser.py
│   └── hook_bridge.py
└── codex/
    ├── adapter.py
    ├── app_server_client.py
    └── event_mapper.py

src/im/
├── models.py                 # InboundEnvelope/ReplyTarget/OutboundMessage
├── router.py
├── presenter.py
└── platforms/...
```

迁移期间可以保留旧 import alias，完成后再删除 `src/ai_assistants/default`、通用层里的 tmux 命名和 `ClaudeFeishuService` 等历史名称。

## 5. 公共 Agent 协议

### 5.1 数据模型

```python
class AgentBackend(str, Enum):
    CLAUDE_CODE = "claude_code"
    CODEX = "codex"

@dataclass(frozen=True)
class SessionKey:
    backend: AgentBackend
    workspace: Path

@dataclass(frozen=True)
class AgentRequest:
    request_id: str
    session_key: SessionKey
    prompt: str
    reply_target: ReplyTarget
    attachments: list[Attachment]

@dataclass(frozen=True)
class AgentEvent:
    event_id: str
    request_id: str
    session_key: SessionKey
    kind: AgentEventKind
    payload: dict
    occurred_at: datetime

class AgentEventKind(str, Enum):
    TURN_STARTED = "turn_started"
    TEXT_DELTA = "text_delta"
    STATUS = "status"
    TOOL_STARTED = "tool_started"
    TOOL_COMPLETED = "tool_completed"
    APPROVAL_REQUIRED = "approval_required"
    USER_INPUT_REQUIRED = "user_input_required"
    TURN_COMPLETED = "turn_completed"
    TURN_CANCELLED = "turn_cancelled"
    ERROR = "error"
```

所有事件都携带 `request_id` 和 `session_key`。`event_id` 用于 Hook 重试、IM 重试和进程恢复后的幂等去重。

### 5.2 接口

```python
class AgentAdapter(Protocol):
    backend: AgentBackend

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def submit(self, request: AgentRequest) -> AsyncIterator[AgentEvent]: ...
    async def cancel(self, session_key: SessionKey, request_id: str) -> bool: ...
    async def respond(self, interaction_id: str, decision: InteractionDecision) -> bool: ...
    async def list_models(self) -> list[ModelInfo]: ...
    async def health(self) -> AgentHealth: ...
    def capabilities(self) -> AgentCapabilities: ...
```

能力通过数据声明，不在业务层判断 `backend == ...`：

```python
AgentCapabilities(
    streaming=True,
    cancellation=True,
    approvals=True,
    user_input=True,
    model_selection=True,
    session_resume=True,
    structured_tool_events=True,
)
```

`#cancel` 调 `AgentRuntime.cancel()`；`#model` 仅在 `model_selection=True` 时展示。CCR 变成 Claude 适配器的模型提供者，Codex 则调用 App Server 的 `model/list`。

## 6. Codex 适配方案

### 6.1 进程模型

Larkode 启动一个受监管的 `codex app-server --listen stdio://` 子进程：

1. 建立 stdin/stdout JSONL 通道。
2. 发送一次 `initialize`，随后发送 `initialized`。
3. 为每个工作空间查找已持久化的 `thread_id`：存在则 `thread/resume`，否则 `thread/start`。
4. 收到手机指令后调用 `turn/start`。
5. 持续读取通知并映射为 `AgentEvent`。
6. 子进程崩溃时由 `AgentRuntime` 指数退避重启，然后按 registry 恢复 thread。

初期使用稳定 API，不开启 `experimentalApi`。WebSocket transport 当前属于实验能力，且本服务与 Codex 位于同一桌面，无需引入网络监听和额外鉴权面。

### 6.2 事件映射

| Codex App Server 消息 | Larkode 事件/动作 |
|---|---|
| `thread/started` 或 `thread/resume` 响应 | 更新 session registry |
| `turn/started` | `TURN_STARTED`，记录 `turn_id` |
| `item/agentMessage/delta` | `TEXT_DELTA`，更新流式卡片 |
| `item/started` / `item/completed` | 可见工具状态；默认不把原始命令输出刷到 IM |
| `turn/plan/updated` | 可选状态卡片，不混入最终回复正文 |
| `item/commandExecution/requestApproval` | `APPROVAL_REQUIRED` |
| `item/fileChange/requestApproval` | `APPROVAL_REQUIRED` |
| `tool/requestUserInput` | `USER_INPUT_REQUIRED` |
| `turn/completed` | `TURN_COMPLETED` / `TURN_CANCELLED` / `ERROR` |
| `error` / 进程退出 | `ERROR`，保留可重试状态 |

取消通过 `turn/interrupt(threadId, turnId)` 实现，不发送终端 ESC。

审批卡片只呈现服务端给出的可选决策。普通命令/文件审批映射 `accept`、`acceptForSession`、`decline`、`cancel`；网络审批需要以网络目标为中心展示，不能假设 `command` 一定是有意义的预览。默认不提供绕过沙箱的“一键永久允许”。

### 6.3 为什么不以 `codex exec` 为主路径

`codex exec --json` 能输出结构化 JSONL，也支持按 session id 恢复，适合 MVP 验证或批处理降级；但 App Server 更适合长驻手机客户端：

- 一个双向连接承载多个 thread/turn。
- 服务端审批请求可直接回传决定。
- 支持 turn 中断、steer、模型发现和更细粒度事件。
- 无需通过终端画面判断任务何时结束。

## 7. Claude Code 适配方案

第一阶段保留已验证的 tmux 运行方式，但把现有类收进 `ClaudeCodeAdapter`：

- `ClaudeTmuxTransport`：启动 CLI、发送 prompt、捕获兼容性输出、发送取消信号。
- `ClaudeHookParser`：解析 Claude Hook payload，映射为公共 `AgentEvent`。
- `ClaudeSessionLocator`：处理 `~/.claude/projects` 和 Claude session id，不进入通用 registry 逻辑。
- `ClaudeModelProvider`：封装 CCR；未配置 CCR 时声明 `model_selection=False`。

Hook 不再直接调用 `FeishuAPI`。新增本机 `HookBridge`：

```text
Claude Hook 子进程 -> Unix Domain Socket -> AgentRuntime -> IM
                                      ^             │
                                      └── 审批结果 ──┘
```

- `Stop`、`PostToolUseFailure` 等通知使用单向事件。
- `PermissionRequest`、`AskUserQuestion` 使用带超时的请求-响应 RPC；卡片选择通过同一个 `interaction_id` 返回 Hook 子进程。
- 守护进程不可用时，非阻塞通知写入 spool 文件；审批类事件应安全失败，不能默认放行。

在 Claude 适配器仍依赖 tmux 截屏期间，完成状态以 `Stop` Hook 为准，屏幕稳定只用于刷新节流，不再作为 turn 完成判据。

## 8. IM 与交互路由调整

### 8.1 入站信封

```python
@dataclass(frozen=True)
class ReplyTarget:
    platform: str
    conversation_id: str
    user_id: str
    message_id: str | None

@dataclass(frozen=True)
class InboundEnvelope:
    reply_target: ReplyTarget
    message_type: MessageType
    text: str
    attachments: list[Attachment]
    raw: dict
```

`EventParser -> CommandExecutor -> TaskManager` 全链路传递 envelope，不能只传 `user_id, command`。

### 8.2 出站模型

Presenter 将 `AgentEvent` 转成平台无关的：

- `TextMessage`
- `StreamingMessage(create/update/finish)`
- `ApprovalCard`
- `ChoiceCard`
- `StatusMessage`
- `FileMessage`

平台适配器负责能力降级。例如某 IM 不支持更新卡片时，以节流文本消息 + 最终消息替代。

### 8.3 交互关联

新增 `pending_interactions` 存储，至少包含：

```text
interaction_id, backend, session_key, request_id, external_request_id,
reply_target, kind, payload_json, status, expires_at, answered_at
```

IM 回调必须具备幂等性：第一次有效点击完成状态迁移，重复点击返回“已处理”，过期点击不再调用 Agent。

## 9. 会话与持久化

新增 `agent_sessions`：

```text
id, backend, workspace, external_session_id, transport_ref,
state, last_reply_target_json, created_at, updated_at, metadata_json
```

规则：

- `workspace` 存 canonical absolute path，并建立 `(backend, workspace)` 唯一索引。
- Codex 的 `external_session_id` 是 `thread_id`；Claude 是 Claude session id。
- `transport_ref` 对 Claude 可存 tmux session 名；Codex 不依赖 tmux。
- tmux 名使用 `larkode-claude-<slug>-<hash>`，仅作为传输标识，不承担数据库功能。
- 工作空间切换只更新当前路由绑定，不从 tmux 名反推路径。
- 每个 session 使用异步锁；同一 session 的新命令默认排队。后续若需要可增加 `turn/steer` 产品语义，但不能自动把所有并发消息都当 steer。

现有 `messages` 表后续补充 `platform`、`conversation_id`、`agent_backend`、`agent_session_id`、`request_id`。`feishu_message_id` 迁移为通用 `platform_message_id`，旧列保留一个兼容版本后再删除。

## 10. 配置方案

建议的新配置：

```dotenv
AGENT_BACKEND=claude_code

CLAUDE_CODE_CLI_PATH=claude
CLAUDE_CODE_HOOK_RPC_TIMEOUT=300
CLAUDE_CODE_CCR_ENABLED=true

CODEX_CLI_PATH=codex
CODEX_APPROVAL_POLICY=on-request
CODEX_SANDBOX=workspace-write
CODEX_MODEL=gpt-5.6-terra
CODEX_REASONING_EFFORT=medium
CODEX_REQUEST_TIMEOUT=30
CODEX_APPROVAL_TIMEOUT=300

AGENT_SESSION_IDLE_TIMEOUT=3600
AGENT_MAX_PENDING_COMMANDS=20
```

`CODEX_MODEL` 与 `CODEX_REASONING_EFFORT` 是服务启动时的默认值。飞书 `#model`、`#think`
菜单只更新当前 Larkode 进程的内存配置，不修改 `.env`；服务重启后重新读取上述默认值。

所有完成回复（Claude Hook 与 Codex App Server）通过 `CardDispatcher` 使用统一展示模板：

```text
[larkode] 回复完成
📨 卡片编号: 14974
🕒 2026-08-13T09:28:46.202294
正文...
```

其中首行是卡片标题，工作区名称由运行时自动替换；编号和 ISO 8601 时间戳由统一卡片层生成。
模型、Think、工作区等带按钮的交互卡片使用 `CardDispatcher.send_interactive_card()`，同样添加
工作区、卡片编号和时间戳，同时保留飞书按钮的回调数据。

### 10.1 飞书侧配置

本次接入不新增飞书自定义菜单，也不要求增加 `#codex` 命令。Agent 后端由服务端
`AGENT_BACKEND` 在启动时选择，用户仍直接发送消息。

Codex 审批卡片复用已有的长连接卡片回调，需要在飞书开放平台确认：

1. 应用已启用机器人能力，并能发送交互卡片。
2. “事件与回调”使用长连接接收事件。
3. 已订阅卡片回传事件 `card.action.trigger`（代码侧已注册
   `register_p2_card_action_trigger`）。
4. 新增或变更权限后，发布一个新的应用版本使配置生效。

如果现有工作空间切换、模型选择卡片已经可以点击并收到反馈，上述通道通常已经
配置完成，无需再次修改。审批等待超过 `CODEX_APPROVAL_TIMEOUT` 秒时默认拒绝。

### 10.2 当前实现进度（2026-08-12）

- 已实现 `AGENT_BACKEND=claude_code|codex` 工厂选择及生命周期管理。
- 已实现 Codex App Server 初始化、thread 创建/恢复、turn、文本 delta、取消和会话持久化。
- 已实现命令/文件审批飞书卡片，以及跨 WebSocket 线程的安全结果回传；超时或异常默认拒绝。
- 已用本机 Codex App Server 0.147.0 alpha 完成 initialize、thread/start、turn/start、delta 与完成事件冒烟；协议配置使用 kebab-case，并兼容早期 camelCase 配置值。
- 已删除 iFlow 运行时代码、配置、测试和专属文档。
- Claude 继续使用 tmux；Codex 主链路不使用 tmux。
- 待完成项：真实 Codex CLI/账号端到端冒烟、流式卡片增量更新、实验性
  `tool/requestUserInput` 的多问题表单，以及通用 `ReplyTarget/Presenter` 收口。

迁移策略：

- 仅使用 `AGENT_BACKEND` 配置后端；配置值仅允许 `claude_code` 或 `codex`。
- `claude_code` 仍可作为默认值，降低升级风险；Codex 稳定后再评估默认切换。
- 配置为 `iflow` 时启动直接失败并给出明确迁移错误，不静默回退 Claude。
- Agent 专有配置保持专有，不设计含义模糊的全局 `PERMISSION_MODE`。
- 启动时执行配置与 CLI 能力检查，错误信息包含缺失命令和修复建议。

## 11. iFlow 删除清单

### 11.1 运行时代码

- 删除 `IFlowHookHandler`、iFlow 环境探测和 `IFLOW_*` 环境变量采集。
- 删除 `Settings.iflow_cli`、`iflow_dir`、`iflow_hook_script` 及 `get_hook_script/get_process_name` 中的 iFlow 分支。
- 删除 `TmuxSessionManager` 中 iFlow CLI 选择分支。
- `AgentBackend` 不保留 `iflow` 枚举或兼容 alias。

### 11.2 测试和样例

- 删除 iFlow 专属单测、fixture 和 `.iflow` 配置示例。
- 把原来同时验证 Claude/iFlow 的参数化测试改为验证 Claude/Codex adapter contract。
- 删除 `docs/3rd/iflow_hooks.md` 和 `docs/done/n012_iflow_hooks_support.md`；历史仍可从 Git 获取，当前文档树不再宣传已移除能力。

### 11.3 用户文档

- README 中“Claude Code、iFlow”改为“Claude Code、Codex”。
- 安装、配置、FAQ、中英文说明都删除 iFlow。
- `CLAUDE.md` 更新为 Agent-neutral 架构说明，并补充 Codex 开发说明。
- 服务类、日志标题、帮助文案从 `ClaudeFeishuService` / “Claude 命令”改为 Larkode / Agent 中性名称。

验收时运行：

```bash
rg -n -i 'iflow' . --glob '!.git/**'
```

结果应为空；如保留迁移错误文案，需作为唯一白名单并注明删除日期。

## 12. 分阶段实施

### 阶段 0：行为锁定

- 为当前消息进入、工作空间切换、Claude 命令发送、Stop Hook、审批、取消和流式卡片补充特征测试。
- 建立 Agent adapter contract tests，所有后端必须通过相同的核心行为用例。
- 记录当前数据库 schema 和配置升级用例。

### 阶段 1：公共领域层与路由

- 引入 `AgentRequest`、`AgentEvent`、`ReplyTarget`、capability 和 session registry。
- `TaskManager` 改为 `AgentRuntime`，由工厂根据 `AGENT_BACKEND` 创建 adapter。
- 系统命令改调 runtime/capability，不再直接调用 tmux 或 CCR。
- 先用 Claude adapter 包装现有实现，确保用户行为不变。

### 阶段 2：Codex App Server 适配器

- 实现子进程监管、JSON-RPC request id 关联、初始化和健康检查。
- 实现 thread start/resume、turn start、delta、完成、错误和 interrupt。
- 实现模型列表及审批/用户输入回传。
- 增加协议录制 fixture，单测不依赖真实 Codex 账号。

### 阶段 3：Hook 与交互统一

- 引入 HookBridge 和 `pending_interactions`。
- Claude Hook 去除飞书依赖，Codex 直接使用 App Server server request。
- IM 卡片回调统一进入 `AgentRuntime.respond()`。
- 增加重试、重复点击、超时、服务重启恢复测试。

### 阶段 4：移除 iFlow 与历史耦合

- 按删除清单清理代码、测试、配置和文档。
- 重命名 `ClaudeFeishuService`、`cc-` 通用会话规则和通用层 Claude 文案。
- 更新 README、`.env.example`、部署脚本和依赖检查。
- 保留一版旧配置迁移提示，不保留 iFlow 运行能力。

### 阶段 5：收口与灰度

- Claude Code 跑完整回归后，分别以 `AGENT_BACKEND=claude_code/codex` 做真实端到端测试。
- 先在单用户、单工作空间运行 Codex，观察进程重启、thread 恢复和审批成功率。
- 指标稳定后删除旧接口 alias 和旧数据库列。

## 13. 测试矩阵

| 场景 | Claude Code | Codex | IM fake | 真实飞书 |
|---|---:|---:|---:|---:|
| 新工作空间创建会话 | 必测 | 必测 | 必测 | 冒烟 |
| 已有会话恢复 | 必测 | 必测 | 必测 | 冒烟 |
| 文本流式输出与最终完成 | 必测 | 必测 | 必测 | 必测 |
| 同 session 请求串行 | 必测 | 必测 | 必测 | 冒烟 |
| 取消运行中 turn | 必测 | 必测 | 必测 | 必测 |
| 命令/文件审批允许与拒绝 | 必测 | 必测 | 必测 | 必测 |
| 用户选择、超时、重复点击 | 必测 | 必测 | 必测 | 必测 |
| Agent 进程崩溃与恢复 | 必测 | 必测 | 必测 | 冒烟 |
| IM 不支持流式更新时降级 | N/A | N/A | 必测 | N/A |
| iFlow 配置迁移错误 | 必测 | 必测 | N/A | N/A |

Codex 单测使用输入/输出 JSONL fixture 覆盖乱序响应、未知通知、部分 delta、审批期间取消、App Server 崩溃。真实 Codex E2E 单独标记，默认测试集不得依赖账号或网络。

## 14. 可观测性与安全

建议为日志统一加入：

```text
request_id, interaction_id, backend, workspace_hash,
external_session_id, turn_id, platform, conversation_id, event_kind
```

关键指标：turn 数、完成/失败/取消数、首 token 延迟、总耗时、审批等待时长、IM 更新失败率、Agent 重启次数、session 恢复失败数。

安全要求：

- 日志不记录 API key、完整环境变量或认证 payload。
- HookBridge 只监听本机 Unix socket，文件权限限制为当前用户。
- Codex 默认 `workspace-write + on-request`，不在产品配置中默认启用危险绕过参数。
- 审批决定必须校验 interaction 所属用户/会话及过期时间。
- App Server stdout 仅作为协议流解析；stderr 单独限长记录，异常 JSON 不得导致主服务退出。

## 15. 完成标准

- `AGENT_BACKEND=claude_code` 与 `codex` 均能完成：发送任务、流式回复、会话恢复、审批、用户选择和取消。
- 核心业务、IM 层和系统命令中不存在 Claude/Codex 类型判断；差异仅位于 adapter 或 capability provider。
- Codex 正常链路不依赖 tmux 截屏，不以输出稳定时间推断完成。
- Hook 代码不直接 import 飞书实现。
- 普通回复准确返回来源 `ReplyTarget`，不会错误广播到其他平台身份。
- 同一 session 无并发 turn 串线，交互回调可幂等处理。
- iFlow 运行能力和用户文档完全移除，旧配置得到明确报错。
- 单元测试、协议 fixture 测试、Claude/Codex E2E 和配置迁移测试全部通过。

## 16. 官方能力依据

- [Codex App Server](https://learn.chatgpt.com/docs/app-server)：JSON-RPC/JSONL transport、thread/turn 生命周期、流式事件、审批、取消与模型发现。
- [Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode)：`codex exec --json`、session resume 和自动化权限模型，作为诊断/降级参考。
- [Codex Hooks](https://learn.chatgpt.com/docs/hooks)：Hook 生命周期、配置位置与信任机制；Codex 主链路仍以 App Server 事件为准，避免 Hook 与协议事件重复发送。
