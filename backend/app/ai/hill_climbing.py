"""Hill-Climbing optimized Alpha-Beta strategy for Othello."""

from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache
from math import inf

from ..game import BLACK, WHITE, apply_move, disc_counts, legal_moves, opponent
from .minimax import POSITION_WEIGHTS, Board, _ordered_moves, _terminal_score
from .training import TRAINING_DEPTH, TRAINING_GAMES, evaluate_weights
from .weight_store import load_weights, save_weights


@dataclass(frozen=True)
class EvaluationWeights:
    positional: float = 1.0
    mobility: float = 12.0
    corners: float = 80.0
    pieces: float = 2.0


BASE_WEIGHTS = EvaluationWeights()
WEIGHT_STEPS = {
    "positional": 0.25,
    "mobility": 2.0,
    "corners": 10.0,
    "pieces": 0.5,
}
WEIGHT_BOUNDS = {
    "positional": (0.5, 2.5),
    "mobility": (4.0, 24.0),
    "corners": (40.0, 160.0),
    "pieces": (0.5, 6.0),
}


def choose_move(board: Board, player: str, depth: int = 3) -> dict[str, int] | None:
    """Choose a move with locally optimized weights and Alpha-Beta search."""
    if player not in (BLACK, WHITE):
        raise ValueError("Player must be 'B' or 'W'.")
    if depth < 1:
        raise ValueError("Search depth must be at least 1.")

    moves = _ordered_moves(board, player)
    if not moves:
        return None

    weights = optimize_weights(board, player)
    best_move = moves[0]
    best_score = -inf
    alpha = -inf
    beta = inf

    for move in moves:
        next_board = apply_move(board, move[0], move[1], player)
        score = _alpha_beta(next_board, opponent(player), player, depth - 1, alpha, beta, weights)
        if score > best_score:
            best_score = score
            best_move = move
        alpha = max(alpha, best_score)

    return {"row": best_move[0], "col": best_move[1]}


def optimize_weights(board: Board, player: str, iterations: int = 1) -> EvaluationWeights:
    """Hill-climb weights using complete matches against the baseline player."""
    if player not in (BLACK, WHITE):
        raise ValueError("Player must be 'B' or 'W'.")
    if iterations < 0:
        raise ValueError("Iterations cannot be negative.")
    return _optimize_complete_games(player, iterations, TRAINING_GAMES)


@lru_cache(maxsize=4)
def _optimize_complete_games(player: str, iterations: int, training_games: int) -> EvaluationWeights:
    saved = load_weights("hill_climbing", player)
    if saved is not None:
        return EvaluationWeights(**saved)

    current = BASE_WEIGHTS
    current_score = _fitness(player, current, training_games)
    fields = tuple(WEIGHT_STEPS)

    for _ in range(iterations):
        best = current
        best_score = current_score
        for field in fields:
            step = WEIGHT_STEPS[field]
            for direction in (-1, 1):
                candidate_value = getattr(current, field) + (direction * step)
                lower, upper = WEIGHT_BOUNDS[field]
                candidate_value = min(upper, max(lower, candidate_value))
                candidate = replace(current, **{field: candidate_value})
                candidate_score = _fitness(player, candidate, training_games)
                if candidate_score > best_score:
                    best = candidate
                    best_score = candidate_score
        if best == current:
            break
        current = best
        current_score = best_score

    save_weights("hill_climbing", player, current)
    return current


@lru_cache(maxsize=256)
def _fitness(player: str, weights: EvaluationWeights, training_games: int) -> float:
    return evaluate_weights(weights, BASE_WEIGHTS, training_games, TRAINING_DEPTH)


def _alpha_beta(
    board: Board,
    current_player: str,
    root_player: str,
    depth: int,
    alpha: float,
    beta: float,
    weights: EvaluationWeights,
) -> float:
    current_moves = legal_moves(board, current_player)
    other_player = opponent(current_player)

    if not current_moves:
        if not legal_moves(board, other_player):
            return _terminal_score(board, root_player)
        return _alpha_beta(board, other_player, root_player, depth, alpha, beta, weights)

    if depth == 0:
        return _evaluate(board, root_player, weights)

    if current_player == root_player:
        value = -inf
        for move in _ordered_moves(board, current_player):
            next_board = apply_move(board, move[0], move[1], current_player)
            value = max(value, _alpha_beta(next_board, other_player, root_player, depth - 1, alpha, beta, weights))
            alpha = max(alpha, value)
            if alpha >= beta:
                break
        return value

    value = inf
    for move in _ordered_moves(board, current_player):
        next_board = apply_move(board, move[0], move[1], current_player)
        value = min(value, _alpha_beta(next_board, other_player, root_player, depth - 1, alpha, beta, weights))
        beta = min(beta, value)
        if alpha >= beta:
            break
    return value


def _evaluate(board: Board, root_player: str, weights: EvaluationWeights) -> float:
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
