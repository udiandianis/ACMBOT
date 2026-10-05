import time
from src.adapters import http
from .metrics import initial_user_metrics, china_midnight


def api_result(action, **parameters):
    """调用 CF 官方 API 并验证状态，返回 result 字段。"""
    response = http.get('https://codeforces.com/api/' + action, params=parameters)
    response.raise_for_status()
    payload = response.json()
    if payload.get('status') != 'OK':
        raise ValueError('Codeforces 查询失败，请检查账号')
    return payload['result']


def fetch_submissions(handle):
    """分页读取 CF 账号的完整提交历史，页间遵循请求间隔。"""
    submissions = []
    offset = 1
    while True:
        page = api_result('user.status', handle=handle, count=10000, **{'from': offset})
        submissions.extend(page)
        if len(page) < 10000:
            return submissions
        offset += len(page)
        time.sleep(2)


def fetch_user_metrics(username):
    """汇总 CF 评分和提交指标；今日统计按北京时间零点计算。"""
    metrics = initial_user_metrics(username)
    rating_history = api_result('user.rating', handle=username)
    if rating_history:
        metrics['rated_contest_count'] = len(rating_history)
        metrics['current_rating'] = rating_history[-1]['newRating']
        metrics['highest_rating'] = max(max(record['oldRating'], record['newRating']) for record in rating_history)
    submissions = fetch_submissions(username)
    if not submissions:
        return metrics
    latest = submissions[0]
    latest_problem = latest['problem']
    metrics['seconds_since_latest_submission'] = max(0, int(time.time() - latest['creationTimeSeconds']))
    metrics['latest_submission_accepted'] = latest.get('verdict') == 'OK'
    metrics['latest_problem_url'] = f'https://codeforces.com/problemset/problem/{latest_problem["contestId"]}/{latest_problem["index"]}'
    midnight = china_midnight()
    for submission in submissions:
        accepted = submission.get('verdict') == 'OK'
        metrics['total_submissions'] += 1
        metrics['accepted_submissions'] += int(accepted)
        if submission['creationTimeSeconds'] >= midnight:
            metrics['today_submissions'] += 1
            metrics['today_accepted_submissions'] += int(accepted)
        problem = submission.get('problem', {})
        if (problem.get('contestId'), problem.get('index')) == (latest_problem['contestId'], latest_problem['index']):
            metrics['attempts_for_latest_problem'] += 1
            metrics['accepted_attempts_for_latest_problem'] += int(accepted)
    return metrics
