import logging
from datetime import datetime, timedelta, timezone
from .practice import refresh_problemset

logger = logging.getLogger(__name__)
BEIJING_TIME = timezone(timedelta(hours=8))


def next_refresh(now, refresh_time):
    """按北京时间计算下一次题库更新时间，已到达的时间顺延到次日。"""
    now = now.astimezone(BEIJING_TIME)
    hour, minute = map(int, refresh_time.split(':'))
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return target if target > now else target + timedelta(days=1)


def run_daily_refresh(stop_event, refresh_time):
    """随机器人运行每日刷新任务；定期校准等待时间，停止时退出。"""
    logger.info('题库每日更新时间：北京时间 %s', refresh_time)
    while not stop_event.is_set():
        target = next_refresh(datetime.now(BEIJING_TIME), refresh_time)
        while not stop_event.is_set():
            remaining = (target - datetime.now(BEIJING_TIME)).total_seconds()
            if remaining <= 0:
                break
            if stop_event.wait(min(remaining, 60)):
                return
        if stop_event.is_set():
            return
        try:
            count = refresh_problemset()
            logger.info('题库更新完成，共 %s 道题', count)
        except Exception:
            logger.exception('题库更新失败，保留原题库，下次定时任务继续尝试')
