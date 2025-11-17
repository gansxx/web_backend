# 心跳检测器 (Heartbeat Detector)

## 概述

心跳检测器是一个独立的服务，用于检测一组IP地址的一组特定端口是否正常能被访问。它能够区分是整个IP不可访问，还是单独的端口不可访问。

## 功能特性

- ✅ **异步并发检测**：同时检测多个IP和端口，提高检测效率
- ✅ **故障分类**：精确区分IP级别故障和端口级别故障
  - **在线 (online)**：所有端口都可达
  - **离线 (offline)**：所有端口都不可达
  - **部分在线 (partial)**：部分端口可达
- ✅ **灵活配置**：支持配置文件和环境变量两种配置方式
- ✅ **详细日志**：使用loguru记录详细的检测过程和结果
- ✅ **REST API**：提供HTTP API接口查询状态和手动触发检测
- ✅ **定期检测**：支持自动定期检测，可配置检测间隔
- ✅ **响应时间统计**：记录每个端口的响应时间

## 架构设计

```
┌─────────────────────────────────────────────────────────┐
│                  Heartbeat Detector                      │
├─────────────────────────────────────────────────────────┤
│  配置层 (Configuration Layer)                            │
│  ├─ 配置文件 (JSON)                                      │
│  ├─ 环境变量                                             │
│  └─ 默认配置                                             │
├─────────────────────────────────────────────────────────┤
│  检测层 (Detection Layer)                                │
│  ├─ 端口检测 (Port Check)                               │
│  ├─ 主机检测 (Host Check)                               │
│  └─ 批量检测 (Batch Check)                              │
├─────────────────────────────────────────────────────────┤
│  API层 (API Layer)                                       │
│  ├─ GET  /health         - 健康检查                      │
│  ├─ POST /check          - 手动触发检测                  │
│  ├─ GET  /status         - 获取所有主机状态              │
│  ├─ GET  /status/{ip}    - 获取特定主机详细状态          │
│  └─ GET  /config         - 获取当前配置                  │
└─────────────────────────────────────────────────────────┘
```

## 快速开始

### 1. 使用默认配置运行

```bash
# 直接运行，使用默认配置
uv run python center_management/heartbeat_detector.py
```

服务将在 `http://0.0.0.0:8003` 启动，默认监控：
- `127.0.0.1` 的端口 22, 80, 443
- `8.8.8.8` 的端口 53

### 2. 使用配置文件运行

创建配置文件 `heartbeat_config.json`：

```json
{
  "targets": [
    {
      "ip": "192.168.1.1",
      "ports": [22, 80, 443]
    },
    {
      "ip": "10.0.0.1",
      "ports": [3306, 6379, 27017]
    }
  ],
  "timeout": 3.0,
  "check_interval": 60,
  "max_workers": 50,
  "enable_auto_check": true
}
```

运行服务：

```bash
uv run python center_management/heartbeat_detector.py
```

### 3. 使用环境变量配置

```bash
export HEARTBEAT_TARGETS='[{"ip": "192.168.1.1", "ports": [22, 80]}, {"ip": "10.0.0.1", "ports": [3306]}]'
export HEARTBEAT_TIMEOUT=5.0
export HEARTBEAT_INTERVAL=30
export HEARTBEAT_MAX_WORKERS=100
export HEARTBEAT_AUTO_CHECK=true

uv run python center_management/heartbeat_detector.py
```

## Docker 部署

### 方式一：使用辅助脚本（推荐）

```bash
# 启动服务
./scripts/run_heartbeat_docker.sh start

# 查看日志
./scripts/run_heartbeat_docker.sh logs

# 查看状态
./scripts/run_heartbeat_docker.sh status

# 停止服务
./scripts/run_heartbeat_docker.sh stop

# 重启服务
./scripts/run_heartbeat_docker.sh restart

# 重新构建镜像
./scripts/run_heartbeat_docker.sh build

# 清理所有容器和镜像
./scripts/run_heartbeat_docker.sh clean
```

### 方式二：使用 Docker Compose

