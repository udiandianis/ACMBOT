import time


def china_midnight():
    """返回北京时间当天零点的 Unix 时间戳。"""
    shifted_timestamp = time.time() + 8 * 3600
    return int(shifted_timestamp - shifted_timestamp % 86400 - 8 * 3600)


def initial_user_metrics(username):
    """创建统一统计结构；计数为零、最近提交通过状态为 False。"""
    counters = ('rated_contest_count', 'current_rating', 'highest_rating', 'total_submissions', 'accepted_submissions',
                'today_submissions', 'today_accepted_submissions', 'seconds_since_latest_submission',
                'accepted_attempts_for_latest_problem', 'attempts_for_latest_problem')
    return dict.fromkeys(counters, 0) | {'username': username, 'latest_problem_url': '', 'latest_submission_accepted': False}
