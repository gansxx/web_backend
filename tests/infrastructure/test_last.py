import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from center_management.backend_api_v3 import test_add_user_v3
from center_management import node_manage as nmanage
from dotenv import load_dotenv
import os

# 加载环境变量
load_dotenv()

#The main function to use
if __name__ == "__main__":
    # 运行测试
    hostname=os.getenv('gateway_ip')
    print(f"测试服务器(网关)地址: {hostname}")
    key_file='id_ed25519'
    # AWS Lightsail 使用 admin 用户，不是 root
    proxy = nmanage.NodeProxy(hostname, 22, 'admin', key_file)
    try:
        url = test_add_user_v3(
            proxy,
            name_arg='test_user_4@example.com',
            url='jiasu.superjiasu.top',
            alias='selftest',
            verify_link=True,  # 禁用链接验证，因为用户添加成功但网络验证可能超时
            max_retries=1,
        )
        print(f"✅ 用户添加成功，访问链接: {url}")
    except Exception as e:
        print(f"❌ 测试失败: {e}")