```bash
# 启动服务
docker compose -f docker-compose.heartbeat.yml up -d

# 查看日志
docker compose -f docker-compose.heartbeat.yml logs -f heartbeat

# 停止服务
docker compose -f docker-compose.heartbeat.yml down

# 重新构建并启动
docker compose -f docker-compose.heartbeat.yml up -d --build
```

### 方式三：手动构建和运行

```bash
# 构建镜像
docker build -f Dockerfile.heartbeat -t heartbeat-detector:latest .

# 运行容器
docker run -d \
  --name heartbeat-detector \
  -p 8003:8003 \
  -v $(pwd)/heartbeat_config.json:/app/heartbeat_config.json:ro \
  -v heartbeat_logs:/app/logs \
  heartbeat-detector:latest

# 查看日志
docker logs -f heartbeat-detector

# 停止容器
docker stop heartbeat-detector

# 删除容器
docker rm heartbeat-detector
```

### Docker 配置说明

#### 环境变量

在 `docker-compose.heartbeat.yml` 中可以配置以下环境变量：

```yaml
environment:
  # 使用配置文件（推荐）
  HEARTBEAT_CONFIG_FILE: /app/heartbeat_config.json

  # 或者直接通过环境变量配置
  HEARTBEAT_TARGETS: '[{"ip": "192.168.1.1", "ports": [22, 80, 443]}]'
  HEARTBEAT_TIMEOUT: 3.0
  HEARTBEAT_INTERVAL: 60
  HEARTBEAT_MAX_WORKERS: 50
  HEARTBEAT_AUTO_CHECK: true
```

#### 自定义配置文件

1. 创建自定义配置文件 `my_heartbeat_config.json`
2. 修改 `docker-compose.heartbeat.yml`：

```yaml
volumes:
  - ./my_heartbeat_config.json:/app/heartbeat_config.json:ro
```

#### 日志持久化

日志自动保存到 Docker volume `heartbeat_logs`，可以通过以下方式查看：

```bash
# 查看日志文件
docker exec heartbeat-detector ls -lh /app/logs/

# 读取日志
docker exec heartbeat-detector tail -f /app/logs/heartbeat_*.log
```

#### 与其他服务集成

与 Supabase 和其他服务一起运行：

```bash
docker compose -f docker-compose-supabase.yml -f docker-compose.heartbeat.yml up -d
```

#### 资源限制

默认配置限制：
- CPU: 最多 0.5 核心
- 内存: 最多 512MB

可在 `docker-compose.heartbeat.yml` 中调整：

```yaml
deploy:
  resources:
    limits:
      cpus: '1.0'
      memory: 1024M
```

## 配置说明

### 配置参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `targets` | List[Dict] | 见下方 | 监控目标列表 |
| `timeout` | float | 3.0 | 连接超时时间（秒） |
| `check_interval` | int | 60 | 定期检测间隔（秒） |
| `max_workers` | int | 50 | 最大并发检测数 |
| `enable_auto_check` | bool | true | 是否启用自动定期检测 |

### 监控目标格式

```json
{
  "ip": "IP地址",
  "ports": [端口1, 端口2, ...]
}
```

### 配置优先级

1. **配置文件** (`heartbeat_config.json`)
2. **环境变量** (`HEARTBEAT_*`)
3. **默认配置**

## API 使用

### 1. 健康检查

```bash
curl http://localhost:8003/health
```

响应：
```json
{
  "status": "ok",
  "service": "heartbeat-detector"
}
```

### 2. 手动触发检测

```bash
curl -X POST http://localhost:8003/check
```

响应：
```json
{
  "success": true,
  "message": "检测完成，共检测 2 个主机",
  "results": {
    "192.168.1.1": {
      "ip": "192.168.1.1",
      "status": "online",
      "total_ports": 3,
      "reachable_ports": 3,
      "unreachable_ports": 0,
      "checked_at": "2025-11-17T08:00:00.123456",
      "ports": [...]
    }
  }
}
```

### 3. 获取所有主机状态

```bash
curl http://localhost:8003/status
```

