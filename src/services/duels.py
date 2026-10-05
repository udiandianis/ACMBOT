import threading
import time
from src.storage import users
from . import practice


class DuelService:
    """持久化单挑邀请，在同一事务中更新状态和双方积分。"""
    def __init__(self):
        """初始化单挑数据表，已有单挑状态保持不变。"""
        self.lock = threading.RLock()
        users.init_db()
        with users.connect() as connection:
            connection.execute('''CREATE TABLE IF NOT EXISTS duels (
                duel_id INTEGER PRIMARY KEY, group_id INTEGER NOT NULL,
                challenger INTEGER NOT NULL, challenged INTEGER NOT NULL,
                rating INTEGER NOT NULL, status TEXT NOT NULL,
                contest_id INTEGER, problem_index TEXT, started_at REAL)''')

    def invite(self, group_id, challenger, challenged, rating):
        """校验绑定及参与状态，事务性创建待接受的单挑邀请。"""
        if challenger == challenged:
            return '不能挑战自己'
        if not 800 <= rating <= 3500 or rating % 100:
            return 'rating范围应该是800-3500之间的整百数'
        with self.lock, users.connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            participants = [connection.execute('SELECT * FROM users WHERE qq_id=?', (user_id,)).fetchone()
                            for user_id in (challenger, challenged)]
            if any(not participant or not participant['codeforces_handle'] for participant in participants):
                return '存在用户未绑定'
            busy = connection.execute('SELECT 1 FROM duels WHERE challenger IN (?, ?) OR challenged IN (?, ?)',
                                      (challenger, challenged, challenger, challenged)).fetchone()
            if busy or any(not participant['duel_available'] for participant in participants):
                return '存在用户有待处理的单挑或正在单挑中'
            connection.execute('INSERT INTO duels (group_id,challenger,challenged,rating,status) VALUES (?,?,?,?,?)',
                               (group_id, challenger, challenged, rating, 'pending'))
            return f'{participants[0]["codeforces_handle"]} 向 {participants[1]["codeforces_handle"]} 发起了挑战\n输入 #duel accept 接受，输入 #duel reject 拒绝'

    def execute(self, group_id, operation, user_id):
        """按邀请群和操作人验证权限后执行单挑操作。"""
        with self.lock:
            with users.connect() as connection:
                duel = connection.execute('SELECT * FROM duels WHERE group_id=? AND (challenger=? OR challenged=?)',
                                          (group_id, user_id, user_id)).fetchone()
            if operation == 'reset':
                with users.connect() as connection:
                    connection.execute('BEGIN IMMEDIATE')
                    related = connection.execute('SELECT challenger,challenged FROM duels WHERE challenger=? OR challenged=?',
                                                 (user_id, user_id)).fetchall()
                    participants = {user_id}
                    for record in related:
                        participants.update((record['challenger'], record['challenged']))
                    connection.execute('DELETE FROM duels WHERE challenger=? OR challenged=?', (user_id, user_id))
                    connection.execute('INSERT INTO users (qq_id) VALUES (?) ON CONFLICT(qq_id) DO NOTHING', (user_id,))
                    for participant in participants:
                        connection.execute('''UPDATE users SET duel_available=CASE WHEN EXISTS (
                            SELECT 1 FROM duels WHERE status='active' AND (challenger=? OR challenged=?)
                            ) THEN 0 ELSE 1 END,updated_at=CURRENT_TIMESTAMP WHERE qq_id=?''',
                            (participant, participant, participant))
                return '重置成功：已取消相关邀请或单挑，双方积分不变' if related else '重置成功'
            if not duel:
                return f'[CQ:at,qq={user_id}] 你没有正在进行中的duel'
            if operation in ('accept', 'reject'):
                if duel['status'] != 'pending':
                    return '单挑已经开始，请使用 #duel judge 结算'
                if duel['challenged'] != user_id:
                    return '只有被挑战者可以接受或拒绝邀请'
                return self.accept(duel) if operation == 'accept' else self.reject(duel)
            if operation == 'judge':
                return self.settle(duel) if duel['status'] == 'active' else '邀请尚未接受，请先接受或拒绝'
            raise ValueError('未知单挑操作')

    def reject(self, duel):
        """删除未接受的邀请，返回拒绝说明。"""
        with users.connect() as connection:
            connection.execute('DELETE FROM duels WHERE duel_id=? AND status=?', (duel['duel_id'], 'pending'))
        return f'[CQ:at,qq={duel["challenger"]}] 对方拒绝了你的挑战'

    def accept(self, duel):
        """分配题目并激活邀请，同时将双方标记为单挑中。"""
        contest_id, problem_index = practice.select_problem(duel['rating'])
        with users.connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            changed = connection.execute('UPDATE duels SET status=?,contest_id=?,problem_index=?,started_at=? WHERE duel_id=? AND status=?',
                ('active', contest_id, problem_index, time.time(), duel['duel_id'], 'pending')).rowcount
            if not changed:
                return '邀请状态已变化'
            connection.execute('UPDATE users SET duel_available=0 WHERE qq_id IN (?,?)', (duel['challenger'], duel['challenged']))
        challenger = users.get_user_field(duel['challenger'], 'codeforces_handle')
        challenged = users.get_user_field(duel['challenged'], 'codeforces_handle')
        return f'{challenged} 接受了 {challenger}的挑战\n题目链接：https://codeforces.com/problemset/problem/{contest_id}/{problem_index}'

    def settle(self, duel):
        """按首次 AC 判定胜者并事务性更新积分；抓取失败保留单挑。"""
        participants = [users.get_user(user_id) for user_id in (duel['challenger'], duel['challenged'])]
        accepted = [practice.accepted_submission(participant['codeforces_handle'], duel['contest_id'], duel['problem_index'], duel['started_at'])
                    for participant in participants]
        elapsed = [submission['creationTimeSeconds'] - duel['started_at'] if submission else float('inf') for submission in accepted]
        changes = [0, 0]
        if elapsed[0] == elapsed[1]:
            summary = '无人完成' if not any(accepted) else '双方同时完成'
        else:
            winner = 0 if elapsed[0] < elapsed[1] else 1
            reward = practice.score_change(duel['rating'], elapsed[winner])
            changes[winner], changes[1 - winner] = reward, -reward
            summary = f'{participants[winner]["codeforces_handle"]} 获胜，耗时：{time.strftime("%H:%M:%S", time.gmtime(elapsed[winner]))}'
        # 查询失败时保留单挑；状态和双方积分在同一事务中提交。
        with users.connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            if not connection.execute('SELECT 1 FROM duels WHERE duel_id=? AND status=?', (duel['duel_id'], 'active')).fetchone():
                return '单挑已经结算'
            score_lines = []
            for participant, delta in zip(participants, changes):
                current_rating = connection.execute('SELECT bot_rating FROM users WHERE qq_id=?', (participant['qq_id'],)).fetchone()['bot_rating'] or 0
                connection.execute('UPDATE users SET bot_rating=COALESCE(bot_rating,0)+?,duel_available=1,updated_at=CURRENT_TIMESTAMP WHERE qq_id=?', (delta, participant['qq_id']))
                score_lines.append(f'{participant["codeforces_handle"]}：{current_rating} + {delta} = {current_rating + delta}')
            connection.execute('DELETE FROM duels WHERE duel_id=?', (duel['duel_id'],))
        return summary + '\nrating变化如下：\n' + '\n'.join(score_lines)
