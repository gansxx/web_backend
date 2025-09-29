from . import node_manage as nmanage
from loguru import logger
import subprocess
import os
import re
import csv
import random
import time
from pathlib import Path
from datetime import datetime
from .dns import dns_status

hostname = '45.32.252.106'
key_file = 'id_ed25519'
logger.info(f"默认测试服务器地址: {hostname}")
logger.info(f"本测试默认使用{key_file}私钥文件，请确保该文件存在可用，且为云端私钥")


def test_add_user_v2(proxy, name_arg='test_user_2@example.com', url=None, alias=None, **kwargs):
    """智能端口选择并添加用户 (v2版本 - 使用智能端口管理器)

    参数:
        proxy: NodeProxy对象
        name_arg: 用户名参数
        url: 替换链接中IP地址的URL (可选)
        alias: 替换链接末尾别名的参数 (可选)
        **kwargs: 其他参数传递给智能端口管理器
            - max_retries: 最大重试次数 (默认: 3)
            - min_port: 最小端口号 (默认: 10000)
            - max_port: 最大端口号 (默认: 30000)
            - up_mbps: 上传带宽限制 (默认: 50)
            - down_mbps: 下载带宽限制 (默认: 50)
            - verify_link: 是否验证链接 (默认: True)

    返回:
        str: 处理后的hysteria2链接（已包含URL和别名替换），失败返回None
    """
    from smart_port_manager import add_user_with_smart_port

    # 记录函数开始时间
    start_time = time.perf_counter()

    logger.info("=== 智能端口选择并添加用户 (v2) ===")

    # DNS状态检查（如果提供了URL）
    if url:
        logger.info(f"检查域名DNS状态: {url}")
        try:
            # 假设url格式为域名，提取主域名和子域名
            if '.' in url:
                parts = url.split('.')
                if len(parts) >= 2:
                    subdomain = parts[0] if len(parts) > 2 else '@'
                    domain = '.'.join(parts[-2:]) if len(parts) > 2 else url

                    # 检查DNS解析是否指向正确的hostname
                    is_match, resolved_ips = dns_status(domain, subdomain, hostname)

                    logger.info(f"DNS解析结果: 域名={url}, 解析IP={resolved_ips}, 目标IP={hostname}")

                    if not is_match:
                        error_msg = f"DNS解析失败: {url} 未解析到目标IP {hostname}, 当前解析到: {resolved_ips}"
                        logger.error(error_msg)
                        return None
                    else:
                        logger.info(f"✅ DNS验证通过: {url} 正确解析到 {hostname}")
        except Exception as e:
            logger.error(f"DNS状态检查失败: {e}")
            logger.warning("跳过DNS检查，继续执行...")

    # 设置默认参数
    default_kwargs = {
        'hostname': hostname,
        'max_retries': 3,
        'min_port': 10000,
        'max_port': 30000,
        'up_mbps': 50,
        'down_mbps': 50,
        'verify_link': True
    }
    default_kwargs.update(kwargs)

    try:
        success, hy2_link, selected_port, details = add_user_with_smart_port(
            proxy=proxy,
            name_arg=name_arg,
            url=url,
            alias=alias,
            **default_kwargs
        )

        if success:
            logger.info(f"✅ 用户 {name_arg} 添加成功")
            logger.info(f"✅ 选择端口: {selected_port}")
            logger.info(f"✅ 处理后HY2链接: {hy2_link}")

            if details.get('verification_result') is not None:
                verification_status = "✅ 通过" if details['verification_result'] else "❌ 失败"
                logger.info(f"✅ 链接验证: {verification_status}")

            # 记录执行时间
            end_time = time.perf_counter()
            execution_time = end_time - start_time
            logger.info(f"📊 函数执行时间: {execution_time:.3f}秒")

            return hy2_link
        else:
            logger.error(f"❌ 用户 {name_arg} 添加失败")
            logger.error(f"❌ 尝试次数: {details.get('attempts', 0)}")
            logger.error(f"❌ 可用端口数: {details.get('available_ports_count', 0)}")
            if details.get('errors'):
                logger.error("❌ 错误详情:")
                for error in details['errors'][-3:]:  # 显示最后3个错误
                    logger.error(f"   - {error}")

            # 记录执行时间（失败情况）
            end_time = time.perf_counter()
            execution_time = end_time - start_time
            logger.info(f"📊 函数执行时间: {execution_time:.3f}秒")

            return None

    except Exception as e:
        logger.error(f"❌ 智能端口管理器调用失败: {e}")
        logger.error(f"智能端口管理器调用失败: {e}")

        # 记录执行时间（异常情况）
        end_time = time.perf_counter()
        execution_time = end_time - start_time
        logger.info(f"📊 函数执行时间: {execution_time:.3f}秒")

        return None

