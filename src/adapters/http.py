"""为平台查询提供带超时限制的请求。"""
import requests
from src.settings import get_settings


def get(url, **kwargs):
    """发送 GET 请求；未指定超时时使用 JSON 中的 request_timeout。"""
    kwargs.setdefault('timeout', get_settings().request_timeout)
    return requests.get(url, **kwargs)


def post(url, **kwargs):
    """发送 POST 请求；未指定超时时使用 JSON 中的 request_timeout。"""
    kwargs.setdefault('timeout', get_settings().request_timeout)
    return requests.post(url, **kwargs)
