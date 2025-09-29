from fastapi import FastAPI, Request, HTTPException, Response
from starlette.middleware.base import BaseHTTPMiddleware
import json
import os
import ipaddress
import uvicorn
from typing import List, Union
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
from .dns import update_record_ip
from .node_manage import fetch_and_save_tables_csv, NodeProxy


def get_host() -> str:
    """获取默认主机地址

    Returns:
        str: 默认主机IP地址
    """
    return "202.182.106.233"



# IP 白名单配置
def get_allowed_ips() -> List[Union[ipaddress.IPv4Address, ipaddress.IPv4Network, ipaddress.IPv6Address, ipaddress.IPv6Network]]:
    """获取允许的IP地址列表，支持单个IP和CIDR网段"""
    allowed_ips_env = os.getenv('ALLOWED_IPS', '127.0.0.1,::1,192.168.0.0/16,10.0.0.0/8,172.16.0.0/12')
    allowed_ips = []

    for ip_str in allowed_ips_env.split(','):
        ip_str = ip_str.strip()
        if not ip_str:
            continue
        try:
            # 尝试解析为网络（支持CIDR）
            if '/' in ip_str:
                network = ipaddress.ip_network(ip_str, strict=False)
                allowed_ips.append(network)
            else:
                # 解析为单个IP地址
                ip = ipaddress.ip_address(ip_str)
                allowed_ips.append(ip)
        except ValueError as e:
            logger.warning(f"无效的IP地址或网段: {ip_str}, 错误: {e}")

    logger.info(f"已加载 {len(allowed_ips)} 个允许的IP/网段: {[str(ip) for ip in allowed_ips]}")
    return allowed_ips

class IPWhitelistMiddleware(BaseHTTPMiddleware):
    """IP白名单中间件"""

    def __init__(self, app, allowed_ips: List[Union[ipaddress.IPv4Address, ipaddress.IPv4Network, ipaddress.IPv6Address, ipaddress.IPv6Network]]):
        super().__init__(app)
        self.allowed_ips = allowed_ips

    async def dispatch(self, request: Request, call_next):
        # 获取客户端IP地址
        client_ip = self._get_client_ip(request)

        # 检查IP是否在白名单中
        if not self._is_ip_allowed(client_ip):
            logger.warning(f"访问被拒绝 - IP: {client_ip}, Path: {request.url.path}, Method: {request.method}")
            return Response(
                content=json.dumps({"error": "Access denied", "detail": "IP not in whitelist"}),
                status_code=403,
                media_type="application/json"
            )

        # IP通过验证，记录日志并继续处理
        logger.info(f"访问允许 - IP: {client_ip}, Path: {request.url.path}, Method: {request.method}")
        response = await call_next(request)
        return response

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端真实IP地址，支持代理和负载均衡"""
        # 检查 X-Forwarded-For 头（代理/负载均衡场景）
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            # X-Forwarded-For 可能包含多个IP，取第一个（真实客户端IP）
            client_ip = forwarded_for.split(',')[0].strip()
            logger.debug(f"使用 X-Forwarded-For 头获取客户端IP: {client_ip}")
            return client_ip

        # 检查 X-Real-IP 头
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            logger.debug(f"使用 X-Real-IP 头获取客户端IP: {real_ip}")
            return real_ip

        # 使用直连IP
        client_ip = request.client.host if request.client else "unknown"
        logger.debug(f"使用直连IP: {client_ip}")
        return client_ip

    def _is_ip_allowed(self, client_ip_str: str) -> bool:
        """检查IP是否在白名单中"""
        if client_ip_str == "unknown":
            logger.warning("无法获取客户端IP地址")
            return False

        try:
            client_ip = ipaddress.ip_address(client_ip_str)
        except ValueError:
            logger.warning(f"无效的客户端IP地址: {client_ip_str}")
            return False

        # 检查是否匹配白名单中的任何IP或网段
        for allowed in self.allowed_ips:
            if isinstance(allowed, (ipaddress.IPv4Network, ipaddress.IPv6Network)):
                # 网段匹配
                if client_ip in allowed:
                    return True
            else:
                # 单个IP匹配
                if client_ip == allowed:
                    return True

        return False

# 创建应用实例
app = FastAPI(title="FastAPI-POST-Receiver", version="1.0")

# 加载允许的IP列表并添加中间件
allowed_ips = get_allowed_ips()
app.add_middleware(IPWhitelistMiddleware, allowed_ips=allowed_ips)

# 健康检查
@app.get("/health")
def health_check():
    return {"msg": "listener is ok"}

# 监听 POST /notify  接收任意 JSON
@app.post("/notify")
async def notify(request: Request):
    try:
        data = await request.json()      # 获取原始 JSON
        print("收到 JSON:", data)        # 控制台打印
        with open("/root/notify.log", "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")
        return {"code": 0} # 回显给客户端
    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/warning_bandwidth")
async def warning_bandwidth(request: Request):
    try:
        data = await request.json()      # 获取原始 JSON
        print("收到 JSON:", data)        # 控制台打印
        ip=data.get("ip")
        # TODO: 这里可以添加对 ip 的处理逻辑，比如更新 DNS 记录
        # TODO: 还应该添加获得所有现在所有未在线用户的域名列表，然后遍历对所有域名进行修改IP

        # 使用NodeProxy共享SSH连接
        with NodeProxy(ip, 22, 'root', 'id_ed25519') as proxy:
            fetch_and_save_tables_csv(proxy=proxy, table_names=['user'])


    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail=str(e))
    return {"msg": "warning bandwidth is ok"}

@app.get("/status_normal")
async def status_normal(request: Request):
    try:
        data = await request.json()      # 获取原始 JSON
        print("收到 JSON:", data)        # 控制台打印
        ip=data.get("ip")
        #TODO: 在本地数据库中添加一条记录，表示该节点恢复正常
        return {"code": 0} # 回显给客户端
    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    print("🚀 启动 Orchestrationer 服务...")
    print("📊 支持功能：")
    print("   - 健康检查 (/health)")
    print("   - 通知接收 (/notify)")
    print("   - 带宽警告处理 (/warning_bandwidth)")
    print("   - 状态恢复处理 (/status_normal)")
    print("🛡️  安全特性：")
    print("   - IP白名单访问控制")
    print("   - 访问日志记录")
    print(f"   - 默认允许的网段: 127.0.0.1, ::1, 192.168.0.0/16, 10.0.0.0/8, 172.16.0.0/12")
    print(f"   - 自定义配置: 设置环境变量 ALLOWED_IPS")
    print()

    uvicorn.run(
        "orchestrationer:app",
        host="0.0.0.0",
        port=8002,
        reload=True,
        log_level="info"
    )