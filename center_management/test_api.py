import node_manage as nmanage
import vps_vultur_manage as vmanage
from loguru import logger
import subprocess
import os
import re
import csv
import random
from pathlib import Path
from datetime import datetime

hostname='202.182.106.233'
logger.info(f"默认测试服务器地址: {hostname}")
logger.info("本测试默认使用/root/.ssh/id_ed25519私钥文件，请确保该文件存在可用，且为云端私钥")

def test_add_user(hostname=hostname, proxy=None):
    """添加用户测试"""
    print("=== 添加用户测试 ===")

    if proxy is None:
        exit_status, hy2_link, out, err = nmanage.run_remote_self_sb_change(
            hostname=hostname,
            port=22,
            username='root',
            key_file='/root/.ssh/id_ed25519',
            port_arg=8957,
            name_arg='supo_alfa@go.com',
            up_mbps=50,
            down_mbps=50
        )
    else:
        # 使用提供的NodeProxy
        args = []
        args.append(f"-p {8957}")
        args.append(f"-n {nmanage.shlex.quote('supo_alfa@go.com')}")
        args.append(f"-u {50}")
        args.append(f"-d {50}")
        argstr = ' '.join(args)
        command = f"sudo /root/sing-box-v2ray/self_sb_change.sh {argstr}"
        logger.info(f"Executing remote script on {hostname}: {command}")

        exit_status, out, err = proxy.execute_command(command)

        # 尝试从 stdout 中解析 hy2_link，脚本以打印 hy2_link 为最后一部分
        hy2_link = None
        if out:
            m = re.search(r"hysteria2://[A-Za-z0-9\-._~%:@/?&=+#]+", out)
            if m:
                hy2_link = m.group(0)

    print(f"Exit Status: {exit_status}")
    print(f"HY2 Link: {hy2_link}")
    print(f"Output: {out}")
    print(f"Error: {err}")

    # 返回链接以便后续验证使用
    return hy2_link if exit_status == 0 else None

def test_verify_link(link=None, hostname=hostname):
    """验证hysteria2链接"""
    print("=== 链接验证测试 ===")

    # 获取脚本路径
    script_path = os.path.join(os.path.dirname(__file__), 'link_verificate.sh')

    if not os.path.exists(script_path):
        print(f"❌ 验证脚本不存在: {script_path}")
        return False

    # 如果没有提供链接，提示用户输入
    if link is None:
        print("⚠️  没有提供链接进行验证")
        print("请输入要验证的 hysteria2 链接:")
        print("(提示: 请先运行 '添加用户测试' 生成链接)")
        user_link = input("请输入链接 (或按回车退出): ").strip()

        if not user_link:
            print("取消链接验证")
            return False

        link = user_link

    # 验证链接格式
    if not re.match(r'^hysteria2://', link):
        print(f"❌ 无效的链接格式: {link}")
        print("链接应该以 hysteria2:// 开头")
        return False

    print(f"正在验证链接: {link[:50]}...")

    try:
        # 执行验证脚本
        result = subprocess.run(
            ['bash', script_path, '-z', link],
            capture_output=True,
            text=True,
            timeout=60  # 60秒超时
        )

        # 输出验证结果
        if result.stdout:
            print("验证输出:")
            print(result.stdout)

        if result.stderr:
            print("验证错误:")
            print(result.stderr)

        # 检查返回状态
        if result.returncode == 0:
            print("✅ 链接验证成功")
            return True
        else:
            print(f"❌ 链接验证失败，返回码: {result.returncode}")
            return False

    except subprocess.TimeoutExpired:
        print("❌ 链接验证超时")
        return False
    except Exception as e:
        print(f"❌ 链接验证异常: {e}")
        return False

def test_add_user_and_verify(hostname=hostname):
    """添加用户并验证链接（完整测试流程）"""
    print("=== 添加用户并验证链接（完整测试流程） ===")

    # 步骤1: 添加用户
    print("步骤 1: 添加用户...")
    link = test_add_user(hostname)

    if link is None:
        print("❌ 用户添加失败，无法进行链接验证")
        return False

    print("✅ 用户添加成功")

    # 步骤2: 等待服务启动
    print("步骤 2: 等待服务启动...")
    import time
    time.sleep(5)  # 等待5秒让服务启动

    # 步骤3: 验证链接
    print("步骤 3: 验证链接...")
    verification_result = test_verify_link(link, hostname)

    if verification_result:
        print("✅ 完整测试流程成功")
        return True
    else:
        print("❌ 链接验证失败")
        return False

