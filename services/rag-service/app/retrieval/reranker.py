"""重排序模块

在初步召回后，对候选文档片段进行精排。
采用两种策略：
1. 基于相似度分数的直接排序（简单场景）
2. 基于关键词匹配加权的混合排序（能源行业优化）
"""

import re
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class Reranker:
    """重排序器

    对检索结果进行精排，综合考虑：
    - 语义相似度（Embedding 距离）
    - 关键词覆盖度（能源行业术语匹配）
    - 文档来源权威性（正式文档 > 草稿）
    - 文本完整性（完整段落 > 截断片段）
    """

    # 能源行业核心关键词（用于加权）
    ENERGY_KEYWORDS_WEIGHTS = {
        "安全": 0.10,
        "操作": 0.08,
        "规程": 0.10,
        "标准": 0.08,
        "规范": 0.08,
        "维护": 0.05,
        "检修": 0.05,
        "电压": 0.05,
        "电流": 0.05,
        "设备": 0.05,
        "保护": 0.08,
        "接地": 0.06,
        "绝缘": 0.06,
    }

    def rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_n: int = 3,
    ) -> List[Dict[str, Any]]:
        """对候选文档重排序

        Args:
            query: 用户查询
            candidates: 候选文档列表
            top_n: 返回前 N 个结果

        Returns:
            重排序后的结果列表
        """
        if len(candidates) <= top_n:
            return candidates

        # 计算综合得分
        for cand in candidates:
            base_score = cand.get("score", 0.0)
            keyword_bonus = self._keyword_score(query, cand.get("text", ""))
            completeness_bonus = self._completeness_score(cand.get("text", ""))
            authority_bonus = self._authority_score(cand.get("metadata", {}))

            cand["_rerank_score"] = (
                base_score * 0.6
                + keyword_bonus * 0.25
                + completeness_bonus * 0.10
                + authority_bonus * 0.05
            )

        # 按综合得分排序
        reranked = sorted(
            candidates,
            key=lambda x: x.get("_rerank_score", 0),
            reverse=True,
        )

        return reranked[:top_n]

    def _keyword_score(self, query: str, text: str) -> float:
        """计算关键词覆盖得分"""
        query_lower = query.lower()
        text_lower = text.lower()

        score = 0.0
        for keyword, weight in self.ENERGY_KEYWORDS_WEIGHTS.items():
            if keyword.lower() in query_lower and keyword.lower() in text_lower:
                score += weight
        return min(score, 1.0)  # 归一化到 [0, 1]

    def _completeness_score(self, text: str) -> float:
        """评估文本完整性 —— 完整的段落得分更高"""
        score = 0.5  # 基础分

        # 有完整句子结尾
        if text.strip().endswith(("。", ".", "）", "）", "\n")):
            score += 0.2
        # 有标题结构
        if re.search(r'第[一二三四五六七八九十\d]+[章节条]', text):
            score += 0.15
        # 长度适中
        if 100 <= len(text) <= 1000:
            score += 0.15

        return min(score, 1.0)

    def _authority_score(self, metadata: Dict) -> float:
        """评估文档来源权威性"""
        source_file = metadata.get("source_file", "")
        title = metadata.get("title", "")
        combined = (source_file + title).lower()

        score = 0.5  # 基础分
        if any(kw in combined for kw in ["标准", "规程", "规范", "手册"]):
            score += 0.3
        if any(kw in combined for kw in ["gb", "dl", "iec", "国标"]):
            score += 0.2

        return min(score, 1.0)
