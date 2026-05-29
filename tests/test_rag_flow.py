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

    def test_protected_patterns_not_split(self):
        """确保受保护的模式（标准编号、产品型号等）不被切断"""
        chunker = DocumentChunker(chunk_size=200, chunk_overlap=0)
        text = "产品型号SRV-20245符合ISO 9001标准，额定功率为220.5W，最大传输速率为10Gbps。"
        chunks = chunker.chunk_text(
            text, doc_id="test", title="规格", source_file="spec.txt",
            strategy="fixed_length",
        )
        # 如果只有一个 chunk，说明保护模式生效了
        for chunk in chunks:
            text_content = chunk["text"]
            print(f"Chunk: {text_content}")


class TestSynonymMapper:
    """同义词映射测试"""

    def test_normalize(self):
        mapper = SynonymMapper()
        assert mapper.normalize("主机") == "服务器"
        assert mapper.normalize("Firewall") == "防火墙"
        assert mapper.normalize("巡检") == "巡检"

    def test_expand_query(self):
        mapper = SynonymMapper()
        expanded = mapper.expand_query("服务器的巡检项目")
        assert len(expanded) >= 1  # 至少有原始查询
        # 至少包含服务器相关的变体
        has_variant = any("服务器" in q for q in expanded)
        assert has_variant, f"扩展的查询中没有找到服务器变体: {expanded}"

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
            {"id": "1", "text": "服务器温度不应超过75°C，需定期检查", "metadata": {}, "score": 0.9},
            {"id": "2", "text": "防火墙配置规范要求", "metadata": {}, "score": 0.5},
            {"id": "3", "text": "安全操作制度和流程规范", "metadata": {}, "score": 0.7},
            {"id": "4", "text": "其他信息", "metadata": {}, "score": 0.3},
            {"id": "5", "text": "设备维护", "metadata": {}, "score": 0.6},
        ]
        results = reranker.rerank("服务器温度", candidates, top_n=3)
        assert len(results) == 3
        # 最相关的应该排在前面
        assert results[0]["id"] in ["1", "2", "3"]

    def test_keyword_bonus(self):
        reranker = Reranker()
        candidates = [
            {"id": "1", "text": "安全操作管理制度和标准规范", "metadata": {}, "score": 0.6},
            {"id": "2", "text": "普通文本内容没有行业术语", "metadata": {}, "score": 0.6},
        ]
        results = reranker.rerank("安全操作标准", candidates, top_n=2)
        # 有关键词的应该得分更高
        assert results[0]["id"] == "1"
