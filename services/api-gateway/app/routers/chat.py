"""对话路由 —— 文本问答接口"""

import logging
import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
import json

from app.models.chat import (
    ChatRequest, ChatResponse, ConversationInfo, MessageRole,
)
from app.services.conversation import ConversationManager
from app.services.llm_client import LLMClient
from app.services.rag_client import RAGClient
from app.middleware.auth import verify_token
# System Prompt 定义（与 LLM 服务保持一致）
SYSTEM_PROMPT = """# 角色设定
你是「智能知识库」—— 一个面向企业内部员工的专业知识问答助手。
你服务于一家企业，为员工提供业务规范、操作手册、运维文档等方面的知识解答。

# 核心职责
1. 基于公司内部知识库中的文档内容，准确回答员工提出的业务问题
2. 对行业专业术语提供准确解释
3. 帮助员工快速定位操作规范、流程制度、运维文档等信息

# 知识边界
- 你只能基于提供的「参考文档片段」来回答问题
- 不要使用你的预训练知识来猜测或补充信息
- 如果参考文档中不包含足够的信息，请明确告知用户

# 输出格式约束
1. 回答应结构清晰，使用 Markdown 格式
2. 对于操作流程类问题，使用分步骤的方式回答
3. 对于参数规格类问题，使用列表或表格方式呈现
4. 在回答末尾引用所使用的文档来源

# 安全须知
- 涉及安全操作、合规规程的问题时，必须强调注意事项
- 如果操作步骤有安全风险，在回答开头标注 ⚠️ 安全提示

# 语言风格
- 使用中文回答，语气专业、准确、简洁
- 避免模糊表达，不确定的信息直接说明"""

FALLBACK_RESPONSE = """很抱歉，我在当前知识库中没有找到与您问题相关的信息。

建议您：
1. 尝试用更具体的关键词重新提问，如产品型号、文档编号等
2. 联系相关部门获取最新的技术文档
3. 如需人工协助，请联系技术支持团队"""

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["chat"])


