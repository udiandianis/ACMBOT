from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / 'config' / 'bot_settings.json'
RESOURCE_DIRECTORY = PROJECT_ROOT / 'resources'
DATA_DIRECTORY = RESOURCE_DIRECTORY / 'data'
IMAGE_RESOURCES = RESOURCE_DIRECTORY / 'images'
REPORT_DIRECTORY = PROJECT_ROOT / 'output' / 'reports'
CHECKIN_DIRECTORY = PROJECT_ROOT / 'output' / 'checkin_calendars'
