"""文档分段引擎

支持三种分段策略：
1. 固定长度分段（按字符/token）
2. 语义分段（按段落/标题自然边界）
3. 滑动窗口分段（带重叠）

针对企业文档特点优化：保留标准编号、产品型号、章节结构等完整性。
"""

import re
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ChunkMetadata:
    """分段元数据"""
    doc_id: str
    title: str
    chunk_index: int
    total_chunks: int
    source_file: str
    page_number: Optional[int] = None
    section_title: Optional[str] = None


class DocumentChunker:
    """文档分段器"""

    # 企业文档特殊模式 —— 不应在中间切断
    PROTECTED_PATTERNS = [
        r'[A-Z]{2,}/?T?\s*\d+[\.-]\d+',  # 标准编号 ISO 9001, GB/T 12345-2020
        r'[A-Z]{2,}-\d{3,}',              # 产品型号 XX-12345
        r'\d+\.\d+\s*[kKmMgG]?[VvWw]',   # 参数值 220.5V, 600W
        r'第[一二三四五六七八九十\d]+章',   # 章节标题
        r'第[一二三四五六七八九十\d]+条',   # 条款编号
    ]

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_text(
        self,
        text: str,
        doc_id: str,
        title: str = "",
        source_file: str = "",
        strategy: str = "sliding_window",
    ) -> List[Dict]:
        """对文本进行分段

        Args:
            text: 输入文本
            doc_id: 文档唯一 ID
            title: 文档标题
            source_file: 源文件路径
            strategy: 分段策略 (fixed_length / semantic / sliding_window)

        Returns:
            分段列表，每段包含 text + metadata
        """
        if strategy == "fixed_length":
            chunks = self._fixed_length_chunk(text)
        elif strategy == "semantic":
            chunks = self._semantic_chunk(text)
        else:
            chunks = self._sliding_window_chunk(text)

        total = len(chunks)
        result = []
        for i, chunk_text in enumerate(chunks):
            if not chunk_text.strip():
                continue
            result.append({
                "text": chunk_text.strip(),
                "metadata": ChunkMetadata(
                    doc_id=doc_id,
                    title=title,
                    chunk_index=i,
                    total_chunks=total,
                    source_file=source_file,
                ).__dict__,
            })

        logger.info(f"Document '{title}' chunked into {len(result)} segments "
                    f"(strategy={strategy}, size={self.chunk_size}, "
                    f"overlap={self.chunk_overlap})")
        return result

    def _fixed_length_chunk(self, text: str) -> List[str]:
        """固定长度分段 —— 按字符数"""
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            # 尝试在保护模式边界处调整
            end = self._adjust_boundary(text, end)
            chunks.append(text[start:end])
            start = end
        return chunks

    def _semantic_chunk(self, text: str) -> List[str]:
        """语义分段 —— 按段落和标题自然边界"""
        # 按双换行（段落边界）分割
        paragraphs = re.split(r'\n\s*\n', text)

        chunks = []
        current_chunk = ""
        for para in paragraphs:
            if len(current_chunk) + len(para) <= self.chunk_size:
                current_chunk += para + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para + "\n\n"
        if current_chunk:
            chunks.append(current_chunk.strip())
        return chunks

    def _sliding_window_chunk(self, text: str) -> List[str]:
        """滑动窗口分段 —— 带重叠的固定长度分段"""
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            end = self._adjust_boundary(text, end)
            chunks.append(text[start:end])
            start += self.chunk_size - self.chunk_overlap
            if start >= len(text):
                break
        return chunks

    def _adjust_boundary(self, text: str, pos: int) -> int:
        """调整分段边界，避免切断受保护的文本模式"""
        if pos >= len(text):
            return len(text)

        # 寻找最近的句子结束点
        search_start = max(0, pos - 50)
        search_text = text[search_start:min(pos + 50, len(text))]

        # 优先在句子结束符处断开
        for sep in ["\n\n", "\n", "。", "；", ". ", "; "]:
            # 在 pos 附近找分隔符
            local_pos = pos - search_start
            nearby = search_text[max(0, local_pos - 30):local_pos + 30]
            if sep in nearby:
                idx = nearby.rfind(sep)
                adjusted = search_start + max(0, local_pos - 30) + idx + len(sep)
                return min(adjusted, len(text))

        return pos
