#!/usr/bin/env python3
"""批量文档导入脚本

支持从目录批量导入文档，带进度报告和错误统计。
"""

import argparse
import logging
import sys
import os
import httpx
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("batch-import")

RAG_SERVICE_URL = os.getenv("RAG_SERVICE_URL", "http://localhost:8003")


def main():
    parser = argparse.ArgumentParser(description="批量导入文档到知识库")
    parser.add_argument("--input-dir", required=True, help="输入目录")
    parser.add_argument("--strategy", default="sliding_window", help="分段策略")
    parser.add_argument("--api-url", default=RAG_SERVICE_URL, help="RAG 服务地址")
    parser.add_argument("--recursive", action="store_true", default=True, help="递归处理子目录")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        logger.error(f"目录不存在: {input_dir}")
        sys.exit(1)

    client = httpx.Client(timeout=300.0)

    try:
        logger.info(f"开始批量导入: {input_dir}")
        url = f"{args.api_url}/ingest"
        response = client.post(url, json={
            "directory": str(input_dir),
            "strategy": args.strategy,
        })
        response.raise_for_status()
        result = response.json()

        logger.info(f"批量导入完成:")
        logger.info(f"  分块数: {result.get('chunks_created', 0)}")
        logger.info(f"  入库数: {result.get('documents_added', 0)}")

        if result.get("errors"):
            logger.warning(f"  错误数: {len(result['errors'])}")
            for err in result["errors"][:5]:
                logger.warning(f"    {err}")

    except Exception as e:
        logger.error(f"批量导入失败: {e}")
        sys.exit(1)
    finally:
        client.close()


if __name__ == "__main__":
    main()
