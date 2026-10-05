import json
import re
import time
import requests
from src.settings import get_settings
from .metrics import initial_user_metrics, china_midnight


def page_data(session, url, timeout, **parameters):
    """读取洛谷页面中的当前 JSON 数据；登录失效和结构变化明确报错。"""
    response = session.get(url, params=parameters, timeout=timeout)
    if response.status_code == 401:
        raise ValueError('洛谷 Cookie 已失效或未登录，请更新 bot_settings.json 的 luogu_cookies')
    if response.status_code == 403:
        raise ValueError('洛谷拒绝访问，请检查 Cookie、账号隐私设置或访问限制')
    response.raise_for_status()
    match = re.search(r'<script id="lentille-context" type="application/json">(.*?)</script>', response.text, re.S)
    if not match:
        raise ValueError('洛谷页面结构已变化，无法读取数据')
    payload = json.loads(match[1])
    if payload.get('status', 200) >= 400:
        raise ValueError('洛谷返回访问错误，请检查 Cookie 和账号权限')
    return payload['data']


def fetch_user_metrics(username):
    """携带 JSON 中的 Cookie 查询洛谷评分、提交和北京时间今日指标。"""
    settings = get_settings()
    metrics = initial_user_metrics(username)
    midnight = china_midnight()
    with requests.Session() as session:
        session.cookies.update(settings.luogu_cookies)
        session.headers['User-Agent'] = 'Mozilla/5.0'
        response = session.get('https://www.luogu.com.cn/api/user/search', params={'keyword': username},
                               timeout=settings.request_timeout)
        response.raise_for_status()
        matches = response.json().get('users', [])
        if not matches:
            raise ValueError('未找到洛谷账号')
        user = next((user for user in matches if user.get('name') == username or str(user.get('uid')) == str(username)), matches[0])
        user_id = user['uid']
        records_url = 'https://www.luogu.com.cn/record/list'
        first_page = page_data(session, records_url, settings.request_timeout, user=user_id, page=1)['records']
        metrics['total_submissions'] = first_page['count']
        accepted = page_data(session, records_url, settings.request_timeout, user=user_id, status=12, page=1)['records']
        metrics['accepted_submissions'] = accepted['count']
        profile = page_data(session, f'https://www.luogu.com.cn/user/{user_id}', settings.request_timeout)
        history = profile.get('elo', [])
        metrics['current_rating'] = profile['user'].get('eloValue', 0)
        metrics['highest_rating'] = max([metrics['current_rating'], *(contest['rating'] for contest in history)])
        metrics['rated_contest_count'] = len(history)
        submissions = first_page['result']
        if not submissions:
            return metrics
        latest = submissions[0]
        problem_id = latest['problem']['pid']
        metrics['latest_problem_url'] = f'https://www.luogu.com.cn/problem/{problem_id}'
        metrics['seconds_since_latest_submission'] = max(0, int(time.time() - latest['submitTime']))
        metrics['latest_submission_accepted'] = latest['status'] == 12
        page = 1
        while submissions:
            for submission in submissions:
                if submission['submitTime'] < midnight:
                    break
                metrics['today_submissions'] += 1
                metrics['today_accepted_submissions'] += submission['status'] == 12
            if submissions[-1]['submitTime'] < midnight:
                break
            page += 1
            submissions = page_data(session, records_url, settings.request_timeout, user=user_id, page=page)['records']['result']
        attempts = page_data(session, records_url, settings.request_timeout, user=user_id, pid=problem_id, page=1)['records']
        passed = page_data(session, records_url, settings.request_timeout, user=user_id, pid=problem_id, status=12, page=1)['records']
        metrics['attempts_for_latest_problem'] = attempts['count']
        metrics['accepted_attempts_for_latest_problem'] = passed['count']
    return metrics
