#!/usr/bin/env python3
"""知识库增量更新脚本

支持：
- 新增文档：检测新文件并入库
- 修改文档：删除旧分段 + 重新入库
- 删除文档：从知识库中移除
"""

import argparse
import logging
import sys
import os
import hashlib
import httpx
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("kb-update")

RAG_SERVICE_URL = os.getenv("RAG_SERVICE_URL", "http://localhost:8003")


def compute_file_hash(filepath: str) -> str:
    """计算文件内容 hash"""
    hasher = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def main():
    parser = argparse.ArgumentParser(description="增量更新知识库")
    parser.add_argument("--docs-dir", required=True, help="文档目录")
    parser.add_argument("--state-file", default=".kb_state.json", help="状态文件路径")
    parser.add_argument("--api-url", default=RAG_SERVICE_URL, help="RAG 服务地址")
    args = parser.parse_args()

    docs_dir = Path(args.docs_dir)
    state_file = Path(args.state_file)

    # 加载上次状态
    previous_state = {}
    if state_file.exists():
        import json
        with open(state_file, "r") as f:
            previous_state = json.load(f)
    logger.info(f"上次状态: {len(previous_state)} 个文件")

    # 扫描当前文件
    supported_ext = {".txt", ".md", ".pdf", ".docx", ".html"}
    current_files = {
        str(f): compute_file_hash(str(f))
        for f in docs_dir.rglob("*")
        if f.suffix.lower() in supported_ext and not f.name.startswith(".")
    }

    # 对比变更
    new_files = set(current_files) - set(previous_state)
    deleted_files = set(previous_state) - set(current_files)
    modified_files = {
        f for f in set(current_files) & set(previous_state)
        if current_files[f] != previous_state[f]
    }

    logger.info(f"新增: {len(new_files)} | 修改: {len(modified_files)} | 删除: {len(deleted_files)}")

    client = httpx.Client(timeout=120.0)

    try:
        # 处理新增和修改的文件
        for fpath in list(new_files) + list(modified_files):
            logger.info(f"处理: {Path(fpath).name}")
            url = f"{args.api_url}/ingest"
            response = client.post(url, json={"filepath": fpath})
            if response.status_code == 200:
                logger.info(f"  成功: {response.json().get('chunks_created', 0)} 个分段")
            else:
                logger.error(f"  失败: {response.text}")

        # 处理删除的文件
        for fpath in deleted_files:
            doc_id = hashlib.md5(Path(fpath).name.encode()).hexdigest()[:12]
            logger.info(f"删除: {Path(fpath).name} (id={doc_id})")
            url = f"{args.api_url}/delete"
            response = client.post(url, json={"doc_id": doc_id})
            if response.status_code == 200:
                logger.info(f"  成功")

        # 保存新状态
        import json
        with open(state_file, "w") as f:
            json.dump(current_files, f, indent=2)
        logger.info(f"状态已保存: {len(current_files)} 个文件")

    except Exception as e:
        logger.error(f"更新失败: {e}")
        sys.exit(1)
    finally:
        client.close()


if __name__ == "__main__":
    main()
