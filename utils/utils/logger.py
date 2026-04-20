"""
日志模块
Author: LumiNest Team
Date: 2026-04-14
"""
import logging
import os
from typing import Optional

from core.constants import LOG_DIR, LOG_FORMAT


class Logger:
    """日志记录器类
    
    提供统一的日志记录功能，支持文件和控制台输出
    """
    
    def __init__(self, name: str, level: int = logging.INFO):
        """初始化日志记录器
        
        Args:
            name: 日志记录器名称
            level: 日志级别，默认为INFO
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        if not self.logger.handlers:
            os.makedirs(LOG_DIR, exist_ok=True)
            
            formatter = logging.Formatter(LOG_FORMAT)
            
            file_handler = logging.FileHandler(
                os.path.join(LOG_DIR, f"{name}.log"),
                encoding='utf-8'
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            
            console_handler = logging.StreamHandler()
            console_handler.setLevel(level)
            console_handler.setFormatter(formatter)
            
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)

    def debug(self, message: str) -> None:
        """记录调试信息
        
        Args:
            message: 日志消息
        """
        self.logger.debug(message)

    def info(self, message: str) -> None:
        """记录普通信息
        
        Args:
            message: 日志消息
        """
        self.logger.info(message)

    def warning(self, message: str) -> None:
        """记录警告信息
        
        Args:
            message: 日志消息
        """
        self.logger.warning(message)

    def error(self, message: str) -> None:
        """记录错误信息
        
        Args:
            message: 日志消息
        """
        self.logger.error(message)

    def critical(self, message: str) -> None:
        """记录严重错误信息
        
        Args:
            message: 日志消息
        """
        self.logger.critical(message)


logger = Logger("luminest")
