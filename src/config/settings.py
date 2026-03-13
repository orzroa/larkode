"""
Pydantic Settings 配置管理

使用 pydantic-settings 提供类型安全的配置管理。
"""
import os
from pathlib import Path
from typing import Any, List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置 - 使用 Pydantic Settings"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # 忽略额外的环境变量
    )

    # ==================== 平台配置 ====================
    im_platform: str = Field(default="feishu", description="IM 平台类型")
    ai_assistant_type: str = Field(default="claude_code", description="AI 助手类型")
    enabled_im_platforms: str = Field(default="feishu", description="启用的 IM 平台列表")

    # ==================== 飞书配置 ====================
    feishu_app_id: str = Field(default="", description="飞书应用 ID")
    feishu_app_secret: str = Field(default="", description="飞书应用密钥")
    feishu_enabled: bool = Field(default=True, description="是否启用飞书")
    feishu_message_receive_id_type: str = Field(default="open_id", description="消息接收 ID 类型")
    feishu_message_domain: str = Field(default="FEISHU_DOMAIN", description="飞书 API 域名")

    # ==================== 通用 AI 配置 ====================
    tmux_session_name: str = Field(default="cc", description="tmux 会话名称")
    session_max_age_minutes: int = Field(default=30, description="Session 最大未更新时间（分钟）")

    # ==================== Claude Code 配置 ====================
    claude_code_workspace_dir: Path = Field(default=Path(""), description="Claude Code 工作目录")
    claude_code_log_file: Path = Field(default=Path(""), description="Claude Code 日志文件路径")
    claude_code_cli_path: str = Field(default="", description="Claude Code CLI 路径")
    claude_code_session_id: str = Field(default="", description="Claude Code 会话 ID")

    # ==================== iFlow 配置 ====================
    iflow_cli: str = Field(default="iflow", description="iFlow CLI 路径")
    iflow_dir: Path = Field(default=Path(""), description="iFlow 工作目录")

    # ==================== Hook 配置 ====================
    ai_hook_script: str = Field(default="src/hook_handler.py", description="AI Hook 脚本路径")
    iflow_hook_script: str = Field(default="src/hook_handler.py", description="iFlow Hook 脚本路径")
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

    # ==================== 截屏配置 ====================
    tmux_capture_lines: int = Field(default=200, description="截屏默认行数")

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

    # ==================== 流式输出配置 ====================
    streaming_output_enabled: bool = Field(default=True, description="是否启用流式输出")
    streaming_poll_interval: float = Field(default=0.5, description="流式输出轮询间隔（秒）")
    streaming_update_interval: float = Field(default=1.0, description="流式输出更新间隔（秒）- 节流控制")
    streaming_timeout: int = Field(default=300, description="流式输出超时时间（秒）")
    streaming_stable_threshold: int = Field(default=2, description="输出稳定阈值（连续多少次不变认为完成）")

    # ==================== 方法 ====================

    def get_hook_script(self) -> str:
        """根据 AI_ASSISTANT_TYPE 获取对应的 hook 脚本路径"""
        if self.ai_assistant_type == "iflow":
            return self.iflow_hook_script
        return self.ai_hook_script

    def is_hook_enabled(self) -> bool:
        """检查 hook 功能是否启用"""
        return self.hook_enabled

    def get_enabled_platforms(self) -> List[str]:
        """获取启用的 IM 平台列表"""
        enabled_str = self.enabled_im_platforms.strip()
        if not enabled_str:
            return []
        return [p.strip().lower() for p in enabled_str.split(",") if p.strip()]

    def is_platform_enabled(self, platform_name: str) -> bool:
        """检查指定平台是否启用"""
        return platform_name.lower() in self.get_enabled_platforms()

    def get_process_name(self) -> str:
        """获取当前 AI 助手的进程名"""
        if self.ai_assistant_type == "iflow":
            return "iflow"
        return "claude"

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
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

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