def test_fetch_db(hostname=hostname, proxy=None):
    """远端数据读取测试"""
    print("=== 远端数据读取测试 ===")
    try:
        if proxy is None:
            # 使用新的直接查询方法
            x = nmanage.fetch_db_data_direct(
                hostname=hostname,
                username='root',
                key_file='/root/.ssh/id_ed25519',
            )
        else:
            logger.info(f"使用 Nodeproxy 从 {hostname} 直接获取数据库数据")
            # 使用提供的NodeProxy进行数据库直接查询
            x = nmanage.fetch_db_data_direct(
                hostname=hostname,
                username='root',
                key_file='/root/.ssh/id_ed25519',
                table_names=['users'],
                db_path='/var/lib/sing-box/v2api_stats.db'
            )

        print("数据库读取结果:")
        print(x)
    except Exception as e:
        print(f"数据库读取失败: {e}")
        # 尝试使用旧方法作为回退
        print("尝试使用旧方法作为回退...")
        try:
            x = nmanage.fetch_and_read_db(
                hostname=hostname,
                username='root',
                key_file='/root/.ssh/id_ed25519',
            )
            print("旧方法成功:")
            print(x)
        except Exception as e2:
            print(f"旧方法也失败: {e2}")

def test_save_csv(hostname=hostname, proxy=None):
    """远端数据读取保存为csv测试"""
    print("=== 远端数据读取保存为CSV测试 ===")
    try:
        # 使用新的直接查询方法获取数据
        data = nmanage.fetch_db_data_direct(
            hostname=hostname,
            username='root',
            key_file='/root/.ssh/id_ed25519',
            table_names=['users','alarm_status'],
            db_path='/var/lib/sing-box/v2api_stats.db'
        )

        # 当未指定 out_dir 时，默认保存至 ./csv/<hostname>/ 目录下
        from pathlib import Path
        import csv

        safe_host = str(hostname).replace(':', '_')
        out_dir = (Path('.') / 'csv' / safe_host).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        written = []
        for table, rows in data.items():
            fname = out_dir / f"{hostname.replace(':','_')}.{table}.csv"
            if not rows:
                with open(fname, 'w', newline='', encoding='utf-8') as f:
                    pass
                written.append(str(fname))
                continue
            cols = list(rows[0].keys())
            with open(fname, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=cols)
                writer.writeheader()
                for r in rows:
                    writer.writerow(r)
            written.append(str(fname))
        print(f"CSV文件保存成功: {written}")

    except Exception as e:
        print(f"CSV保存失败: {e}")
        # 尝试使用旧方法作为回退
        print("尝试使用旧方法作为回退...")
        try:
            nmanage.fetch_and_save_tables_csv(
                hostname=hostname,
                username='root',
                key_file='/root/.ssh/id_ed25519',
                table_names=['users','alarm_status'],
            )
            print("旧方法成功")
        except Exception as e2:
            print(f"旧方法也失败: {e2}")

