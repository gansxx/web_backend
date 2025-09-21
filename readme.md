# 配置env文件
```env
FRONTEND_URL
POSTGRES_PASSWORD
JWT_SECRET
ANON_KEY
SERVICE_ROLE_KEY
DASHBOARD_USERNAME
DASHBOARD_PASSWORD
```

# 安装supabase cli以及pgtap
- scp本地上传或通过curl下载最新版本
```bash

```
- pgtap用于自动化测试postgresql

# docker容器配置
```bash
# Pull the latest images
docker compose pull
# Start the services (in detached mode)
docker compose up -d
```
- 关闭非必须容器
```bash
docker stop supabase-vector realtime-dev.supabase-realtime supabase-storage supabase-edge-functions supabase-imgproxy
```

# python环境配置
```bash
bash Miniconda3-latest-Linux-x86_64 -b -p $HOME/miniconda3
$HOME/miniconda3/bin/conda init
source ~/.bashrc
conda create -n "fastapi" python==3.12
conda activate fastapi
pip install uv
uv pip install -r requirements.txt
```

# 运行后端服务器入口
```bash
python run.py
```
- 默认跑在8001接口上

## 数据库函数迁移与测试规范

- 所有函数/触发器/索引/策略必须通过 `supabase/migrations/*.sql` 管理并代码评审。
- 引入/修改函数步骤：
  1. 在本地 DEV 库实现并验证 SQL；
  2. `supabase db diff -f "<描述>"` 生成迁移；
  3. 在 `supabase/tests/db/` 编写 pgtap 测试；
  4. `supabase db reset` 后用 psql 跑全部测试；
  5. `supabase link` + `supabase db push` 推送到环境。
- 运行测试：
  - `psql "postgresql://postgres:postgres@localhost:54322/postgres" -v ON_ERROR_STOP=1 -f supabase/tests/db/*.sql`
- 多环境：
  - 每个环境绑定独立 Supabase 项目，禁止直连生产手改。
