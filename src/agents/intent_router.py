"""意图路由 Agent"""
from typing import Literal


class IntentRouter:
    """意图路由：决定使用 RAG 还是 Deep Research 模式"""

    # 简单模式的关键词
    SIMPLE_KEYWORDS = ["是什么", "什么是", "定义", "介绍", "作者是谁", "哪一年"]

    # 复杂模式的关键词
    COMPLEX_KEYWORDS = ["对比", "比较", "区别", "优劣", "综述", "进展", "趋势", "分析"]

    def route(self, query: str) -> Literal["simple", "deep_research"]:
        """路由用户查询（简单规则版，后续可替换为LLM）"""
        query_lower = query.lower()

        # 检查是否包含复杂模式关键词
        for keyword in self.COMPLEX_KEYWORDS:
            if keyword in query_lower:
                return "deep_research"

        # 检查是否包含简单模式关键词
        for keyword in self.SIMPLE_KEYWORDS:
            if keyword in query_lower:
                return "simple"

        # 默认：根据查询长度判断
        if len(query) > 30:
            return "deep_research"

        return "simple"


# 测试代码
if __name__ == "__main__":
    router = IntentRouter()

    test_queries = [
        "Transformer是什么",
        "对比Transformer和Mamba的优劣",
        "BERT的作者是谁",
        "大模型领域最新的研究进展有哪些",
    ]

    print("意图路由测试:\n")
    for query in test_queries:
        mode = router.route(query)
        print(f"查询: {query}")
        print(f"模式: {mode}\n")
