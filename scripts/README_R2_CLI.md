# R2 包管理交互式终端工具

一个功能完整、用户友好的 Python 终端脚本，用于管理 R2 软件包分发系统。

## ✨ 功能特性

- 🎨 **美观的终端界面** - 使用 `rich` 库提供彩色输出和格式化表格
- 📦 **完整的 API 覆盖** - 支持所有 14 个 R2 包管理操作
- 🔄 **交互式菜单** - 数字选择菜单，操作简单直观
- ✅ **完善的错误处理** - 友好的错误提示和用户引导
- ⚙️ **灵活配置** - 支持环境变量和命令行参数
- 📊 **结果美化** - JSON 高亮、表格展示、进度条

## 🚀 快速开始

### 安装依赖

脚本依赖已在项目中安装：
- `requests` - HTTP 客户端
- `rich` - 终端美化

如需单独安装：
```bash
uv add rich requests
# 或
pip install rich requests
```

### 基本使用

```bash
# 进入项目目录
cd /root/self_code/web_backend

# 运行脚本（使用默认配置）
uv run python scripts/r2_cli.py

# 或直接运行（如果已激活虚拟环境）
python scripts/r2_cli.py
```

### 命令行参数

```bash
# 指定 API 地址
python scripts/r2_cli.py --base-url http://localhost:8001

# 指定默认用户 ID
python scripts/r2_cli.py --user-id "your-uuid-here"

# 指定请求超时时间（秒）
python scripts/r2_cli.py --timeout 60

# 组合使用
python scripts/r2_cli.py --base-url http://localhost:8001 --user-id "uuid" --timeout 60

# 查看帮助
python scripts/r2_cli.py --help
```

### 环境变量配置

可以通过环境变量配置默认值：

```bash
export R2_API_URL="http://localhost:8001"
export R2_USER_ID="00000000-0000-0000-0000-000000000000"
export R2_TIMEOUT="30"

python scripts/r2_cli.py
```

或在 `.env` 文件中配置（需手动加载）：
```env
R2_API_URL=http://localhost:8001
R2_USER_ID=00000000-0000-0000-0000-000000000000
R2_TIMEOUT=30
```

## 📋 功能菜单

脚本启动后会显示交互式菜单：

```
╔═══════════════════════════════════════════════════╗
║   🚀 R2 包管理系统 - 交互式终端工具 v1.0         ║
║                                                   ║
║   📦 完整的包管理功能                             ║
║   🎨 美观的终端界面                               ║
║   ⚡ 快速且易用                                   ║
╚═══════════════════════════════════════════════════╝

╭──────────┬────────┬──────────────────╮
│  1       │  📤    │  上传包          │
│  2       │  📊    │  查看包信息      │
│  3       │  📋    │  列出包版本      │
│  4       │  🔍    │  搜索包          │
│  5       │  📚    │  列出所有公开包  │
│  6       │  👤    │  查看我的上传    │
│  7       │  ✏️     │  更新包元数据    │
│  8       │  🗑️     │  删除包          │
│  9       │  📈    │  查看存储统计    │
│  10      │  📊    │  查看包统计      │
│  11      │  🧹    │  清理旧包        │
│  12      │  ✅    │  验证包完整性    │
│  13      │  💚    │  健康检查        │
│  14      │  📥    │  生成下载链接    │
│  0       │  🚪    │  退出            │
╰──────────┴────────┴──────────────────╯
```

## 🔧 功能详解

### 1. 📤 上传包

上传软件包到 R2 存储。

**交互流程：**
```
选择操作: 1
📤 上传包

包名称: my-tool
版本号 (如: 1.0.0): 1.0.0
文件路径: ./my-tool-1.0.0.tar.gz
描述 (可选): A useful command-line tool
标签 (逗号分隔, 可选): cli,python,tool
是否公开? (Y/n): y

⏳ 正在上传...
✅ 上传成功

{
  "id": "uuid-here",
  "package_name": "my-tool",
  "version": "1.0.0",
  "r2_key": "packages/my-tool/1.0.0/my-tool-1.0.0",
  "file_size": 1572864,
  "file_hash": "sha256:abc123...",
  "hash_algorithm": "sha256",
  "created_at": "2025-10-16T08:30:00Z"
}
```

