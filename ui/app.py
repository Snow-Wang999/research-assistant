"""Gradio Web界面 - 支持流式输出"""
import gradio as gr
import sys
import time
from pathlib import Path
from datetime import datetime

# 添加src目录到路径
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
        title = paper.get('title', '未知标题')
        title_cn = paper.get('title_cn', '')
        source_tag = f" [{paper.get('source', '')}]" if show_source else ""

        if title_cn:
            output = f"**[{index}]{source_tag} {title}**\n\n"
            output += f"📖 *{title_cn}*\n\n"
        else:
            output = f"**[{index}]{source_tag} {title}**\n\n"

        authors = paper.get('authors', [])
        if authors:
            output += f"- 作者: {', '.join(authors[:3])}\n"
        output += f"- 年份: {paper.get('year', 'N/A')}\n"
        if paper.get("citation_count"):
            output += f"- 引用: {paper['citation_count']}\n"

        summary = paper.get('summary', '')
        if summary:
            output += f"- 📝 **摘要**: {summary}\n"
        elif paper.get("abstract"):
            abstract = paper['abstract']
            if len(abstract) > 200:
                abstract = abstract[:200] + "..."
            output += f"- 摘要: {abstract}\n"

        if paper.get('url'):
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

        if guide.get("categories"):
            lines.append(f"### 📂 论文分类\n")
            for cat in guide["categories"]:
                name = cat.get("name", "其他")
                desc = cat.get("description", "")
                papers = cat.get("papers", [])
                paper_nums = [str(p.get("index", "")) for p in papers]
                cat_text = f"#### {name} ({len(papers)}篇)\n"
                cat_text += f"- 论文编号: `{', '.join(paper_nums)}`\n"
                if desc:
                    cat_text += f"- 说明: {desc}\n"
                lines.append(cat_text)

        return "\n".join(lines)

    def search_papers_stream(query: str, mode: str = "auto"):
        """流式搜索论文 - 实时显示进度"""
        if not query.strip():
            yield "请输入研究问题", "", "", "", ""
            return

        start_time = datetime.now()
        actual_mode = "auto" if mode == "智能判断" else ("simple" if mode == "快速搜索" else "deep_research")

        # 阶段1: 显示开始状态
        start_time_str = start_time.strftime("%H:%M:%S")
        header = f"## 🔍 查询分析\n\n"
        header += f"**查询**: {query}\n\n"
        header += f"**模式**: {'🚀 深度研究' if actual_mode == 'deep_research' or (actual_mode == 'auto' and len(query) > 20) else '⚡ 快速搜索'}\n\n"
        header += f"**状态**: ⏳ 正在分析查询... (开始于 {start_time_str})\n"

        yield header, f"⏳ 正在分析问题，请稍候...\n\n> 开始时间: {start_time_str}，可点击「停止」按钮取消", "", "*🔄 搜索中...*", "*🔄 搜索中...*"

        # 阶段2: 执行搜索
        try:
            result = assistant.process_query(query, mode=actual_mode)
        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds()
            error_msg = f"## ❌ 搜索出错\n\n耗时: {elapsed:.1f}秒\n\n错误: {str(e)}"
            yield header.replace("⏳ 正在分析查询...", f"❌ 出错 ({elapsed:.1f}s)"), error_msg, "", "", ""
            return

        elapsed = (datetime.now() - start_time).total_seconds()

        # 更新 header
        header = f"## 🔍 查询分析\n\n"
        header += f"**意图**: {result.get('intent', '未识别')}\n\n"
        keywords = result.get('keywords', [])
        if keywords:
            header += f"**搜索关键词**: `{'`, `'.join(keywords)}`\n\n"
        mode_display = "🚀 深度研究" if result['mode'] == "deep_research" else "⚡ 快速搜索"
        header += f"**模式**: {mode_display} | "
        header += f"**搜索源**: {', '.join(result.get('sources', [])) or '无'} | "
        header += f"**找到**: {result.get('total_found', len(result.get('papers', [])))} 篇\n\n"
        header += f"**总耗时**: ✅ {elapsed:.1f}秒\n"

        # 深度研究模式：显示研究报告
        report_output = ""
        if result['mode'] == 'deep_research' and result.get('report'):
            # 显示子问题分解
            decomposition = result.get('decomposition', {})
            if decomposition:
                report_output += "## 📋 问题分解\n\n"
                report_output += f"**问题类型**: {decomposition.get('query_type', 'N/A')}\n\n"
                report_output += f"**研究策略**: {decomposition.get('strategy', 'N/A')}\n\n"
                sub_questions = decomposition.get('sub_questions', [])
                if sub_questions:
                    report_output += "**子问题**:\n"
                    for i, sq in enumerate(sub_questions, 1):
                        report_output += f"{i}. {sq.get('question', '')} *(目的: {sq.get('purpose', '')})*\n"
                    report_output += "\n"

            # 显示研究报告
            report_output += "---\n\n"
            report_output += result['report']

            # 显示元数据和各阶段耗时
            metadata = result.get('metadata', {})
            if metadata:
                report_output += "\n\n---\n"
                report_output += f"**总耗时: {metadata.get('duration_seconds', 0):.1f}秒** | "
                report_output += f"子问题: {metadata.get('sub_questions_count', 0)}个 | "
                report_output += f"论文: {metadata.get('total_papers', 0)}篇\n\n"

                # 显示各阶段耗时详情
                stage_times = metadata.get('stage_times', {})
                if stage_times:
                    report_output += "**⏱️ 各阶段耗时:**\n"
                    for stage, time_sec in stage_times.items():
                        stage_name = stage.split('_', 1)[1] if '_' in stage else stage
                        report_output += f"- {stage_name}: {time_sec:.1f}秒\n"

        # 阅读导航（快速搜索模式）
        reading_guide = result.get('reading_guide', {})
        guide_output = format_reading_guide(reading_guide) if result['mode'] == 'simple' else ""

        # 论文列表（深度研究模式使用原始搜索结果，独立于报告引用）
        if result['mode'] == 'deep_research':
            arxiv_papers = result.get('arxiv_papers', [])
            openalex_papers = result.get('openalex_papers', [])

            # arXiv 论文独立编号从1开始
            arxiv_output = f"### arXiv 最新论文 ({len(arxiv_papers)}篇)\n\n"
            arxiv_output += "> ℹ️ *以下编号与报告引用编号无关*\n\n"
            for i, paper in enumerate(arxiv_papers, 1):
                arxiv_output += format_paper(paper, i)
            if not arxiv_papers:
                arxiv_output += "*暂无结果*\n"

            # OpenAlex 论文独立编号从1开始
            openalex_output = f"### OpenAlex 经典论文 ({len(openalex_papers)}篇)\n\n"
            openalex_output += "> ℹ️ *以下编号与报告引用编号无关*\n\n"
            for i, paper in enumerate(openalex_papers, 1):
                openalex_output += format_paper(paper, i)
            if not openalex_papers:
                openalex_output += "*暂无结果*\n"
        else:
            arxiv_papers = result.get('arxiv_papers', [])
            openalex_papers = result.get('openalex_papers', [])

            arxiv_output = f"### arXiv 最新论文 ({len(arxiv_papers)}篇)\n\n"
            for i, paper in enumerate(arxiv_papers, 1):
                arxiv_output += format_paper(paper, i)
            if not arxiv_papers:
                arxiv_output += "*暂无结果*\n"

            start_index = len(arxiv_papers) + 1
            openalex_output = f"### OpenAlex 经典论文 ({len(openalex_papers)}篇)\n\n"
            for i, paper in enumerate(openalex_papers, start_index):
                openalex_output += format_paper(paper, i)
            if not openalex_papers:
                openalex_output += "*暂无结果*\n"

        yield header, report_output, guide_output, arxiv_output, openalex_output

    # 创建界面
    with gr.Blocks(title="科研助手", theme=gr.themes.Soft()) as app:
        gr.Markdown(
            """
            # 🔬 科研助手 v0.3.0

            输入你的研究问题，我会帮你搜索相关论文并提供阅读建议。

            **v0.3.0 新功能**:
            - 🚀 **深度研究模式**: 子问题分解 + 并行搜索 + 研究报告生成
            - ⏱️ **实时进度显示**: 显示各阶段耗时
            - ⏹️ **停止按钮**: 可随时取消搜索
            """
        )

        with gr.Row():
            query_input = gr.Textbox(
                label="研究问题",
                placeholder="例如：对比 Transformer 和 RNN 的优劣",
                lines=2,
                scale=3,
            )
            mode_selector = gr.Radio(
                choices=["智能判断", "快速搜索", "深度研究"],
                value="智能判断",
                label="搜索模式",
                scale=1,
            )

        with gr.Row():
            search_btn = gr.Button("🔍 搜索论文", variant="primary", scale=4)
            stop_btn = gr.Button("⏹️ 停止", variant="stop", scale=1)

        # 查询分析区
        header_output = gr.Markdown(label="查询分析")

        # 深度研究报告区
        report_output = gr.Markdown(label="研究报告")

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
                ["对比 Transformer 和 RNN 的优劣"],
                ["RAG在文档解析任务中的作用"],
                ["Transformer注意力机制"],
                ["大模型最新进展"],
            ],
            inputs=query_input,
        )

        # 搜索事件（流式输出）
        search_event = search_btn.click(
            fn=search_papers_stream,
            inputs=[query_input, mode_selector],
            outputs=[header_output, report_output, guide_output, arxiv_output, openalex_output]
        )
        submit_event = query_input.submit(
            fn=search_papers_stream,
            inputs=[query_input, mode_selector],
            outputs=[header_output, report_output, guide_output, arxiv_output, openalex_output]
        )

        # 停止按钮取消搜索
        stop_btn.click(
            fn=None,
            inputs=None,
            outputs=None,
            cancels=[search_event, submit_event]
        )

    return app


if __name__ == "__main__":
    app = create_app()
    app.launch(share=False)
