import os
import json
import types
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.dnspod.v20210323 import dnspod_client, models
from loguru import logger
logger.info("Initializing DNS client,and it's v0.3.2")
try:
    # 实例化一个认证对象，入参需要传入腾讯云账户 SecretId 和 SecretKey，此处还需注意密钥对的保密
    # 代码泄露可能会导致 SecretId 和 SecretKey 泄露，并威胁账号下所有资源的安全性
    # 以下代码示例仅供参考，建议采用更安全的方式来使用密钥
    # 请参见：https://cloud.tencent.com/document/product/1278/85305
    # 密钥可前往官网控制台 https://console.cloud.tencent.com/cam/capi 进行获取
    cred = credential.Credential(os.getenv("TENCENTCLOUD_SECRET_ID"), os.getenv("TENCENTCLOUD_SECRET_KEY"))
    # 使用临时密钥示例
    # cred = credential.Credential("SecretId", "SecretKey", "Token")
    # 实例化一个http选项，可选的，没有特殊需求可以跳过
    httpProfile = HttpProfile()
    httpProfile.endpoint = "dnspod.tencentcloudapi.com"

    # 实例化一个client选项，可选的，没有特殊需求可以跳过
    clientProfile = ClientProfile()
    clientProfile.httpProfile = httpProfile
    # 实例化要请求产品的client对象,clientProfile是可选的
    client = dnspod_client.DnspodClient(cred, "", clientProfile)

except TencentCloudSDKException as err:
    logger.error(err)
    logger.info("初始化失败")

def create_record(domain, Value, SubDomain, RecordType="A", RecordLine="默认", TTL=600):
    # 实例化一个请求对象,每个接口都会对应一个request对象
    req = models.CreateRecordRequest()
    params = {
        "Domain": domain,
        "RecordType": RecordType,
        "RecordLine": RecordLine,
        "Value": Value,
        "SubDomain": SubDomain,
        "TTL": TTL
    }
    try:
        req.from_json_string(json.dumps(params))

        # 返回的resp是一个CreateRecordResponse的实例，与请求对象对应
        resp = client.CreateRecord(req)
        # 输出json格式的字符串回包
        logger.info(resp.to_json_string())
    except TencentCloudSDKException as err:
        logger.error(err)

def update_record_ip(domain, SubDomain, new_ip, record_id=None, RecordType="A", RecordLine="默认", TTL=600):
    # 实例化一个请求对象,每个接口都会对应一个request对象
    if record_id is None:
        try:
            record_id = get_record_id(domain, SubDomain, RecordType)
        except Exception as e:
            logger.error(f"Failed to get record ID: {e}")
            return

     # 实例化一个请求对象,每个接口都会对应一个request对象
    req = models.ModifyRecordRequest()
    params = {
        "Domain": domain,
        "RecordType": RecordType,
        "RecordLine": RecordLine,
        "Value": new_ip,
        "RecordId": record_id,
        "SubDomain": SubDomain,
        "TTL": TTL
    }
    
    try:
        logger.info(f"Updating record ID {record_id} for {SubDomain}.{domain} to new IP {new_ip}")
        
        req.from_json_string(json.dumps(params))
        # 返回的resp是一个UpdateRecordResponse的实例，与请求对象对应
        # logger.info(f"Update response: {resp.to_json_string()}")
        resp = client.ModifyRecord(req)
        # 输出json格式的字符串回包
        logger.info(resp.to_json_string())
    except TencentCloudSDKException as err:
        logger.error(err)

def get_record_id(domain, Subdomain, RecordType="A"):
    # 实例化一个请求对象,每个接口都会对应一个request对象
    try:
        req = models.DescribeRecordListRequest()
        params = {
            "Domain": domain,
            "Subdomain": Subdomain,
            "RecordType": RecordType
        }
        req.from_json_string(json.dumps(params))

        # 返回的resp是一个DescribeRecordListResponse的实例，与请求对象对应
        resp = client.DescribeRecordList(req)
        # 输出json格式的字符串回包
        logger.info(resp.to_json_string())
        return resp.RecordList[0].RecordId
    except TencentCloudSDKException as err:
        logger.error(err)
        logger.info("查询失败")


def dns_status(domain, SubDomain, expected_ip, RecordType="A"):
    """
    检查域名记录是否已在公共 DNS 生效（是否解析到 expected_ip）。

    返回 (bool, list) -> (是否匹配, 当前解析到的 IP 列表)

    参数:
    - domain: 顶级域名，例如 'example.com'
    - SubDomain: 子域名，例如 'www' 或 '@' 或 ''
    - expected_ip: 期望的 IP 地址字符串，例如 '1.2.3.4'
    - RecordType: 当前仅支持 'A'，保留参数兼容性
    """
    import socket

    if SubDomain in (None, "", "@"):
        fqdn = domain
    else:
        fqdn = f"{SubDomain}.{domain}"

    try:
        # 使用系统解析器解析域名，获取所有地址信息
        infos = socket.getaddrinfo(fqdn, None)
        # 从 address info 中抽取 IP
        ips = []
        for ai in infos:
            try:
                ip = ai[4][0]
                if ip not in ips:
                    ips.append(ip)
            except Exception:
                continue

        logger.info("dns_status: %s -> %s" % (fqdn, ips))
        return (expected_ip in ips, ips)
    except Exception as e:
        logger.error(e)
        return (False, [])
        