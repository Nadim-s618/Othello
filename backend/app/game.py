from __future__ import annotations

from dataclasses import dataclass

BOARD_SIZE = 8
EMPTY = "."
BLACK = "B"
WHITE = "W"
DIRECTIONS = (
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1),            (0, 1),
    (1, -1),  (1, 0),   (1, 1),
)


class InvalidMove(ValueError):
    """Raised when a requested Othello move is not legal."""


def initial_board() -> list[list[str]]:
    board = [[EMPTY for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
    board[3][3] = WHITE
    board[3][4] = BLACK
    board[4][3] = BLACK
    board[4][4] = WHITE
    return board


def opponent(player: str) -> str:
    return WHITE if player == BLACK else BLACK


def in_bounds(row: int, col: int) -> bool:
    return 0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE


def flips_for_move(board: list[list[str]], row: int, col: int, player: str) -> list[tuple[int, int]]:
    if not in_bounds(row, col) or board[row][col] != EMPTY:
        return []

    other = opponent(player)
    flips: list[tuple[int, int]] = []
    for row_delta, col_delta in DIRECTIONS:
        candidate: list[tuple[int, int]] = []
        current_row, current_col = row + row_delta, col + col_delta
        while in_bounds(current_row, current_col) and board[current_row][current_col] == other:
            candidate.append((current_row, current_col))
            current_row += row_delta
            current_col += col_delta
        if candidate and in_bounds(current_row, current_col) and board[current_row][current_col] == player:
            flips.extend(candidate)
    return flips


def legal_moves(board: list[list[str]], player: str) -> list[dict[str, int]]:
    return [
        {"row": row, "col": col}
        for row in range(BOARD_SIZE)
        for col in range(BOARD_SIZE)
        if flips_for_move(board, row, col, player)
    ]


def apply_move(board: list[list[str]], row: int, col: int, player: str) -> list[list[str]]:
    flips = flips_for_move(board, row, col, player)
    if not flips:
        raise InvalidMove("That square is not a legal move.")

    next_board = [current_row[:] for current_row in board]
    next_board[row][col] = player
    for flip_row, flip_col in flips:
        next_board[flip_row][flip_col] = player
    return next_board


def disc_counts(board: list[list[str]]) -> dict[str, int]:
    return {
        BLACK: sum(cell == BLACK for row in board for cell in row),
        WHITE: sum(cell == WHITE for row in board for cell in row),
    }


def winner_for(board: list[list[str]]) -> str:
    counts = disc_counts(board)
    if counts[BLACK] == counts[WHITE]:
        return "DRAW"
    return BLACK if counts[BLACK] > counts[WHITE] else WHITE


@dataclass(frozen=True)
class TurnResolution:
    current_player: str
    status: str
    winner: str | None
    message: str


def resolve_next_turn(board: list[list[str]], player_who_moved: str) -> TurnResolution:
    next_player = opponent(player_who_moved)
    if legal_moves(board, next_player):
        return TurnResolution(next_player, "active", None, f"{next_player} to move.")

    if legal_moves(board, player_who_moved):
        return TurnResolution(
            player_who_moved,
            "active",
            None,
            f"{next_player} has no legal moves. Turn passed to {player_who_moved}.",
        )

    return TurnResolution(player_who_moved, "finished", winner_for(board), "No legal moves remain. Game over.")

