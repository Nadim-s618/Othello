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

To use PostgreSQL locally, copy `backend/.env.example` to `backend/.env` and
replace `DATABASE_URL` with your connection string. The backend loads this file
automatically when it starts. Keep `backend/.env` private; for Vercel, add the
same variables in the project environment settings instead.

## Run the frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the URL printed by Vite, usually <http://localhost:5173>.

For local development, `VITE_API_URL` is optional and defaults to
`http://127.0.0.1:8000/api`. For a deployed frontend, copy
`frontend/.env.example` to `frontend/.env.local`, set the deployed backend URL,
and configure the same `VITE_API_URL` in the frontend hosting provider before
building. Vite embeds this value at build time, so redeploy after changing it.

## Deploy on Vercel

This repository can be deployed as two Vercel projects from the same Git
repository:

### Backend project

- Root Directory: `backend`
- Framework preset: let Vercel detect FastAPI/Python
- Build Command: leave empty
- Output Directory: leave empty
- Start Command: leave empty

Vercel uses `backend/main.py` as the FastAPI entrypoint. After deployment,
verify `https://YOUR-BACKEND.vercel.app/api/health`.

Set this backend environment variable in Vercel, replacing the URL with the
deployed frontend URL:

```text
FRONTEND_ORIGINS=https://YOUR-FRONTEND.vercel.app
```

Also set a persistent PostgreSQL connection string:

```text
DATABASE_URL=postgresql://USER:PASSWORD@HOST/DATABASE?sslmode=require
```

Create this database with a provider such as Neon, Supabase, or Vercel
Postgres. The application creates its `games` table automatically on startup.

### Frontend project

- Root Directory: `frontend`
- Framework preset: Vite
- Build Command: `npm run build`
- Output Directory: `dist`

Set this frontend environment variable:

```text
VITE_API_URL=https://YOUR-BACKEND.vercel.app/api
```

The frontend and backend are separate deployments, so this variable is
required in production. Do not leave it pointing to `localhost` or
`127.0.0.1`.

SQLite remains available for local development. Vercel deployments require
`DATABASE_URL` so game state is stored in PostgreSQL rather than temporary
function storage.

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
