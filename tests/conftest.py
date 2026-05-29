"""测试配置和共享 fixtures"""

import pytest
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def sample_documents():
    """示例文档数据"""
    return [
        {
            "text": "变压器的日常巡检项目包括：油温检查、油位检查、声响检查、渗漏检查和套管检查。"
                    "上层油温不应超过85°C。油位应在油标刻度范围内。",
            "metadata": {
                "doc_id": "test001",
                "title": "变压器维护手册",
                "source_file": "test/transformer.md",
                "chunk_index": 0,
            },
        },
        {
            "text": "110kV变电站的安全距离不小于1.5米。作业人员必须佩戴安全帽、绝缘鞋、工作服。"
                    "特种作业人员需持相应特种作业操作证。",
            "metadata": {
                "doc_id": "test002",
                "title": "安全操作规程",
                "source_file": "test/safety.md",
                "chunk_index": 0,
            },
        },
        {
            "text": "SF6断路器的额定压力为0.6MPa。报警压力为0.52MPa，闭锁压力为0.5MPa。"
                    "定期检查SF6气体压力，确保在正常范围内。",
            "metadata": {
                "doc_id": "test003",
                "title": "断路器维护手册",
                "source_file": "test/breaker.md",
                "chunk_index": 0,
            },
        },
    ]


@pytest.fixture
def sample_queries():
    """测试查询列表"""
    return [
        {
            "query": "变压器的巡检项目有哪些？",
            "expected_keywords": ["油温", "油位", "声响", "渗漏", "套管"],
        },
        {
            "query": "110kV安全距离是多少？",
            "expected_keywords": ["1.5", "米"],
        },
        {
            "query": "SF6断路器额定压力？",
            "expected_keywords": ["0.6", "MPa"],
        },
    ]
