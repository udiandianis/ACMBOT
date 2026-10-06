import io
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from tests.support import test_settings
from src.storage import users
from src.storage.r2 import R2Storage
from src.services.media import MediaService


class CloudCollectionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        database = patch.object(users, 'DB_PATH', Path(self.directory.name) / 'bot.db')
        database.start()
        self.addCleanup(database.stop)
        users.init_db()
        self.settings = replace(test_settings(), media_admins=(1,), r2_endpoint='https://example.com',
                                r2_bucket='test', r2_access_key_id='test', r2_secret_access_key='test')
        self.client = Mock()
        storage = patch('src.services.media.R2Storage')
        self.cloud = storage.start().return_value
        self.addCleanup(storage.stop)
        self.objects = {}
        self.cloud.put.side_effect = lambda key, content: self.objects.__setitem__(key, content)
        self.cloud.read_text.side_effect = lambda key: self.objects[key].decode('utf-8')
        self.cloud.delete.side_effect = lambda key: self.objects.pop(key, None)
        self.cloud.url.return_value = 'https://example.com/get?a=1&b=2'
        self.event = SimpleNamespace(group_id=7, user_id=1, reply_id=None)

    def text_message(self, content='hello$world'):
        self.client.get_message.return_value = {'message': [{'type': 'text', 'data': {'text': content}}]}

    def test_attachment_types_use_numeric_object_names(self):
        service = MediaService(self.client, self.settings)
        for kind, suffix in (('image', '.png'), ('video', '.mp4'), ('record', '.mp3'), ('file', '.pdf')):
            self.client.get_message.return_value = {'message': [{'type': kind, 'data': {
                'file': 'hash' + suffix, 'url': 'https://example.com/original'}}]}
            with patch('src.services.media.requests.get', return_value=Mock(content=b'content')):
                self.assertEqual(service.add(kind, 1), '添加成功')
            self.assertEqual(self.objects[f'{kind}/1{suffix}'], b'content')
            self.assertEqual(service.random(kind), f'[CQ:{kind},file=https://example.com/get?a=1&amp;b=2]')
        self.assertEqual(service.delete('image-1', 2), '权限不足')
        self.assertEqual(service.delete('image-1', 1), '删除成功：image-1')
        self.assertNotIn('image/1.png', self.objects)

    def test_text_keeps_dollar_and_newlines(self):
        service = MediaService(self.client, self.settings)
        self.text_message('hello$world\r\nsecond')
        self.assertEqual(service.add('bjg', 1), '添加成功')
        self.assertEqual(service.random('bjg'), 'hello$world\r\nsecond')
        self.assertEqual(service.list(), '可以使用的关键词：\n\nbjg')

    def test_failed_upload_does_not_reuse_number_or_publish_index(self):
        service = MediaService(self.client, self.settings)
        self.text_message()
        self.cloud.put.side_effect = RuntimeError('network')
        with self.assertRaises(RuntimeError):
            service.add('bjg', 1)
        self.assertEqual(service.list(), '没有可以使用的关键词')
        self.cloud.put.side_effect = lambda key, content: self.objects.__setitem__(key, content)
        self.assertEqual(service.add('bjg', 1), '添加成功')

    def test_delete_clear_and_restart_never_reuse_numbers(self):
        service = MediaService(self.client, self.settings)
        self.text_message()
        for number in (1, 2, 3):
            self.assertEqual(service.add('bjg', 1), '添加成功')
        service.delete('bjg-2', 1)
        service = MediaService(self.client, self.settings)
        self.assertEqual(service.add('bjg', 1), '添加成功')
        service.request_clear('bjg', self.event)
        self.assertEqual(service.confirm('清空', 'bjg', self.event), '清空成功：bjg')
        self.assertEqual(self.objects, {})
        self.assertEqual(service.add('bjg', 1), '添加成功')

    def test_failed_delete_keeps_index(self):
        service = MediaService(self.client, self.settings)
        self.text_message()
        service.add('bjg', 1)
        self.cloud.delete.side_effect = RuntimeError('network')
        with self.assertRaises(RuntimeError):
            service.delete('bjg-1', 1)
        self.assertIn('bjg', service.list())

    def test_concurrent_additions_have_distinct_numbers(self):
        from concurrent.futures import ThreadPoolExecutor
        services = [MediaService(self.client, self.settings) for _ in range(2)]
        self.text_message()
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda service: service.add('bjg', 1), services))
        self.assertEqual(results, ['添加成功', '添加成功'])
        self.assertEqual(set(self.objects), {'bjg/1.txt', 'bjg/2.txt'})

    def test_empty_content_and_invalid_keyword_do_not_upload(self):
        service = MediaService(self.client, self.settings)
        self.text_message('  ')
        self.assertIn('没有可保存', service.add('bjg', 1))
        for key in ('', '../outside', 'a/b'):
            with self.assertRaises(ValueError):
                service.add(key, 1)
        self.cloud.put.assert_not_called()

    def test_database_record_without_cloud_path_is_rejected(self):
        users.init_db()
        with users.connect() as connection:
            connection.execute('CREATE TABLE collection_items (keyword TEXT, item_number INTEGER, kind TEXT, object_key TEXT)')
            connection.execute("INSERT INTO collection_items VALUES ('bjg', 1, 'text', NULL)")
        with self.assertRaisesRegex(ValueError, '缺少云端路径'):
            MediaService(self.client, self.settings)


class R2StorageTests(unittest.TestCase):
    def setUp(self):
        factory = patch('src.storage.r2.boto3.client')
        self.client = factory.start().return_value
        self.addCleanup(factory.stop)
        self.storage = R2Storage(replace(test_settings(), r2_endpoint='https://example.com', r2_bucket='test',
                                        r2_access_key_id='test', r2_secret_access_key='test'))

    def test_upload_sets_content_type(self):
        self.storage.put('bjg/1.png', b'content')
        self.client.put_object.assert_called_once_with(Bucket='test', Key='bjg/1.png', Body=b'content', ContentType='image/png')

    def test_text_stream_is_closed(self):
        body = io.BytesIO('你好$world'.encode('utf-8'))
        self.client.get_object.return_value = {'Body': body}
        self.assertEqual(self.storage.read_text('bjg/1.txt'), '你好$world')
        self.assertTrue(body.closed)

    def test_signed_url_uses_configured_expiry(self):
        self.storage.url('bjg/1.png')
        self.client.generate_presigned_url.assert_called_once_with('get_object', Params={'Bucket': 'test', 'Key': 'bjg/1.png'}, ExpiresIn=self.storage.expiry)

    def test_delete_targets_one_object(self):
        self.storage.delete('bjg/1.png')
        self.client.delete_object.assert_called_once_with(Bucket='test', Key='bjg/1.png')


if __name__ == '__main__':
    unittest.main()
