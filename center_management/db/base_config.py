from supabase import create_client, Client
from loguru import logger
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class BaseConfig:
    """数据库配置基类"""
    def __init__(self):
        self.url: str = os.getenv('SUPABASE_URL', 'http://localhost:8000')
        self.key: str = os.getenv('SERVICE_ROLE_KEY')
        logger.info(f"Supabase URL: {self.url}")
        self.supabase: Client = create_client(self.url, self.key)
        # logger.info("数据库配置初始化成功")
    
    def get_client(self) -> Client:
        """获取 Supabase 客户端"""
        return self.supabase