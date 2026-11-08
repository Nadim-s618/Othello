import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000/api'

const AI_OPTIONS = [
  ['greedy', 'Greedy AI', 'Beginner', 'Selects the best immediate move'],
  ['minimax', 'Minimax AI', 'Intermediate', 'Searches future moves using Minimax'],
  ['alpha_beta', 'Alpha-Beta AI', 'Advanced', 'Uses Alpha-Beta pruning to improve search efficiency'],
  ['hill_climbing', 'Hill Climbing Optimized AI', 'Optimized', 'Minimax + Alpha-Beta with Hill Climbing optimized weights'],
  ['genetic_algorithm', 'Genetic Algorithm Optimized AI', 'Optimized', 'Minimax + Alpha-Beta with Genetic Algorithm optimized weights'],
]

const AI_DETAILS = Object.fromEntries(
  AI_OPTIONS.map(([value, label, level]) => [value, { label, level }]),
)

async function api(path, options = {}) {
  let response
  try {
    response = await fetch(`${API_URL}${path}`, {
      headers: { 'Content-Type': 'application/json', ...options.headers },
      ...options,
    })
  } catch {
    throw new Error('Cannot connect to the game server. Start FastAPI on port 8000 and retry.')
  }
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(payload.detail ?? 'Something went wrong.')
  return payload
}

function Disc({ value }) {
  return value === '.' ? null : <span className={`disc ${value === 'B' ? 'black' : 'white'}`} />
}

