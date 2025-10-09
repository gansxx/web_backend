# Web Backend Systemd 部署指南

## 快速部署

### 前置要求

- Linux系统（已测试：Ubuntu 20.04+, Debian 11+）
- Systemd服务管理器
- Root权限
- UV已安装（通常在 `/usr/local/bin/uv`）
- 项目位于 `~/web_backend` 或 `/root/web_backend`

### 一键部署

在云端服务器上执行以下命令：

```bash
cd ~/web_backend
git pull origin main
sudo bash deployment/deploy.sh
```

部署脚本会自动完成：
1. ✅ 创建日志目录 `/var/log/web_backend/`
2. ✅ 安装systemd服务配置
3. ✅ 安装logrotate日志轮转配置
4. ✅ 重载systemd
5. ✅ 启用服务开机自启
6. ✅ 启动服务

---

## 手动部署

如果需要手动部署，按以下步骤操作：

### 1. 创建日志目录

```bash
sudo mkdir -p /var/log/web_backend
sudo chmod 755 /var/log/web_backend
```

### 2. 安装systemd服务

```bash
sudo cp deployment/web_backend.service /etc/systemd/system/
sudo chmod 644 /etc/systemd/system/web_backend.service
```

### 3. 安装logrotate配置

```bash
sudo cp deployment/web_backend.logrotate /etc/logrotate.d/web_backend
sudo chmod 644 /etc/logrotate.d/web_backend
```

### 4. 启用并启动服务

```bash
sudo systemctl daemon-reload
sudo systemctl enable web_backend.service
sudo systemctl start web_backend.service
```

### 5. 验证部署

```bash
sudo systemctl status web_backend.service
```

---

## 服务管理命令

### 查看服务状态

```bash
systemctl status web_backend.service
```

### 启动服务

```bash
sudo systemctl start web_backend.service
```

### 停止服务

```bash
sudo systemctl stop web_backend.service
```

### 重启服务

```bash
sudo systemctl restart web_backend.service
```

### 重载配置（不中断服务）

```bash
sudo systemctl reload web_backend.service
```

### 禁用开机自启

```bash
sudo systemctl disable web_backend.service
```

---

## 日志查看

### 查看实时日志（journalctl）

```bash
# 查看实时日志
journalctl -u web_backend.service -f

# 查看最近100行日志
journalctl -u web_backend.service -n 100

# 查看今天的日志
journalctl -u web_backend.service --since today

# 查看错误级别日志
journalctl -u web_backend.service -p err
```

### 查看日志文件

```bash
# 标准输出日志
tail -f /var/log/web_backend/web_backend.log

# 错误日志
tail -f /var/log/web_backend/web_backend_error.log

# 查看所有日志文件
ls -lh /var/log/web_backend/
```

---

## 日志轮转

日志轮转由logrotate自动管理，配置如下：

- **轮转时机**：每日或超过50MB时
- **保留数量**：最近7个日志文件
- **压缩**：旧日志自动gzip压缩
- **权限**：640 root:root

### 手动测试日志轮转

```bash
# 测试logrotate配置（不实际轮转）
sudo logrotate -d /etc/logrotate.d/web_backend

# 强制执行日志轮转
sudo logrotate -f /etc/logrotate.d/web_backend
```

---

## 故障排查

### 服务无法启动

1. 查看详细错误信息：
```bash
journalctl -u web_backend.service -n 50 --no-pager
```

2. 检查配置文件语法：
```bash
systemd-analyze verify /etc/systemd/system/web_backend.service
```

3. 检查环境变量文件：
```bash
cat /root/self_code/web_backend/.env
```

### 服务频繁重启

查看重启历史：
```bash
journalctl -u web_backend.service | grep -i restart
```

检查应用程序错误：
```bash
tail -f /var/log/web_backend/web_backend_error.log
```

### 日志文件过大

检查日志文件大小：
```bash
du -sh /var/log/web_backend/*
```

手动清理旧日志：
```bash
sudo rm /var/log/web_backend/*.gz
```

---

## 配置自定义

### 修改端口

编辑 `~/web_backend/.env` 文件：
```bash
BIND_ADDRESS=0.0.0.0:9000
```

然后重启服务：
```bash
sudo systemctl restart web_backend.service
```

### 修改Worker数量

编辑 `~/web_backend/.env` 文件：
```bash
GUNICORN_WORKERS=8
```

然后重启服务：
```bash
sudo systemctl restart web_backend.service
```

### 修改日志级别

编辑 `~/web_backend/.env` 文件：
```bash
LOG_LEVEL=debug
```

然后重启服务：
```bash
sudo systemctl restart web_backend.service
```

---

## 卸载

如需卸载服务：

```bash
# 停止并禁用服务
sudo systemctl stop web_backend.service
sudo systemctl disable web_backend.service

# 删除配置文件
sudo rm /etc/systemd/system/web_backend.service
sudo rm /etc/logrotate.d/web_backend

# 重载systemd
sudo systemctl daemon-reload

# 可选：删除日志文件
sudo rm -rf /var/log/web_backend/
```

---

## 更多信息

详细文档请参考：[docs/SYSTEMD_DEPLOYMENT.md](../docs/SYSTEMD_DEPLOYMENT.md)
