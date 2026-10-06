import random
import json
import time
from pathlib import Path
from urllib.parse import quote
import requests
from ..events import segments
from ..storage import users
from ..storage.r2 import R2Storage
from ..router import Reply


class MediaService:
    MESSAGE_RETENTION_SECONDS = 7 * 24 * 60 * 60
    CONFIRMATION_SECONDS = 60

    def __init__(self, client, settings):
        """连接 R2 并建立收藏编号、消息映射及确认记录。"""
        self.client, self.settings = client, settings
        self.cloud = R2Storage(settings)
        with users.connect() as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS collection_items (
                keyword TEXT NOT NULL, item_number INTEGER NOT NULL,
                kind TEXT NOT NULL, object_key TEXT NOT NULL,
                PRIMARY KEY (keyword, item_number))""")
            connection.execute("""CREATE TABLE IF NOT EXISTS collection_counters (
                keyword TEXT PRIMARY KEY, last_number INTEGER NOT NULL)""")
            connection.execute("""CREATE TABLE IF NOT EXISTS collection_messages (
                group_id INTEGER NOT NULL, message_id INTEGER NOT NULL,
                keyword TEXT NOT NULL, item_number INTEGER NOT NULL, expires_at REAL NOT NULL,
                PRIMARY KEY (group_id, message_id))""")
            connection.execute("""CREATE TABLE IF NOT EXISTS collection_confirmations (
                group_id INTEGER NOT NULL, user_id INTEGER NOT NULL, action TEXT NOT NULL,
                target TEXT NOT NULL, items TEXT NOT NULL, expires_at REAL NOT NULL,
                PRIMARY KEY (group_id, user_id))""")
            if connection.execute('SELECT 1 FROM collection_items WHERE object_key IS NULL LIMIT 1').fetchone():
                raise ValueError('收藏记录缺少云端路径，请检查数据库')

    @staticmethod
    def validate_keyword(key):
        """校验关键词，避免无效对象路径或消息字符。"""
        key = key.strip()
        if (not key or key in ('.', '..') or key.endswith(('.', ' '))
                or any(c in key for c in '/\\:<>"|?*') or any(ord(c) < 32 for c in key)):
            raise ValueError('请输入有效的关键词')
        return key

    @staticmethod
    def next_number(connection, key):
        """在当前写事务中递增编号，删除后不复用。"""
        connection.execute('''INSERT INTO collection_counters VALUES (?, 1)
            ON CONFLICT(keyword) DO UPDATE SET last_number=last_number+1''', (key,))
        return connection.execute('SELECT last_number FROM collection_counters WHERE keyword=?', (key,)).fetchone()[0]

    def list(self):
        """返回包含文件的关键词列表，供合并转发。"""
        with users.connect() as connection:
            keys = [row[0] for row in connection.execute('SELECT DISTINCT keyword FROM collection_items ORDER BY keyword')]
        return '可以使用的关键词：\n\n' + '\n\n'.join('、'.join(keys[start:start + 20]) for start in range(0, len(keys), 20)) if keys else '没有可以使用的关键词'

    def random(self, key, group_id=None):
        """从 R2 随机读取一条内容，发送成功后记录引用映射。"""
        key = self.validate_keyword(key)
        with users.connect() as connection:
            items = connection.execute('SELECT * FROM collection_items WHERE keyword=?', (key,)).fetchall()
        if not items:
            return '没有这个关键词'
        item = random.choice(items)
        if item['kind'] == 'text':
            content = self.cloud.read_text(item['object_key'])
        else:
            location = self.cloud.url(item['object_key']).replace('&', '&amp;')
            content = f"[CQ:{item['kind']},file={location}]"
        if group_id is None:
            return content
        return Reply(content, on_sent=lambda result: self.record_sent(group_id, result, key, item['item_number']))

    def record_sent(self, group_id, result, key, number):
        """发送成功后，将返回的消息 ID 与收藏编号关联，保留七天。"""
        if not isinstance(result, dict) or type(result.get('message_id')) is not int:
            return
        now = time.time()
        with users.connect() as connection:
            connection.execute('DELETE FROM collection_messages WHERE expires_at<=?', (now,))
            connection.execute('INSERT OR REPLACE INTO collection_messages VALUES (?, ?, ?, ?, ?)',
                (group_id, result['message_id'], key, number, now + self.MESSAGE_RETENTION_SECONDS))

    def request_delete(self, target, event):
        """按引用的机器人消息或明确编号定位内容，仅创建待确认操作。"""
        if event.user_id not in self.settings.media_admins:
            return '权限不足'
        if event.reply_id is not None:
            with users.connect() as connection:
                item = connection.execute('''SELECT keyword, item_number FROM collection_messages
                    WHERE group_id=? AND message_id=? AND expires_at>?''',
                    (event.group_id, event.reply_id, time.time())).fetchone()
            if item is None:
                return '这条消息没有可用的收藏记录，请使用编号删除'
            identifier = f"{item['keyword']}-{item['item_number']}"
            if target.strip() not in ('', item['keyword'], identifier):
                return '引用的内容不属于这个关键词'
            key, number = item['keyword'], item['item_number']
        else:
            key, separator, value = target.strip().rpartition('-')
            if not separator or not value.isascii() or not value.isdigit() or int(value) < 1:
                return '请引用机器人发出的内容发送 删除关键词，或发送 删除关键词-编号'
            key, number = self.validate_keyword(key), int(value)
            identifier = f'{key}-{number}'
        with users.connect() as connection:
            if not connection.execute('SELECT 1 FROM collection_items WHERE keyword=? AND item_number=?', (key, number)).fetchone():
                return '对应内容已被删除'
        return self.request_confirmation('删除', identifier, [(key, number)], event)

    def request_clear(self, key, event):
        """列出当前关键词的编号，只为本次范围创建清空确认。"""
        if event.user_id not in self.settings.media_admins:
            return '权限不足'
        key = self.validate_keyword(key)
        with users.connect() as connection:
            items = [(key, row[0]) for row in connection.execute('SELECT item_number FROM collection_items WHERE keyword=?', (key,))]
        if not items:
            return '没有这个关键词'
        return self.request_confirmation('清空', key, items, event)

    def request_confirmation(self, action, target, items, event):
        """记录该群该管理员的最新操作范围，要求明确确认或取消。"""
        now = time.time()
        with users.connect() as connection:
            connection.execute('DELETE FROM collection_confirmations WHERE expires_at<=?', (now,))
            connection.execute('INSERT OR REPLACE INTO collection_confirmations VALUES (?, ?, ?, ?, ?, ?)',
                (event.group_id, event.user_id, action, target, json.dumps(items, ensure_ascii=False), now + self.CONFIRMATION_SECONDS))
        detail = f'{target}（共 {len(items)} 项）' if action == '清空' else target
        return f'即将{action} {detail}。\n请在 {self.CONFIRMATION_SECONDS} 秒内发送 @bot 确认{action} {target}；放弃请发送 @bot 取消删除。'

    def confirm(self, action, target, event):
        """原管理员在原群确认指定操作；一次消费，过期及不匹配时不执行。"""
        if event.user_id not in self.settings.media_admins:
            return '权限不足'
        with users.connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            pending = connection.execute('SELECT * FROM collection_confirmations WHERE group_id=? AND user_id=?',
                                         (event.group_id, event.user_id)).fetchone()
            if pending is None:
                return '没有待确认的删除操作'
            if pending['expires_at'] <= time.time():
                connection.execute('DELETE FROM collection_confirmations WHERE group_id=? AND user_id=?', (event.group_id, event.user_id))
                return '确认已过期，请重新发起删除'
            if pending['action'] != action or pending['target'] != target.strip():
                return '确认内容与待处理操作不一致，请检查编号或关键词'
            connection.execute('DELETE FROM collection_confirmations WHERE group_id=? AND user_id=?', (event.group_id, event.user_id))
        results = [self.delete(f'{key}-{number}', event.user_id) for key, number in json.loads(pending['items'])]
        return results[0] if action == '删除' else f'清空成功：{target.strip()}'

    def cancel(self, event):
        """取消该群中由当前用户发起的待确认操作。"""
        with users.connect() as connection:
            cursor = connection.execute('DELETE FROM collection_confirmations WHERE group_id=? AND user_id=?', (event.group_id, event.user_id))
        return '已取消删除' if cursor.rowcount else '没有待确认的删除操作'

    def add(self, key, reply_id):
        """保存被回复消息的内容，成功后返回简短提示。"""
        key = self.validate_keyword(key)
        parts = segments(self.client.get_message(reply_id).get('message'))
        attachments = [part for part in parts if part.get('type') in ('image', 'video', 'file', 'record')]
        if attachments:
            kind, item = attachments[0]['type'], attachments[0]['data']
            url = str(item.get('url', '')).replace('&amp;', '&')
            if not url.startswith(('https://', 'http://')):
                return '被回复的文件没有可下载地址'
            suffix = Path(str(item.get('file', ''))).suffix.lower()
            if not suffix[1:].isalnum() or len(suffix) > 12:
                suffix = {'image': '.jpg', 'video': '.mp4', 'record': '.mp3', 'file': '.bin'}[kind]
            response = requests.get(quote(url, safe=':/?&=%'), timeout=self.settings.request_timeout)
            response.raise_for_status()
            content = response.content
        else:
            kind, suffix = 'text', '.txt'
            text = ''.join(str(part['data'].get('text', '')) for part in parts if part.get('type') == 'text')
            if not text.strip():
                return '被回复的消息没有可保存的内容'
            content = text.encode('utf-8')
        with users.connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            number = self.next_number(connection, key)
        object_key = f'{key}/{number}{suffix}'
        self.cloud.put(object_key, content)
        with users.connect() as connection:
            connection.execute("""INSERT INTO collection_items
                (keyword, item_number, kind, object_key) VALUES (?, ?, ?, ?)""",
                (key, number, kind, object_key))
        return '添加成功'

    def delete(self, identifier, user_id):
        """管理员按固定编号删除文件，无需引用原消息。"""
        if user_id not in self.settings.media_admins:
            return '权限不足'
        key, separator, number = identifier.strip().rpartition('-')
        if not separator or not number.isascii() or not number.isdigit() or int(number) < 1:
            return '请发送 @bot 删除关键词-编号，例如 删除bjg-12'
        key = self.validate_keyword(key)
        with users.connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            item = connection.execute('SELECT object_key FROM collection_items WHERE keyword=? AND item_number=?',
                                      (key, int(number))).fetchone()
            if item is None:
                return '未找到对应编号'
            self.cloud.delete(item['object_key'])
            connection.execute('DELETE FROM collection_items WHERE keyword=? AND item_number=?', (key, int(number)))
        return f'删除成功：{key}-{int(number)}'
