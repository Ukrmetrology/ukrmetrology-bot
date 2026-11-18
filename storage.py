import json
import sqlite3


class Store:
    def __init__(self, path):
        self.path = path
        with self.conn() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS applications(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    payload TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    contract TEXT
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS manager_modes(
                    user_id INTEGER PRIMARY KEY,
                    app_id INTEGER
                )"""
            )

    def conn(self):
        return sqlite3.connect(self.path)

    def create(self, data):
        with self.conn() as connection:
            cursor = connection.execute(
                "INSERT INTO applications(payload, status) VALUES(?, ?)",
                (json.dumps(data, ensure_ascii=False), "pending"),
            )
            app_id = cursor.lastrowid
            saved = dict(data)
            saved["id"] = app_id
            connection.execute(
                "UPDATE applications SET payload=? WHERE id=?",
                (json.dumps(saved, ensure_ascii=False), app_id),
            )
            return app_id

    def update(self, app_id, data):
        with self.conn() as connection:
            saved = dict(data)
            saved["id"] = app_id
            connection.execute(
                "UPDATE applications SET payload=? WHERE id=?",
                (json.dumps(saved, ensure_ascii=False), app_id),
            )

    def get(self, app_id):
        with self.conn() as connection:
            row = connection.execute(
                "SELECT id, payload FROM applications WHERE id=?",
                (app_id,),
            ).fetchone()
            if not row:
                return None
            data = json.loads(row[1])
            data["id"] = row[0]
            return data

    def set_status(self, app_id, status):
        with self.conn() as connection:
            connection.execute(
                "UPDATE applications SET status=? WHERE id=?",
                (status, app_id),
            )

    def set_contract(self, app_id, path):
        with self.conn() as connection:
            connection.execute(
                "UPDATE applications SET contract=? WHERE id=?",
                (path, app_id),
            )

    def get_contract(self, app_id):
        with self.conn() as connection:
            row = connection.execute(
                "SELECT contract FROM applications WHERE id=?",
                (app_id,),
            ).fetchone()
            return row[0] if row else None

    def set_manager_mode(self, user_id, app_id):
        with self.conn() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO manager_modes VALUES(?, ?)",
                (user_id, app_id),
            )

    def get_manager_mode(self, user_id):
        with self.conn() as connection:
            row = connection.execute(
                "SELECT app_id FROM manager_modes WHERE user_id=?",
                (user_id,),
            ).fetchone()
            return row[0] if row else None

    def clear_manager_mode(self, user_id):
        with self.conn() as connection:
            connection.execute(
                "DELETE FROM manager_modes WHERE user_id=?",
                (user_id,),
            )
