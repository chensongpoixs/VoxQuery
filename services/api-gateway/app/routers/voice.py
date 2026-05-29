"""语音对话路由 —— 语音问答接口（ASR → LLM+RAG → TTS）"""

import logging
import uuid
from datetime import datetime
from fastapi import APIRouter, Request, UploadFile, File, Depends, HTTPException
from fastapi.responses import Response, StreamingResponse

from app.models.chat import VoiceChatRequest, ChatResponse
from app.services.conversation import ConversationManager
from app.services.llm_client import LLMClient
from app.services.rag_client import RAGClient
from app.services.asr_client import ASRClient
from app.services.tts_client import TTSClient
from app.middleware.auth import verify_token

# 复用 chat 路由中的 System Prompt
from app.routers.chat import SYSTEM_PROMPT, FALLBACK_RESPONSE

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/voice", tags=["voice"])


def _build_chat_messages(system_prompt: str, history: list, context: str, user_message: str) -> list:
    messages = [{"role": "system", "content": system_prompt}]
    for h in history[-6:]:
        messages.append(h)
    if context:
        user_content = f"【参考文档片段】\n{context}\n\n【用户问题】\n{user_message}"
    else:
        user_content = user_message
    messages.append({"role": "user", "content": user_content})
    return messages


@router.post("/chat")
async def voice_chat(
    audio: UploadFile = File(...),
    voice_id: str = "default",
    conversation_id: str = None,
    req: Request = None,
    _: bool = Depends(verify_token),
):
    """语音对话 —— 上传音频，返回音频回复

    流程：Audio → ASR → Text → RAG检索 → LLM → TTS → Audio
    """
    app_state = req.app.state
    conv_mgr: ConversationManager = app_state.conversation_manager
    llm_client: LLMClient = app_state.llm_client
    rag_client: RAGClient = app_state.rag_client
    asr_client: ASRClient = app_state.asr_client
    tts_client: TTSClient = app_state.tts_client

    conv_id = conversation_id or conv_mgr.create_conversation()

    try:
        # Step 1: ASR 语音识别
        audio_bytes = await audio.read()
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="空音频文件")

        asr_result = await asr_client.transcribe(audio_bytes, audio.filename or "audio.wav")
        user_text = asr_result.get("text", "")
        if not user_text.strip():
            raise HTTPException(status_code=400, detail="未能识别出有效语音内容")

        # Step 2: 指代消解
        resolved_question = conv_mgr.resolve_coreference(conv_id, user_text)

        # Step 3: RAG 检索
        context = ""
        try:
            search_result = await rag_client.search(resolved_question, top_k=3)
            for r in search_result.get("results", []):
                context += f"[来源: {r.get('metadata', {}).get('source_file', '未知')}]\n"
                context += f"{r['text']}\n\n"
        except Exception as e:
            logger.warning(f"RAG search failed: {e}")

        # Step 4: 保存用户消息
        conv_mgr.add_message(conv_id, "user", user_text)

        # Step 5: LLM 推理
        messages = _build_chat_messages(
            SYSTEM_PROMPT,
            conv_mgr.get_history(conv_id)[:-1],
            context,
            resolved_question,
        )

        try:
            llm_result = await llm_client.chat(messages)
            answer_text = llm_result["content"]
        except Exception as e:
            logger.error(f"LLM error: {e}")
            answer_text = FALLBACK_RESPONSE

        # Step 6: 保存助手回复
        conv_mgr.add_message(conv_id, "assistant", answer_text)

        # Step 7: TTS 语音合成
        try:
            audio_response = await tts_client.synthesize(answer_text, voice_id=voice_id)
        except Exception as e:
            logger.error(f"TTS error: {e}")
            raise HTTPException(status_code=500, detail="语音合成失败")

        return Response(
            content=audio_response,
            media_type="audio/wav",
            headers={
                "X-Conversation-Id": conv_id,
                "X-Transcribed-Text": user_text[:200],
                "X-Answer-Text": answer_text[:200],
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Voice chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    language: str = None,
    req: Request = None,
    _: bool = Depends(verify_token),
):
    """仅语音识别 —— 音频转文字"""
    asr_client: ASRClient = req.app.state.asr_client
    audio_bytes = await audio.read()
    result = await asr_client.transcribe(audio_bytes, audio.filename, language)
    return result


@router.post("/synthesize")
async def synthesize_speech(
    text: str,
    voice_id: str = "default",
    speed: float = 1.0,
    req: Request = None,
    _: bool = Depends(verify_token),
):
    """仅语音合成 —— 文字转音频"""
    tts_client: TTSClient = req.app.state.tts_client
    audio_bytes = await tts_client.synthesize(text, voice_id, speed)
    return Response(content=audio_bytes, media_type="audio/wav")


@router.get("/voices")
async def list_voices(
    req: Request,
    _: bool = Depends(verify_token),
):
    """获取可用音色列表"""
    tts_client: TTSClient = req.app.state.tts_client
    return await tts_client.list_voices()


@router.post("/voices/clone")
async def clone_voice(
    audio: UploadFile = File(...),
    voice_name: str = "cloned_voice",
    req: Request = None,
    _: bool = Depends(verify_token),
):
    """克隆新音色"""
    tts_client: TTSClient = req.app.state.tts_client
    audio_bytes = await audio.read()
    return await tts_client.clone_voice(audio_bytes, voice_name, audio.filename)


@router.get("/health/asr-tts")
async def check_voice_services(req: Request):
    """检查语音服务健康状态"""
    app_state = req.app.state
    asr_client: ASRClient = app_state.asr_client
    tts_client: TTSClient = app_state.tts_client

    asr_healthy = await asr_client.health()
    tts_healthy = await tts_client.health()

    return {
        "asr": "healthy" if asr_healthy else "unhealthy",
        "tts": "healthy" if tts_healthy else "unhealthy",
        "timestamp": datetime.now().isoformat(),
    }
