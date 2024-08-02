from datetime import datetime
import numpy as np
from flask import Flask, request
import requests
import warnings
import re
import os
import random
import json
import time
import pandas as pd
import CodeforcesQuery
import NewcoderQuery
import LuoguQuery
import Collector
import Duel
import RecentAcm
import DailyProblem

warnings.filterwarnings("ignore")
app = Flask(__name__)
duel_dict = {}


@app.route('/', methods=['POST'])
def handler() -> str:  # 消息处理
    """
    监听消息并对消息进行响应

    返回：
    str：响应状态
    """
    if request.method == 'POST':
        data = request.json
        res = ''  # 初始化响应为空
        print(data)  # 监听机器人接收的所有消息json
        print(duel_dict)

        # 新人入群
        if 'notice_type' in data and data['notice_type'] == 'group_increase' and data['group_id'] in [547460746]:
            requests.get(f"http://127.0.0.1:5020/send_group_msg",
                         params={"group_id": data['group_id'],
                                 "message": f"[CQ:at,qq={data['user_id']}] 欢迎加入之江ACM招新群！\n"
                                            f"1、新进群的同学请进入洛谷注册账号（luogu.com），并在文档填写自己的信息（https://a.d4t.cn/M5hwu3）\n"
                                            f"2、相关入门资料群公告和群文件自取\n"
                                            f"3、如有任何疑问可以在群里直接提问或私聊管理员"})
        if 'problemset.json' not in os.listdir(os.path.dirname(__file__)):  # 不存在problemset.json就重新爬取
            Download()
        if 'message_type' in data and data['message_type'] == 'group':  # 在群聊里发消息
            # 打印此条消息的基本信息
            print(f"发消息者的QQ：{data['sender']['user_id']}', {type(data['sender']['user_id'])}")
            print(f"发消息者的昵称：{data['sender']['nickname']}', {type(data['sender']['nickname'])}")
            print(f"发消息者的内容：{data['message']}', {type(data['message'])}")

            # 筛选出可能调用NameQuery的data
            data1 = re.compile(r'^#([a-zA-z]{2})\s*(.*)').findall(data['message'])
            if data1 and len(data1[0]) > 1:
                oj_name, user_name = data1[0]
                oj_name = oj_name.lower()
                if oj_name in ['cf', 'nk', 'lg']:
                    res = NameQuery(oj_name, user_name)

            # 筛选出可能调用ChooseKey的data
            data2 = re.compile(r'(..)\s*(.*)').findall(data['message'])
            if data2 and len(data2[0]) > 1:
                op, key = data2[0]
                if op in ['来只', '清空', '给我']:
                    res = ChooseKey(op, key, data)
            data2 = re.compile(r'.*]\s*(..)\s*(.*)').findall(data['message'])
            if data2 and len(data2[0]) > 1:
                op, key = data2[0]
                if op in ['删除', '添加']:
                    res = ChooseKey(op, key, data)

            # 筛选出可能调用AtQuery的data
            data3 = re.compile(r"^\[CQ:at,qq=(\d+)]\s*(..)").findall(data['message'])
            if data3 and len(data3[0]) > 1:
                qq_num, oj_name = data3[0]
                if oj_name in ['cf', 'nk', 'lg']:
                    res = AtQuery(int(qq_num), oj_name)

            # 筛选出可能调用RandomProblem的data
            data4 = re.compile(r"^\[CQ:at,qq=(\d+)]\s*(....)").findall(data['message'])
            if data4 and len(data4[0]) > 1:
                qq_num, order = data4[0]
                if qq_num in ['3661517915'] and order == '随机一题':
                    qq_num = data['sender']['user_id']
                    res = RandomProblem(qq_num)
                if qq_num in ['3661517915'] and order in ['我写好了', '我写完了']:
                    qq_num = data['sender']['user_id']
                    res = RandomProblemJudge(qq_num)
                if qq_num in ['3661517915'] and order in ['每日题目']:
                    res = DailyProblem.dailyProblem()
            # 筛选出可能调用Bind的data
            data5 = re.compile(r"^绑定(..)\s*(.*)").findall(data['message'])
            if data5 and len(data5[0]) > 1:
                oj_name, user_name = data5[0]
                qq_num = data['sender']['user_id']
                if oj_name in ['cf', 'nk', 'lg']:
                    res = Bind(oj_name, user_name, qq_num)

            # 筛选出可能调用Duel的data
            data6 = re.compile(r"^/duel\s*(.*)").findall(data['message'])
            if data6:
                if len(data6[0].split()) == 1:
                    order = data6[0]
                    qq_num = data['sender']['user_id']
                    if order.lower() == 'accept':
                        print('触发了接受单挑')
                        res = Duel.accept(duel_dict, qq_num)
                    if order.lower() == 'reject':
                        print('触发了拒绝单挑')
                        res = Duel.reject(duel_dict, qq_num)
                    if order.lower() == 'judge':
                        print('触发了单挑结算')
                        res = Duel.judge(duel_dict, qq_num)
                if len(data6[0].split(']')) == 2:
                    print('触发了单挑邀请')
                    challenged, rating = data6[0].split(']')
                    challenged = int(re.compile(r"\[CQ:at,qq=(\d+)").findall(challenged)[0])
                    rating = rating.lstrip()
                    challenger = data['sender']['user_id']
                    if 800 <= int(rating) <= 3500:
                        res = Duel.invite(duel_dict, challenger, challenged, rating)
                    else:
                        qq_num = data['sender']['user_id']
                        res = f'[CQ:at,qq={qq_num}] rating范围应该是800-3500之间的整百数'

            # 筛选出可能调用RecentAcm的data
            data7 = re.compile(r"^近期(...)").findall(data['message'])
            if data7:
                if data7[0].lower() == 'acm':
                    print('触发了近期acm')
                    res = RecentAcm.get_data()

            if data['message'] == '/help':
                res = (f'给我看看：查看所有关键词\n\n'
                       f'来只xx：如果关键词xx存在，随机发送一张保存的图片)\n\n'
                       f'近期acm：返回近期cf/nk/lg/at的比赛\n\n'
                       f'@图片删除xx：短期内可以删除关键词xx下@的图片\n\n'
                       f'@图片添加xx：添加@的图片到关键词xx\n\n'
                       f'绑定cf/nk/lg 你的id：绑定对应oj的账号\n\n'
                       f'#cf/nk/lg id：查询id在对应oj的信息\n\n@某人 '
                       f'cf/nk/lg：如果此人已经绑定，返回其在对应oj的信息\n\n'
                       f'@bot 随机一题：bot根据你的cf分数+0/100/200随机选一道题目，每次使用这条指令都会发出新题目\n\n'
                       f'@bot 我写完了：结算随机一题\n\n'
                       f'/duel @某人 800-3500：bot挑选指定分数的一道cf题目，开启你与@的用户的duel\n\n'
                       f'/duel accept：接受duel\n\n'
                       f'/duel reject：拒绝duel\n\n'
                       f'/duel judge：结算duel，如果双方都没完成也会结算，可以作为换题使用')

        if res:
            requests.get(f"http://127.0.0.1:5020/send_group_msg",
                         params={"group_id": data['group_id'],
                                 "message": res})

        # 每日做题反馈
        now = datetime.now()
        print(now)
        # if now.minute == 0 and (now.hour in [11, 23]) and 'interval' in data:
        #     data['group_id'] = 547460746
        #     res = TodayInvoluteDog()
        #     requests.get(f"http://127.0.0.1:5020/send_group_msg",
        #                  params={"group_id": data['group_id'],
        #                          "message": res})
        # 每日推荐题目更新
        if now.hour == 8 and now.minute == 0:
            data['group_id'] = 547460746
            res = DailyProblem.dailyProblem()
            requests.get(f"http://127.0.0.1:5020/send_group_msg",
                         params={"group_id": data['group_id'],
                                 "message": res})
        # 每日推荐题目判断
        if 'interval' in data:
            data['group_id'] = 547460746
            res = DailyProblem.daliyProblemJudge()
            requests.get(f"http://127.0.0.1:5020/send_group_msg",
                         params={"group_id": data['group_id'],
                                 "message": res})

        return 'OK Data'
    else:
        return 'No Data'


