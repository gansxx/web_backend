from . import node_manage as nmanage
from loguru import logger
import subprocess
import os
import re
import csv
import random
import time
from pathlib import Path
from datetime import datetime, timedelta


def _modify_hysteria2_link(hy2_link, url=None, alias=None, selected_port=None):
    """修改hysteria2链接中的IP地址和别名

    参数:
        hy2_link: 原始hysteria2链接
        url: 替换IP地址的URL
        alias: 替换末尾别名的参数
        selected_port: 选择的端口号

    返回:
        str: 修改后的链接
    """
    if not hy2_link:
        return hy2_link

    modified_link = hy2_link

    try:
        # 替换IP地址
        if url:
            # 使用正则表达式匹配和替换IP地址部分
            # 格式: hysteria2://uuid@ip:port?params#alias
            ip_pattern = r'(@)([^:]+)(:\d+)'
            modified_link = re.sub(ip_pattern, fr'\1{url}\3', modified_link)

        # 替换别名
        if alias:
            # 替换#后面的别名部分
            alias_pattern = r'(#)([^#]+)$'
            modified_link = re.sub(alias_pattern, fr'\1{alias}', modified_link)

    except Exception as e:
        logger.error(f"修改hysteria2链接失败: {e}")
        return hy2_link

    return modified_link


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


def verify_hy2_link_simple(link):
    """简化版hysteria2链接验证

    参数:
        link: hysteria2链接

    返回:
        bool: 验证是否成功
    """
    if not link or not link.startswith('hysteria2://'):
        logger.warning("链接格式无效")
        return False

    # 获取脚本路径
    script_path = os.path.join(os.path.dirname(__file__), 'link_verificate.sh')

    if not os.path.exists(script_path):
        logger.warning(f"验证脚本不存在: {script_path}")
        return False

    try:
        # 获取脚本所在目录作为工作目录
        script_dir = os.path.dirname(script_path)

        # 执行验证脚本
        result = subprocess.run(
            ['bash', script_path, '-z', link],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=script_dir  # 设置工作目录为脚本所在目录
        )

        if result.returncode == 0:
            logger.info("链接验证成功")
            if result.stdout.strip():
                logger.debug(f"验证输出: {result.stdout.strip()}")
            return True
        else:
            logger.warning(f"链接验证失败，返回码: {result.returncode}")
            if result.stderr.strip():
                logger.warning(f"错误输出: {result.stderr.strip()}")
            if result.stdout.strip():
                logger.debug(f"标准输出: {result.stdout.strip()}")
            return False

    except subprocess.TimeoutExpired:
        logger.warning("链接验证超时")
        return False
    except Exception as e:
        logger.error(f"链接验证异常: {e}")
        return False


def add_user_with_smart_port(proxy, name_arg, hostname=None, max_retries=3,
                           min_port=10000, max_port=30000,
                           up_mbps=50, down_mbps=50, verify_link=True,
                           url=None, alias=None):
    """智能端口选择并添加用户

    参数:
        proxy: NodeProxy对象（SSH连接）
        name_arg: 用户名
        hostname: 主机名（用于CSV文件命名，从proxy获取或使用默认值）
        max_retries: 最大重试次数
        min_port: 最小端口号
        max_port: 最大端口号
        up_mbps: 上传带宽限制
        down_mbps: 下载带宽限制
        verify_link: 是否验证生成的链接
        url: 替换链接中IP地址的URL (可选)
        alias: 替换链接末尾别名的参数 (可选)

    返回:
        tuple: (success, hy2_link, selected_port, details)
            - success: bool, 是否成功
            - hy2_link: str, 生成的hysteria2链接或None（已处理URL和别名替换）
            - selected_port: int, 选择的端口或None
            - details: dict, 详细信息包含错误信息等
    """
    # 默认hostname处理
    if hostname is None:
        hostname = getattr(proxy, 'hostname', 'unknown_host')

    details = {
        'attempts': 0,
        'errors': [],
        'available_ports_count': 0,
        'verification_result': None
    }

    logger.info(f"开始智能端口选择，目标主机: {hostname}, 用户名: {name_arg}")

    try:
        # 获取可用端口
        logger.info("获取可用端口列表...")
        available_ports = get_available_ports(hostname, proxy, min_port, max_port)
        details['available_ports_count'] = len(available_ports)

        if not available_ports:
            error_msg = "没有可用的端口"
            logger.error(error_msg)
            details['errors'].append(error_msg)
            return False, None, None, details

        # 获取CSV文件路径
        csv_file = get_or_create_port_csv(hostname, proxy)

        # 重试机制
        for retry in range(max_retries):
            details['attempts'] = retry + 1
            logger.info(f"第 {retry + 1} 次尝试...")

            # 随机选择端口
            selected_port = random.choice(available_ports)
            logger.info(f"选择端口: {selected_port}")

            try:
                # 调用添加用户函数
                logger.info(f"使用端口 {selected_port} 添加用户 {name_arg}...")
                exit_status, hy2_link, out, err = nmanage.run_remote_self_sb_change(
                    proxy=proxy,
                    port_arg=selected_port,
                    name_arg=name_arg,
                    up_mbps=up_mbps,
                    down_mbps=down_mbps
                )

                if exit_status == 0 and hy2_link:
                    logger.info(f"✅ 用户添加成功，端口: {selected_port}")
                    logger.info(f"原始HY2链接: {hy2_link}")

                    # 标记端口为已使用
                    mark_port_as_used(csv_file, selected_port)

                    # 先验证原始链接（使用IP地址，hysteria可以正常解析）
                    verification_success = True
                    if verify_link:
                        logger.info("验证原始链接（IP地址）...")
                        verification_success = verify_hy2_link_simple(hy2_link)
                        details['verification_result'] = verification_success

                    if verification_success:
                        logger.info("✅ 原始链接验证成功" if verify_link else "✅ 跳过链接验证")

                        # 原始链接验证成功后，进行链接替换逻辑
                        processed_link = hy2_link
                        if url or alias:
                            processed_link = _modify_hysteria2_link(hy2_link, url, alias, selected_port)
                            logger.info(f"处理后HY2链接: {processed_link}")

                        return True, processed_link, selected_port, details
                    else:
                        logger.warning(f"⚠️ 原始链接验证失败，端口 {selected_port} 可能有问题")
                        details['errors'].append(f"原始链接验证失败 (端口: {selected_port})")
                        # 从可用端口列表中移除
                        if selected_port in available_ports:
                            available_ports.remove(selected_port)

                else:
                    error_msg = f"用户添加失败，端口: {selected_port}, 退出状态: {exit_status}, 错误: {err}"
                    logger.error(error_msg)
                    details['errors'].append(error_msg)

                    # 从可用端口列表中移除
                    if selected_port in available_ports:
                        available_ports.remove(selected_port)

                    if not available_ports:
                        error_msg = "没有更多可用的端口"
                        logger.error(error_msg)
                        details['errors'].append(error_msg)
                        return False, None, None, details

            except Exception as e:
                error_msg = f"添加用户时发生异常: {e}"
                logger.error(error_msg)
                details['errors'].append(error_msg)
                # 从可用端口列表中移除
                if selected_port in available_ports:
                    available_ports.remove(selected_port)

        error_msg = f"达到最大重试次数 {max_retries}，添加用户失败"
        logger.error(error_msg)
        details['errors'].append(error_msg)
        return False, None, None, details

    except Exception as e:
        error_msg = f"智能端口选择过程失败: {e}"
        logger.error(error_msg)
        details['errors'].append(error_msg)
        return False, None, None, details


