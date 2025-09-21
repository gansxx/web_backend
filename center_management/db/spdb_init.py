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


# 加载环境变量
load_dotenv()

class spdbConfig:
    """Supabase 数据库配置类"""
    def __init__(self):
        self.url: str = os.getenv('SUPABASE_URL', 'http://localhost:8000')
        self.key: str = os.getenv('SERVICE_ROLE_KEY')
        # self.key='UpNVntn3cDxHJpq99YMc1T1AQgQpc8kfYTuRgBiYa15BLrx8etQoXz3gZv1/u2oq'
        logger.info(f"Supabase URL: {self.url}")
        logger.info(f"Supabase Key: {self.key}")
        self.supabase: Client = create_client(self.url, self.key)
        logger.info("初始化成功")
    

    def test(self):
        try:
            response = self.supabase.table("sold_products").select("*").execute()
            logger.info(f"查询响应为{response}")
            # r_2=self.supabase.table("test").insert({"id": 2}).execute()
            # logger.info(f"插入响应为{r_2}")
        except APIError as e:
            logger.error(f"API Error: {e}")
        
    def insert_data(self, product_name: str, subscription_url: str, email: str, phone: str, duration_days: int = 365):
        """插入数据到 products 表"""
        end_time = f"now() + interval '{duration_days} days'"
        self.supabase.table("sold_products").insert({
            "subscription_url": subscription_url,
            "product_name": product_name,
            "email": email,
            "phone": phone,
            "end_time": end_time,
        }).execute()
        logger.info(f"Inserted product {product_name} for {email}")
        
    # def fetch_data_user(self,user_email: str="",phone: str=""):
    #     """获取用户的产品数据"""
    #     if not user_email:
    #         if phone:
    #             response = self.supabase.table("sold_products").select("product_name, subscription_url, email, phone, end_time").eq("phone", phone).execute()
    #             return response.data
    #         return []
    #     response = self.supabase.table("sold_products").select("product_name, subscription_url, email, phone, end_time").eq("email", user_email).execute()
    #     return response.data
    
    def fetch_data_user(self,user_email: str="",phone: str=""):
        """获取用户的产品数据（通过 SQL 函数）"""
        params = {
            "p_user_email": user_email or None,
            "p_phone": phone or None,
        }
        response = self.supabase.rpc("fetch_user_products", params).execute()
        return response.data or []