from base_config import BaseConfig
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions
from loguru import logger
import os
from dotenv import load_dotenv
from urllib.parse import urlparse
import requests
import json
from postgrest.exceptions import APIError
import jwt
import datetime


class ProductConfig(BaseConfig):
    """产品数据库配置类"""
    def __init__(self):
        super().__init__()
        logger.info("产品配置初始化成功")
    

    def test(self):
        try:
            response = self.supabase.table("test_products").select("*").execute()
            logger.info(f"查询响应为{response}")
            # r_2=self.supabase.table("test").insert({"id": 2}).execute()
            # logger.info(f"插入响应为{r_2}")
        except APIError as e:
            logger.error(f"API Error: {e}")

    def insert_product(self, product_name: str, subscription_url: str, email: str, phone: str, duration_days: int = 365):
        """插入数据到 products 表（通过 RPC 调用）"""
        try:
            # 将天数转换为 PostgreSQL interval 格式
            time_plan = f"{duration_days} days"
            params = {
                "p_product_name": product_name,
                "p_subscription_url": subscription_url,
                "p_email": email,
                "p_phone": phone,
                "p_time_plan": time_plan
            }
            response = self.supabase.rpc("insert_product", params).execute()
            logger.info(f"Inserted product {product_name} for {email}, product ID: {response.data}")
            return response.data  # 返回新产品的UUID
        except APIError as e:
            logger.error(f"插入产品数据失败: {e}")
            raise e
        
    
    def fetch_product_user(self,user_email: str="",phone: str=""):
        """获取用户的产品数据（通过 SQL 函数）"""
        params = {
            "p_user_email": user_email or None,
            "p_phone": phone or None,
        }
        response = self.supabase.rpc("fetch_user_products", params).execute()
        return response.data or []