def TodayInvoluteDog() -> str:
    df1 = pd.read_excel('check.xlsx')  # 要查询的qq
    df2 = pd.read_excel('qqid.xlsx')
    qq_dic = {}
    lazy = []
    for i in df1['qq']:
        print(i)
        ac = submit = 0
        idx = df2['qq'].to_list().index(i)
        if not pd.isna(df2['cf'][idx]):
            cfdata = CodeforcesQuery.get_data(df2['cf'][idx])
            ac += cfdata['TodayAccept']
            submit += cfdata['TodaySubmit']
        if not pd.isna(df2['lg'][idx]):
            lgdata = LuoguQuery.get_data(df2['lg'][idx])
            ac += lgdata['TodayAccept']
            submit += lgdata['TodaySubmit']
        if not pd.isna(df2['nk'][idx]):
            nkdata = NewcoderQuery.get_data(df2['nk'][idx])
            ac += nkdata['TodayAccept']
            submit += nkdata['TodaySubmit']
        qq_dic[i] = [ac, submit]
        if ac == submit == 0:
            lazy.append(i)
    solve = sorted(qq_dic.items(), key=lambda x: (x[1][0], -x[1][1]), reverse=True)
    mess = "今日卷狗："
    for i in range(3):
        mess += f"[CQ:at,qq={solve[i][0]}]({solve[i][1][0]}/{solve[i][1][1]}) "
    mess += "\n今日最佳摸鱼："
    for i in range(-1, -max(3, len(lazy)) - 1, -1):
        print(solve[i][0])
        mess += f"[CQ:at,qq={solve[i][0]}]({solve[i][1][0]}/{solve[i][1][1]}) "
    return mess


