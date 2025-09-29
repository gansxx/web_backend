#!/bin/bash
# PostgreSQL 数据库远程复制工具 - 使用示例

# 脚本路径
SCRIPT_PATH="center_management/db/migration/pg_dump_remote.py"

echo "PostgreSQL 数据库远程复制工具 - 使用示例"
echo "========================================="

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 函数定义
print_example() {
    echo -e "\n${BLUE}$1${NC}"
    echo -e "${GREEN}$2${NC}"
    echo -e "${YELLOW}说明：${NC}$3\n"
}

print_section() {
    echo -e "\n${RED}=== $1 ===${NC}"
}

# 基础操作示例
print_section "基础操作"

print_example "测试数据库连接" \
    "uv run python $SCRIPT_PATH --test" \
    "检查本地和远程数据库连接状态"

print_example "查看帮助信息" \
    "uv run python $SCRIPT_PATH --help" \
    "显示所有可用参数和选项"

# 数据库导出示例
print_section "数据库导出"

print_example "从远程导出全库（自动命名）" \
    "uv run python $SCRIPT_PATH --export --source remote" \
    "导出远程数据库的完整数据到自动生成的备份文件"

print_example "从本地导出到指定文件" \
    "uv run python $SCRIPT_PATH --export --source local --output my_local_backup.sql" \
    "导出本地数据库到指定的文件名"

print_example "导出指定表" \
    "uv run python $SCRIPT_PATH --export --source remote --tables \"orders,products,users\"" \
    "只导出指定的表，表名用逗号分隔"

print_example "只导出数据结构" \
    "uv run python $SCRIPT_PATH --export --source remote --schema-only" \
    "只导出表结构、索引、约束等，不包含数据"

print_example "只导出数据" \
    "uv run python $SCRIPT_PATH --export --source remote --data-only" \
    "只导出表数据，不包含结构定义"

# 数据库导入示例
print_section "数据库导入"

print_example "从备份文件导入到本地" \
    "uv run python $SCRIPT_PATH --import --file backups/full_remote_20240930_123000.sql --target local" \
    "将备份文件导入到本地数据库"

print_example "导入前清理数据库" \
    "uv run python $SCRIPT_PATH --import --file backup.sql --target local --clean" \
    "导入前先删除目标数据库中的所有表"

# 数据库同步示例
print_section "数据库同步（最常用）"

print_example "完整同步：远程 → 本地" \
    "uv run python $SCRIPT_PATH --sync --source remote --target local" \
    "从远程数据库完整同步到本地（导出+导入一步完成）"

print_example "同步前清理本地数据库" \
    "uv run python $SCRIPT_PATH --sync --source remote --target local --clean" \
    "先清理本地数据库，然后从远程完整同步"

print_example "只同步指定表" \
    "uv run python $SCRIPT_PATH --sync --source remote --target local --tables \"orders,products\"" \
    "只同步指定的表到本地数据库"

# 备份管理示例
print_section "备份管理"

print_example "列出所有备份文件" \
    "uv run python $SCRIPT_PATH --list" \
    "显示备份目录中的所有 SQL 文件及其大小和创建时间"

print_example "清理旧备份（保留5个）" \
    "uv run python $SCRIPT_PATH --cleanup --keep 5" \
    "删除旧的备份文件，只保留最新的5个"

print_example "清理旧备份（保留10个）" \
    "uv run python $SCRIPT_PATH --cleanup --keep 10" \
    "删除旧的备份文件，只保留最新的10个"

# 实际工作场景示例
print_section "实际工作场景"

print_example "开发环境数据更新（推荐）" \
    "uv run python $SCRIPT_PATH --sync --source remote --target local --clean" \
    "完全用生产数据替换本地开发数据库"

print_example "生产数据库备份" \
    "uv run python $SCRIPT_PATH --export --source remote --output \"prod_backup_\$(date +%Y%m%d_%H%M%S).sql\"" \
    "创建带时间戳的生产数据库备份"

print_example "测试特定功能的数据" \
    "uv run python $SCRIPT_PATH --sync --source remote --target local --tables \"orders,order_items,payments\"" \
    "只同步订单相关的表来测试支付功能"

print_example "获取最新的产品数据" \
    "uv run python $SCRIPT_PATH --export --source remote --tables \"products\" --data-only" \
    "只导出产品表的数据（保持本地结构不变）"

# 高级用法示例
print_section "高级用法"

print_example "备份 + 数据同步组合" \
    "uv run python $SCRIPT_PATH --export --source remote --output daily_backup.sql && \
uv run python $SCRIPT_PATH --sync --source remote --target local --clean" \
    "先备份远程数据库，然后同步到本地"

print_example "批量操作脚本示例" \
    "# 创建一个每日同步脚本
cat > daily_sync.sh << 'EOF'
#!/bin/bash
echo \"开始每日数据同步 - \$(date)\"
uv run python $SCRIPT_PATH --export --source remote --output \"daily_backup_\$(date +%Y%m%d).sql\"
uv run python $SCRIPT_PATH --sync --source remote --target local --clean
uv run python $SCRIPT_PATH --cleanup --keep 7
echo \"同步完成 - \$(date)\"
EOF
chmod +x daily_sync.sh" \
    "创建自动化的每日数据同步脚本"

# 故障排除提示
print_section "故障排除提示"

echo -e "${YELLOW}1. 连接失败:${NC}"
echo "   - 检查网关 IP 地址是否正确"
echo "   - 确认远程数据库服务正在运行"
echo "   - 检查防火墙和端口设置"

echo -e "\n${YELLOW}2. 权限错误:${NC}"
echo "   - 验证数据库用户名和密码"
echo "   - 确保用户有相应的数据库权限"

echo -e "\n${YELLOW}3. 工具缺失:${NC}"
echo "   - 安装 PostgreSQL 客户端: sudo apt-get install postgresql-client"
echo "   - 同步 Python 依赖: uv sync"

echo -e "\n${YELLOW}4. 环境变量:${NC}"
echo "   - 检查 .env 文件是否存在"
echo "   - 确认 POSTGRES_PASSWORD 等变量已设置"

echo -e "\n${RED}重要提醒：${NC}"
echo -e "${YELLOW}• 在生产环境中使用 --clean 参数前请务必谨慎${NC}"
echo -e "${YELLOW}• 建议定期清理备份文件以节省磁盘空间${NC}"
echo -e "${YELLOW}• 大型数据库的同步可能需要较长时间，请耐心等待${NC}"

echo -e "\n${GREEN}快速开始：${NC}"
echo "1. uv run python $SCRIPT_PATH --test    # 测试连接"
echo "2. uv run python $SCRIPT_PATH --sync --source remote --target local --clean    # 完整同步"
echo "3. uv run python $SCRIPT_PATH --list    # 查看备份文件"