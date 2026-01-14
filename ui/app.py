"""Gradio Web界面 - Tab + Sidebar架构 v0.4.0"""
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
from tools.pdf import PaperProcessor


def create_app():
    """创建Gradio应用"""
    assistant = ResearchAssistant()
    pdf_processor = PaperProcessor()

    def show_paper_details(paper_json: str) -> str:
        """显示论文详情到侧边栏"""
        if not paper_json or paper_json == "{}":
            return "## 📄 论文详情\n\n点击论文标题查看详细信息"

        import json
        try:
            paper = json.loads(paper_json)
        except:
            return "## 📄 论文详情\n\n数据解析失败"

        output = "## 📄 论文详情\n\n"

        # 标题
        title = paper.get('title', '未知标题')
        output += f"### {title}\n\n"

        # 中文标题（如果有）
        title_cn = paper.get('title_cn', '')
        if title_cn:
            output += f"*{title_cn}*\n\n"

        # 作者
        authors = paper.get('authors', [])
        if authors:
            output += f"**👥 作者**: {', '.join(authors[:5])}\n\n"

        # 年份、引用数
        year = paper.get('year', 'N/A')
        output += f"**📅 年份**: {year}\n\n"

        citation_count = paper.get('citation_count')
        if citation_count:
            output += f"**📊 引用数**: {citation_count}\n\n"

        # 来源
        source = paper.get('source', '').upper()
        if source:
            output += f"**🔖 来源**: {source}\n\n"

        # 摘要
        abstract = paper.get('abstract', '')
        summary = paper.get('summary', '')  # LLM生成的中文摘要

        if summary:
            output += f"**📝 摘要** (AI生成):\n\n{summary}\n\n"

        if abstract:
            output += f"**📄 原文摘要**:\n\n{abstract}\n\n"

        # URL
        url = paper.get('url', '')
        if url:
            output += f"**🔗 链接**: [{url}]({url})\n\n"

        # arXiv ID（如果是arXiv论文，显示获取全文按钮提示）
        if source == 'ARXIV' and url:
            import re
            match = re.search(r'(\d{4}\.\d{4,5})', url)
            if match:
                arxiv_id = match.group(1)
                output += f"\n---\n\n💡 **提示**: 这是 arXiv 论文，可在深度研究模式中勾选「使用全文研究」来获取 PDF 全文。\n\n"

        return output

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

    def search_papers_stream(query: str, mode: str = "auto", use_fulltext: bool = False):
        """流式搜索论文 - 实时显示进度

        Args:
            query: 查询字符串
            mode: 搜索模式 ("auto", "simple", "deep_research")
            use_fulltext: 是否使用全文研究（仅深度研究模式有效）
        """
        if not query.strip():
            yield "请输入研究问题", "", "", "", "", "{}"
            return

        start_time = datetime.now()
        actual_mode = "auto" if mode == "智能判断" else ("simple" if mode == "快速搜索" else "deep_research")

        # 阶段1: 显示开始状态
        start_time_str = start_time.strftime("%H:%M:%S")
        header = f"## 🔍 查询分析\n\n"
        header += f"**查询**: {query}\n\n"

        # 显示模式（包括全文研究状态）
        if actual_mode == 'deep_research' or (actual_mode == 'auto' and len(query) > 20):
            mode_display = "🚀 深度研究"
            if use_fulltext:
                mode_display += " (📄 全文模式)"
        else:
            mode_display = "⚡ 快速搜索"

        header += f"**模式**: {mode_display}\n\n"
        header += f"**状态**: ⏳ 正在分析查询... (开始于 {start_time_str})\n"

        yield header, f"⏳ 正在分析问题，请稍候...\n\n> 开始时间: {start_time_str}，可点击「停止」按钮取消", "", "*🔄 搜索中...*", "*🔄 搜索中...*", "{}"

        # 阶段2: 执行搜索（传入 use_fulltext 参数）
        try:
            result = assistant.process_query(query, mode=actual_mode, use_fulltext=use_fulltext)
        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds()
            error_msg = f"## ❌ 搜索出错\n\n耗时: {elapsed:.1f}秒\n\n错误: {str(e)}"
            yield header.replace("⏳ 正在分析查询...", f"❌ 出错 ({elapsed:.1f}s)"), error_msg, "", "", "", "{}"
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
        # 同时准备 papers_list_json 供侧边栏选择
        import json
        papers_list = []

        if result['mode'] == 'deep_research':
            arxiv_papers = result.get('arxiv_papers', [])
            openalex_papers = result.get('openalex_papers', [])
            papers_list = arxiv_papers + openalex_papers  # 合并用于侧边栏

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
            papers_list = arxiv_papers + openalex_papers

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

        # 返回论文列表JSON供侧边栏使用
        papers_json = json.dumps(papers_list, ensure_ascii=False)

        yield header, report_output, guide_output, arxiv_output, openalex_output, papers_json

    def analyze_pdf(pdf_file):
        """分析上传的 PDF 文件"""
        if pdf_file is None:
            return "请先上传 PDF 文件", "", "", ""

        try:
            # 获取文件路径
            pdf_path = pdf_file.name if hasattr(pdf_file, 'name') else str(pdf_file)

            # 处理 PDF
            result = pdf_processor.process_local_pdf(pdf_path)

            if not result.success:
                return f"## ❌ 分析失败\n\n{result.error}", "", "", ""

            # 构建结果
            header = f"## ✅ 分析完成\n\n"
            header += f"**标题**: {result.title}\n\n"
            header += f"**页数**: {result.total_pages}\n\n"
            header += f"**全文长度**: {len(result.full_text)} 字符\n\n"
            header += f"**切片数**: {len(result.chunks)}\n"

            # 摘要
            abstract = ""
            if result.abstract:
                abstract = f"### 📝 摘要\n\n{result.abstract}"
            else:
                abstract = "*未能自动提取摘要*"

            # 全文预览
            fulltext_preview = result.full_text[:3000] if result.full_text else "无法提取全文"

            # 切片信息
            chunks_info = "### 📊 切片统计\n\n"
            if result.chunks:
                total_tokens = sum(c.token_count for c in result.chunks)
                avg_tokens = total_tokens / len(result.chunks)
                chunks_info += f"- 切片数量: {len(result.chunks)}\n"
                chunks_info += f"- 总 Token 数: {total_tokens}\n"
                chunks_info += f"- 平均每片: {avg_tokens:.0f} tokens\n\n"

                # 显示前 5 个切片预览
                chunks_info += "**前 5 个切片预览:**\n\n"
                for i, chunk in enumerate(result.chunks[:5], 1):
                    preview = chunk.text[:100].replace("\n", " ")
                    chunks_info += f"{i}. (第{chunk.pages}页, {chunk.token_count}tokens) `{preview}...`\n\n"
            else:
                chunks_info += "*无切片信息*"

            return header, abstract, fulltext_preview, chunks_info

        except Exception as e:
            return f"## ❌ 处理出错\n\n{str(e)}", "", "", ""

    # 创建界面
    with gr.Blocks(title="科研助手 v0.4.0", theme=gr.themes.Soft()) as app:
        gr.Markdown(
            """
            # 🔬 科研助手 v0.4.0

            **v0.4.0 新功能**:
            - 🏗️ **Tab + Sidebar 架构**: 更清晰的布局
            - 📄 **PDF 全文研究**: 下载arXiv论文并使用全文分析
            - 🎯 **智能筛选**: LLM 评估论文相关性
            """
        )

        # 主布局：左侧内容区 + 右侧侧边栏
        with gr.Row():
            # 左侧：Tab导航 + 内容区
            with gr.Column(scale=7):
                with gr.Tabs() as tabs:
                    # Tab 1: 搜索（快速模式）
                    with gr.Tab("搜索", id="search"):
                        gr.Markdown("### ⚡ 快速搜索模式\n\n快速搜索相关论文并提供阅读建议")

                        with gr.Row():
                            search_query_input = gr.Textbox(
                                label="研究问题",
                                placeholder="例如：Transformer注意力机制",
                                lines=2,
                                scale=4
                            )

                        with gr.Row():
                            search_btn = gr.Button("🔍 搜索论文", variant="primary", scale=4)
                            search_stop_btn = gr.Button("⏹️ 停止", variant="stop", scale=1)

                        search_header = gr.Markdown(label="查询分析")
                        search_guide = gr.Markdown(label="阅读建议")

                        with gr.Row():
                            with gr.Column():
                                search_arxiv = gr.Markdown(label="arXiv论文")
                            with gr.Column():
                                search_openalex = gr.Markdown(label="OpenAlex论文")

                        gr.Examples(
                            examples=[
                                ["Transformer注意力机制"],
                                ["RAG文档解析"],
                                ["大模型最新进展"],
                            ],
                            inputs=search_query_input,
                        )

                    # Tab 2: 深度研究
                    with gr.Tab("深度研究", id="deep_research"):
                        gr.Markdown("### 🚀 深度研究模式\n\n子问题分解 + 并行搜索 + 研究报告生成")

                        with gr.Row():
                            dr_query_input = gr.Textbox(
                                label="研究问题",
                                placeholder="例如：对比 Transformer 和 RNN 的优劣",
                                lines=2,
                                scale=4
                            )

                        # v0.4.0: 全文研究选项
                        with gr.Row():
                            use_fulltext_checkbox = gr.Checkbox(
                                label="📄 使用全文研究 (下载arXiv PDF，需要更多时间)",
                                value=False,
                                info="启用后会筛选相关论文并下载PDF进行深入分析"
                            )

                        with gr.Row():
                            dr_search_btn = gr.Button("🚀 开始研究", variant="primary", scale=4)
                            dr_stop_btn = gr.Button("⏹️ 停止", variant="stop", scale=1)

                        dr_header = gr.Markdown(label="查询分析")
                        dr_report = gr.Markdown(label="研究报告")

                        with gr.Row():
                            with gr.Column():
                                dr_arxiv = gr.Markdown(label="arXiv论文")
                            with gr.Column():
                                dr_openalex = gr.Markdown(label="OpenAlex论文")

                        gr.Examples(
                            examples=[
                                ["对比 Transformer 和 RNN 的优劣"],
                                ["RAG在文档解析任务中的作用"],
                                ["多模态大模型的发展趋势"],
                            ],
                            inputs=dr_query_input,
                        )

                    # Tab 3: 论文库（PDF 上传分析）
                    with gr.Tab("论文库", id="papers"):
                        gr.Markdown(
                            """
                            ### 📚 本地论文库

                            上传 PDF 文件进行解析和分析。支持：
                            - 📤 单个 PDF 上传分析
                            - 📄 提取全文和摘要
                            - 🔢 文档切片统计
                            """
                        )

                        with gr.Row():
                            pdf_upload = gr.File(
                                label="上传 PDF 文件",
                                file_types=[".pdf"],
                                file_count="single"
                            )

                        with gr.Row():
                            analyze_btn = gr.Button("📄 分析 PDF", variant="primary")

                        # 分析结果显示
                        pdf_result_header = gr.Markdown(label="分析结果")
                        pdf_abstract = gr.Markdown(label="摘要")
                        pdf_fulltext = gr.Textbox(
                            label="全文预览（前3000字）",
                            lines=15,
                            max_lines=20,
                            interactive=False
                        )
                        pdf_chunks_info = gr.Markdown(label="切片信息")

            # 右侧：统一侧边栏
            with gr.Column(scale=3):
                gr.Markdown("### 📄 论文详情")

                # 论文选择器（下拉菜单）
                paper_selector = gr.Dropdown(
                    label="选择论文",
                    choices=[],
                    interactive=True,
                    info="从搜索结果中选择论文查看详情"
                )

                # 侧边栏内容（显示选中论文的详情）
                sidebar_content = gr.Markdown(
                    value="## 📄 论文详情\n\n点击上方下拉菜单选择论文查看详细信息",
                    label="详细信息"
                )

                # 隐藏的状态：存储所有论文数据JSON
                papers_state = gr.State(value="[]")

        # 事件绑定

        # 搜索Tab - 快速搜索
        search_report_dummy = gr.State(value="")  # 占位，快速模式不需要report

        search_event = search_btn.click(
            fn=search_papers_stream,
            inputs=[search_query_input, gr.State(value="快速搜索"), gr.State(value=False)],
            outputs=[search_header, search_report_dummy, search_guide, search_arxiv, search_openalex, papers_state]
        )

        submit_search_event = search_query_input.submit(
            fn=search_papers_stream,
            inputs=[search_query_input, gr.State(value="快速搜索"), gr.State(value=False)],
            outputs=[search_header, search_report_dummy, search_guide, search_arxiv, search_openalex, papers_state]
        )

        search_stop_btn.click(fn=None, inputs=None, outputs=None, cancels=[search_event, submit_search_event])

        # 深度研究Tab
        dr_guide_dummy = gr.State(value="")  # 占位，深度模式不需要guide

        dr_event = dr_search_btn.click(
            fn=search_papers_stream,
            inputs=[dr_query_input, gr.State(value="深度研究"), use_fulltext_checkbox],
            outputs=[dr_header, dr_report, dr_guide_dummy, dr_arxiv, dr_openalex, papers_state]
        )

        submit_dr_event = dr_query_input.submit(
            fn=search_papers_stream,
            inputs=[dr_query_input, gr.State(value="深度研究"), use_fulltext_checkbox],
            outputs=[dr_header, dr_report, dr_guide_dummy, dr_arxiv, dr_openalex, papers_state]
        )

        dr_stop_btn.click(fn=None, inputs=None, outputs=None, cancels=[dr_event, submit_dr_event])

        # 论文库Tab - PDF 上传分析
        analyze_btn.click(
            fn=analyze_pdf,
            inputs=[pdf_upload],
            outputs=[pdf_result_header, pdf_abstract, pdf_fulltext, pdf_chunks_info]
        )

        # 侧边栏：更新论文选择器（当搜索完成后）
        def update_paper_selector(papers_json: str):
            """更新论文下拉菜单"""
            import json
            try:
                papers = json.loads(papers_json) if papers_json else []
                if not papers:
                    return gr.Dropdown(choices=[], value=None)

                choices = []
                for i, p in enumerate(papers, 1):
                    title = p.get('title', '未知标题')[:60]
                    choices.append((f"[{i}] {title}...", i-1))  # (显示文本, 值)

                return gr.Dropdown(choices=choices, value=None)
            except:
                return gr.Dropdown(choices=[], value=None)

        # 当搜索完成时更新选择器
        papers_state.change(
            fn=update_paper_selector,
            inputs=[papers_state],
            outputs=[paper_selector]
        )

        # 侧边栏：当选择论文时显示详情
        def show_selected_paper(paper_index, papers_json):
            """显示选中的论文详情"""
            import json
            if paper_index is None or not papers_json:
                return "## 📄 论文详情\n\n请先搜索论文，然后从上方下拉菜单选择"

            try:
                papers = json.loads(papers_json)
                if 0 <= paper_index < len(papers):
                    paper = papers[paper_index]
                    return show_paper_details(json.dumps(paper, ensure_ascii=False))
                else:
                    return "## 📄 论文详情\n\n论文索引无效"
            except Exception as e:
                return f"## 📄 论文详情\n\n解析出错: {str(e)}"

        paper_selector.change(
            fn=show_selected_paper,
            inputs=[paper_selector, papers_state],
            outputs=[sidebar_content]
        )

    return app


if __name__ == "__main__":
    app = create_app()
    app.launch(share=False)