响应：
```json
{
  "192.168.1.1": {
    "ip": "192.168.1.1",
    "status": "online",
    "total_ports": 3,
    "reachable_ports": 3,
    "unreachable_ports": 0,
    "checked_at": "2025-11-17T08:00:00.123456"
  },
  "10.0.0.1": {
    "ip": "10.0.0.1",
    "status": "partial",
    "total_ports": 3,
    "reachable_ports": 2,
    "unreachable_ports": 1,
    "checked_at": "2025-11-17T08:00:00.123456"
  }
}
```

### 4. 获取特定主机详细状态

```bash
curl http://localhost:8003/status/192.168.1.1
```

响应：
```json
{
  "ip": "192.168.1.1",
  "status": "online",
  "ports": [
    {
      "port": 22,
      "status": "reachable",
      "response_time": 0.023,
      "error": null,
      "checked_at": "2025-11-17T08:00:00.123456"
    },
    {
      "port": 80,
      "status": "reachable",
      "response_time": 0.015,
      "error": null,
      "checked_at": "2025-11-17T08:00:00.123456"
    }
  ],
  "total_ports": 2,
  "reachable_ports": 2,
  "unreachable_ports": 0,
  "checked_at": "2025-11-17T08:00:00.123456"
}
```

### 5. 获取当前配置

```bash
curl http://localhost:8003/config
```

## 故障诊断

### 主机状态判定逻辑

1. **在线 (online)**：所有配置的端口都可达
2. **离线 (offline)**：所有配置的端口都不可达
   - 可能原因：
     - 主机网络故障
     - 主机关机
     - 防火墙阻止所有端口
     - 路由问题
3. **部分在线 (partial)**：部分端口可达，部分端口不可达
   - 可能原因：
     - 特定服务未启动
     - 端口级别的防火墙规则
     - 服务监听配置问题

### 端口状态

- **reachable**：端口可达，服务正常监听
- **unreachable**：端口不可达，连接被拒绝
- **timeout**：连接超时，可能是网络延迟或防火墙DROP规则

## 测试

### 运行测试脚本

```bash
# 运行完整测试套件
uv run python center_management/test_heartbeat.py
```

测试包含：
1. 单个端口检测测试
2. 单个主机检测测试
3. 多个主机检测测试
4. 配置文件加载测试
5. API调用模拟测试

### 示例测试输出

```
============================================================
心跳检测器 - 测试套件
============================================================

============================================================
测试1: 单个端口检测
============================================================
✓ 127.0.0.1:22 可达 (响应时间: 0.002s)
✗ 127.0.0.1:9999 不可达

============================================================
测试2: 单个主机检测
============================================================
主机: 127.0.0.1
状态: partial
总端口数: 5
可达端口: 3
不可达端口: 2
```

## 日志

### 日志级别

- **DEBUG**：详细的端口连接信息
- **INFO**：检测开始、完成、统计信息
- **WARNING**：端口不可达、超时
- **ERROR**：主机离线、检测失败

### 日志文件

日志文件保存在 `logs/heartbeat_{time}.log`，配置：
- 自动轮转：文件大小达到 500MB
- 保留时间：10 天

### 日志示例

```
2025-11-17 08:00:00 | INFO     | 🚀 开始检测 3 个目标主机...
2025-11-17 08:00:00 | DEBUG    | ✓ 192.168.1.1:22 可达 (响应时间: 0.023s)
2025-11-17 08:00:00 | WARNING  | ✗ 192.168.1.1:9999 不可达 - Connection refused
2025-11-17 08:00:00 | INFO     | ✓ 192.168.1.1 在线 - 所有 3 个端口可达
2025-11-17 08:00:00 | INFO     | ✅ 检测完成 - 耗时: 0.15s, 在线: 2, 离线: 0, 部分: 1
```

## 集成到现有系统

### 作为独立服务

```bash
# 在后台运行
nohup uv run python center_management/heartbeat_detector.py > heartbeat.log 2>&1 &
```

### 在代码中使用

