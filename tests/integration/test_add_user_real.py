#!/usr/bin/env python3
"""
实际调用后端API执行添加用户的完整集成测试

此脚本测试完整的用户添加流程：
1. 连接到远程服务器（网关）
2. 调用 test_add_user_v2 添加用户
3. 生成 hysteria2 订阅链接
4. 可选：验证链接有效性

使用方法:
    uv run python tests/integration/test_add_user_real.py

    或使用自定义参数:
    uv run python tests/integration/test_add_user_real.py --email test@example.com --url jiasu.example.com
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from center_management.backend_api_v2 import test_add_user_v2
from center_management import node_manage as nmanage
from dotenv import load_dotenv
import os


def test_add_user_real(
    email: str = None,
    url: str = None,
    alias: str = None,
    verify_link: bool = False,
    max_retries: int = 2,
    up_mbps: int = 50,
    down_mbps: int = 50,
):
    """
    实际调用后端API执行添加用户操作

    参数:
        email: 用户邮箱（用作用户名）
        url: 订阅链接中使用的域名
        alias: 订阅链接的别名
        verify_link: 是否验证链接有效性
        max_retries: 最大重试次数
        up_mbps: 上传带宽限制(Mbps)
        down_mbps: 下载带宽限制(Mbps)

    返回:
        tuple: (success: bool, subscription_url: str, error_msg: str)
    """

    print("=" * 70)
    print("开始测试用户添加功能")
    print("=" * 70)

    # 加载环境变量
    load_dotenv()

    # 获取配置
    gateway_ip = os.getenv('gateway_ip')
    gateway_user = os.getenv('gateway_user', 'admin')
    key_file = 'id_ed25519'

    # 生成默认参数
    if not email:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        email = f'test_user_{timestamp}@example.com'

    if not alias:
        alias = 'test_subscription'

    print(f"\n📋 测试配置:")
    print(f"   网关地址: {gateway_ip}")
    print(f"   网关用户: {gateway_user}")
    print(f"   SSH密钥: {key_file}")
    print(f"   用户邮箱: {email}")
    print(f"   订阅URL: {url or '使用IP地址'}")
    print(f"   订阅别名: {alias}")
    print(f"   上传带宽: {up_mbps} Mbps")
    print(f"   下载带宽: {down_mbps} Mbps")
    print(f"   验证链接: {'是' if verify_link else '否'}")
    print(f"   最大重试: {max_retries} 次")

    if not gateway_ip:
        error_msg = "❌ 错误: gateway_ip 环境变量未设置"
        print(f"\n{error_msg}")
        return False, None, error_msg

    print(f"\n🔌 连接到服务器...")

    try:
        # 创建SSH连接
        proxy = nmanage.NodeProxy(gateway_ip, 22, gateway_user, key_file)
        print(f"✅ SSH连接建立成功")

        print(f"\n👤 开始添加用户...")
        print(f"   正在调用 test_add_user_v2()...")

        # 调用添加用户函数
        subscription_url = test_add_user_v2(
            proxy,
            name_arg=email,
            url=url,
            alias=alias,
            verify_link=verify_link,
            max_retries=max_retries,
            up_mbps=up_mbps,
            down_mbps=down_mbps,
        )

        if subscription_url:
            print("\n" + "=" * 70)
            print("✅ 用户添加成功！")
            print("=" * 70)
            print(f"\n📱 订阅链接:")
            print(f"   {subscription_url}")
            print(f"\n💾 可以将此链接保存到数据库或返回给用户")
            print("=" * 70)

            return True, subscription_url, None
        else:
            error_msg = "❌ 用户添加失败: test_add_user_v2 返回 None"
            print(f"\n{error_msg}")
            print("   可能的原因:")
            print("   - 端口分配失败")
            print("   - DNS解析失败（如果指定了URL）")
            print("   - 远程脚本执行失败")
            print("   - 网络连接问题")

            return False, None, error_msg

    except Exception as e:
        error_msg = f"❌ 测试过程中发生异常: {str(e)}"
        print(f"\n{error_msg}")
        import traceback
        print("\n详细错误信息:")
        traceback.print_exc()

        return False, None, error_msg

    finally:
        print("\n🔌 关闭SSH连接...")


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description="实际调用后端API执行添加用户的集成测试",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用默认参数（自动生成邮箱）
  uv run python tests/integration/test_add_user_real.py

  # 指定用户邮箱
  uv run python tests/integration/test_add_user_real.py --email test@example.com

  # 指定订阅URL和别名
  uv run python tests/integration/test_add_user_real.py --email test@example.com --url jiasu.example.com --alias free_plan

  # 启用链接验证
  uv run python tests/integration/test_add_user_real.py --email test@example.com --verify

  # 自定义带宽限制
  uv run python tests/integration/test_add_user_real.py --email test@example.com --up 100 --down 100
        """
    )

    parser.add_argument(
        '--email',
        type=str,
        help='用户邮箱（用作用户名）。不指定则自动生成'
    )

    parser.add_argument(
        '--url',
        type=str,
        help='订阅链接中使用的域名（如 jiasu.example.com）。不指定则使用IP地址'
    )

    parser.add_argument(
        '--alias',
        type=str,
        default='test_subscription',
        help='订阅链接的别名（默认: test_subscription）'
    )

    parser.add_argument(
        '--verify',
        action='store_true',
        help='验证生成的订阅链接有效性（需要额外时间）'
    )

    parser.add_argument(
        '--retries',
        type=int,
        default=2,
        help='最大重试次数（默认: 2）'
    )

    parser.add_argument(
        '--up',
        type=int,
        default=50,
        help='上传带宽限制 Mbps（默认: 50）'
    )

    parser.add_argument(
        '--down',
        type=int,
        default=50,
        help='下载带宽限制 Mbps（默认: 50）'
    )

    args = parser.parse_args()

    # 执行测试
    success, subscription_url, error_msg = test_add_user_real(
        email=args.email,
        url=args.url,
        alias=args.alias,
        verify_link=args.verify,
        max_retries=args.retries,
        up_mbps=args.up,
        down_mbps=args.down,
    )

    # 退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
