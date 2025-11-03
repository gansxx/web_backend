from cloudflare import Cloudflare
import json
from dotenv import load_dotenv
import os
load_dotenv()
with open('ecs_ip_preview.json') as f:
    ip = json.load(f)
print("Updating DNS to: ", ip)

# 使用 API Token
cf = Cloudflare(api_token=os.getenv('cloudflare_dns_key'))
#还要在这里加入terrafrom创建的机器的ip地址
# 配置
zone_name = "selfgo.asia"
record_name : str = "preview.selfgo.asia"
record_ip = ip

# 获取 zone_id
zones = cf.zones.list(name=str(zone_name))
zone_id = zones.result[0].id

# 查询 DNS 记录
records = cf.dns.records.list(zone_id=zone_id, name=str(record_name))#type: ignore

if records.result:
    # 已存在 → 更新
    record_id = records.result[0].id
    result = cf.dns.records.update(
        zone_id=zone_id,
        dns_record_id=record_id,
        type="A",
        name=str(record_name),
        content=record_ip,
        ttl=120,
        proxied=False,
    )
    print("🔄 Updated:", result)
else:
    # 不存在 → 创建
    result = cf.dns.records.create(
        zone_id=zone_id,
        type="A",
        name=str(record_name),
        content=record_ip,
        ttl=120,
        proxied=False,
    )
    print("✅ Created:", result)

