from fastapi import APIRouter
from fastapi.responses import Response
# from loguru import logger
# import os
from datetime import datetime, timezone


#后期在这里添加对应的数据查询逻辑
#在supabase中单独创建一个schema用于保存节点
#需要同步修改前端的教程，改为clash格式，从而为用户生成续订的方式
router = APIRouter(tags=["test"])
@router.get(f"/test/url")
async def return_url():
    test_url="hysteria2://9d5cbf0d-ee29-40d1-b3d6-7d0966b54e@unlimited.selfgo.asia:264?sni=www.bing.com&alpn=h3&insecure=1#unlimited_plan"

    # 创建响应对象并添加自定义头
    response = Response(
        content=test_url,
        media_type="text/plain"
    )
    # 1. 当前时间 → 秒级时间戳（float）
    dt = datetime(2026, 6, 25, 12, 0, 0, tzinfo=timezone.utc)
    ts = int(dt.timestamp())

    # 添加订阅信息头
    response.headers["subscription-userinfo"] = f"upload=455727941; download=6174315083; total=1073741824000; expire={ts}"
    response.headers["support-url"] = "https://t.me/hiddify"
    response.headers["profile-web-page-url"] = "https://hiddify.com"
    response.headers["profile-update-interval"]= "12"
    response.headers["profile-title"]="I love hiddify"
    response.headers["content-disposition"]= "attachment; filename=abc.txt"

    return response