"""Genetic Algorithm optimized Alpha-Beta strategy for Othello."""

from __future__ import annotations

import random
from dataclasses import replace
from functools import lru_cache
from math import inf

from ..game import BLACK, WHITE, apply_move, legal_moves, opponent
from .hill_climbing import (
    BASE_WEIGHTS,
    WEIGHT_BOUNDS,
    WEIGHT_STEPS,
    EvaluationWeights,
    _alpha_beta,
)
from .minimax import Board, _ordered_moves
from .training import TRAINING_DEPTH, TRAINING_GAMES, evaluate_weights
from .weight_store import load_weights, save_weights


GENE_FIELDS = tuple(WEIGHT_STEPS)


def choose_move(board: Board, player: str, depth: int = 3) -> dict[str, int] | None:
    """Choose a move using evolved weights and Alpha-Beta search."""
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


def optimize_weights(
    board: Board,
    player: str,
    generations: int = 1,
    population_size: int = 4,
    mutation_rate: float = 0.25,
) -> EvaluationWeights:
    """Evolve evaluation weights with selection, crossover, and mutation.

    The optimizer is deterministic for a player and configuration, which keeps
    local matches reproducible while still providing population-based search.
    """
    if player not in (BLACK, WHITE):
        raise ValueError("Player must be 'B' or 'W'.")
    if generations < 0:
        raise ValueError("Generations cannot be negative.")
    if population_size < 4:
        raise ValueError("Population size must be at least 4.")
    if not 0 <= mutation_rate <= 1:
        raise ValueError("Mutation rate must be between 0 and 1.")
    return _evolve_complete_games(player, generations, population_size, mutation_rate, TRAINING_GAMES)


@lru_cache(maxsize=4)
def _evolve_complete_games(
    player: str,
    generations: int,
    population_size: int,
    mutation_rate: float,
    training_games: int,
) -> EvaluationWeights:
    saved = load_weights("genetic_algorithm", player)
    if saved is not None:
        return EvaluationWeights(**saved)

    rng = random.Random(_seed_for_player(player))
    population = [BASE_WEIGHTS]
    population.extend(_random_candidate(rng) for _ in range(population_size - 1))

    for _ in range(generations):
        ranked = sorted(
            ((_fitness(candidate, training_games), candidate) for candidate in population),
            key=lambda item: item[0],
            reverse=True,
        )
        elite_count = max(2, population_size // 4)
        elites = [candidate for _, candidate in ranked[:elite_count]]
        next_population = elites[:]

        while len(next_population) < population_size:
            parent_a = rng.choice(elites)
            parent_b = rng.choice(elites)
            child = _crossover(parent_a, parent_b, rng)
            child = _mutate(child, rng, mutation_rate)
            next_population.append(child)
        population = next_population

    best = max(population, key=lambda candidate: _fitness(candidate, training_games))
    save_weights("genetic_algorithm", player, best)
    return best


@lru_cache(maxsize=256)
def _fitness(weights: EvaluationWeights, training_games: int) -> float:
    return evaluate_weights(weights, BASE_WEIGHTS, training_games, TRAINING_DEPTH)


def _random_candidate(rng: random.Random) -> EvaluationWeights:
    return EvaluationWeights(
        **{
            field: rng.uniform(*WEIGHT_BOUNDS[field])
            for field in GENE_FIELDS
        }
    )


def _crossover(
    parent_a: EvaluationWeights,
    parent_b: EvaluationWeights,
    rng: random.Random,
) -> EvaluationWeights:
    genes = {}
    for field in GENE_FIELDS:
        first = getattr(parent_a, field)
        second = getattr(parent_b, field)
        ratio = rng.random()
        genes[field] = (first * ratio) + (second * (1 - ratio))
    return EvaluationWeights(**genes)


def _mutate(
    candidate: EvaluationWeights,
    rng: random.Random,
    mutation_rate: float,
) -> EvaluationWeights:
    genes = {}
    for field in GENE_FIELDS:
        value = getattr(candidate, field)
        if rng.random() < mutation_rate:
            value += rng.uniform(-WEIGHT_STEPS[field], WEIGHT_STEPS[field])
        lower, upper = WEIGHT_BOUNDS[field]
        genes[field] = min(upper, max(lower, value))
    return replace(candidate, **genes)


def _seed_for_player(player: str) -> int:
    return 17_431 if player == BLACK else 17_432
