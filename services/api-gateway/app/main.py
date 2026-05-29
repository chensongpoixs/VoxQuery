"""API Gateway —— 能源行业知识库问答系统入口

功能：
- 文本/语音对话路由
- 知识库管理
- 多轮对话记忆
- 指代消解
- 流式响应
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings
from app.routers import chat, knowledge, voice, admin
from app.middleware.logging import RequestLoggingMiddleware
from app.services.conversation import ConversationManager
from app.services.llm_client import LLMClient
from app.services.rag_client import RAGClient
from app.services.asr_client import ASRClient
from app.services.tts_client import TTSClient

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("api-gateway")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期 —— 初始化服务客户端"""
    settings = Settings()
    app.state.settings = settings

    logger.info(f"Starting {settings.project_name} v{settings.version}")
    logger.info(f"Environment: {settings.environment}")

    # 初始化服务客户端
    app.state.llm_client = LLMClient(settings)
    app.state.rag_client = RAGClient(settings)
    app.state.asr_client = ASRClient(settings)
    app.state.tts_client = TTSClient(settings)
    app.state.conversation_manager = ConversationManager(settings)

    logger.info("All service clients initialized")
    yield

    # 清理资源
    await app.state.llm_client.close()
    await app.state.rag_client.close()
    await app.state.asr_client.close()
    await app.state.tts_client.close()
    logger.info("API Gateway shutdown complete")


def create_app() -> FastAPI:
    settings = Settings()

    app = FastAPI(
        title=settings.project_name,
        version=settings.version,
        description="面向能源行业的内部业务知识库问答系统 + 语音对话助手",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 请求日志
    app.add_middleware(RequestLoggingMiddleware)

    # 注册路由
    app.include_router(chat.router)
    app.include_router(knowledge.router)
    app.include_router(voice.router)
    app.include_router(admin.router)

    # 根路径
    @app.get("/")
    async def root():
        return {
            "name": settings.project_name,
            "version": settings.version,
            "docs": "/docs",
        }

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    return app


app = create_app()
