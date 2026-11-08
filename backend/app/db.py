from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_DATA_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = Path("/tmp/othello") if os.getenv("VERCEL") else PROJECT_DATA_DIR
DATA_DIR = Path(os.getenv("OTHELLO_DATA_DIR", str(DEFAULT_DATA_DIR)))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_PATH = DATA_DIR / "othello.db"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH, timeout=5.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def init_db() -> None:
    with connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS games (
                id TEXT PRIMARY KEY,
                board TEXT NOT NULL,
                current_player TEXT NOT NULL,
                status TEXT NOT NULL,
                winner TEXT,
                last_message TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(games)")}
        if "version" not in columns:
            connection.execute("ALTER TABLE games ADD COLUMN version INTEGER NOT NULL DEFAULT 0")


def create_game(game_id: str, board: list[list[str]], current_player: str, message: str) -> dict[str, Any]:
    timestamp = utc_now()
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO games (id, board, current_player, status, winner, last_message, created_at, updated_at)
            VALUES (?, ?, ?, 'active', NULL, ?, ?, ?)
            """,
            (game_id, json.dumps(board), current_player, message, timestamp, timestamp),
        )
    return get_game(game_id)


def get_game(game_id: str) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
    if row is None:
        return None
    game = dict(row)
    game["board"] = json.loads(game["board"])
    return game


def update_game(
    game_id: str,
    board: list[list[str]],
    current_player: str,
    status: str,
    winner: str | None,
    message: str,
    expected_version: int,
) -> dict[str, Any] | None:
    """Update a game only if it has not changed since it was read."""
    with connect() as connection:
        cursor = connection.execute(
            """
            UPDATE games
            SET board = ?, current_player = ?, status = ?, winner = ?, last_message = ?, updated_at = ?, version = version + 1
            WHERE id = ? AND version = ?
            """,
            (json.dumps(board), current_player, status, winner, message, utc_now(), game_id, expected_version),
        )
        if cursor.rowcount != 1:
            return None
    return get_game(game_id)
