from fastapi import FastAPI, Request, HTTPException
import json
from dns import update_record_ip
from node_manage import fetch_and_save_tables_csv, NodeProxy



app = FastAPI(title="FastAPI-POST-Receiver", version="1.0")

# 健康检查
@app.get("/health")
def health_check():
    return {"msg": "listener is ok"}

# 监听 POST /notify  接收任意 JSON
@app.post("/notify")
async def notify(request: Request):
    try:
        data = await request.json()      # 获取原始 JSON
        print("收到 JSON:", data)        # 控制台打印
        with open("/root/notify.log", "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")
        return {"code": 0} # 回显给客户端
    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/warning_bandwidth")
async def warning_bandwidth(request: Request):
    try:
        data = await request.json()      # 获取原始 JSON
        print("收到 JSON:", data)        # 控制台打印
        ip=data.get("ip")
        # TODO: 这里可以添加对 ip 的处理逻辑，比如更新 DNS 记录
        # TODO: 还应该添加获得所有现在所有未在线用户的域名列表，然后遍历对所有域名进行修改IP

        # 使用NodeProxy共享SSH连接
        with NodeProxy(ip, 22, 'root', 'id_ed25519') as proxy:
            fetch_and_save_tables_csv(hostname=ip, username='root', key_file='id_ed25519', table_names=['user'], proxy=proxy)


    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail=str(e))
    return {"msg": "warning bandwidth is ok"}

@app.get("/status_normal")
async def status_normal(request: Request):
    try:
        data = await request.json()      # 获取原始 JSON
        print("收到 JSON:", data)        # 控制台打印
        ip=data.get("ip")
        #TODO: 在本地数据库中添加一条记录，表示该节点恢复正常
        return {"code": 0} # 回显给客户端
    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail=str(e))