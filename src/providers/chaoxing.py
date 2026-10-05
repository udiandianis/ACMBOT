import json
import re
import requests
from src.settings import get_settings
from src.storage import users


def fetch_pending_homework(user_id):
    """使用绑定的学习通账号登录，返回最多五项最先到期的未交作业。"""
    credentials = users.get_user_field(user_id, 'chaoxing_credentials')
    if not credentials:
        return '暂未绑定'
    try:
        account = json.loads(credentials)
        if not isinstance(account, list) or len(account) != 2 or not all(isinstance(value, str) and value for value in account):
            raise ValueError('invalid credentials')
        username, password = account
    except (ValueError, TypeError):
        return '学习通绑定信息格式无效，请重新发送 #bind chaoxing 账号 密码'
    timeout = get_settings().request_timeout
    with requests.Session() as session:
        response = session.post('https://passport2.chaoxing.com/fanyalogin',
            data={'fid': '-1', 'uname': username, 'password': password, 'refer': 'http://i.mooc.chaoxing.com'}, timeout=timeout)
        response.raise_for_status()
        if not response.json().get('status'):
            return '登录失败，请检查学习通账号密码'
        response = session.get('https://mooc1-api.chaoxing.com/work/stu-work', timeout=timeout)
        response.raise_for_status()
    homework = []
    for title, course, remaining in re.findall(r'作业名称(.*?)作业状态未提交所属课程(.*?)剩余时间(.*?)"', response.text):
        if remaining:
            days = re.search(r'(\d+)天', remaining)
            hours = re.search(r'(\d+)小时', remaining)
            minutes = re.search(r'(\d+)分钟', remaining)
            remaining_minutes = (int(days[1]) * 1440 if days else 0) + (int(hours[1]) * 60 if hours else 0) + (int(minutes[1]) if minutes else 0)
            homework.append((remaining_minutes, f'课程名称：{course}\n作业名称：{title}\n剩余时间：{remaining}'))
    homework.sort(key=lambda assignment: assignment[0])
    return '\n\n'.join(description for _, description in homework[:5]) if homework else '暂无未提交作业'
