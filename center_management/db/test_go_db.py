import sys
import os
from loguru import logger
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


logger.info("开始初始化数据库表")
# s=sq_db.test()
# logger.info(f"响应为{s}")
# r=sq_db.fetch_data_user("2021020024@email.szu.cn")
from order import OrderConfig  
from product import ProductConfig
order_config = OrderConfig()
product_config = ProductConfig()
# r=order_config.fetch_order_user("2021020024@email.szu.cn")
# logger.info(f"fetch_order_user的响应为{r}")
# r=product_config.fetch_product_user("2021020024@email.szu.cn")
# logger.info(f"fetch_product_user的响应为{r}")
# r=product_config.insert_product(product_name="测试产品", subscription_url="https://test.com", email="2021020024@email.szu.cn", duration_days=30, phone="")
# logger.info(f"insert_product的响应为{r}")
r=order_config.insert_order(product_name="测试产品", trade_num=1, amount=100, email="2021020024@email.szu.cn", phone="")
logger.info(f"insert_order的响应为{r}")
r=order_config.cleanup_processed_timeout_trackers(0)
logger.info(f"clear_timeout_tracker_records的响应为{r}")
# r=order_config.update_order_status(order_id=r, status="已完成")
# logger.info(f"update_order_status的响应为{r}")