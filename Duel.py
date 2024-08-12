import pandas as pd
import json
import random
import requests
import time


def invite(duel_dict: dict, challenger: int, challenged: int, rating: str) -> str:
    """
    发送挑战者（challenger）邀请被挑战者（challenged）进行duel的消息

    参数：
    duel_dict（dict）：存放duel关系的字典
    challenger（int）：挑战者的QQ号
    challenged（int）：被挑战则会的QQ号
    rating：挑战者希望duel的rating

    返回：
    mess（str）：邀请消息
    """
    try:
        df = pd.read_excel('qqid.xlsx')
        idx1 = df['qq'].to_list().index(challenger)  # 挑战者的index
        idx2 = df['qq'].to_list().index(challenged)  # 被挑战者的index
        if df['duel_status'][idx1] and df['duel_status'][idx2]:
            mess = (f"{df['cf'][idx1]} 向 {df['cf'][idx2]} 发起了挑战\n"
                    f"输入/duel accept接受 输入/duel reject拒绝")
            duel_dict[challenger] = [challenged, rating]
        else:
            mess = '存在用户处于duel中'
    except:
        mess = '存在用户未绑定'
    return mess


def accept(duel_dict: dict, challenged: int) -> str:
    """
    被挑战者（challenged）接受挑战，获取题目并发送

    参数：
    duel_dict（dict）：存放duel关系的字典
    challenged（int）：被挑战者QQ号
    """
    for i, j in duel_dict.items():
        if challenged == j[0]:  # 找到了匹配关系,得到duel的所有信息
            challenger = i
            rating = j[1]
            break
    else:
        return f'[CQ:at,qq={challenged}] 你没有正在进行中的duel'
    df = pd.read_excel('qqid.xlsx')
    idx1 = df['qq'].to_list().index(challenger)
    idx2 = df['qq'].to_list().index(challenged)
    df['duel_status'][idx1] = 0
    df['duel_status'][idx2] = 0
    challenger_id = df['cf'][idx1]
    challenged_id = df['cf'][idx2]
    with open('problemset.json', 'r', encoding='utf-8') as f:
        problemset_dict = json.load(f)
    ID, INDEX = random.sample(problemset_dict[rating], 1)[0]  # 题目的id和比赛的index
    problem_url = f"https://codeforces.com/problemset/problem/{ID}/{INDEX}"
    TIME = time.time()  # 接受duel的时间，用于结算
    # 将两者都加入duel关系中
    duel_dict[challenger] = [challenged, ID, INDEX, TIME]
    duel_dict[challenged] = [challenger, ID, INDEX, TIME]
    mess = (f"{challenged_id} 接受了 {challenger_id}的挑战\n"
            f"题目链接：{problem_url}")
    df.to_excel('qqid.xlsx', index=False)
    return mess


def reject(duel_dict: dict, challenged: int) -> str:
    """
    被挑战者（challenged）拒绝了挑战，告知挑战者并

    参数：
    duel_dict（dict）：存放duel关系的字典
    challenged（int）：被挑战者QQ号
    """
    for i, j in duel_dict.items():
        if challenged == j[0]:  # 找到了匹配关系,得到duel的所有信息
            challenger = i
            break
    else:
        return f'[CQ:at,qq={challenged}] 你没有正在进行中的duel'
    duel_dict.pop(challenger, None)
    mess = f"[CQ:at,qq={challenger}] 对方拒绝了你的挑战"
    return mess


def judge(duel_dict: dict, challenged: int) -> str:
    """
    在duel_dict中找出需要结算的一组并记录

    参数：
    duel_dict（dict）：存放duel关系的字典
    challenged（int）：发起结算的用户的QQ号，由于用作结算，因此无需区分挑战关系
    now（float）：结算时的时间戳

    返回：
    mess（str）：这一场单挑的结果
    """
    for i, j in duel_dict.items():
        if challenged == j[0]:  # 找到了匹配关系,结算时删除这一组关系
            challenger = i
            # 比赛id,题目index,接受duel的时间
            ID, INDEX, TIME = duel_dict[challenger][1], duel_dict[challenger][2], duel_dict[challenger][3]
            duel_dict.pop(challenger, None)
            duel_dict.pop(challenged, None)
            break
    df = pd.read_excel('qqid.xlsx')
    idx1 = df['qq'].to_list().index(challenger)  # 挑战者index
    idx2 = df['qq'].to_list().index(challenged)  # 被挑战者index
    cfid1 = df['cf'][idx1]
    cfid2 = df['cf'][idx2]
    url1 = f"https://codeforces.com/api/user.status?handle={cfid1}&count=100"
    url2 = f"https://codeforces.com/api/user.status?handle={cfid2}&count=100"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0"
    }
    # 完成题目的标记
    f1 = f2 = 0

    # 完成题目的时间
    time1 = time2 = float("inf")
    resp1 = requests.get(url1, headers=headers, verify=False).json()
    resp2 = requests.get(url2, headers=headers, verify=False).json()

    # 遍历双方的提交记录（最近提交的100题）
    for i in resp1['result']:
        if i['problem']['contestId'] == ID and i['problem']['index'] == INDEX and i[
            'verdict'] == "OK" and int(i[
                                           'creationTimeSeconds']) > TIME:
            f1 = 1
            time1 = int(i['creationTimeSeconds']) - TIME
            rating1 = int(i['problem']['rating']) * 0.01
            break
    for i in resp2['result']:
        if i['problem']['contestId'] == ID and i['problem']['index'] == INDEX and i[
            'verdict'] == "OK" and int(i[
                                           'creationTimeSeconds']) > TIME:
            f2 = 1
            time2 = int(i['creationTimeSeconds']) - TIME
            rating2 = int(i['problem']['rating']) * 0.01
            break
    if f1 + f2:
        old_rating1 = df['rating'][idx1]
        old_rating2 = df['rating'][idx2]
        if time1 < time2 and f1:
            winner = cfid1
            t = time.strftime("%H:%M:%S", time.gmtime(time1))
            change1 = int(rating1 * 60 / (time1 / 60) * (rating1 / 10) ** 3)
            change2 = -change1
        elif time2 < time1 and f2:
            winner = cfid2
            t = time.strftime("%H:%M:%S", time.gmtime(time2))
            change1 = -int(rating2 * 60 / (time2 / 60) * (rating2 / 10) ** 3)
            change2 = -change1
        df['rating'][idx1] += change1
        df['rating'][idx2] += change2
        mess = (f"{winner} 获胜，耗时：{t}\n"
                f"rating变化如下：\n"
                f"{cfid1}：{old_rating1} + {change1} = {df['rating'][idx1]}\n"
                f"{cfid2}：{old_rating2} + {change2} = {df['rating'][idx2]}")
    else:
        old_rating1 = df['rating'][idx1]
        old_rating2 = df['rating'][idx2]
        change1 = change2 = 0
        mess = (f"无人完成，rating变化如下：\n"
                f"{cfid1}：{old_rating1} + {change1} = {df['rating'][idx1]}\n"
                f"{cfid2}：{old_rating2} + {change2} = {df['rating'][idx2]}")
    df['duel_status'][idx1] = 1
    df['duel_status'][idx2] = 1
    df.to_excel('qqid.xlsx', index=False)
    return mess
def reset(qq_num:int) -> str:
    df = pd.read_excel('qqid.xlsx')
    idx = df['qq'].to_list().index(qq_num)
    df['duel_status'][idx] = 1
    df.to_excel('qqid.xlsx', index=False)
    return '重置成功'