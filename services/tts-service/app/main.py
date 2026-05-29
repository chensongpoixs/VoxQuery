"""TTS 语音合成服务 —— CosyVoice2

支持：
- 文字转语音（流式输出）
- 零样本音色克隆
- 多音色管理
"""

import asyncio
import logging
import io
import hashlib
import tempfile
import os
from typing import Optional
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager

from app.config import TTSServiceConfig

logger = logging.getLogger(__name__)
config = TTSServiceConfig()

_model = None
_voice_registry: dict = {}


def get_model():
    """懒加载 CosyVoice2 模型"""
    global _model
    if _model is None:
        try:
            # CosyVoice2 为阿里通义开源模型
            # 实际部署时替换为真实模型加载代码
            logger.info(f"Loading CosyVoice2 from: {config.model_path or 'HuggingFace'}")

            # 预置音色库
            _voice_registry["default"] = {
                "name": "默认女声",
                "description": "专业企业播报音色",
                "sample_url": None,
            }
            _voice_registry["male_engineer"] = {
                "name": "男工程师",
                "description": "沉稳技术男声",
                "sample_url": None,
            }
            _voice_registry["female_operator"] = {
                "name": "女操作员",
                "description": "清晰调度女声",
                "sample_url": None,
            }

            _model = True  # Placeholder: 实际为模型对象
            logger.info("CosyVoice2 loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load CosyVoice2: {e}")
            raise
    return _model


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"TTS Service starting on port {config.port}")
    yield
    logger.info("TTS Service shutting down")


app = FastAPI(
    title="KB - TTS Service",
    version="1.0.0",
    lifespan=lifespan,
)


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4096, description="待合成文本")
    voice_id: str = Field(default="default", description="音色 ID")
    speed: float = Field(default=1.0, ge=0.5, le=2.0, description="语速")
    response_format: str = Field(default="wav", description="音频格式 wav/mp3")
    stream: bool = Field(default=False, description="是否流式返回")


class VoiceCloneRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4096, description="待合成文本")
    voice_name: str = Field(..., description="新音色名称")


class VoiceInfo(BaseModel):
    voice_id: str
    name: str
    description: str


def _synthesize_audio(text: str, voice_id: str, speed: float) -> bytes:
    """执行语音合成

    实际部署时替换为 CosyVoice2 模型推理代码。
    当前为占位实现，通过生成静音音频来验证链路。
    """
    import numpy as np
    import wave
    import struct

    # 实际 CosyVoice2 推理代码：
    # model = get_model()
    # audio = model.tts(text, voice_id=voice_id, speed=speed)
    # return audio_to_wav_bytes(audio)

    # -- 占位音频生成（验证链路用）--
    logger.info(f"TTS: voice={voice_id}, speed={speed}, text_len={len(text)}")
    sample_rate = config.sample_rate
    # 按中文朗读速度 ~4 chars/sec 估算时长
    duration = max(1.0, len(text) / 4.0 * speed)
    num_samples = int(sample_rate * duration)

    # 生成简单正弦波（440Hz）验证音频链路
    t = np.linspace(0, duration, num_samples, endpoint=False)
    audio = (np.sin(2 * np.pi * 440 * t) * 0.3 * 32767).astype(np.int16)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio.tobytes())
    buf.seek(0)
    return buf.read()

    # 实际部署时，替换上述占位代码为 CosyVoice2 推理：
    # from cosyvoice import CosyVoice2
    # model = CosyVoice2(model_path=config.model_path)
    # audio_tensor = model.synthesize(text, voice_id=voice_id, speed=speed)
    # return convert_to_wav_bytes(audio_tensor, config.sample_rate)


# ========== REST API ==========

@app.get("/health")
async def health_check():
    get_model()
    return {"status": "healthy", "model": config.model_name}


@app.get("/voices", response_model=list[VoiceInfo])
async def list_voices():
    """列出可用音色"""
    get_model()
    return [
        VoiceInfo(voice_id=vid, name=info["name"], description=info["description"])
        for vid, info in _voice_registry.items()
    ]


@app.post("/v1/tts")
async def synthesize(request: TTSRequest):
    """文字转语音 —— 生成完整音频"""
    try:
        get_model()
        audio_bytes = _synthesize_audio(request.text, request.voice_id, request.speed)

        media_type = "audio/wav" if request.response_format == "wav" else "audio/mpeg"
        return Response(
            content=audio_bytes,
            media_type=media_type,
            headers={
                "X-Audio-Duration": str(len(audio_bytes) / (config.sample_rate * 2)),
                "X-Voice-Id": request.voice_id,
            },
        )
    except Exception as e:
        logger.error(f"TTS error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/tts/stream")
async def synthesize_stream(request: TTSRequest):
    """流式语音合成 —— 逐块返回音频"""
    get_model()

    async def audio_generator():
        # 按句子分块合成
        sentences = request.text.replace("。", "。\n").split("\n")
        sentences = [s.strip() for s in sentences if s.strip()]

        for sentence in sentences:
            audio_chunk = _synthesize_audio(sentence, request.voice_id, request.speed)
            yield audio_chunk
            await asyncio_sleep(0.05)  # 模拟流式间隔

    return StreamingResponse(
        audio_generator(),
        media_type="audio/wav",
        headers={"X-Voice-Id": request.voice_id},
    )


@app.post("/v1/voice/clone")
async def clone_voice(
    file: UploadFile = File(...),
    voice_name: str = "cloned_voice",
):
    """零样本音色克隆 —— 上传参考音频，创建新音色"""
    try:
        contents = await file.read()
        voice_id = hashlib.md5(contents).hexdigest()[:12]

        # 保存参考音频
        ref_path = os.path.join(tempfile.gettempdir(), f"voice_{voice_id}.wav")
        with open(ref_path, "wb") as f:
            f.write(contents)

        # 注册新音色（实际部署时调用 CosyVoice2 音色注册 API）
        _voice_registry[voice_id] = {
            "name": voice_name,
            "description": f"克隆音色 (ref: {file.filename})",
            "sample_path": ref_path,
        }

        logger.info(f"Voice cloned: id={voice_id}, name={voice_name}")
        return {
            "status": "success",
            "voice_id": voice_id,
            "voice_name": voice_name,
        }
    except Exception as e:
        logger.error(f"Voice clone error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/v1/voice/{voice_id}")
async def delete_voice(voice_id: str):
    """删除音色"""
    if voice_id in ("default", "male_engineer", "female_operator"):
        raise HTTPException(status_code=400, detail="不能删除系统内置音色")
    if voice_id in _voice_registry:
        del _voice_registry[voice_id]
        return {"status": "deleted", "voice_id": voice_id}
    raise HTTPException(status_code=404, detail="音色不存在")


@app.get("/stats")
async def get_stats():
    return {
        "model": config.model_name,
        "sample_rate": config.sample_rate,
        "voice_count": len(_voice_registry),
    }


# 异步 sleep helper
async def asyncio_sleep(seconds: float):
    await asyncio.sleep(seconds)
