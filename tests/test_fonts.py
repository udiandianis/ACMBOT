import tempfile
import unittest
import warnings
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from unittest.mock import patch
from PIL import Image
from src.fonts import font_for_text
from src.services import checkin, statistics, trainings

NICKNAME = '**Blืุu้๊eb็้er๎ryำ์**'


class FontRenderingTests(unittest.TestCase):
    def test_thai_nickname_has_complete_font(self):
        font = font_for_text(NICKNAME, 24)
        self.assertIsNotNone(font)
        self.assertEqual(Path(font.path).name, 'NotoSansThai.ttf')

    def test_checkin_with_mixed_name_and_repeat(self):
        with tempfile.TemporaryDirectory() as directory:
            event = {'sender': {'user_id': 42, 'nickname': '北极狗 ' + NICKNAME}}
            with patch.object(checkin, 'CHECKIN_DIRECTORY', Path(directory) / 'output' / 'checkin_calendars'):
                path = checkin.get_png(event)
                original = path.read_bytes()
                self.assertEqual(checkin.get_png(event).read_bytes(), original)
            with Image.open(path) as image:
                self.assertEqual(image.size[0], 600)
                self.assertLess(image.crop((10, 50, 590, 95)).convert('L').getextrema()[0], 100)
            self.assertFalse(path.with_suffix('.tmp.png').exists())

    def test_reports_with_mixed_name_have_no_missing_glyphs(self):
        name = '北极狗 ' + NICKNAME
        record = {'NAME': name, 'platforms': {'CF': {'accepted': 2, 'submitted': 3}},
                  'errors': [], 'accepted': 2, 'submitted': 3, 'rank': 1}
        progress = {'name': name, 'failed': False, 'total': 18,
                    'by_training': {key: 1 for key in trainings.TRAINING_LABELS}}
        with tempfile.TemporaryDirectory() as directory, warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter('always')
            destination = Path(directory) / 'reports'
            with patch.object(statistics, 'REPORT_DIRECTORY', destination), patch.object(statistics, 'collect_statistics', return_value=({}, [record])):
                statistics.get_png()
            user = {'name': name, 'luogu_username': 'test', 'class_name': '测试班级',
                    'enrollment_year': trainings.datetime.now(trainings.timezone(trainings.timedelta(hours=8))).year}
            with patch.object(trainings, 'REPORT_DIRECTORY', destination), patch.object(trainings.users, 'list_users', return_value=[user]), patch.object(trainings, 'load_training_problems', return_value={key: {'P1'} for key in trainings.TRAINING_LABELS}), patch.object(trainings, 'fetch_user_progress', return_value=progress):
                trainings.get_png()
            for filename in ('solve.png', 'luogu.png'):
                with Image.open(destination / filename) as image:
                    image.verify()
            self.assertFalse([str(w.message) for w in captured if 'Glyph' in str(w.message) and 'missing' in str(w.message)])
