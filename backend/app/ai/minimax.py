"""Minimax strategy for selecting an Othello move.

The search is intentionally independent from FastAPI so it can be reused by
an API endpoint, a single-player game service, or future strategy comparisons.
"""

from __future__ import annotations

from math import inf

from ..game import BLACK, WHITE, apply_move, disc_counts, legal_moves, opponent

Board = list[list[str]]
Move = tuple[int, int]

# Stable Othello positional weights. Corners are valuable; squares next to a
# corner are dangerous early in the game because they can give the opponent
# access to that corner.
POSITION_WEIGHTS = (
    (120, -20, 20, 5, 5, 20, -20, 120),
    (-20, -40, -5, -5, -5, -5, -40, -20),
    (20, -5, 15, 3, 3, 15, -5, 20),
    (5, -5, 3, 3, 3, 3, -5, 5),
    (5, -5, 3, 3, 3, 3, -5, 5),
    (20, -5, 15, 3, 3, 15, -5, 20),
    (-20, -40, -5, -5, -5, -5, -40, -20),
    (120, -20, 20, 5, 5, 20, -20, 120),
)

DEFAULT_DEPTHS = {
    "easy": 2,
    "medium": 3,
    "hard": 5,
}


def depth_for_difficulty(difficulty: str) -> int:
    """Return a safe search depth for the UI difficulty labels."""
    try:
        return DEFAULT_DEPTHS[difficulty.lower()]
    except KeyError as error:
        raise ValueError("Difficulty must be easy, medium, or hard.") from error


def choose_move(board: Board, player: str, depth: int = 3) -> dict[str, int] | None:
    """Choose the best move for ``player`` using depth-limited Minimax.

    Returns a JSON-friendly ``{"row": ..., "col": ...}`` object, or ``None``
    when the player has no legal move and must pass.
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
    for move in moves:
        next_board = apply_move(board, move[0], move[1], player)
        score = _minimax(next_board, opponent(player), player, depth - 1)
        if score > best_score:
            best_score = score
            best_move = move

    return {"row": best_move[0], "col": best_move[1]}


def minimax_score(board: Board, player: str, depth: int = 3) -> float:
    """Return the position score from ``player``'s perspective.

    This is useful for debugging, visualizing, and comparing strategies.
    """
    if player not in (BLACK, WHITE):
        raise ValueError("Player must be 'B' or 'W'.")
    if depth < 0:
        raise ValueError("Search depth cannot be negative.")
    return _minimax(board, player, player, depth)


def _minimax(board: Board, current_player: str, root_player: str, depth: int) -> float:
    current_moves = legal_moves(board, current_player)
    other_player = opponent(current_player)

    # A player with no move passes. If the opponent also has no move, the game
    # is over regardless of the requested search depth.
    if not current_moves:
        if not legal_moves(board, other_player):
            return _terminal_score(board, root_player)
        return _minimax(board, other_player, root_player, depth)

    if depth == 0:
        return _evaluate(board, root_player)

    scores = []
    for move in _ordered_moves(board, current_player):
        next_board = apply_move(board, move[0], move[1], current_player)
        scores.append(_minimax(next_board, other_player, root_player, depth - 1))

    return max(scores) if current_player == root_player else min(scores)


def _ordered_moves(board: Board, player: str) -> list[Move]:
    """Search corners and strong positional moves first for stable choices."""
    moves = [(move["row"], move["col"]) for move in legal_moves(board, player)]
    return sorted(moves, key=lambda move: POSITION_WEIGHTS[move[0]][move[1]], reverse=True)


def _evaluate(board: Board, root_player: str) -> float:
    other_player = opponent(root_player)
    counts = disc_counts(board)
    piece_difference = counts[root_player] - counts[other_player]

    root_moves = len(legal_moves(board, root_player))
    other_moves = len(legal_moves(board, other_player))
    mobility_difference = root_moves - other_moves

    root_corners = _corner_count(board, root_player)
    other_corners = _corner_count(board, other_player)
    corner_difference = root_corners - other_corners

    positional_score = 0
    for row, board_row in enumerate(board):
        for col, cell in enumerate(board_row):
            if cell == root_player:
                positional_score += POSITION_WEIGHTS[row][col]
            elif cell == other_player:
                positional_score -= POSITION_WEIGHTS[row][col]

    return (
        positional_score
        + (12 * mobility_difference)
        + (80 * corner_difference)
        + (2 * piece_difference)
    )


def _terminal_score(board: Board, root_player: str) -> float:
    counts = disc_counts(board)
    difference = counts[root_player] - counts[opponent(root_player)]
    if difference > 0:
        return 1_000_000 + difference
    if difference < 0:
        return -1_000_000 + difference
    return 0


def _corner_count(board: Board, player: str) -> int:
    last = len(board) - 1
    return sum(
        board[row][col] == player
        for row, col in ((0, 0), (0, last), (last, 0), (last, last))
    )
