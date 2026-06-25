"""SSRF 防护：统一的出站 URL 安全校验。

设计目标：让"代理 / 抓取第三方资源"这类服务器主动外发请求时，
只能访问公网地址，绝不能被诱导去访问内网 / 回环 / 链路本地 / 云元数据等目标。

核心做法（不是简单的字符串前缀黑名单）：
1. 把主机名解析成真实 IP（A/AAAA 全部记录），任意一条命中内网段即拒绝（fail-closed）。
   这样可一次性堵死：
     - 阿里云元数据 100.100.100.200（属于 100.64.0.0/10，is_private=True）
     - AWS/GCP 元数据 169.254.169.254（链路本地）
     - 0.0.0.0、127.0.0.0/8、10/8、172.16/12、192.168/16
     - 十进制/八进制 IP、IPv6、IPv4-mapped IPv6（::ffff:127.0.0.1）
     - 解析到内网 IP 的域名（DNS rebinding 的常见形态）
2. 只允许 http/https。
3. 配合 safe_get() 对每一次重定向跳转重新校验，避免"公网 URL 302 跳内网"绕过。
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

import httpx


class UnsafeURLError(Exception):
    """目标 URL 解析到内网/被拒绝的地址，或重定向次数过多。"""


def _ip_is_blocked(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        # 无法解析为 IP —— fail closed
        return True
    # 解包 IPv4-mapped IPv6（如 ::ffff:127.0.0.1）后再判定
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    # is_global 为 False 即非公网可路由地址：一次性覆盖私网、回环、链路本地、
    # 保留段、组播，以及 100.64.0.0/10 共享地址段（阿里云元数据 100.100.100.200 落在此段，
    # is_private 在部分 Python 版本里对它返回 False，故必须用 is_global 把关）。
    if not ip.is_global:
        return True
    # 兜底：即便某些 Python 版本 is_global 判定有出入，下列标志位也要拦住。
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def is_safe_url(url: str) -> bool:
    """True 仅当 url 是 http/https 且其主机名解析出的所有 IP 都是公网地址。

    解析失败、无主机名、非 http(s)、或任意一条解析记录命中内网段，均返回 False。
    """
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"}:
        return False

    try:
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError:
        # 非法端口等
        return False
    if not host:
        return False

    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError, OSError):
        # 域名无法解析 —— fail closed
        return False

    ips = {info[4][0] for info in infos}
    if not ips:
        return False
    return all(not _ip_is_blocked(ip) for ip in ips)


def safe_get(
    client: httpx.Client,
    url: str,
    *,
    max_redirects: int = 3,
    max_bytes: int | None = None,
) -> httpx.Response:
    """以 SSRF 安全的方式发起 GET：

    - 发起前及每一次重定向跳转后都用 is_safe_url() 重新校验目标；
    - 自行处理重定向（client 级别 follow_redirects 失效），避免绕过；
    - 可选 max_bytes 上限，超出即拒绝，防止超大响应耗尽内存。

    不安全或重定向过多时抛出 UnsafeURLError。
    """
    current = url
    for _ in range(max_redirects + 1):
        if not is_safe_url(current):
            raise UnsafeURLError(current)
        resp = client.get(current, follow_redirects=False)
        if resp.is_redirect and resp.headers.get("location"):
            current = str(resp.url.join(resp.headers["location"]))
            resp.close()
            continue
        if max_bytes is not None:
            declared = resp.headers.get("content-length")
            if declared and declared.isdigit() and int(declared) > max_bytes:
                resp.close()
                raise UnsafeURLError(f"response too large: {url}")
            if len(resp.content) > max_bytes:
                raise UnsafeURLError(f"response too large: {url}")
        return resp
    raise UnsafeURLError(f"too many redirects: {url}")
