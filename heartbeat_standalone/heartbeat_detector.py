"""
心跳检测器 - 独立版本
用于检测一组IP的一组特定端口是否正常能被访问

功能特性：
- 异步并发检测多个IP和端口
- 区分IP级别故障（所有端口都不可达）和端口级别故障（部分端口不可达）
- 支持通过配置文件或环境变量配置监控目标
- 提供详细的检测结果和日志
- 可作为独立服务运行
- 提供REST API查询检测状态和手动触发检测
"""

import asyncio
import time
import json
import os
from datetime import datetime
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from loguru import logger
import uvicorn


class PortStatus(str, Enum):
    """端口状态枚举"""
    REACHABLE = "reachable"  # 可达
    UNREACHABLE = "unreachable"  # 不可达
    TIMEOUT = "timeout"  # 超时


class HostStatus(str, Enum):
    """主机状态枚举"""
    ONLINE = "online"  # 在线（所有端口可达）
    PARTIAL = "partial"  # 部分在线（部分端口可达）
    OFFLINE = "offline"  # 离线（所有端口不可达）
    UNKNOWN = "unknown"  # 未知


@dataclass
class PortCheckResult:
    """单个端口检测结果"""
    port: int
    status: PortStatus
    response_time: Optional[float]  # 响应时间（秒）
    error: Optional[str] = None
    checked_at: str = None

    def __post_init__(self):
        if self.checked_at is None:
            self.checked_at = datetime.now().isoformat()


@dataclass
class HostCheckResult:
    """主机检测结果"""
    ip: str
    status: HostStatus
    ports: List[PortCheckResult]
    total_ports: int
    reachable_ports: int
    unreachable_ports: int
    checked_at: str = None

    def __post_init__(self):
        if self.checked_at is None:
            self.checked_at = datetime.now().isoformat()


class HeartbeatConfig(BaseModel):
    """心跳检测配置"""
    targets: List[Dict[str, Any]] = Field(
        default=[
            {"ip": "127.0.0.1", "ports": [22, 80, 443]},
            {"ip": "8.8.8.8", "ports": [53]},
        ],
        description="监控目标列表，每个目标包含ip和ports"
    )
    timeout: float = Field(default=3.0, description="连接超时时间（秒）")
    check_interval: int = Field(default=60, description="检测间隔（秒）")
    max_workers: int = Field(default=50, description="最大并发数")
    enable_auto_check: bool = Field(default=True, description="是否启用自动定期检测")


