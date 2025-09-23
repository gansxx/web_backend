import node_manage as nmanage
import vps_vultur_manage as vmanage
from loguru import logger

hostname='202.182.106.233'
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

def test_list_instances():
    """列出当前所有后端实例的 IP 与区域"""
    print("=== 列出所有实例 IP 与区域 ===")
    try:
        data = vmanage.list_instances()
        instances = data.get('instances', []) if isinstance(data, dict) else []
        if not instances:
            print("当前没有实例或获取失败")
            return
        for inst in instances:
            iid = (inst.get('id') or inst.get('instance_id') or '').strip()
            label = (inst.get('label') or inst.get('hostname') or iid or '').strip()

            # 兼容不同返回结构下的 region 表示
            region_val = inst.get('region')
            if isinstance(region_val, dict):
                region = region_val.get('slug') or region_val.get('id') or region_val.get('name')
            else:
                region = region_val or inst.get('region_code') or inst.get('location')

            # 优先从列表字段取主 IP，不存在则调用按实例查询接口补充
            ip = inst.get('main_ip') or inst.get('ip')
            if not ip and iid:
                try:
                    ip = vmanage.get_instance_ip(iid)
                except Exception as e:
                    logger.warning(f"获取实例 {iid} IP 失败: {e}")
                    ip = '-'

            print(f"- {label or iid} | Region: {region or '-'} | IP: {ip or '-'}")
    except Exception as e:
        print(f"获取实例列表失败: {e}")

def main():
    """主函数，提供交互式菜单"""
    tests = {
        '1': ('添加用户测试', test_add_user),
        '2': ('远端数据读取测试', test_fetch_db),
        '3': ('远端数据读取保存为CSV测试', test_save_csv),
        '4': ('列出所有实例 IP 与区域', test_list_instances),
    }
    
    while True:
        print("\n请选择要执行的测试:")
        for key, (desc, _) in tests.items():
            print(f"{key}. {desc}")
        print("q. 退出")
        choice = input("\n请输入选择 (1-4, q): ").strip().lower()
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