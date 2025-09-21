import node_manage as nmanage
from loguru import logger

hostname='45.32.252.10'
print(f"默认测试服务器地址: {hostname}")
logger.info("本测试默认使用/root/.ssh/id_ed25519私钥文件，请确保该文件存在可用，且为云端私钥")
def test_add_user(hostname=hostname):
    """添加用户测试"""
    print("=== 添加用户测试 ===")
    
    exit_status, hy2_link, out, err = nmanage.run_remote_self_sb_change(
        hostname=hostname,
        port=22,
        username='root',
        key_file='/root/.ssh/id_ed25519',
        port_arg=9993,
        name_arg='supo@go.com',
        up_mbps=50,
        down_mbps=50
    )
    print(f"Exit Status: {exit_status}")
    print(f"HY2 Link: {hy2_link}")
    print(f"Output: {out}")
    print(f"Error: {err}")

def test_fetch_db(hostname=hostname):
    """远端数据读取测试"""
    print("=== 远端数据读取测试 ===")
    try:
        x = nmanage.fetch_and_read_db(
            hostname=hostname,
            username='root',
            key_file='id_ed25519',
        )
        print("数据库读取结果:")
        print(x)
    except Exception as e:
        print(f"数据库读取失败: {e}")

def test_save_csv(hostname=hostname):
    """远端数据读取保存为csv测试"""
    print("=== 远端数据读取保存为CSV测试 ===")
    try:
        nmanage.fetch_and_save_tables_csv(
            hostname=hostname,
            username='root',
            key_file='id_ed25519',
            table_names=['users','alarm_status'],
        )
        print("CSV文件保存成功")
    except Exception as e:
        print(f"CSV保存失败: {e}")

def main():
    """主函数，提供交互式菜单"""
    tests = {
        '1': ('添加用户测试', test_add_user),
        '2': ('远端数据读取测试', test_fetch_db),
        '3': ('远端数据读取保存为CSV测试', test_save_csv),
    }
    
    while True:
        print("\n请选择要执行的测试:")
        for key, (desc, _) in tests.items():
            print(f"{key}. {desc}")
        print("q. 退出")
        
        choice = input("\n请输入选择 (1-3, q): ").strip().lower()
        
        if choice == 'q':
            print("退出程序")
            break
        elif choice in tests:
            _, test_func = tests[choice]
            try:
                test_func()
            except Exception as e:
                print(f"测试执行失败: {e}")
        else:
            print("无效选择，请重新输入")

if __name__ == '__main__':
    main()