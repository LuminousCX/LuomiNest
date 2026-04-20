"""
配置文件
"""

import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# API配置
API_KEY = os.getenv("API_KEY", "a3d12396-36fc-462c-bcf6-dc8d359f54fa")
MODEL_ID = os.getenv("MODEL_ID", "ep-20260326114224-p7lsz")

# 记忆配置
DEFAULT_USER_ID = "user_default"
MEMORY_MAX_COUNT = 500
MEMORY_FILE = "mem0_memory.json"
KNOWLEDGE_BASE_FILE = "knowledge_base.json"
VECTOR_STORE_FILE = "vector_store.json"

# 硬件端口配置
HARDWARE_CONFIG = {
    "serial": {
        "port": "COM3",  # 串口端口
        "baudrate": 9600,  # 波特率
        "timeout": 1  # 超时时间（秒）
    },
    "server": {
        "host": "0.0.0.0",  # 监听所有网络接口
        "port": 8080  # 服务器端口
    }
}