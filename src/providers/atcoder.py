import threading
import time
from src.adapters import http
from .metrics import initial_user_metrics, china_midnight

_api_lock = threading.Lock()
_last_api_request = 0.0


def fetch_submissions(username):
    """分页读取 AtCoder Problems 的提交；按接口要求控制请求间隔。"""
    global _last_api_request
    submissions = []
    cursor = 0
    while True:
        with _api_lock:
            delay = 1.05 - (time.monotonic() - _last_api_request)
            if delay > 0:
                time.sleep(delay)
            try:
                response = http.get('https://kenkoooo.com/atcoder/atcoder-api/v3/user/submissions',
                                    params={'user': username, 'from_second': cursor})
                response.raise_for_status()
                page = response.json()
            finally:
                _last_api_request = time.monotonic()
        if not isinstance(page, list):
            raise ValueError('AtCoder Problems 返回了无效提交数据')
        submissions.extend(page)
        if len(page) < 500:
            break
        next_cursor = max(submission['epoch_second'] for submission in page) + 1
        if next_cursor <= cursor:
            raise ValueError('AtCoder 提交分页没有推进')
        cursor = next_cursor
    return submissions


def fetch_user_metrics(username):
    """汇总完整提交中的 AC 次数和今日指标，并查询官方评分历史。"""
    metrics = initial_user_metrics(username)
    submissions = fetch_submissions(username)
    metrics['total_submissions'] = len(submissions)
    metrics['accepted_submissions'] = sum(submission['result'] == 'AC' for submission in submissions)
    today = [submission for submission in submissions if submission['epoch_second'] >= china_midnight()]
    metrics['today_submissions'] = len(today)
    metrics['today_accepted_submissions'] = sum(submission['result'] == 'AC' for submission in today)
    if submissions:
        latest = max(submissions, key=lambda submission: submission['epoch_second'])
        related = [submission for submission in submissions if submission['problem_id'] == latest['problem_id']]
        metrics['latest_problem_url'] = f'https://atcoder.jp/contests/{latest["contest_id"]}/tasks/{latest["problem_id"]}'
        metrics['latest_submission_accepted'] = latest['result'] == 'AC'
        metrics['seconds_since_latest_submission'] = max(0, int(time.time() - latest['epoch_second']))
        metrics['attempts_for_latest_problem'] = len(related)
        metrics['accepted_attempts_for_latest_problem'] = sum(submission['result'] == 'AC' for submission in related)
    response = http.get(f'https://atcoder.jp/users/{username}/history/json')
    response.raise_for_status()
    rated_history = [contest for contest in response.json() if contest.get('IsRated')]
    metrics['rated_contest_count'] = len(rated_history)
    if rated_history:
        metrics['current_rating'] = rated_history[-1]['NewRating']
        metrics['highest_rating'] = max(contest['NewRating'] for contest in rated_history)
    return metrics
