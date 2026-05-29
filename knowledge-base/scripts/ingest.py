#!/usr/bin/env python3
"""知识库文档导入脚本

将文档目录中的文件解析、分段、向量化后存入知识库。
用法：
    python ingest.py --docs-dir ./sample-docs
    python ingest.py --docs-dir ./sample-docs --strategy semantic
"""

import argparse
import logging
import sys
import os
import httpx
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("kb-ingest")

RAG_SERVICE_URL = os.getenv("RAG_SERVICE_URL", "http://localhost:8003")


def main():
    parser = argparse.ArgumentParser(description="导入文档到知识库")
    parser.add_argument(
        "--docs-dir", required=True, help="文档目录路径"
    )
    parser.add_argument(
        "--strategy", default="sliding_window",
        choices=["fixed_length", "semantic", "sliding_window"],
        help="分段策略"
    )
    parser.add_argument(
        "--api-url", default=RAG_SERVICE_URL,
        help="RAG 服务地址"
    )
    args = parser.parse_args()

    docs_dir = Path(args.docs_dir)
    if not docs_dir.exists():
        logger.error(f"文档目录不存在: {docs_dir}")
        sys.exit(1)

    # 扫描文件
    supported_ext = {".txt", ".md", ".pdf", ".docx", ".html"}
    files = [
        f for f in docs_dir.rglob("*")
        if f.suffix.lower() in supported_ext and not f.name.startswith(".")
    ]

    if not files:
        logger.warning(f"目录 {docs_dir} 中未找到支持的文档文件")
        logger.info(f"支持的格式: {', '.join(supported_ext)}")
        sys.exit(0)

    logger.info(f"找到 {len(files)} 个文件")
    for f in files:
        logger.info(f"  - {f.relative_to(docs_dir)}")

    # 调用 RAG 服务入库
    client = httpx.Client(timeout=120.0)
    try:
        url = f"{args.api_url}/ingest"
        response = client.post(url, json={
            "directory": str(docs_dir),
            "strategy": args.strategy,
        })
        response.raise_for_status()
        result = response.json()

        logger.info(f"入库完成: {result.get('documents_added', 0)} 个片段, "
                    f"{result.get('chunks_created', 0)} 个分块")

        if result.get("errors"):
            for err in result["errors"]:
                logger.warning(f"  错误: {err}")

    except httpx.ConnectError:
        logger.error(f"无法连接到 RAG 服务: {args.api_url}")
        logger.info("请确保 RAG 服务已启动: docker compose up -d rag-service")
        sys.exit(1)
    except Exception as e:
        logger.error(f"导入失败: {e}")
        sys.exit(1)
    finally:
        client.close()


if __name__ == "__main__":
    main()
