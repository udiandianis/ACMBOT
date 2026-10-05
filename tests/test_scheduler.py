import sys
import unittest
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.services import scheduler


class SchedulerTests(unittest.TestCase):
    def test_midnight_uses_beijing_time(self):
        now = datetime(2026, 10, 5, 15, 59, 59, tzinfo=timezone.utc)
        target = scheduler.next_refresh(now, '00:00')
        self.assertEqual(target, datetime(2026, 10, 6, 0, 0, tzinfo=scheduler.BEIJING_TIME))
        self.assertEqual((target - now).total_seconds(), 1)

    def test_reached_time_and_year_boundary_roll_forward(self):
        now = datetime(2026, 12, 31, 23, 30, tzinfo=scheduler.BEIJING_TIME)
        self.assertEqual(scheduler.next_refresh(now, '23:30'), datetime(2027, 1, 1, 23, 30, tzinfo=scheduler.BEIJING_TIME))

    def test_stopping_while_waiting_skips_refresh(self):
        stop = Mock()
        stop.is_set.return_value = False
        stop.wait.return_value = True
        with patch.object(scheduler, 'refresh_problemset') as refresh:
            scheduler.run_daily_refresh(stop, '00:00')
            refresh.assert_not_called()
        self.assertLessEqual(stop.wait.call_args.args[0], 60)

    def test_refresh_failure_is_logged_and_scheduler_keeps_waiting(self):
        before = datetime(2026, 10, 5, 23, 59, 59, tzinfo=scheduler.BEIJING_TIME)
        midnight = datetime(2026, 10, 6, tzinfo=scheduler.BEIJING_TIME)
        stop = Mock()
        stop.is_set.return_value = False
        stop.wait.return_value = True
        with patch.object(scheduler, 'datetime', wraps=datetime) as clock, patch.object(scheduler, 'refresh_problemset', side_effect=RuntimeError('timeout')) as refresh:
            clock.now.side_effect = [before, midnight, midnight, midnight]
            with self.assertLogs(scheduler.logger, level='ERROR') as logs:
                scheduler.run_daily_refresh(stop, '00:00')
            refresh.assert_called_once_with()
            self.assertIn('保留原题库', logs.output[0])
            stop.wait.assert_called_once_with(60)
