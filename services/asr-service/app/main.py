"""ASR 语音识别服务 —— Whisper-large-v3

支持中英文混合识别，提供 REST API 和 WebSocket 流式解码。
"""

import logging
import io
import tempfile
import os
from typing import Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from contextlib import asynccontextmanager
import numpy as np

from app.config import ASRServiceConfig

logger = logging.getLogger(__name__)
config = ASRServiceConfig()

_model = None


def get_model():
    """懒加载 Whisper 模型"""
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        model_source = config.model_path or config.model_name
        logger.info(f"Loading Whisper model: {model_source}")

        _model = WhisperModel(
            model_source,
            device=config.device,
            compute_type=config.compute_type,
            local_files_only=bool(config.model_path and os.path.isdir(config.model_path)),
        )
        logger.info("Whisper model loaded")
    return _model


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"ASR Service starting on port {config.port}")
    get_model()  # 预加载
    yield
    logger.info("ASR Service shutting down")


app = FastAPI(
    title="Energy KB - ASR Service",
    version="1.0.0",
    lifespan=lifespan,
)


class ASRResponse(BaseModel):
    text: str
    language: str
    segments: list = []
    duration_seconds: float = 0.0


@app.get("/health")
async def health_check():
    return {"status": "healthy", "model": config.model_name}


@app.post("/v1/transcribe", response_model=ASRResponse)
async def transcribe(
    file: UploadFile = File(...),
    language: Optional[str] = None,
):
    """音频转录接口 —— 上传音频文件返回文字"""
    try:
        contents = await file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="空音频文件")

        # 保存为临时文件
        suffix = os.path.splitext(file.filename or "audio.wav")[1] or ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        try:
            model = get_model()
            lang = language or config.default_language
            if lang == "auto":
                lang = None

            segments_result, info = model.transcribe(
                tmp_path,
                language=lang,
                beam_size=config.beam_size,
                vad_filter=True,
                vad_parameters={"threshold": config.vad_threshold},
            )

            segments = list(segments_result)
            full_text = " ".join(seg.text for seg in segments)

            return ASRResponse(
                text=full_text,
                language=info.language,
                segments=[
                    {
                        "start": round(seg.start, 2),
                        "end": round(seg.end, 2),
                        "text": seg.text,
                    }
                    for seg in segments
                ],
                duration_seconds=round(info.duration, 2),
            )
        finally:
            os.unlink(tmp_path)

    except Exception as e:
        logger.error(f"Transcription error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/transcribe")
async def ws_transcribe(websocket: WebSocket):
    """WebSocket 流式转录 —— 实时接收音频流，逐段返回识别文本"""
    await websocket.accept()
    logger.info("WebSocket streaming transcription started")

    audio_buffer = bytearray()

    try:
        while True:
            # 接收音频数据块
            data = await websocket.receive_bytes()
            audio_buffer.extend(data)

            # 累积足够数据后进行识别（约 2 秒音频 @ 16kHz 16bit mono）
            if len(audio_buffer) > 64000:
                # 写入临时文件
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    tmp.write(bytes(audio_buffer))
                    tmp_path = tmp.name

                try:
                    model = get_model()
                    segments, info = model.transcribe(
                        tmp_path,
                        beam_size=config.beam_size,
                        vad_filter=True,
                    )
                    for seg in segments:
                        await websocket.send_json({
                            "text": seg.text,
                            "start": round(seg.start, 2),
                            "end": round(seg.end, 2),
                            "is_final": False,
                        })
                finally:
                    os.unlink(tmp_path)

                audio_buffer.clear()

    except WebSocketDisconnect:
        # 处理剩余音频
        if audio_buffer:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(bytes(audio_buffer))
                tmp_path = tmp.name
            try:
                model = get_model()
                segments, _ = model.transcribe(tmp_path)
                for seg in segments:
                    await websocket.send_json({
                        "text": seg.text,
                        "start": round(seg.start, 2),
                        "end": round(seg.end, 2),
                        "is_final": True,
                    })
            finally:
                os.unlink(tmp_path)
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")


@app.get("/stats")
async def get_stats():
    return {
        "model": config.model_name,
        "language": config.default_language,
        "device": config.device,
        "compute_type": config.compute_type,
    }
