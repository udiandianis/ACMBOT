import unittest
from unittest.mock import Mock, call, patch

from src.services.progress import QueryProgress
from src.services import statistics


class QueryProgressTests(unittest.TestCase):
    def test_reports_current_counts_every_ten_seconds(self):
        send = Mock()
        progress = QueryProgress(send)
        progress.update(13, 64)
        progress.stopped = Mock()
        progress.stopped.wait.side_effect = [False, False, True]
        send.side_effect = lambda _: progress.update(57, 64)
        progress.report()
        self.assertEqual(send.call_args_list, [call('正在查询 13/64'), call('正在查询 57/64')])
        self.assertEqual(progress.stopped.wait.call_args_list, [call(10)] * 3)

    def test_finished_or_stopped_query_sends_no_progress(self):
        send = Mock()
        progress = QueryProgress(send)
        progress.update(64, 64)
        progress.stopped = Mock()
        progress.stopped.wait.side_effect = [False, True]
        progress.report()
        send.assert_not_called()

    def test_context_stops_timer_on_failure(self):
        progress = QueryProgress(Mock(), interval=0.01)
        with self.assertRaises(ValueError):
            with progress as update:
                update(0, 64)
                raise ValueError('查询失败')
        self.assertTrue(progress.stopped.is_set())
        self.assertFalse(progress.thread.is_alive())

    def test_statistics_counts_users_including_failed_queries(self):
        participants = [
            {'qq_id': 1, 'name': '用户一', 'codeforces_handle': 'one', 'luogu_username': 'one'},
            {'qq_id': 2, 'name': '用户二', 'codeforces_handle': 'two'},
            {'qq_id': 3, 'name': '用户三'},
            {'qq_id': 4, 'name': None, 'codeforces_handle': 'excluded'},
        ]
        fetch = Mock(return_value={'today_accepted_submissions': 1, 'today_submissions': 2})
        failed = Mock(side_effect=ValueError('洛谷查询失败'))
        update = Mock()
        with patch.object(statistics.users, 'list_users', return_value=participants), \
             patch.object(statistics, 'PLATFORMS', {'CF': ('codeforces_handle', fetch), 'LG': ('luogu_username', failed)}):
            records, _ = statistics.collect_statistics(update)
        self.assertEqual(update.call_args_list, [call(0, 3), call(1, 3), call(2, 3), call(3, 3)])
        self.assertEqual(records[1]['errors'], ['LG'])
        self.assertEqual(fetch.call_count, 2)
