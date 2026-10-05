import json
import random
import threading
import time
from src.adapters import http
from src.storage import users
from src.providers import codeforces

_problemset_lock = threading.Lock()


def refresh_problemset(only_if_empty=False):
    """下载并事务更新题库；按需初始化时已有题目则跳过，失败保留原数据。"""
    with _problemset_lock:
        with users.connect() as connection:
            if only_if_empty and connection.execute('SELECT 1 FROM codeforces_problems LIMIT 1').fetchone():
                return
        response = http.get('https://codeforces.com/api/problemset.problems')
        response.raise_for_status()
        payload = response.json()
        if payload.get('status') != 'OK':
            raise RuntimeError('Codeforces 题库下载失败')
        problems = {(problem['contestId'], problem['index']): problem['rating']
                    for problem in payload['result']['problems']
                    if problem.get('rating') in range(800, 3600, 100)}
        if not problems:
            raise ValueError('Codeforces 题库为空，请稍后重试')
        with users.connect() as connection:
            connection.execute('DELETE FROM codeforces_problems')
            connection.executemany('INSERT INTO codeforces_problems VALUES (?, ?, ?)',
                                   [(contest_id, index, rating) for (contest_id, index), rating in problems.items()])
        return len(problems)


def select_problem(rating, excluded=()):
    """从指定评分档选择未被排除的题目，返回比赛 ID 和题目索引。"""
    difficulty = min(max(int(rating) // 100 * 100, 800), 3500)
    refresh_problemset(only_if_empty=True)
    with users.connect() as connection:
        candidates = [tuple(row) for row in connection.execute(
            'SELECT contest_id, problem_index FROM codeforces_problems WHERE rating=?', (difficulty,))]
    if not candidates:
        raise ValueError(f'题库中没有 {difficulty} 分题目')
    candidates = [problem for problem in candidates if tuple(problem) not in excluded]
    if not candidates:
        raise ValueError(f'{difficulty} 分题目已全部通过，暂无未通过的题目')
    return random.choice(candidates)


def accepted_submission(handle, contest_id, problem_index, started_at):
    """返回任务开始后目标题目的首次 AC；没有则返回 None。"""
    submissions = codeforces.fetch_submissions(handle)
    accepted = [submission for submission in submissions
                if submission.get('verdict') == 'OK'
                and submission.get('problem', {}).get('contestId') == contest_id
                and submission.get('problem', {}).get('index') == problem_index
                and submission.get('creationTimeSeconds', 0) > started_at]
    return min(accepted, key=lambda submission: submission['creationTimeSeconds']) if accepted else None


def score_change(rating, elapsed_seconds):
    """根据题目评分和耗时计算积分，耗时最低按一秒计算。"""
    scaled_rating = int(rating) * 0.01
    return int(scaled_rating * 60 / (max(elapsed_seconds, 1) / 60) * (scaled_rating / 10) ** 3)


def random_problem(user_id):
    """按 CF 评分分配未 AC 的题目并保存；查询失败不覆盖现有任务。"""
    handle = users.get_user_field(user_id, 'codeforces_handle')
    if not handle:
        return '暂未绑定'
    rating_history = codeforces.api_result('user.rating', handle=handle)
    rating = rating_history[-1]['newRating'] if rating_history else 0
    submissions = codeforces.fetch_submissions(handle)
    solved = {(submission['problem']['contestId'], submission['problem']['index'])
              for submission in submissions if submission.get('verdict') == 'OK'}
    contest_id, problem_index = select_problem(rating, excluded=solved)
    users.update_user_fields(user_id, assigned_problem=json.dumps([contest_id, problem_index]), assigned_at=time.time())
    return f'[CQ:at,qq={user_id}] 你的题目是：\nhttps://codeforces.com/problemset/problem/{contest_id}/{problem_index}'


def judge_problem(user_id):
    """检查首次 AC，事务性加分并清除任务；重复调用不重复加分。"""
    user = users.get_user(user_id)
    if not user or not user.get('codeforces_handle'):
        return '暂未绑定'
    if not user.get('assigned_problem'):
        return f'[CQ:at,qq={user_id}] 暂无题目'
    contest_id, problem_index = json.loads(user['assigned_problem'])
    started_at = user.get('assigned_at') or 0
    submission = accepted_submission(user['codeforces_handle'], contest_id, problem_index, started_at)
    if not submission:
        return f'[CQ:at,qq={user_id}] 未检测到AC提交！'
    elapsed_seconds = submission['creationTimeSeconds'] - started_at
    delta = score_change(submission['problem'].get('rating', 800), elapsed_seconds)
    with users.connect() as connection:
        connection.execute('BEGIN IMMEDIATE')
        current = connection.execute('SELECT assigned_problem, assigned_at, bot_rating FROM users WHERE qq_id=?', (user_id,)).fetchone()
        if current['assigned_problem'] != user['assigned_problem'] or current['assigned_at'] != user['assigned_at']:
            return '题目已结算或已更换，请重新查询'
        old_rating = int(current['bot_rating'] or 0)
        connection.execute('UPDATE users SET bot_rating=COALESCE(bot_rating,0)+?, assigned_problem=NULL, updated_at=CURRENT_TIMESTAMP WHERE qq_id=?', (delta, user_id))
    elapsed_text = time.strftime('%H:%M:%S', time.gmtime(elapsed_seconds))
    return (f'[CQ:at,qq={user_id}] 恭喜你完成了题目！\n耗时：{elapsed_text} rating变化如下：\n'
            f'{user["codeforces_handle"]}：{old_rating} + {delta} = {old_rating + delta}')
