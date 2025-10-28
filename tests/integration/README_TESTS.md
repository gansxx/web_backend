# Integration Tests - 集成测试说明

本目录包含了后端API的集成测试脚本，用于测试实际的用户添加功能。

## 测试脚本说明

### 1. test_free_plan_import.py - 导入链测试

**用途**: 验证 `routes/free_plan.py` 中所需的所有模块导入是否正常工作

**运行方式**:
```bash
uv run python tests/integration/test_free_plan_import.py
```

**测试内容**:
- ✅ `center_management.backend_api_v2.test_add_user_v2` 导入
- ✅ `center_management.node_manage.NodeProxy` 导入
- ✅ 环境变量配置检查
- ✅ 函数签名验证

**预期输出**:
```
============================================================
测试 routes/free_plan.py 的导入和依赖
============================================================

1. 测试导入 test_add_user_v2...
   ✅ from center_management.backend_api_v2 import test_add_user_v2

2. 测试导入 NodeProxy...
   ✅ from center_management.node_manage import NodeProxy

...

✅ 所有导入测试通过！
✅ routes/free_plan.py 应该能够正常工作
============================================================
```

---

### 2. test_add_user_real.py - 实际用户添加测试

**用途**: 实际调用后端API执行完整的用户添加流程

**运行方式**:

#### 基本用法 - 使用默认参数
```bash
# 自动生成测试用户邮箱
uv run python tests/integration/test_add_user_real.py
```

#### 指定用户邮箱
```bash
uv run python tests/integration/test_add_user_real.py --email test@example.com
```

#### 指定订阅URL和别名
```bash
uv run python tests/integration/test_add_user_real.py \
  --email test@example.com \
  --url jiasu.example.com \
  --alias free_plan
```

#### 启用链接验证（需要更多时间）
```bash
uv run python tests/integration/test_add_user_real.py \
  --email test@example.com \
  --verify
```

#### 自定义带宽限制
```bash
uv run python tests/integration/test_add_user_real.py \
  --email test@example.com \
  --up 100 \
  --down 100
```

#### 完整参数示例
```bash
uv run python tests/integration/test_add_user_real.py \
  --email premium_user@example.com \
  --url jiasu.superjiasu.top \
  --alias premium_plan \
  --up 200 \
  --down 200 \
  --retries 3 \
  --verify
```

**测试流程**:
1. 📋 加载环境配置（gateway_ip, gateway_user等）
2. 🔌 建立SSH连接到远程服务器
3. 👤 调用 `test_add_user_v2()` 添加用户
4. 🔍 智能端口选择和分配
5. 📝 生成 hysteria2 订阅链接
6. ✅ 可选：验证链接有效性
7. 📱 返回订阅链接

**预期输出**:
```
======================================================================
开始测试用户添加功能
======================================================================

📋 测试配置:
   网关地址: 52.198.232.212
   网关用户: admin
   用户邮箱: test_user_20251022_001234@example.com
   订阅URL: 使用IP地址
   订阅别名: test_subscription
   上传带宽: 50 Mbps
   下载带宽: 50 Mbps
   验证链接: 否
   最大重试: 2 次

🔌 连接到服务器...
✅ SSH连接建立成功

👤 开始添加用户...
   正在调用 test_add_user_v2()...

======================================================================
✅ 用户添加成功！
======================================================================

📱 订阅链接:
   hysteria2://password@52.198.232.212:12345?sni=example.com#test_subscription

💾 可以将此链接保存到数据库或返回给用户
======================================================================
```

**命令行参数**:
| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--email` | string | 否 | 自动生成 | 用户邮箱（用作用户名） |
| `--url` | string | 否 | None | 订阅链接中使用的域名 |
| `--alias` | string | 否 | test_subscription | 订阅链接的别名 |
| `--verify` | flag | 否 | False | 验证生成的订阅链接 |
| `--retries` | int | 否 | 2 | 最大重试次数 |
| `--up` | int | 否 | 50 | 上传带宽限制(Mbps) |
| `--down` | int | 否 | 50 | 下载带宽限制(Mbps) |

---

## 环境要求

### 必需的环境变量

确保 `.env` 文件中配置了以下变量：

```bash
# 网关服务器配置
gateway_ip=52.198.232.212        # 远程服务器IP地址
gateway_user=admin               # SSH登录用户名（默认: admin）

# 其他Supabase配置...
```

### SSH密钥配置

确保存在有效的SSH私钥：
```bash
# 默认位置
~/.ssh/id_ed25519

# 或在项目根目录
./id_ed25519
```

---

## 故障排查

### 问题1: 导入错误
```
ModuleNotFoundError: No module named 'center_management.backend_api_v2'
```

**解决方法**:
- 确保已执行文件重命名操作
- 检查 `center_management/backend_api_v2.py` 是否存在
- 运行导入测试: `uv run python tests/integration/test_free_plan_import.py`

### 问题2: SSH连接失败
```
❌ SSH连接失败: Connection refused
```

**解决方法**:
- 检查 `gateway_ip` 环境变量是否正确
- 确认SSH密钥文件存在且有正确权限 (chmod 600)
- 验证服务器是否可达: `ping $gateway_ip`
- 测试SSH连接: `ssh -i ~/.ssh/id_ed25519 admin@$gateway_ip`

### 问题3: 用户添加失败
```
❌ 用户添加失败: test_add_user_v2 返回 None
```

**可能原因**:
- 端口池已耗尽（检查端口范围配置）
- DNS解析失败（如果指定了 --url）
- 远程服务器脚本执行失败
- 网络连接不稳定

**调试方法**:
1. 检查服务器日志
2. 增加重试次数: `--retries 5`
3. 禁用链接验证测试: 不使用 `--verify`
4. 检查远程服务器的 `/root/sing-box-v2ray/self_sb_change.sh` 脚本

### 问题4: DNS解析失败
```
❌ DNS解析失败: jiasu.example.com 未解析到目标IP
```

**解决方法**:
- 检查域名DNS记录是否正确配置
- 使用 `dig` 或 `nslookup` 验证DNS解析
- 暂时使用IP地址（不指定 --url 参数）

---

## 开发建议

### 在开发环境中测试
```bash
# 快速测试导入
uv run python tests/integration/test_free_plan_import.py

# 测试用户添加（不验证链接）
uv run python tests/integration/test_add_user_real.py --email dev_test@example.com
```

### 在生产部署前测试
```bash
# 完整测试（包括链接验证）
uv run python tests/integration/test_add_user_real.py \
  --email prod_test@example.com \
  --url jiasu.production.com \
  --verify \
  --retries 3
```

---

## 相关文件

- `center_management/backend_api_v2.py` - 用户添加核心逻辑
- `center_management/node_manage.py` - SSH连接和远程执行
- `center_management/smart_port_manager.py` - 智能端口分配
- `routes/free_plan.py` - FastAPI路由，调用用户添加功能

---

## 更新日志

- **2025-10-22**: 创建集成测试脚本
  - 添加 `test_free_plan_import.py` - 导入链验证
  - 添加 `test_add_user_real.py` - 实际用户添加测试
  - 文件重命名: `test_api_v2.py` → `backend_api_v2.py`