def Download() -> None:
    """
    本地未检测到题目信息文件，重新爬取到本地

    返回：
    None
    """
    print('未找到problemset.json,正在下载题目信息文件...')
    url = "https://codeforces.com/api/problemset.problems"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
    }
    resp = requests.get(url, headers=headers).text
    dic = json.loads(resp)
    problemset_dict = {i: [] for i in range(800, 3600, 100)}
    for i in dic['result']['problems']:
        if 'rating' in i:
            problemset_dict[i['rating']].append([i['contestId'], i['index']])
    with open('problemset.json', 'w', encoding='utf-8') as f:
        f.write(json.dumps(problemset_dict, ensure_ascii=False, indent=4))
    print('题目信息已保存至problemset.json')


def NameQuery(oj_name: str, user_name: str) -> str:
    """
    根据传入的参数选择oj进行查询并返回记录

    参数：
    oj_name（str)：oj的名字
    user_name（str)：需要查询的用户名

    返回：
    str：将查询到的信息返回
    """
    print(f"触发了{oj_name}查询 {user_name}")
    oj_dict = {"cf": CodeforcesQuery, "nk": NewcoderQuery, "lg": LuoguQuery}
    try:
        user_data = oj_dict[oj_name].get_data(user_name)
        # 对提交时间进行划分
        if user_data["LatestSubmitTime"] < 120:  # 两分钟内
            user_data["LatestSubmitTime"] = "just now"
        elif user_data["LatestSubmitTime"] < 7200:  # 两小时内
            user_data["LatestSubmitTime"] = f"{user_data['LatestSubmitTime'] // 60} minutes ago"
        elif user_data["LatestSubmitTime"] < 86400:  # 一天内
            user_data["LatestSubmitTime"] = f"{user_data['LatestSubmitTime'] // 3600} hours ago"
        elif user_data["LatestSubmitTime"] < 172800:  # 两天内
            user_data["LatestSubmitTime"] = f"{user_data['LatestSubmitTime'] // 86400} day ago"
        else:  # 两天以上
            user_data["LatestSubmitTime"] = f"{user_data['LatestSubmitTime'] // 86400} days ago"

        # 对提交状态的判断
        if user_data['LatestSubmitStatus'] == 0:  # 没AC
            if user_data['LatestSubmitTimes'] > 1:  # 多次尝试
                user_data['LatestSubmitStatus'] = f"Unaccept in {user_data['LatestSubmitTimes']} tries"
            else:
                user_data['LatestSubmitStatus'] = f"Unaccept in {user_data['LatestSubmitTimes']} try"
        else:
            if user_data['LatestSubmitPassed'] > 1:  # 曾经AC过
                user_data['LatestSubmitStatus'] = "Accepted"
            else:
                if user_data['LatestSubmitTimes'] > 1:  # 第一次AC多次尝试
                    user_data['LatestSubmitStatus'] = f"Accept in {user_data['LatestSubmitTimes']} tries"
                else:
                    user_data['LatestSubmitStatus'] = "Accept in 1 try !"
        if oj_name == 'lg':
            user_data['RatingTimes'] = '?'
        res = (f"{user_name}：{user_data['RatingNow']}/{user_data['RatingMax']}（{user_data['RatingTimes']}）\n"
               f"All：{user_data['AllAccept']}/{user_data['AllSubmit']}\n"
               f"Today：{user_data['TodayAccept']}/{user_data['TodaySubmit']}\n"
               f"Latest：{user_data['LatestSubmitTime']} {user_data['LatestSubmitStatus']}\n"
               f"{user_data['LatestSubmitLink']}"
               )
        return res
    except:
        return f"{user_name} 查询失败"


