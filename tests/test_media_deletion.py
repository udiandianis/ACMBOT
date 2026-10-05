import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch
from src.app import create_app
from src.events import GroupMessage
from tests.support import test_settings
from src.services.media import MediaService
from src.storage import users


def event(user_id=1, group_id=7, reply_id=None, text=''):
    """构造管理员的群命令事件。"""
    parts = [{'type': 'at', 'data': {'qq': str(test_settings().bot_qq)}},
             {'type': 'text', 'data': {'text': text}}]
    if reply_id is not None:
        parts.insert(0, {'type': 'reply', 'data': {'id': str(reply_id)}})
    return GroupMessage.parse({'message_type': 'group', 'group_id': group_id,
        'user_id': user_id, 'message_id': 90, 'sender': {}, 'message': parts})


class DeletionConfirmationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        database = patch.object(users, 'DB_PATH', Path(self.directory.name) / 'bot.db')
        database.start()
        self.addCleanup(database.stop)
        users.init_db()
        self.client = Mock()
        self.settings = replace(test_settings(), media_admins=(1, 2))
        self.objects = {}
        storage = patch('src.services.media.R2Storage')
        cloud = storage.start().return_value
        self.addCleanup(storage.stop)
        cloud.put.side_effect = lambda key, content: self.objects.__setitem__(key, content)
        cloud.read_text.side_effect = lambda key: self.objects[key].decode('utf-8')
        cloud.delete.side_effect = lambda key: self.objects.pop(key, None)
        self.service = MediaService(self.client, self.settings)
        self.client.get_message.return_value = {'message': [{'type': 'text', 'data': {'text': 'hello'}}]}
        self.service.add('bjg', 10)

    def test_reply_delete_waits_for_confirmation_and_survives_restart(self):
        reply = self.service.random('bjg', 7)
        self.assertEqual(reply.text, 'hello')
        reply.on_sent({'message_id': 101})
        self.service = MediaService(self.client, self.settings)
        self.assertIn('确认删除 bjg-1', self.service.request_delete('bjg', event(reply_id=101)))
        self.assertIn('bjg/1.txt', self.objects)
        self.assertEqual(self.service.confirm('删除', 'bjg-1', event()), '删除成功：bjg-1')
        self.assertNotIn('bjg/1.txt', self.objects)
        self.assertIn('没有待确认', self.service.confirm('删除', 'bjg-1', event()))

    def test_other_user_group_or_target_cannot_confirm(self):
        self.service.request_delete('bjg-1', event())
        for request, target in ((event(user_id=2), 'bjg-1'), (event(group_id=8), 'bjg-1'), (event(), 'bjg-2')):
            self.assertNotIn('成功', self.service.confirm('删除', target, request))
        self.assertIn('bjg/1.txt', self.objects)
        self.assertEqual(self.service.request_delete('bjg-1', event(user_id=3)), '权限不足')
        self.assertEqual(self.service.confirm('删除', 'bjg-1', event(user_id=3)), '权限不足')

    def test_confirmation_expiration_and_cancellation(self):
        with patch('src.services.media.time.time', return_value=100):
            self.service.request_delete('bjg-1', event())
        with patch('src.services.media.time.time', return_value=161):
            self.assertIn('过期', self.service.confirm('删除', 'bjg-1', event()))
        self.service.request_delete('bjg-1', event())
        self.assertEqual(self.service.cancel(event()), '已取消删除')
        self.assertIn('没有待确认', self.service.confirm('删除', 'bjg-1', event()))
        self.assertIn('bjg/1.txt', self.objects)

    def test_replied_message_must_match_group_keyword_and_retention(self):
        self.service.record_sent(7, {'message_id': 101}, 'bjg', 1)
        self.assertIn('没有可用', self.service.request_delete('bjg', event(group_id=8, reply_id=101)))
        self.assertIn('不属于', self.service.request_delete('cat', event(reply_id=101)))
        with patch('src.services.media.time.time', return_value=100):
            self.service.record_sent(7, {'message_id': 102}, 'bjg', 1)
        with patch('src.services.media.time.time', return_value=100 + self.service.MESSAGE_RETENTION_SECONDS):
            self.assertIn('没有可用', self.service.request_delete('bjg', event(reply_id=102)))

    def test_latest_request_does_not_confirm_earlier_target(self):
        self.service.add('bjg', 10)
        self.service.request_delete('bjg-1', event())
        self.service.request_delete('bjg-2', event())
        self.assertIn('不一致', self.service.confirm('删除', 'bjg-1', event()))
        self.assertEqual(self.service.confirm('删除', 'bjg-2', event()), '删除成功：bjg-2')
        self.assertIn('bjg/1.txt', self.objects)

    def test_clear_confirm_only_removes_original_selection(self):
        self.assertIn('确认清空 bjg', self.service.request_clear('bjg', event()))
        self.service.add('bjg', 10)
        self.assertEqual(self.service.confirm('清空', 'bjg', event()), '清空成功：bjg')
        self.assertNotIn('bjg/1.txt', self.objects)
        self.assertIn('bjg/2.txt', self.objects)

    def test_actual_send_result_is_recorded_but_send_failure_is_not(self):
        services = Mock(media=self.service)
        self.client.send_group.return_value = {'message_id': 101}
        client = create_app(self.settings, self.client, services).test_client()
        client.post('/', json=event(text='来只bjg').raw)
        self.assertIn('确认删除 bjg-1', self.service.request_delete('bjg', event(reply_id=101)))
        self.client.send_group.side_effect = RuntimeError('network')
        with self.assertLogs('src.app', level='ERROR'):
            client.post('/', json=event(text='来只bjg').raw)
        with users.connect() as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM collection_messages').fetchone()[0], 1)

    def test_concurrent_confirmations_only_delete_once(self):
        from concurrent.futures import ThreadPoolExecutor
        self.service.request_delete('bjg-1', event())
        with patch.object(self.service, 'delete', wraps=self.service.delete) as delete:
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(lambda _: self.service.confirm('删除', 'bjg-1', event()), range(2)))
        delete.assert_called_once_with('bjg-1', 1)
        self.assertEqual(results.count('删除成功：bjg-1'), 1)

    def test_cloud_delete_uses_mapped_object_only_after_confirmation(self):
        cloud = Mock()
        self.service.cloud = cloud
        with users.connect() as connection:
            connection.execute("UPDATE collection_items SET object_key='bjg/1.txt'")
        self.service.record_sent(7, {'message_id': 101}, 'bjg', 1)
        self.service.request_delete('bjg', event(reply_id=101))
        cloud.delete.assert_not_called()
        self.assertEqual(self.service.confirm('删除', 'bjg-1', event()), '删除成功：bjg-1')
        cloud.delete.assert_called_once_with('bjg/1.txt')


if __name__ == '__main__':
    unittest.main()
