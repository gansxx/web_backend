# Cloud Pool Demo - 多云VPS管理系统

这个目录包含了从center_management移动过来的多云VPS管理相关代码，统一管理多个云服务商的VPS实例。

## 目录结构

```
cloud_pool_demo/
├── __init__.py                    # 包初始化文件
├── README.md                      # 本说明文档
├── README_multi_cloud.md          # 详细的多云管理文档
├── demo_multi_cloud.py            # 多云管理演示脚本
├── node_manage_v2.py              # 增强的节点管理器
├── vps_manager/                   # 核心VPS管理模块
│   ├── __init__.py
│   ├── base.py                    # 抽象基类
│   ├── config.py                  # 配置管理
│   ├── factory.py                 # 工厂模式
│   ├── ssh_manager.py             # SSH管理
│   ├── exceptions.py              # 异常处理
│   ├── vultr.py                   # Vultr提供商
│   ├── aws_ec2.py                 # AWS EC2提供商
│   └── aws_lightsail.py           # AWS Lightsail提供商
├── aws_ec2_credentials.json       # AWS EC2凭证配置
├── aws_lightsail_credentials.json # AWS Lightsail凭证配置
├── vultr_credentials.json         # Vultr凭证配置
├── vps_config.json               # VPS配置文件
└── server_detail_multi.ini       # 服务器详情配置
```

## 使用方法

### 从主项目中导入

```python
# 从cloud_pool_demo导入多云管理功能
from cloud_pool_demo import EnhancedNodeProxy, CloudVPSManager, get_provider

# 创建VPS管理器
manager = CloudVPSManager()

# 获取特定云提供商
provider = get_provider('vultr')
```

### 运行演示

```bash
# 进入cloud_pool_demo目录
cd cloud_pool_demo

# 运行多云演示
python demo_multi_cloud.py
```

### 作为模块使用

```python
# 从项目根目录使用
import sys
sys.path.append('cloud_pool_demo')

from vps_manager import get_provider, list_providers
from node_manage_v2 import CloudVPSManager, EnhancedNodeProxy
```

## 支持的云提供商

- **Vultr**: 全功能API集成
- **AWS EC2**: 完整的EC2实例生命周期管理
- **AWS Lightsail**: 简化的云实例统一接口

## 配置文件

- `vps_config.json`: 各云提供商的VPS配置
- `*_credentials.json`: 各云提供商的API凭证
- `server_detail_multi.ini`: INI格式的服务器配置

## 注意事项

1. 确保已安装必要的依赖：`requests`, `loguru`, `paramiko`, `boto3`
2. 配置正确的API凭证在相应的credentials文件中
3. 该代码已从center_management目录移动，原始路径的引用已更新
4. 使用相对导入确保模块间的正确引用关系

更多详细信息请参阅 `README_multi_cloud.md`。