def test_smart_port_manager_v2(proxy, name_arg='test_smart_port@example.com'):
    """智能端口管理器完整功能测试 (v2版本)

    参数:
        proxy: NodeProxy对象
        name_arg: 用户名参数

    返回:
        bool: 测试是否成功
    """
    from smart_port_manager import add_user_with_smart_port, get_port_statistics, cleanup_old_port_records

    logger.info("=== 智能端口管理器完整功能测试 (v2) ===")

    try:
        # 1. 获取端口统计信息
        logger.info("\n1. 获取端口统计信息...")
        stats = get_port_statistics(hostname, proxy)
        if stats:
            logger.info(f"   - 总计跟踪端口: {stats['total_tracked']}")
            logger.info(f"   - 已使用端口: {stats['used_ports']}")
            logger.info(f"   - 可用端口数: {stats['available_in_range']}")
            logger.info(f"   - 协议分布: {stats['protocols']}")

        # 2. 测试智能端口添加用户 - 启用验证
        logger.info("\n2. 测试智能端口添加用户（启用验证）...")
        success1, hy2_link1, port1, details1 = add_user_with_smart_port(
            proxy=proxy,
            name_arg=f"{name_arg}_verified",
            hostname=hostname,
            max_retries=2,
            verify_link=True
        )

        if success1:
            logger.info(f"   ✅ 第一次添加成功，端口: {port1}")
            logger.info(f"   ✅ 验证结果: {details1.get('verification_result')}")
        else:
            logger.error(f"   ❌ 第一次添加失败，错误: {details1.get('errors', [])}")

        # 3. 测试智能端口添加用户 - 禁用验证（更快）
        logger.info("\n3. 测试智能端口添加用户（禁用验证）...")
        success2, hy2_link2, port2, details2 = add_user_with_smart_port(
            proxy=proxy,
            name_arg=f"{name_arg}_fast",
            hostname=hostname,
            max_retries=2,
            verify_link=False
        )

        if success2:
            logger.info(f"   ✅ 第二次添加成功，端口: {port2}")
            logger.info(f"   ✅ 跳过验证，快速模式")
        else:
            logger.error(f"   ❌ 第二次添加失败，错误: {details2.get('errors', [])}")

        # 4. 端口范围测试
        logger.info("\n4. 测试自定义端口范围...")
        success3, hy2_link3, port3, details3 = add_user_with_smart_port(
            proxy=proxy,
            name_arg=f"{name_arg}_range",
            hostname=hostname,
            min_port=15000,
            max_port=16000,
            max_retries=1,
            verify_link=False
        )

        if success3:
            logger.info(f"   ✅ 自定义范围添加成功，端口: {port3} (应在15000-16000范围内)")
        else:
            logger.error(f"   ❌ 自定义范围添加失败，错误: {details3.get('errors', [])}")

        # 5. 获取更新后的端口统计
        logger.info("\n5. 获取更新后的端口统计...")
        updated_stats = get_port_statistics(hostname, proxy)
        if updated_stats:
            logger.info(f"   - 更新后总计跟踪: {updated_stats['total_tracked']}")
            logger.info(f"   - 更新后已使用: {updated_stats['used_ports']}")
            logger.info(f"   - 更新后可用: {updated_stats['available_in_range']}")

        # 6. 清理测试（谨慎使用）
        logger.info("\n6. 清理旧端口记录测试（清理0天前的记录作为演示）...")
        # 注意：这里使用0天只是为了测试功能，实际使用应该设置合理的天数
        # cleaned = cleanup_old_port_records(hostname, proxy, days_old=0)
        # print(f"   - 清理了 {cleaned} 条记录")
        logger.info("   - 跳过清理操作（避免影响实际数据）")

        # 计算成功率
        successful_operations = sum([success1, success2, success3])
        total_operations = 3
        success_rate = successful_operations / total_operations * 100

        logger.info(f"\n📊 智能端口管理器测试结果:")
        logger.info(f"   - 成功操作: {successful_operations}/{total_operations}")
        logger.info(f"   - 成功率: {success_rate:.1f}%")
        logger.info(f"   - 使用端口: {[p for p in [port1, port2, port3] if p is not None]}")

        return success_rate >= 66.7  # 至少2/3成功才算通过

    except Exception as e:
        logger.error(f"❌ 智能端口管理器测试失败: {e}")
        logger.error(f"智能端口管理器测试失败: {e}")
        return False

