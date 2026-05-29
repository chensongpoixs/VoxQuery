"""多轮对话管理

功能：
1. 对话历史存储（Redis + 内存降级）
2. 多轮上下文拼接
3. 指代消解（将不完整问题补全为完整问题）
4. 对话摘要与过期清理
"""

import json
import logging
import hashlib
import time
from typing import List, Dict, Optional
from datetime import datetime
import redis
from app.config import Settings

logger = logging.getLogger(__name__)


class ConversationManager:
    """对话管理器"""

    MAX_HISTORY_TURNS = 10  # 最多保留 10 轮对话

    def __init__(self, settings: Settings):
        self.ttl = settings.conversation_ttl
        self._memory_store: Dict[str, List[Dict]] = {}

        # 尝试连接 Redis
        try:
            self.redis = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                password=settings.redis_password or None,
                db=settings.redis_db,
                decode_responses=True,
                socket_connect_timeout=3,
            )
            self.redis.ping()
            self._use_redis = True
            logger.info("Redis connected for conversation storage")
        except Exception as e:
            logger.warning(f"Redis unavailable, using in-memory store: {e}")
            self.redis = None
            self._use_redis = False

    def create_conversation(self, title: str = "") -> str:
        """创建新对话"""
        conv_id = hashlib.md5(
            f"{title}{time.time()}".encode()
        ).hexdigest()[:12]

        conv_data = {
            "title": title or "新对话",
            "messages": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        if self._use_redis:
            self.redis.setex(
                f"conv:{conv_id}",
                self.ttl,
                json.dumps(conv_data, ensure_ascii=False),
            )
        else:
            self._memory_store[conv_id] = conv_data

        logger.info(f"Conversation created: {conv_id}")
        return conv_id

    def add_message(self, conv_id: str, role: str, content: str):
        """添加消息到对话历史"""
        conv = self._get_conv(conv_id)
        if conv is None:
            return

        conv["messages"].append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })
        conv["updated_at"] = datetime.now().isoformat()

        # 限制历史长度
        if len(conv["messages"]) > self.MAX_HISTORY_TURNS * 2:
            conv["messages"] = conv["messages"][-(self.MAX_HISTORY_TURNS * 2):]

        self._save_conv(conv_id, conv)

    def get_history(self, conv_id: str) -> List[Dict[str, str]]:
        """获取对话历史（用于 LLM 上下文）"""
        conv = self._get_conv(conv_id)
        if conv is None:
            return []

        history = []
        for msg in conv["messages"]:
            history.append({
                "role": msg["role"],
                "content": msg["content"],
            })
        return history

    def get_conversation_info(self, conv_id: str) -> Optional[Dict]:
        """获取对话详情"""
        conv = self._get_conv(conv_id)
        if conv is None:
            return None
        return {
            "id": conv_id,
            "title": conv.get("title", ""),
            "messages": conv["messages"],
            "created_at": conv["created_at"],
            "updated_at": conv["updated_at"],
            "message_count": len(conv["messages"]),
        }

    def resolve_coreference(self, conv_id: str, current_question: str) -> str:
        """指代消解：基于对话历史补全当前问题

        如果当前问题是省略式提问（如"它的参数是多少？"），
        基于对话历史中的上下文补充完整。
        """
        history = self.get_history(conv_id)
        if not history:
            return current_question

        # 检查是否包含指代词
        pronouns = ["它", "他", "她", "这个", "那个", "这些", "那些", "其"]
        has_pronoun = any(p in current_question for p in pronouns)

        if not has_pronoun:
            # 检查是否过于简短（可能是省略式提问）
            if len(current_question) < 10:
                # 获取上一轮话题作为上下文
                last_user_msgs = [
                    h["content"] for h in history if h["role"] == "user"
                ]
                if last_user_msgs:
                    return (f"基于之前的讨论（{last_user_msgs[-1][:100]}），"
                            f"请回答：{current_question}")

        if has_pronoun:
            # 将上一轮助手回答的关键主题前置
            last_assistant_msgs = [
                h["content"] for h in history if h["role"] == "assistant"
            ]
            if last_assistant_msgs:
                # 提取主题关键词（简化实现：取第一句）
                last_topic = last_assistant_msgs[-1].split("。")[0][:100]
                return f"关于「{last_topic}」，{current_question}"

        return current_question

    def delete_conversation(self, conv_id: str) -> bool:
        """删除对话"""
        if self._use_redis:
            self.redis.delete(f"conv:{conv_id}")
        self._memory_store.pop(conv_id, None)
        return True

    def list_conversations(self) -> List[Dict]:
        """列出所有对话摘要"""
        conversations = []

        if self._use_redis:
            for key in self.redis.scan_iter("conv:*"):
                data = self.redis.get(key)
                if data:
                    conv = json.loads(data)
                    conv_id = key.replace("conv:", "")
                    conversations.append({
                        "id": conv_id,
                        "title": conv.get("title", ""),
                        "message_count": len(conv.get("messages", [])),
                        "updated_at": conv.get("updated_at", ""),
                    })
        else:
            for conv_id, conv in self._memory_store.items():
                conversations.append({
                    "id": conv_id,
                    "title": conv.get("title", ""),
                    "message_count": len(conv.get("messages", [])),
                    "updated_at": conv.get("updated_at", ""),
                })

        return sorted(
            conversations,
            key=lambda x: x["updated_at"],
            reverse=True,
        )

    def _get_conv(self, conv_id: str) -> Optional[Dict]:
        """获取对话数据"""
        if self._use_redis:
            data = self.redis.get(f"conv:{conv_id}")
            if data:
                return json.loads(data)
        return self._memory_store.get(conv_id)

    def _save_conv(self, conv_id: str, conv: Dict):
        """保存对话数据"""
        if self._use_redis:
            self.redis.setex(
                f"conv:{conv_id}",
                self.ttl,
                json.dumps(conv, ensure_ascii=False),
            )
        else:
            self._memory_store[conv_id] = conv