**注意事项：**
- 必须从 localhost 运行（访问控制限制）
- 文件路径可以是相对或绝对路径
- 版本号必须符合语义化版本规范 (如: 1.0.0, 2.1.3-beta)
- 标签用逗号分隔，便于搜索和分类

### 2. 📊 查看包信息

获取指定包的详细信息。

**交互流程：**
```
选择操作: 2
📊 查看包信息

包名称: my-tool
版本号: 1.0.0

✅ my-tool v1.0.0 信息

{
  "id": "uuid",
  "package_name": "my-tool",
  "version": "1.0.0",
  "description": "A useful tool",
  "tags": ["cli", "python"],
  "is_public": true,
  "file_size": 1572864,
  "download_count": 150,
  "status": "active",
  "created_at": "2025-10-16T08:30:00Z"
}
```

### 3. 📋 列出包版本

列出指定包的所有版本历史。

**交互流程：**
```
选择操作: 3
📋 列出包版本

包名称: my-tool
最大显示数量 (20): 10

my-tool 的所有版本
╭────────┬────────┬────────────┬──────────────────────╮
│ 版本   │ 状态   │ 下载次数   │ 创建时间             │
├────────┼────────┼────────────┼──────────────────────┤
│ 1.2.0  │ active │ 89         │ 2025-10-15T10:00:00Z │
│ 1.1.0  │ active │ 234        │ 2025-10-10T09:30:00Z │
│ 1.0.0  │ active │ 150        │ 2025-10-05T08:00:00Z │
╰────────┴────────┴────────────┴──────────────────────╯
```

### 4. 🔍 搜索包

按关键词、标签搜索包。

**交互流程：**
```
选择操作: 4
🔍 搜索包

搜索关键词 (可选): cli
标签 (逗号分隔, 可选): python
只搜索公开包? (Y/n): y
最大显示数量 (20): 20

找到 5 个包
╭──────────────┬────────┬──────────────────────────┬────────────╮
│ 包名         │ 版本   │ 描述                     │ 下载次数   │
├──────────────┼────────┼──────────────────────────┼────────────┤
│ my-tool      │ 1.2.0  │ A useful CLI tool        │ 150        │
│ cli-helper   │ 2.1.0  │ CLI utility helper       │ 89         │
│ python-utils │ 1.0.5  │ Python utility library   │ 234        │
╰──────────────┴────────┴──────────────────────────┴────────────╯
```

### 5. 📚 列出所有公开包

列出系统中所有公开可访问的包。

**交互流程：**
```
选择操作: 5
📚 列出所有公开包

最大显示数量 (20): 30

公开包列表 (共 15 个)
╭──────────────┬────────┬────────────────────┬────────────╮
│ 包名         │ 版本   │ 描述               │ 下载次数   │
├──────────────┼────────┼────────────────────┼────────────┤
│ ...          │ ...    │ ...                │ ...        │
╰──────────────┴────────┴────────────────────┴────────────╯
```

### 6. 👤 查看我的上传

查看特定用户上传的所有包。

**交互流程：**
```
选择操作: 6
👤 查看我的上传

用户 ID (00000000-0000-0000-0000-000000000000): [Enter使用默认]
最大显示数量 (20): 20

我的上传 (共 3 个)
╭──────────┬────────┬────────┬────────────╮
│ 包名     │ 版本   │ 状态   │ 下载次数   │
├──────────┼────────┼────────┼────────────┤
│ my-tool  │ 1.2.0  │ active │ 150        │
│ my-lib   │ 2.0.0  │ active │ 45         │
╰──────────┴────────┴────────┴────────────╯
```

### 7. ✏️ 更新包元数据

更新包的描述、标签、可见性等信息。

**交互流程：**
```
选择操作: 7
✏️ 更新包元数据

包名称: my-tool
版本号: 1.0.0

请输入要更新的字段 (留空则不更新):
新描述: Updated description for my tool
新标签 (逗号分隔): cli,python,utility,updated
是否公开 (y/n/留空): y

✅ 更新成功

{
  "id": "uuid",
  "package_name": "my-tool",
  "version": "1.0.0",
  "description": "Updated description for my tool",
  "tags": ["cli", "python", "utility", "updated"],
  "is_public": true,
  "updated_at": "2025-10-16T09:00:00Z"
}
```

