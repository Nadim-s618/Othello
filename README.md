# Othello

A small Human vs Human Othello game with a React/Vite frontend and a FastAPI/SQLite backend.

## Requirements

- Python 3.10+
- Node.js 18+

## Run the backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\\Scripts\\activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

If virtual-environment creation was interrupted, recreate it and wait for the command to finish:

```bash
cd backend
python3 -m venv --clear .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

The API runs at <http://127.0.0.1:8000>. The SQLite database is created automatically at `backend/othello.db`.

## Run the frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the URL printed by Vite, usually <http://localhost:5173>.

## API outline

- `POST /api/games` creates a game.
- `GET /api/games/{game_id}` returns the board, legal moves, turn, counts, and status.
- `POST /api/games/{game_id}/moves` with `{ "row": 2, "col": 3 }` plays a move.
- `POST /api/games/{game_id}/pass` passes when the current player has no legal move.

## AI strategy logic

- **Greedy AI:** chooses the legal move with the largest immediate disc gain; positional weights break ties.
- **Minimax AI:** searches future moves to a bounded depth and evaluates position, mobility, corners, and disc count.
- **Alpha-Beta AI:** uses the same Minimax evaluation while pruning branches that cannot improve the result.
- **Hill Climbing Optimized AI:** starts with base evaluation weights, generates nearby variations, tests them through complete Othello matches, measures win rate or match score, keeps better combinations, and repeats until the stopping condition. The resulting weights are used with Alpha-Beta search.
- **Genetic Algorithm Optimized AI:** evaluates candidates through multiple matches against fixed baseline opponents, uses win rate or tournament performance as fitness, applies selection, crossover, mutation, and elitism, and preserves the best-performing weight combination for Alpha-Beta search.

## Fair AI comparison

- Minimax and Alpha-Beta use the same heuristic weights and a fixed search depth of 3.
- Hill Climbing and Genetic Algorithm use their saved optimized weights with the same Alpha-Beta depth.
- Optimized weights are saved to `backend/optimized_weights.json` after training and loaded on later games.
- `backend/app/ai/benchmark.py` provides `benchmark_against()` to test every strategy against the same opponent over alternating-color games.
