"""
backend_api_v3.py - 用户添加 API (v3 版本)

核心变化：
- 调用 run_add_user_v3()，由远程脚本自动分配端口
- 移除本地端口管理（CSV 文件）
- 简化重试逻辑，信任远程脚本的端口分配
- 重试间隔 5 秒
- 独立实现 _modify_hysteria2_link()（无 port 参数）
- 保留 DNS 验证和链接验证功能
"""

from center_management import node_manage as nmanage
from loguru import logger
import subprocess
import os
import re
import time
from center_management.dns import dns_status
from dotenv import load_dotenv

load_dotenv()

# 获得网关地址（在第一版中为默认单台服务器位置）
hostname = os.getenv('gateway_ip')
key_file = 'id_ed25519'
logger.info(f"默认测试服务器地址: {hostname}")
logger.info(f"本测试默认使用{key_file}私钥文件，请确保该文件存在可用，且为云端私钥")


def _modify_hysteria2_link(hy2_link, url=None, alias=None):
    """修改 Hysteria2 链接中的服务器地址和别名

    v3 版本变化：移除 selected_port 参数，因为端口已经在链接中

    参数:
        hy2_link: 原始 hysteria2 链接
        url: 新的域名（可选，替换 IP 地址）
        alias: 新的别名（可选，替换 # 后的部分）

    返回:
        str: 修改后的 hysteria2 链接
    """
    if not hy2_link:
        return hy2_link

    modified_link = hy2_link

    try:
        # 替换 IP 地址为域名
        if url:
            # 使用正则表达式匹配和替换 IP 地址部分
            # 格式: hysteria2://uuid@ip:port?params#alias
            # 匹配: @后面到:之前的部分（IP 或域名）
            ip_pattern = r'(@)([^:]+)(:\d+)'
            modified_link = re.sub(ip_pattern, rf'\1{url}\3', modified_link)
            logger.debug(f"链接 IP 已替换为: {url}")

        # 替换别名
        # 别名默认在边缘节点确认为官网地址，方便用户回源官网
        if alias:
            # 移除旧别名（如果存在）
            if '#' in modified_link:
                modified_link = modified_link.split('#')[0]
            # 添加新别名
            front_name="官网地址:go.superjiasu.top"
            modified_link = f"{modified_link}#{front_name}"
            logger.debug(f"链接别名已替换为: {front_name}")

    except Exception as e:
        logger.error(f"修改 hysteria2 链接失败: {e}")
        return hy2_link

    return modified_link


