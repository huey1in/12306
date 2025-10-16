#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""日志记录工具模块"""

import logging
from datetime import datetime


def setup_logging(log_filename="12306.log"):
    """设置日志记录"""
    root_logger = logging.getLogger()

    # 检查是否已经配置过
    if not root_logger.handlers:
        root_logger.setLevel(logging.INFO)

        # 添加文件handler
        file_handler = logging.FileHandler(log_filename, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

        # 添加控制台handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    logger = logging.getLogger('12306')
    logger.info("12306订票工具启动")
    return logger


def get_logger(name='12306'):
    """获取日志记录器"""
    return logging.getLogger(name)
