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

        # arXiv ID（如果是arXiv论文，显示获取全文提示）
        if source == 'ARXIV' and url:
            import re
            match = re.search(r'(\d{4}\.\d{4,5})', url)
            if match:
                arxiv_id = match.group(1)
                output += f"\n---\n\n💡 **提示**: 这是 arXiv 论文 (ID: `{arxiv_id}`)，点击下方「获取全文」按钮可下载 PDF 并提取全文。\n\n"
        else:
            output += f"\n---\n\n⚠️ 非 arXiv 论文，暂不支持全文获取。\n\n"

        return output

    def jump_to_citation(cite_num, report_sources_json, papers_json):
        """根据引用编号跳转到对应论文

        Args:
            cite_num: 引用编号（1, 2, 3...）
            report_sources_json: 报告来源列表 JSON（与引用编号对应）
            papers_json: 论文列表 JSON
        """
        import json

        if cite_num is None or cite_num < 1:
            return (
                "## ⚠️ 请输入有效的引用编号\n\n引用编号从 1 开始",
                gr.update(value=None),
                "{}"
            )

        try:
            # 尝试从 report_sources 获取（与报告引用编号一致）
            report_sources = json.loads(report_sources_json) if report_sources_json else []
            papers = json.loads(papers_json) if papers_json else []

            # 引用编号是 1-indexed，转换为 0-indexed
            idx = int(cite_num) - 1

            # 优先使用 report_sources（与报告引用一致）
            source_list = report_sources if report_sources else papers

            if idx < 0 or idx >= len(source_list):
                return (
                    f"## ⚠️ 引用 [{int(cite_num)}] 不存在\n\n当前共有 {len(source_list)} 个来源",
                    gr.update(value=None),
                    "{}"
                )

            paper = source_list[idx]
            paper_json = json.dumps(paper, ensure_ascii=False)

            # 返回论文详情和更新当前论文状态
            return (
                show_paper_details(paper_json),
                gr.update(value=idx),  # 更新下拉菜单选中项
                paper_json
            )

        except Exception as e:
            return (
                f"## ❌ 跳转失败\n\n错误: {str(e)}",
                gr.update(value=None),
                "{}"
            )

    def fetch_paper_fulltext(current_paper_json):
        """获取论文全文

        Args:
            current_paper_json: 当前选中论文的 JSON
        """
        import json
        import re

        if not current_paper_json or current_paper_json == "{}":
            return "请先选择一篇论文"

        try:
            paper = json.loads(current_paper_json)
        except:
            return "论文数据解析失败"

        url = paper.get('url', '')
        source = paper.get('source', '').lower()
        title = paper.get('title', '未知标题')

        # 只支持 arXiv 论文
        if source != 'arxiv':
            return f"⚠️ 暂不支持非 arXiv 论文的全文获取\n\n论文来源: {source.upper()}"

        # 提取 arXiv ID
        match = re.search(r'(\d{4}\.\d{4,5})', url)
        if not match:
            return f"⚠️ 无法从 URL 提取 arXiv ID\n\nURL: {url}"

        arxiv_id = match.group(1)

        try:
            # 使用 PaperProcessor 下载并解析 PDF
            result = pdf_processor.process(arxiv_id)

            if not result.success:
                return f"❌ 获取全文失败\n\n{result.error}"

            # 返回全文
            full_text = result.full_text
            if not full_text:
                return "❌ PDF 解析成功但未提取到文本"

            # 添加元信息头
            header = f"📄 **{title}**\n"
            header += f"arXiv ID: {arxiv_id} | 页数: {result.total_pages}\n"
            header += f"字符数: {len(full_text):,}\n"
            header += "=" * 50 + "\n\n"

            return header + full_text

        except Exception as e:
            return f"❌ 获取全文时出错\n\n错误: {str(e)}"

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

    def search_papers_stream(query: str, mode: str = "auto", use_fulltext: bool = False, use_v2: bool = False):
        """流式搜索论文 - 实时显示进度

        Args:
            query: 查询字符串
            mode: 搜索模式 ("auto", "simple", "deep_research")
            use_fulltext: 是否使用全文研究（仅深度研究模式有效）
            use_v2: 是否使用 V2 架构（Supervisor 循环）
        """
        if not query.strip():
            yield "请输入研究问题", "", "", "", "", "", "{}"
            return

        start_time = datetime.now()
        actual_mode = "auto" if mode == "智能判断" else ("simple" if mode == "快速搜索" else "deep_research")

        # 阶段1: 显示开始状态
        start_time_str = start_time.strftime("%H:%M:%S")
        header = f"## 🔍 查询分析\n\n"
        header += f"**查询**: {query}\n\n"

        # 显示模式（包括全文研究状态和V2架构）
        if actual_mode == 'deep_research' or (actual_mode == 'auto' and len(query) > 20):
            mode_display = "🚀 深度研究"
            if use_v2:
                mode_display += " (V2 Supervisor 循环)"
            if use_fulltext:
                mode_display += " (📄 全文模式)"
        else:
            mode_display = "⚡ 快速搜索"

        header += f"**模式**: {mode_display}\n\n"
        header += f"**状态**: ⏳ 正在分析查询... (开始于 {start_time_str})\n"

        yield header, f"⏳ 正在分析问题，请稍候...\n\n> 开始时间: {start_time_str}，可点击「停止」按钮取消", "*等待研究完成...*", "", "*🔄 搜索中...*", "{}", "[]"

        # 阶段2: 执行搜索（传入 use_fulltext 和 use_v2 参数）
        try:
            result = assistant.process_query(query, mode=actual_mode, use_fulltext=use_fulltext, use_v2=use_v2)
        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds()
            error_msg = f"## ❌ 搜索出错\n\n耗时: {elapsed:.1f}秒\n\n错误: {str(e)}"
            yield header.replace("⏳ 正在分析查询...", f"❌ 出错 ({elapsed:.1f}s)"), error_msg, "", "", "", "{}", "[]"
            return

        elapsed = (datetime.now() - start_time).total_seconds()

        # 更新 header
        header = f"## 🔍 查询分析\n\n"
        header += f"**意图**: {result.get('intent', '未识别')}\n\n"
        keywords = result.get('keywords', [])
        if keywords:
            header += f"**搜索关键词**: `{'`, `'.join(keywords)}`\n\n"
        mode_display = "🚀 深度研究" if result['mode'] in ("deep_research", "deep_research_v2") else "⚡ 快速搜索"
        header += f"**模式**: {mode_display} | "
        header += f"**搜索源**: {', '.join(result.get('sources', [])) or '无'} | "
        header += f"**找到**: {result.get('total_found', len(result.get('papers', [])))} 篇\n\n"
        header += f"**总耗时**: ✅ {elapsed:.1f}秒\n"

        # 深度研究模式：显示研究报告
        report_output = ""
        thinking_output = ""  # 分离的思考过程输出

        if result['mode'] in ('deep_research', 'deep_research_v2') and result.get('report'):
            # V2 模式显示思考历史（分离到 thinking_output）
            if result['mode'] == 'deep_research_v2':
                thinking_history = result.get('thinking_history', [])
                if thinking_history:
                    thinking_output = "### 研究思考过程\n\n"
                    for record in thinking_history:
                        # 支持新格式（带轮次）和旧格式（纯字符串）
                        if isinstance(record, dict):
                            round_num = record.get('round', '?')
                            thought = record.get('thought', '')
                        else:
                            round_num = '?'
                            thought = str(record)

                        # 长思考内容使用 HTML details 实现展开/收起
                        if len(thought) > 80:
                            thought_preview = thought[:80].replace('\n', ' ')
                            thought_full = thought.replace('\n', '<br>')
                            thinking_output += f"**第 {round_num} 轮：** {thought_preview}... "
                            thinking_output += f"<details><summary>📖 展开全部</summary>\n\n{thought_full}\n\n</details>\n\n"
                        else:
                            thinking_output += f"**第 {round_num} 轮：** {thought}\n\n"
            else:
                # V1 模式显示子问题分解（也放到 thinking_output）
                decomposition = result.get('decomposition', {})
                if decomposition:
                    thinking_output = "### 问题分解\n\n"
                    thinking_output += f"**问题类型**: {decomposition.get('query_type', 'N/A')}\n\n"
                    thinking_output += f"**研究策略**: {decomposition.get('strategy', 'N/A')}\n\n"
                    sub_questions = decomposition.get('sub_questions', [])
                    if sub_questions:
                        thinking_output += "**子问题**:\n"
                        for i, sq in enumerate(sub_questions, 1):
                            thinking_output += f"{i}. {sq.get('question', '')} *(目的: {sq.get('purpose', '')})*\n"

            # 显示研究报告（不包含思考过程）
            report_output += result['report']

            # 显示元数据和各阶段耗时
            metadata = result.get('metadata', {})
            if metadata:
                report_output += "\n\n---\n"
                report_output += f"**总耗时: {metadata.get('duration_seconds', 0):.1f}秒** | "

                if result['mode'] == 'deep_research_v2':
                    # V2 元数据
                    total_searched = metadata.get('total_searched', 0)
                    total_selected = metadata.get('total_selected', 0)
                    report_output += f"研究轮数: {metadata.get('total_rounds', 0)}轮 | "
                    report_output += f"论文: 搜索 {total_searched} 篇 → 筛选 {total_selected} 篇\n\n"
                    report_output += f"**完成原因**: {metadata.get('completion_reason', 'N/A')}\n"
                else:
                    # V1 元数据
                    report_output += f"子问题: {metadata.get('sub_questions_count', 0)}个 | "
                    report_output += f"论文: {metadata.get('total_papers', 0)}篇\n\n"

                    # 显示各阶段耗时详情
                    stage_times = metadata.get('stage_times', {})
                    if stage_times:
                        report_output += "**⏱️ 各阶段耗时:**\n"
                        for stage, time_sec in stage_times.items():
                            stage_name = stage.split('_', 1)[1] if '_' in stage else stage
                            report_output += f"- {stage_name}: {time_sec:.1f}秒\n"

        # 如果没有思考过程，显示提示
        if not thinking_output:
            thinking_output = "*无思考记录（仅深度研究模式有效）*"

        # 阅读导航（快速搜索模式）
        reading_guide = result.get('reading_guide', {})
        guide_output = format_reading_guide(reading_guide) if result['mode'] == 'simple' else ""

        # 论文列表（合并为单一列表，带来源标签）
        import json
        arxiv_papers = result.get('arxiv_papers', [])
        openalex_papers = result.get('openalex_papers', [])
        papers_list = arxiv_papers + openalex_papers

        # 统一生成论文列表（带来源标签）
        arxiv_count = len(arxiv_papers)
        openalex_count = len(openalex_papers)
        total_count = arxiv_count + openalex_count

        papers_output = f"### 📚 相关论文 ({total_count}篇)\n\n"
        papers_output += f"> arXiv: {arxiv_count}篇 | OpenAlex: {openalex_count}篇\n\n"

        if result['mode'] in ('deep_research', 'deep_research_v2'):
            papers_output += "> ℹ️ *以下编号与报告引用编号无关*\n\n"

        for i, paper in enumerate(papers_list, 1):
            papers_output += format_paper(paper, i, show_source=True)

        if not papers_list:
            papers_output += "*暂无结果*\n"

        # 返回论文列表JSON供侧边栏使用
        papers_json = json.dumps(papers_list, ensure_ascii=False)

        # 返回报告来源JSON（与报告引用编号一致）
        report_sources = result.get('report_sources', [])
        report_sources_json = json.dumps(report_sources, ensure_ascii=False) if report_sources else "[]"

        yield header, report_output, thinking_output, guide_output, papers_output, papers_json, report_sources_json

    # === 论文库功能函数 ===

    # 全文分页参数
    CHARS_PER_PAGE = 3000

    def analyze_pdf(pdf_file):
        """分析上传的 PDF 文件（增强版）"""
        empty_result = (
            "请先上传 PDF 文件", "",  # header, abstract
            "", "第 1 / 1 页", gr.update(maximum=1, value=1),  # fulltext, page_info, page_slider
            "", gr.update(maximum=1, value=1), "", "",  # chunks_info, chunk_selector, chunk_content, translation
            {}  # pdf_state
        )

        if pdf_file is None:
            return empty_result

        try:
            pdf_path = pdf_file.name if hasattr(pdf_file, 'name') else str(pdf_file)
            result = pdf_processor.process_local_pdf(pdf_path)

            if not result.success:
                return (
                    f"## ❌ 分析失败\n\n{result.error}", "", "", "第 1 / 1 页",
                    gr.update(maximum=1, value=1), "", gr.update(maximum=1, value=1), "", "", {}
                )

            # 基本信息
            header = f"## ✅ 分析完成\n\n"
            header += f"**📄 标题**: {result.title}\n\n"
            header += f"**📖 页数**: {result.total_pages} 页\n\n"
            header += f"**📝 全文长度**: {len(result.full_text):,} 字符\n\n"
            header += f"**🧩 切片数**: {len(result.chunks)} 个\n"

            # 摘要
            abstract = result.abstract if result.abstract else "*未能自动提取摘要（可尝试 AI 总结）*"

            # 全文分页
            full_text = result.full_text or ""
            total_pages = max(1, (len(full_text) + CHARS_PER_PAGE - 1) // CHARS_PER_PAGE)
            first_page_text = full_text[:CHARS_PER_PAGE] if full_text else "无法提取全文"
            page_info = f"第 1 / {total_pages} 页（每页 {CHARS_PER_PAGE} 字）"

            # 切片统计
            chunks_info = ""
            if result.chunks:
                total_tokens = sum(c.token_count for c in result.chunks)
                avg_tokens = total_tokens / len(result.chunks)
                chunks_info = f"**切片数量**: {len(result.chunks)} | **总 Token**: {total_tokens:,} | **平均**: {avg_tokens:.0f} tokens/片"
            else:
                chunks_info = "*无切片信息*"

            # 第一个切片内容
            first_chunk = result.chunks[0].text if result.chunks else ""

            # 存储状态（用于后续操作）
            pdf_state = {
                "title": result.title,
                "abstract": result.abstract,
                "full_text": full_text,
                "total_pages": total_pages,
                "chunks": [{"text": c.text, "pages": c.pages, "tokens": c.token_count} for c in result.chunks]
            }

            return (
                header, abstract,
                first_page_text, page_info, gr.update(maximum=total_pages, value=1),
                chunks_info, gr.update(maximum=max(1, len(result.chunks)), value=1),
                first_chunk, "",
                pdf_state
            )

        except Exception as e:
            return (
                f"## ❌ 处理出错\n\n{str(e)}", "", "", "第 1 / 1 页",
                gr.update(maximum=1, value=1), "", gr.update(maximum=1, value=1), "", "", {}
            )

    def update_fulltext_page(page_num: int, pdf_state: dict):
        """更新全文显示页码"""
        if not pdf_state or "full_text" not in pdf_state:
            return "", "第 1 / 1 页"

        full_text = pdf_state["full_text"]
        total_pages = pdf_state.get("total_pages", 1)
        page_num = max(1, min(int(page_num), total_pages))

        start = (page_num - 1) * CHARS_PER_PAGE
        end = start + CHARS_PER_PAGE
        page_text = full_text[start:end]

        page_info = f"第 {page_num} / {total_pages} 页（每页 {CHARS_PER_PAGE} 字）"
        return page_text, page_info

    def update_chunk_content(chunk_idx: int, pdf_state: dict):
        """更新切片内容显示"""
        if not pdf_state or "chunks" not in pdf_state:
            return "", ""

        chunks = pdf_state["chunks"]
        idx = max(0, min(int(chunk_idx) - 1, len(chunks) - 1))

        if idx < len(chunks):
            chunk = chunks[idx]
            return chunk["text"], ""  # 清空翻译结果
        return "", ""

    def translate_chunk(chunk_idx: int, pdf_state: dict):
        """翻译选中的切片"""
        if not pdf_state or "chunks" not in pdf_state:
            return "*请先上传并分析 PDF*"

        chunks = pdf_state["chunks"]
        idx = max(0, min(int(chunk_idx) - 1, len(chunks) - 1))

        if idx >= len(chunks):
            return "*切片不存在*"

        chunk_text = chunks[idx]["text"]

        # 调用 LLM 翻译
        try:
            from utils.llm_client import QwenClient
            from utils.config import config

            translator_config = config.get_translator_config()
            api_key = translator_config.get("qwen_api_key")

            if not api_key:
                return "*未配置 QWEN_API_KEY，无法翻译*"

            client = QwenClient(api_key=api_key)
            prompt = f"请将以下学术论文段落翻译成中文，保持专业术语准确：\n\n{chunk_text}"

            translation = client.chat(prompt, task_type="translation", max_tokens=2000)
            return f"### 🌐 翻译结果\n\n{translation}"

        except Exception as e:
            return f"*翻译失败: {str(e)}*"

    def summarize_pdf(pdf_state: dict):
        """AI 总结全文"""
        if not pdf_state or "full_text" not in pdf_state:
            return "*请先上传并分析 PDF*"

        title = pdf_state.get("title", "未知标题")
        abstract = pdf_state.get("abstract", "")
        full_text = pdf_state.get("full_text", "")

        # 取前 8000 字用于总结（避免超出 token 限制）
        text_for_summary = full_text[:8000] if len(full_text) > 8000 else full_text

        try:
            from utils.llm_client import QwenClient
            from utils.config import config

            translator_config = config.get_translator_config()
            api_key = translator_config.get("qwen_api_key")

            if not api_key:
                return "*未配置 QWEN_API_KEY，无法生成总结*"

            client = QwenClient(api_key=api_key)
            prompt = f"""请对以下学术论文进行结构化总结：

**论文标题**: {title}

**摘要**: {abstract if abstract else '（无摘要）'}

**正文内容**:
{text_for_summary}

请按以下格式输出总结：

## 研究背景与问题
（一句话概括研究背景和要解决的问题）

## 主要方法
（概括论文采用的核心方法或技术）

## 关键发现
- 发现1
- 发现2
- 发现3

## 主要贡献
（概括论文的创新点和贡献）

## 局限与展望
（如有）
"""

            summary = client.chat(prompt, task_type="summary", max_tokens=1500)
            return summary

        except Exception as e:
            return f"*总结失败: {str(e)}*"

    def export_markdown(report_content: str, papers_json: str) -> str:
        """导出 Markdown 报告"""
        import tempfile
        import json
        from datetime import datetime

        if not report_content or report_content.startswith("⏳"):
            return None

        # 生成完整的 Markdown 文件
        # 检查报告是否已有标题（以 # 开头）
        has_title = report_content.strip().startswith('#')

        if has_title:
            # 报告已有标题，只添加元数据
            md_content = f"*导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"
            md_content += "---\n\n"
            md_content += report_content
        else:
            # 报告无标题，添加默认标题
            md_content = f"# 研究报告\n\n"
            md_content += f"*导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"
            md_content += "---\n\n"
            md_content += report_content

        # 检查报告是否已包含参考来源（深度研究模式会自动添加）
        has_references = "## 参考来源" in report_content or "参考来源" in report_content

        # 只有在报告未包含参考来源时才添加论文列表
        if not has_references:
            md_content += "\n\n---\n\n## 参考论文\n\n"
            try:
                papers = json.loads(papers_json) if papers_json else []
                for i, p in enumerate(papers, 1):
                    title = p.get('title', '未知标题')
                    authors = ', '.join(p.get('authors', [])[:3])
                    year = p.get('year', 'N/A')
                    url = p.get('url', '')
                    md_content += f"{i}. **{title}** ({year})\n"
                    if authors:
                        md_content += f"   - 作者: {authors}\n"
                    if url:
                        md_content += f"   - 链接: [{url}]({url})\n"
                    md_content += "\n"
            except:
                pass

        # 保存到临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
            f.write(md_content)
            return f.name

    def export_bibtex(papers_json: str) -> str:
        """导出 BibTeX 格式"""
        import tempfile
        import json
        import re

        if not papers_json:
            return None

        try:
            papers = json.loads(papers_json)
        except:
            return None

        if not papers:
            return None

        bib_entries = []
        for i, p in enumerate(papers, 1):
            title = p.get('title', 'Unknown')
            authors = p.get('authors', [])
            year = p.get('year', '')
            url = p.get('url', '')
            source = p.get('source', 'misc')

            # 生成 cite key
            first_author = authors[0].split()[-1] if authors else 'unknown'
            first_word = re.sub(r'[^a-zA-Z]', '', title.split()[0]) if title else 'paper'
            cite_key = f"{first_author.lower()}{year}{first_word.lower()}"

            # 格式化作者
            author_str = ' and '.join(authors) if authors else 'Unknown'

            # 构建 BibTeX 条目
            entry_type = 'article' if source == 'openalex' else 'misc'
            entry = f"@{entry_type}{{{cite_key},\n"
            entry += f"  title = {{{title}}},\n"
            entry += f"  author = {{{author_str}}},\n"
            if year:
                entry += f"  year = {{{year}}},\n"
            if url:
                entry += f"  url = {{{url}}},\n"
            if source == 'arxiv':
                entry += f"  note = {{arXiv preprint}},\n"
            entry += "}\n"
            bib_entries.append(entry)

        # 保存到临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.bib', delete=False, encoding='utf-8') as f:
            f.write('\n'.join(bib_entries))
            return f.name

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

                        # 合并的论文列表（带来源标签）
                        search_papers = gr.Markdown(label="相关论文")

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

                        # v0.4.5: V2架构选项
                        with gr.Row():
                            use_v2_checkbox = gr.Checkbox(
                                label="🔄 使用 V2 架构 (Supervisor 循环，动态决策研究轮数)",
                                value=False,
                                info="启用 V2 架构：动态研究循环 + 显式反思过程"
                            )

                        with gr.Row():
                            dr_search_btn = gr.Button("🚀 开始研究", variant="primary", scale=3)
                            dr_fullscreen_btn = gr.Button("📖 全屏查看", variant="secondary", scale=1)
                            dr_stop_btn = gr.Button("⏹️ 停止", variant="stop", scale=1)

                        dr_header = gr.Markdown(label="查询分析")

                        # 思考过程（折叠显示）
                        with gr.Accordion("🧠 思考过程", open=False) as dr_thinking_accordion:
                            dr_thinking = gr.Markdown(value="*研究完成后显示思考过程*")

                        dr_report = gr.Markdown(label="研究报告")

                        # 导出按钮行
                        with gr.Row():
                            export_md_btn = gr.Button("📄 导出 Markdown", scale=1)
                            export_bib_btn = gr.Button("📚 导出 BibTeX", scale=1)

                        # 下载文件显示区（导出后可见）
                        export_file = gr.File(label="📥 点击下载", visible=True, interactive=False)

                        # 合并的论文列表（带来源标签）
                        dr_papers = gr.Markdown(label="相关论文")

                        gr.Examples(
                            examples=[
                                ["对比 Transformer 和 RNN 的优劣"],
                                ["RAG在文档解析任务中的作用"],
                                ["多模态大模型的发展趋势"],
                            ],
                            inputs=dr_query_input,
                        )

                    # Tab 3: 报告查看（全屏）
                    with gr.Tab("📖 报告", id="report_view"):
                        gr.Markdown(
                            """
                            ### 📖 研究报告全文

                            在深度研究 Tab 完成研究后，点击「全屏查看」按钮将报告显示在此处。
                            """
                        )
                        report_fullscreen = gr.Markdown(
                            value="*等待研究完成后查看报告...*",
                            elem_id="fullscreen-report"
                        )

                    # Tab 4: 论文库（PDF 上传分析）
                    with gr.Tab("论文库", id="papers"):
                        gr.Markdown(
                            """
                            ### 📚 本地论文库

                            上传 PDF 文件进行深度解析。支持：
                            - 📄 智能提取标题和摘要
                            - 📖 全文分页浏览
                            - 🧩 切片复制与翻译
                            - 📝 AI 一键总结
                            """
                        )

                        # 上传区域
                        with gr.Row():
                            pdf_upload = gr.File(
                                label="上传 PDF 文件",
                                file_types=[".pdf"],
                                file_count="single"
                            )

                        with gr.Row():
                            analyze_btn = gr.Button("📄 分析 PDF", variant="primary", scale=2)
                            summarize_btn = gr.Button("📝 AI 总结", variant="secondary", scale=1)

                        # 基本信息
                        pdf_result_header = gr.Markdown(label="分析结果")

                        # 摘要（可折叠）
                        with gr.Accordion("📝 摘要", open=True):
                            pdf_abstract = gr.Markdown(label="摘要")

                        # 全文浏览（分页）
                        with gr.Accordion("📖 全文浏览", open=False):
                            with gr.Row():
                                pdf_page_slider = gr.Slider(
                                    minimum=1, maximum=1, step=1, value=1,
                                    label="页码", info="拖动切换页面"
                                )
                                pdf_page_info = gr.Markdown("第 1 / 1 页")
                            pdf_fulltext = gr.Textbox(
                                label="全文内容",
                                lines=20,
                                max_lines=25,
                                interactive=False,
                                show_copy_button=True
                            )

                        # 切片浏览
                        with gr.Accordion("🧩 文档切片", open=False):
                            pdf_chunks_info = gr.Markdown(label="切片统计")
                            with gr.Row():
                                chunk_selector = gr.Slider(
                                    minimum=1, maximum=1, step=1, value=1,
                                    label="选择切片", scale=3
                                )
                                translate_chunk_btn = gr.Button("🌐 翻译此切片", scale=1)
                            chunk_content = gr.Textbox(
                                label="切片内容",
                                lines=8,
                                interactive=False,
                                show_copy_button=True
                            )
                            chunk_translation = gr.Markdown(label="翻译结果")

                        # AI 总结结果
                        with gr.Accordion("📊 AI 总结", open=False):
                            pdf_summary = gr.Markdown(value="*点击「AI 总结」按钮生成*")

                        # 隐藏状态：存储 PDF 解析结果
                        pdf_state = gr.State(value={})

            # 右侧：统一侧边栏
            with gr.Column(scale=3):
                gr.Markdown("### 📄 论文详情")

                # 引用编号输入（用于报告引用跳转）
                with gr.Row():
                    cite_number_input = gr.Number(
                        label="🔍 按引用编号查找",
                        value=None,
                        precision=0,
                        minimum=1,
                        info="输入报告中的引用编号 [1][2]...",
                        scale=2
                    )
                    cite_jump_btn = gr.Button("跳转", scale=1, size="sm")

                # 论文选择器（下拉菜单）
                paper_selector = gr.Dropdown(
                    label="选择论文",
                    choices=[],
                    interactive=True,
                    info="从搜索结果中选择论文查看详情"
                )

                # 侧边栏内容（显示选中论文的详情）
                sidebar_content = gr.Markdown(
                    value="## 📄 论文详情\n\n点击上方下拉菜单选择论文查看详细信息\n\n💡 **提示**: 输入报告中的引用编号 [1][2] 可快速跳转到对应论文",
                    label="详细信息"
                )

                # 获取全文按钮（仅 arXiv 论文可用）
                with gr.Row():
                    fetch_fulltext_btn = gr.Button("📄 获取全文", variant="secondary", visible=True)

                # 全文显示区域（可折叠）
                with gr.Accordion("📖 论文全文", open=False, visible=True) as fulltext_accordion:
                    paper_fulltext = gr.Textbox(
                        label="全文内容",
                        lines=15,
                        max_lines=20,
                        interactive=False,
                        show_copy_button=True,
                        value=""
                    )

                # 隐藏的状态：存储所有论文数据JSON
                papers_state = gr.State(value="[]")

                # 隐藏的状态：报告来源列表（与引用编号对应）
                report_sources_state = gr.State(value="[]")

                # 隐藏的状态：当前选中论文的信息
                current_paper_state = gr.State(value="{}")

        # 事件绑定

        # 搜索Tab - 快速搜索
        search_report_dummy = gr.State(value="")  # 占位，快速模式不需要report
        search_thinking_dummy = gr.State(value="")  # 占位，快速模式不需要thinking
        search_sources_dummy = gr.State(value="[]")  # 占位，快速模式不需要report_sources

        search_event = search_btn.click(
            fn=search_papers_stream,
            inputs=[search_query_input, gr.State(value="快速搜索"), gr.State(value=False)],
            outputs=[search_header, search_report_dummy, search_thinking_dummy, search_guide, search_papers, papers_state, search_sources_dummy]
        )

        submit_search_event = search_query_input.submit(
            fn=search_papers_stream,
            inputs=[search_query_input, gr.State(value="快速搜索"), gr.State(value=False)],
            outputs=[search_header, search_report_dummy, search_thinking_dummy, search_guide, search_papers, papers_state, search_sources_dummy]
        )

        search_stop_btn.click(fn=None, inputs=None, outputs=None, cancels=[search_event, submit_search_event])

        # 深度研究Tab
        dr_guide_dummy = gr.State(value="")  # 占位，深度模式不需要guide

        dr_event = dr_search_btn.click(
            fn=search_papers_stream,
            inputs=[dr_query_input, gr.State(value="深度研究"), use_fulltext_checkbox, use_v2_checkbox],
            outputs=[dr_header, dr_report, dr_thinking, dr_guide_dummy, dr_papers, papers_state, report_sources_state]
        )

        submit_dr_event = dr_query_input.submit(
            fn=search_papers_stream,
            inputs=[dr_query_input, gr.State(value="深度研究"), use_fulltext_checkbox, use_v2_checkbox],
            outputs=[dr_header, dr_report, dr_thinking, dr_guide_dummy, dr_papers, papers_state, report_sources_state]
        )

        dr_stop_btn.click(fn=None, inputs=None, outputs=None, cancels=[dr_event, submit_dr_event])

        # 导出按钮事件
        export_md_btn.click(
            fn=export_markdown,
            inputs=[dr_report, papers_state],
            outputs=[export_file]
        )

        export_bib_btn.click(
            fn=export_bibtex,
            inputs=[papers_state],
            outputs=[export_file]
        )

        # 全屏查看按钮 - 复制报告到报告 Tab
        def copy_report_to_fullscreen(report_content):
            """复制报告内容到全屏 Tab"""
            if not report_content or report_content.startswith("⏳"):
                return "## ⚠️ 暂无报告\n\n请先在「深度研究」Tab 中完成研究。"
            return f"## 📖 研究报告\n\n{report_content}"

        dr_fullscreen_btn.click(
            fn=copy_report_to_fullscreen,
            inputs=[dr_report],
            outputs=[report_fullscreen]
        ).then(
            fn=None,
            inputs=None,
            outputs=None,
            js="() => { document.querySelector('[data-tab-id=\"report_view\"]')?.click(); }"
        )

        # 论文库Tab - PDF 分析及交互
        analyze_btn.click(
            fn=analyze_pdf,
            inputs=[pdf_upload],
            outputs=[
                pdf_result_header, pdf_abstract,
                pdf_fulltext, pdf_page_info, pdf_page_slider,
                pdf_chunks_info, chunk_selector,
                chunk_content, chunk_translation,
                pdf_state
            ]
        )

        # 全文分页切换
        pdf_page_slider.change(
            fn=update_fulltext_page,
            inputs=[pdf_page_slider, pdf_state],
            outputs=[pdf_fulltext, pdf_page_info]
        )

        # 切片选择切换
        chunk_selector.change(
            fn=update_chunk_content,
            inputs=[chunk_selector, pdf_state],
            outputs=[chunk_content, chunk_translation]
        )

        # 翻译切片
        translate_chunk_btn.click(
            fn=translate_chunk,
            inputs=[chunk_selector, pdf_state],
            outputs=[chunk_translation]
        )

        # AI 总结
        summarize_btn.click(
            fn=summarize_pdf,
            inputs=[pdf_state],
            outputs=[pdf_summary]
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
            """显示选中的论文详情，同时更新 current_paper_state"""
            import json
            if paper_index is None or not papers_json:
                return (
                    "## 📄 论文详情\n\n请先搜索论文，然后从上方下拉菜单选择",
                    "{}"
                )

            try:
                papers = json.loads(papers_json)
                if 0 <= paper_index < len(papers):
                    paper = papers[paper_index]
                    paper_json = json.dumps(paper, ensure_ascii=False)
                    return (
                        show_paper_details(paper_json),
                        paper_json
                    )
                else:
                    return (
                        "## 📄 论文详情\n\n论文索引无效",
                        "{}"
                    )
            except Exception as e:
                return (
                    f"## 📄 论文详情\n\n解析出错: {str(e)}",
                    "{}"
                )

        paper_selector.change(
            fn=show_selected_paper,
            inputs=[paper_selector, papers_state],
            outputs=[sidebar_content, current_paper_state]
        )

        # 引用编号跳转事件
        cite_jump_btn.click(
            fn=jump_to_citation,
            inputs=[cite_number_input, report_sources_state, papers_state],
            outputs=[sidebar_content, paper_selector, current_paper_state]
        )

        # 输入框回车也触发跳转
        cite_number_input.submit(
            fn=jump_to_citation,
            inputs=[cite_number_input, report_sources_state, papers_state],
            outputs=[sidebar_content, paper_selector, current_paper_state]
        )

        # 获取全文按钮事件
        fetch_fulltext_btn.click(
            fn=fetch_paper_fulltext,
            inputs=[current_paper_state],
            outputs=[paper_fulltext]
        )

    return app


if __name__ == "__main__":
    app = create_app()
    app.launch(share=False)