def test_fetch_db_v2(proxy, table_names=None, db_path=None):
    """远端数据读取测试 (v2版本)

    参数:
        proxy: NodeProxy对象
        table_names: 要查询的表名列表
        db_path: 数据库文件路径

    返回:
        dict: 数据库查询结果
    """
    logger.info("=== 远端数据读取测试 (v2) ===")

    try:
        data = nmanage.fetch_db_data_direct(
            proxy=proxy,
            table_names=table_names,
            db_path=db_path
        )

        logger.info("数据库读取结果:")
        for table, rows in data.items():
            logger.info(f"  - {table}: {len(rows)} 条记录")

        return data

    except Exception as e:
        logger.error(f"❌ 数据库读取失败: {e}")
        return {}

def test_save_csv_v2(proxy, table_names, out_dir=None):
    """远端数据读取保存为CSV测试 (v2版本)

    参数:
        proxy: NodeProxy对象
        table_names: 要查询的表名列表
        out_dir: 输出目录

    返回:
        list: 写入的文件路径列表
    """
    logger.info("=== 远端数据读取保存为CSV测试 (v2) ===")

    try:
        written_files = nmanage.fetch_and_save_tables_csv(
            proxy=proxy,
            table_names=table_names,
            out_dir=out_dir
        )

        logger.info(f"CSV文件保存成功: {written_files}")
        return written_files

    except Exception as e:
        logger.error(f"❌ CSV保存失败: {e}")
        return []

def test_remote_ports_v2(proxy, timeout=10):
    """获取远端端口测试 (v2版本)

    参数:
        proxy: NodeProxy对象
        timeout: 超时时间

    返回:
        dict: 按协议分组的端口列表
    """
    logger.info("=== 获取远端端口测试 (v2) ===")

    try:
        ports_by_protocol = nmanage.get_remote_ports_by_protocol(
            proxy=proxy,
            timeout=timeout
        )

        if not ports_by_protocol:
            logger.error("❌ 未获取到端口信息或获取失败")
            return {}

        logger.info("✅ 远端端口获取成功")
        logger.info("\n按协议分组的端口列表:")

        for protocol, ports in ports_by_protocol.items():
            logger.info(f"  {protocol.upper()}: {ports}")
            logger.info(f"    端口数量: {len(ports)}")

        # 显示统计信息
        total_ports = sum(len(ports) for ports in ports_by_protocol.values())
        logger.info(f"\n总计监听端口数: {total_ports}")

        return ports_by_protocol

    except Exception as e:
        logger.error(f"❌ 远端端口获取失败: {e}")
        return {}

