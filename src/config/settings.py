"""
Pydantic Settings 配置管理

使用 pydantic-settings 提供类型安全的配置管理。
"""
import os
from pathlib import Path
from typing import Any, List, Optional
from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 使用模块常量，避免 Pydantic 将类内下划线属性视为私有字段。
ENV_FILE = Path(__file__).parent.parent.parent / ".env"


class Settings(BaseSettings):
    """应用配置 - 使用 Pydantic Settings"""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        populate_by_name=True,
        extra="ignore",  # 忽略额外的环境变量
    )

    # ==================== 平台配置 ====================
    im_platform: str = Field(default="feishu", description="IM 平台类型")
    agent_backend: str = Field(default="claude_code", description="Agent 后端（claude_code 或 codex）")
    enabled_im_platforms: str = Field(default="feishu", description="启用的 IM 平台列表")

    # ==================== 飞书配置 ====================
    feishu_app_id: str = Field(default="", description="飞书应用 ID")
    feishu_app_secret: str = Field(default="", description="飞书应用密钥")
    feishu_enabled: bool = Field(default=True, description="是否启用飞书")
    feishu_message_receive_id_type: str = Field(default="open_id", description="消息接收 ID 类型")
    feishu_message_domain: str = Field(default="FEISHU_DOMAIN", description="飞书 API 域名")
    feishu_allowed_user_id: str = Field(
        default="",
        validation_alias=AliasChoices(
            "FEISHU_ALLOWED_USER_ID",
            "FEISHU_ALLOWED_USER_IDS",  # 旧配置名，仅用于单值迁移兼容
        ),
        description="唯一允许控制 Agent 的飞书用户 ID；空值回退到 Hook 通知用户",
    )

    # ==================== 通用 AI 配置 ====================
    tmux_session_name: str = Field(
        default="cc",
        description="[已废弃] tmux 会话名称（现在根据工作空间动态生成）",
        deprecated=True
    )
    session_max_age_minutes: int = Field(default=30, description="Session 最大未更新时间（分钟）")

    # ==================== Claude Code 配置 ====================
    claude_code_log_file: Path = Field(default=Path(""), description="Claude Code 日志文件路径")
    claude_code_cli_path: str = Field(default="", description="Claude Code CLI 路径")
    claude_code_session_id: str = Field(default="", description="Claude Code 会话 ID")

    # ==================== Codex 配置 ====================
    codex_cli_path: str = Field(default="codex", description="Codex CLI 路径")
    codex_model: str = Field(default="gpt-5.6-terra", description="Codex 模型")
    codex_reasoning_effort: str = Field(default="medium", description="Codex 推理强度")
    codex_approval_policy: str = Field(default="on-request", description="Codex App Server 审批策略")
    codex_sandbox: str = Field(default="workspace-write", description="Codex App Server 沙箱")
    codex_request_timeout: float = Field(default=30.0, description="Codex 协议请求超时（秒）")
    codex_approval_timeout: float = Field(default=300.0, description="Codex 审批等待超时（秒）")

    # ==================== Hook 配置 ====================
    ai_hook_script: str = Field(default="src/hook_handler.py", description="AI Hook 脚本路径")
    hook_enabled: bool = Field(default=True, description="是否启用 Hook")

    # ==================== 卡片消息配置 ====================
    card_max_length: int = Field(default=1500, description="卡片消息最大长度")
    use_safe_card_formatting: bool = Field(default=True, description="是否使用安全格式化")

    # ==================== 任务配置 ====================
    task_timeout: int = Field(default=300, description="任务超时时间（秒）")
    max_task_history: int = Field(default=100, description="最大任务历史记录数")

    # ==================== 数据库配置 ====================
    data_dir: Path = Field(default=Path("./data"), description="数据目录")
    db_path: Path = Field(default=Path("./data/larkode.db"), description="数据库路径")

    # ==================== 文件上传配置 ====================
    file_upload_type: str = Field(default="stream", description="文件上传类型")

    # ==================== 日志配置 ====================
    log_dir: Path = Field(default=Path("./logs"), description="日志目录")
    log_level: str = Field(default="INFO", description="日志级别")

    # ==================== Hook 通知配置 ====================
    feishu_hook_notification_user_id: str = Field(default="", description="Hook 通知用户 ID")
    show_user_prompt_card: bool = Field(default=False, description="是否显示用户提问卡片")
    show_command_confirmation_card: bool = Field(default=False, description="是否显示命令确认卡片")

    # ==================== 权限模式 ====================
    permission_mode: str = Field(default="default", description="权限模式")

    # ==================== 文件消息配置 ====================
    use_file_for_long_content: bool = Field(default=True, description="长内容是否使用文件")
    upload_dir: Path = Field(default=Path("./uploads"), description="上传目录")
    attachment_max_bytes: int = Field(
        default=50 * 1024 * 1024,
        ge=1,
        description="单个入站附件最大字节数",
    )

    # ==================== 截屏配置 ====================
    tmux_capture_lines: int = Field(default=200, description="截屏默认行数")

    # ==================== 工作空间配置 ====================
    workspace_discovery_enabled: bool = Field(
        default=False,
        description="是否启用工作空间自动发现"
    )
    workspace_root_dir: Path = Field(
        default=Path(""),
        description="工作空间自动发现的根目录"
    )
    workspace_discovery_depth: int = Field(
        default=1,
        description="工作空间自动发现的扫描深度"
    )
    workspace_exclude_patterns: str = Field(
        default='[".git", "node_modules", "__pycache__", ".venv", "venv", ".pytest_cache", "htmlcov", ".idea", ".vscode", "dist", "build"]',
        description="排除的目录模式（JSON 格式）"
    )
    workspace_default_dir: Path = Field(
        default=Path(""),
        description="默认工作空间目录"
    )

    # 已废弃：手动配置的工作空间列表
    workspaces: str = Field(
        default="[]",
        description="[已废弃] 工作空间配置（JSON 格式）",
        deprecated=True
    )

    # ==================== AI 自动重启配置 ====================
    ai_auto_restart_enabled: bool = Field(default=True, description="是否启用 AI 自动重启")
    ai_max_restart_attempts: int = Field(default=3, description="最大重启次数")
    ai_restart_delay: float = Field(default=5.0, description="重启延迟（秒）")
    ai_crash_detection_interval: float = Field(default=2.0, description="崩溃检测间隔（秒）")

    # ==================== Slack 配置 ====================
    slack_enabled: bool = Field(default=False, description="是否启用 Slack")
    slack_bot_token: str = Field(default="", description="Slack Bot Token")
    slack_signing_secret: str = Field(default="", description="Slack Signing Secret")
    slack_app_id: str = Field(default="", description="Slack App ID")

    # ==================== 钉钉配置 ====================
    dingtalk_enabled: bool = Field(default=False, description="是否启用钉钉")
    dingtalk_app_key: str = Field(default="", description="钉钉 App Key")
    dingtalk_app_secret: str = Field(default="", description="钉钉 App Secret")

    # ==================== MiniMax 配置 ====================
    minimax_api_key: str = Field(default="", description="MiniMax API Key")
    minimax_group_id: str = Field(default="", description="MiniMax Group ID")
    minimax_enabled: bool = Field(default=True, description="是否启用 MiniMax")

    # ==================== 流式输出配置 ====================
    streaming_output_enabled: bool = Field(default=True, description="是否启用流式输出")
    streaming_poll_interval: float = Field(default=0.5, description="流式输出轮询间隔（秒）")
    streaming_update_interval: float = Field(default=1.0, description="流式输出更新间隔（秒）- 节流控制")
    streaming_timeout: int = Field(default=3600, description="流式输出超时时间（秒），可通过 STREAMING_TIMEOUT 环境变量配置")
    streaming_stable_threshold: int = Field(default=2, description="输出稳定阈值（连续多少次不变认为完成）")
    streaming_capture_lines: int = Field(default=10, description="流式输出时抓取 tmux 的行数")

    # ==================== 依赖服务配置 ====================
    # 收到外部指令时自动检查的依赖服务（如 ccr、lut），未启动则自动拉起
    dependency_check_enabled: bool = Field(default=True, description="是否启用依赖服务自动检查")
    dependency_check_interval: float = Field(default=30.0, description="依赖服务检查间隔（秒），避免每个命令都执行 status")
    dependent_services: str = Field(
        default="",
        description="依赖服务配置（JSON 列表），每项包含 name/start_cmd/status_cmd/running_pattern"
    )
    dependency_start_timeout: float = Field(default=15.0, description="依赖服务启动超时（秒）")
    dependency_status_timeout: float = Field(default=5.0, description="依赖服务状态检测超时（秒）")

    # ==================== Validators ====================

    @field_validator('workspace_root_dir', 'workspace_default_dir', mode='before')
    @classmethod
    def expand_env_vars(cls, v: Any) -> Path:
        """展开路径中的环境变量"""
        if isinstance(v, str):
            # 展开环境变量，如 $HOME 或 ${HOME}
            expanded = os.path.expandvars(v)
            # 展开 ~ 为用户主目录
            expanded = os.path.expanduser(expanded)
            return Path(expanded)
        elif isinstance(v, Path):
            # 如果已经是 Path，先转为字符串再展开
            expanded = os.path.expandvars(str(v))
            expanded = os.path.expanduser(expanded)
            return Path(expanded)
        return v

    @field_validator('codex_approval_policy', mode='before')
    @classmethod
    def normalize_codex_approval_policy(cls, value: Any) -> str:
        aliases = {
            "onRequest": "on-request",
            "unlessTrusted": "untrusted",
        }
        normalized = aliases.get(str(value), str(value))
        # granular 属于实验协议；当前客户端没有声明 experimentalApi，禁止误配。
        allowed = {"untrusted", "on-request", "never"}
        if normalized not in allowed:
            raise ValueError(f"无效的 CODEX_APPROVAL_POLICY: {normalized}")
        return normalized

    @field_validator('codex_sandbox', mode='before')
    @classmethod
    def normalize_codex_sandbox(cls, value: Any) -> str:
        aliases = {
            "readOnly": "read-only",
            "workspaceWrite": "workspace-write",
            "dangerFullAccess": "danger-full-access",
        }
        normalized = aliases.get(str(value), str(value))
        allowed = {"read-only", "workspace-write", "danger-full-access"}
        if normalized not in allowed:
            raise ValueError(f"无效的 CODEX_SANDBOX: {normalized}")
        return normalized

    @field_validator('feishu_allowed_user_id', mode='before')
    @classmethod
    def validate_single_feishu_controller(cls, value: Any) -> str:
        """Larkode 是单用户遥控器：拒绝多控制者和通配符授权。"""
        normalized = str(value or "").strip()
        if normalized == "*":
            raise ValueError("FEISHU_ALLOWED_USER_ID 不允许使用通配符 *")
        if "," in normalized:
            raise ValueError("Larkode 不支持多用户，FEISHU_ALLOWED_USER_ID 只能配置一个 ID")
        return normalized

    # ==================== 方法 ====================

    def get_hook_script(self) -> str:
        """获取 Claude Code hook 脚本路径。Codex 使用 App Server 事件。"""
        return self.ai_hook_script

    def get_agent_backend(self) -> str:
        """获取有效 Agent 后端。"""
        backend = self.agent_backend.strip().lower()
        if backend not in {"claude_code", "codex"}:
            raise ValueError(f"不支持的 Agent 后端: {backend}")
        return backend

    def set_codex_session_preferences(
        self, model: Optional[str] = None, reasoning_effort: Optional[str] = None
    ) -> None:
        """更新当前进程的 Codex 偏好，不写入 .env。"""
        if model is not None:
            self.codex_model = model
        if reasoning_effort is not None:
            self.codex_reasoning_effort = reasoning_effort

    def is_hook_enabled(self) -> bool:
        """检查 hook 功能是否启用"""
        return self.hook_enabled

    def get_enabled_platforms(self) -> List[str]:
        """获取启用的 IM 平台列表"""
        enabled_str = self.enabled_im_platforms.strip()
        if not enabled_str:
            return []
        return [p.strip().lower() for p in enabled_str.split(",") if p.strip()]

    def get_feishu_allowed_user_id(self) -> str:
        """返回唯一控制者的飞书 ID；默认使用通知接收人。"""
        configured = self.feishu_allowed_user_id.strip()
        if configured:
            return configured
        fallback = self.feishu_hook_notification_user_id.strip()
        return fallback

    def is_feishu_user_authorized(self, *user_ids: Optional[str]) -> bool:
        """校验消息/卡片操作者；只允许配置的唯一控制者。"""
        allowed = self.get_feishu_allowed_user_id()
        return bool(allowed and allowed in (uid for uid in user_ids if uid))

    def is_platform_enabled(self, platform_name: str) -> bool:
        """检查指定平台是否启用"""
        return platform_name.lower() in self.get_enabled_platforms()

    def get_process_name(self) -> str:
        """获取当前 AI 助手的进程名"""
        return "codex" if self.get_agent_backend() == "codex" else "claude"

    def get_workspaces(self) -> List[dict]:
        """[已废弃] 获取工作空间列表，请使用 WorkspaceManager"""
        try:
            import json
            workspaces = json.loads(self.workspaces)
            if isinstance(workspaces, list):
                return workspaces
            return []
        except (json.JSONDecodeError, TypeError):
            return []

    def get_platform_config(self, platform_name: str) -> dict:
        """获取指定平台的配置"""
        platform_name = platform_name.lower()

        if platform_name == "feishu":
            return {
                "app_id": self.feishu_app_id,
                "app_secret": self.feishu_app_secret,
                "message_receive_id_type": self.feishu_message_receive_id_type,
                "message_domain": self.feishu_message_domain,
            }
        elif platform_name == "slack":
            return {
                "bot_token": self.slack_bot_token,
                "signing_secret": self.slack_signing_secret,
                "app_id": self.slack_app_id,
            }
        elif platform_name == "dingtalk":
            return {
                "app_key": self.dingtalk_app_key,
                "app_secret": self.dingtalk_app_secret,
            }
        else:
            return {}

    def init_directories(self):
        """初始化必要的目录"""
        # 将相对路径转换为绝对路径（基于项目根目录）
        # 项目根目录是 src/config 的父目录的父目录
        project_root = Path(__file__).parent.parent.parent

        # 转换数据目录和数据库路径为绝对路径
        if not self.data_dir.is_absolute():
            self.data_dir = project_root / self.data_dir
        if not self.db_path.is_absolute():
            self.db_path = project_root / self.db_path
        if not self.log_dir.is_absolute():
            self.log_dir = project_root / self.log_dir
        if not self.upload_dir.is_absolute():
            self.upload_dir = project_root / self.upload_dir

        # 创建目录
        private_dirs = {
            self.data_dir,
            self.db_path.parent,
            self.log_dir,
            self.upload_dir,
        }
        for directory in private_dirs:
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            directory.chmod(0o700)

        # .env、数据库和历史运行日志均可能包含凭据或完整对话。
        if ENV_FILE.exists():
            ENV_FILE.chmod(0o600)
        if self.db_path.exists():
            self.db_path.chmod(0o600)
        for directory in (self.log_dir, self.upload_dir):
            for path in directory.iterdir():
                if path.is_file() and not path.is_symlink():
                    path.chmod(0o600)

    def __setattr__(self, name: str, value: Any):
        """支持大小写不敏感的属性设置"""
        # 尝试转换为小写
        lower_name = name.lower()
        if lower_name != name:
            # 检查是否存在对应的属性（可能是字段或属性）
            if hasattr(type(self), lower_name):
                attr = getattr(type(self), lower_name)
                # 如果是 property，使用 setattr
                if isinstance(attr, property):
                    setattr(self, lower_name, value)
                    return
            # 否则直接设置
        super().__setattr__(name, value)

    def __getattr__(self, name: str):
        """支持大小写不敏感的属性访问"""
        # 如果属性不存在，尝试转换为小写
        lower_name = name.lower()
        if lower_name != name:
            try:
                return object.__getattribute__(self, lower_name)
            except AttributeError:
                pass
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def model_dump(self, **kwargs) -> dict:
        """导出配置为字典"""
        # 过滤掉私有属性和方法
        result = {}
        for key, value in self.__dict__.items():
            if not key.startswith("_") and key not in ["model_config"]:
                result[key] = value
        return result


# 创建全局设置实例
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    获取全局设置实例（单例模式）

    Returns:
        Settings 实例
    """
    global _settings
    if _settings is None:
        _settings = Settings()
        # 初始化目录（并将相对路径转换为绝对路径）
        _settings.init_directories()
    return _settings


def reload_settings() -> Settings:
    """
    重新加载设置

    Returns:
        新的 Settings 实例
    """
    global _settings
    _settings = Settings()
    return _settings


Config = get_settings()
