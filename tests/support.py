import json
import tempfile
from functools import lru_cache
from pathlib import Path
from unittest.mock import patch
from src.settings import Settings


@lru_cache(maxsize=1)
def test_settings():
    """从示例创建虚构配置，测试不读取真实账号或访问外部服务。"""
    document = json.loads((Path(__file__).resolve().parents[1] / 'config/bot_settings.example.json').read_text(encoding='utf-8'))
    document['bot']['qq'] = 3661517915
    document['collections']['r2'].update(endpoint='https://example.invalid', bucket='test',
                                         access_key_id='test', secret_access_key='test')
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'bot_settings.json'
        path.write_text(json.dumps(document), encoding='utf-8')
        with patch('src.settings.CONFIG_PATH', path):
            return Settings.load()
