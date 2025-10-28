#!/usr/bin/env python3
"""
启动脚本 - 运行找回密码API服务
支持开发模式（uvicorn）和生产模式（gunicorn）
"""

import os
import sys
import uvicorn
from test_main import app

def print_service_info():
    
    print("开始启动服务")


def run_development():
    """开发模式：使用uvicorn，支持热重载"""
    print("🔧 开发模式 - 使用 Uvicorn（热重载已启用）")
    print_service_info()

    uvicorn.run(
        "test_main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )


def run_production():
    """生产模式：使用gunicorn，多进程处理"""
    print("🏭 生产模式 - 使用 Gunicorn（多进程）")
    print_service_info()

    # 使用gunicorn启动
    from gunicorn.app.base import BaseApplication

    class StandaloneApplication(BaseApplication):
        def __init__(self, app, options=None):
            self.options = options or {}
            self.application = app
            super().__init__()

        def load_config(self):
            # 从gunicorn_config.py加载配置（如果存在）
            config_file = "gunicorn_config.py"
            config = {}

            if os.path.exists(config_file):
                # 手动执行配置文件并提取配置
                import importlib.util
                spec = importlib.util.spec_from_file_location("gunicorn_config", config_file)
                config_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(config_module)

                # 提取所有配置变量
                for key in dir(config_module):
                    if not key.startswith('_') and key in self.cfg.settings:
                        config[key] = getattr(config_module, key)

            # 命令行选项覆盖配置文件
            for key, value in self.options.items():
                if value is not None:
                    config[key] = value

            # 应用配置
            for key, value in config.items():
                if key in self.cfg.settings:
                    self.cfg.set(key.lower(), value)

        def load(self):
            return self.application

    options = {
        'bind': os.getenv('BIND_ADDRESS', '0.0.0.0:8001'),
        'workers': int(os.getenv('GUNICORN_WORKERS', 4)),
        'worker_class': 'uvicorn.workers.UvicornWorker',
    }

    StandaloneApplication(app, options).run()


if __name__ == "__main__":
    # 检查环境变量决定运行模式
    # ENVIRONMENT=production 或 USE_GUNICORN=true 启用生产模式
    environment = os.getenv("ENVIRONMENT", "development").lower()
    use_gunicorn = os.getenv("USE_GUNICORN", "false").lower() in ("true", "1", "yes")

    # 支持命令行参数
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
        if mode in ("prod", "production"):
            use_gunicorn = True
        elif mode in ("dev", "development"):
            use_gunicorn = False

    if environment == "production" or use_gunicorn:
        run_production()
    else:
        run_development()
