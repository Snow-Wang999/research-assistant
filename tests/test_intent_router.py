"""意图路由测试"""
import pytest
from src.agents.intent_router import IntentRouter


class TestIntentRouter:
    """意图路由器测试类"""

    def setup_method(self):
        """每个测试方法前执行"""
        self.router = IntentRouter()

    def test_simple_keywords(self):
        """测试简单查询关键词"""
        simple_queries = [
            "Transformer是什么",
            "什么是注意力机制",
            "BERT的定义",
            "GPT作者是谁",
        ]
        for query in simple_queries:
            assert self.router.route(query) == "simple", f"查询 '{query}' 应该路由到 simple"

    def test_deep_research_keywords(self):
        """测试深度研究关键词"""
        deep_queries = [
            "对比Transformer和RNN",
            "比较不同的优化器",
            "分析大模型的发展趋势",
            "综述强化学习的研究进展",
        ]
        for query in deep_queries:
            assert self.router.route(query) == "deep_research", f"查询 '{query}' 应该路由到 deep_research"

    def test_length_based_routing(self):
        """测试基于长度的路由"""
        short_query = "GPT参数量"
        long_query = "请详细分析一下大语言模型在自然语言处理领域的各种应用场景"

        # 短查询默认走simple
        assert self.router.route(short_query) == "simple"

        # 长查询（>30字符）走deep_research
        assert self.router.route(long_query) == "deep_research"

    def test_mixed_keywords(self):
        """测试混合关键词（复杂关键词优先）"""
        # 同时包含简单和复杂关键词时，复杂关键词优先
        query = "什么是Transformer，对比RNN有什么区别"
        assert self.router.route(query) == "deep_research"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
