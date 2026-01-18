"""统一日志模块

提供项目级别的日志功能：
- 控制台输出（带颜色）
- 文件输出（按日期轮换）
- 不同级别：DEBUG, INFO, WARNING, ERROR
"""
import logging
import sys
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Optional


# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"


def ensure_logs_dir():
    """确保 logs 目录存在"""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


class ColoredFormatter(logging.Formatter):
    """带颜色的控制台格式化器"""

    # ANSI 颜色代码
    COLORS = {
        'DEBUG': '\033[36m',      # 青色
        'INFO': '\033[32m',       # 绿色
        'WARNING': '\033[33m',    # 黄色
        'ERROR': '\033[31m',      # 红色
        'CRITICAL': '\033[35m',   # 紫色
        'RESET': '\033[0m'        # 重置
    }

    def format(self, record):
        # 添加颜色
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"
            record.msg = f"{self.COLORS[levelname]}{record.msg}{self.COLORS['RESET']}"
        return super().format(record)


def get_logger(
    name: str,
    level: int = logging.DEBUG,
    console: bool = True,
    file: bool = True,
    log_file: Optional[str] = None
) -> logging.Logger:
    """
    获取配置好的 logger 实例

    Args:
        name: logger 名称（通常用 __name__）
        level: 日志级别
        console: 是否输出到控制台
        file: 是否输出到文件
        log_file: 自定义日志文件名（默认使用日期）

    Returns:
        logging.Logger: 配置好的 logger
    """
    logger = logging.getLogger(name)

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # 格式
    console_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    file_format = "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
    date_format = "%H:%M:%S"
    file_date_format = "%Y-%m-%d %H:%M:%S"

    # 控制台 Handler
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(ColoredFormatter(console_format, datefmt=date_format))
        logger.addHandler(console_handler)

    # 文件 Handler
    if file:
        ensure_logs_dir()

        # 日志文件名
        if log_file:
            log_path = LOGS_DIR / log_file
        else:
            today = datetime.now().strftime("%Y-%m-%d")
            log_path = LOGS_DIR / f"research_{today}.log"

        # 使用 RotatingFileHandler，单文件最大 10MB，保留 5 个备份
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(file_format, datefmt=file_date_format))
        logger.addHandler(file_handler)

    return logger


# 预配置的 loggers
def get_search_logger():
    """搜索模块专用 logger"""
    return get_logger("search", level=logging.DEBUG)


def get_agent_logger():
    """Agent 模块专用 logger"""
    return get_logger("agent", level=logging.DEBUG)


def get_pdf_logger():
    """PDF 处理模块专用 logger"""
    return get_logger("pdf", level=logging.DEBUG)


def get_llm_logger():
    """LLM 调用专用 logger"""
    return get_logger("llm", level=logging.DEBUG)


# 便捷的全局 logger
_main_logger: Optional[logging.Logger] = None


def logger() -> logging.Logger:
    """获取主 logger（单例）"""
    global _main_logger
    if _main_logger is None:
        _main_logger = get_logger("research_assistant")
    return _main_logger


# 便捷函数
def debug(msg: str, *args, **kwargs):
    """输出 DEBUG 级别日志"""
    logger().debug(msg, *args, **kwargs)


def info(msg: str, *args, **kwargs):
    """输出 INFO 级别日志"""
    logger().info(msg, *args, **kwargs)


def warning(msg: str, *args, **kwargs):
    """输出 WARNING 级别日志"""
    logger().warning(msg, *args, **kwargs)


def error(msg: str, *args, **kwargs):
    """输出 ERROR 级别日志"""
    logger().error(msg, *args, **kwargs)


def exception(msg: str, *args, **kwargs):
    """输出异常信息（带堆栈）"""
    logger().exception(msg, *args, **kwargs)


# 测试代码
if __name__ == "__main__":
    # 测试主 logger
    print("=== 测试主 logger ===")
    debug("这是 DEBUG 信息")
    info("这是 INFO 信息")
    warning("这是 WARNING 信息")
    error("这是 ERROR 信息")

    # 测试模块 logger
    print("\n=== 测试模块 logger ===")
    search_log = get_search_logger()
    search_log.info("搜索模块启动")
    search_log.debug("搜索关键词: transformer attention")

    agent_log = get_agent_logger()
    agent_log.info("Agent 开始执行任务")
    agent_log.warning("任务执行超时，正在重试")

    print(f"\n日志文件位置: {LOGS_DIR}")
