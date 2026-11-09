from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from dotenv import load_dotenv

PROJECT_DATA_DIR = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_DATA_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
USING_POSTGRES = DATABASE_URL.startswith(("postgres://", "postgresql://"))

if os.getenv("VERCEL") and not USING_POSTGRES:
    raise RuntimeError("DATABASE_URL must be configured for the deployed application.")

DEFAULT_DATA_DIR = Path("/tmp/othello") if os.getenv("VERCEL") else PROJECT_DATA_DIR
DATA_DIR = Path(os.getenv("OTHELLO_DATA_DIR", str(DEFAULT_DATA_DIR)))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_PATH = DATA_DIR / "othello.db"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> Any:
    if USING_POSTGRES:
        import psycopg
        from psycopg.rows import dict_row

        return psycopg.connect(
            DATABASE_URL,
            row_factory=dict_row,
            connect_timeout=10,
            prepare_threshold=None,
        )

    connection = sqlite3.connect(DATABASE_PATH, timeout=5.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def placeholder() -> str:
    return "%s" if USING_POSTGRES else "?"


@contextmanager
def connection_scope() -> Iterator[Any]:
    """Open one database connection, commit or roll back, then always close it."""
    connection = connect()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db() -> None:
    with connection_scope() as connection:
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
        if USING_POSTGRES:
            connection.execute(
                "ALTER TABLE games ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 0"
            )
        else:
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(games)")}
            if "version" not in columns:
                connection.execute("ALTER TABLE games ADD COLUMN version INTEGER NOT NULL DEFAULT 0")


def create_game(game_id: str, board: list[list[str]], current_player: str, message: str) -> dict[str, Any]:
    timestamp = utc_now()
    mark = placeholder()
    with connection_scope() as connection:
        connection.execute(
            f"""
            INSERT INTO games (id, board, current_player, status, winner, last_message, created_at, updated_at)
            VALUES ({mark}, {mark}, {mark}, 'active', NULL, {mark}, {mark}, {mark})
            """,
            (game_id, json.dumps(board), current_player, message, timestamp, timestamp),
        )
    return get_game(game_id)


def get_game(game_id: str) -> dict[str, Any] | None:
    mark = placeholder()
    with connection_scope() as connection:
        row = connection.execute(f"SELECT * FROM games WHERE id = {mark}", (game_id,)).fetchone()
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
    mark = placeholder()
    with connection_scope() as connection:
        cursor = connection.execute(
            f"""
            UPDATE games
            SET board = {mark}, current_player = {mark}, status = {mark}, winner = {mark}, last_message = {mark}, updated_at = {mark}, version = version + 1
            WHERE id = {mark} AND version = {mark}
            """,
            (json.dumps(board), current_player, status, winner, message, utc_now(), game_id, expected_version),
        )
        if cursor.rowcount != 1:
            return None
    return get_game(game_id)
