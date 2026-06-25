"""SSRF 守卫单元测试：is_safe_url + safe_get。

DNS 解析通过 monkeypatch socket.getaddrinfo 控制，保证离线确定性。
"""

import socket

import httpx
import pytest

import app.core.url_security as url_security
from app.core.url_security import UnsafeURLError, is_safe_url, safe_get


def _stub_dns(monkeypatch, mapping: dict[str, str]) -> None:
    """mapping: host -> ip。未在 mapping 中的主机抛 gaierror（模拟解析失败）。"""

    def fake(host, port, *args, **kwargs):
        if host in mapping:
            ip = mapping[host]
            family = socket.AF_INET6 if ":" in ip else socket.AF_INET
            return [(family, socket.SOCK_STREAM, 6, "", (ip, port or 80))]
        raise socket.gaierror("name resolution failed")

    monkeypatch.setattr(url_security.socket, "getaddrinfo", fake)


# ---------------------------------------------------------------- scheme / shape

def test_rejects_non_http_scheme(monkeypatch):
    _stub_dns(monkeypatch, {"example.com": "93.184.216.34"})
    assert is_safe_url("ftp://example.com/x") is False
    assert is_safe_url("file:///etc/passwd") is False
    assert is_safe_url("gopher://example.com/x") is False
    assert is_safe_url("") is False
    assert is_safe_url("not a url") is False


def test_allows_public_host(monkeypatch):
    _stub_dns(monkeypatch, {"example.com": "93.184.216.34"})
    assert is_safe_url("https://example.com/a.png") is True
    assert is_safe_url("http://example.com:8080/a.png") is True


# ----------------------------------------------------------- internal IP literals

@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/x",
        "http://0.0.0.0/x",
        "http://10.0.0.5/x",
        "http://192.168.1.2/x",
        "http://172.16.0.1/x",
        "http://172.31.255.254/x",
        "http://169.254.169.254/x",     # AWS/GCP 元数据
        "http://169.254.169.254/latest/meta-data/iam/security-credentials/",
        "http://100.100.100.200/latest/meta-data/",  # 阿里云元数据（100.64/10）
        "http://100.64.0.1/x",
        "http://[::1]/x",               # IPv6 回环
        "http://[::ffff:127.0.0.1]/x",  # IPv4-mapped 回环
    ],
)
def test_blocks_internal_ip_literals(url):
    assert is_safe_url(url) is False


def test_blocks_decimal_ip_encoding(monkeypatch):
    # 2130706433 == 127.0.0.1：解析失败则 fail-closed，解析成功则命中回环，二者皆拒
    _stub_dns(monkeypatch, {})
    assert is_safe_url("http://2130706433/x") is False


# --------------------------------------------------- DNS rebinding / 主机名打内网

def test_blocks_hostname_resolving_to_internal(monkeypatch):
    _stub_dns(monkeypatch, {"evil.example": "169.254.169.254"})
    assert is_safe_url("http://evil.example/x") is False


def test_blocks_hostname_resolving_to_aliyun_metadata(monkeypatch):
    _stub_dns(monkeypatch, {"rebind.example": "100.100.100.200"})
    assert is_safe_url("http://rebind.example/latest/meta-data/") is False


def test_blocks_when_any_record_internal(monkeypatch):
    # 一条公网 + 一条内网 A 记录 → 拒绝（要求全部公网）
    def fake(host, port, *args, **kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port or 80)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.9", port or 80)),
        ]

    monkeypatch.setattr(url_security.socket, "getaddrinfo", fake)
    assert is_safe_url("http://split.example/x") is False


def test_fails_closed_on_resolution_error(monkeypatch):
    _stub_dns(monkeypatch, {})
    assert is_safe_url("http://nonexistent.invalid/x") is False


# ----------------------------------------------------------- safe_get 重定向校验

class _Resp:
    def __init__(self, *, is_redirect=False, location=None, content=b"img",
                 url="http://x/", content_type="image/png"):
        self.is_redirect = is_redirect
        self.headers = {"content-type": content_type}
        if location:
            self.headers["location"] = location
        self.content = content
        self.url = httpx.URL(url)

    def close(self):
        pass

    def raise_for_status(self):
        pass


class _ScriptedClient:
    def __init__(self, script):
        self.script = list(script)
        self.requested: list[str] = []

    def get(self, url, follow_redirects=False):
        self.requested.append(url)
        return self.script.pop(0)


def test_safe_get_blocks_redirect_to_internal(monkeypatch):
    _stub_dns(monkeypatch, {"good.example": "93.184.216.34", "bad.example": "169.254.169.254"})
    client = _ScriptedClient([_Resp(is_redirect=True, location="http://bad.example/meta")])
    with pytest.raises(UnsafeURLError):
        safe_get(client, "http://good.example/a.png")


def test_safe_get_follows_safe_redirect(monkeypatch):
    _stub_dns(monkeypatch, {"good.example": "93.184.216.34", "cdn.example": "93.184.216.34"})
    client = _ScriptedClient([
        _Resp(is_redirect=True, location="http://cdn.example/final.png"),
        _Resp(content=b"PNGDATA"),
    ])
    resp = safe_get(client, "http://good.example/a.png")
    assert resp.content == b"PNGDATA"
    assert client.requested == ["http://good.example/a.png", "http://cdn.example/final.png"]


def test_safe_get_rejects_initial_internal(monkeypatch):
    _stub_dns(monkeypatch, {})
    client = _ScriptedClient([_Resp()])
    with pytest.raises(UnsafeURLError):
        safe_get(client, "http://169.254.169.254/latest/meta-data/")
    assert client.requested == []  # 校验在发请求之前


def test_safe_get_rejects_oversized(monkeypatch):
    _stub_dns(monkeypatch, {"good.example": "93.184.216.34"})
    big = _Resp(content=b"x" * 100)
    big.headers["content-length"] = "100"
    client = _ScriptedClient([big])
    with pytest.raises(UnsafeURLError):
        safe_get(client, "http://good.example/a.png", max_bytes=10)


def test_safe_get_too_many_redirects(monkeypatch):
    _stub_dns(monkeypatch, {"a.example": "93.184.216.34"})
    client = _ScriptedClient([
        _Resp(is_redirect=True, location="http://a.example/1"),
        _Resp(is_redirect=True, location="http://a.example/2"),
        _Resp(is_redirect=True, location="http://a.example/3"),
        _Resp(is_redirect=True, location="http://a.example/4"),
        _Resp(is_redirect=True, location="http://a.example/5"),
    ])
    with pytest.raises(UnsafeURLError):
        safe_get(client, "http://a.example/0", max_redirects=3)
