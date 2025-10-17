#!/usr/bin/env python3
"""
AWS Lightsail 凭证测试脚本
测试当前环境中的AWS凭证是否有效
"""
import json
import os
import sys
from pathlib import Path
from load_dotenv import load_dotenv
load_dotenv()  # 加载环境变量

# 添加项目路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError
except ImportError:
    print("❌ 错误: 未安装 boto3，请运行: uv pip install boto3")
    sys.exit(1)


def load_credentials():
    """加载凭证文件"""
    cred_file = Path(__file__).parent / "aws_lightsail_credentials.json"

    if not cred_file.exists():
        print(f"❌ 凭证文件不存在: {cred_file}")
        return None

    with open(cred_file) as f:
        config = json.load(f)

    credentials = config.get('credentials', {})
    region = config.get('region', 'ap-northeast-1')

    # 替换环境变量占位符
    access_key = credentials.get('access_key_id', '')
    if access_key.startswith('${') and access_key.endswith('}'):
        env_var = access_key[2:-1]
        access_key = os.getenv(env_var, '')

    secret_key = credentials.get('secret_access_key', '')
    if secret_key.startswith('${') and secret_key.endswith('}'):
        env_var = secret_key[2:-1]
        secret_key = os.getenv(env_var, '')

    session_token = credentials.get('session_token', '')
    if session_token and session_token.startswith('${') and session_token.endswith('}'):
        env_var = session_token[2:-1]
        session_token = os.getenv(env_var, '')

    return {
        'access_key_id': access_key,
        'secret_access_key': secret_key,
        'session_token': session_token if session_token else None,
        'region': region
    }


def test_credentials(credentials):
    """测试AWS凭证"""
    print("=" * 60)
    print("AWS Lightsail 凭证测试")
    print("=" * 60)

    # 检查凭证完整性
    if not credentials['access_key_id']:
        print("❌ 错误: AWS_ACCESS_KEY_ID 未设置")
        print("   请设置环境变量: export AWS_ACCESS_KEY_ID=your_access_key")
        return False

    if not credentials['secret_access_key']:
        print("❌ 错误: AWS_SECRET_ACCESS_KEY 未设置")
        print("   请设置环境变量: export AWS_SECRET_ACCESS_KEY=your_secret_key")
        return False

    print(f"✓ Access Key ID: {credentials['access_key_id'][:10]}...{credentials['access_key_id'][-4:]}")
    print(f"✓ Secret Access Key: {credentials['secret_access_key'][:10]}...****")
    if credentials['session_token']:
        print(f"✓ Session Token: {credentials['session_token'][:20]}...")
    print(f"✓ Region: {credentials['region']}")
    print()

    # 创建客户端
    try:
        print("🔧 创建 Lightsail 客户端...")
        session_params = {
            'aws_access_key_id': credentials['access_key_id'],
            'aws_secret_access_key': credentials['secret_access_key'],
            'region_name': credentials['region']
        }

        if credentials['session_token']:
            session_params['aws_session_token'] = credentials['session_token']

        client = boto3.client('lightsail', **session_params)
        print("✅ 客户端创建成功")
        print()

    except (NoCredentialsError, PartialCredentialsError) as e:
        print(f"❌ 凭证错误: {e}")
        return False
    except Exception as e:
        print(f"❌ 客户端创建失败: {e}")
        return False

    # 测试1: 获取区域列表
    print("📍 测试1: 获取可用区域...")
    try:
        response = client.get_regions(includeAvailabilityZones=True)
        regions = response.get('regions', [])
        print(f"✅ 成功获取 {len(regions)} 个区域")
        for region in regions[:3]:  # 只显示前3个
            print(f"   - {region['name']} ({region['displayName']})")
        if len(regions) > 3:
            print(f"   ... 还有 {len(regions) - 3} 个区域")
        print()
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_msg = e.response['Error']['Message']
        print(f"❌ 权限错误 [{error_code}]: {error_msg}")
        print("   需要权限: lightsail:GetRegions")
        return False
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False

    # 测试2: 列出实例
    print("💻 测试2: 列出 Lightsail 实例...")
    try:
        response = client.get_instances()
        instances = response.get('instances', [])
        print(f"✅ 成功列出 {len(instances)} 个实例")

        if instances:
            for instance in instances:
                name = instance.get('name', 'N/A')
                state = instance.get('state', {}).get('name', 'N/A')
                ip = instance.get('publicIpAddress', 'N/A')
                blueprint = instance.get('blueprintName', 'N/A')
                print(f"   - {name}: {state} | IP: {ip} | {blueprint}")
        else:
            print("   当前区域没有实例")
        print()
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_msg = e.response['Error']['Message']
        print(f"❌ 权限错误 [{error_code}]: {error_msg}")
        print("   需要权限: lightsail:GetInstances")
        return False
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False

    # 测试3: 获取套餐列表
    print("📦 测试3: 获取可用套餐...")
    try:
        response = client.get_bundles(includeInactive=False)
        bundles = response.get('bundles', [])
        print(f"✅ 成功获取 {len(bundles)} 个套餐")
        for bundle in bundles[:3]:  # 只显示前3个
            name = bundle.get('name', 'N/A')
            price = bundle.get('price', 0)
            cpu = bundle.get('cpuCount', 0)
            ram = bundle.get('ramSizeInGb', 0)
            print(f"   - {name}: ${price}/月 | {cpu} vCPU, {ram}GB RAM")
        if len(bundles) > 3:
            print(f"   ... 还有 {len(bundles) - 3} 个套餐")
        print()
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_msg = e.response['Error']['Message']
        print(f"❌ 权限错误 [{error_code}]: {error_msg}")
        print("   需要权限: lightsail:GetBundles")
        return False
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False

    # 测试4: 获取蓝图列表
    print("🎨 测试4: 获取操作系统蓝图...")
    try:
        response = client.get_blueprints()
        blueprints = response.get('blueprints', [])
        os_blueprints = [bp for bp in blueprints if bp.get('type') == 'os']
        print(f"✅ 成功获取 {len(os_blueprints)} 个操作系统蓝图")
        for bp in os_blueprints[:3]:  # 只显示前3个
            name = bp.get('name', 'N/A')
            description = bp.get('description', 'N/A')
            print(f"   - {name}: {description}")
        if len(os_blueprints) > 3:
            print(f"   ... 还有 {len(os_blueprints) - 3} 个蓝图")
        print()
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_msg = e.response['Error']['Message']
        print(f"❌ 权限错误 [{error_code}]: {error_msg}")
        print("   需要权限: lightsail:GetBlueprints")
        return False
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False

    print("=" * 60)
    print("✅ 所有测试通过！AWS凭证有效且权限配置正确")
    print("=" * 60)
    return True


def main():
    """主函数"""
    credentials = load_credentials()

    if not credentials:
        sys.exit(1)

    success = test_credentials(credentials)

    if not success:
        print()
        print("⚠️  建议检查事项:")
        print("   1. 确认 IAM 用户有 Lightsail 相关权限")
        print("   2. 检查 Access Key 是否正确且未过期")
        print("   3. 如果使用临时凭证，确认 Session Token 是否有效")
        print("   4. 验证选择的区域是否支持 Lightsail 服务")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
