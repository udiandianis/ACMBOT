import threading
from ..paths import REPORT_DIRECTORY
from . import accounts, practice, media
from .duels import DuelService


class BotServices:
    def __init__(self, settings, client):
        """组装业务服务和互斥锁，初始化持久化单挑服务。"""
        self.settings, self.client = settings, client
        self.media = media.MediaService(client, settings)
        self.duels = DuelService()
        self._practice_lock = threading.Lock()
        self._render_lock = threading.Lock()

    query = staticmethod(accounts.query)
    query_bound = staticmethod(accounts.query_bound)
    bind = staticmethod(accounts.bind)

    def contests(self):
        """调用比赛提供方，返回即将开始的比赛说明。"""
        from ..providers import contests
        return contests.fetch_upcoming_contests()

    def answer(self, provider, question):
        """使用指定服务的独立配置请求中文回答。"""
        from ..providers.ai import answer
        return answer(question, self.settings, provider)

    def pending_homework(self, user_id):
        """查询待交作业，并在返回文本中提及请求用户。"""
        from ..providers import chaoxing
        return f'[CQ:at,qq={user_id}]\n' + chaoxing.fetch_pending_homework(user_id)

    def random_problem(self, user_id):
        """串行分配随机 CF 题目并保存用户任务。"""
        with self._practice_lock:
            return practice.random_problem(user_id)

    def judge_problem(self, user_id):
        """串行结算用户任务，防止同一任务重复增加积分。"""
        with self._practice_lock:
            return practice.judge_problem(user_id)

    def statistics(self):
        """串行生成统计表，返回对应 CQ 图片消息。"""
        from . import statistics
        with self._render_lock:
            statistics.get_png()
            return f'[CQ:image,file={(REPORT_DIRECTORY / "solve.png").as_posix()}]'

    def training_report(self):
        """串行生成洛谷题单报告，返回 CQ 图片消息。"""
        from . import trainings
        with self._render_lock:
            trainings.get_png()
            return f'[CQ:image,file={(REPORT_DIRECTORY / "luogu.png").as_posix()}]'

    def checkin(self, event):
        """串行更新签到月历，返回回复原消息的 CQ 图片消息。"""
        from . import checkin
        with self._render_lock:
            path = checkin.get_png(event)
            return f'[CQ:reply,id={event.get("message_id", "")}]成功🦌了[CQ:image,file={path.as_posix()}]'

    def invite(self, group_id, challenger, challenged, rating):
        """在指定群创建并保存单挑邀请，返回操作说明。"""
        return self.duels.invite(group_id, challenger, challenged, rating)

    def duel(self, group_id, operation, user_id):
        """执行单挑接受、拒绝、结算或重置操作。"""
        return self.duels.execute(group_id, operation, user_id)
