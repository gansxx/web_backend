#!/usr/bin/env python3
"""
启动脚本 - 运行找回密码API服务
"""

import uvicorn
from test_main import app

if __name__ == "__main__":
    print("🚀 启动找回密码API服务...")
    print("📧 支持功能：")
    print("   - 发送密码重置邮件 (/recall)")
    print("   - 验证重置验证码 (/recall/verify)")
    print("   - 重置密码 (/recall/reset)")
    print("   - 用户注册 (/signup)")
    print("   - 用户登录 (/login)")
    print("   - 退出登录 (/logout)")
    print("   - 用户信息 (/me)")
    print()
    
    uvicorn.run(
        "test_main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )
