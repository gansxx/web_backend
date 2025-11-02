# Orchestrationer 服务

## 概述

orchestrationer.py 是一个独立的 FastAPI 服务，用于接收和处理各种通知和状态更新。该服务现在包含 IP 白名单安全机制。

## 功能特性

### 🔧 核心功能
- **健康检查** (`/health`) - 服务状态检查
- **通知接收** (`/notify`) - 接收任意 JSON 通知数据
- **带宽警告处理** (`/warning_bandwidth`) - 处理带宽警告，执行 SSH 连接和数据抓取
- **状态恢复处理** (`/status_normal`) - 处理节点状态恢复通知

### 🛡️ 安全特性
- **IP 白名单访问控制** - 只允许指定 IP 和网段访问
- **访问日志记录** - 详细记录所有访问尝试（允许和拒绝）
- **代理支持** - 支持 `X-Forwarded-For` 和 `X-Real-IP` 头部

## 独立性确认

✅ **完全独立于 main.py**
- 使用独立的 FastAPI 应用实例
- 运行在不同端口 (8002 vs 8001)
- 没有代码依赖关系
- 可以独立启动和停止

## 启动方式

### 方法1: 直接运行
```bash
conda activate proxy_manage
cd /root/self_code/web_backend/center_management
python orchestrationer.py
```

### 方法2: 使用 uvicorn
```bash
conda activate proxy_manage
cd /root/self_code/web_backend/center_management
uvicorn orchestrationer:app --host 0.0.0.0 --port 8002 --reload
```

## IP 白名单配置

### 默认配置
服务默认允许以下 IP 和网段访问：
- `127.0.0.1` - 本地回环地址
- `::1` - IPv6 本地回环地址
- `192.168.0.0/16` - 私有网络 A 类
- `10.0.0.0/8` - 私有网络 B 类
- `172.16.0.0/12` - 私有网络 C 类

### 自定义配置
使用环境变量 `ALLOWED_IPS` 来自定义允许的 IP 地址：

```bash
# 设置允许的 IP（逗号分隔）
export ALLOWED_IPS="127.0.0.1,192.168.1.0/24,203.0.113.0/24"

# 或者在启动时设置
ALLOWED_IPS="127.0.0.1,10.0.0.1" python orchestrationer.py
```

支持格式：
- 单个 IP: `192.168.1.1`
- CIDR 网段: `192.168.1.0/24`
- 混合配置: `127.0.0.1,192.168.0.0/16,203.0.113.42`

## 安全日志

### 访问允许日志
```
INFO - 访问允许 - IP: 127.0.0.1, Path: /health, Method: GET
```

### 访问拒绝日志
```
WARNING - 访问被拒绝 - IP: 8.8.8.8, Path: /notify, Method: POST
```

## API 端点

### GET /health
健康检查端点
```json
{
  "msg": "listener is ok"
}
```

### POST /notify
接收通知数据
```bash
curl -X POST http://localhost:8002/notify \\
  -H "Content-Type: application/json" \\
  -d '{"message": "test notification"}'
```

### GET /warning_bandwidth
带宽警告处理（需要包含 IP 数据的 JSON）
```bash
curl -X GET http://localhost:8002/warning_bandwidth \\
  -H "Content-Type: application/json" \\
  -d '{"ip": "192.168.1.100"}'
```

### GET /status_normal
状态恢复处理
```bash
curl -X GET http://localhost:8002/status_normal \\
  -H "Content-Type: application/json" \\
  -d '{"ip": "192.168.1.100"}'
```

## 测试

运行测试脚本验证功能：
```bash
conda activate proxy_manage
cd /root/self_code/web_backend/center_management
python test_ip_whitelist.py
```

## 故障排除

### 常见问题

1. **连接被拒绝**
   - 检查服务是否正在运行
   - 确认端口 8002 可访问
   - 检查防火墙设置

2. **IP 访问被拒绝**
   - 检查 `ALLOWED_IPS` 环境变量配置
   - 确认客户端 IP 在白名单中
   - 检查代理/负载均衡器配置

3. **依赖模块缺失**
   - 确保使用正确的 conda 环境: `proxy_manage`
   - 检查所需依赖是否已安装

### 调试命令
```bash
# 检查服务状态
curl http://localhost:8002/health

# 查看日志
tail -f /path/to/log/file

# 测试 IP 白名单
python test_ip_whitelist.py
```

## 监控建议

1. **访问日志监控** - 定期检查访问被拒绝的日志
2. **健康检查** - 定期调用 `/health` 端点
3. **性能监控** - 监控响应时间和资源使用
4. **安全审计** - 定期审查 IP 白名单配置