def test_remote_ports(hostname=hostname, proxy=None):
    """获取远端端口测试"""
    print("=== 获取远端端口测试 ===")
    try:
        if proxy is None:
            ports_by_protocol = nmanage.get_remote_ports_by_protocol(
                hostname=hostname,
                port=22,
                username='root',
                key_file='/root/.ssh/id_ed25519'
            )
        else:
            # 使用提供的NodeProxy获取端口信息
            logger.info(f"Getting remote ports from {hostname}")

            # 先尝试 ss 命令，如果失败则使用 netstat 命令
            cmd = "ss -tuln"
            exit_status, output, error = proxy.execute_command(cmd, timeout=30)

            # 如果 ss 命令失败，尝试使用 netstat
            if exit_status != 0:
                logger.warning("ss command failed, trying netstat...")
                cmd = "netstat -tuln"
                exit_status, output, error = proxy.execute_command(cmd, timeout=30)

                if exit_status != 0:
                    logger.error(f"Both ss and netstat commands failed: {error}")
                    ports_by_protocol = {}
                else:
                    # 解析输出并按协议分组
                    ports_by_protocol = {'tcp': [], 'udp': [], 'tcp6': [], 'udp6': []}
                    for line in output.strip().split('\n'):
                        line = line.strip()
                        if not line or line.startswith('Netid') or line.startswith('Proto') or line.startswith('Active'):
                            continue

                        # 解析 ss/netstat 命令输出格式
                        parts = line.split()
                        if len(parts) >= 5:
                            protocol = parts[0].lower()
                            address = parts[4]  # Local Address:Port 在第5列

                            # 处理 IPv6 地址格式 [::]:port 或 127.0.0.1:port
                            if ']:' in address:
                                port_part = address.split(']:')[-1]
                            elif ':' in address:
                                port_part = address.split(':')[-1]
                            else:
                                port_part = address

                            # 移除可能的 * 前缀
                            port_part = port_part.lstrip('*')

                            if port_part.isdigit():
                                port = int(port_part)

                                # 根据地址类型判断协议版本
                                if '[' in address or '::' in address:
                                    protocol_key = f"{protocol}6"
                                else:
                                    protocol_key = protocol

                                if protocol_key in ports_by_protocol:
                                    if port not in ports_by_protocol[protocol_key]:
                                        ports_by_protocol[protocol_key].append(port)

                    # 过滤掉空列表并排序
                    ports_by_protocol = {k: sorted(v) for k, v in ports_by_protocol.items() if v}
            else:
                # 解析输出并按协议分组
                ports_by_protocol = {'tcp': [], 'udp': [], 'tcp6': [], 'udp6': []}
                for line in output.strip().split('\n'):
                    line = line.strip()
                    if not line or line.startswith('Netid') or line.startswith('Proto') or line.startswith('Active'):
                        continue

                    # 解析 ss/netstat 命令输出格式
                    parts = line.split()
                    if len(parts) >= 5:
                        protocol = parts[0].lower()
                        address = parts[4]  # Local Address:Port 在第5列

                        # 处理 IPv6 地址格式 [::]:port 或 127.0.0.1:port
                        if ']:' in address:
                            port_part = address.split(']:')[-1]
                        elif ':' in address:
                            port_part = address.split(':')[-1]
                        else:
                            port_part = address

                        # 移除可能的 * 前缀
                        port_part = port_part.lstrip('*')

                        if port_part.isdigit():
                            port = int(port_part)

                            # 根据地址类型判断协议版本
                            if '[' in address or '::' in address:
                                protocol_key = f"{protocol}6"
                            else:
                                protocol_key = protocol

                            if protocol_key in ports_by_protocol:
                                if port not in ports_by_protocol[protocol_key]:
                                    ports_by_protocol[protocol_key].append(port)

                # 过滤掉空列表并排序
                ports_by_protocol = {k: sorted(v) for k, v in ports_by_protocol.items() if v}

        if not ports_by_protocol:
            print("❌ 未获取到端口信息或获取失败")
            return False

        print("✅ 远端端口获取成功")
        print("\n按协议分组的端口列表:")

        for protocol, ports in ports_by_protocol.items():
            print(f"  {protocol.upper()}: {ports}")
            print(f"    端口数量: {len(ports)}")

        # 显示统计信息
        total_ports = sum(len(ports) for ports in ports_by_protocol.values())
        print(f"\n总计监听端口数: {total_ports}")

        return True

    except Exception as e:
        print(f"❌ 远端端口获取失败: {e}")
        return False

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

def test_shared_connection(hostname=hostname):
    """使用共享SSH连接的测试演示"""
    print("=== 使用共享SSH连接的测试演示 ===")

    try:
        # 创建一次SSH连接，然后复用
        print("1. 创建SSH连接...")
        proxy = nmanage.NodeProxy(hostname, 22, 'root', '/root/.ssh/id_ed25519')

        with proxy:
            print("✅ SSH连接已建立")

            # 2. 测试添加用户
            print("\n2. 测试添加用户...")
            link = test_add_user(hostname, proxy)
            if link:
                print("✅ 用户添加成功")
            else:
                print("❌ 用户添加失败")
                return False

            # 3. 测试获取远端端口
            logger.info("\n3. 测试获取远端端口...")
            if test_remote_ports(hostname, proxy):
                logger.info("✅ 端口获取成功")
            else:
                logger.error("❌ 端口获取失败")
                return False

            # 4. 测试数据库读取（使用新的直接查询方法）
            logger.info("4. 测试数据库读取（直接查询）...")
            data = nmanage.fetch_db_data_direct(
                hostname=hostname,
                username='root',
                key_file='/root/.ssh/id_ed25519',
                proxy=proxy,
                db_path='/var/lib/sing-box/v2api_stats.db'
            )
            logger.info(f"数据库读取成功: {len(data)} 个表")
            for table, rows in data.items():
                logger.info(f"  - {table}: {len(rows)} 条记录")

            # 5. 测试CSV保存（使用新的直接查询方法）
            logger.info("5. 测试CSV保存（直接查询）...")
            test_save_csv(hostname, proxy)

        logger.info("✅ 共享SSH连接测试完成，连接已自动关闭")
        return True

    except Exception as e:
        logger.error(f"❌ 共享SSH连接测试失败: {e}")
        return False

