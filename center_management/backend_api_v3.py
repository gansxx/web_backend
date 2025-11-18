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
        if alias:
            # 移除旧别名（如果存在）
            if '#' in modified_link:
                modified_link = modified_link.split('#')[0]
            # 添加新别名
            modified_link = f"{modified_link}#{alias}"
            logger.debug(f"链接别名已替换为: {alias}")

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


def test_add_user_v3(proxy, name_arg='test_user_3@example.com', url=None, alias=None, **kwargs):
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
        alias: 替换链接末尾别名的参数（可选）
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
            logger.debug(f"HY2 link: {hy2_link}")

            if exit_status == 0 and hy2_link:
                # 提取端口号（用于日志）
                selected_port = result.get('port') if isinstance(result, dict) else None
                if selected_port:
                    logger.info(f"✅ 远程分配端口: {selected_port}")
                else:
                    logger.warning("⚠️ 无法从结果中提取端口号")

                # 链接验证
                verification_success = True
                if verify_link:
                    logger.info("开始验证链接...")
                    verification_success = verify_hy2_link_simple(hy2_link)

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
                processed_link = _modify_hysteria2_link(hy2_link, url, alias)

                # Phase 4: 成功返回
                logger.info(f"{'='*50}")
                logger.info(f"✅ 用户 {name_arg} 添加成功")
                logger.info(f"✅ 分配端口: {selected_port}")
                logger.info(f"✅ 原始链接: {hy2_link}")
                logger.info(f"✅ 处理后链接: {processed_link}")

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
