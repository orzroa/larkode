"""
CCR 模型切换命令处理器
处理 #model 命令，支持显示模型列表和切换模型
"""
import json
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Tuple

# 优先使用新的日志工具，失败则回退到标准 logging
try:
    from src.logging_utils import get_logger
except ImportError:
    import logging

try:
    logger = get_logger(__name__)
except NameError:
    logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from src.interfaces.im_platform import NormalizedCard

CONFIG_PATH = Path.home() / ".claude-code-router" / "config.json"


class CCRCommands:
    """CCR 模型切换命令处理器"""

    def __init__(self):
        """初始化 CCR 命令处理器"""
        pass

    def load_config(self) -> dict:
        """加载配置文件"""
        if not CONFIG_PATH.exists():
            return None

        try:
            with open(CONFIG_PATH, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"加载配置文件失败: {e}")
            return None

    def save_config(self, config: dict):
        """保存配置文件"""
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)

    def extract_models_from_providers(self, config: dict) -> List[str]:
        """
        从 Providers 字段提取所有模型
        返回: [完整格式]
        """
        models = []

        if 'Providers' not in config or not isinstance(config['Providers'], list):
            return models

        for provider in config['Providers']:
            provider_name = provider.get('name')
            model_list = provider.get('models', [])

            if provider_name and isinstance(model_list, list):
                for model_name in model_list:
                    if isinstance(model_name, str) and model_name.startswith('#'):
                        continue
                    full_format = f"{provider_name},{model_name}"
                    models.append(full_format)

        # 按提供商+模型名排序（字母顺序）
        models.sort(key=lambda x: (x.split(',')[0], x.split(',')[1]) if ',' in x else (x, ''))
        return models

    def get_current_model(self, config: dict) -> Optional[str]:
        """获取当前默认模型（Router.default）"""
        return config.get('Router', {}).get('default')

    def update_default_model(self, model_string: str):
        """更新配置文件中的 default 模型"""
        config = self.load_config()
        if config is None:
            return False

        if 'Router' not in config:
            config['Router'] = {}
        config['Router']['default'] = model_string
        self.save_config(config)
        return True

    def restart_ccr(self) -> Tuple[bool, str]:
        """重启 CCR 服务"""
        try:
            # 先尝试 restart
            result = subprocess.run(
                ["ccr", "restart"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                return True, "CCR 服务重启完成"

            # restart 失败则尝试 start
            logger.warning("CCR restart 失败，尝试 start")
            result = subprocess.run(
                ["ccr", "start"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                return True, "CCR 服务启动完成"

            return False, f"操作失败: {result.stderr}"

        except subprocess.TimeoutExpired:
            return False, "操作超时"
        except FileNotFoundError:
            return False, "未找到 ccr 命令，请确保已安装 CCR"
        except Exception as e:
            return False, f"操作失败: {str(e)}"

    def find_model_by_input(self, input_str: str, models: List[str]) -> Optional[str]:
        """根据输入查找对应的完整格式"""
        # 如果是数字序号
        clean_input = input_str.strip().rstrip('*')
        if clean_input.isdigit():
            idx = int(clean_input)
            if 1 <= idx <= len(models):
                return models[idx - 1]
            return None

        # 如果是完整格式（包含逗号）
        if ',' in input_str:
            return input_str.strip()

        return None

    async def handle_model_command(
        self,
        user_id: str,
        args: str,
        send_message_func
    ):
        """
        处理 #model 命令

        Args:
            user_id: 用户 ID
            args: 命令参数（可选）
            send_message_func: 发送消息的回调函数
        """
        # 加载配置和模型列表
        config = self.load_config()

        if config is None:
            await self._send_error(
                user_id,
                "配置文件不存在，请先运行 ccr code 初始化配置",
                send_message_func
            )
            return

        models = self.extract_models_from_providers(config)

        if not models:
            await self._send_error(
                user_id,
                "配置文件中没有找到任何模型，请检查 CCR 配置",
                send_message_func
            )
            return

        current = self.get_current_model(config)

        # 无参数：显示模型列表
        if not args.strip():
            await self._show_model_list(user_id, models, current, send_message_func)
            return

        # 有参数：切换模型
        model_string = self.find_model_by_input(args, models)

        if not model_string:
            await self._send_error(
                user_id,
                f"无效输入: {args}\n请输入序号 (1-{len(models)}) 或完整格式 (如 deepseek,deepseek-chat)",
                send_message_func
            )
            return

        # 如果是完整格式但不在列表中，给出警告
        if ',' in args and model_string not in models:
            warning_msg = f"⚠️ 警告: {model_string} 不在 Providers 列表中"
            logger.warning(warning_msg)

        # 如果已是当前模型
        if model_string == current:
            await self._send_success(
                user_id,
                f"当前已是此模型: {model_string}",
                send_message_func
            )
            return

        # 切换模型
        success = self.update_default_model(model_string)
        if not success:
            await self._send_error(
                user_id,
                "更新配置文件失败",
                send_message_func
            )
            return

        # 重启 CCR 服务
        restart_ok, restart_msg = self.restart_ccr()

        if restart_ok:
            # 构建完整的模型列表，高亮新模型
            model_lines = []
            for i, m in enumerate(models, 1):
                if m == model_string:
                    model_lines.append(f"- **{i}** **`{m}`** ✅")
                else:
                    model_lines.append(f"- **{i}** `{m}`")

            content = f"""
✅ **模型切换成功**

- 新模型: `{model_string}`
- {restart_msg}

---

**模型列表**:

{chr(10).join(model_lines)}

---

💡 现在可以执行 `ccr code` 使用新模型
"""
            await self._send_success(user_id, content, send_message_func)
        else:
            await self._send_error(
                user_id,
                f"切换成功但重启失败: {restart_msg}\n请手动执行 `ccr restart`",
                send_message_func
            )

    async def _show_model_list(
        self,
        user_id: str,
        models: List[str],
        current: Optional[str],
        send_message_func
    ):
        """显示模型列表"""
        from src.interfaces.im_platform import NormalizedCard

        # 构建 Markdown 列表
        lines = []
        for i, model in enumerate(models, 1):
            if model == current:
                lines.append(f"- **{i}** **`{model}`** ✅")
            else:
                lines.append(f"- **{i}** `{model}`")

        content = f"""
**当前模型**: `{current or "未设置"}`

{chr(10).join(lines)}

---

💡 使用 `#model <序号>` 或 `#model <完整格式>` 切换模型
"""
        card = NormalizedCard(
            card_type="model_list",
            title="模型列表",
            content=content,
            template_color="blue"
        )
        await send_message_func(user_id, card=card)

    async def _send_success(
        self,
        user_id: str,
        content: str,
        send_message_func
    ):
        """发送成功消息"""
        from src.interfaces.im_platform import NormalizedCard

        card = NormalizedCard(
            card_type="success",
            title="成功",
            content=content,
            template_color="green"
        )
        await send_message_func(user_id, card=card)

    async def _send_error(
        self,
        user_id: str,
        error: str,
        send_message_func
    ):
        """发送错误消息"""
        from src.interfaces.im_platform import NormalizedCard

        card = NormalizedCard(
            card_type="error",
            title="错误",
            content=error,
            template_color="red"
        )
        await send_message_func(user_id, card=card)
