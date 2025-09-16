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
