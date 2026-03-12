"""
数据模型
"""
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class MessageType(str, Enum):
    """消息类型"""
    COMMAND = "command"
    RESPONSE = "response"
    STATUS = "status"
    ERROR = "error"


class MessageDirection(str, Enum):
    """消息方向"""
    UPSTREAM = "upstream"      # 用户发送的消息（上行）
    DOWNSTREAM = "downstream"  # 发送给用户的消息（下发）


class MessageSource(str, Enum):
    """消息来源"""
    FEISHU = "feishu"        # 飞书消息
    HOOK = "hook"            # Hook 通知消息
    API_TEST = "api_test"    # API 测试消息


class Message(BaseModel):
    """消息模型"""
    id: Optional[int] = Field(None, description="自增主键")
    user_id: str = Field(..., description="飞书用户 ID")
    message_type: MessageType = Field(..., description="消息类型")
    content: str = Field(..., description="消息内容")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    direction: Optional[MessageDirection] = Field(None, description="消息方向")
    is_test: Optional[bool] = Field(None, description="是否为测试消息，None 表示使用全局测试模式")
    message_source: Optional[MessageSource] = Field(None, description="消息来源")
    feishu_message_id: str = Field(..., description="飞书原始消息 ID")
    card_id: Optional[int] = Field(None, description="卡片编号")