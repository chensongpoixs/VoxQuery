"""管理接口路由"""

import logging
from fastapi import APIRouter, Request, Depends
from app.services.llm_client import LLMClient
from app.services.rag_client import RAGClient
from app.services.asr_client import ASRClient
from app.services.tts_client import TTSClient
from app.middleware.auth import verify_token, create_access_token
from app.config import Settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/health")
async def full_health_check(req: Request):
    """全局健康检查 —— 检测所有下游服务"""
    app_state = req.app.state
    llm_client: LLMClient = app_state.llm_client
    rag_client: RAGClient = app_state.rag_client
    asr_client: ASRClient = app_state.asr_client
    tts_client: TTSClient = app_state.tts_client

    results = {
        "api_gateway": "healthy",
        "llm_service": "healthy" if await llm_client.health() else "unhealthy",
        "rag_service": "healthy" if await rag_client.health() else "unhealthy",
    }

    # 语音服务可选
    try:
        results["asr_service"] = "healthy" if await asr_client.health() else "unhealthy"
    except Exception:
        results["asr_service"] = "unavailable"

    try:
        results["tts_service"] = "healthy" if await tts_client.health() else "unhealthy"
    except Exception:
        results["tts_service"] = "unavailable"

    all_healthy = all(
        v == "healthy" for v in results.values()
        if v != "unavailable"
    )

    return {
        "status": "healthy" if all_healthy else "degraded",
        "services": results,
        "version": app_state.settings.version,
        "environment": app_state.settings.environment,
    }


@router.post("/auth/token")
async def login(req: Request, username: str = "admin", password: str = "admin"):
    """获取访问 Token（简易实现，生产环境需对接企业 SSO）"""
    settings: Settings = req.app.state.settings
    # 简易认证（生产环境替换为 LDAP/OAuth）
    if username == "admin" and password == "admin":
        token = create_access_token(settings, username)
        return {"access_token": token, "token_type": "bearer"}
    return {"error": "认证失败"}, 401
