#!/usr/bin/env python
"""科研助手启动脚本"""
import argparse
import sys
from pathlib import Path

# 添加src目录到路径
project_root = Path(__file__).parent
src_dir = project_root / "src"
sys.path.insert(0, str(src_dir))


def run_cli():
    """运行命令行界面"""
    from main import main
    main()


def run_web(share: bool = False, port: int = 7860):
    """运行Web界面"""
    # 添加ui目录
    ui_dir = project_root / "ui"
    sys.path.insert(0, str(ui_dir))

    from app import create_app
    app = create_app()
    app.launch(share=share, server_port=port)


def main():
    parser = argparse.ArgumentParser(
        description="科研助手 - AI Research Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run.py              # 启动CLI
  python run.py --web        # 启动Web界面
  python run.py --web --share  # 启动Web并生成公开链接
  python run.py --web --port 8080  # 指定端口
        """
    )

    parser.add_argument(
        "--web", "-w",
        action="store_true",
        help="启动Web界面（默认启动CLI）"
    )
    parser.add_argument(
        "--share", "-s",
        action="store_true",
        help="生成公开分享链接（仅Web模式）"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=7860,
        help="Web服务端口（默认7860）"
    )

    args = parser.parse_args()

    print("=" * 50)
    print("科研助手 v0.1.0")
    print("=" * 50)
    print()

    if args.web:
        print("启动模式: Web界面")
        print(f"端口: {args.port}")
        if args.share:
            print("公开链接: 已启用")
        print()
        run_web(share=args.share, port=args.port)
    else:
        print("启动模式: 命令行")
        print()
        run_cli()


if __name__ == "__main__":
    main()