def get_or_create_port_csv(hostname, proxy):
    """获取或创建端口CSV文件

    参数:
        hostname: 远程服务器地址
        proxy: NodeProxy对象

    返回:
        str: CSV文件路径
    """
    # 创建csv目录
    csv_dir = Path('.') / 'csv'
    csv_dir.mkdir(exist_ok=True)

    # 生成CSV文件名
    safe_hostname = str(hostname).replace(':', '_')
    csv_file = csv_dir / f"{safe_hostname}_ports.csv"

    # 如果CSV文件不存在，创建它
    if not csv_file.exists():
        logger.info(f"创建端口CSV文件: {csv_file}")

        # 获取远程端口信息
        logger.info("获取远程端口信息...")
        ports_by_protocol = nmanage.get_remote_ports_by_protocol(
            hostname=hostname,
            port=22,
            username='root',
            key_file='/root/.ssh/id_ed25519',
            proxy=proxy
        )

        # 写入CSV文件
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['port', 'protocol', 'timestamp', 'status'])

            timestamp = datetime.now().isoformat()

            # 写入TCP端口
            for port in ports_by_protocol.get('tcp', []):
                writer.writerow([port, 'tcp', timestamp, 'used'])

            # 写入TCP6端口
            for port in ports_by_protocol.get('tcp6', []):
                writer.writerow([port, 'tcp6', timestamp, 'used'])

        logger.info(f"端口CSV文件创建完成，共写入 {sum(len(ports) for ports in ports_by_protocol.values())} 个端口")

    return str(csv_file)

def get_available_ports(hostname, proxy, min_port=10000, max_port=30000):
    """获取可用端口列表

    参数:
        hostname: 远程服务器地址
        proxy: NodeProxy对象
        min_port: 最小端口号
        max_port: 最大端口号

    返回:
        list: 可用端口列表
    """
    csv_file = get_or_create_port_csv(hostname, proxy)

    # 读取已使用的端口
    used_ports = set()
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['status'] == 'used':
                    used_ports.add(int(row['port']))
    except Exception as e:
        logger.error(f"读取端口CSV文件失败: {e}")
        return []

    # 生成可用端口列表
    available_ports = []
    for port in range(min_port, max_port + 1):
        if port not in used_ports:
            available_ports.append(port)

    logger.info(f"端口范围 {min_port}-{max_port} 内可用端口数量: {len(available_ports)}")
    return available_ports

