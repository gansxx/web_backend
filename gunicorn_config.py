"""
Gunicorn配置文件 - 用于生产环境部署
"""

import multiprocessing
import os

# 服务器套接字
bind = "0.0.0.0:8001"
backlog = 2048

# Worker进程
workers = int(os.getenv("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
max_requests = 1000  # 重启worker之前处理的最大请求数，防止内存泄漏
max_requests_jitter = 50  # 随机化重启，避免所有worker同时重启
timeout = 300  # Worker超时时间（秒） - 增加到5分钟以支持大文件上传 (原 120秒)
keepalive = 5  # Keep-Alive连接的等待时间

# 日志
accesslog = "-"  # 输出到stdout
errorlog = "-"   # 输出到stderr
loglevel = os.getenv("LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# 进程命名
proc_name = "web_backend_api"

# 守护进程（生产环境通常由systemd或supervisor管理，设为False）
daemon = False

# Preload应用（减少内存占用，但重启时会重新加载）
preload_app = True

# 优雅重启超时
graceful_timeout = 30

# Worker临时文件目录
worker_tmp_dir = "/dev/shm"  # 使用内存文件系统，提升性能

# 启动时的回调
def on_starting(server):
    """服务器启动时执行"""
    print("🚀 Gunicorn服务器正在启动...")
    print(f"📦 Workers: {workers}")
    print(f"🌐 绑定地址: {bind}")
    print(f"📝 日志级别: {loglevel}")


def on_reload(server):
    """配置重载时执行"""
    print("🔄 Gunicorn配置已重新加载")


def when_ready(server):
    """服务器准备就绪时执行"""
    print("✅ Gunicorn服务器已就绪，开始接受请求")


def on_exit(server):
    """服务器关闭时执行"""
    print("🛑 Gunicorn服务器已关闭")