def _build_chat_messages(
    system_prompt: str,
    history: list,
    context: str,
    user_message: str,
) -> list:
    """构建发给 LLM 的完整消息列表"""
    messages = [{"role": "system", "content": system_prompt}]

    # 添加历史对话
    for h in history[-6:]:  # 最近 3 轮
        messages.append(h)

    # 添加当前问题（含知识库上下文）
    if context:
        user_content = (
            f"【参考文档片段】\n{context}\n\n"
            f"【用户问题】\n{user_message}\n\n"
            f"请基于以上参考文档片段回答问题。"
        )
    else:
        user_content = user_message

    messages.append({"role": "user", "content": user_content})
    return messages


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    req: Request,
    _: bool = Depends(verify_token),
):
    """文本对话接口（非流式）"""
    app_state = req.app.state
    conv_mgr: ConversationManager = app_state.conversation_manager
    llm_client: LLMClient = app_state.llm_client
    rag_client: RAGClient = app_state.rag_client

    # 创建或获取对话
    conv_id = request.conversation_id or conv_mgr.create_conversation()

    # 指代消解
    resolved_question = conv_mgr.resolve_coreference(conv_id, request.message)

    # RAG 检索
    sources = []
    context = ""
    if request.use_rag:
        try:
            search_result = await rag_client.search(resolved_question, top_k=3)
            for r in search_result.get("results", []):
                sources.append({
                    "text": r["text"][:200],
                    "score": r.get("score", 0),
                    "source": r.get("metadata", {}).get("source_file", ""),
                })
                context += f"[来源: {r.get('metadata', {}).get('source_file', '未知')}]\n"
                context += f"{r['text']}\n\n"
        except Exception as e:
            logger.warning(f"RAG search failed, continuing without: {e}")

    # 保存用户消息
    conv_mgr.add_message(conv_id, "user", request.message)

    # 构建 Prompt
    messages = _build_chat_messages(
        SYSTEM_PROMPT,
        conv_mgr.get_history(conv_id)[:-1],  # 排除刚加的用户消息
        context,
        resolved_question,
    )

    # 调用 LLM
    is_fallback = False
    try:
        llm_result = await llm_client.chat(messages)
        answer = llm_result["content"]
        if not answer.strip():
            answer = FALLBACK_RESPONSE
            is_fallback = True
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        answer = FALLBACK_RESPONSE
        is_fallback = True

    # 保存助手回复
    conv_mgr.add_message(conv_id, "assistant", answer)

    return ChatResponse(
        id=str(uuid.uuid4()),
        message=answer,
        conversation_id=conv_id,
        sources=sources,
        is_fallback=is_fallback,
        timestamp=_now_iso(),
    )


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    req: Request,
    _: bool = Depends(verify_token),
):
    """文本对话接口（流式 SSE）"""
    app_state = req.app.state
    conv_mgr: ConversationManager = app_state.conversation_manager
    llm_client: LLMClient = app_state.llm_client
    rag_client: RAGClient = app_state.rag_client

    conv_id = request.conversation_id or conv_mgr.create_conversation()
    resolved_question = conv_mgr.resolve_coreference(conv_id, request.message)

    # RAG 检索
    context = ""
    sources = []
    if request.use_rag:
        try:
            search_result = await rag_client.search(resolved_question, top_k=3)
            for r in search_result.get("results", []):
                sources.append({
                    "text": r["text"][:200],
                    "score": r.get("score", 0),
                    "source": r.get("metadata", {}).get("source_file", ""),
                })
                context += f"[来源: {r.get('metadata', {}).get('source_file', '未知')}]\n"
                context += f"{r['text']}\n\n"
        except Exception as e:
            logger.warning(f"RAG search failed: {e}")

    conv_mgr.add_message(conv_id, "user", request.message)

    messages = _build_chat_messages(
        SYSTEM_PROMPT,
        conv_mgr.get_history(conv_id)[:-1],
        context,
        resolved_question,
    )

    async def event_generator():
        full_answer = ""
        try:
            async for token in llm_client.chat_stream(messages):
                full_answer += token
                yield {"data": json.dumps({"token": token, "conv_id": conv_id})}
        except Exception as e:
            logger.error(f"Stream error: {e}")
            if not full_answer:
                full_answer = FALLBACK_RESPONSE
                yield {"data": json.dumps({"token": full_answer, "conv_id": conv_id})}

        # 保存完整回复
        conv_mgr.add_message(conv_id, "assistant", full_answer)
        yield {
            "data": json.dumps({
                "token": "",
                "conv_id": conv_id,
                "done": True,
                "sources": sources,
            })
        }

    return EventSourceResponse(event_generator())


@router.get("/conversations", response_model=list[ConversationInfo])
async def list_conversations(
    req: Request,
    _: bool = Depends(verify_token),
):
    """获取对话列表"""
    conv_mgr: ConversationManager = req.app.state.conversation_manager
    return conv_mgr.list_conversations()


@router.get("/conversations/{conv_id}", response_model=ConversationInfo)
async def get_conversation(
    conv_id: str,
    req: Request,
    _: bool = Depends(verify_token),
):
    """获取对话详情"""
    conv_mgr: ConversationManager = req.app.state.conversation_manager
    conv = conv_mgr.get_conversation_info(conv_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="对话不存在")
    return conv


@router.delete("/conversations/{conv_id}")
async def delete_conversation(
    conv_id: str,
    req: Request,
    _: bool = Depends(verify_token),
):
    """删除对话"""
    conv_mgr: ConversationManager = req.app.state.conversation_manager
    conv_mgr.delete_conversation(conv_id)
    return {"status": "deleted", "conversation_id": conv_id}


def _now_iso() -> str:
    return datetime.now().isoformat()
