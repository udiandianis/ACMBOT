import logging
import json
from src.storage import users
from src.providers import codeforces, nowcoder, luogu, atcoder

logger = logging.getLogger(__name__)
PROVIDERS = {'codeforces': codeforces, 'nowcoder': nowcoder, 'luogu': luogu, 'atcoder': atcoder}
FIELD_PLATFORMS = {users.BINDING_FIELDS[platform]: platform for platform in PROVIDERS}


def query(platform, username):
    """查询指定平台账号并格式化结果；抓取失败返回提示。"""
    try:
        metrics = PROVIDERS[platform].fetch_user_metrics(username)
        elapsed = metrics['seconds_since_latest_submission']
        if not metrics['attempts_for_latest_problem']:
            elapsed_text, status = '', 'None'
        else:
            if elapsed < 120:
                elapsed_text = 'just now'
            elif elapsed < 7200:
                elapsed_text = f'{elapsed // 60} minutes ago'
            elif elapsed < 86400:
                elapsed_text = f'{elapsed // 3600} hours ago'
            else:
                elapsed_text = f'{elapsed // 86400} days ago'
            attempts = metrics['attempts_for_latest_problem']
            status = 'Accepted' if metrics['latest_submission_accepted'] else f'Unaccepted in {attempts} tries'
        contest_count = metrics['rated_contest_count']
        return (f'{username}：{metrics["current_rating"]}/{metrics["highest_rating"]}（{contest_count}）\n'
                f'All：{metrics["accepted_submissions"]}/{metrics["total_submissions"]}\n'
                f'Today：{metrics["today_accepted_submissions"]}/{metrics["today_submissions"]}\n'
                f'Latest：{elapsed_text} {status}\n{metrics["latest_problem_url"]}')
    except ValueError as error:
        return str(error)
    except Exception:
        logger.exception('Account query failed for platform=%s', platform)
        return f'{username} 查询失败'


def query_bound(user_id, account_field):
    """查询用户已绑定的平台账号；未绑定时返回提示。"""
    username = users.get_user_field(user_id, account_field)
    return query(FIELD_PLATFORMS[account_field], username) if username else '暂未绑定'


def bind(account_field, account_value, user_id):
    """将姓名或平台账号写入 SQLite；学习通账号密码按列表保存。"""
    if account_field not in users.BINDING_FIELDS.values():
        raise ValueError('不支持的账号类型')
    users.update_user_field(user_id, account_field, json.dumps(account_value.split(), ensure_ascii=False) if account_field == 'chaoxing_credentials' else account_value)
    return '绑定成功'
