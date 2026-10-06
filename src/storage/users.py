from contextlib import contextmanager
import sqlite3
from src.paths import DATA_DIRECTORY

DB_PATH = DATA_DIRECTORY / 'bot.db'
USER_FIELDS = (
    'qq_id', 'name', 'class_name', 'enrollment_year', 'duel_available', 'bot_rating',
    'nowcoder_handle', 'codeforces_handle', 'luogu_username', 'atcoder_handle',
    'chaoxing_credentials', 'assigned_problem', 'assigned_at',
)
BINDING_FIELDS = {
    'name': 'name', 'class': 'class_name', 'chaoxing': 'chaoxing_credentials',
    'codeforces': 'codeforces_handle', 'nowcoder': 'nowcoder_handle',
    'luogu': 'luogu_username', 'atcoder': 'atcoder_handle',
}


@contextmanager
def connect():
    """提供事务连接上下文；退出时提交或回滚并关闭连接。"""
    connection = sqlite3.connect(str(DB_PATH), timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA journal_mode=WAL')
    connection.execute('PRAGMA busy_timeout=30000')
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def init_db():
    """创建用户与题库表，保留已有数据。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as connection:
        connection.execute('''CREATE TABLE IF NOT EXISTS users (
            qq_id INTEGER PRIMARY KEY, name TEXT, class_name TEXT, enrollment_year INTEGER,
            duel_available INTEGER DEFAULT 1, bot_rating INTEGER DEFAULT 0,
            nowcoder_handle TEXT, codeforces_handle TEXT, luogu_username TEXT,
            atcoder_handle TEXT, chaoxing_credentials TEXT,
            assigned_problem TEXT, assigned_at REAL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
        columns = {row['name'] for row in connection.execute('PRAGMA table_info(users)')}
        for field, field_type in (('class_name', 'TEXT'), ('enrollment_year', 'INTEGER')):
            if field not in columns:
                connection.execute(f'ALTER TABLE users ADD COLUMN {field} {field_type}')
        connection.execute('''CREATE TABLE IF NOT EXISTS codeforces_problems (
            contest_id INTEGER NOT NULL,
            problem_index TEXT NOT NULL,
            rating INTEGER NOT NULL,
            PRIMARY KEY (contest_id, problem_index))''')
        connection.execute('CREATE INDEX IF NOT EXISTS codeforces_problems_rating ON codeforces_problems (rating)')
        connection.execute('''CREATE TABLE IF NOT EXISTS luogu_training_problems (
            training_id INTEGER NOT NULL, problem_id TEXT NOT NULL,
            PRIMARY KEY (training_id, problem_id))''')


def ensure_user(qq_id):
    """确保用户记录存在，重复调用不覆盖已有字段。"""
    with connect() as connection:
        connection.execute('INSERT INTO users (qq_id) VALUES (?) ON CONFLICT(qq_id) DO NOTHING', (int(qq_id),))


def get_user(qq_id):
    """按 QQ 号返回用户字典；未找到时返回 None。"""
    with connect() as connection:
        row = connection.execute('SELECT * FROM users WHERE qq_id=?', (int(qq_id),)).fetchone()
    return dict(row) if row else None


def get_user_field(qq_id, field):
    """验证字段名称并返回用户字段值，未找到时返回 None。"""
    if field not in USER_FIELDS:
        raise ValueError('未知用户字段: ' + field)
    user = get_user(qq_id)
    return user.get(field) if user else None


def update_user_fields(qq_id, **fields):
    """验证字段后事务性更新用户资料，不允许修改 QQ 主键。"""
    if any(field not in USER_FIELDS or field == 'qq_id' for field in fields):
        raise ValueError('未知或不可修改的用户字段')
    if not fields:
        return
    ensure_user(qq_id)
    assignments = ', '.join(field + '=?' for field in fields)
    with connect() as connection:
        connection.execute(f'UPDATE users SET {assignments},updated_at=CURRENT_TIMESTAMP WHERE qq_id=?',
                           (*fields.values(), int(qq_id)))


def update_user_field(qq_id, field, value):
    """更新单个用户字段，不存在的用户会先创建。"""
    update_user_fields(qq_id, **{field: value})


def list_users():
    """按 QQ 号排序返回所有用户字典。"""
    with connect() as connection:
        return [dict(row) for row in connection.execute('SELECT * FROM users ORDER BY qq_id')]