### 8. 🗑️ 删除包

删除指定的包版本（支持软删除和硬删除）。

**交互流程：**
```
选择操作: 8
🗑️ 删除包

包名称: my-tool
版本号: 1.0.0
永久删除 (硬删除)? 否则为软删除 (y/N): n
⚠️ 确认删除 my-tool v1.0.0? (y/N): y

✅ 删除成功

{
  "message": "Package deleted successfully",
  "package_name": "my-tool",
  "version": "1.0.0",
  "deleted_at": "2025-10-16T09:15:00Z"
}
```

**删除类型说明：**
- **软删除 (Soft Delete)**: 标记为已删除，保留文件，可恢复
- **硬删除 (Hard Delete)**: 永久删除文件和记录，不可恢复

### 9. 📈 查看存储统计

查看整体存储使用情况和统计信息。

**交互流程：**
```
选择操作: 9
📈 查看存储统计

✅ 存储统计

{
  "total_packages": 150,
  "total_versions": 500,
  "total_downloads": 50000,
  "total_size_bytes": 10737418240,
  "total_size_mb": 10240.0,
  "total_size_gb": 10.0,
  "bucket_name": "test",
  "r2_bucket_size_bytes": 10737418240,
  "r2_object_count": 500
}
```

### 10. 📊 查看包统计

查看指定包的详细统计信息。

**交互流程：**
```
选择操作: 10
📊 查看包统计

包名称: my-tool

✅ my-tool 统计信息

{
  "package_name": "my-tool",
  "total_versions": 3,
  "total_downloads": 473,
  "total_size_bytes": 4718592,
  "total_size_mb": 4.5,
  "latest_version": "1.2.0",
  "latest_upload_date": "2025-10-15T10:00:00Z"
}
```

### 11. 🧹 清理旧包

清理超过指定天数的归档包。

**交互流程：**
```
选择操作: 11
🧹 清理旧包

归档天数阈值 (90): 90
仅预览 (不实际删除)? (Y/n): y

[预览模式]
找到 5 个符合条件的包

待清理的包
╭──────────────┬────────┬──────────────────────╮
│ 包名         │ 版本   │ 归档时间             │
├──────────────┼────────┼──────────────────────┤
│ old-package  │ 0.5.0  │ 2025-07-01T12:00:00Z │
│ deprecated   │ 1.0.0  │ 2025-06-15T10:00:00Z │
╰──────────────┴────────┴──────────────────────╯
```

**使用建议：**
1. 先使用 `dry_run=true` 预览
2. 确认清理列表无误后再执行实际清理
3. 建议定期执行（如每月一次）

### 12. ✅ 验证包完整性

验证包文件的完整性（检查哈希值）。

**交互流程：**
```
选择操作: 12
✅ 验证包完整性

包名称: my-tool
版本号: 1.0.0

⏳ 正在验证...

✅ my-tool v1.0.0 完整性验证通过!
```

### 13. 💚 健康检查

检查 R2 系统和数据库的连接状态。

**交互流程：**
```
选择操作: 13
💚 健康检查

⏳ 检查中...

状态: healthy
R2 连接: ✅ 正常
数据库连接: ✅ 正常
```

### 14. 📥 生成下载链接

为指定包生成临时下载链接。

**交互流程：**
```
选择操作: 14
📥 生成下载链接

包名称: my-tool
版本号: 1.0.0
链接有效期 (秒) (3600): 7200

✅ 下载链接已生成!

🔗 下载链接:
https://your-r2-domain.com/packages/my-tool/1.0.0/my-tool-1.0.0?X-Amz-...

⏰ 有效期: 7200 秒 (120 分钟)
```

## ⚠️ 访问控制说明

根据 R2 API 的访问控制模型：

### Localhost-Only 操作（必须在服务器本地运行）

以下操作只能从 localhost (127.0.0.1, ::1) 执行：

- ✅ 上传包
- ✅ 更新包元数据
- ✅ 删除包
- ✅ 搜索包
- ✅ 列出公开包
- ✅ 查看我的上传
- ✅ 查看包信息
- ✅ 列出包版本
- ✅ 存储统计
- ✅ 包统计
- ✅ 清理旧包
- ✅ 验证完整性
- ✅ 健康检查

### External Access（可从外部访问）

