"""
Profile 加载器与配置生成引擎。

从 YAML profile 生成：
  - .env 环境变量文件
  - docker-compose.override.yml（GPU 绑定）
  - supervisord.conf（原生部署进程管理）
"""
from __future__ import annotations

import os
import textwrap
from pathlib import Path
from typing import Optional

import yaml

from configs.profile_schema import ProfileSpec


# ============================================================
# Profile 加载
# ============================================================

def load_profile(name_or_path: str, profiles_dir: str = "configs/profiles") -> ProfileSpec:
    """加载 profile 文件并返回验证后的 ProfileSpec。

    Args:
        name_or_path: profile 名称（如 'single-gpu'）或 .yaml 路径
        profiles_dir: profiles 目录路径

    Returns:
        验证后的 ProfileSpec 实例
    """
    # 判断是名称还是路径
    if os.path.isfile(name_or_path):
        path = Path(name_or_path)
    elif name_or_path.endswith((".yaml", ".yml")):
        path = Path(name_or_path)
    else:
        path = Path(profiles_dir) / f"{name_or_path}.yaml"

    if not path.exists():
        raise FileNotFoundError(f"Profile 文件不存在: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return ProfileSpec.model_validate(data)


# ============================================================
# .env 生成
# ============================================================

def generate_env(profile: ProfileSpec) -> str:
    """从 profile 生成 .env 文件内容"""
    env = profile.to_env_vars()

    sections = [
        ("全局配置", ["PROJECT_NAME", "DEPLOYMENT_MODE", "HARDWARE_PROFILE",
                       "MODELS_DIR", "ENVIRONMENT", "LOG_LEVEL"]),
        ("API Gateway", ["API_GATEWAY_HOST", "API_GATEWAY_PORT", "API_GATEWAY_WORKERS",
                         "JWT_SECRET_KEY", "JWT_ALGORITHM", "JWT_EXPIRE_MINUTES"]),
        ("Redis", ["REDIS_HOST", "REDIS_PORT", "REDIS_DB", "REDIS_PASSWORD",
                    "CONVERSATION_TTL", "RETRIEVAL_CACHE_TTL"]),
        ("LLM 服务", ["LLM_MODEL_NAME", "LLM_MAX_TOKENS", "LLM_TEMPERATURE",
                       "LLM_TOP_P", "LLM_CONTEXT_WINDOW", "LLM_TENSOR_PARALLEL_SIZE",
                       "LLM_QUANTIZATION", "LLM_MAX_CONCURRENT",
                       "LLM_GPU_MEMORY_UTILIZATION", "LLM_KV_CACHE_DTYPE",
                       "NVIDIA_VISIBLE_DEVICES_LLM"]),
        ("Embedding 服务", ["EMBEDDING_MODEL_NAME", "EMBEDDING_MAX_LENGTH",
                             "EMBEDDING_BATCH_SIZE", "NVIDIA_VISIBLE_DEVICES_EMBEDDING"]),
        ("RAG 服务", ["RAG_TOP_K", "RAG_RERANK_TOP_N", "RAG_SIMILARITY_THRESHOLD"]),
        ("ChromaDB", ["CHROMA_HOST", "CHROMA_PORT", "CHROMA_COLLECTION_NAME"]),
        ("ASR 服务", ["ASR_MODEL_NAME", "ASR_LANGUAGE", "ASR_VAD_THRESHOLD"]),
        ("TTS 服务", ["TTS_DEFAULT_VOICE", "TTS_SAMPLE_RATE",
                       "NVIDIA_VISIBLE_DEVICES_ASR_TTS"]),
        ("GPU 分配", ["NVIDIA_VISIBLE_DEVICES_LLM", "NVIDIA_VISIBLE_DEVICES_EMBEDDING",
                       "NVIDIA_VISIBLE_DEVICES_ASR_TTS"]),
        ("模型下载", ["HF_ENDPOINT", "USE_MODELSCOPE"]),
        ("知识库", ["KNOWLEDGE_CHUNK_SIZE", "KNOWLEDGE_CHUNK_OVERLAP"]),
    ]

    lines = [
        "# ============================================================",
        f"# 知识库问答系统 - 环境变量配置",
        f"# Profile: {profile.profile.name} ({profile.profile.description})",
        f"# 部署模式: {profile.deployment.mode}",
        f"# GPU: {profile.gpus.count}×{profile.gpus.models[0] if profile.gpus.models else 'N/A'}",
        f"# 自动生成，请勿手动编辑",
        "# ============================================================",
        "",
    ]

    for section_name, keys in sections:
        lines.append(f"# ---------- {section_name} ----------")
        for key in keys:
            val = env.get(key, "")
            lines.append(f"{key}={val}")
        lines.append("")

    return "\n".join(lines)


# ============================================================
# Docker Compose Override 生成
# ============================================================

def _svc_gpu_block(device_ids: list[int], indent_spaces: int = 6) -> str:
    """生成单个服务的 deploy.resources GPU 块（带缩进）"""
    ids_str = ", ".join(f'"{d}"' for d in device_ids)
    indent = " " * indent_spaces
    lines = [
        f"{indent}deploy:",
        f"{indent}  resources:",
        f"{indent}    reservations:",
        f"{indent}      devices:",
        f"{indent}        - driver: nvidia",
        f'{indent}          device_ids: [{ids_str}]',
        f"{indent}          capabilities: [gpu]",
    ]
    return "\n".join(lines)


def generate_docker_override(profile: ProfileSpec) -> str:
    """从 profile 生成 docker-compose.override.yml 内容

    Docker Compose 会自动合并 docker-compose.yml + docker-compose.override.yml。
    本文件只包含 GPU 绑定配置。
    """
    svcs = profile.services
    gpu_blocks: dict[str, str] = {}

    # LLM
    llm_devices = [svcs.llm.gpu_device] if isinstance(svcs.llm.gpu_device, int) else svcs.llm.gpu_device
    gpu_blocks["llm-service"] = _svc_gpu_block(llm_devices)

    # Embedding
    gpu_blocks["embedding-service"] = _svc_gpu_block([svcs.embedding.gpu_device])

    # ASR
    gpu_blocks["asr-service"] = _svc_gpu_block([svcs.asr.gpu_device])

    # TTS
    gpu_blocks["tts-service"] = _svc_gpu_block([svcs.tts.gpu_device])

    header = textwrap.dedent(f"""\
    # ============================================================
    # Docker Compose GPU 绑定覆盖文件
    # Profile: {profile.profile.name} ({profile.profile.description})
    # GPU: {profile.gpus.count}×{profile.gpus.models[0] if profile.gpus.models else 'N/A'}
    # 自动生成，请勿手动编辑
    # ============================================================
    """)

    svc_yamls = []
    for svc_name in ["llm-service", "embedding-service", "asr-service", "tts-service"]:
        svc_yamls.append(f"  {svc_name}:")
        svc_yamls.append(gpu_blocks[svc_name])
        svc_yamls.append("")  # 空行分隔

    return header + "\nservices:\n" + "\n".join(svc_yamls)


# ============================================================
# Supervisord 配置生成 (原生部署)
# ============================================================

def generate_supervisord(profile: ProfileSpec, project_dir: str = ".") -> str:
    """从 profile 生成 supervisord.conf 内容

    每个服务作为一个 [program] 段，由 supervisord 统一管理进程生命周期。
    """
    svcs = profile.services
    proj = os.path.abspath(project_dir)

    programs = []

    # 基础设施（无 GPU）
    programs.append(_supervisord_program(
        name="redis",
        command="redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru",
        directory=proj,
        env={},
        priority=1,
    ))
    programs.append(_supervisord_program(
        name="chromadb",
        command="chroma run --host 0.0.0.0 --port 8004 --path ./data/chroma",
        directory=proj,
        env={"IS_PERSISTENT": "TRUE", "ANONYMIZED_TELEMETRY": "FALSE"},
        priority=2,
    ))

    # LLM
    llm_env = {
        "CUDA_VISIBLE_DEVICES": svcs.llm.cuda_visible_devices(),
        "MODEL_NAME": svcs.llm.model,
        "TENSOR_PARALLEL_SIZE": str(svcs.llm.tensor_parallel_size),
        "QUANTIZATION": svcs.llm.quantization,
        "CONTEXT_WINDOW": str(svcs.llm.context_window),
        "MAX_NUM_SEQS": str(svcs.llm.max_num_seqs),
        "GPU_MEMORY_UTILIZATION": str(svcs.llm.gpu_memory_utilization),
        "KV_CACHE_DTYPE": svcs.llm.kv_cache_dtype,
        "PORT": "8001",
        "MODEL_PATH": f"{proj}/models/gemma3",
    }
    programs.append(_supervisord_program(
        name="llm-service",
        command="bash services/llm-service/scripts/start_vllm.sh",
        directory=proj,
        env=llm_env,
        priority=10,
    ))

    # Embedding
    emb_env = {
        "CUDA_VISIBLE_DEVICES": svcs.embedding.cuda_visible_devices(),
        "MODEL_NAME": svcs.embedding.model,
        "MAX_LENGTH": str(svcs.embedding.max_length),
        "BATCH_SIZE": str(svcs.embedding.batch_size),
        "PORT": "8002",
    }
    programs.append(_supervisord_program(
        name="embedding-service",
        command="python services/embedding-service/app/main.py",
        directory=proj,
        env=emb_env,
        priority=11,
    ))

    # ASR
    asr_env = {
        "CUDA_VISIBLE_DEVICES": svcs.asr.cuda_visible_devices(),
        "MODEL_NAME": svcs.asr.model,
        "DEFAULT_LANGUAGE": svcs.asr.language,
        "VAD_THRESHOLD": str(svcs.asr.vad_threshold),
        "PORT": "8005",
    }
    programs.append(_supervisord_program(
        name="asr-service",
        command="python services/asr-service/app/main.py",
        directory=proj,
        env=asr_env,
        priority=12,
    ))

    # TTS
    tts_env = {
        "CUDA_VISIBLE_DEVICES": svcs.tts.cuda_visible_devices(),
        "DEFAULT_VOICE": svcs.tts.default_voice,
        "SAMPLE_RATE": str(svcs.tts.sample_rate),
        "PORT": "8006",
    }
    programs.append(_supervisord_program(
        name="tts-service",
        command="python services/tts-service/app/main.py",
        directory=proj,
        env=tts_env,
        priority=13,
    ))

    # RAG
    rag_env = {
        "EMBEDDING_SERVICE_URL": "http://localhost:8002",
        "CHROMA_HOST": "localhost",
        "CHROMA_PORT": "8004",
        "CHROMA_COLLECTION": "kb_knowledge",
        "TOP_K": "5",
        "RERANK_TOP_N": "3",
        "SIMILARITY_THRESHOLD": "0.65",
        "REDIS_HOST": "localhost",
        "REDIS_PORT": "6379",
        "PORT": "8003",
    }
    programs.append(_supervisord_program(
        name="rag-service",
        command="python services/rag-service/app/main.py",
        directory=proj,
        env=rag_env,
        priority=20,
    ))

    # API Gateway
    api_env = {
        "LLM_SERVICE_URL": "http://localhost:8001",
        "EMBEDDING_SERVICE_URL": "http://localhost:8002",
        "RAG_SERVICE_URL": "http://localhost:8003",
        "ASR_SERVICE_URL": "http://localhost:8005",
        "TTS_SERVICE_URL": "http://localhost:8006",
        "REDIS_HOST": "localhost",
        "REDIS_PORT": "6379",
        "CONVERSATION_TTL": "86400",
        "PORT": "8000",
    }
    programs.append(_supervisord_program(
        name="api-gateway",
        command="uvicorn services.api-gateway.app.main:app --host 0.0.0.0 --port 8000",
        directory=proj,
        env=api_env,
        priority=30,
    ))

    # Frontend
    fe_env = {
        "NEXT_PUBLIC_API_URL": "http://localhost:8000",
        "NEXT_PUBLIC_WS_URL": "ws://localhost:8000",
        "PORT": "3000",
    }
    programs.append(_supervisord_program(
        name="frontend",
        command="npm run dev",
        directory=f"{proj}/frontend",
        env=fe_env,
        priority=40,
    ))

    header = textwrap.dedent(f"""\
    ; ============================================================
    ; Supervisord 配置 — 知识库问答系统
    ; Profile: {profile.profile.name} ({profile.profile.description})
    ; 部署模式: native
    ; 自动生成，请勿手动编辑
    ; ============================================================
    [unix_http_server]
    file=/tmp/supervisor.sock

    [supervisord]
    logfile=/tmp/supervisord.log
    logfile_maxbytes=50MB
    logfile_backups=10
    loglevel=info
    pidfile=/tmp/supervisord.pid
    nodaemon=false

    [rpcinterface:supervisor]
    supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface

    [supervisorctl]
    serverurl=unix:///tmp/supervisor.sock

    """)

    return header + "\n".join(programs) + "\n"


def _supervisord_program(
    name: str, command: str, directory: str,
    env: dict[str, str], priority: int = 10,
) -> str:
    """生成单个 supervisord [program] 段"""
    env_str = ",".join(f'{k}="{v}"' for k, v in env.items())
    return textwrap.dedent(f"""\
    [program:{name}]
    command={command}
    directory={directory}
    environment={env_str}
    priority={priority}
    autostart=true
    autorestart=true
    startsecs=5
    startretries=3
    stopwaitsecs=10
    stopsignal=TERM
    redirect_stderr=true
    stdout_logfile=/tmp/{name}.log
    stdout_logfile_maxbytes=50MB

    """)


# ============================================================
# Systemd Unit 生成 (可选)
# ============================================================

def generate_systemd_units(profile: ProfileSpec, project_dir: str = ".") -> dict[str, str]:
    """生成 systemd unit 文件字典 {服务名: unit内容}"""
    proj = os.path.abspath(project_dir)
    svcs = profile.services
    user = os.environ.get("USER", "root")

    units = {}

    # 为每个核心服务生成 unit
    service_defs = [
        ("llm-service", f"bash {proj}/services/llm-service/scripts/start_vllm.sh",
         {"CUDA_VISIBLE_DEVICES": svcs.llm.cuda_visible_devices(), "PORT": "8001"}),
        ("embedding-service", f"python {proj}/services/embedding-service/app/main.py",
         {"CUDA_VISIBLE_DEVICES": svcs.embedding.cuda_visible_devices(), "PORT": "8002"}),
        ("asr-service", f"python {proj}/services/asr-service/app/main.py",
         {"CUDA_VISIBLE_DEVICES": svcs.asr.cuda_visible_devices(), "PORT": "8005"}),
        ("tts-service", f"python {proj}/services/tts-service/app/main.py",
         {"CUDA_VISIBLE_DEVICES": svcs.tts.cuda_visible_devices(), "PORT": "8006"}),
        ("rag-service", f"python {proj}/services/rag-service/app/main.py", {"PORT": "8003"}),
        ("api-gateway", f"uvicorn services.api-gateway.app.main:app --host 0.0.0.0 --port 8000",
         {"PORT": "8000"}),
    ]

    for name, cmd, extra_env in service_defs:
        env_lines = ""
        for k, v in extra_env.items():
            env_lines += f"Environment={k}={v}\n"
        unit = textwrap.dedent(f"""\
        [Unit]
        Description=Knowledge Base {name}
        After=network.target

        [Service]
        Type=simple
        User={user}
        WorkingDirectory={proj}
        ExecStart={cmd}
        {env_lines}Restart=always
        RestartSec=10

        [Install]
        WantedBy=multi-user.target
        """)
        units[name] = unit

    return units
