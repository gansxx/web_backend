#!/usr/bin/env python3
"""
测试找回密码功能的脚本
"""

import requests
import json
import time

# API基础URL
BASE_URL = "http://localhost:8001"

def test_recall_flow():
    """测试完整的找回密码流程"""
    
    print("🧪 开始测试找回密码功能...")
    print("=" * 50)
    
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
        print()
    except Exception as e:
        print(f"❌ 发送邮件失败: {e}")
        return
    
    # 2. 验证验证码（这里需要用户手动输入）
    print("🔐 步骤2: 验证验证码")
    print("请检查邮箱并输入收到的验证码:")
    code = input("验证码: ").strip()
    
    if not code:
        print("❌ 未输入验证码，跳过验证步骤")
        return
    
    try:
        response = requests.post(
            f"{BASE_URL}/recall/verify",
            json={"email": test_email, "code": code},
            headers={"Content-Type": "application/json"}
        )
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.json()}")
        print()
    except Exception as e:
        print(f"❌ 验证码验证失败: {e}")
        return
    
    # 3. 重置密码
    print("🔄 步骤3: 重置密码")
    new_password = "newpassword123"
    
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
        print()
    except Exception as e:
        print(f"❌ 密码重置失败: {e}")
        return
    
    # 4. 测试新密码登录
    print("🔑 步骤4: 测试新密码登录")
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
        print(f"❌ 登录测试失败: {e}")
    
    print("=" * 50)
    print("🎉 测试完成！")

def test_health_check():
    """测试健康检查端点"""
    print("🏥 测试健康检查端点...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.json()}")
    except Exception as e:
        print(f"❌ 健康检查失败: {e}")

if __name__ == "__main__":
    print("🚀 找回密码功能测试工具")
    print()
    
    # 测试健康检查
    test_health_check()
    print()
    
    # 测试找回密码流程
    test_recall_flow()
