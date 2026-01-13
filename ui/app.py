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
from tools.reading_guide import ReadingGuide


def create_app():
    """创建Gradio应用"""
    assistant = ResearchAssistant()

    def format_paper(paper: dict, index: int, show_source: bool = False) -> str:
        """格式化单篇论文"""
        # 标题：英文 + 中文翻译
        title = paper['title']
        title_cn = paper.get('title_cn', '')
        source_tag = f" [{paper.get('source', '')}]" if show_source else ""

        if title_cn:
            output = f"**[{index}]{source_tag} {title}**\n\n"
            output += f"📖 *{title_cn}*\n\n"
        else:
            output = f"**[{index}]{source_tag} {title}**\n\n"

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

    def format_reading_guide(guide: dict) -> str:
        """格式化阅读导航"""
        if not guide or guide.get("error"):
            return ""

        lines = ["## 📚 阅读建议\n"]

        if guide.get("summary"):
            lines.append(f"{guide['summary']}\n")

        if guide.get("entry_point"):
            ep = guide["entry_point"]
            title = ep.get('title', '')[:60]
            lines.append(f"### 🌟 入门必读")
            lines.append(f"**[{ep.get('index', '')}] {title}...**")
            lines.append(f"> {ep.get('reason', '')}\n")

        if guide.get("core_papers"):
            lines.append(f"### 📌 核心论文")
            for cp in guide["core_papers"]:
                title = cp.get('title', '')[:60]
                lines.append(f"- **[{cp.get('index', '')}] {title}...** → {cp.get('reason', '')}")
            lines.append("")

        if guide.get("latest"):
            lt = guide["latest"]
            title = lt.get('title', '')[:60]
            lines.append(f"### 🆕 最新进展")
            lines.append(f"**[{lt.get('index', '')}] {title}...**")
            lines.append(f"> {lt.get('reason', '')}\n")

        if guide.get("reading_order"):
            order = guide["reading_order"][:5]
            lines.append(f"### 📖 推荐阅读顺序")
            lines.append(f"**{' → '.join(map(str, order))}**\n")

        # 论文分类
        if guide.get("categories"):
            lines.append(f"### 📂 论文分类\n")
            for cat in guide["categories"]:
                name = cat.get("name", "其他")
                desc = cat.get("description", "")
                papers = cat.get("papers", [])
                paper_nums = [str(p.get("index", "")) for p in papers]
                # 使用 Markdown 列表格式，确保换行
                cat_text = f"#### {name} ({len(papers)}篇)\n"
                cat_text += f"- 论文编号: `{', '.join(paper_nums)}`\n"
                if desc:
                    cat_text += f"- 说明: {desc}\n"
                lines.append(cat_text)

        return "\n".join(lines)

    def search_papers(query: str, mode: str = "auto") -> tuple:
        """搜索论文，返回分栏结果"""
        if not query.strip():
            return "请输入研究问题", "", "", ""

        # 根据用户选择的模式搜索
        actual_mode = "auto" if mode == "智能判断" else ("simple" if mode == "快速搜索" else "deep_research")
        result = assistant.process_query(query, mode=actual_mode)

        # 查询分析信息
        header = f"## 🔍 查询分析\n\n"
        header += f"**意图**: {result.get('intent', '未识别')}\n\n"
        keywords = result.get('keywords', [])
        if keywords:
            header += f"**搜索关键词**: `{'`, `'.join(keywords)}`\n\n"
        mode_display = "🚀 深度研究" if result['mode'] == "deep_research" else "⚡ 快速搜索"
        header += f"**模式**: {mode_display} | "
        header += f"**搜索源**: {', '.join(result.get('sources', [])) or '无'} | "
        header += f"**找到**: {result.get('total_found', len(result.get('papers', [])))} 篇\n\n"

        # 阅读导航
        reading_guide = result.get('reading_guide', {})
        guide_output = format_reading_guide(reading_guide)

        # 统一编号：arXiv 先编，OpenAlex 接着编
        arxiv_papers = result.get('arxiv_papers', [])
        openalex_papers = result.get('openalex_papers', [])

        # arXiv 论文（左栏）：编号 1, 2, 3...
        arxiv_output = f"### arXiv 最新论文 ({len(arxiv_papers)}篇)\n\n"
        for i, paper in enumerate(arxiv_papers, 1):
            arxiv_output += format_paper(paper, i)
        if not arxiv_papers:
            arxiv_output += "*暂无结果*\n"

        # OpenAlex 论文（右栏）：编号从 arXiv 后续接
        start_index = len(arxiv_papers) + 1
        openalex_output = f"### OpenAlex 经典论文 ({len(openalex_papers)}篇)\n\n"
        for i, paper in enumerate(openalex_papers, start_index):
            openalex_output += format_paper(paper, i)
        if not openalex_papers:
            openalex_output += "*暂无结果*\n"

        return header, guide_output, arxiv_output, openalex_output

    # 创建界面
    with gr.Blocks(title="科研助手", theme=gr.themes.Soft()) as app:
        gr.Markdown(
            """
            # 🔬 科研助手 v0.2.0

            输入你的研究问题，我会帮你搜索相关论文并提供阅读建议。

            **新功能**:
            - 🧠 智能查询分析（自动生成多组搜索关键词）
            - 📚 阅读导航（推荐入门论文、核心论文、最新进展）
            - 📝 摘要中文总结
            """
        )

        with gr.Row():
            query_input = gr.Textbox(
                label="研究问题",
                placeholder="例如：RAG在文档解析任务中的作用",
                lines=2,
                scale=3,
            )
            mode_selector = gr.Radio(
                choices=["智能判断", "快速搜索", "深度研究"],
                value="智能判断",
                label="搜索模式",
                scale=1,
            )

        search_btn = gr.Button("🔍 搜索论文", variant="primary")

        # 查询分析区
        header_output = gr.Markdown(label="查询分析")

        # 阅读导航区
        guide_output = gr.Markdown(label="阅读建议")

        # 分栏显示结果
        with gr.Row():
            with gr.Column():
                arxiv_output = gr.Markdown(label="arXiv论文")
            with gr.Column():
                openalex_output = gr.Markdown(label="OpenAlex论文")

        # 示例
        gr.Examples(
            examples=[
                ["RAG在文档解析任务中的作用"],
                ["Transformer注意力机制"],
                ["对比Transformer和Mamba的优劣"],
                ["大模型最新进展"],
            ],
            inputs=query_input,
        )

        search_btn.click(
            fn=search_papers,
            inputs=[query_input, mode_selector],
            outputs=[header_output, guide_output, arxiv_output, openalex_output]
        )
        query_input.submit(
            fn=search_papers,
            inputs=[query_input, mode_selector],
            outputs=[header_output, guide_output, arxiv_output, openalex_output]
        )

    return app


if __name__ == "__main__":
    app = create_app()
    # share=False: 仅本地访问 http://127.0.0.1:7860
    # share=True:  生成公开链接（72小时有效）
    app.launch(share=False)
