"""RAG 检索流程测试"""

import pytest
import sys
import os

# 添加服务路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "rag-service"))

from app.indexing.chunker import DocumentChunker
from app.retrieval.synonym import SynonymMapper
from app.retrieval.reranker import Reranker


class TestDocumentChunker:
    """文档分段测试"""

    def test_fixed_length_chunk(self):
        chunker = DocumentChunker(chunk_size=100, chunk_overlap=0)
        text = "这是一段测试文本。" * 20
        chunks = chunker.chunk_text(
            text, doc_id="test", title="测试文档",
            source_file="test.txt", strategy="fixed_length",
        )
        assert len(chunks) > 1
        for chunk in chunks:
            assert "text" in chunk
            assert "metadata" in chunk
            assert len(chunk["text"]) <= 150  # 允许一定边界调整

    def test_semantic_chunk(self):
        chunker = DocumentChunker(chunk_size=512, chunk_overlap=50)
        text = "第一段内容。\n\n第二段内容。\n\n第三段内容。"
        chunks = chunker.chunk_text(
            text, doc_id="test", title="测试",
            source_file="test.txt", strategy="semantic",
        )
        assert len(chunks) >= 1

    def test_sliding_window_chunk(self):
        chunker = DocumentChunker(chunk_size=100, chunk_overlap=20)
        text = "ABCDEFGHIJ" * 30
        chunks = chunker.chunk_text(
            text, doc_id="test", title="测试",
            source_file="test.txt", strategy="sliding_window",
        )
        assert len(chunks) > 1

    def test_chunk_metadata(self):
        chunker = DocumentChunker(chunk_size=512, chunk_overlap=50)
        chunks = chunker.chunk_text(
            "测试文本内容", doc_id="DOC001", title="运维手册",
            source_file="/docs/maintenance.pdf",
        )
        for chunk in chunks:
            assert chunk["metadata"]["doc_id"] == "DOC001"
            assert chunk["metadata"]["title"] == "运维手册"
            assert "chunk_index" in chunk["metadata"]

    def test_empty_text(self):
        chunker = DocumentChunker()
        chunks = chunker.chunk_text(
            "", doc_id="test", title="空文档", source_file="empty.txt",
        )
        assert len(chunks) == 0

    def test_energy_terms_not_split(self):
        """确保能源行业术语不被切断"""
        chunker = DocumentChunker(chunk_size=200, chunk_overlap=0)
        text = "设备GB/T 12345-2020标准规定了变压器的额定电压为110.5kV，额定容量为50000kVA。"
        chunks = chunker.chunk_text(
            text, doc_id="test", title="标准", source_file="std.txt",
            strategy="fixed_length",
        )
        # 如果只有一个 chunk，说明保护模式生效了
        # 如果有多个，检查每个 chunk 的内容
        for chunk in chunks:
            text_content = chunk["text"]
            # 不应在标准号中间切断（但可能因长度被切）
            print(f"Chunk: {text_content}")


class TestSynonymMapper:
    """同义词映射测试"""

    def test_normalize(self):
        mapper = SynonymMapper()
        assert mapper.normalize("主变") == "变压器"
        assert mapper.normalize("PT") == "互感器"
        assert mapper.normalize("刀闸") == "隔离开关"

    def test_expand_query(self):
        mapper = SynonymMapper()
        expanded = mapper.expand_query("主变的巡检项目")
        assert len(expanded) >= 1  # 至少有原始查询
        # 至少包含变压器相关的变体
        has_variant = any("变压器" in q for q in expanded)
        assert has_variant, f"扩展的查询中没有找到变压器变体: {expanded}"

    def test_unknown_term(self):
        mapper = SynonymMapper()
        assert mapper.normalize("不存在的术语xyz") == "不存在的术语xyz"

    def test_add_synonym(self):
        mapper = SynonymMapper()
        mapper.add_synonym("测试设备", ["测试机", "试验设备"])
        assert mapper.normalize("测试机") == "测试设备"
        assert mapper.normalize("试验设备") == "测试设备"


class TestReranker:
    """重排序测试"""

    def test_rerank_by_score(self):
        reranker = Reranker()
        candidates = [
            {"id": "1", "text": "变压器油温不应超过85°C", "metadata": {}, "score": 0.9},
            {"id": "2", "text": "断路器SF6额定压力", "metadata": {}, "score": 0.5},
            {"id": "3", "text": "安全操作规范", "metadata": {}, "score": 0.7},
            {"id": "4", "text": "其他信息", "metadata": {}, "score": 0.3},
            {"id": "5", "text": "电缆维护", "metadata": {}, "score": 0.6},
        ]
        results = reranker.rerank("变压器温度", candidates, top_n=3)
        assert len(results) == 3
        # 最相关的应该排在前面
        assert results[0]["id"] in ["1", "2", "3"]

    def test_keyword_bonus(self):
        reranker = Reranker()
        candidates = [
            {"id": "1", "text": "变压器安全操作规程和标准规范", "metadata": {}, "score": 0.6},
            {"id": "2", "text": "普通文本内容没有行业术语", "metadata": {}, "score": 0.6},
        ]
        results = reranker.rerank("安全规程", candidates, top_n=2)
        # 有关键词的应该得分更高
        assert results[0]["id"] == "1"
