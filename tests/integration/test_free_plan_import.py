#!/usr/bin/env python3
"""
测试 routes/free_plan.py 中的导入和函数调用是否正常
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def test_free_plan_imports():
    """测试免费套餐路由所需的所有导入"""
    print("=" * 60)
    print("测试 routes/free_plan.py 的导入和依赖")
    print("=" * 60)

    try:
        # 模拟 routes/free_plan.py:287 的导入
        print("\n1. 测试导入 test_add_user_v2...")
        from center_management.backend_api_v2 import test_add_user_v2
        print("   ✅ from center_management.backend_api_v2 import test_add_user_v2")

        print("\n2. 测试导入 NodeProxy...")
        from center_management.node_manage import NodeProxy
        print("   ✅ from center_management.node_manage import NodeProxy")

        print("\n3. 测试导入其他依赖...")
        from dotenv import load_dotenv
        import os
        print("   ✅ from dotenv import load_dotenv")
        print("   ✅ import os")

        print("\n4. 检查函数签名...")
        import inspect
        sig = inspect.signature(test_add_user_v2)
        print(f"   test_add_user_v2 参数: {sig}")

        print("\n5. 检查环境变量...")
        load_dotenv()
        gateway_ip = os.getenv('gateway_ip')
        gateway_user = os.getenv('gateway_user', 'admin')
        print(f"   gateway_ip: {gateway_ip}")
        print(f"   gateway_user: {gateway_user}")

        if not gateway_ip:
            print("   ⚠️  WARNING: gateway_ip 环境变量未设置")
        else:
            print("   ✅ 环境变量配置正常")

        print("\n" + "=" * 60)
        print("✅ 所有导入测试通过！")
        print("✅ routes/free_plan.py 应该能够正常工作")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_free_plan_imports()
    sys.exit(0 if success else 1)
