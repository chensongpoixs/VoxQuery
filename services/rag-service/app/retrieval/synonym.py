"""能源行业同义词映射模块

解决能源行业术语多样性的问题：
- "变压器" = "变压器设备" = "主变" = "电力变压器"
- "断路器" = "开关" = "高压开关"
- "GIS" = "气体绝缘开关设备" = "SF6开关设备"

在同义词映射后扩展查询，提高检索命中率。
"""

import logging
from typing import List, Dict, Set, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


# 能源行业核心同义词映射表
ENERGY_SYNONYMS: Dict[str, List[str]] = {
    # 设备类
    "变压器": ["主变", "电力变压器", "变压器设备", "配电变压器"],
    "断路器": ["高压断路器", "开关", "高压开关", "真空断路器", "SF6断路器"],
    "隔离开关": ["刀闸", "隔离刀闸", "高压隔离开关"],
    "互感器": ["电压互感器", "PT", "电流互感器", "CT"],
    "避雷器": ["过电压保护器", "氧化锌避雷器", "浪涌保护器"],
    "GIS": ["气体绝缘开关设备", "SF6开关设备", "GIS设备", "封闭式组合电器"],
    "开关柜": ["高压开关柜", "低压开关柜", "配电柜", "MCC柜"],
    "电缆": ["电力电缆", "高压电缆", "中压电缆", "控制电缆"],

    # 系统类
    "变电站": ["变电所", "升压站", "降压站", "配电站"],
    "输电线路": ["送电线路", "架空线路", "高压线路", "电力线路"],
    "配电系统": ["配电网络", "配电网", "配电线路"],
    "继电保护": ["保护装置", "继保", "保护系统", "微机保护"],
    "SCADA": ["监控系统", "数据采集与监视控制", "远动系统"],

    # 参数类
    "额定电压": ["标称电压", "运行电压", "系统电压", "工作电压"],
    "额定电流": ["标称电流", "工作电流", "载流量"],
    "短路容量": ["短路电流", "短路水平", "短路功率"],
    "绝缘水平": ["绝缘强度", "耐压水平", "绝缘等级"],

    # 运维类
    "预防性试验": ["预防性测试", "定期试验", "预防性检修"],
    "状态检修": ["在线监测", "状态监测", "预知性维护"],
    "巡检": ["巡视检查", "日常巡检", "设备巡视"],
    "故障诊断": ["故障分析", "缺陷诊断", "异常诊断"],

    # 安全类
    "工作票": ["第一种工作票", "第二种工作票", "作业票"],
    "操作票": ["倒闸操作票", "调度操作票"],
    "安全距离": ["安全间距", "电气安全距离", "带电距离"],
    "接地保护": ["保护接地", "工作接地", "接地装置"],
}


class SynonymMapper:
    """同义词映射器

    功能：
    1. 查询扩展：根据输入词找到所有同义词变体
    2. 术语标准化：将变体映射到标准术语
    3. 索引增强：在文档入库时为术语创建同义词索引
    """

    def __init__(self, synonyms_dict: Optional[Dict[str, List[str]]] = None):
        self.synonyms = synonyms_dict or ENERGY_SYNONYMS
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
