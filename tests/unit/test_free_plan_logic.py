#!/usr/bin/env python3
"""
测试免费套餐检查逻辑
"""

# 模拟测试数据
def test_free_plan_logic():
    """测试免费套餐检查逻辑"""

    # 模拟用户产品数据
    test_cases = [
        # Case 1: 用户没有产品
        {
            "name": "无产品用户",
            "products": [],
            "expected_has_free": False
        },
        # Case 2: 用户有付费产品但没有免费套餐
        {
            "name": "仅有付费产品",
            "products": [
                {"subscription_url": "https://example.com/premium", "product_name": "Premium Plan"},
                {"subscription_url": "https://example.com/pro", "product_name": "Pro Plan"}
            ],
            "expected_has_free": False
        },
        # Case 3: 用户有免费套餐
        {
            "name": "有免费套餐",
            "products": [
                {"subscription_url": "https://example.com/premium", "product_name": "Premium Plan"},
                {"subscription_url": "https://example.com/free-plan", "product_name": "Free Plan"},
                {"subscription_url": "https://example.com/basic", "product_name": "Basic Plan"}
            ],
            "expected_has_free": True
        },
        # Case 4: 用户有多种免费套餐
        {
            "name": "多个免费套餐",
            "products": [
                {"subscription_url": "https://example.com/free-trial", "product_name": "Free Trial"},
                {"subscription_url": "https://example.com/free-basic", "product_name": "Free Basic"},
                {"subscription_url": "https://example.com/premium", "product_name": "Premium Plan"}
            ],
            "expected_has_free": True
        },
        # Case 5: 大小写不敏感
        {
            "name": "大小写不敏感",
            "products": [
                {"subscription_url": "https://example.com/Free_Plan", "product_name": "Free Plan"},
                {"subscription_url": "https://example.com/FREE-TRIAL", "product_name": "Free Trial"}
            ],
            "expected_has_free": True
        }
    ]

    for test_case in test_cases:
        print(f"\n测试案例: {test_case['name']}")

        # 模拟免费套餐检查逻辑
        user_products = test_case['products']
        free_plans = []
        all_products = []

        for product in user_products:
            all_products.append(product)

            # 检查 subscription_url 中是否包含免费套餐
            if isinstance(product, dict):
                subscription_url = product.get("subscription_url", "")
                if subscription_url and "free" in str(subscription_url).lower():
                    free_plans.append(product)

        has_free_plan = len(free_plans) > 0

        print(f"  输入产品: {len(user_products)} 个")
        print(f"  免费套餐: {len(free_plans)} 个")
        print(f"  结果: {has_free_plan}")
        print(f"  期望: {test_case['expected_has_free']}")

        if has_free_plan == test_case['expected_has_free']:
            print("  ✅ 通过")
        else:
            print("  ❌ 失败")

        # 详细显示免费套餐
        if free_plans:
            print("  免费套餐详情:")
            for plan in free_plans:
                print(f"    - {plan.get('product_name', 'N/A')}: {plan.get('subscription_url', 'N/A')}")

if __name__ == "__main__":
    test_free_plan_logic()
    print("\n免费套餐检查逻辑测试完成！")