def mark_port_as_used(csv_file, port, protocol='tcp'):
    """标记端口为已使用

    参数:
        csv_file: CSV文件路径
        port: 端口号
        protocol: 协议类型
    """
    try:
        # 读取现有数据
        ports = []
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                ports.append(row)

        # 检查端口是否已存在
        port_exists = any(int(p['port']) == port for p in ports)

        if not port_exists:
            # 添加新端口记录
            with open(csv_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([port, protocol, datetime.now().isoformat(), 'used'])
            logger.info(f"端口 {port} 已标记为已使用")
        else:
            logger.info(f"端口 {port} 已存在于CSV文件中")

    except Exception as e:
        logger.error(f"标记端口 {port} 为已使用失败: {e}")

def test_add_user_with_smart_port(name_arg, hostname=hostname, max_retries=3):
    """智能端口选择并添加用户

    参数:
        name_arg: 用户名参数
        hostname: 远程服务器地址（有默认值）
        max_retries: 最大重试次数

    返回:
        bool: 成功返回True，失败返回False
    """
    print("=== 智能端口选择并添加用户 ===")
    logger.info(f"开始智能端口选择，目标主机: {hostname}, 用户名: {name_arg}")

    try:
        # 创建SSH连接
        logger.info("创建SSH连接...")
        with nmanage.NodeProxy(hostname, 22, 'root', '/root/.ssh/id_ed25519') as proxy:
            logger.info("✅ SSH连接已建立")

            # 获取可用端口
            logger.info("获取可用端口列表...")
            available_ports = get_available_ports(hostname, proxy)

            if not available_ports:
                logger.error("没有可用的端口")
                return False

            # 获取CSV文件路径
            csv_file = get_or_create_port_csv(hostname, proxy)

            # 重试机制
            for retry in range(max_retries):
                logger.info(f"第 {retry + 1} 次尝试...")

                # 随机选择端口
                selected_port = random.choice(available_ports)
                logger.info(f"选择端口: {selected_port}")

                try:
                    # 调用添加用户函数
                    logger.info(f"使用端口 {selected_port} 添加用户 {name_arg}...")
                    exit_status, hy2_link, out, err = nmanage.run_remote_self_sb_change(
                        hostname=hostname,
                        port=22,
                        username='root',
                        key_file='/root/.ssh/id_ed25519',
                        port_arg=selected_port,
                        name_arg=name_arg,
                        up_mbps=50,
                        down_mbps=50
                    )

                    if exit_status == 0 and hy2_link:
                        logger.info(f"✅ 用户添加成功，端口: {selected_port}")
                        logger.info(f"HY2链接: {hy2_link}")

                        # 标记端口为已使用
                        mark_port_as_used(csv_file, selected_port)

                        # 验证链接
                        logger.info("验证链接...")
                        verify_result = test_verify_link(hy2_link, hostname)

                        if verify_result:
                            logger.info("✅ 链接验证成功")
                            print(f"✅ 用户 {name_arg} 添加成功，端口: {selected_port}")
                            print(f"✅ 链接验证通过")
                            return True
                        else:
                            logger.warning(f"⚠️ 链接验证失败，端口 {selected_port} 可能有问题")
                            # 从可用端口列表中移除
                            if selected_port in available_ports:
                                available_ports.remove(selected_port)

                    else:
                        logger.error(f"❌ 用户添加失败，端口: {selected_port}")
                        logger.error(f"退出状态: {exit_status}")
                        logger.error(f"错误信息: {err}")

                        # 从可用端口列表中移除
                        if selected_port in available_ports:
                            available_ports.remove(selected_port)

                        if not available_ports:
                            logger.error("没有更多可用的端口")
                            return False

                except Exception as e:
                    logger.error(f"添加用户时发生异常: {e}")
                    # 从可用端口列表中移除
                    if selected_port in available_ports:
                        available_ports.remove(selected_port)

            logger.error(f"达到最大重试次数 {max_retries}，添加用户失败")
            return False

    except Exception as e:
        logger.error(f"SSH连接失败: {e}")
        return False

def main():
    """主函数，提供交互式菜单"""
    tests = {
        '1': ('添加用户测试', test_add_user),
        '2': ('链接验证测试', test_verify_link),
        '3': ('添加用户并验证链接（完整测试）', test_add_user_and_verify),
        '4': ('远端数据读取测试', test_fetch_db),
        '5': ('远端数据读取保存为CSV测试', test_save_csv),
        '6': ('获取远端端口测试', test_remote_ports),
        '7': ('列出所有实例 IP 与区域', test_list_instances),
        '8': ('使用共享SSH连接的测试演示', test_shared_connection),
        '9': ('智能端口选择并添加用户', test_add_user_with_smart_port),
    }

    while True:
        print("\n请选择要执行的测试:")
        for key, (desc, _) in tests.items():
            print(f"{key}. {desc}")
        print("q. 退出")
        choice = input("\n请输入选择 (1-9, q): ").strip().lower()
        if choice == 'q':
            print("退出程序")
            break
        elif choice in tests:
            _, test_func = tests[choice]
            try:
                # 对于智能端口选择功能，需要额外的参数
                if choice == '9':
                    name_arg = input("请输入用户名 (例如: test@example.com): ").strip()
                    if name_arg:
                        test_func(name_arg)
                    else:
                        print("用户名不能为空")
                else:
                    test_func()
            except Exception as e:
                print(f"测试执行失败: {e}")
        else:
            print("无效选择，请重新输入")

if __name__ == '__main__':
    main()