function App() {
  const [mode, setMode] = useState(null)
  const [aiPlayer, setAiPlayer] = useState('minimax')
  const [singleGameStarted, setSingleGameStarted] = useState(false)
  const [tournamentBlack, setTournamentBlack] = useState('minimax')
  const [tournamentWhite, setTournamentWhite] = useState('alpha_beta')
  const [tournamentStarted, setTournamentStarted] = useState(false)
  const [game, setGame] = useState(null)
  const [hint, setHint] = useState(null)
  const [hintLoading, setHintLoading] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const tournamentMoveInFlight = useRef(false)
  const aiReady = aiPlayer === 'greedy' || aiPlayer === 'minimax' || aiPlayer === 'alpha_beta' || aiPlayer === 'hill_climbing' || aiPlayer === 'genetic_algorithm'
  const aiLabel = AI_DETAILS[aiPlayer].label
  const aiLevel = AI_DETAILS[aiPlayer].level

  function applyNavigationState(screen) {
    if (screen === 'home') {
      setMode(null)
      setSingleGameStarted(false)
      setTournamentStarted(false)
    } else if (screen === 'single-setup') {
      setMode('single')
      setSingleGameStarted(false)
      setTournamentStarted(false)
    } else if (screen === 'single-game') {
      setMode('single')
      setSingleGameStarted(true)
      setTournamentStarted(false)
    } else if (screen === 'multiplayer-game') {
      setMode('multiplayer')
      setSingleGameStarted(false)
      setTournamentStarted(false)
    } else if (screen === 'tournament-setup') {
      setMode('tournament')
      setSingleGameStarted(false)
      setTournamentStarted(false)
    } else if (screen === 'tournament-game') {
      setMode('tournament')
      setSingleGameStarted(false)
      setTournamentStarted(true)
    }
  }

  function navigateTo(screen) {
    window.history.pushState(
      { ...window.history.state, othello: { screen } },
      '',
      `${window.location.pathname}${window.location.search}${window.location.hash}`,
    )
    applyNavigationState(screen)
  }

  useEffect(() => {
    const currentScreen = window.history.state?.othello?.screen
    if (!currentScreen) {
      window.history.replaceState(
        { ...window.history.state, othello: { screen: 'home' } },
        '',
        `${window.location.pathname}${window.location.search}${window.location.hash}`,
      )
    } else {
      applyNavigationState(currentScreen)
    }

    function handlePopState(event) {
      const screen = event.state?.othello?.screen
      if (screen) applyNavigationState(screen)
    }

    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [])

  useEffect(() => {
    let cancelled = false
    if (!game || game.status !== 'active') {
      setHint(null)
      setHintLoading(false)
      return () => { cancelled = true }
    }

    setHint(null)
    setHintLoading(true)
    api(`/games/${game.id}/hint`)
      .then(nextHint => {
        if (!cancelled) setHint(nextHint)
      })
      .catch(() => {
        if (!cancelled) setHint({ message: 'Tip unavailable right now.' })
      })
      .finally(() => {
        if (!cancelled) setHintLoading(false)
      })

    return () => { cancelled = true }
  }, [game?.id, game?.updated_at, game?.current_player, game?.status])

  const startGame = useCallback(async () => {
    setBusy(true)
    setError('')
    setSingleGameStarted(false)
    setTournamentStarted(false)
    try {
      setGame(await api('/games', { method: 'POST' }))
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setBusy(false)
    }
  }, [])

  function selectMode(selectedMode) {
    setError('')
    setGame(null)
    const screen = selectedMode === 'single'
      ? 'single-setup'
      : selectedMode === 'tournament' ? 'tournament-setup' : 'multiplayer-game'
    navigateTo(screen)
    if (selectedMode === 'multiplayer') startGame()
  }

  async function startSingleGame() {
    if (!aiReady) return
    setBusy(true)
    setError('')
    setTournamentStarted(false)
    try {
      setGame(await api('/games', { method: 'POST' }))
      navigateTo('single-game')
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setBusy(false)
    }
  }

  async function runAiMove(currentGame) {
    return api(`/games/${currentGame.id}/ai-move`, {
      method: 'POST',
      body: JSON.stringify({ strategy: aiPlayer }),
    })
  }

  async function startTournament() {
    setBusy(true)
    setError('')
    try {
      setGame(await api('/games', { method: 'POST' }))
      navigateTo('tournament-game')
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setBusy(false)
    }
  }

  // Tournament games are fully automatic: the current side's selected AI
  // gets one move, then the updated game state triggers the next turn.
  useEffect(() => {
    if (mode !== 'tournament' || !tournamentStarted || !game || game.status !== 'active' || busy || tournamentMoveInFlight.current) return
    const strategy = game.current_player === 'B' ? tournamentBlack : tournamentWhite
    tournamentMoveInFlight.current = true
    setBusy(true)
    api(`/games/${game.id}/ai-move`, {
      method: 'POST',
      body: JSON.stringify({ strategy }),
    })
      .then(setGame)
      .catch((requestError) => setError(requestError.message))
      .finally(() => {
        tournamentMoveInFlight.current = false
        setBusy(false)
      })
  }, [mode, tournamentStarted, game?.id, game?.updated_at, game?.status, game?.current_player, tournamentBlack, tournamentWhite])

  const legalSet = useMemo(
    () => new Set((game?.legal_moves ?? []).map(({ row, col }) => `${row}-${col}`)),
    [game],
  )

  async function play(row, col) {
    if (!game || busy || game.status !== 'active' || !legalSet.has(`${row}-${col}`)) return
    setBusy(true)
    setError('')
    try {
      const humanGame = await api(`/games/${game.id}/moves`, {
        method: 'POST',
        body: JSON.stringify({ row, col }),
      })
      setGame(humanGame)
      if (mode === 'single' && humanGame.status === 'active' && humanGame.current_player === 'W') {
        setGame(await runAiMove(humanGame))
      }
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setBusy(false)
    }
  }

  async function pass() {
    if (!game || busy) return
    setBusy(true)
    setError('')
    try {
      const passedGame = await api(`/games/${game.id}/pass`, { method: 'POST' })
      setGame(passedGame)
      if (mode === 'single' && passedGame.status === 'active' && passedGame.current_player === 'W') {
        setGame(await runAiMove(passedGame))
      }
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setBusy(false)
    }
  }

  const currentLabel = game?.current_player === 'B' ? 'Black' : 'White'
  const noMoves = game?.status === 'active' && game.legal_moves.length === 0
  const blackPlayerLabel = mode === 'tournament'
    ? AI_DETAILS[tournamentBlack].label
    : mode === 'single' ? 'You' : 'Player 1'
  const whitePlayerLabel = mode === 'tournament'
    ? AI_DETAILS[tournamentWhite].label
    : mode === 'single' ? aiLabel : 'Player 2'
  const winnerLabel = game?.winner === 'DRAW'
    ? 'Draw'
    : game?.winner === 'B'
      ? `Black wins · ${blackPlayerLabel}`
      : `White wins · ${whitePlayerLabel}`
  const winnerName = game?.winner === 'B' ? blackPlayerLabel : game?.winner === 'W' ? whitePlayerLabel : 'Draw'
  const winnerColor = game?.winner === 'B' ? 'Black' : game?.winner === 'W' ? 'White' : null

  function backToPreviousSetup() {
    setError('')
    navigateTo(mode === 'single' ? 'single-setup' : mode === 'tournament' ? 'tournament-setup' : 'home')
  }

  if (!mode) {
    return (
      <main className="page-shell mode-page home-page">
        <section className="hero">
          <p className="eyebrow">Classic strategy · choose your game</p>
          <h1>Othello</h1>
          <p className="subtitle">How would you like to play?</p>
        </section>
        <section className="mode-grid" aria-label="Choose game mode">
          <button className="mode-card" onClick={() => selectMode('single')}>
            <span className="mode-icon">◉</span>
            <span className="mode-title">Single Player</span>
            <span className="mode-description">Challenge the computer</span>
            <span className="mode-status">5 AI strategies</span>
          </button>
          <button className="mode-card featured" onClick={() => selectMode('multiplayer')}>
            <span className="mode-icon">◉◉</span>
            <span className="mode-title">Multiplayer</span>
            <span className="mode-description">Play against another person</span>
            <span className="mode-status ready">Ready to play</span>
          </button>
          <button className="mode-card" onClick={() => selectMode('tournament')}>
            <span className="mode-icon">◉ vs ◉</span>
            <span className="mode-title">AI Tournament</span>
            <span className="mode-description">Compare AI strategies head-to-head</span>
            <span className="mode-status ready">Ready to play</span>
          </button>
        </section>
      </main>
    )
  }

  if (mode === 'tournament' && !tournamentStarted) {
    return (
      <main className="page-shell mode-page">
        <section className="hero">
          <p className="eyebrow">AI tournament</p>
          <h1>Choose your players</h1>
          <p className="subtitle">Select an AI strategy for Black and another for White.</p>
        </section>
        <section className="tournament-setup-card">
          <span className="mode-icon">◉ vs ◉</span>
          <h2>AI Tournament</h2>
          <p>Both players will move automatically using the same Othello rules and search depth.</p>
          <div className="tournament-players">
            <div className="tournament-picker">
              <span className="setup-label">Black AI</span>
              <div className="tournament-ai-options">
                {AI_OPTIONS.map(([value, label, level]) => (
                  <button
                    className={`tournament-ai-option ${tournamentBlack === value ? 'selected' : ''}`}
                    key={value}
                    type="button"
                    aria-pressed={tournamentBlack === value}
                    onClick={() => setTournamentBlack(value)}
                  >
                    <span>{label}</span><small>{level}</small>
                  </button>
                ))}
              </div>
            </div>
            <span className="versus">vs</span>
            <div className="tournament-picker">
              <span className="setup-label">White AI</span>
              <div className="tournament-ai-options">
                {AI_OPTIONS.map(([value, label, level]) => (
                  <button
                    className={`tournament-ai-option ${tournamentWhite === value ? 'selected' : ''}`}
                    key={value}
                    type="button"
                    aria-pressed={tournamentWhite === value}
                    onClick={() => setTournamentWhite(value)}
                  >
                    <span>{label}</span><small>{level}</small>
                  </button>
                ))}
              </div>
            </div>
          </div>
          <button className="start-ai-button" onClick={startTournament} disabled={busy}>
            {busy ? 'Starting tournament…' : 'Start tournament'}
          </button>
          <button className="text-button" onClick={() => navigateTo('home')}>Back to game modes</button>
        </section>
      </main>
    )
  }

  if (mode === 'single' && !singleGameStarted) {
    return (
      <main className="page-shell mode-page">
        <section className="hero">
          <p className="eyebrow">Single player · setup</p>
          <h1>Choose your opponent</h1>
          <p className="subtitle">Select an AI strategy and difficulty before starting your match.</p>
        </section>
        <section className="ai-setup-card">
          <div className="setup-section">
            <p className="setup-label">Choose AI player</p>
            <div className="ai-options">
              {AI_OPTIONS.map(([value, label, level, description]) => (
                <button
                  className={`ai-option ${aiPlayer === value ? 'selected' : ''}`}
                  key={value}
                  onClick={() => setAiPlayer(value)}
                >
                  <span className="ai-option-top"><span className="option-radio" />{label}<small>{level}</small></span>
                  <span className="ai-option-description">{description}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="setup-summary">
            <span>Selected opponent</span>
            <strong>{aiLabel} · {aiLevel}</strong>
          </div>
          {!aiReady && <p className="setup-note">This strategy is available for setup but not yet playable. All five AI strategies are connected.</p>}
          <button className="start-ai-button" onClick={startSingleGame} disabled={busy || !aiReady}>
            {busy ? 'Starting game…' : 'Start single-player game'}
          </button>
          <button className="text-button" onClick={() => navigateTo('home')}>Back to game modes</button>
        </section>
      </main>
    )
  }

  return (
    <main className="page-shell">
      <section className="hero">
        <p className="eyebrow">{mode === 'single' ? `Single player · ${aiLabel}` : mode === 'tournament' ? `AI Tournament · ${AI_DETAILS[tournamentBlack].label} vs ${AI_DETAILS[tournamentWhite].label}` : 'Classic strategy · local match'}</p>
        <h1>Othello</h1>
        <p className="subtitle">{mode === 'single' ? `You are Black. The ${aiLabel} computer plays White.` : mode === 'tournament' ? 'Watch two AI strategies compete automatically.' : 'Surround your opponent’s discs, flip the line, and own the board.'}</p>
        <button className="text-button change-mode" onClick={() => { setError(''); navigateTo('home') }}>Change game mode</button>
      </section>

      <section className="game-layout">
        <div className="game-column">
        <div className="matchup-card" aria-label="Player colors">
          <div className="matchup-player">
            <span className="matchup-disc black" />
            <span><small>BLACK</small><strong>{blackPlayerLabel}</strong></span>
          </div>
          <span className="matchup-vs">VS</span>
          <div className="matchup-player white-player">
            <span className="matchup-disc white" />
            <span><small>WHITE</small><strong>{whitePlayerLabel}</strong></span>
          </div>
        </div>

        <div className="board-status-row">
        <div className="tip-card" aria-live="polite">
          <p className="label">Next move tip</p>
          {hintLoading ? (
            <strong className="tip-thinking">Analyzing…</strong>
          ) : hint?.move ? (
            <>
              <strong className="tip-move">{hint.move.notation}</strong>
              <p>{hint.message}</p>
            </>
          ) : (
            <p>{hint?.message ?? 'Waiting for the board…'}</p>
          )}
          <small>Powered by Alpha-Beta search</small>
        </div>
        <div className="board-card">
          {game ? (
            <div className="board-wrap">
              <div className="axis top-axis">{[...Array(8)].map((_, index) => <span key={index}>{String.fromCharCode(65 + index)}</span>)}</div>
              <div className="board-row">
                <div className="axis side-axis">{[...Array(8)].map((_, index) => <span key={index}>{index + 1}</span>)}</div>
                <div className="board" role="grid" aria-label="Othello board">
                  {game.board.map((row, rowIndex) => row.map((cell, colIndex) => {
                    const isLegal = legalSet.has(`${rowIndex}-${colIndex}`)
                    return (
                      <button
                        className={`square ${isLegal ? 'legal' : ''}`}
                        key={`${rowIndex}-${colIndex}`}
                        onClick={() => play(rowIndex, colIndex)}
                        aria-label={`${String.fromCharCode(65 + colIndex)}${rowIndex + 1}${isLegal ? ', legal move' : ''}`}
                        disabled={mode === 'tournament' || !isLegal || busy || game.status !== 'active'}
                      >
                        <Disc value={cell} />
                        {isLegal && <span className="hint" />}
                      </button>
                    )
                  }))}
                </div>
              </div>
            </div>
          ) : (
            <div className="loading">
              {error ? (
                <>
                  <strong>Board unavailable</strong>
                  <span>{error}</span>
                  <button className="retry-button" onClick={mode === 'single' ? startSingleGame : startGame} disabled={busy}>Retry connection</button>
                </>
              ) : <span>Starting game…</span>}
            </div>
          )}
        </div>

        <aside className="side-panel">
          <div className="turn-card">
            <p className="label">{game?.status === 'finished' ? 'Final result' : 'Current turn'}</p>
            <div className="turn-line">
              <span className={`turn-disc ${game?.current_player === 'B' ? 'black' : 'white'}`} />
              <strong>{game?.status === 'finished' ? winnerLabel : mode === 'tournament' ? `${game.current_player === 'B' ? AI_DETAILS[tournamentBlack].label : AI_DETAILS[tournamentWhite].label} to move` : `${currentLabel} to move`}</strong>
            </div>
            <p className="message">{game?.last_message ?? 'Connecting to the game server…'}</p>
          </div>

          <div className="score-card">
            <div><span className="score-dot black" /><span className="score-name"><span>Black</span><small>{blackPlayerLabel}</small></span><strong>{game?.counts?.B ?? 2}</strong></div>
            <div><span className="score-dot white" /><span className="score-name"><span>White</span><small>{whitePlayerLabel}</small></span><strong>{game?.counts?.W ?? 2}</strong></div>
          </div>
        </aside>
        </div>

        <div className="below-board">
          <div className="actions">
            {mode !== 'tournament' && noMoves && <button className="pass-button" onClick={pass} disabled={busy}>Pass turn</button>}
            <button className="new-button" onClick={mode === 'single' ? startSingleGame : mode === 'tournament' ? startTournament : startGame} disabled={busy}>New game</button>
          </div>
          {error && <p className="error">{error}</p>}
          <p className="help">Click a glowing square to place a disc. A move is legal when it brackets one or more opposing discs.</p>
        </div>
        </div>
      </section>

      {game?.status === 'finished' && (
        <div className="winner-overlay" role="dialog" aria-modal="true" aria-labelledby="winner-title">
          <div className="winner-card">
            <span className="winner-spark" aria-hidden="true">✦</span>
            <p className="label">Game finished</p>
            <h2 id="winner-title">{winnerName}</h2>
            <p className="winner-result">
              {winnerColor ? `${winnerColor} wins` : 'The game ended in a draw'}
            </p>
            <div className="winner-score">
              <span>Black <strong>{game.counts.B}</strong></span>
              <span>White <strong>{game.counts.W}</strong></span>
            </div>
            <div className="winner-actions">
              <button className="winner-new-button" onClick={mode === 'single' ? startSingleGame : mode === 'tournament' ? startTournament : startGame}>New game</button>
              <button className="winner-back-button" onClick={backToPreviousSetup}>Back</button>
            </div>
          </div>
        </div>
      )}
    </main>
  )
}

export default App