def test_find_database_v2(proxy, possible_paths=None, timeout=10):
    """查找数据库文件测试 (v2版本)

    参数:
        proxy: NodeProxy对象
        possible_paths: 可能的数据库路径列表
        timeout: 超时时间

    返回:
        str: 找到的数据库文件路径，失败返回None
    """
    logger.info("=== 查找数据库文件测试 (v2) ===")

    try:
        db_path = nmanage.find_database_file(
            proxy=proxy,
            possible_paths=possible_paths,
            timeout=timeout
        )

        if db_path:
            logger.info(f"✅ 找到数据库文件: {db_path}")
        else:
            logger.error("❌ 未找到数据库文件")

        return db_path

    except Exception as e:
        logger.error(f"❌ 查找数据库文件失败: {e}")
        return None

def test_comprehensive_v2(hostname=hostname):
    """综合测试 - 使用单一SSH连接完成所有操作 (v2版本)

    参数:
        hostname: 远程服务器地址

    返回:
        bool: 测试是否成功
    """
    logger.info("=== 综合测试 (v2版本) - 单一SSH连接 ===")

    try:
        # 创建单一SSH连接
        logger.info("1. 创建SSH连接...")
        with nmanage.NodeProxy(hostname, 22, 'root', {key_file}) as proxy:
            logger.info("✅ SSH连接已建立")

            # 2. 查找数据库
            logger.info("\n2. 查找数据库文件...")
            db_path = test_find_database_v2(proxy)

            # 3. 获取端口信息
            logger.info("\n3. 获取端口信息...")
            ports = test_remote_ports_v2(proxy)

            # 4. 添加测试用户
            logger.info("\n4. 添加测试用户...")
            test_name = f"test_user_{int(time.time())}"

            hy2_link = test_add_user_v2(
                proxy=proxy,
                name_arg=test_name,
                up_mbps=50,
                down_mbps=50,
                verify_link=False  # 禁用验证以加快测试速度
            )

            # 5. 读取数据库数据
            logger.info("\n5. 读取数据库数据...")
            if db_path:
                data = test_fetch_db_v2(proxy, table_names=['users'], db_path=db_path)
            else:
                data = test_fetch_db_v2(proxy, table_names=['users'])

            # 6. 保存CSV文件
            logger.info("\n6. 保存CSV文件...")
            csv_files = test_save_csv_v2(proxy, table_names=['users'])

            # 7. 验证链接（如果成功创建）
            if hy2_link:
                logger.info("\n7. 验证HY2链接...")
                verification_result = verify_hy2_link_local(hy2_link)
                if verification_result:
                    logger.info("✅ 链接验证成功")
                else:
                    logger.error("❌ 链接验证失败")

            logger.info("\n✅ 综合测试完成")
            logger.info("=" * 50)
            logger.info("测试结果总结:")
            logger.info(f"  - 数据库路径: {db_path or '未找到'}")
            logger.info(f"  - 端口信息: {len(ports)} 种协议")
            logger.info(f"  - 用户创建: {'成功' if hy2_link else '失败'}")
            logger.info(f"  - 数据读取: {len(data)} 个表")
            logger.info(f"  - CSV文件: {len(csv_files)} 个文件")

            return True

    except Exception as e:
        logger.error(f"❌ 综合测试失败: {e}")
        return False

def verify_hy2_link_local(link):
    """本地验证hysteria2链接

    参数:
        link: hysteria2链接

    返回:
        bool: 验证是否成功
    """
    if not link or not link.startswith('hysteria2://'):
        return False

    # 获取脚本路径
    script_path = os.path.join(os.path.dirname(__file__), 'link_verificate.sh')

    if not os.path.exists(script_path):
        logger.warning(f"⚠️ 验证脚本不存在: {script_path}")
        return False

    try:
        # 执行验证脚本
        result = subprocess.run(
            ['bash', script_path, '-z', link],
            capture_output=True,
            text=True,
            timeout=60
        )

        return result.returncode == 0

    except Exception as e:
        logger.error(f"❌ 链接验证异常: {e}")
        return False

