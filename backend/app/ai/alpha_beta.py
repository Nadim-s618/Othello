"""Alpha-Beta pruning strategy for selecting an Othello move."""

from __future__ import annotations

from math import inf

from ..game import BLACK, WHITE, apply_move, legal_moves, opponent
from .minimax import (
    Board,
    _evaluate,
    _ordered_moves,
    _terminal_score,
)


def choose_move(board: Board, player: str, depth: int = 3) -> dict[str, int] | None:
    """Choose a move using Minimax with Alpha-Beta pruning.

    The evaluation function and move ordering match the Minimax strategy, so
    the two algorithms can be compared fairly while Alpha-Beta searches fewer
    branches.
    """
    if player not in (BLACK, WHITE):
        raise ValueError("Player must be 'B' or 'W'.")
    if depth < 1:
        raise ValueError("Search depth must be at least 1.")

    moves = _ordered_moves(board, player)
    if not moves:
        return None

    best_move = moves[0]
    best_score = -inf
    alpha = -inf
    beta = inf

    for move in moves:
        next_board = apply_move(board, move[0], move[1], player)
        score = _alpha_beta(next_board, opponent(player), player, depth - 1, alpha, beta)
        if score > best_score:
            best_score = score
            best_move = move
        alpha = max(alpha, best_score)

    return {"row": best_move[0], "col": best_move[1]}


def alpha_beta_score(board: Board, player: str, depth: int = 3) -> float:
    """Return the Alpha-Beta search score from ``player``'s perspective."""
    if player not in (BLACK, WHITE):
        raise ValueError("Player must be 'B' or 'W'.")
    if depth < 0:
        raise ValueError("Search depth cannot be negative.")
    return _alpha_beta(board, player, player, depth, -inf, inf)


def _alpha_beta(
    board: Board,
    current_player: str,
    root_player: str,
    depth: int,
    alpha: float,
    beta: float,
) -> float:
    current_moves = legal_moves(board, current_player)
    other_player = opponent(current_player)

    # A player with no legal move passes without consuming a search ply. If
    # neither player can move, the position is terminal.
    if not current_moves:
        if not legal_moves(board, other_player):
            return _terminal_score(board, root_player)
        return _alpha_beta(board, other_player, root_player, depth, alpha, beta)

    if depth == 0:
        return _evaluate(board, root_player)

    if current_player == root_player:
        value = -inf
        for move in _ordered_moves(board, current_player):
            next_board = apply_move(board, move[0], move[1], current_player)
            value = max(value, _alpha_beta(next_board, other_player, root_player, depth - 1, alpha, beta))
            alpha = max(alpha, value)
            if alpha >= beta:
                break
        return value

    value = inf
    for move in _ordered_moves(board, current_player):
        next_board = apply_move(board, move[0], move[1], current_player)
        value = min(value, _alpha_beta(next_board, other_player, root_player, depth - 1, alpha, beta))
        beta = min(beta, value)
        if alpha >= beta:
            break
    return value
