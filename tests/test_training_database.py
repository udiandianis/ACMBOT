import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, call, patch

from src.services import trainings
from src.storage import users
from tests.support import test_settings


class TrainingDatabaseTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        for change in (patch.object(users, 'DB_PATH', Path(directory.name) / 'bot.db'),
                       patch.object(trainings, 'get_settings', return_value=test_settings()),
                       patch.object(trainings, 'TRAINING_LABELS', {100: '顺序', 101: '分支'})):
            change.start()
            self.addCleanup(change.stop)
        users.init_db()

    def seed(self):
        with users.connect() as connection:
            connection.executemany('INSERT INTO luogu_training_problems VALUES (?, ?)', [(100, 'P0'), (101, 'P1')])

    def test_initial_download_persists_and_subsequent_reads_skip_network(self):
        progress = Mock()
        response = Mock(text='<a href="/problem/P1">题目</a>')
        with patch.object(trainings.http, 'get', return_value=response) as fetch:
            self.assertEqual(trainings.load_training_problems(progress), {100: {'P1'}, 101: {'P1'}})
            self.assertEqual(progress.call_args_list, [call(0, 2), call(1, 2), call(2, 2)])
            self.assertEqual(fetch.call_count, 2)
            users.init_db()
            trainings.load_training_problems()
            self.assertEqual(fetch.call_count, 2)

    def test_daily_refresh_replaces_removed_and_new_problems(self):
        self.seed()
        response = Mock(text='<a href="/problem/P2">题目</a>')
        with patch.object(trainings.http, 'get', return_value=response):
            self.assertEqual(trainings.refresh_training_problems(), 2)
        self.assertEqual(trainings.read_training_problems(), {100: {'P2'}, 101: {'P2'}})

    def test_failed_or_empty_download_keeps_all_previous_records(self):
        self.seed()
        response = Mock(text='<a href="/problem/P2">题目</a>')
        for failure in (RuntimeError('timeout'), Mock(text='no problems')):
            with patch.object(trainings.http, 'get', side_effect=[response, failure]):
                with self.assertRaises((RuntimeError, ValueError)):
                    trainings.refresh_training_problems()
            self.assertEqual(trainings.read_training_problems(), {100: {'P0'}, 101: {'P1'}})
