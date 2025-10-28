import os
import json
import socket
import time
from typing import Tuple, List, Optional, Dict, Any
import dns.resolver
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.dnspod.v20210323 import dnspod_client, models
from loguru import logger
from dotenv import load_dotenv

# ① 把 .env 加载进环境变量
load_dotenv()   # 默认当前目录下的 .env

class DNSClient:
    """
    DNS管理客户端类，用于管理腾讯云DNSPod服务

    这个类封装了DNSPod API的操作，包括创建、更新和查询DNS记录。
    支持从环境变量加载认证信息，并提供便捷的DNS操作方法。

    Environment Variables:
        TENCENTCLOUD_SECRET_ID: 腾讯云Secret ID
        TENCENTCLOUD_SECRET_KEY: 腾讯云Secret Key

    Example:
        # 从环境变量初始化
        dns_client = DNSClient()

        # 创建DNS记录
        dns_client.create_record("example.com", "1.2.3.4", "www")

        # 检查DNS状态
        is_match, ips = dns_client.dns_status("example.com", "www", "1.2.3.4")
    """

    def __init__(self, secret_id: Optional[str] = None, secret_key: Optional[str] = None,
                 region: str = "", endpoint: str = "dnspod.tencentcloudapi.com"):
        """
        初始化DNS客户端

        Args:
            secret_id: 腾讯云Secret ID，如果为None则从环境变量获取
            secret_key: 腾讯云Secret Key，如果为None则从环境变量获取
            region: 区域，默认为空字符串
            endpoint: API端点，默认为DNSPod API
        """
        self.secret_id = secret_id or os.getenv("TENCENTCLOUD_SECRET_ID")
        self.secret_key = secret_key or os.getenv("TENCENTCLOUD_SECRET_KEY")
        self.region = region
        self.endpoint = endpoint
        self._client = None
        self._initialized = False

        logger.info("Initializing DNS client v0.4.0")

    def _init_client(self) -> None:
        """
        初始化腾讯云客户端

        Raises:
            ValueError: 当缺少必需的认证信息时
            TencentCloudSDKException: 当客户端初始化失败时
        """
        if self._initialized and self._client:
            return

        if not self.secret_id or not self.secret_key:
            raise ValueError("TENCENTCLOUD_SECRET_ID and TENCENTCLOUD_SECRET_KEY must be set")

        try:
            # 实例化认证对象
            cred = credential.Credential(self.secret_id, self.secret_key)

            # 实例化HTTP选项
            http_profile = HttpProfile()
            http_profile.endpoint = self.endpoint

            # 实例化客户端选项
            client_profile = ClientProfile()
            client_profile.httpProfile = http_profile

            # 实例化DNSPod客户端
            self._client = dnspod_client.DnspodClient(cred, self.region, client_profile)
            self._initialized = True

            logger.info("DNS client initialized successfully")

        except TencentCloudSDKException as err:
            logger.error(f"Failed to initialize DNS client: {err}")
            raise
        except Exception as err:
            logger.error(f"Unexpected error during DNS client initialization: {err}")
            raise

    @property
    def client(self):
        """获取腾讯云客户端实例，延迟初始化"""
        if not self._initialized:
            self._init_client()
        return self._client

    def validate_credentials(self) -> bool:
        """
        验证认证信息是否有效

        Returns:
            bool: 认证信息是否有效
        """
        if not self.secret_id or not self.secret_key:
            logger.error("Missing DNS credentials")
            return False

        try:
            # 尝试初始化客户端来验证凭证
            self._init_client()
            return True
        except Exception as err:
            logger.error(f"Invalid DNS credentials: {err}")
            return False

    def create_record(self, domain: str, value: str, subdomain: str,
                     record_type: str = "A", record_line: str = "默认",
                     ttl: int = 600) -> bool:
        """
        创建DNS记录

        Args:
            domain: 域名（如 example.com）
            value: 记录值（如 IP地址）
            subdomain: 子域名（如 www 或 @）
            record_type: 记录类型（A、CNAME等）
            record_line: 解析线路（如 默认）
            ttl: TTL值

        Returns:
            bool: 创建成功返回True，失败返回False

        Raises:
            TencentCloudSDKException: API调用失败
            ValueError: 参数验证失败
        """
        if not all([domain, value, subdomain]):
            raise ValueError("Domain, value, and subdomain are required")

        try:
            logger.info(f"Creating DNS record: {subdomain}.{domain} -> {value}")

            # 实例化请求对象
            req = models.CreateRecordRequest()
            params = {
                "Domain": domain,
                "RecordType": record_type,
                "RecordLine": record_line,
                "Value": value,
                "SubDomain": subdomain,
                "TTL": ttl
            }

            req.from_json_string(json.dumps(params))

            # 发送请求
            resp = self.client.CreateRecord(req)

            logger.info(f"DNS record created successfully: {resp.to_json_string()}")
            return True

        except TencentCloudSDKException as err:
            logger.error(f"Failed to create DNS record: {err}")
            raise
        except Exception as err:
            logger.error(f"Unexpected error creating DNS record: {err}")
            raise

    def update_record_ip(self, domain: str, subdomain: str, new_ip: str,
                        record_id: Optional[int] = None, record_type: str = "A",
                        record_line: str = "默认", ttl: int = 600) -> bool:
        """
        更新DNS记录IP地址

        Args:
            domain: 域名
            subdomain: 子域名
            new_ip: 新的IP地址
            record_id: 记录ID，如果为None则自动查询
            record_type: 记录类型
            record_line: 解析线路
            ttl: TTL值

        Returns:
            bool: 更新成功返回True，失败返回False

        Raises:
            TencentCloudSDKException: API调用失败
            ValueError: 参数验证失败
        """
        if not all([domain, subdomain, new_ip]):
            raise ValueError("Domain, subdomain, and new_ip are required")

        try:
            # 如果没有提供record_id，则查询获取
            if record_id is None:
                record_id = self.get_record_id(domain, subdomain, record_type)
                if record_id is None:
                    raise ValueError(f"Record not found for {subdomain}.{domain}")

            logger.info(f"Updating record ID {record_id} for {subdomain}.{domain} to new IP {new_ip}")

            # 实例化请求对象
            req = models.ModifyRecordRequest()
            params = {
                "Domain": domain,
                "RecordType": record_type,
                "RecordLine": record_line,
                "Value": new_ip,
                "RecordId": record_id,
                "SubDomain": subdomain,
                "TTL": ttl
            }

            req.from_json_string(json.dumps(params))

            # 发送请求
            resp = self.client.ModifyRecord(req)

            logger.info(f"DNS record updated successfully: {resp.to_json_string()}")
            return True

        except TencentCloudSDKException as err:
            logger.error(f"Failed to update DNS record: {err}")
            raise
        except Exception as err:
            logger.error(f"Unexpected error updating DNS record: {err}")
            raise

    def get_record_id(self, domain: str, subdomain: str, record_type: str = "A") -> Optional[int]:
        """
        获取DNS记录ID

        Args:
            domain: 域名
            subdomain: 子域名
            record_type: 记录类型

        Returns:
            Optional[int]: 记录ID，如果未找到则返回None

        Raises:
            TencentCloudSDKException: API调用失败
        """
        try:
            logger.info(f"Getting record ID for {subdomain}.{domain}")

            # 实例化请求对象
            req = models.DescribeRecordListRequest()
            params = {
                "Domain": domain,
                "Subdomain": subdomain,
                "RecordType": record_type
            }

            req.from_json_string(json.dumps(params))

            # 发送请求
            resp = self.client.DescribeRecordList(req)

            logger.info(f"Record list response: {resp.to_json_string()}")

            # 检查是否有记录
            if hasattr(resp, 'RecordList') and resp.RecordList:
                return resp.RecordList[0].RecordId
            else:
                logger.warning(f"No record found for {subdomain}.{domain}")
                return None

        except TencentCloudSDKException as err:
            logger.error(f"Failed to get record ID: {err}")
            raise
        except Exception as err:
            logger.error(f"Unexpected error getting record ID: {err}")
            raise

    def dns_status(self, domain: str, subdomain: str, expected_ip: str = "",
                  record_type: str = "A") -> Tuple[bool, List[str]]:
        """
        检查域名记录是否已在公共DNS生效

        使用 dnspython 库直接查询公共DNS服务器，绕过系统DNS缓存，
        确保获取最新的DNS记录。支持重试机制以应对DNS传播延迟。

        Args:
            domain: 顶级域名（如 example.com）
            subdomain: 子域名（如 www 或 @）
            expected_ip: 期望的IP地址（可选）
            record_type: 记录类型（当前仅支持A记录）

        Returns:
            Tuple[bool, List[str]]: (是否匹配期望IP, 当前解析到的IP列表)

        Raises:
            Exception: DNS解析失败（严格模式，所有重试失败后抛出异常）
        """
        # 构建完整域名
        if subdomain in (None, "", "@"):
            fqdn = domain
        else:
            fqdn = f"{subdomain}.{domain}"

        # 从环境变量读取配置，提供默认值
        dns_servers_str = os.getenv("DNS_SERVERS", "114.114.114.114,8.8.8.8")
        dns_servers = [s.strip() for s in dns_servers_str.split(",")]
        query_timeout = int(os.getenv("DNS_QUERY_TIMEOUT", "5"))
        retry_attempts = int(os.getenv("DNS_RETRY_ATTEMPTS", "3"))
        retry_interval = int(os.getenv("DNS_RETRY_INTERVAL", "2"))

        logger.info(f"Checking DNS status for {fqdn} (type: {record_type})")
        logger.info(f"DNS config: servers={dns_servers}, timeout={query_timeout}s, retries={retry_attempts}")

        # 配置 DNS resolver
        resolver = dns.resolver.Resolver()
        resolver.nameservers = dns_servers
        resolver.timeout = query_timeout
        resolver.lifetime = query_timeout

        # 重试逻辑
        last_error = None
        for attempt in range(1, retry_attempts + 1):
            try:
                logger.info(f"DNS query attempt {attempt}/{retry_attempts} for {fqdn}")

                # 执行DNS查询（直接查询公共DNS，绕过系统缓存）
                answers = resolver.resolve(fqdn, record_type)

                # 提取IP地址列表
                ips = [rdata.address for rdata in answers]

                logger.info(f"✅ DNS resolution successful: {fqdn} -> {ips}")

                # 检查是否匹配期望IP
                if expected_ip:
                    is_match = expected_ip in ips
                    if is_match:
                        logger.info(f"✅ DNS verification passed: {fqdn} resolves to expected IP {expected_ip}")
                    else:
                        logger.warning(f"⚠️ DNS mismatch: {fqdn} resolves to {ips}, expected {expected_ip}")
                    return (is_match, ips)
                else:
                    return (bool(ips), ips)

            except dns.resolver.NXDOMAIN as err:
                # 域名不存在，无需重试
                last_error = err
                logger.error(f"❌ DNS resolution failed: domain {fqdn} does not exist (NXDOMAIN)")
                raise Exception(f"Domain {fqdn} does not exist") from err

            except dns.resolver.NoAnswer as err:
                # 查询无结果，无需重试
                last_error = err
                logger.error(f"❌ DNS resolution failed: no {record_type} record for {fqdn}")
                raise Exception(f"No {record_type} record found for {fqdn}") from err

            except (dns.resolver.Timeout, dns.exception.Timeout) as err:
                # 超时错误，可能需要重试
                last_error = err
                logger.warning(f"⚠️ DNS query timeout on attempt {attempt}/{retry_attempts}: {err}")

                if attempt < retry_attempts:
                    logger.info(f"Retrying in {retry_interval} seconds...")
                    time.sleep(retry_interval)
                else:
                    logger.error(f"❌ DNS resolution failed after {retry_attempts} attempts: all queries timed out")
                    raise Exception(f"DNS resolution timeout for {fqdn} after {retry_attempts} attempts") from err

            except Exception as err:
                # 其他错误，可能是网络问题，尝试重试
                last_error = err
                logger.warning(f"⚠️ DNS query error on attempt {attempt}/{retry_attempts}: {err}")

                if attempt < retry_attempts:
                    logger.info(f"Retrying in {retry_interval} seconds...")
                    time.sleep(retry_interval)
                else:
                    logger.error(f"❌ DNS resolution failed after {retry_attempts} attempts: {err}")
                    raise Exception(f"DNS resolution failed for {fqdn}: {err}") from err

        # 理论上不会到达这里，但为了安全起见
        raise Exception(f"DNS resolution failed for {fqdn}: {last_error}")

    def list_records(self, domain: str, record_type: Optional[str] = None,
                    subdomain: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        列出域名下的所有DNS记录

        Args:
            domain: 域名
            record_type: 可选，按记录类型过滤
            subdomain: 可选，按子域名过滤

        Returns:
            List[Dict[str, Any]]: DNS记录列表
        """
        try:
            logger.info(f"Listing records for domain: {domain}")

            req = models.DescribeRecordListRequest()
            params = {"Domain": domain}

            if record_type:
                params["RecordType"] = record_type
            if subdomain:
                params["Subdomain"] = subdomain

            req.from_json_string(json.dumps(params))

            resp = self.client.DescribeRecordList(req)

            records = []
            if hasattr(resp, 'RecordList') and resp.RecordList:
                for record in resp.RecordList:
                    records.append({
                        "record_id": record.RecordId,
                        "name": record.Name,
                        "type": record.Type,
                        "value": record.Value,
                        "ttl": record.TTL,
                        "status": record.Status,
                        "updated_on": record.UpdatedOn
                    })

            logger.info(f"Found {len(records)} records for domain {domain}")
            return records

        except TencentCloudSDKException as err:
            logger.error(f"Failed to list records: {err}")
            raise
        except Exception as err:
            logger.error(f"Unexpected error listing records: {err}")
            raise


# 为了向后兼容，创建全局DNS客户端实例
# 这使得现有代码可以在不修改的情况下继续工作
_global_dns_client = None


def get_global_dns_client() -> DNSClient:
    """
    获取全局DNS客户端实例

    Returns:
        DNSClient: 全局DNS客户端实例
    """
    global _global_dns_client
    if _global_dns_client is None:
        _global_dns_client = DNSClient()
    return _global_dns_client


# 向后兼容的函数接口
def create_record(domain: str, value: str, subdomain: str, record_type: str = "A",
                 record_line: str = "默认", ttl: int = 600) -> bool:
    """
    向后兼容的DNS记录创建函数

    Args:
        domain: 域名
        value: 记录值
        subdomain: 子域名
        record_type: 记录类型
        record_line: 解析线路
        ttl: TTL值

    Returns:
        bool: 创建成功返回True，失败返回False
    """
    client = get_global_dns_client()
    return client.create_record(domain, value, subdomain, record_type, record_line, ttl)


def update_record_ip(domain: str, subdomain: str, new_ip: str, record_id: Optional[int] = None,
                    record_type: str = "A", record_line: str = "默认", ttl: int = 600) -> bool:
    """
    向后兼容的DNS记录更新函数

    Args:
        domain: 域名
        subdomain: 子域名
        new_ip: 新IP地址
        record_id: 记录ID
        record_type: 记录类型
        record_line: 解析线路
        ttl: TTL值

    Returns:
        bool: 更新成功返回True，失败返回False
    """
    client = get_global_dns_client()
    return client.update_record_ip(domain, subdomain, new_ip, record_id, record_type, record_line, ttl)


def get_record_id(domain: str, subdomain: str, record_type: str = "A") -> Optional[int]:
    """
    向后兼容的记录ID查询函数

    Args:
        domain: 域名
        subdomain: 子域名
        record_type: 记录类型

    Returns:
        Optional[int]: 记录ID
    """
    client = get_global_dns_client()
    return client.get_record_id(domain, subdomain, record_type)


def dns_status(domain: str, subdomain: str, expected_ip: str = "", record_type: str = "A") -> Tuple[bool, List[str]]:
    """
    向后兼容的DNS状态检查函数

    Args:
        domain: 域名
        subdomain: 子域名
        expected_ip: 期望IP
        record_type: 记录类型

    Returns:
        Tuple[bool, List[str]]: (是否匹配, IP列表)
    """
    client = get_global_dns_client()
    return client.dns_status(domain, subdomain, expected_ip, record_type)