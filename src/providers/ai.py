import html
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def answer(question, settings, provider):
    """使用 GPT 或 DeepSeek 的独立配置回答，未配置密钥时返回提示。"""
    if provider not in ('gpt', 'deepseek'):
        raise ValueError('未知 AI 服务')
    api_key = getattr(settings, provider + '_api_key')
    if not api_key:
        return 'AI 服务尚未配置 API Key'
    url = getattr(settings, provider + '_base_url').rstrip('/') + '/chat/completions'
    with requests.Session() as session:
        retry = Retry(total=1, backoff_factor=0.5, allowed_methods={'POST'},
                      status_forcelist=(408, 409, 429, 500, 502, 503, 504), raise_on_status=False)
        session.mount('https://', HTTPAdapter(max_retries=retry))
        session.mount('http://', HTTPAdapter(max_retries=retry))
        response = session.post(url, headers={'Authorization': f'Bearer {api_key}'},
            json={'model': getattr(settings, provider + '_model'),
                  'messages': [{'role': 'user', 'content': html.unescape(question) + '切记需要中文回答'}]},
            timeout=settings.request_timeout)
        response.raise_for_status()
        result = response.json()
    choices = result.get('choices') or []
    if not choices:
        return 'AI 未返回内容'
    return choices[0]['message'].get('content') or 'AI 未返回内容'
