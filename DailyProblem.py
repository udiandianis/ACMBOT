import time

import pandas as pd
import json
import random
import requests


daily_problem_list = [
    'https://codeforces.com/problemset/problem/1654/A',
    'https://codeforces.com/problemset/problem/864/A',
    'https://codeforces.com/problemset/problem/779/C'
]
ACED_SET = set()

def randomProblem(rating: int) -> str:
    """
    获取随机cf题目链接
    :param rating: rating
    :return:
    """
    with open('problemset.json', 'r', encoding='utf-8') as f:
        problemset_dict = json.load(f)
    print('已找到problemset.json,正在获取题目信息...')
    # 根据当前的rating选择题目，最低800分，最高3500分
    target_rating = str(min(max(rating - rating % 100, 800), 3500))
    ID, INDEX = random.sample(problemset_dict[target_rating], 1)[0]  # 题目的id和比赛的index
    problem_url = f"https://codeforces.com/problemset/problem/{ID}/{INDEX}"
    return problem_url


def daliyProblemJudge():
    """
    每日题目循环结算
    :return: none
    """
    global ACED_SET
    print('daliyProblemJudging...')
    df = pd.read_excel('qqid.xlsx')
    cf_dict = df.set_index('cf')['qq'].to_dict()
    cid_list = [(i.split('/')[-2], i.split('/')[-1]) for i in daily_problem_list]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0"
    }
    mess = ''
    aced_set = set()
    for ID, INDEX in cid_list:
        url = f"https://codeforces.com/api/contest.status?contestId={ID}&from=1&count=100"
        resp = requests.get(url, headers=headers, verify=False).json()
        if resp['status'] == 'OK':
            for i in resp['result']:
                if (i['problem']['index'] == INDEX
                        and i['author']['members'][0]['handle'] in cf_dict
                        and i.get('verdict', '') == 'OK'):
                    if i['id'] not in ACED_SET:
                        mess += f"{i['author']['members'][0]['handle']} 通过了每日题目 CF{ID}{INDEX}\n"
                    aced_set.add(i['id'])
    ACED_SET = aced_set
    if mess:
        return mess.rstrip()


def dailyProblem(n: bool = False) -> str:
    """
    生成每日题目，难度：800,1000,1200
    自动进行循环结算
    :return: message
    """
    global daily_problem_list
    if not daily_problem_list or n:
        daily_problem_list = [
            randomProblem(800),
            randomProblem(1000),
            randomProblem(1200)
        ]
    return '新生今日题目：\n800: ' + \
        daily_problem_list[0] + '\n1000: ' +\
        daily_problem_list[1] + '\n1200: ' +\
        daily_problem_list[2]


if __name__ == '__main__':
    print(dailyProblem())