import sqlite3
from typing import List, Tuple


class Database:
    def __init__(self, db_path: str = "leaderboard.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS players (
                    user_id    INTEGER PRIMARY KEY,
                    name       TEXT    NOT NULL,
                    wins       INTEGER DEFAULT 0,
                    losses     INTEGER DEFAULT 0,
                    games      INTEGER DEFAULT 0,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def _upsert_player(self, conn, user_id: int, name: str):
        conn.execute("""
            INSERT INTO players (user_id, name) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET name = excluded.name
        """, (user_id, name))

    def record_win(self, user_id: int, name: str):
        with sqlite3.connect(self.db_path) as conn:
            self._upsert_player(conn, user_id, name)
            conn.execute("""
                UPDATE players
                SET wins = wins + 1,
                    games = games + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (user_id,))
            conn.commit()

    def record_loss(self, user_id: int, name: str):
        with sqlite3.connect(self.db_path) as conn:
            self._upsert_player(conn, user_id, name)
            conn.execute("""
                UPDATE players
                SET losses = losses + 1,
                    games = games + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (user_id,))
            conn.commit()

    def get_leaderboard(self, limit: int = 10) -> List[Tuple]:
        """Returns (name, wins, losses, games) sorted by wins desc."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT name, wins, losses, games
                FROM players
                WHERE games > 0
                ORDER BY wins DESC, games ASC
                LIMIT ?
            """, (limit,))
            return cursor.fetchall()

    def get_player_stats(self, user_id: int) -> dict | None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT name, wins, losses, games
                FROM players
                WHERE user_id = ?
            """, (user_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "name": row[0],
                "wins": row[1],
                "losses": row[2],
                "games": row[3],
                "winrate": round(row[1] / row[3] * 100) if row[3] > 0 else 0
            }