```python
import asyncio
from center_management.heartbeat_detector import (
    HeartbeatDetector,
    HeartbeatConfig
)

async def main():
    # 创建配置
    config = HeartbeatConfig(
        targets=[
            {"ip": "192.168.1.1", "ports": [22, 80, 443]},
        ],
        timeout=3.0,
        enable_auto_check=False
    )

    # 创建检测器
    detector = HeartbeatDetector(config)

    # 执行检测
    results = await detector.check_all()

    # 处理结果
    for ip, result in results.items():
        print(f"{ip}: {result.status.value}")
        if result.status == "partial":
            for port_result in result.ports:
                if port_result.status != "reachable":
                    print(f"  端口 {port_result.port} 不可达")

asyncio.run(main())
```

### 与Orchestrationer集成

可以在 `center_management/orchestrationer.py` 中集成心跳检测器，实现自动化监控和告警。

## 性能考虑

### 并发控制

- 使用 `max_workers` 参数控制最大并发数
- 默认值 50 适合大多数场景
- 监控大量主机时可适当增加

### 超时设置

- `timeout` 参数控制单个端口的连接超时
- 建议值：2-5 秒
- 过小可能导致误报，过大会影响检测速度

### 检测间隔

- `check_interval` 参数控制定期检测的间隔
- 建议值：30-300 秒
- 根据实际需求和系统负载调整

## 故障排查

### 所有端口都显示超时

1. 检查网络连接
2. 检查防火墙规则
3. 增加 `timeout` 值

### 误报离线

1. 检查目标服务是否真的在运行
2. 检查监听地址（0.0.0.0 vs 127.0.0.1）
3. 检查防火墙规则

### 检测速度慢

1. 减少 `timeout` 值
2. 增加 `max_workers` 值
3. 减少监控目标数量

## 常见使用场景

### 1. VPS节点监控

监控多个VPS节点的SSH、HTTP、HTTPS端口：

```json
{
  "targets": [
    {"ip": "vps1.example.com", "ports": [22, 80, 443]},
    {"ip": "vps2.example.com", "ports": [22, 80, 443]},
    {"ip": "vps3.example.com", "ports": [22, 80, 443]}
  ],
  "timeout": 5.0,
  "check_interval": 60
}
```

### 2. 数据库服务监控

监控数据库服务的端口可用性：

```json
{
  "targets": [
    {"ip": "db-master", "ports": [3306, 6379, 27017]},
    {"ip": "db-slave", "ports": [3306, 6379, 27017]}
  ],
  "timeout": 3.0,
  "check_interval": 30
}
```

### 3. 微服务健康检查

监控微服务集群的各个服务端口：

```json
{
  "targets": [
    {"ip": "api-service", "ports": [8001, 8002, 8003]},
    {"ip": "cache-service", "ports": [6379]},
    {"ip": "queue-service", "ports": [5672, 15672]}
  ],
  "timeout": 2.0,
  "check_interval": 20
}
```

## 技术细节

### 检测原理

使用Python的 `asyncio.open_connection()` 建立TCP连接来检测端口可达性：

1. 尝试建立TCP连接
2. 连接成功 → 端口可达
3. 连接拒绝 → 端口不可达
4. 连接超时 → 超时

### 异步架构

- 使用 `asyncio` 实现异步并发检测
- 使用 `Semaphore` 控制并发数
- 使用 `gather` 并发执行多个检测任务

### 数据模型

- `PortCheckResult`：单个端口检测结果
- `HostCheckResult`：单个主机检测结果（包含多个端口）
- `HeartbeatConfig`：检测器配置

## 未来扩展

- [ ] 支持ICMP Ping检测
- [ ] 支持HTTP/HTTPS健康检查（检查响应码）
- [ ] 支持检测结果持久化到数据库
- [ ] 支持告警通知（邮件、钉钉、企业微信）
- [ ] 支持Web控制台
- [ ] 支持检测历史记录和趋势分析

## 相关文档

- [项目主文档](../CLAUDE.md)
- [Orchestrationer服务](../center_management/orchestrationer.py)
- [节点管理系统](../center_management/node_manage.py)

## 许可证

本项目的一部分，遵循项目整体许可证。