class HeartbeatDetector:
    """心跳检测器核心类"""

    def __init__(self, config: HeartbeatConfig):
        self.config = config
        self.latest_results: Dict[str, HostCheckResult] = {}
        self.check_task: Optional[asyncio.Task] = None
        self._running = False

    async def check_port(self, ip: str, port: int, timeout: float) -> PortCheckResult:
        """
        检测单个端口的可达性

        Args:
            ip: 目标IP地址
            port: 目标端口
            timeout: 超时时间（秒）

        Returns:
            PortCheckResult: 端口检测结果
        """
        start_time = time.time()

        try:
            # 创建异步socket连接
            future = asyncio.open_connection(ip, port)
            reader, writer = await asyncio.wait_for(future, timeout=timeout)

            # 连接成功，关闭连接
            writer.close()
            await writer.wait_closed()

            response_time = time.time() - start_time

            logger.debug(f"✓ {ip}:{port} 可达 (响应时间: {response_time:.3f}s)")
            return PortCheckResult(
                port=port,
                status=PortStatus.REACHABLE,
                response_time=response_time
            )

        except asyncio.TimeoutError:
            response_time = time.time() - start_time
            logger.warning(f"⏱ {ip}:{port} 超时 (耗时: {response_time:.3f}s)")
            return PortCheckResult(
                port=port,
                status=PortStatus.TIMEOUT,
                response_time=response_time,
                error="Connection timeout"
            )

        except Exception as e:
            response_time = time.time() - start_time
            logger.warning(f"✗ {ip}:{port} 不可达 - {str(e)} (耗时: {response_time:.3f}s)")
            return PortCheckResult(
                port=port,
                status=PortStatus.UNREACHABLE,
                response_time=response_time,
                error=str(e)
            )

    async def check_host(self, ip: str, ports: List[int]) -> HostCheckResult:
        """
        检测单个主机的所有端口

        Args:
            ip: 目标IP地址
            ports: 要检测的端口列表

        Returns:
            HostCheckResult: 主机检测结果
        """
        logger.info(f"🔍 开始检测主机 {ip} 的 {len(ports)} 个端口...")

        # 并发检测所有端口
        tasks = [
            self.check_port(ip, port, self.config.timeout)
            for port in ports
        ]
        port_results = await asyncio.gather(*tasks)

        # 统计结果
        reachable_count = sum(
            1 for r in port_results
            if r.status == PortStatus.REACHABLE
        )
        unreachable_count = len(port_results) - reachable_count

        # 确定主机状态
        if reachable_count == len(port_results):
            host_status = HostStatus.ONLINE
            logger.info(f"✓ {ip} 在线 - 所有 {len(ports)} 个端口可达")
        elif reachable_count == 0:
            host_status = HostStatus.OFFLINE
            logger.error(f"✗ {ip} 离线 - 所有 {len(ports)} 个端口不可达")
        else:
            host_status = HostStatus.PARTIAL
            logger.warning(
                f"⚠ {ip} 部分在线 - {reachable_count}/{len(ports)} 个端口可达"
            )

        return HostCheckResult(
            ip=ip,
            status=host_status,
            ports=port_results,
            total_ports=len(port_results),
            reachable_ports=reachable_count,
            unreachable_ports=unreachable_count
        )

    async def check_all(self) -> Dict[str, HostCheckResult]:
        """
        检测所有配置的目标主机

        Returns:
            Dict[str, HostCheckResult]: 所有主机的检测结果，key为IP地址
        """
        logger.info(f"🚀 开始检测 {len(self.config.targets)} 个目标主机...")
        start_time = time.time()

        # 并发检测所有主机（使用信号量控制并发数）
        semaphore = asyncio.Semaphore(self.config.max_workers)

        async def check_with_semaphore(target):
            async with semaphore:
                return await self.check_host(target['ip'], target['ports'])

        tasks = [
            check_with_semaphore(target)
            for target in self.config.targets
        ]
        results = await asyncio.gather(*tasks)

        # 转换为字典
        results_dict = {result.ip: result for result in results}
        self.latest_results = results_dict

        elapsed_time = time.time() - start_time

        # 统计总体情况
        online_count = sum(1 for r in results if r.status == HostStatus.ONLINE)
        offline_count = sum(1 for r in results if r.status == HostStatus.OFFLINE)
        partial_count = sum(1 for r in results if r.status == HostStatus.PARTIAL)

        logger.info(
            f"✅ 检测完成 - 耗时: {elapsed_time:.2f}s, "
            f"在线: {online_count}, 离线: {offline_count}, 部分: {partial_count}"
        )

        return results_dict

    async def run_periodic_check(self):
        """定期执行检测任务"""
        logger.info(f"⏰ 启动定期检测 - 间隔: {self.config.check_interval}秒")
        self._running = True

        while self._running:
            try:
                await self.check_all()
            except Exception as e:
                logger.error(f"定期检测出错: {e}")

            # 等待下一次检测
            await asyncio.sleep(self.config.check_interval)

    async def start(self):
        """启动检测器"""
        if self.config.enable_auto_check and not self.check_task:
            self.check_task = asyncio.create_task(self.run_periodic_check())
            logger.info("✓ 心跳检测器已启动")

    async def stop(self):
        """停止检测器"""
        self._running = False
        if self.check_task:
            self.check_task.cancel()
            try:
                await self.check_task
            except asyncio.CancelledError:
                pass
            self.check_task = None
            logger.info("✓ 心跳检测器已停止")

    def get_latest_results(self) -> Dict[str, HostCheckResult]:
        """获取最新的检测结果"""
        return self.latest_results


# ==================== FastAPI 服务 ====================

app = FastAPI(
    title="Heartbeat Detector Service",
    description="心跳检测服务 - 监控IP和端口的可达性",
    version="1.0.0"
)

# 全局检测器实例
detector: Optional[HeartbeatDetector] = None


