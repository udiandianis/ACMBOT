import requests
from datetime import datetime


def get_data() -> str:
    """
    获取指定oj近7日的比赛并返回

    返回：
    mess（str）：近7日的比赛内容
    """
    url = "https://contests.sdutacm.cn/contests.json"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0"
    }
    resp = requests.get(url, headers=headers, verify=False).json()

    # 存放解析的数据
    data = []
    for i in resp:
        if i["source"] in ["Codeforces", "AtCoder", "洛谷", "牛客竞赛"]:  # 只查看这四个oj的比赛情况
            match_time = datetime.fromisoformat(i["start_time"])  # 比赛时间
            current_time = datetime.utcnow()  # 当前时间
            current_time = current_time.replace(tzinfo=match_time.tzinfo)

            # 时间戳相减计算还有开始时间
            time_difference = match_time - current_time
            days = time_difference.days
            hours, minutes = divmod(time_difference.seconds, 3600)
            minutes, seconds = divmod(minutes, 60)

            # 只查看七天内的比赛
            if 0 <= days < 7:
                data.append(
                    f'{days}天{hours}小时{minutes}分钟后' + '\n'
                    + f'({i["source"]}){i["name"]}' + '\n'
                    + f'{i["link"]}')

    # 防止消息太长,只发五场

    if data:
        mess = "\n\n".join(data[:5])
    else:
        mess = "近7日没有比赛"
    return mess
