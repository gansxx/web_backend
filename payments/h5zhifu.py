"""
H5支付网关(h5zhifu)集成

文档：
- H5支付接口：https://h5zhifu.com/doc/api/h5.html
- 签名算法：https://h5zhifu.com/doc/api/sign.html

功能：
- 生成签名：对非空参数按ASCII字典序排序，拼接 key=value&...，再追加 &key=密钥，MD5并大写
- 构造 H5 支付请求数据
- 可选真实发起请求，或 dry-run 模式仅返回将要发送的数据
- 提供简单的回调签名验证函数

注意：
- amount 单位为分(int)
- pay_type: "alipay" | "wechat"
- notify_url 必填
- 真实请求地址：https://open.h5zhifu.com/api/h5 (POST, application/json)
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests


H5_API_URL = "https://open.h5zhifu.com/api/h5"


def _md5_upper(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest().upper()


def sign_payload(data: Dict[str, Any], secret_key: str) -> str:
    """生成签名。

    规则：
    - 过滤掉值为空(空字符串/None)的键
    - 按参数名ASCII字典序排序
    - 使用 key=value&... 形式拼接原始值（不要URL转义）
    - 末尾拼接 &key=密钥
    - 对拼接字符串取MD5并转大写
    """
    # 过滤为空的参数（None 或 空字符串）
    filtered = {k: v for k, v in data.items() if v is not None and v != ""}
    # 按键排序
    items = sorted(filtered.items(), key=lambda kv: kv[0])
    # 使用原始值拼接
    base = "&".join(f"{k}={v}" for k, v in items)
    to_sign = f"{base}&key={secret_key}" if base else f"key={secret_key}"
    return _md5_upper(to_sign)


def verify_signature(data_with_sign: Dict[str, Any], secret_key: str) -> bool:
    """验证签名，data_with_sign 需包含 sign 字段。"""
    provided = data_with_sign.get("sign")
    if not provided:
        return False
    data = {k: v for k, v in data_with_sign.items() if k != "sign"}
    calc = sign_payload(data, secret_key)
    return calc == str(provided)


@dataclass
class H5PayRequest:
    app_id: int
    out_trade_no: str
    description: str
    pay_type: str  # "alipay" | "wechat"
    amount: int  # 单位分
    notify_url: str
    attach: Optional[str] = None

    def to_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "app_id": self.app_id,
            "out_trade_no": self.out_trade_no,
            "description": self.description,
            "pay_type": self.pay_type,
            "amount": self.amount,
            "notify_url": self.notify_url,
        }
        if self.attach is not None:
            payload["attach"] = self.attach
        return payload


def create_h5_order(
    req: H5PayRequest,
    secret_key: str,
    *,
    dry_run: bool = True,
    timeout: float = 10.0,
) -> Dict[str, Any]:
    """创建 H5 订单。

    参数：
    - req: 请求数据
    - secret_key: 通信密钥
    - dry_run: 为 True 则不发起网络请求，仅返回将要发送的 payload
    - timeout: 请求超时时间

    返回：
    - dry_run=True: { "request_url": str, "payload": dict }
    - dry_run=False: 返回三元组字典 { "status_code": int, "response": dict, "raw_text": str }
    """
    payload = req.to_payload()
    payload["sign"] = sign_payload(payload, secret_key)

    if dry_run:
        return {"request_url": H5_API_URL, "payload": payload}

    headers = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    resp = requests.post(H5_API_URL, data=json.dumps(payload), headers=headers, timeout=timeout)
    try:
        body = resp.json()
    except Exception:
        body = None
    return {"status_code": resp.status_code, "response": body, "raw_text": resp.text}


if __name__ == "__main__":
    # 示例：使用环境变量或直接填写测试参数。
    # 注意：请替换为你自己的 app_id、secret_key、notify_url。
    import os

    app_id = int(os.getenv("H5ZHIFU_APP_ID", "12345"))
    secret_key = os.getenv("H5ZHIFU_SECRET_KEY", "xxxxxxxxxxx")

    demo = H5PayRequest(
        app_id=app_id,
        out_trade_no=os.getenv("OUT_TRADE_NO", "ORDER1234567890"),
        description=os.getenv("DESCRIPTION", "Test product"),
        pay_type=os.getenv("PAY_TYPE", "alipay"),
        amount=int(os.getenv("AMOUNT", "1")),  # 1 分
        notify_url=os.getenv("NOTIFY_URL", "https://example.com/notify"),
        attach=os.getenv("ATTACH", None),
    )

    result = create_h5_order(demo, secret_key=secret_key, dry_run=True)
    print("[DRY-RUN] POST", result["request_url"]) 
    print(json.dumps(result["payload"], ensure_ascii=False, indent=2))