def verify_hy2_link_simple(hy2_link, timeout=60):
    """简化版 Hysteria2 链接验证

    调用 link_verificate.sh 脚本进行验证

    参数:
        hy2_link: hysteria2 链接
        timeout: 超时时间（秒），默认 60 秒

    返回:
        bool: 验证是否成功
    """
    if not hy2_link or not hy2_link.startswith('hysteria2://'):
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
        logger.debug(f"执行验证脚本: {script_path}")
        result = subprocess.run(
            ['bash', script_path, '-z', hy2_link],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=script_dir  # 设置工作目录为脚本所在目录
        )

        if result.returncode == 0:
            logger.info("✅ 链接验证成功")
            return True
        else:
            logger.warning(f"❌ 链接验证失败 (返回码: {result.returncode})")
            if result.stderr:
                logger.debug(f"验证错误输出: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        logger.error(f"链接验证超时 (>{timeout}秒)")
        return False
    except Exception as e:
        logger.error(f"链接验证异常: {e}")
        return False


def update_user(proxy, name_arg, days=30, **kwargs):
    """更新用户到期时间功能（延长订阅）

    核心功能：
    - 调用 run_update_user() 更新远程服务器上用户的到期时间
    - 简化的重试逻辑，信任远程脚本的更新操作
    - 重试间隔 5 秒

    参数:
        proxy: NodeProxy 对象
        name_arg: 用户邮箱地址
        days: 延长天数（默认: 30）
        **kwargs: 其他参数
            - max_retries: 最大重试次数（默认: 3）
            - retry_delay: 重试等待时间（秒，默认: 5）

    返回:
        dict: 更新结果字典，包含旧/新到期日期等信息，失败返回 None
    """
    # 记录函数开始时间
    start_time = time.perf_counter()

    logger.info("=== 用户到期时间更新 ===")
    logger.info(f"用户名: {name_arg}")
    logger.info(f"延长天数: {days}")

    # Phase 1: 参数配置
    default_kwargs = {
        'max_retries': 3,
        'retry_delay': 5
    }
    default_kwargs.update(kwargs)

    max_retries = default_kwargs['max_retries']
    retry_delay = default_kwargs['retry_delay']

    logger.info(f"配置参数: max_retries={max_retries}, retry_delay={retry_delay}s")

    # Phase 2: 重试循环
    for retry in range(max_retries):
        attempt = retry + 1
        logger.info(f"{'='*50}")
        logger.info(f"第 {attempt}/{max_retries} 次尝试...")

        try:
            # 调用 run_update_user
            logger.info("调用 run_update_user()...")
            exit_status, result, out, err = nmanage.run_update_user(
                proxy=proxy,
                name_arg=name_arg,
                days=days
            )

            logger.debug(f"Exit status: {exit_status}")
            logger.debug(f"Result: {result}")

            if exit_status == 0 and result and isinstance(result, dict):
                # 成功
                logger.info(f"✅ 用户到期时间更新成功")
                logger.info(f"  旧到期日期: {result.get('old_expires_date', 'N/A')}")
                logger.info(f"  新到期日期: {result.get('new_expires_date', 'N/A')}")
                logger.info(f"  延长天数: {result.get('days_extended', days)}")

                if result.get('was_banned'):
                    logger.info(f"  用户曾被禁，解禁状态: {'成功' if result.get('unban_success') else '失败'}")

                # Phase 3: 成功返回
                logger.info(f"{'='*50}")
                logger.info(f"✅ 用户 {name_arg} 到期时间更新完成")

                # 执行时间记录
                end_time = time.perf_counter()
                execution_time = end_time - start_time
                logger.info(f"📊 函数执行时间: {execution_time:.3f} 秒")
                logger.info(f"{'='*50}")

                return result

            else:
                # 更新失败
                logger.error(f"❌ 用户更新失败 (尝试 {attempt}/{max_retries})")
                logger.error(f"Exit status: {exit_status}")
                if err:
                    logger.error(f"错误信息: {err}")

                # 未达到最大重试次数，等待后继续
                if attempt < max_retries:
                    logger.info(f"⏳ 等待 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)
                    continue

        except Exception as e:
            logger.error(f"❌ 异常发生 (尝试 {attempt}/{max_retries}): {e}")
            logger.exception("详细异常信息:")

            # 未达到最大重试次数，等待后继续
            if attempt < max_retries:
                logger.info(f"⏳ 等待 {retry_delay} 秒后重试...")
                time.sleep(retry_delay)
                continue

    # Phase 4: 重试次数耗尽
    logger.error(f"{'='*50}")
    logger.error(f"❌ 用户 {name_arg} 到期时间更新失败")
    logger.error(f"❌ 已尝试 {max_retries} 次，全部失败")

    # 执行时间记录
    end_time = time.perf_counter()
    execution_time = end_time - start_time
    logger.info(f"📊 函数执行时间: {execution_time:.3f} 秒")
    logger.error(f"{'='*50}")

    return None


def test_add_user_v3(proxy, name_arg=None, url=None, alias=None, **kwargs):
    """智能用户添加功能（v3 版本）

    核心变化：
    - 调用 run_add_user_v3()，无需手动指定端口
    - 简化重试逻辑，信任远程脚本的端口分配
    - 重试间隔 5 秒
    - 移除 CSV 端口管理
    - 独立实现链接处理函数

    参数:
        proxy: NodeProxy 对象
        name_arg: 用户名参数
        url: 替换链接中 IP 地址的 URL（可选）
        alias: 用户套餐计划（必填）
        **kwargs: 其他参数
            - max_retries: 最大重试次数（默认: 3）
            - up_mbps: 上传带宽限制（默认: 50）
            - down_mbps: 下载带宽限制（默认: 50）
            - verify_link: 是否验证链接（默认: True）
            - retry_delay: 重试等待时间（秒，默认: 5）

    返回:
        str: 处理后的 hysteria2 链接（已包含 URL 和别名替换），失败返回 None
    """
    # 记录函数开始时间
    start_time = time.perf_counter()

    logger.info("=== 智能用户添加 (v3) ===")
    logger.info(f"用户名: {name_arg}")
    if url:
        logger.info(f"域名: {url}")
    if alias:
        logger.info(f"别名: {alias}")

    hostname = proxy.hostname

    # Phase 1: DNS 状态检查（如果提供了 URL）
    if url:
        logger.info(f"检查域名 DNS 状态: {url}")
        try:
            if '.' in url:
                parts = url.split('.')
                if len(parts) >= 2:
                    # 提取子域名和主域名
                    subdomain = parts[0] if len(parts) > 2 else '@'
                    domain = '.'.join(parts[-2:]) if len(parts) > 2 else url

                    logger.debug(f"域名: {domain}, 子域名: {subdomain}")

                    # DNS 验证
                    is_match, resolved_ips = dns_status(domain, subdomain, hostname)

                    if not is_match:
                        logger.error(f"❌ DNS 解析失败: {url} 未解析到目标 IP {hostname}")
                        logger.error(f"解析结果: {resolved_ips}")
                        return None
                    else:
                        logger.info(f"✅ DNS 验证通过: {url} 正确解析到 {hostname}")
        except Exception as e:
            logger.error(f"DNS 状态检查失败: {e}")
            logger.warning("跳过 DNS 检查，继续执行...")

    # Phase 2: 参数配置
    default_kwargs = {
        'max_retries': 3,
        'up_mbps': 50,
        'down_mbps': 50,
        'verify_link': True,
        'retry_delay': 5  # 重试等待时间（秒）
    }
    default_kwargs.update(kwargs)

    max_retries = default_kwargs['max_retries']
    up_mbps = default_kwargs['up_mbps']
    down_mbps = default_kwargs['down_mbps']
    verify_link = default_kwargs['verify_link']
    retry_delay = default_kwargs['retry_delay']

    logger.info(f"配置参数: max_retries={max_retries}, up_mbps={up_mbps}, down_mbps={down_mbps}, verify_link={verify_link}, retry_delay={retry_delay}s")

    # Phase 3: 重试循环
    for retry in range(max_retries):
        attempt = retry + 1
        logger.info(f"{'='*50}")
        logger.info(f"第 {attempt}/{max_retries} 次尝试...")

        try:
            # 调用 run_add_user_v3（无端口参数，由远程脚本自动分配）
            logger.info("调用 run_add_user_v3()...")
            exit_status, hy2_link, result, err = nmanage.run_add_user_v3(
                proxy=proxy,
                name_arg=name_arg,
                alias=alias,
                up_mbps=up_mbps,
                down_mbps=down_mbps
            )

            logger.debug(f"Exit status: {exit_status}")
            logger.debug(f"HY2 link(s): {hy2_link}")

            if exit_status == 0 and hy2_link:
                # 提取链接数量和端口号（用于日志）
                link_count = result.get('link_count', 1) if isinstance(result, dict) else 1
                logger.info(f"✅ 获取到 {link_count} 个链接")

                selected_port = result.get('port') if isinstance(result, dict) else None
                if selected_port:
                    logger.info(f"✅ 远程分配端口: {selected_port}")
                else:
                    logger.warning("⚠️ 无法从结果中提取端口号")

                # 链接验证（只验证第一个链接）
                verification_success = True
                if verify_link:
                    logger.info("开始验证链接（只验证第一个）...")
                    # 从聚合字符串中提取第一个链接
                    first_link = hy2_link.split('\n')[0].strip() if '\n' in hy2_link else hy2_link
                    verification_success = verify_hy2_link_simple(first_link)

                    if verification_success:
                        logger.info("✅ 链接验证通过")
                    else:
                        logger.warning(f"❌ 链接验证失败 (尝试 {attempt}/{max_retries})")

                        # 未达到最大重试次数，等待后继续
                        if attempt < max_retries:
                            logger.info(f"⏳ 等待 {retry_delay} 秒后重试...")
                            time.sleep(retry_delay)
                            continue
                        else:
                            logger.error("❌ 达到最大重试次数，验证仍失败")
                            return None

                # 链接处理（URL 和别名替换）
                # 处理所有链接
                links = hy2_link.split('\n') if '\n' in hy2_link else [hy2_link]
                processed_links = []
                for link in links:
                    link = link.strip()
                    if link:
                        processed = _modify_hysteria2_link(link, url, alias)
                        processed_links.append(processed)

                # 重新聚合为字符串
                processed_link = '\n'.join(processed_links)

                # Phase 4: 成功返回
                logger.info(f"{'='*50}")
                logger.info(f"✅ 用户 {name_arg} 添加成功")
                logger.info(f"✅ 分配端口: {selected_port}")
                logger.info(f"✅ 链接数量: {len(processed_links)}")
                logger.info(f"✅ 原始链接:\n{hy2_link}")
                logger.info(f"✅ 处理后链接:\n{processed_link}")

                # 执行时间记录
                end_time = time.perf_counter()
                execution_time = end_time - start_time
                logger.info(f"📊 函数执行时间: {execution_time:.3f} 秒")
                logger.info(f"{'='*50}")

                return processed_link

            else:
                # 添加失败
                logger.error(f"❌ 用户添加失败 (尝试 {attempt}/{max_retries})")
                logger.error(f"Exit status: {exit_status}")
                if err:
                    logger.error(f"错误信息: {err}")

                # 未达到最大重试次数，等待后继续
                if attempt < max_retries:
                    logger.info(f"⏳ 等待 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)
                    continue

        except Exception as e:
            logger.error(f"❌ 异常发生 (尝试 {attempt}/{max_retries}): {e}")
            logger.exception("详细异常信息:")

            # 未达到最大重试次数，等待后继续
            if attempt < max_retries:
                logger.info(f"⏳ 等待 {retry_delay} 秒后重试...")
                time.sleep(retry_delay)
                continue

    # Phase 5: 重试次数耗尽
    logger.error(f"{'='*50}")
    logger.error(f"❌ 用户 {name_arg} 添加失败")
    logger.error(f"❌ 已尝试 {max_retries} 次，全部失败")

    # 执行时间记录
    end_time = time.perf_counter()
    execution_time = end_time - start_time
    logger.info(f"📊 函数执行时间: {execution_time:.3f} 秒")
    logger.error(f"{'='*50}")

    return None


def add_user_subscription(proxy, name_arg=None, url=None, alias=None, **kwargs) -> tuple[str | None, str | None]:
    """创建订阅用户并返回URL和unique_name

    专门用于subscription产品生成，返回更详细的信息。
    与 test_add_user_v3() 类似，但额外返回 unique_name 用于订阅续期。

    参数:
        proxy: NodeProxy 对象
        name_arg: 用户名参数（通常是邮箱）
        url: 替换链接中 IP 地址的 URL（可选）
        alias: 用户套餐计划（必填）
        **kwargs: 其他参数
            - max_retries: 最大重试次数（默认: 3）
            - up_mbps: 上传带宽限制（默认: 50）
            - down_mbps: 下载带宽限制（默认: 50）
            - verify_link: 是否验证链接（默认: True）
            - retry_delay: 重试等待时间（秒，默认: 5）

    返回:
        tuple: (subscription_url, unique_name)
            - subscription_url: 处理后的 hysteria2 链接，失败返回 None
            - unique_name: 远端生成的唯一标识符 (email_timestamp)，失败返回 None
    """
    # 记录函数开始时间
    start_time = time.perf_counter()

    logger.info("=== 创建订阅用户 (add_user_subscription) ===")
    logger.info(f"用户名: {name_arg}")
    if url:
        logger.info(f"域名: {url}")
    if alias:
        logger.info(f"别名: {alias}")

    hostname = proxy.hostname

    # Phase 1: DNS 状态检查（如果提供了 URL）
    if url:
        logger.info(f"检查域名 DNS 状态: {url}")
        try:
            if '.' in url:
                parts = url.split('.')
                if len(parts) >= 2:
                    subdomain = parts[0] if len(parts) > 2 else '@'
                    domain = '.'.join(parts[-2:]) if len(parts) > 2 else url

                    logger.debug(f"域名: {domain}, 子域名: {subdomain}")

                    is_match, resolved_ips = dns_status(domain, subdomain, hostname)

                    if not is_match:
                        logger.error(f"❌ DNS 解析失败: {url} 未解析到目标 IP {hostname}")
                        logger.error(f"解析结果: {resolved_ips}")
                        return None, None
                    else:
                        logger.info(f"✅ DNS 验证通过: {url} 正确解析到 {hostname}")
        except Exception as e:
            logger.error(f"DNS 状态检查失败: {e}")
            logger.warning("跳过 DNS 检查，继续执行...")

    # Phase 2: 参数配置
    default_kwargs = {
        'max_retries': 3,
        'up_mbps': 50,
        'down_mbps': 50,
        'verify_link': True,
        'retry_delay': 5
    }
    default_kwargs.update(kwargs)

    max_retries = default_kwargs['max_retries']
    up_mbps = default_kwargs['up_mbps']
    down_mbps = default_kwargs['down_mbps']
    verify_link = default_kwargs['verify_link']
    retry_delay = default_kwargs['retry_delay']

    logger.info(f"配置参数: max_retries={max_retries}, up_mbps={up_mbps}, down_mbps={down_mbps}, verify_link={verify_link}, retry_delay={retry_delay}s")

    # Phase 3: 重试循环
    for retry in range(max_retries):
        attempt = retry + 1
        logger.info(f"{'='*50}")
        logger.info(f"第 {attempt}/{max_retries} 次尝试...")

        try:
            logger.info("调用 run_add_user_v3()...")
            exit_status, hy2_link, result, err = nmanage.run_add_user_v3(
                proxy=proxy,
                name_arg=name_arg,
                alias=alias,
                up_mbps=up_mbps,
                down_mbps=down_mbps
            )

            logger.debug(f"Exit status: {exit_status}")
            logger.debug(f"HY2 link(s): {hy2_link}")

            if exit_status == 0 and hy2_link:
                # 提取链接数量和端口号
                link_count = result.get('link_count', 1) if isinstance(result, dict) else 1
                logger.info(f"✅ 获取到 {link_count} 个链接")

                selected_port = result.get('port') if isinstance(result, dict) else None
                if selected_port:
                    logger.info(f"✅ 远程分配端口: {selected_port}")
                else:
                    logger.warning("⚠️ 无法从结果中提取端口号")

                # 提取 unique_name
                unique_name = result.get('unique_name') if isinstance(result, dict) else None
                if unique_name:
                    logger.info(f"✅ Unique name: {unique_name}")
                else:
                    logger.warning("⚠️ 无法从结果中提取 unique_name")

                # 链接验证
                verification_success = True
                if verify_link:
                    logger.info("开始验证链接（只验证第一个）...")
                    first_link = hy2_link.split('\n')[0].strip() if '\n' in hy2_link else hy2_link
                    verification_success = verify_hy2_link_simple(first_link)

                    if verification_success:
                        logger.info("✅ 链接验证通过")
                    else:
                        logger.warning(f"❌ 链接验证失败 (尝试 {attempt}/{max_retries})")

                        if attempt < max_retries:
                            logger.info(f"⏳ 等待 {retry_delay} 秒后重试...")
                            time.sleep(retry_delay)
                            continue
                        else:
                            logger.error("❌ 达到最大重试次数，验证仍失败")
                            return None, None

                # 链接处理（URL 和别名替换）
                links = hy2_link.split('\n') if '\n' in hy2_link else [hy2_link]
                processed_links = []
                for link in links:
                    link = link.strip()
                    if link:
                        processed = _modify_hysteria2_link(link, url, alias)
                        processed_links.append(processed)

                processed_link = '\n'.join(processed_links)

                # Phase 4: 成功返回
                logger.info(f"{'='*50}")
                logger.info(f"✅ 用户 {name_arg} 添加成功")
                logger.info(f"✅ 分配端口: {selected_port}")
                logger.info(f"✅ Unique name: {unique_name}")
                logger.info(f"✅ 链接数量: {len(processed_links)}")
                logger.info(f"✅ 处理后链接:\n{processed_link}")

                end_time = time.perf_counter()
                execution_time = end_time - start_time
                logger.info(f"📊 函数执行时间: {execution_time:.3f} 秒")
                logger.info(f"{'='*50}")

                return processed_link, unique_name

            else:
                logger.error(f"❌ 用户添加失败 (尝试 {attempt}/{max_retries})")
                logger.error(f"Exit status: {exit_status}")
                if err:
                    logger.error(f"错误信息: {err}")

                if attempt < max_retries:
                    logger.info(f"⏳ 等待 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)
                    continue

        except Exception as e:
            logger.error(f"❌ 异常发生 (尝试 {attempt}/{max_retries}): {e}")
            logger.exception("详细异常信息:")

            if attempt < max_retries:
                logger.info(f"⏳ 等待 {retry_delay} 秒后重试...")
                time.sleep(retry_delay)
                continue

    # Phase 5: 重试次数耗尽
    logger.error(f"{'='*50}")
    logger.error(f"❌ 用户 {name_arg} 添加失败 (add_user_subscription)")
    logger.error(f"❌ 已尝试 {max_retries} 次，全部失败")

    end_time = time.perf_counter()
    execution_time = end_time - start_time
    logger.info(f"📊 函数执行时间: {execution_time:.3f} 秒")
    logger.error(f"{'='*50}")

    return None, None
