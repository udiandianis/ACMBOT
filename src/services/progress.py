import logging
import threading

logger = logging.getLogger(__name__)


class QueryProgress:
    def __init__(self, send, interval=5):
        """定时报告实际查询人数，结束后停止发送。"""
        self.send, self.interval = send, interval
        self.completed = self.total = 0
        self.stage = ''
        self.lock = threading.Lock()
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self.report, daemon=True)

    def update(self, completed, total, stage=''):
        """由查询线程更新已处理人数，失败也算已处理。"""
        with self.lock:
            self.completed, self.total = completed, total
            self.stage = stage

    def report(self):
        """每五秒发送当前数量，全部查询完成后停止定时报告。"""
        while not self.stopped.wait(self.interval):
            with self.lock:
                completed, total = self.completed, self.total
                stage = self.stage
            if total and completed < total:
                try:
                    self.send(f'当前进度 {stage + " " if stage else ""}{completed}/{total}')
                except Exception:
                    logger.exception('查询进度发送失败')

    def __enter__(self):
        self.thread.start()
        return self.update

    def __exit__(self, error_type, *_):
        self.stopped.set()
        self.thread.join()
        if error_type is None and self.total:
            try:
                self.send(f'当前进度 {self.stage + " " if self.stage else ""}{self.completed}/{self.total}')
            except Exception:
                logger.exception('最终进度发送失败')
