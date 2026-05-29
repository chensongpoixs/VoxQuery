"""企业知识库同义词映射模块

解决企业内术语多样性的问题，支持自定义配置：
- 设备名称的同义表达
- 缩写与全称的对应
- 不同部门的称呼习惯差异

在同义词映射后扩展查询，提高检索命中率。
"""

import logging
from typing import List, Dict, Set, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


# 默认同义词映射表（请通过 YAML 文件自定义）
DEFAULT_SYNONYMS: Dict[str, List[str]] = {
    # 设备/产品类
    "服务器": ["Server", "主机", "服务器设备", "计算节点"],
    "防火墙": ["网络防火墙", "Firewall", "安全网关", "NGFW"],
    "交换机": ["网络交换机", "Switch", "交换设备", "数据交换机"],
    "存储设备": ["存储", "Storage", "磁盘阵列", "NAS", "SAN"],

    # 系统/平台类
    "ERP": ["企业资源计划", "ERP系统", "企业管理系统"],
    "CRM": ["客户关系管理", "CRM系统", "客户管理系统"],
    "OA": ["办公自动化", "OA系统", "协同办公"],
    "监控系统": ["监控平台", "运维监控", "系统监控", "网络监控"],

    # 参数类
    "吞吐量": ["吞吐率", "Throughput", "处理能力", "处理量"],
    "响应时间": ["延迟", "Latency", "RT", "响应延迟"],
    "可用性": ["高可用", "HA", "服务可用率", "Availability"],

    # 运维类
    "巡检": ["日常巡检", "例行检查", "巡检查看", "巡视检查"],
    "故障处理": ["故障排除", "故障修复", "问题解决", "Troubleshooting"],
    "备份": ["数据备份", "Backup", "灾备", "数据保护"],

    # 安全/合规类
    "访问控制": ["权限管理", "授权管理", "Access Control", "访问权限"],
    "身份认证": ["登录认证", "Authentication", "身份验证", "MFA", "多因素认证"],
    "数据加密": ["加密", "Encryption", "数据加解密", "密码保护"],
    "安全审计": ["日志审计", "Audit", "审计追踪", "操作审计"],
    "应急预案": ["应急响应", "灾难恢复", "DR", "应急计划"],
}


class SynonymMapper:
    """同义词映射器

    功能：
    1. 查询扩展：根据输入词找到所有同义词变体
    2. 术语标准化：将变体映射到标准术语
    3. 索引增强：在文档入库时为术语创建同义词索引
    """

    def __init__(self, synonyms_dict: Optional[Dict[str, List[str]]] = None):
        self.synonyms = synonyms_dict or DEFAULT_SYNONYMS
        self._standard_map: Dict[str, str] = {}
        self._build_reverse_map()

    def _build_reverse_map(self):
        """构建反向映射：变体 → 标准术语"""
        for standard, variants in self.synonyms.items():
            self._standard_map[standard.lower()] = standard  # 标准术语自身
            for variant in variants:
                self._standard_map[variant.lower()] = standard

    def normalize(self, term: str) -> str:
        """术语标准化：将任意变体映射到标准术语"""
        return self._standard_map.get(term.lower(), term)

    def expand_query(self, query: str) -> List[str]:
        """查询扩展：为查询中的术语生成同义词变体

        返回扩展后的查询变体列表，用于多路召回
        """
        expanded = [query]

        for standard, variants in self.synonyms.items():
            # 检查查询中是否包含标准术语或其变体
            all_terms = [standard] + variants
            for term in all_terms:
                if term.lower() in query.lower():
                    # 用其他变体替换，生成扩展查询
                    for alt in all_terms:
                        if alt.lower() != term.lower():
                            expanded_query = query.lower().replace(
                                term.lower(), alt.lower()
                            )
                            expanded.append(expanded_query)
                    break

        return list(set(expanded))  # 去重

    def add_synonym(self, standard: str, variants: List[str]):
        """动态添加同义词映射"""
        if standard not in self.synonyms:
            self.synonyms[standard] = []
        self.synonyms[standard].extend(variants)
        for v in variants:
            self._standard_map[v.lower()] = standard
        self._standard_map[standard.lower()] = standard

    def load_from_file(self, filepath: str):
        """从 YAML 文件加载同义词映射"""
        import yaml
        path = Path(filepath)
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if data:
                self.synonyms.update(data)
                self._build_reverse_map()
                logger.info(f"Loaded synonyms from {filepath}: {len(data)} groups")

    def get_synonym_count(self) -> int:
        return len(self.synonyms)