- ✅ 生成下载链接（公开包无需认证，私有包需要认证）

**如果从非 localhost 运行：**
- 大部分管理操作会返回 `403 Forbidden`
- 只有下载链接生成功能可以正常使用

**建议使用方式：**
1. **本地使用**: 直接在服务器上运行脚本
2. **远程使用**: 通过 SSH 连接到服务器后运行
3. **SSH 隧道**: 建立 SSH 隧道后本地访问

```bash
# SSH 方式
ssh user@server "cd /path/to/project && python scripts/r2_cli.py"

# SSH 隧道
ssh -L 8001:localhost:8001 user@server
python scripts/r2_cli.py --base-url http://localhost:8001
```

## 🔧 错误处理

脚本提供友好的错误提示：

### 常见错误及解决方法

**1. 连接错误**
```
❌ 网络错误: Connection refused
```
**解决**: 确保 R2 API 服务正在运行 (`uv run python run.py`)

**2. 403 Forbidden**
```
🔒 访问被拒绝：此操作只能从本地主机执行
```
**解决**: 在服务器本地运行脚本，或通过 SSH 连接

**3. 404 Not Found**
```
❌ 未找到：请求的资源不存在
```
**解决**: 检查包名称和版本号是否正确

**4. 文件不存在**
```
❌ 文件不存在: ./my-package.tar.gz
```
**解决**: 检查文件路径是否正确（支持相对和绝对路径）

**5. 版本已存在**
```
❌ 错误 (400): Package my-tool v1.0.0 already exists
```
**解决**: 使用不同的版本号或先删除现有版本

## 🎨 界面特性

### 彩色输出
- 🟢 绿色：成功操作
- 🔴 红色：错误和警告
- 🔵 蓝色：信息提示
- 🟡 黄色：注意事项

### 表格展示
- 清晰的列对齐
- 自动列宽调整
- 边框美化
- 数据高亮

### 进度指示
- 上传文件时显示进度条
- 长时间操作显示旋转指示器
- 操作状态实时反馈

### JSON 美化
- 语法高亮
- 自动缩进
- 行号显示（可选）
- 主题化显示

## 📝 使用技巧

### 1. 批量操作

可以通过脚本或命令行工具配合使用：

```bash
# 批量上传
for file in packages/*.tar.gz; do
    echo "Uploading $file"
    # 使用自动化工具或 expect 脚本
done
```

### 2. 配置文件

创建配置脚本简化使用：

```bash
# ~/.r2_cli_config
export R2_API_URL="http://localhost:8001"
export R2_USER_ID="your-default-user-id"
export R2_TIMEOUT="60"

# 使用
source ~/.r2_cli_config
python scripts/r2_cli.py
```

### 3. 快捷别名

在 `~/.bashrc` 或 `~/.zshrc` 中添加：

```bash
alias r2cli='cd /root/self_code/web_backend && uv run python scripts/r2_cli.py'
alias r2='r2cli'
```

使用：
```bash
r2  # 直接启动 CLI
```

### 4. 日志记录

重定向输出保存操作日志：

```bash
python scripts/r2_cli.py 2>&1 | tee r2_operations.log
```

## 🐛 故障排查

### 脚本无法启动

**问题**: `ModuleNotFoundError: No module named 'rich'`

**解决**:
```bash
uv add rich requests
# 或
pip install rich requests
```

### API 连接失败

**问题**: 无法连接到 API

**检查清单**:
1. ✅ API 服务是否运行: `curl http://localhost:8001/health`
2. ✅ 端口是否正确: 默认 8001
3. ✅ 防火墙设置
4. ✅ URL 配置是否正确

### 权限问题

**问题**: `Permission denied` 或 `403 Forbidden`

**解决**:
1. 确保从 localhost 运行
2. 检查文件权限
3. 使用正确的用户 ID

## 📚 相关文档

- [R2 包管理系统 README](../center_management/r2_storage/README.md)
- [API 路由文档](../routes/r2_packages.py)
- [访问控制测试](../tests/integration/test_r2_access_control.py)

## 🤝 贡献

欢迎提交问题和改进建议！

## 📄 许可证

This tool is part of the web_backend project.

---

**版本**: 1.0
**最后更新**: 2025-10-16
**维护者**: R2 开发团队
