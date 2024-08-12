import requests
import time


def get_data(username: str) -> dict:
    """
    根据传入的ID查询该用户在网站Codeforces的做题情况

    参数：
    username（str）: 用户的ID

    返回：
    res（str）:按照格式返回这个用户在网站的做题记录
    """
    # 用户的所有信息
    user_data = {
        "Username": username,  # 用户名
        "RatingTimes": 0,  # 参赛次数
        "RatingNow": 0,  # 当前分
        "RatingMax": 0,  # 最高分
        "AllSubmit": 0,  # 总提交数
        "AllAccept": 0,  # 总通过数
        "TodaySubmit": 0,  # 今日提交数
        "TodayAccept": 0,  # 今日通过数
        "LatestSubmitTime": 0,  # 最新的提交时间
        "LatestSubmitStatus": 0,  # 最新的提交状态
        "LatestSubmitPassed": 0,  # 最新提交的题目以前是否通过
        "LatestSubmitTimes": 0,  # 最新题目的提交次数
        "LatestSubmitLink": ""  # 最新提交题目链接
    }

    # 计算出今天0的时间戳，中国位于东八区因此需要调整8小时的偏移量
    now = time.time() + 8 * 3600
    start_time = now - now % 86400 - 8 * 3600

    # 调用api获取记录
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0"
    }
    problem_url = f"https://codeforces.com/api/user.status?handle={username}&count=10000"  # 做题api 设置查询上线为10000
    rating_url = f"https://codeforces.com/api/user.rating?handle={username}"  # rating查询 api

    # rating统计
    rating_resp = requests.get(rating_url, headers=headers, verify=False).json()
    try:  # 没参加过比赛会获取不到数据，用异常退出
        for i in rating_resp["result"]:
            user_data["RatingTimes"] += 1
            user_data["RatingMax"] = max(user_data["RatingMax"], i["oldRating"], i["newRating"])
        user_data["RatingNow"] = i["newRating"]
    except:
        pass

    # 做题统计
    problem_resp = requests.get(problem_url, headers=headers, verify=False).json()

    # 直接更新最新做题时间和链接
    user_data["LatestSubmitTime"] = int(time.time() - problem_resp["result"][0]["creationTimeSeconds"])
    user_data[
        "LatestSubmitLink"] = f'https://codeforces.com/contest/{problem_resp["result"][0]["contestId"]}/problem/{problem_resp["result"][0]["problem"]["index"]}'
    lastest_problem = problem_resp["result"][0]["problem"]  # 最新问题的信息json
    for i in problem_resp["result"]:
        if i["creationTimeSeconds"] >= start_time:  # 今天的提交
            user_data["TodaySubmit"] += 1
            if i["verdict"] == "OK":
                user_data["TodayAccept"] += 1
        user_data["AllSubmit"] += 1
        if i["verdict"] == "OK":
            user_data["AllAccept"] += 1
        if lastest_problem == i["problem"]:  # 对于最新问题的统计
            user_data["LatestSubmitTimes"] += 1
            if i["verdict"] == "OK":
                user_data["LatestSubmitStatus"] = 1
                user_data["LatestSubmitPassed"] += 1

    # 对于大量提交的用户信息进行特判
    if user_data["AllSubmit"] == 10000:
        user_data["AllSubmit"] = "10000+"

    # 将所有信息返回
    return user_data