def load_config() -> HeartbeatConfig:
    """
    加载配置
    优先级：配置文件 > 环境变量 > 默认配置
    """
    config_file = os.getenv('HEARTBEAT_CONFIG_FILE', 'config.json')

    # 尝试从配置文件加载
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            logger.info(f"✓ 从配置文件加载配置: {config_file}")
            return HeartbeatConfig(**config_data)
        except Exception as e:
            logger.warning(f"⚠ 加载配置文件失败: {e}，使用默认配置")

    # 尝试从环境变量加载
    targets_env = os.getenv('HEARTBEAT_TARGETS')
    if targets_env:
        try:
            targets = json.loads(targets_env)
            config_data = {
                'targets': targets,
                'timeout': float(os.getenv('HEARTBEAT_TIMEOUT', '3.0')),
                'check_interval': int(os.getenv('HEARTBEAT_INTERVAL', '60')),
                'max_workers': int(os.getenv('HEARTBEAT_MAX_WORKERS', '50')),
                'enable_auto_check': os.getenv('HEARTBEAT_AUTO_CHECK', 'true').lower() == 'true'
            }
            logger.info("✓ 从环境变量加载配置")
            return HeartbeatConfig(**config_data)
        except Exception as e:
            logger.warning(f"⚠ 从环境变量加载配置失败: {e}，使用默认配置")

    # 使用默认配置
    logger.info("✓ 使用默认配置")
    return HeartbeatConfig()


class CheckResponse(BaseModel):
    """检测响应模型"""
    success: bool
    message: str
    results: Dict[str, Dict]


class HostStatusResponse(BaseModel):
    """主机状态响应模型"""
    ip: str
    status: str
    total_ports: int
    reachable_ports: int
    unreachable_ports: int
    checked_at: str


@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    global detector
    config = load_config()
    detector = HeartbeatDetector(config)
    await detector.start()
    logger.info("🚀 心跳检测服务已启动")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    global detector
    if detector:
        await detector.stop()
    logger.info("👋 心跳检测服务已关闭")


@app.get("/health")
def health_check():
    """健康检查"""
    return {"status": "ok", "service": "heartbeat-detector"}


@app.post("/check", response_model=CheckResponse)
async def trigger_check():
    """手动触发一次检测"""
    if not detector:
        raise HTTPException(status_code=500, detail="检测器未初始化")

    try:
        results = await detector.check_all()
        results_dict = {
            ip: asdict(result) for ip, result in results.items()
        }
        return CheckResponse(
            success=True,
            message=f"检测完成，共检测 {len(results)} 个主机",
            results=results_dict
        )
    except Exception as e:
        logger.error(f"检测失败: {e}")
        raise HTTPException(status_code=500, detail=f"检测失败: {str(e)}")


@app.get("/status", response_model=Dict[str, HostStatusResponse])
async def get_status():
    """获取最新的检测状态"""
    if not detector:
        raise HTTPException(status_code=500, detail="检测器未初始化")

    results = detector.get_latest_results()

    if not results:
        return {}

    return {
        ip: HostStatusResponse(
            ip=result.ip,
            status=result.status.value,
            total_ports=result.total_ports,
            reachable_ports=result.reachable_ports,
            unreachable_ports=result.unreachable_ports,
            checked_at=result.checked_at
        )
        for ip, result in results.items()
    }


@app.get("/status/{ip}")
async def get_host_status(ip: str):
    """获取特定主机的详细状态"""
    if not detector:
        raise HTTPException(status_code=500, detail="检测器未初始化")

    results = detector.get_latest_results()

    if ip not in results:
        raise HTTPException(status_code=404, detail=f"未找到主机 {ip} 的检测结果")

    return asdict(results[ip])


@app.get("/config")
async def get_config():
    """获取当前配置"""
    if not detector:
        raise HTTPException(status_code=500, detail="检测器未初始化")

    return detector.config.dict()


if __name__ == "__main__":
    # 配置日志
    logger.add(
        "logs/heartbeat_{time}.log",
        rotation="500 MB",
        retention="10 days",
        level="INFO"
    )

    print("=" * 60)
    print("🚀 心跳检测器服务")
    print("=" * 60)
    print()
    print("📋 功能特性:")
    print("   ✓ 异步并发检测多个IP和端口")
    print("   ✓ 区分IP级别和端口级别的故障")
    print("   ✓ 定期自动检测")
    print("   ✓ REST API查询和手动触发")
    print()
    print("🔧 配置方式:")
    print("   1. 配置文件: config.json")
    print("   2. 环境变量: HEARTBEAT_TARGETS, HEARTBEAT_TIMEOUT等")
    print("   3. 默认配置: 127.0.0.1:22,80,443 和 8.8.8.8:53")
    print()
    print("📡 API端点:")
    print("   GET  /health          - 健康检查")
    print("   POST /check           - 手动触发检测")
    print("   GET  /status          - 获取所有主机状态")
    print("   GET  /status/{ip}     - 获取特定主机详细状态")
    print("   GET  /config          - 获取当前配置")
    print()
    print("=" * 60)
    print()

    uvicorn.run(
        "heartbeat_detector:app",
        host="0.0.0.0",
        port=8003,
        reload=False,
        log_level="info"
    )
