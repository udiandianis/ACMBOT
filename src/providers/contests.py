import html
import re
from datetime import datetime, timezone
from src.adapters import http
from .codeforces import api_result


def fetch_upcoming_contests():
    """从 CF 和 AtCoder 官方站点查询未来比赛，按时间返回最多五场。"""
    upcoming = []
    failures = []
    now = datetime.now(timezone.utc)
    try:
        for contest in api_result('contest.list', gym='false'):
            if contest.get('phase') == 'BEFORE':
                upcoming.append((datetime.fromtimestamp(contest['startTimeSeconds'], timezone.utc),
                                 'Codeforces', contest['name'],
                                 f'https://codeforces.com/contest/{contest["id"]}'))
    except Exception:
        failures.append('Codeforces')
    try:
        response = http.get('https://atcoder.jp/contests/')
        response.raise_for_status()
        block = re.search(r'<div id="contest-table-upcoming".*?</tbody>', response.text, re.S)
        if block is None:
            raise ValueError('AtCoder 比赛页面结构已变化')
        for row in re.findall(r'<tr>(.*?)</tr>', block[0], re.S):
            starts = re.search(r'<time[^>]*>([^<]+)</time>', row)
            contest = re.search(r'<a href="/contests/([^"]+)">([^<]+)</a>', row)
            if starts and contest:
                upcoming.append((datetime.strptime(starts[1], '%Y-%m-%d %H:%M:%S%z'),
                                 'AtCoder', html.unescape(contest[2]),
                                 'https://atcoder.jp/contests/' + contest[1]))
    except Exception:
        failures.append('AtCoder')
    lines = []
    for starts, platform, name, url in sorted(upcoming)[:5]:
        seconds = max(0, int((starts - now).total_seconds()))
        days, seconds = divmod(seconds, 86400)
        hours, seconds = divmod(seconds, 3600)
        lines.append(f'{days}天{hours}小时{seconds // 60}分钟后\n({platform}){name}\n{url}')
    if not lines and failures:
        raise ValueError('比赛查询失败，请稍后重试')
    text = '\n\n'.join(lines) or '暂无近期比赛'
    return text + ('\n\n未能查询：' + '、'.join(failures) if failures else '')
