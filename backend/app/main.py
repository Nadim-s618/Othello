from __future__ import annotations

import uuid
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .db import USING_POSTGRES, create_game, get_game, init_db, update_game
from .ai.alpha_beta import choose_move as choose_alpha_beta_move
from .ai.genetic_algorithm import choose_move as choose_genetic_move
from .ai.greedy import choose_move as choose_greedy_move
from .ai.hill_climbing import choose_move as choose_hill_climbing_move
from .ai.minimax import choose_move
from .game import (
    BLACK,
    WHITE,
    apply_move,
    disc_counts,
    initial_board,
    legal_moves,
    resolve_next_turn,
    winner_for,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Othello API", version="1.0.0", lifespan=lifespan)

configured_origins = [
    origin.strip()
    for origin in os.getenv("FRONTEND_ORIGINS", "").split(",")
    if origin.strip()
]
if not configured_origins:
    configured_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=configured_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# All search-based strategies use the same depth for fair comparisons.
COMPARISON_SEARCH_DEPTH = 3


class MoveRequest(BaseModel):
    row: int = Field(ge=0, le=7)
    col: int = Field(ge=0, le=7)


class AIMoveRequest(BaseModel):
    strategy: str = "minimax"


def public_game(game: dict) -> dict:
    board = game["board"]
    counts = disc_counts(board)
    return {
        "id": game["id"],
        "board": board,
        "current_player": game["current_player"],
        "status": game["status"],
        "winner": game["winner"],
        "last_message": game["last_message"],
        "counts": counts,
        "legal_moves": legal_moves(board, game["current_player"]) if game["status"] == "active" else [],
        "created_at": game["created_at"],
        "updated_at": game["updated_at"],
    }


def require_game(game_id: str) -> dict:
    game = get_game(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found.")
    return game


def save_game(
    game: dict,
    board: list[list[str]],
    current_player: str,
    status: str,
    winner: str | None,
    message: str,
) -> dict:
    """Persist a move only if the game version is still current."""
    updated = update_game(
        game["id"],
        board,
        current_player,
        status,
        winner,
        message,
        expected_version=game["version"],
    )
    if updated is None:
        raise HTTPException(
            status_code=409,
            detail="This game changed before your move was saved. Refresh the game and try again.",
        )
    return public_game(updated)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "database": "postgresql" if USING_POSTGRES else "sqlite",
    }


@app.post("/api/games", status_code=201)
def new_game() -> dict:
    game = create_game(str(uuid.uuid4()), initial_board(), BLACK, "Black moves first.")
    return public_game(game)


@app.get("/api/games/{game_id}")
def read_game(game_id: str) -> dict:
    return public_game(require_game(game_id))


@app.get("/api/games/{game_id}/hint")
def game_hint(game_id: str) -> dict:
    """Return the strongest recommended move without changing the game."""
    game = require_game(game_id)
    if game["status"] != "active":
        return {
            "strategy": "alpha_beta",
            "player": game["current_player"],
            "move": None,
            "message": "The game is over. No further move is recommended.",
        }

    player = game["current_player"]
    move = choose_alpha_beta_move(game["board"], player, COMPARISON_SEARCH_DEPTH)
    if move is None:
        return {
            "strategy": "alpha_beta",
            "player": player,
            "move": None,
            "message": f"{player} has no legal move and should pass.",
        }

    notation = f"{chr(move['col'] + 65)}{move['row'] + 1}"
    return {
        "strategy": "alpha_beta",
        "player": player,
        "move": {**move, "notation": notation},
        "message": f"Alpha-Beta recommends {notation} for {player}.",
    }


@app.post("/api/games/{game_id}/moves")
def play_move(game_id: str, move: MoveRequest) -> dict:
    game = require_game(game_id)
    if game["status"] != "active":
        raise HTTPException(status_code=409, detail="This game is already over.")

    player = game["current_player"]
    if not legal_moves(game["board"], player):
        raise HTTPException(status_code=409, detail=f"{player} has no legal moves; pass the turn.")

    try:
        board = apply_move(game["board"], move.row, move.col, player)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    resolution = resolve_next_turn(board, player)
    return save_game(
        game,
        board,
        resolution.current_player,
        resolution.status,
        resolution.winner,
        resolution.message,
    )


@app.post("/api/games/{game_id}/pass")
def pass_turn(game_id: str) -> dict:
    game = require_game(game_id)
    if game["status"] != "active":
        raise HTTPException(status_code=409, detail="This game is already over.")

    player = game["current_player"]
    if legal_moves(game["board"], player):
        raise HTTPException(status_code=409, detail="A legal move is available; the turn cannot be passed.")

    other_player = WHITE if player == BLACK else BLACK
    if legal_moves(game["board"], other_player):
        return save_game(
            game,
            game["board"],
            other_player,
            "active",
            None,
            f"{player} passed. {other_player} to move.",
        )
    else:
        return save_game(
            game,
            game["board"],
            player,
            "finished",
            winner_for(game["board"]),
            "Both players have no legal moves. Game over.",
        )


@app.post("/api/games/{game_id}/ai-move")
def play_ai_move(game_id: str, request: AIMoveRequest) -> dict:
    """Apply one computer move for the current player.

    The strategy is supplied by the client for now; game configuration
    persistence can be added later.
    """
    game = require_game(game_id)
    if game["status"] != "active":
        raise HTTPException(status_code=409, detail="This game is already over.")
    if request.strategy not in ("greedy", "minimax", "alpha_beta", "hill_climbing", "genetic_algorithm"):
        raise HTTPException(status_code=501, detail="Only Greedy, Minimax, Alpha-Beta, Hill Climbing, and Genetic Algorithm AI are connected yet.")

    player = game["current_player"]
    if request.strategy == "greedy":
        strategy_label = "Greedy AI"
        move = choose_greedy_move(game["board"], player)
    elif request.strategy == "hill_climbing":
        strategy_label = "Hill Climbing AI"
        move = choose_hill_climbing_move(game["board"], player, COMPARISON_SEARCH_DEPTH)
    elif request.strategy == "genetic_algorithm":
        strategy_label = "Genetic Algorithm AI"
        move = choose_genetic_move(game["board"], player, COMPARISON_SEARCH_DEPTH)
    else:
        strategy_label = "Minimax"
        search = choose_move
        if request.strategy == "alpha_beta":
            strategy_label = "Alpha-Beta"
            search = choose_alpha_beta_move
        move = search(game["board"], player, COMPARISON_SEARCH_DEPTH)
    if move is None:
        other_player = WHITE if player == BLACK else BLACK
        if legal_moves(game["board"], other_player):
            return save_game(
                game,
                game["board"],
                other_player,
                "active",
                None,
                f"{player} has no legal moves. Turn passed to {other_player}.",
            )
        else:
            return save_game(
                game,
                game["board"],
                player,
                "finished",
                winner_for(game["board"]),
                "Both players have no legal moves. Game over.",
            )

    board = apply_move(game["board"], move["row"], move["col"], player)
    resolution = resolve_next_turn(board, player)
    return save_game(
        game,
        board,
        resolution.current_player,
        resolution.status,
        resolution.winner,
        f"{strategy_label} (depth {COMPARISON_SEARCH_DEPTH}) played {chr(move['col'] + 65)}{move['row'] + 1}. {resolution.message}",
    )
