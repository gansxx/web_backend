import sys
import os
from loguru import logger
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import spdb_init as sq

sq_db = sq.spdbConfig()

logger.info("开始初始化数据库表")
# s=sq_db.test()
# logger.info(f"响应为{s}")
r=sq_db.fetch_data_user("2021020024@email.szu.cn")
logger.info(f"响应为{r}")
# logger.info("开始插入测试数据")
# sq_db.insert_data(
#             product_name="测试套餐",
#             subscription_url="https://test.com/path?param=value&other='test'",
#             email="2021020024@example.com",
#             phone=""
#         )
# sq_db.fetch_data_user("2021020024@example.com")