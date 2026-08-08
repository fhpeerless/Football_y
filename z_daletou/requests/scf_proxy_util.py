"""
SCF 代理工具 — 通过腾讯云函数绕过国外IP封锁

GitHub Actions 在国外运行，无法直接访问 sporttery.cn 等国内网站。
此模块通过腾讯云函数(国内IP)转发请求，实现代理访问。

使用方法:
    from scf_proxy_util import proxy_get

    # 完全兼容 requests.get 接口
    resp = proxy_get("https://webapi.sporttery.cn/...", params={...}, headers={...})

环境变量 (由 GitHub Actions 传入):
    SCF_FUNCTION_URL: 腾讯云函数域名 (如 1386835830-xxx.ap-guangzhou.tencentscf.com)
    SCF_TOKEN:        鉴权令牌

当以上环境变量未设置时，自动回退为直接请求，本地调试不受影响。
"""

import requests
import os
import urllib.parse
from typing import Optional

# 从环境变量读取代理配置
SCF_BASE_URL = os.environ.get("SCF_FUNCTION_URL", "")
SCF_TOKEN = os.environ.get("SCF_TOKEN", "")

# 是否启用代理（两个环境变量同时存在时才启用）
USE_PROXY = bool(SCF_BASE_URL and SCF_TOKEN)


def _build_target_url(base_url: str, params: Optional[dict] = None) -> str:
    """构建目标完整 URL（含查询参数）"""
    if not params:
        return base_url
    query_string = urllib.parse.urlencode(params, doseq=True)
    return f"{base_url}?{query_string}"


def proxy_request(method: str, url: str, **kwargs) -> requests.Response:
    """
    通过 SCF 代理发送 HTTP 请求

    参数与 requests.request() 完全兼容。
    当 USE_PROXY=True 时自动走 SCF 代理，否则直接请求。

    处理逻辑:
        1. 构建目标完整 URL（含查询参数）
        2. 用 quote() 编码后拼接到 SCF 代理 URL
        3. 清理 Host 请求头（避免冲突）
        4. 其余参数透传给内层 requests
    """
    if not USE_PROXY:
        return requests.request(method, url, **kwargs)

    # 1. 构建目标完整 URL（含查询参数）
    params = kwargs.pop("params", None)
    target_url = _build_target_url(url, params)

    # 2. 清理请求头中可能冲突的字段
    headers = kwargs.pop("headers", {})
    headers.pop("Host", None)

    # 3. 手动拼接代理 URL（避免 params 方式可能引发的编码问题）
    encoded_target = urllib.parse.quote(target_url, safe='')
    proxy_url = f"https://{SCF_BASE_URL}/?url={encoded_target}&token={urllib.parse.quote(SCF_TOKEN, safe='')}"

    # 4. 发送到 SCF 代理
    return requests.request(method, proxy_url, headers=headers, **kwargs)


def proxy_get(url: str, **kwargs) -> requests.Response:
    """通过 SCF 代理发送 GET 请求"""
    return proxy_request("GET", url, **kwargs)
