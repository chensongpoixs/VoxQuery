"""API Gateway 集成测试"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "api-gateway"))

from app.config import Settings
from app.models.chat import ChatRequest, ChatResponse, MessageRole
from app.services.conversation import ConversationManager


class TestSettings:
    """配置测试"""

    def test_default_settings(self):
        settings = Settings()
        assert settings.project_name == "Energy KB Q&A System"
        assert settings.port == 8000

    def test_environment(self):
        settings = Settings(environment="production")
        assert settings.environment == "production"


class TestChatModels:
    """数据模型测试"""

    def test_chat_request(self):
        req = ChatRequest(message="测试问题", conversation_id=None, use_rag=True, stream=True)
        assert req.message == "测试问题"
        assert req.use_rag is True

    def test_chat_request_validation(self):
        # 空消息应该被拒绝
        with pytest.raises(Exception):
            ChatRequest(message="")

    def test_message_role(self):
        assert MessageRole.user == "user"
        assert MessageRole.assistant == "assistant"
        assert MessageRole.system == "system"


class TestConversationManager:
    """对话管理测试"""

    def test_create_conversation(self):
        settings = Settings(redis_host="localhost", redis_port=6379)
        # 使用内存存储（Redis 不可用时降级）
        mgr = ConversationManager(settings)
        conv_id = mgr.create_conversation("测试对话")
        assert conv_id
        assert len(conv_id) == 12  # MD5 前 12 位

    def test_add_and_get_messages(self):
        settings = Settings(redis_host="localhost", redis_port=6379)
        mgr = ConversationManager(settings)
        conv_id = mgr.create_conversation()

        mgr.add_message(conv_id, "user", "变压器的巡检项目有哪些？")
        mgr.add_message(conv_id, "assistant", "日常巡检包括油温检查、油位检查等。")

        history = mgr.get_history(conv_id)
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"
        assert "油温" in history[1]["content"]

    def test_conversation_info(self):
        settings = Settings(redis_host="localhost", redis_port=6379)
        mgr = ConversationManager(settings)
        conv_id = mgr.create_conversation("设备维护")

        info = mgr.get_conversation_info(conv_id)
        assert info["title"] == "设备维护"
        assert info["message_count"] == 0

    def test_coreference_resolution(self):
        """指代消解测试"""
        settings = Settings(redis_host="localhost", redis_port=6379)
        mgr = ConversationManager(settings)
        conv_id = mgr.create_conversation()

        mgr.add_message(conv_id, "user", "变压器的额定容量是多少？")
        mgr.add_message(conv_id, "assistant", "SZ11-50000/110型变压器的额定容量为50000kVA。")

        # 省略式提问
        resolved = mgr.resolve_coreference(conv_id, "它的巡检项目有哪些？")
        assert "变压器" in resolved or "SZ11" in resolved or "50000kVA" in resolved

    def test_delete_conversation(self):
        settings = Settings(redis_host="localhost", redis_port=6379)
        mgr = ConversationManager(settings)
        conv_id = mgr.create_conversation()
        mgr.add_message(conv_id, "user", "测试")

        mgr.delete_conversation(conv_id)
        assert mgr.get_conversation_info(conv_id) is None

    def test_list_conversations(self):
        settings = Settings(redis_host="localhost", redis_port=6379)
        mgr = ConversationManager(settings)
        mgr.create_conversation("对话A")
        mgr.create_conversation("对话B")

        convs = mgr.list_conversations()
        assert len(convs) == 2
        assert convs[0]["title"] in ("对话A", "对话B")

    def test_history_limit(self):
        """测试对话历史长度限制"""
        settings = Settings(redis_host="localhost", redis_port=6379)
        mgr = ConversationManager(settings)
        conv_id = mgr.create_conversation()

        # 添加超过限制的消息
        for i in range(25):
            mgr.add_message(conv_id, "user", f"问题{i}")
            mgr.add_message(conv_id, "assistant", f"回答{i}")

        history = mgr.get_history(conv_id)
        assert len(history) <= 20  # MAX_HISTORY_TURNS * 2 = 20