def get_port_statistics(hostname, proxy):
    """获取端口使用统计信息

    参数:
        hostname: 远程服务器地址
        proxy: NodeProxy对象

    返回:
        dict: 统计信息
    """
    try:
        csv_file = get_or_create_port_csv(hostname, proxy)

        stats = {
            'total_tracked': 0,
            'used_ports': 0,
            'available_in_range': 0,
            'protocols': {},
            'recent_additions': []
        }

        # 读取CSV文件统计
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                stats['total_tracked'] += 1
                if row['status'] == 'used':
                    stats['used_ports'] += 1

                protocol = row.get('protocol', 'unknown')
                stats['protocols'][protocol] = stats['protocols'].get(protocol, 0) + 1

        # 计算指定范围内的可用端口
        available_ports = get_available_ports(hostname, proxy)
        stats['available_in_range'] = len(available_ports)

        logger.info(f"端口统计: 总计跟踪 {stats['total_tracked']}, 已使用 {stats['used_ports']}, 可用 {stats['available_in_range']}")

        return stats

    except Exception as e:
        logger.error(f"获取端口统计失败: {e}")
        return {}


def cleanup_old_port_records(hostname, proxy, days_old=30):
    """清理旧的端口记录

    参数:
        hostname: 远程服务器地址
        proxy: NodeProxy对象
        days_old: 清理多少天前的记录

    返回:
        int: 清理的记录数量
    """
    try:
        csv_file = get_or_create_port_csv(hostname, proxy)

        # 获取当前远程端口
        current_ports = nmanage.get_remote_ports_by_protocol(proxy=proxy)
        current_tcp_ports = set(current_ports.get('tcp', []) + current_ports.get('tcp6', []))

        # 读取现有记录
        records = []
        cleaned_count = 0
        cutoff_date = datetime.now() - timedelta(days=days_old)

        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    record_date = datetime.fromisoformat(row['timestamp'])
                    port_num = int(row['port'])

                    # 保留记录的条件：
                    # 1. 仍在远程服务器上监听
                    # 2. 记录时间在清理阈值内
                    if port_num in current_tcp_ports or record_date > cutoff_date:
                        records.append(row)
                    else:
                        cleaned_count += 1
                        logger.debug(f"清理旧端口记录: {port_num} ({row['timestamp']})")

                except (ValueError, KeyError) as e:
                    # 保留有问题的记录而不是丢弃
                    logger.warning(f"解析端口记录时出错: {e}, 保留记录")
                    records.append(row)

        # 重写CSV文件
        if cleaned_count > 0:
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                if records:
                    fieldnames = records[0].keys()
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(records)
                else:
                    # 如果没有记录，写入表头
                    writer = csv.writer(f)
                    writer.writerow(['port', 'protocol', 'timestamp', 'status'])

            logger.info(f"清理了 {cleaned_count} 条旧端口记录")

        return cleaned_count

    except Exception as e:
        logger.error(f"清理端口记录失败: {e}")
        return 0