def test_performance_comparison(hostname=hostname, iterations=3):
    """性能对比测试 - v1 vs v2版本

    参数:
        hostname: 远程服务器地址
        iterations: 测试迭代次数
    """
    logger.info("=== 性能对比测试 (v1 vs v2) ===")

    import time
    from v1 import node_manage as nmanage_v1

    v1_times = []
    v2_times = []

    for i in range(iterations):
        logger.info(f"\n--- 第 {i+1} 次迭代 ---")

        # 测试v1版本（多次连接）
        logger.info("测试v1版本（多次SSH连接）...")
        v1_start = time.time()
        try:
            # v1版本会创建多个连接
            nmanage_v1.get_remote_ports_by_protocol(hostname, 22, 'root', f'/root/.ssh/{key_file}')
            nmanage_v1.find_database_file(hostname, 'root', f'/root/.ssh/{key_file}')
            nmanage_v1.fetch_db_data_direct(hostname, 'root', f'/root/.ssh/{key_file}', table_names=['users'])
        except Exception as e:
            logger.error(f"v1版本测试失败: {e}")
        v1_end = time.time()
        v1_times.append(v1_end - v1_start)

        # 测试v2版本（单次连接）
        logger.info("测试v2版本（单次SSH连接）...")
        v2_start = time.time()
        try:
            with nmanage.NodeProxy(hostname, 22, 'root', f'/root/.ssh/{key_file}') as proxy:
                nmanage.get_remote_ports_by_protocol(proxy)
                nmanage.find_database_file(proxy)
                nmanage.fetch_db_data_direct(proxy, table_names=['users'])
        except Exception as e:
            logger.error(f"v2版本测试失败: {e}")
        v2_end = time.time()
        v2_times.append(v2_end - v2_start)

        logger.info(f"v1耗时: {v1_times[-1]:.2f}s, v2耗时: {v2_times[-1]:.2f}s")

    # 计算平均时间和改进率
    avg_v1 = sum(v1_times) / len(v1_times)
    avg_v2 = sum(v2_times) / len(v2_times)
    improvement = ((avg_v1 - avg_v2) / avg_v1) * 100

    logger.info("\n" + "=" * 50)
    logger.info("性能测试结果:")
    logger.info(f"v1平均耗时: {avg_v1:.2f}s")
    logger.info(f"v2平均耗时: {avg_v2:.2f}s")
    logger.info(f"性能提升: {improvement:.1f}%")
    logger.info(f"速度提升: {avg_v1/avg_v2:.1f}x")

def main():
    """主函数，提供交互式菜单"""
    tests = {
        '1': ('添加用户测试 (v2)', lambda: test_with_connection(test_add_user_v2)),
        '2': ('远端数据读取测试 (v2)', lambda: test_with_connection(test_fetch_db_v2)),
        '3': ('远端数据保存CSV测试 (v2)', lambda: test_with_connection(lambda p: test_save_csv_v2(p, ['users']))),
        '4': ('获取远端端口测试 (v2)', lambda: test_with_connection(test_remote_ports_v2)),
        '5': ('查找数据库文件测试 (v2)', lambda: test_with_connection(test_find_database_v2)),
        '6': ('综合测试 (v2版本)', test_comprehensive_v2),
        '7': ('性能对比测试 (v1 vs v2)', test_performance_comparison),
    }

    def test_with_connection(test_func):
        """使用临时连接执行测试函数"""
        with nmanage.NodeProxy(hostname, 22, 'root', f'/root/.ssh/{key_file}') as proxy:
            return test_func(proxy)

    while True:
        logger.info("\n请选择要执行的测试:")
        for key, (desc, _) in tests.items():
            logger.info(f"{key}. {desc}")
        logger.info("q. 退出")

        choice = input("\n请输入选择 (1-7, q): ").strip().lower()

        if choice == 'q':
            logger.info("退出程序")
            break
        elif choice in tests:
            _, test_func = tests[choice]
            try:
                test_func()
            except Exception as e:
                logger.error(f"测试执行失败: {e}")
        else:
            logger.error("无效选择，请重新输入")

if __name__ == '__main__':
    main()