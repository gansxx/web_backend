#!/usr/bin/env python3
"""
调试找回密码功能的脚本
"""

import requests
import json
import time
import os

# API基础URL
BASE_URL = "http://localhost:8001"

def debug_recall_flow():
    """调试完整的找回密码流程"""
    
    print("🔍 开始调试找回密码功能...")
    print("=" * 60)
    
    # 测试邮箱
    test_email = "2021020024@email.szu.edu.cn"
    
    # 1. 发送密码重置邮件
    print("📧 步骤1: 发送密码重置邮件")
    try:
        response = requests.post(
            f"{BASE_URL}/recall",
            json={"email": test_email},
            headers={"Content-Type": "application/json"}
        )
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.json()}")
        
        if response.status_code == 200:
            print("✅ 邮件发送成功")
        else:
            print("❌ 邮件发送失败")
            return
        print()
    except Exception as e:
        print(f"❌ 发送邮件异常: {e}")
        return
    
    # 2. 等待用户输入验证码
    print("🔐 步骤2: 验证验证码")
    print("请检查邮箱并输入收到的验证码:")
    print("注意：验证码通常只有几分钟有效期，请尽快输入")
    code = input("验证码: ").strip()
    
    if not code:
        print("❌ 未输入验证码，跳过验证步骤")
        return
    
    # 3. 验证验证码
    print(f"正在验证验证码: {code}")
    # try:
    #     response = requests.post(
    #         f"{BASE_URL}/recall/verify",
    #         json={"email": test_email, "code": code},
    #         headers={"Content-Type": "application/json"}
    #     )
    #     print(f"状态码: {response.status_code}")
    #     print(f"响应: {response.json()}")
        
    #     if response.status_code == 200:
    #         print("✅ 验证码验证成功")
    #     else:
    #         print("❌ 验证码验证失败")
    #         if "expired" in str(response.json()).lower():
    #             print("💡 提示：验证码已过期，请重新发送邮件")
    #         return
    #     print()
    # except Exception as e:
    #     print(f"❌ 验证码验证异常: {e}")
    #     return
    
    # 4. 重置密码
    print("🔄 步骤2: 重置密码")
    new_password = "zhang123"
    
    try:
        response = requests.post(
            f"{BASE_URL}/recall/reset",
            json={
                "email": test_email, 
                "code": code, 
                "new_password": new_password
            },
            headers={"Content-Type": "application/json"}
        )
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.json()}")
        
        if response.status_code == 200:
            logger.info("✅ 密码重置成功")
        else:
            print("❌ 密码重置失败")
            if "expired" in str(response.json()).lower():
                print("💡 提示：验证码已过期，请重新发送邮件")
            elif "admin" in str(response.json()).lower():
                print("💡 提示：需要配置SUPABASE_SERVICE_ROLE_KEY环境变量")
        print()
    except Exception as e:
        print(f"❌ 密码重置异常: {e}")
        return
    
    # 5. 测试新密码登录
    print("🔑 步骤3: 测试新密码登录")
    try:
        response = requests.post(
            f"{BASE_URL}/login",
            json={"email": test_email, "password": new_password},
            headers={"Content-Type": "application/json"}
        )
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            print("✅ 新密码登录成功！")
            print(f"响应: {response.json()}")
        else:
            print("❌ 新密码登录失败")
            print(f"响应: {response.json()}")
    except Exception as e:
        print(f"❌ 登录测试异常: {e}")
    
    print("=" * 60)
    print("🎉 调试完成！")

def check_environment():
    """检查环境配置"""
    print("🔧 检查环境配置...")
    print("-" * 40)
    
    # 检查环境变量
    env_vars = [
        'SUPABASE_URL',
        'ANON_KEY', 
        'SERVICE_ROLE_KEY',
        'FRONTEND_URL'
    ]
    
    for var in env_vars:
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: {value[:20]}..." if len(value) > 20 else f"✅ {var}: {value}")
        else:
            print(f"❌ {var}: 未设置")
    
    print("-" * 40)

def test_health_check():
    """测试健康检查端点"""
    print("🏥 测试健康检查端点...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            print(f"✅ 健康检查成功: {response.json()}")
        else:
            print(f"❌ 健康检查失败: {response.json()}")
    except Exception as e:
        print(f"❌ 健康检查异常: {e}")

def show_troubleshooting_tips():
    """显示故障排除提示"""
    print("\n💡 故障排除提示:")
    print("-" * 40)
    print("1. 验证码过期：验证码通常只有几分钟有效期")
    print("2. 环境变量：确保SUPABASE_SERVICE_ROLE_KEY已设置")
    print("3. Supabase服务：确保本地Supabase服务正在运行")
    print("4. 端口配置：确保服务运行在正确的端口上")
    print("5. 网络连接：检查localhost:8001是否可访问")
    print("-" * 40)

if __name__ == "__main__":
    print("🚀 找回密码功能调试工具")
    print()
    
    # 检查环境配置
    check_environment()
    print()
    
    # 测试健康检查
    test_health_check()
    print()
    
    # 显示故障排除提示
    show_troubleshooting_tips()
    print()
    
    # 调试找回密码流程
    debug_recall_flow()
