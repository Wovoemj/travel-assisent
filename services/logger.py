"""统一日志系统 - 替换所有 print 输出"""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler


def setup_logger(name='travel_assistant', log_dir='logs', level=logging.INFO):
    """
    配置统一日志系统
    - 控制台输出：INFO级别，带颜色
    - 文件输出：DEBUG级别，自动轮转(5MB × 3个备份)
    """
    Path(log_dir).mkdir(exist_ok=True)

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # 控制台格式
    console_fmt = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    )

    # 文件格式（更详细）
    file_fmt = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s:%(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 控制台处理器
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(console_fmt)

    # 文件处理器（自动轮转）
    file_handler = RotatingFileHandler(
        f'{log_dir}/app.log',
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_fmt)

    # 错误日志单独文件
    error_handler = RotatingFileHandler(
        f'{log_dir}/error.log',
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.WARNING)
    error_handler.setFormatter(file_fmt)

    logger.addHandler(console)
    logger.addHandler(file_handler)
    logger.addHandler(error_handler)

    return logger


# 全局 logger 实例
log = setup_logger()
