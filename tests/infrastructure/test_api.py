from . import node_manage as nmanage
from . import vps_vultur_manage as vmanage
from loguru import logger
import subprocess
import os
import re
import csv
import random
import time
from pathlib import Path
from datetime import datetime
from .dns import DNSClient, get_global_dns_client

hostname='45.32.252.106'
logger.info(f"默认测试服务器地址: {hostname}")
logger.info("本测试默认使用id_ed25519私钥文件，请确保该文件存在可用，且为云端私钥")

def test_add_user(hostname=hostname, proxy=None):
    """添加用户测试"""
    print("=== 添加用户测试 ===")

    if proxy is None:
        with nmanage.NodeProxy(hostname, 22, 'root', 'id_ed25519') as proxy:
            exit_status, hy2_link, out, err = nmanage.run_remote_self_sb_change(
                proxy=proxy,
                port_arg=8957,
                name_arg='supo_alfa@go.com',
                up_mbps=50,
                down_mbps=50
            )
    else:
        # 使用提供的NodeProxy
        exit_status, hy2_link, out, err = nmanage.run_remote_self_sb_change(
            proxy=proxy,
            port_arg=8957,
            name_arg='supo_alfa@go.com',
            up_mbps=50,
            down_mbps=50
        )

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
            with nmanage.NodeProxy(hostname, 22, 'root', '/root/.ssh/id_ed25519') as proxy:
                x = nmanage.fetch_db_data_direct(proxy=proxy)
        else:
            logger.info(f"使用 Nodeproxy 从 {hostname} 直接获取数据库数据")
            # 使用提供的NodeProxy进行数据库直接查询
            x = nmanage.fetch_db_data_direct(
                proxy=proxy,
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
        with nmanage.NodeProxy(hostname, 22, 'root', '/root/.ssh/id_ed25519') as proxy:
            data = nmanage.fetch_db_data_direct(
                proxy=proxy,
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
            with nmanage.NodeProxy(hostname, 22, 'root', '/root/.ssh/id_ed25519') as proxy:
                ports_by_protocol = nmanage.get_remote_ports_by_protocol(proxy=proxy)
        else:
            # 使用提供的NodeProxy获取端口信息
            ports_by_protocol = nmanage.get_remote_ports_by_protocol(proxy=proxy)

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
        ports_by_protocol = nmanage.get_remote_ports_by_protocol(proxy=proxy)

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
                    # 调用添加用户函数（复用现有proxy连接）
                    logger.info(f"使用端口 {selected_port} 添加用户 {name_arg}...")
                    exit_status, hy2_link, out, err = nmanage.run_remote_self_sb_change(
                        hostname=hostname,
                        port=22,
                        username='root',
                        key_file='/root/.ssh/id_ed25519',
                        port_arg=selected_port,
                        name_arg=name_arg,
                        up_mbps=50,
                        down_mbps=50,
                        proxy=proxy
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

def test_dns_client_initialization():
    """DNS客户端初始化测试"""
    print("=== DNS客户端初始化测试 ===")

    try:
        # 测试从环境变量初始化
        logger.info("尝试从环境变量初始化DNS客户端...")
        dns_client = DNSClient()

        # 验证凭证
        logger.info("验证DNS凭证...")
        if dns_client.validate_credentials():
            print("✅ DNS客户端初始化成功")
            print("✅ DNS凭证验证通过")
            return True
        else:
            print("❌ DNS凭证验证失败")
            print("❌ 请检查 TENCENTCLOUD_SECRET_ID 和 TENCENTCLOUD_SECRET_KEY 环境变量")
            return False

    except Exception as e:
        logger.error(f"❌ DNS客户端初始化失败: {e}")
        print(f"❌ DNS客户端初始化失败: {e}")
        print("❌ 请确保已正确设置腾讯云DNS凭证")
        return False

def test_dns_create_record(domain=None, subdomain=None, ip_address=None, record_type="A"):
    """DNS记录创建测试

    参数:
        domain: 域名（如example.com）
        subdomain: 子域名（如www或@）
        ip_address: IP地址
        record_type: 记录类型（A、CNAME等）

    返回:
        bool: 成功返回True，失败返回False
    """
    print("=== DNS记录创建测试 ===")

    try:
        # 初始化DNS客户端
        dns_client = get_global_dns_client()

        # 验证客户端初始化
        if not dns_client.validate_credentials():
            print("❌ DNS客户端初始化失败，请检查凭证")
            return False

        # 如果没有提供参数，使用交互式输入
        if domain is None:
            domain = input("请输入域名 (例如: example.com): ").strip()

        if subdomain is None:
            subdomain = input("请输入子域名 (例如: www 或 @): ").strip()

        if ip_address is None:
            ip_address = input("请输入IP地址 (例如: 1.2.3.4): ").strip()

        # 验证输入参数
        if not domain or not subdomain or not ip_address:
            print("❌ 域名、子域名和IP地址都不能为空")
            return False

        # 验证IP地址格式
        import re
        if not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip_address):
            print(f"❌ 无效的IP地址格式: {ip_address}")
            return False

        logger.info(f"开始创建DNS记录: {subdomain}.{domain} -> {ip_address}")

        # 调用DNS客户端创建记录方法
        success = dns_client.create_record(
            domain=domain,
            value=ip_address,
            subdomain=subdomain,
            record_type=record_type,
            record_line="默认",
            ttl=600
        )

        if success:
            print(f"✅ DNS记录创建请求已发送")
            print(f"   域名: {subdomain}.{domain}")
            print(f"   记录类型: {record_type}")
            print(f"   IP地址: {ip_address}")
            print(f"   TTL: 600")
            return True
        else:
            print("❌ DNS记录创建失败")
            return False

    except Exception as e:
        logger.error(f"❌ DNS记录创建失败: {e}")
        print(f"❌ DNS记录创建失败: {e}")
        return False

def test_dns_status(domain=None, subdomain=None, expected_ip=None):
    """DNS解析状态测试

    参数:
        domain: 域名（如example.com）
        subdomain: 子域名（如www或@）
        expected_ip: 期望的IP地址

    返回:
        bool: 解析成功返回True，失败返回False
    """
    print("=== DNS解析状态测试 ===")

    try:
        # 初始化DNS客户端
        dns_client = get_global_dns_client()

        # 如果没有提供参数，使用交互式输入
        if domain is None:
            domain = input("请输入域名 (例如: example.com): ").strip()

        if subdomain is None:
            subdomain = input("请输入子域名 (例如: www 或 @): ").strip()

        if expected_ip is None:
            expected_ip = input("请输入期望的IP地址 (可选，留空只查看解析结果): ").strip()

        # 验证输入参数
        if not domain or not subdomain:
            print("❌ 域名和子域名都不能为空")
            return False

        logger.info(f"检查DNS解析状态: {subdomain}.{domain}")

        # 调用DNS客户端状态检查方法
        is_match, resolved_ips = dns_client.dns_status(domain, subdomain, expected_ip if expected_ip else "")

        print(f"域名: {subdomain}.{domain}")
        print(f"解析结果: {resolved_ips}")

        if expected_ip:
            if is_match:
                print(f"✅ DNS解析成功，匹配期望IP: {expected_ip}")
            else:
                print(f"❌ DNS解析不匹配，期望IP: {expected_ip}，实际IP: {resolved_ips}")
        else:
            print("✅ DNS解析检查完成")

        return is_match if expected_ip else bool(resolved_ips)

    except Exception as e:
        logger.error(f"❌ DNS解析检查失败: {e}")
        print(f"❌ DNS解析检查失败: {e}")
        return False

def test_dns_full_workflow(domain=None, subdomain=None, ip_address=None):
    """DNS完整工作流测试：创建记录 → 等待生效 → 检查状态

    参数:
        domain: 域名（如example.com）
        subdomain: 子域名（如www或@）
        ip_address: IP地址

    返回:
        bool: 完整流程成功返回True，失败返回False
    """
    print("=== DNS完整工作流测试 ===")

    try:
        # 初始化DNS客户端
        dns_client = get_global_dns_client()

        # 验证客户端初始化
        if not dns_client.validate_credentials():
            print("❌ DNS客户端初始化失败，请检查凭证")
            return False

        # 如果没有提供参数，使用交互式输入
        if domain is None:
            domain = input("请输入域名 (例如: example.com): ").strip()

        if subdomain is None:
            subdomain = input("请输入子域名 (例如: www 或 @): ").strip()

        if ip_address is None:
            ip_address = input("请输入IP地址 (例如: 1.2.3.4): ").strip()

        # 验证输入参数
        if not domain or not subdomain or not ip_address:
            print("❌ 域名、子域名和IP地址都不能为空")
            return False

        # 步骤1: 创建DNS记录
        print("步骤 1: 创建DNS记录...")
        logger.info(f"创建DNS记录: {subdomain}.{domain} -> {ip_address}")
        create_result = dns_client.create_record(
            domain=domain,
            value=ip_address,
            subdomain=subdomain,
            record_type="A",
            record_line="默认",
            ttl=600
        )
        if not create_result:
            print("❌ DNS记录创建失败")
            return False
        print("✅ DNS记录创建成功")

        # 步骤2: 等待DNS生效
        print("步骤 2: 等待DNS生效...")
        import time
        print("⏳ 等待60秒让DNS记录生效...")
        time.sleep(60)

        # 步骤3: 检查DNS状态
        print("步骤 3: 检查DNS解析状态...")
        logger.info(f"检查DNS解析状态: {subdomain}.{domain} -> {ip_address}")
        status_result = dns_client.dns_status(domain, subdomain, ip_address)

        if status_result[0]:  # status_result 是一个 tuple (is_match, ips)
            print("✅ DNS完整工作流测试成功")
            print(f"✅ 域名 {subdomain}.{domain} 成功解析到 {ip_address}")
            return True
        else:
            print("❌ DNS解析检查失败，可能需要更长时间生效")
            print(f"❌ 当前解析结果: {status_result[1]}")
            return False

    except Exception as e:
        logger.error(f"❌ DNS完整工作流测试失败: {e}")
        print(f"❌ DNS完整工作流测试失败: {e}")
        return False

def test_subscription_out(hostname=hostname, target_domain=None, subdomain="test"):
    """订阅链接生成测试(IP转域名)

    将hysteria2链接中的IP地址转换为域名，并验证功能

    参数:
        hostname: 远程服务器地址
        target_domain: 目标域名 (如 example.com)
        subdomain: 子域名前缀 (默认: test)

    返回:
        str: 转换后的hysteria2链接，失败返回None
    """
    print("=== 订阅链接生成测试(IP转域名) ===")

    # 初始化时间和日志
    start_time = time.time()
    log_entries = []
    execution_log = []

    def log_stage(stage_name, duration, success=True, details=""):
        """记录阶段日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        status = "✅" if success else "❌"
        log_entry = f"[{timestamp}] {status} {stage_name}: {duration:.3f}s - {details}"
        log_entries.append(log_entry)
        execution_log.append({
            'stage': stage_name,
            'duration': duration,
            'success': success,
            'details': details,
            'timestamp': timestamp
        })
        print(log_entry)
        logger.info(log_entry)

    try:
        # 阶段1: 获取目标域名参数
        stage_start = time.time()
        if target_domain is None:
            target_domain = input("请输入目标域名 (例如: example.com): ").strip()
            if not target_domain:
                print("❌ 目标域名不能为空")
                return None

        # 验证域名格式
        if not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)+$', target_domain):
            print(f"❌ 无效的域名格式: {target_domain}")
            return None

        stage_duration = time.time() - stage_start
        log_stage("域名参数获取", stage_duration, True, f"目标域名: {target_domain}, 子域名: {subdomain}")

        # 阶段2: 调用test_add_user获取原始链接
        stage_start = time.time()
        print("阶段 2: 添加用户获取原始链接...")
        original_link = test_add_user(hostname)
        if not original_link:
            stage_duration = time.time() - stage_start
            log_stage("用户创建", stage_duration, False, "无法获取原始hysteria2链接")
            return None

        stage_duration = time.time() - stage_start
        log_stage("用户创建", stage_duration, True, f"获取到原始链接: {original_link[:80]}...")

        # 阶段3: 解析hysteria2链接提取IP
        stage_start = time.time()
        print("阶段 3: 解析hysteria2链接...")

        # 解析hysteria2链接格式: hysteria2://auth@host:port?query
        import urllib.parse as urlparse
        try:
            parsed = urlparse.urlparse(original_link)
            host_port = parsed.netloc.split('@')[-1]  # 移除认证部分
            host = host_port.split(':')[0]  # 移除端口部分

            # 验证是否为IP地址
            if not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', host):
                stage_duration = time.time() - stage_start
                log_stage("链接解析", stage_duration, False, f"提取的host不是IP地址: {host}")
                return None

            ip_address = host

        except Exception as e:
            stage_duration = time.time() - stage_start
            log_stage("链接解析", stage_duration, False, f"解析失败: {e}")
            return None

        stage_duration = time.time() - stage_start
        log_stage("链接解析", stage_duration, True, f"提取到IP地址: {ip_address}")

        # 阶段4: 创建DNS记录
        stage_start = time.time()
        print("阶段 4: 创建DNS记录...")

        try:
            dns_client = get_global_dns_client()
            if not dns_client.validate_credentials():
                stage_duration = time.time() - stage_start
                log_stage("DNS客户端验证", stage_duration, False, "DNS客户端初始化失败")
                return None

            # 创建DNS记录
            full_domain = f"{subdomain}.{target_domain}"

            try:
                dns_success = dns_client.create_record(
                    domain=target_domain,
                    value=ip_address,
                    subdomain=subdomain,
                    record_type="A",
                    record_line="默认",
                    ttl=600
                )

                if dns_success:
                    stage_duration = time.time() - stage_start
                    log_stage("DNS记录创建", stage_duration, True, f"DNS记录已创建: {full_domain} -> {ip_address}")
                else:
                    stage_duration = time.time() - stage_start
                    log_stage("DNS记录创建", stage_duration, False, f"无法创建DNS记录: {full_domain} -> {ip_address}")
                    return None

            except Exception as e:
                error_str = str(e)
                # 检查是否是记录已存在的错误
                if "InvalidParameter.DomainRecordExist" in error_str and "记录已经存在，无需再次添加" in error_str:
                    stage_duration = time.time() - stage_start
                    print(f"⚠️  DNS记录已存在: {full_domain}")

                    # 提供用户选择
                    print("请选择操作:")
                    print("1. 跳过DNS记录创建，继续测试")
                    print("2. 使用不同的子域名")
                    print("3. 退出测试")

                    choice = input("请输入选择 (1/2/3): ").strip()

                    if choice == "1":
                        # 跳过DNS创建，继续测试
                        log_stage("DNS记录创建", stage_duration, True, f"跳过已存在的DNS记录: {full_domain}")
                        print(f"✅ 跳过DNS记录创建，继续使用现有记录: {full_domain}")
                    elif choice == "2":
                        # 使用不同的子域名
                        new_subdomain = input("请输入新的子域名前缀: ").strip()
                        if not new_subdomain:
                            print("❌ 子域名不能为空")
                            return None

                        # 尝试创建新的DNS记录
                        try:
                            new_full_domain = f"{new_subdomain}.{target_domain}"
                            dns_success = dns_client.create_record(
                                domain=target_domain,
                                value=ip_address,
                                subdomain=new_subdomain,
                                record_type="A",
                                record_line="默认",
                                ttl=600
                            )

                            if dns_success:
                                full_domain = new_full_domain
                                subdomain = new_subdomain
                                log_stage("DNS记录创建", stage_duration, True, f"使用新子域名创建DNS记录: {full_domain} -> {ip_address}")
                                print(f"✅ 使用新子域名成功创建DNS记录: {full_domain}")
                            else:
                                log_stage("DNS记录创建", stage_duration, False, f"无法创建新DNS记录: {new_full_domain}")
                                return None

                        except Exception as e2:
                            stage_duration = time.time() - stage_start
                            log_stage("DNS记录创建", stage_duration, False, f"创建新DNS记录失败: {e2}")
                            return None
                    elif choice == "3":
                        # 退出测试
                        stage_duration = time.time() - stage_start
                        log_stage("DNS记录创建", stage_duration, False, "用户选择退出测试")
                        return None
                    else:
                        print("❌ 无效选择，退出测试")
                        stage_duration = time.time() - stage_start
                        log_stage("DNS记录创建", stage_duration, False, "用户选择了无效选项")
                        return None
                else:
                    # 其他类型的错误
                    stage_duration = time.time() - stage_start
                    log_stage("DNS记录创建", stage_duration, False, f"创建失败: {e}")
                    return None

        except Exception as e:
            # DNS客户端验证阶段的异常处理
            stage_duration = time.time() - stage_start
            log_stage("DNS客户端验证", stage_duration, False, f"DNS客户端初始化异常: {e}")
            return None

        # 阶段5: 生成新的hysteria2链接
        stage_start = time.time()
        print("阶段 5: 生成新的hysteria2链接...")

        try:
            # 替换原始链接中的IP为域名
            new_link = original_link.replace(ip_address, full_domain)

            # 验证新链接格式
            if not new_link.startswith('hysteria2://'):
                stage_duration = time.time() - stage_start
                log_stage("新链接生成", stage_duration, False, "生成的链接格式不正确")
                return None

        except Exception as e:
            stage_duration = time.time() - stage_start
            log_stage("新链接生成", stage_duration, False, f"生成失败: {e}")
            return None

        stage_duration = time.time() - stage_start
        log_stage("新链接生成", stage_duration, True, f"新链接: {new_link[:50]}...")

        # 阶段6: 测试DNS状态
        stage_start = time.time()
        print("阶段 6: 测试DNS解析状态...")

        try:
            # 等待DNS传播
            print("等待DNS传播(30秒)...")
            time.sleep(30)

            # 检查DNS状态
            dns_status, resolved_ips = dns_client.dns_status(target_domain, subdomain, ip_address)

            if not dns_status:
                stage_duration = time.time() - stage_start
                log_stage("DNS状态检查", stage_duration, False, f"DNS未正确解析: {resolved_ips}")
                return None

        except Exception as e:
            stage_duration = time.time() - stage_start
            log_stage("DNS状态检查", stage_duration, False, f"检查失败: {e}")
            return None

        stage_duration = time.time() - stage_start
        log_stage("DNS状态检查", stage_duration, True, f"DNS解析成功: {resolved_ips}")

        # 阶段7: 验证新链接
        stage_start = time.time()
        print("阶段 7: 验证新链接...")

        try:
            # 等待服务更新
            print("等待服务更新(10秒)...")
            time.sleep(10)

            verification_result = test_verify_link(new_link, hostname)
            if not verification_result:
                stage_duration = time.time() - stage_start
                log_stage("新链接验证", stage_duration, False, "新链接验证失败")
                return None

        except Exception as e:
            stage_duration = time.time() - stage_start
            log_stage("新链接验证", stage_duration, False, f"验证失败: {e}")
            return None

        stage_duration = time.time() - stage_start
        log_stage("新链接验证", stage_duration, True, "新链接验证成功")

        # 计算总执行时间
        total_duration = time.time() - start_time

        # 保存执行日志到文件
        log_filename = f"subscription_out_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        try:
            with open(log_filename, 'w', encoding='utf-8') as f:
                f.write(f"订阅链接生成测试执行日志\n")
                f.write(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"总执行时间: {total_duration:.3f}s\n")
                f.write(f"目标域名: {target_domain}\n")
                f.write(f"子域名: {subdomain}\n")
                f.write(f"完整域名: {full_domain}\n")
                f.write(f"原始IP: {ip_address}\n")
                f.write(f"原始链接: {original_link}\n")
                f.write(f"新链接: {new_link}\n")
                f.write("\n=== 详细执行日志 ===\n")
                for entry in log_entries:
                    f.write(f"{entry}\n")

            print(f"✅ 执行日志已保存到: {log_filename}")

        except Exception as e:
            print(f"❌ 保存日志文件失败: {e}")

        # 最终结果
        log_stage("总执行时间", total_duration, True, f"订阅链接生成成功")
        print(f"\n🎉 订阅链接生成测试成功!")
        print(f"📋 原始链接: {original_link}")
        print(f"📋 新链接: {new_link}")
        print(f"📋 DNS记录: {full_domain} -> {ip_address}")
        print(f"⏱️  总执行时间: {total_duration:.3f}秒")

        return new_link

    except Exception as e:
        total_duration = time.time() - start_time
        log_stage("总执行时间", total_duration, False, f"测试执行失败: {e}")
        logger.error(f"❌ 订阅链接生成测试失败: {e}")
        return None

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
        '10': ('DNS客户端初始化测试', test_dns_client_initialization),
        '11': ('DNS记录创建测试', test_dns_create_record),
        '12': ('DNS解析状态测试', test_dns_status),
        '13': ('DNS完整工作流测试', test_dns_full_workflow),
        '14': ('订阅链接生成测试(IP转域名)', test_subscription_out),
    }

    while True:
        print("\n请选择要执行的测试:")
        for key, (desc, _) in tests.items():
            print(f"{key}. {desc}")
        print("q. 退出")
        choice = input("\n请输入选择 (1-14, q): ").strip().lower()
        if choice == 'q':
            print("退出程序")
            break
        elif choice in tests:
            _, test_func = tests[choice]
            try:
                # 对于需要额外参数的功能
                if choice == '9':
                    name_arg = input("请输入用户名 (例如: test@example.com): ").strip()
                    if name_arg:
                        test_func(name_arg)
                    else:
                        print("用户名不能为空")
                elif choice == '14':
                    # 订阅链接生成测试需要域名参数
                    domain_arg = input("请输入目标域名 (例如: example.com): ").strip()
                    subdomain_arg = input("请输入子域名前缀 (默认: test): ").strip() or "test"
                    if domain_arg:
                        test_func(target_domain=domain_arg, subdomain=subdomain_arg)
                    else:
                        print("目标域名不能为空")
                else:
                    test_func()
            except Exception as e:
                print(f"测试执行失败: {e}")
        else:
            print("无效选择，请重新输入")

if __name__ == '__main__':
    main()