"""Gradio Web界面"""
import gradio as gr
import sys
from pathlib import Path

# 添加src目录到路径（无论从哪里运行都能正确导入）
project_root = Path(__file__).parent.parent
src_dir = project_root / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from main import ResearchAssistant


def create_app():
    """创建Gradio应用"""
    assistant = ResearchAssistant()

    def format_paper(paper: dict, index: int) -> str:
        """格式化单篇论文"""
        # 标题：英文 + 中文翻译
        title = paper['title']
        title_cn = paper.get('title_cn', '')
        if title_cn:
            output = f"**[{index}] {title}**\n\n"
            output += f"📖 *{title_cn}*\n\n"
        else:
            output = f"**[{index}] {title}**\n\n"

        output += f"- 作者: {', '.join(paper['authors'])}\n"
        output += f"- 年份: {paper.get('year', 'N/A')}\n"
        if paper.get("citation_count"):
            output += f"- 引用: {paper['citation_count']}\n"

        # 摘要：优先显示LLM总结，否则显示原始摘要
        summary = paper.get('summary', '')
        if summary:
            output += f"- 📝 **摘要**: {summary}\n"
        elif paper.get("abstract"):
            abstract = paper['abstract']
            if len(abstract) > 200:
                abstract = abstract[:200] + "..."
            output += f"- 摘要: {abstract}\n"

        output += f"- [🔗 查看论文]({paper['url']})\n\n"
        output += "---\n\n"
        return output

    def search_papers(query: str) -> tuple:
        """搜索论文，返回分栏结果"""
        if not query.strip():
            return "请输入研究问题", "", ""

        result = assistant.process_query(query)

        # 顶部信息
        header = f"## 查询模式: {result['mode']}\n\n"
        search_query = result.get('search_query', query)
        if search_query != query:
            header += f"**原始查询**: {query}\n\n"
            header += f"**搜索关键词**: `{search_query}`\n\n"
        header += f"**搜索源**: {', '.join(result.get('sources', [])) or '无'}\n\n"

        # arXiv 论文（左栏）
        arxiv_papers = result.get('arxiv_papers', [])
        arxiv_output = f"### arXiv 最新论文 ({len(arxiv_papers)}篇)\n\n"
        for i, paper in enumerate(arxiv_papers, 1):
            arxiv_output += format_paper(paper, i)
        if not arxiv_papers:
            arxiv_output += "*暂无结果*\n"

        # OpenAlex 论文（右栏）
        openalex_papers = result.get('openalex_papers', [])
        openalex_output = f"### OpenAlex 经典论文 ({len(openalex_papers)}篇)\n\n"
        for i, paper in enumerate(openalex_papers, 1):
            openalex_output += format_paper(paper, i)
        if not openalex_papers:
            openalex_output += "*暂无结果*\n"

        return header, arxiv_output, openalex_output

    # 创建界面
    with gr.Blocks(title="科研助手", theme=gr.themes.Soft()) as app:
        gr.Markdown(
            """
            # 科研助手 v0.1.0

            输入你的研究问题，我会帮你搜索相关论文。

            - **简单查询**（如"Transformer是什么"）→ 快速检索模式
            - **复杂查询**（如"对比Transformer和Mamba"）→ 深度研究模式
            """
        )

        with gr.Row():
            query_input = gr.Textbox(
                label="研究问题",
                placeholder="例如：Transformer注意力机制的原理是什么？",
                lines=2,
            )

        search_btn = gr.Button("搜索论文", variant="primary")

        # 顶部信息区
        header_output = gr.Markdown(label="查询信息")

        # 分栏显示结果
        with gr.Row():
            with gr.Column():
                arxiv_output = gr.Markdown(label="arXiv论文")
            with gr.Column():
                openalex_output = gr.Markdown(label="OpenAlex论文")

        # 示例
        gr.Examples(
            examples=[
                ["Transformer是什么"],
                ["对比Transformer和Mamba的优劣"],
                ["大模型领域最新的研究进展"],
                ["BERT的作者是谁"],
            ],
            inputs=query_input,
        )

        search_btn.click(
            fn=search_papers,
            inputs=query_input,
            outputs=[header_output, arxiv_output, openalex_output]
        )
        query_input.submit(
            fn=search_papers,
            inputs=query_input,
            outputs=[header_output, arxiv_output, openalex_output]
        )

    return app


if __name__ == "__main__":
    app = create_app()
    # share=False: 仅本地访问 http://127.0.0.1:7860
    # share=True:  生成公开链接（72小时有效）
    app.launch(share=False)
