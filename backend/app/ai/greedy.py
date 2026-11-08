"""Greedy Othello strategy.

The strategy chooses the legal move with the largest immediate disc gain.
Positional weights provide deterministic tie-breaking and prefer corners.
"""

from __future__ import annotations

from ..game import BLACK, WHITE, apply_move, disc_counts, legal_moves
from .minimax import POSITION_WEIGHTS, Board


def choose_move(board: Board, player: str) -> dict[str, int] | None:
    """Choose the legal move that flips the most discs immediately."""
    if player not in (BLACK, WHITE):
        raise ValueError("Player must be 'B' or 'W'.")

    moves = legal_moves(board, player)
    if not moves:
        return None

    current_count = disc_counts(board)[player]
    best_move = moves[0]
    best_score = None

    for move in moves:
        next_board = apply_move(board, move["row"], move["col"], player)
        immediate_gain = disc_counts(next_board)[player] - current_count
        positional_tiebreak = POSITION_WEIGHTS[move["row"]][move["col"]]
        score = (immediate_gain, positional_tiebreak)
        if best_score is None or score > best_score:
            best_score = score
            best_move = move

    return best_move
