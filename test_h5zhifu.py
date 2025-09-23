import json

from payments.h5zhifu import H5PayRequest, sign_payload, verify_signature, create_h5_order


def test_sign_algorithm_matches_docs_example():
    data = {
        "app_id": 12345,
        "amount": 1,
        "out_trade_no": "123456789",
    }
    key = "xxxxxxxxx"
    s = sign_payload(data, key)
    # 依据文档示例：amount=1&app_id=12345&out_trade_no=123456789&key=xxxxxxxxx
    # MD5 大写
    import hashlib

    expected = hashlib.md5(
        "amount=1&app_id=12345&out_trade_no=123456789&key=xxxxxxxxx".encode("utf-8")
    ).hexdigest().upper()
    assert s == expected


def test_verify_signature():
    payload = {
        "app_id": 111,
        "out_trade_no": "ORDER1",
        "description": "desc",
        "pay_type": "alipay",
        "amount": 2,
        "notify_url": "https://example.com/notify",
        "attach": "abc",
    }
    key = "key123"
    sig = sign_payload(payload, key)
    payload_with_sign = dict(payload, sign=sig)
    assert verify_signature(payload_with_sign, key) is True
    assert verify_signature(dict(payload_with_sign, sign="WRONG"), key) is False


def test_create_h5_order_dry_run_structure():
    req = H5PayRequest(
        app_id=1,
        out_trade_no="ORDER-001",
        description="Test",
        pay_type="alipay",
        amount=1,
        notify_url="https://example.com/notify",
        attach=None,
    )
    result = create_h5_order(req, secret_key="k", dry_run=True)
    assert "request_url" in result and "payload" in result
    p = result["payload"]
    # 必须字段存在
    for k in [
        "app_id",
        "out_trade_no",
        "description",
        "pay_type",
        "amount",
        "notify_url",
        "sign",
    ]:
        assert k in p
    # attach 为 None 时不应出现
    assert "attach" not in p
    # sign 非空
    assert isinstance(p["sign"], str) and len(p["sign"]) > 0
