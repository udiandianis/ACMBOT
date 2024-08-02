import requests
import random
import re
import os
import shutil

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0"
}


def get_one(key: str) -> str:
    """
    在img文件夹下根据key随机选择一个文件并返回

    参数：
    key（str）：指定要操作的对象

    返回：
    str：要发送的内容
    """
    path = fr"{os.path.dirname(__file__)}\img\{key}"
    if os.path.exists(path):  # 存在这个关键词
        cnt = len(os.listdir(path))  # 这个关键词下文件的数量
        if cnt:
            file = f'{path}/{os.listdir(path)[random.randint(0, cnt - 1)]}'  # 随机选择一个文件发送
            # 不同的文件需要不同格式的CQ码发送
            if 'txt' in file:
                f = open(file, 'r', encoding="utf-8").readlines()
                mess = f[random.randint(0, len(f) - 1)].strip()
            elif 'mp4' in file:
                mess = f'[CQ:video,file={file}]'
            elif 'mp3' in file:
                mess = f'[CQ:file,file={file}]'
            else:
                mess = f'[CQ:image,file={file}]'
            return mess
    return '没有这个关键词'


def add_one(data: dict, key: str) -> str:
    """
    在img文件夹下根据key添加一个文件并返回状态

    参数：
    data（dict）：监听的消息，用于获取之前@的消息的id
    key（str）：指定要操作的对象

    返回：
    str：要发送的内容
    """
    message_id = "-" + re.findall(r"[0-9]+", data['message'])[0]  # 之前@的消息的id
    print(message_id)
    path = fr"{os.path.dirname(__file__)}\img\{key}"
    if not os.path.exists(path):
        os.makedirs(path)
    content = requests.get(f"http://127.0.0.1:5020/get_msg", params={'message_id': message_id}).json()['data'][
        'message']  # @的消息的内容
    print(content)
    if 'url' in content:
        file_name = content.split(',')[1].replace('.jpf.gif','.gif')  # 文件名
        for i in content.split(','):
            if 'url' in i:
                file_url = i.split('url=')[-1].replace("&amp;", "&").replace(
            "https://multimedia.nt.qq.com.cn/", "https://gchat.qpic.cn/")  # 重写url，爬取文件
        print(file_url)
        resp = requests.get(file_url, headers=headers, verify=False).content
        file = fr'{path}\{file_name}'
        with open(file, 'wb') as f:  # 写入文件
            f.write(resp)
    else:
        # 如果消息中没有url，则不是可以下载的文件，当作文本写入
        file = fr'{path}\{key}.txt'
        if not os.path.exists(file):
            with open(file, 'w', encoding="utf-8") as f:
                f.write(content + "\n")
        else:
            with open(file, 'a', encoding="utf=8") as f:
                f.write(content + "\n")
    return "添加成功"


def del_one(data: dict, key: str) -> str:
    """
    在img文件夹下根据key删除指定文件并返回状态

    参数：
    data（dict）：监听的消息，用于获取之前@的消息的id
    key（str）：指定要操作的对象

    返回：
    str：要发送的内容
    """
    message_id = "-" + re.findall(r"[0-9]+", data['message'])[0]  # 之前@的消息的id
    path = fr"{os.path.dirname(__file__)}\img\{key}"
    if os.path.exists(path):
        content = requests.get(f"http://127.0.0.1:5020/get_msg", params={'message_id': message_id}).json()['data'][
            'message']  # @的消息的内容
        if 'url' in content:
            for i in os.listdir(path):
                if i == content.split(',')[1]:
                    os.remove(fr'{path}\{i}')
                    return '删除成功'
        else:
            return '不支持删除文本'


def del_all(data: str, key: str) -> str:
    """
    在img文件夹下根据key删除整个关键词并返回状态

    参数：
    data（dict）：监听的消息，用于获取之前@的消息的id
    key（str）：指定要操作的对象

    返回：
    str：要发送的内容
    """

    path = fr"{os.path.dirname(__file__)}\img\{key}"
    if os.path.exists(path):
        if data['sender']['user_id'] in [1040530821]:
            shutil.rmtree(path)
            return '清空成功'
        return '权限不足'
    return '没有这个关键词'


def show_all() -> str:
    """
    遍历文件夹查找是否存在可用的关键词

    返回：
    str：返回检索的信息
    """
    mess = "可以使用的关键词："
    path = fr"{os.path.dirname(__file__)}\img"
    for i in os.listdir(path):
        if os.listdir(f'{path}\\{i}'):
            mess = mess + ' ' + i
    if mess == "可以使用的关键词：":
        mess = "没有可以使用关键词"
    return mess
