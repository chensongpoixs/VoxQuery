"""文档索引流水线

处理流程：
原始文档 → 文档解析 → 文本清洗 → 分段 → 向量化 → 向量入库
"""

import logging
import hashlib
import os
from typing import List, Dict, Optional, Callable
from pathlib import Path
import tempfile

from app.indexing.chunker import DocumentChunker

logger = logging.getLogger(__name__)


class IndexingPipeline:
    """索引流水线"""

    SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx", ".html", ".htm"}

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50):
        self.chunker = DocumentChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    def parse_file(self, filepath: str) -> str:
        """解析文件，提取文本内容"""
        ext = Path(filepath).suffix.lower()

        if ext == ".txt":
            return self._parse_txt(filepath)
        elif ext == ".md":
            return self._parse_txt(filepath)  # Markdown 直接读文本
        elif ext == ".pdf":
            return self._parse_pdf(filepath)
        elif ext == ".docx":
            return self._parse_docx(filepath)
        elif ext in (".html", ".htm"):
            return self._parse_html(filepath)
        else:
            raise ValueError(f"Unsupported file format: {ext}")

    def _parse_txt(self, filepath: str) -> str:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()

    def _parse_pdf(self, filepath: str) -> str:
        try:
            from pypdf import PdfReader
            reader = PdfReader(filepath)
            pages = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
            return "\n\n".join(pages)
        except ImportError:
            logger.warning("pypdf not installed, falling back to text extraction")
            return self._parse_txt(filepath)

    def _parse_docx(self, filepath: str) -> str:
        try:
            from docx import Document
            doc = Document(filepath)
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            return "\n".join(paragraphs)
        except ImportError:
            logger.warning("python-docx not installed")
            return self._parse_txt(filepath)

    def _parse_html(self, filepath: str) -> str:
        import re
        text = self._parse_txt(filepath)
        # 简易 HTML 标签清理
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'&[a-z]+;', ' ', text)
        return text

    def clean_text(self, text: str) -> str:
        """文本清洗"""
        import re

        # 统一换行
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        # 移除多余空行（保留最多 2 个连续换行）
        text = re.sub(r'\n{3,}', '\n\n', text)
        # 移除过多空格
        text = re.sub(r' {2,}', ' ', text)
        # 移除控制字符
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

        return text.strip()

    def process_file(
        self,
        filepath: str,
        strategy: str = "sliding_window",
    ) -> List[Dict]:
        """处理单个文件：解析 → 清洗 → 分段

        Args:
            filepath: 文件路径
            strategy: 分段策略

        Returns:
            分段列表
        """
        filename = Path(filepath).name
        doc_id = hashlib.md5(filename.encode()).hexdigest()[:12]

        logger.info(f"Processing: {filename}")
        text = self.parse_file(filepath)
        text = self.clean_text(text)

        if not text.strip():
            logger.warning(f"Empty content in {filename}, skipping")
            return []

        chunks = self.chunker.chunk_text(
            text=text,
            doc_id=doc_id,
            title=filename,
            source_file=filepath,
            strategy=strategy,
        )

        return chunks

    def process_directory(
        self,
        directory: str,
        strategy: str = "sliding_window",
        progress_callback: Optional[Callable] = None,
    ) -> List[Dict]:
        """批量处理目录下的所有文档

        Args:
            directory: 文档目录路径
            strategy: 分段策略
            progress_callback: 进度回调函数

        Returns:
            所有文档的分段列表
        """
        all_chunks = []
        dir_path = Path(directory)

        if not dir_path.exists():
            logger.error(f"Directory not found: {directory}")
            return []

        files = [
            f for f in dir_path.rglob("*")
            if f.suffix.lower() in self.SUPPORTED_EXTENSIONS
            and not f.name.startswith(".")
        ]

        logger.info(f"Found {len(files)} files in {directory}")

        for i, filepath in enumerate(files):
            try:
                chunks = self.process_file(str(filepath), strategy)
                all_chunks.extend(chunks)
                if progress_callback:
                    progress_callback(i + 1, len(files), filepath.name)
            except Exception as e:
                logger.error(f"Error processing {filepath}: {e}")

        logger.info(f"Indexing complete: {len(all_chunks)} chunks "
                    f"from {len(files)} files")
        return all_chunks
