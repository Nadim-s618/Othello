"""Complete-game training for optimized Othello evaluation weights."""

from __future__ import annotations

from dataclasses import dataclass
from math import inf
from typing import Any

from ..game import (
    BLACK,
    WHITE,
    apply_move,
    disc_counts,
    initial_board,
    legal_moves,
    opponent,
    winner_for,
)
from .minimax import Board, POSITION_WEIGHTS, _ordered_moves, _terminal_score

TRAINING_DEPTH = 3
# A small live-training budget keeps the first optimized move responsive.
# The training method still plays complete matches with both colors.
TRAINING_GAMES = 2


@dataclass(frozen=True)
class MatchResult:
    winner: str
    counts: dict[str, int]
    plies: int


def evaluate_weights(
    candidate_weights: Any,
    baseline_weights: Any,
    games: int = TRAINING_GAMES,
    depth: int = TRAINING_DEPTH,
) -> float:
    """Evaluate candidates through complete weighted Alpha-Beta matches.

    The baseline weights are the same weights used by Minimax and Alpha-Beta,
    so optimized candidates are trained against the actual comparison player.
    Candidates play both colors and are scored primarily by wins and draws,
    with a small final-disc margin tie-breaker.
    """
    if games < 2 or games % 2 != 0:
        raise ValueError("Games must be an even number of at least 2.")
    if depth < 1:
        raise ValueError("Training depth must be at least 1.")

    wins = 0.0
    margin_total = 0.0
    colors = (BLACK, WHITE)
    for index in range(games):
        candidate_player = colors[index % 2]
        result = play_weighted_match(candidate_weights, baseline_weights, candidate_player, depth)
        if result.winner == candidate_player:
            wins += 1.0
        elif result.winner == "DRAW":
            wins += 0.5
        other_player = opponent(candidate_player)
        total_discs = max(1, result.counts[BLACK] + result.counts[WHITE])
        margin_total += (result.counts[candidate_player] - result.counts[other_player]) / total_discs

    win_rate = wins / games
    normalized_margin = (margin_total / games + 1.0) / 2.0
    return (0.9 * win_rate) + (0.1 * normalized_margin)


def play_weighted_match(
    candidate_weights: Any,
    baseline_weights: Any,
    candidate_player: str,
    depth: int = TRAINING_DEPTH,
    max_plies: int = 64,
) -> MatchResult:
    """Play a complete match using the same search depth as live gameplay."""
    board = initial_board()
    current_player = BLACK
    consecutive_passes = 0
    plies = 0

    while consecutive_passes < 2 and plies < max_plies:
        moves = legal_moves(board, current_player)
        if not moves:
            consecutive_passes += 1
            current_player = opponent(current_player)
            plies += 1
            continue

        consecutive_passes = 0
        weights = candidate_weights if current_player == candidate_player else baseline_weights
        move = _choose_weighted_move(board, current_player, weights, depth)
        if move is None:
            raise RuntimeError("Weighted player returned no move despite legal moves existing.")
        board = apply_move(board, move["row"], move["col"], current_player)
        current_player = opponent(current_player)
        plies += 1

    return MatchResult(winner_for(board), disc_counts(board), plies)


def _choose_weighted_move(
    board: Board,
    player: str,
    weights: Any,
    depth: int = TRAINING_DEPTH,
) -> dict[str, int] | None:
    moves = _ordered_moves(board, player)
    if not moves:
        return None

    best_move = moves[0]
    best_score = -inf
    alpha = -inf
    beta = inf
    for move in moves:
        next_board = apply_move(board, move[0], move[1], player)
        score = _weighted_alpha_beta(
            next_board,
            opponent(player),
            player,
            depth - 1,
            alpha,
            beta,
            weights,
        )
        if score > best_score:
            best_score = score
            best_move = move
        alpha = max(alpha, best_score)

    return {"row": best_move[0], "col": best_move[1]}


def _weighted_alpha_beta(
    board: Board,
    current_player: str,
    root_player: str,
    depth: int,
    alpha: float,
    beta: float,
    weights: Any,
) -> float:
    current_moves = legal_moves(board, current_player)
    other_player = opponent(current_player)

    if not current_moves:
        if not legal_moves(board, other_player):
            return _terminal_score(board, root_player)
        return _weighted_alpha_beta(board, other_player, root_player, depth, alpha, beta, weights)

    if depth == 0:
        return _evaluate(board, root_player, weights)

    if current_player == root_player:
        value = -inf
        for move in _ordered_moves(board, current_player):
            next_board = apply_move(board, move[0], move[1], current_player)
            value = max(value, _weighted_alpha_beta(next_board, other_player, root_player, depth - 1, alpha, beta, weights))
            alpha = max(alpha, value)
            if alpha >= beta:
                break
        return value

    value = inf
    for move in _ordered_moves(board, current_player):
        next_board = apply_move(board, move[0], move[1], current_player)
        value = min(value, _weighted_alpha_beta(next_board, other_player, root_player, depth - 1, alpha, beta, weights))
        beta = min(beta, value)
        if alpha >= beta:
            break
    return value


def _evaluate(board: Board, root_player: str, weights: Any) -> float:
    other_player = opponent(root_player)
    counts = disc_counts(board)
    piece_difference = counts[root_player] - counts[other_player]
    mobility_difference = len(legal_moves(board, root_player)) - len(legal_moves(board, other_player))
    corner_difference = _corner_count(board, root_player) - _corner_count(board, other_player)

    positional_difference = 0
    for row, board_row in enumerate(board):
        for col, cell in enumerate(board_row):
            if cell == root_player:
                positional_difference += POSITION_WEIGHTS[row][col]
            elif cell == other_player:
                positional_difference -= POSITION_WEIGHTS[row][col]

    return (
        weights.positional * positional_difference
        + weights.mobility * mobility_difference
        + weights.corners * corner_difference
        + weights.pieces * piece_difference
    )


def _corner_count(board: Board, player: str) -> int:
    last = len(board) - 1
    return sum(
        board[row][col] == player
        for row, col in ((0, 0), (0, last), (last, 0), (last, last))
    )
