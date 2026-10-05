from .metrics import initial_user_metrics
from src.adapters import http as requests
import time
from datetime import datetime, timezone, timedelta
import re

def fetch_user_metrics(username: str) -> dict:
    """查询牛客评分和提交指标；今日统计基于最近 200 条提交。"""
    user_data = initial_user_metrics(username)
    now = time.time() + 8 * 3600
    start_time = now - now % 86400 - 8 * 3600
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0'}
    user_search_url = f'https://ac.nowcoder.com/acm/contest/rating-index?searchUserName={username}'
    user_search_response = requests.get(user_search_url, headers=headers).text
    user_id = re.compile('tr data-isFollowedByHost=" 0 " data-uid="(.*)">').findall(user_search_response)[0]
    practice_url = f'https://ac.nowcoder.com/acm/contest/profile/{user_id}/practice-coding?&pageSize=200'
    rating_url = f'https://ac.nowcoder.com/acm/contest/rating-history?token=&uid={user_id}'
    rating_response = requests.get(rating_url, headers=headers).json()
    user_data['current_rating'] = int(rating_response['data'][-1]['rating']) if rating_response.get('data') else 0
    try:
        for record in rating_response['data']:
            user_data['highest_rating'] = max(user_data['highest_rating'], int(record['rating']))
            user_data['rated_contest_count'] += 1
    except:
        pass
    practice_records = requests.get(practice_url, headers=headers).text
    practice_data = re.compile('<div class="state-num">(.*?)</div>', re.S).findall(practice_records)
    user_data['total_submissions'] = int(practice_data[2])
    user_data['accepted_submissions'] = int(practice_data[1])
    practice_records = re.compile('<td><a href="/acm/problem/(.*?)" target="_blank">.*?<td><span class="match-score.">(.*?)</span></td>(.*?)</tr>', re.S).findall(practice_records)
    for record in practice_records:
        score = record[1]
        submit_time = ' '.join(re.compile('<td>(.*)</td>').findall(record[2])[-1].split())
        if datetime.strptime(submit_time, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone(timedelta(hours=8))).timestamp() >= start_time:
            user_data['today_submissions'] += 1
            if score == '100':
                user_data['today_accepted_submissions'] += 1
    if not practice_records:
        return user_data
    problem_id = practice_records[0][0]
    user_data['latest_problem_url'] = f'https://ac.nowcoder.com/acm/problem/{problem_id}'
    problem_url = f'https://ac.nowcoder.com/acm/contest/profile/{user_id}/practice-coding?pageSize=200&search={problem_id}'
    problem_records = requests.get(problem_url, headers=headers).text
    problem_records = re.compile('<span class="match-score.">(.*?)</span></td>(.*?)</tr>', re.S).findall(problem_records)
    for record in problem_records:
        score = record[0]
        user_data['attempts_for_latest_problem'] += 1
        if score == '100':
            user_data['accepted_attempts_for_latest_problem'] += 1
    user_data['latest_submission_accepted'] = practice_records[0][1] == '100'
    latest_time = re.compile('<td>(.*)</td>').findall(practice_records[0][2])[-1]
    user_data['seconds_since_latest_submission'] = int(time.time() - datetime.strptime(latest_time.strip(), '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone(timedelta(hours=8))).timestamp())
    return user_data