def ChooseKey(op: str, key: str, data: dict) -> str:
    """
    根据不同的操作和对象进行不同的命令选择

    参数：
    op（str）:操作的命令
    key（str）：操作的对象
    data（dict）：监听到的消息
    返回 ：
    str：将操作命令返回
    """
    print(f'触发了{op} {key}')
    if op == '来只':
        return Collector.get_one(key)
    if op == '删除':
        try:
            return Collector.del_one(data, key)
        except:
            return '删除失败'
    if op == '添加':
        try:
            return Collector.add_one(data, key)
        except:
            return '添加失败'
    if op == '清空':
        return Collector.del_all(data, key)
    if op == '给我' and key == '看看':
        return Collector.show_all()


def AtQuery(qq_num: int, oj_name: str) -> str:
    """
    通过@得到用户的qq，再用pandas获取对应用户在各个oj上的账号进行查询

    参数：
    qq_name：被@的用户的qq
    oj_name：oj的名字

    返回：
    str：将查询到的信息返回
    """
    print('触发了at查询')
    df = pd.read_excel('qqid.xlsx')
    if qq_num in df['qq'].to_list():
        idx = df['qq'].to_list().index(qq_num)
        oj_id = df[oj_name][idx]
        if not pd.isna(oj_id):  # 可以查询
            return NameQuery(oj_name, oj_id)
        return '暂未绑定'
    else:
        return '暂未绑定'


