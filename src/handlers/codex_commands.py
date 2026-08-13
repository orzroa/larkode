"""Codex 模型与 Think 等级的飞书选择卡。"""

from typing import Any, Dict, List, Optional

from src.config.settings import get_settings
from src.option_card import OptionCardData, OptionItem, build_option_card


class CodexCommands:
    """基于 App Server 的实时模型目录管理当前进程的 Codex 偏好。"""

    def __init__(self, task_manager) -> None:
        self.task_manager = task_manager

    async def _catalog(self) -> List[Dict[str, Any]]:
        assistant = self.task_manager.ai_assistant
        get_catalog = getattr(assistant, "get_model_catalog", None)
        if not get_catalog:
            raise RuntimeError("当前 Codex 助手不支持读取模型目录")
        return await get_catalog()

    @staticmethod
    def _model_id(model: Dict[str, Any]) -> str:
        return model.get("model") or model.get("id") or ""

    @classmethod
    def _supported_efforts(cls, model: Dict[str, Any]) -> List[Dict[str, Any]]:
        """返回模型实际可选的 Think 等级；Luna 明确不支持 max。"""
        efforts = model.get("supportedReasoningEfforts") or []
        if "luna" in cls._model_id(model).lower():
            efforts = [item for item in efforts if item.get("reasoningEffort") != "max"]
        return efforts

    @staticmethod
    async def _send_result_card(user_id: str, title: str, content: str, send_message_func):
        """发送明确的选择结果卡，避免卡片点击后没有视觉反馈。"""
        await send_message_func(user_id, card={
            "schema": "2.0",
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": "green",
            },
            "body": {"elements": [{"tag": "markdown", "content": content}]},
        })

    async def show_model_option_card(self, user_id: str, send_message_func, page: int = 1):
        models = await self._catalog()
        settings = get_settings()
        current = settings.codex_model or next(
            (self._model_id(item) for item in models if item.get("isDefault")), ""
        )
        items = [
            OptionItem(
                key=self._model_id(item),
                label=item.get("displayName") or self._model_id(item),
                description=self._model_id(item),
                is_current=(self._model_id(item) == current),
            )
            for item in models
            if self._model_id(item)
        ]
        if not items:
            raise RuntimeError("当前账号没有可用的 Codex 模型")
        card = build_option_card(OptionCardData(
            title="🤖 Codex 模型",
            category="codex_model",
            items=items,
            page=page,
            header_note=(
                f"当前模型: `{current or 'Codex 默认'}` · "
                "点击模型切换；发送 `#think` 选择 Think 等级"
            ),
        ))
        await send_message_func(user_id, card=card)

    async def show_effort_option_card(self, user_id: str, send_message_func, page: int = 1):
        models = await self._catalog()
        settings = get_settings()
        model_id = settings.codex_model or next(
            (self._model_id(item) for item in models if item.get("isDefault")), ""
        )
        model = next((item for item in models if self._model_id(item) == model_id), None)
        if not model:
            raise RuntimeError("找不到当前 Codex 模型，请先选择模型")
        efforts = self._supported_efforts(model)
        supported_keys = {item.get("reasoningEffort") for item in efforts}
        configured = settings.codex_reasoning_effort or ""
        current = configured if configured in supported_keys else (
            model.get("defaultReasoningEffort")
            if model.get("defaultReasoningEffort") in supported_keys
            else (next(iter(supported_keys), "") if supported_keys else "")
        )
        items = [
            OptionItem(
                key=item.get("reasoningEffort", ""),
                label=item.get("reasoningEffort", ""),
                description=item.get("description"),
                is_current=(item.get("reasoningEffort") == current),
            )
            for item in efforts
            if item.get("reasoningEffort")
        ]
        if not items:
            raise RuntimeError(f"模型 {model_id} 未返回可选 Think 等级")
        card = build_option_card(OptionCardData(
            title="🧠 Codex Think 等级",
            category="codex_effort",
            items=items,
            page=page,
            header_note=f"模型: `{model_id}` · 当前 Think: `{current}`",
            action_context={"model_id": model_id},
        ))
        await send_message_func(user_id, card=card)

    async def handle_model_select(self, user_id: str, model_id: str, send_message_func):
        models = await self._catalog()
        selected = next((item for item in models if self._model_id(item) == model_id), None)
        if not selected:
            raise ValueError(f"无效的 Codex 模型: {model_id}")
        settings = get_settings()
        if settings.codex_model == model_id:
            effort = settings.codex_reasoning_effort or selected.get("defaultReasoningEffort") or ""
            result_title = "✅ Codex 模型未变更"
        else:
            effort = selected.get("defaultReasoningEffort") or "medium"
            settings.set_codex_session_preferences(model=model_id, reasoning_effort=effort)
            result_title = "✅ Codex 模型已切换"
        await self._send_result_card(
            user_id,
            result_title,
            (
                f"**模型：** `{model_id}`\n\n"
                f"**Think：** `{effort}`\n\n"
                "仅对当前进程生效；下一条任务起生效。"
            ),
            send_message_func,
        )

    async def handle_effort_select(
        self, user_id: str, effort: str, send_message_func, expected_model_id: str = ""
    ):
        models = await self._catalog()
        settings = get_settings()
        model_id = settings.codex_model or next(
            (self._model_id(item) for item in models if item.get("isDefault")), ""
        )
        if expected_model_id and expected_model_id != model_id:
            raise ValueError(
                f"该 Think 卡片属于模型 {expected_model_id}，当前模型已切换为 {model_id}，请重新发送 #think"
            )
        model = next((item for item in models if self._model_id(item) == model_id), None)
        supported = {
            item.get("reasoningEffort")
            for item in self._supported_efforts(model or {})
        }
        if effort not in supported:
            raise ValueError(f"模型 {model_id} 不支持 Think 等级: {effort}")
        settings.set_codex_session_preferences(reasoning_effort=effort)
        await self._send_result_card(
            user_id,
            "✅ Codex Think 等级已切换",
            (
                f"**模型：** `{model_id}`\n\n"
                f"**Think：** `{effort}`\n\n"
                "仅对当前进程生效；下一条任务起生效。"
            ),
            send_message_func,
        )
