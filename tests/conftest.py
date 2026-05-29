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
            "text": "服务器的日常巡检项目包括：温度检查、风扇状态检查、磁盘健康检查和网络连通性检查。"
                    "CPU温度不应超过75°C。所有风扇应在正常转速范围内。",
            "metadata": {
                "doc_id": "test001",
                "title": "服务器维护手册",
                "source_file": "test/server.md",
                "chunk_index": 0,
            },
        },
        {
            "text": "访客进入数据中心需要提前24小时申请访问权限。所有人员必须佩戴工牌、登记身份信息。"
                    "第三方人员需签署保密协议后方可进入。",
            "metadata": {
                "doc_id": "test002",
                "title": "安全管理制度",
                "source_file": "test/safety.md",
                "chunk_index": 0,
            },
        },
        {
            "text": "防火墙的额定吞吐量为10Gbps。最大并发连接数为200万，新建连接速率为15万/秒。"
                    "定期检查防火墙规则状态，确保策略在有效期内。",
            "metadata": {
                "doc_id": "test003",
                "title": "网络设备维护手册",
                "source_file": "test/firewall.md",
                "chunk_index": 0,
            },
        },
    ]


@pytest.fixture
def sample_queries():
    """测试查询列表"""
    return [
        {
            "query": "服务器的巡检项目有哪些？",
            "expected_keywords": ["温度", "风扇", "磁盘", "网络"],
        },
        {
            "query": "数据中心访问权限如何申请？",
            "expected_keywords": ["24小时", "申请"],
        },
        {
            "query": "防火墙吞吐量是多少？",
            "expected_keywords": ["10Gbps", "Gbps"],
        },
    ]
