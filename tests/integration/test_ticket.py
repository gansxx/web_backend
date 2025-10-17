#!/usr/bin/env python3
"""
测试工单API功能
"""

import requests
import json

# 测试数据
test_ticket = {
    "subject": "测试工单标题",
    "priority": "normal",
    "category": "技术支持",
    "description": "这是一个测试工单的详细描述，用于验证API功能是否正常工作。"
}

def test_create_ticket():
    """测试创建工单功能"""
    url = "http://localhost:8001/support/tickets"
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(url, json=test_ticket, headers=headers)

        print(f"HTTP状态码: {response.status_code}")
        print(f"响应内容: {response.text}")

        if response.status_code == 201:
            result = response.json()
            print(f"✅ 工单创建成功!")
            print(f"工单ID: {result.get('ticket_id')}")
            print(f"消息: {result.get('message')}")
            return result.get('ticket_id')
        else:
            print(f"❌ 工单创建失败: {response.status_code}")
            return None

    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到服务器，请确保服务器已启动 (python run.py)")
        return None
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return None

def test_get_ticket(ticket_id):
    """测试获取工单功能"""
    if not ticket_id:
        print("❌ 没有有效的工单ID")
        return

    url = f"http://localhost:8001/support/tickets/{ticket_id}"

    try:
        response = requests.get(url)

        print(f"\n获取工单 - HTTP状态码: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print("✅ 工单获取成功!")
            print(f"工单详情: {json.dumps(result, ensure_ascii=False, indent=2)}")
        else:
            print(f"❌ 工单获取失败: {response.text}")

    except Exception as e:
        print(f"❌ 获取工单失败: {e}")

if __name__ == "__main__":
    print("🧪 开始测试工单API...")
    print("=" * 50)

    # 测试创建工单
    ticket_id = test_create_ticket()

    # 测试获取工单
    if ticket_id:
        test_get_ticket(ticket_id)

    print("\n" + "=" * 50)
    print("🏁 测试完成")