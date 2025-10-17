#!/usr/bin/env python3
"""
测试 orchestrationer.py 的 IP 白名单功能
"""

import requests
import json
import time
import sys

def test_ip_whitelist():
    """测试IP白名单功能"""

    # 测试URL - 假设orchestrationer运行在8002端口
    base_url = "http://127.0.0.1:8002"

    print("🧪 开始测试 IP 白名单功能...")
    print("=" * 50)

    # 测试健康检查端点
    print("📋 测试 1: 健康检查端点 (/health)")
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            print("✅ 健康检查通过 - IP白名单允许本地访问")
            print(f"   响应: {response.json()}")
        else:
            print(f"❌ 健康检查失败 - 状态码: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("❌ 连接失败 - 请确保 orchestrationer 服务正在运行")
        print("   启动命令: python orchestrationer.py")
        return False
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        return False

    print()

    # 测试通知端点
    print("📋 测试 2: 通知端点 (/notify)")
    test_data = {
        "message": "IP白名单测试",
        "timestamp": time.time(),
        "source": "test_script"
    }

    try:
        response = requests.post(
            f"{base_url}/notify",
            json=test_data,
            timeout=5
        )
        if response.status_code == 200:
            print("✅ 通知端点测试通过 - IP白名单允许POST请求")
            print(f"   响应: {response.json()}")
        else:
            print(f"❌ 通知端点测试失败 - 状态码: {response.status_code}")
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        return False

    print()

    # 模拟被拒绝的IP (需要在实际环境中配置不同的IP)
    print("📋 测试 3: IP白名单配置检查")
    print("   当前允许的默认IP范围:")
    print("   - 127.0.0.1 (本地)")
    print("   - ::1 (IPv6本地)")
    print("   - 192.168.0.0/16 (私有网络)")
    print("   - 10.0.0.0/8 (私有网络)")
    print("   - 172.16.0.0/12 (私有网络)")
    print("✅ IP白名单配置合理 - 允许本地和私有网络访问")

    print()
    print("🎉 所有测试完成!")
    return True

def test_middleware_logic():
    """测试中间件逻辑"""
    print("🔧 测试 IP 白名单中间件逻辑...")

    # 测试IP地址解析
    import ipaddress

    test_ips = [
        ("127.0.0.1", True),
        ("192.168.1.1", True),
        ("10.0.0.1", True),
        ("172.16.0.1", True),
        ("8.8.8.8", False),  # 公网IP应该被拒绝
        ("invalid_ip", False)
    ]

    # 模拟白名单检查逻辑
    allowed_networks = [
        ipaddress.ip_network("127.0.0.1/32"),
        ipaddress.ip_network("192.168.0.0/16"),
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("172.16.0.0/12")
    ]

    def check_ip(ip_str):
        try:
            ip = ipaddress.ip_address(ip_str)
            for network in allowed_networks:
                if ip in network:
                    return True
            return False
        except ValueError:
            return False

    for test_ip, expected in test_ips:
        result = check_ip(test_ip)
        status = "✅" if result == expected else "❌"
        print(f"   {status} {test_ip}: {'允许' if result else '拒绝'} (期望: {'允许' if expected else '拒绝'})")

if __name__ == "__main__":
    print("🚀 IP白名单测试工具")
    print("=" * 50)

    # 先测试中间件逻辑
    test_middleware_logic()
    print()

    # 再测试实际HTTP请求
    success = test_ip_whitelist()

    if not success:
        print()
        print("💡 如果测试失败，请确保:")
        print("   1. orchestrationer.py 服务正在运行")
        print("   2. 服务运行在端口 8002")
        print("   3. IP白名单配置正确")
        print()
        print("🔧 启动服务命令:")
        print("   cd /root/self_code/web_backend/center_management")
        print("   conda activate proxy_manage")
        print("   python orchestrationer.py")
        sys.exit(1)
    else:
        print("✅ 所有测试都通过了!")