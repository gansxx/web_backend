"""
心跳检测器测试脚本

测试功能：
1. 单个端口检测
2. 单个主机检测
3. 批量主机检测
4. API接口测试
"""

import asyncio
import sys
import json
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from center_management.heartbeat_detector import (
    HeartbeatDetector,
    HeartbeatConfig,
    HostStatus,
    PortStatus
)
from loguru import logger


# 配置日志
logger.remove()  # 移除默认处理器
logger.add(
    sys.stdout,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="INFO"
)


async def test_single_port():
    """测试单个端口检测"""
    print("\n" + "=" * 60)
    print("测试1: 单个端口检测")
    print("=" * 60)

    config = HeartbeatConfig(enable_auto_check=False)
    detector = HeartbeatDetector(config)

    # 测试本地SSH端口（应该可达）
    result = await detector.check_port("127.0.0.1", 22, 3.0)
    print(f"\n本地SSH端口(22): {result.status.value}")
    print(f"响应时间: {result.response_time:.3f}s")

    # 测试一个不存在的端口（应该不可达）
    result = await detector.check_port("127.0.0.1", 9999, 3.0)
    print(f"\n不存在的端口(9999): {result.status.value}")
    print(f"错误信息: {result.error}")

    # 测试外部DNS端口（应该可达）
    result = await detector.check_port("8.8.8.8", 53, 3.0)
    print(f"\nGoogle DNS(8.8.8.8:53): {result.status.value}")
    print(f"响应时间: {result.response_time:.3f}s")


async def test_single_host():
    """测试单个主机检测"""
    print("\n" + "=" * 60)
    print("测试2: 单个主机检测")
    print("=" * 60)

    config = HeartbeatConfig(enable_auto_check=False)
    detector = HeartbeatDetector(config)

    # 测试本地主机多个端口
    result = await detector.check_host("127.0.0.1", [22, 80, 8001, 8002, 9999])

    print(f"\n主机: {result.ip}")
    print(f"状态: {result.status.value}")
    print(f"总端口数: {result.total_ports}")
    print(f"可达端口: {result.reachable_ports}")
    print(f"不可达端口: {result.unreachable_ports}")
    print("\n端口详情:")
    for port_result in result.ports:
        status_icon = "✓" if port_result.status == PortStatus.REACHABLE else "✗"
        print(f"  {status_icon} 端口 {port_result.port}: {port_result.status.value} "
              f"({port_result.response_time:.3f}s)")


async def test_multiple_hosts():
    """测试多个主机检测"""
    print("\n" + "=" * 60)
    print("测试3: 多个主机检测")
    print("=" * 60)

    # 配置多个测试目标
    config = HeartbeatConfig(
        targets=[
            {"ip": "127.0.0.1", "ports": [22, 80, 8001]},
            {"ip": "8.8.8.8", "ports": [53]},
            {"ip": "1.1.1.1", "ports": [53, 80, 443]},
            {"ip": "192.168.1.254", "ports": [80, 443]},  # 可能不可达
        ],
        timeout=2.0,
        enable_auto_check=False
    )

    detector = HeartbeatDetector(config)
    results = await detector.check_all()

    print(f"\n检测了 {len(results)} 个主机:\n")

    for ip, result in results.items():
        status_icon = {
            HostStatus.ONLINE: "✓",
            HostStatus.PARTIAL: "⚠",
            HostStatus.OFFLINE: "✗",
            HostStatus.UNKNOWN: "?"
        }.get(result.status, "?")

        print(f"{status_icon} {result.ip} - {result.status.value}")
        print(f"   可达: {result.reachable_ports}/{result.total_ports} 个端口")

        if result.status == HostStatus.PARTIAL:
            print("   端口详情:")
            for port_result in result.ports:
                if port_result.status != PortStatus.REACHABLE:
                    print(f"     ✗ 端口 {port_result.port}: {port_result.status.value}")


async def test_with_config_file():
    """测试使用配置文件"""
    print("\n" + "=" * 60)
    print("测试4: 使用配置文件")
    print("=" * 60)

    # 创建测试配置文件
    test_config = {
        "targets": [
            {"ip": "127.0.0.1", "ports": [22, 8001, 8002]},
            {"ip": "8.8.8.8", "ports": [53]},
        ],
        "timeout": 2.0,
        "check_interval": 60,
        "max_workers": 10,
        "enable_auto_check": False
    }

    config_file = Path(__file__).parent.parent / "test_heartbeat_config.json"
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(test_config, f, indent=2, ensure_ascii=False)

    print(f"✓ 创建测试配置文件: {config_file}")

    # 从配置文件加载
    import os
    os.environ['HEARTBEAT_CONFIG_FILE'] = str(config_file)

    from center_management.heartbeat_detector import load_config
    config = load_config()

    print(f"✓ 从配置文件加载配置")
    print(f"   目标数: {len(config.targets)}")
    print(f"   超时: {config.timeout}s")
    print(f"   检测间隔: {config.check_interval}s")

    detector = HeartbeatDetector(config)
    results = await detector.check_all()

    print(f"\n检测结果: {len(results)} 个主机")

    # 清理测试文件
    config_file.unlink()
    print(f"✓ 清理测试配置文件")


async def test_api_simulation():
    """模拟API调用测试"""
    print("\n" + "=" * 60)
    print("测试5: 模拟API调用")
    print("=" * 60)

    config = HeartbeatConfig(
        targets=[
            {"ip": "127.0.0.1", "ports": [22, 80]},
            {"ip": "8.8.8.8", "ports": [53]},
        ],
        enable_auto_check=False
    )

    detector = HeartbeatDetector(config)

    # 模拟 POST /check
    print("\n模拟 POST /check (手动触发检测):")
    results = await detector.check_all()
    print(f"✓ 检测完成，共 {len(results)} 个主机")

    # 模拟 GET /status
    print("\n模拟 GET /status (获取最新状态):")
    latest = detector.get_latest_results()
    for ip, result in latest.items():
        print(f"  {ip}: {result.status.value} "
              f"({result.reachable_ports}/{result.total_ports} 端口可达)")

    # 模拟 GET /status/{ip}
    print("\n模拟 GET /status/127.0.0.1 (获取特定主机状态):")
    if "127.0.0.1" in latest:
        result = latest["127.0.0.1"]
        print(f"  主机: {result.ip}")
        print(f"  状态: {result.status.value}")
        print(f"  检测时间: {result.checked_at}")
        print(f"  端口详情:")
        for port_result in result.ports:
            print(f"    端口 {port_result.port}: {port_result.status.value}")


async def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("心跳检测器 - 测试套件")
    print("=" * 60)

    try:
        await test_single_port()
        await test_single_host()
        await test_multiple_hosts()
        await test_with_config_file()
        await test_api_simulation()

        print("\n" + "=" * 60)
        print("✓ 所有测试完成")
        print("=" * 60)

    except Exception as e:
        logger.error(f"测试出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
