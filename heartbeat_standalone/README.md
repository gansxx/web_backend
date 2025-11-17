# Heartbeat Detector - 独立版

一个完全独立的心跳检测器服务，用于监控IP地址和端口的可用性。

## 特性

- ✅ **完全独立**: 不依赖任何外部项目，可单独部署
- ✅ **异步并发**: 高效检测多个IP和端口
- ✅ **故障分类**: 精确区分IP级别故障和端口级别故障
- ✅ **REST API**: 提供完整的HTTP API接口
- ✅ **Docker支持**: 开箱即用的容器化部署
- ✅ **灵活配置**: 支持配置文件和环境变量
- ✅ **最小依赖**: 仅依赖 FastAPI, Uvicorn, Pydantic, Loguru

## 快速开始

### 方式一：Docker部署（推荐）

```bash
# 启动服务
docker compose up -d

# 查看日志
docker compose logs -f

# 查看状态
curl http://localhost:8003/health

# 停止服务
docker compose down
```

### 方式二：直接运行

```bash
# 安装依赖
pip install -r <(uv pip compile pyproject.toml)
# 或使用 uv
uv sync

# 运行服务
python heartbeat_detector.py
# 或使用 uv
uv run python heartbeat_detector.py
```

## 配置

### 使用配置文件（推荐）

编辑 `config.json`：

```json
{
  "targets": [
    {
      "ip": "192.168.1.1",
      "ports": [22, 80, 443]
    },
    {
      "ip": "10.0.0.1",
      "ports": [3306, 6379]
    }
  ],
  "timeout": 3.0,
  "check_interval": 60,
  "max_workers": 50,
  "enable_auto_check": true
}
```

### 使用环境变量

```bash
export HEARTBEAT_TARGETS='[{"ip": "192.168.1.1", "ports": [22, 80, 443]}]'
export HEARTBEAT_TIMEOUT=3.0
export HEARTBEAT_INTERVAL=60
export HEARTBEAT_MAX_WORKERS=50
export HEARTBEAT_AUTO_CHECK=true
```

### Docker环境变量

在 `docker-compose.yml` 中设置：

```yaml
environment:
  HEARTBEAT_TARGETS: '[{"ip": "192.168.1.1", "ports": [22, 80, 443]}]'
  HEARTBEAT_TIMEOUT: 3.0
  HEARTBEAT_INTERVAL: 60
```

## API 使用

### 健康检查

```bash
curl http://localhost:8003/health
```

### 手动触发检测

```bash
curl -X POST http://localhost:8003/check
```

### 获取所有主机状态

```bash
curl http://localhost:8003/status
```

响应示例：

```json
{
  "192.168.1.1": {
    "ip": "192.168.1.1",
    "status": "online",
    "total_ports": 3,
    "reachable_ports": 3,
    "unreachable_ports": 0,
    "checked_at": "2025-11-17T10:00:00.123456"
  }
}
```

### 获取特定主机详细状态

```bash
curl http://localhost:8003/status/192.168.1.1
```

响应示例：

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
      "checked_at": "2025-11-17T10:00:00.123456"
    }
  ],
  "total_ports": 3,
  "reachable_ports": 3,
  "unreachable_ports": 0,
  "checked_at": "2025-11-17T10:00:00.123456"
}
```

### 获取当前配置

```bash
curl http://localhost:8003/config
```

## 状态说明

### 主机状态

- **online**: 所有端口都可达 - 主机完全正常
- **offline**: 所有端口都不可达 - 主机离线或网络故障
- **partial**: 部分端口可达 - 部分服务正常，部分服务异常

### 端口状态

- **reachable**: 端口可达 - 服务正常
- **unreachable**: 端口不可达 - 连接被拒绝
- **timeout**: 连接超时 - 可能是网络延迟或防火墙阻止

## Docker详细说明

### 构建镜像

```bash
docker build -t heartbeat-detector:latest .
```

### 运行容器

```bash
docker run -d \
  --name heartbeat-detector \
  -p 8003:8003 \
  -v $(pwd)/config.json:/app/config.json:ro \
  -v heartbeat_logs:/app/logs \
  heartbeat-detector:latest
```

### 查看日志

```bash
# 容器日志
docker logs -f heartbeat-detector

# 应用日志
docker exec heartbeat-detector tail -f /app/logs/heartbeat_*.log
```

### 自定义配置

1. 修改 `config.json`
2. 重启容器：`docker compose restart`

### 资源限制

默认限制（可在 `docker-compose.yml` 修改）：
- CPU: 0.5 核心
- 内存: 256MB

## 目录结构

```
heartbeat_standalone/
├── heartbeat_detector.py   # 主程序
├── config.json              # 配置文件
├── pyproject.toml           # Python依赖
├── Dockerfile               # Docker镜像定义
├── docker-compose.yml       # Docker Compose配置
├── .dockerignore            # Docker构建排除
└── README.md                # 本文档
```

## 故障排查

### 所有端口都显示超时

1. 检查网络连接
2. 检查防火墙规则
3. 增加 `timeout` 值

### 端口误报不可达

1. 检查目标服务是否真的在运行
2. 检查监听地址（0.0.0.0 vs 127.0.0.1）
3. 检查防火墙规则

### 检测速度慢

1. 减少 `timeout` 值
2. 增加 `max_workers` 值
3. 减少监控目标数量

## 性能优化

### 并发控制

- 默认 `max_workers=50` 适合大多数场景
- 监控大量主机时可增加到 100-200
- 资源受限时可降低到 10-20

### 超时设置

- 默认 `timeout=3.0` 秒
- 本地网络可降低到 1-2 秒
- 跨网络检测可增加到 5-10 秒

### 检测间隔

- 默认 `check_interval=60` 秒
- 关键服务可降低到 10-30 秒
- 资源受限时可增加到 120-300 秒

## 依赖项

- **Python**: >= 3.12
- **FastAPI**: >= 0.115.6 - Web框架
- **Uvicorn**: >= 0.34.0 - ASGI服务器
- **Pydantic**: >= 2.10.6 - 数据验证
- **Loguru**: >= 0.7.3 - 日志记录

## 许可证

本项目为独立部署版本，完全开源。

## 技术支持

遇到问题？
1. 检查日志文件
2. 使用 `/health` 端点检查服务状态
3. 查看 Docker 容器日志

## 更新记录

### v1.0.0 (2025-11-17)
- 初始独立版本发布
- 支持异步并发检测
- 提供完整 REST API
- Docker 容器化支持