def RandomProblem(qq_num: int) -> str:
    """
    监听消息得到用户的qq，再用pandas获取对应用户在cf上的账号，对账号的rating随机加上0/100/200作为今天的练习题并返回，并对qqid.xlsx进行状态修改

    参数：
    qq_name：发消息的用户的qq

    返回：
    str：随机一题的链接
    """
    print('触发了随机一题')
    df = pd.read_excel('qqid.xlsx')
    if qq_num in df['qq'].to_list():
        idx = df['qq'].to_list().index(qq_num)
        oj_id = df['cf'][idx]
        if not pd.isna(oj_id):  # 可以查询
            with open('problemset.json', 'r', encoding='utf-8') as f:
                problemset_dict = json.load(f)
            print('已找到problemset.json,正在获取题目信息...')
            user_data = CodeforcesQuery.get_data(oj_id)
            # 根据当前的rating选择题目，最低800分，最高3500分
            target_rating = str(min(max(user_data['RatingNow'] - user_data['RatingNow'] % 100, 800), 3500))
            ID, INDEX = random.sample(problemset_dict[target_rating], 1)[0]  # 题目的id和比赛的index
            problem_url = f"https://codeforces.com/problemset/problem/{ID}/{INDEX}"
            mess = (f"[CQ:at,qq={qq_num}] 你的题目是：\n"
                    f"{problem_url}")
            df['problem'][idx] = [ID, INDEX]
            df['time'][idx] = time.time()
            df.to_excel('qqid.xlsx', index=False)
            return mess
        return '暂未绑定'
    else:
        return '暂未绑定'


def RandomProblemJudge(qq_num: int) -> str:
    """
    判定随机一题

    参数：
    qq_name：发消息的用户的qq

    """
    print('触发了随机一题判定')
    df = pd.read_excel('qqid.xlsx')
    f = 0
    if qq_num in df['qq'].to_list():
        idx = df['qq'].to_list().index(qq_num)
        oj_id = df['cf'][idx]
        if not pd.isna(oj_id):  # 可以查询
            if not pd.isna(df['problem'][idx]):  # 有待判的题目
                ID, INDEX = eval(df['problem'][idx])
                problem_time = df['time'][idx]
                user_url = f"https://codeforces.com/api/user.status?handle={oj_id}&count=10000"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                                  "Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0"
                }
                resp = requests.get(user_url, headers=headers, verify=False).json()
                for i in resp['result']:
                    if i['problem']['contestId'] == ID and i['problem']['index'] == INDEX and i[
                        'verdict'] == "OK" and int(i[
                                                       'creationTimeSeconds']) > problem_time:
                        f = 1
                        use_time = int(i['creationTimeSeconds']) - problem_time
                        rating = int(i['problem']['rating']) * 0.01
                        break
                if f:
                    t = time.strftime("%H:%M:%S", time.gmtime(use_time))
                    change = int(rating * 60 / (use_time / 60) * (rating / 10) ** 3)
                    old_rating = df['rating'][idx]
                    mess = (f"[CQ:at, qq={qq_num}] 恭喜你完成了题目！[CQ:face,id=144][CQ:face,id=144][CQ:face,id=144]\n"
                            f"耗时：{t} rating变化如下：\n"
                            f"{oj_id}：{old_rating} + {change} = {df['rating'][idx]}\n")
                    df['problem'][idx] = np.nan
                    df.to_excel('qqid.xlsx', index=False)
                    return mess
                else:
                    return f"[CQ:at,qq={qq_num}] 未检测到AC提交！"
            else:
                return f'[CQ:at,qq={qq_num}] 暂无题目'
        else:
            return '暂未绑定'
    else:
        return '暂未绑定'


def Bind(oj_name: str, user_name: str, qq_num: int) -> str:
    """
    将对应的oj和用户名以及qq相绑定

    参数：
    oj_name：oj的名字
    user_name：oj用户名
    qq_num：要绑定的qq号

    返回：
    绑定结果的响应状态
    """
    print('触发了绑定')
    df = pd.read_excel('qqid.xlsx')
    if qq_num not in df['qq'].values:
        df = df._append({'qq': qq_num, 'duel_status': 1, 'rating': 0, 'nk': '', 'cf': '', 'lg': '', 'problem': ''},
                        ignore_index=True)
        df.to_excel('qqid.xlsx', index=False)
        df = pd.read_excel('qqid.xlsx')
    idx = df['qq'].to_list().index(qq_num)
    df.loc[idx, oj_name] = user_name
    df.to_excel('qqid.xlsx', index=False)
    return '绑定成功'


if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5010, threaded=True)

# test
