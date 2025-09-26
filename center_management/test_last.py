from test_api_v2 import test_add_user_v2
import node_manage as nmanage

#The main function to use
if __name__ == "__main__":
    # 运行测试
    hostname='45.32.252.106'
    key_file='id_ed25519'
    proxy = nmanage.NodeProxy(hostname, 22, 'root', key_file)
    try:
        url = test_add_user_v2(
            proxy,
            name_arg='test_user_4@example.com',
            url='jiasu.selfgo.asia',
            alias='selftest',
            verify_link=True,
            max_retries=1,
        )
        print(f"✅ 用户添加成功，访问链接: {url}")
    except Exception as e:
        print(f"❌ 测试失败: {e}")