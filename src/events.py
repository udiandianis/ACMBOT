import html
import re
from dataclasses import dataclass


def segments(message):
    """将消息数组或 CQ 字符串转换为统一的消息段列表。"""
    if isinstance(message, list):
        return [segment for segment in message if isinstance(segment, dict) and isinstance(segment.get('data'), dict)]
    if not isinstance(message, str):
        return []
    result, offset = [], 0
    for match in re.finditer(r'\[CQ:([^,\]]+)((?:,[^\]]*)?)\]', message):
        if match.start() > offset:
            result.append({'type': 'text', 'data': {'text': html.unescape(message[offset:match.start()])}})
        fields = dict(field.split('=', 1) for field in match[2].lstrip(',').split(',') if '=' in field)
        result.append({'type': match[1], 'data': {key: html.unescape(value) for key, value in fields.items()}})
        offset = match.end()
    if offset < len(message):
        result.append({'type': 'text', 'data': {'text': html.unescape(message[offset:])}})
    return result


@dataclass(frozen=True)
class GroupMessage:
    group_id: int
    user_id: int
    message_id: int | None
    text: str
    mentions: tuple[int, ...]
    reply_id: int | None
    role: str
    raw: dict

    @classmethod
    def parse(cls, data):
        """解析群事件的文本、提及和回复；无效或非群事件返回 None。"""
        if data.get('message_type') != 'group':
            return None
        sender = data.get('sender') or {}
        if not isinstance(sender, dict):
            return None
        parts = segments(data.get('message'))
        try:
            group_id = int(data['group_id'])
            user_id = int(data.get('user_id', sender.get('user_id')))
            message_id = int(data['message_id']) if data.get('message_id') is not None else None
            mentions = tuple(int(segment['data']['qq']) for segment in parts if segment.get('type') == 'at'
                             and str(segment['data'].get('qq', '')).isdigit())
            reply_id = next((int(segment['data']['id']) for segment in parts if segment.get('type') == 'reply'), None)
        except (KeyError, ValueError, TypeError):
            return None
        text = ''.join(str(segment['data'].get('text', '')) for segment in parts if segment.get('type') == 'text').strip()
        normalized = dict(data, message=parts, sender=dict(sender, user_id=user_id))
        return cls(group_id, user_id, message_id, text, mentions, reply_id, sender.get('role', 'member'), normalized)
