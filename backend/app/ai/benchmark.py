"""Round-robin helpers for fair AI strategy comparisons."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from ..game import BLACK, WHITE, apply_move, disc_counts, initial_board, legal_moves, opponent, winner_for
from .alpha_beta import choose_move as choose_alpha_beta_move
from .genetic_algorithm import choose_move as choose_genetic_move
from .greedy import choose_move as choose_greedy_move
from .hill_climbing import choose_move as choose_hill_climbing_move
from .minimax import Board, choose_move as choose_minimax_move
from .training import MatchResult

MoveChooser = Callable[..., dict[str, int] | None]
STRATEGY_CHOOSERS: dict[str, MoveChooser] = {
    "greedy": choose_greedy_move,
    "minimax": choose_minimax_move,
    "alpha_beta": choose_alpha_beta_move,
    "hill_climbing": choose_hill_climbing_move,
    "genetic_algorithm": choose_genetic_move,
}


def play_strategy_match(
    black_strategy: str,
    white_strategy: str,
    depth: int = 3,
    max_plies: int = 64,
) -> MatchResult:
    """Play one complete match with the requested strategies as each color."""
    _validate_strategy(black_strategy)
    _validate_strategy(white_strategy)
    if depth < 1:
        raise ValueError("Search depth must be at least 1.")

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
        strategy = black_strategy if current_player == BLACK else white_strategy
        chooser = STRATEGY_CHOOSERS[strategy]
        move = chooser(board, current_player) if strategy == "greedy" else chooser(board, current_player, depth)
        if move is None:
            raise RuntimeError("Strategy returned no move despite legal moves existing.")
        board = apply_move(board, move["row"], move["col"], current_player)
        current_player = opponent(current_player)
        plies += 1

    return MatchResult(winner_for(board), disc_counts(board), plies)


def benchmark_against(
    strategies: Iterable[str] = tuple(STRATEGY_CHOOSERS),
    opponent_strategy: str = "minimax",
    games: int = 4,
    depth: int = 3,
) -> dict[str, dict[str, float | int]]:
    """Compare strategies against one fixed opponent over alternating colors."""
    _validate_strategy(opponent_strategy)
    if games < 2 or games % 2 != 0:
        raise ValueError("Games must be an even number of at least 2.")

    report: dict[str, dict[str, float | int]] = {}
    for strategy in strategies:
        _validate_strategy(strategy)
        wins = draws = losses = 0
        for index in range(games):
            candidate_is_black = index % 2 == 0
            result = play_strategy_match(
                strategy if candidate_is_black else opponent_strategy,
                opponent_strategy if candidate_is_black else strategy,
                depth,
            )
            candidate_color = BLACK if candidate_is_black else WHITE
            if result.winner == candidate_color:
                wins += 1
            elif result.winner == "DRAW":
                draws += 1
            else:
                losses += 1
        report[strategy] = {
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "win_rate": wins / games,
            "score_rate": (wins + (0.5 * draws)) / games,
        }
    return report


def _validate_strategy(strategy: str) -> None:
    if strategy not in STRATEGY_CHOOSERS:
        raise ValueError(f"Unknown strategy: {strategy}")

