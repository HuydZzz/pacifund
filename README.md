# PaciFund — Funding Rate Arbitrage Scanner & Auto-Executor

> Built for the [Pacifica Hackathon 2025](https://pacifica.fi) · Tracks: Trading Bots + Analytics

<div align="center">
  
**Capture delta-neutral yield from funding rate spreads between Pacifica and other perps exchanges.**

[Live Demo](https://pacifund.vercel.app) · [API Docs](#api-endpoints) · [Architecture](#architecture)

</div>

---

## What is PaciFund?

PaciFund is a funding rate arbitrage tool that scans for spread differences between Pacifica and other perpetuals exchanges (Binance, Bybit, dYdX). When it finds a profitable spread:

1. **Detects** — Continuously monitors funding rates across exchanges
2. **Analyzes** — Calculates spread, estimates slippage/fees, scores confidence
3. **Sizes** — Uses quarter-Kelly criterion for optimal position sizing
4. **Executes** — Places delta-neutral trades via Pacifica API (long on low-rate exchange, short on high-rate exchange)
5. **Monitors** — Real-time P&L tracking, risk management, auto-close on target/stop-loss

**The result:** You collect the funding rate difference every 8 hours while being hedged against price movement.

### Why does this matter for Pacifica?

- **Brings volume** — Arb traders are the first power users of any new perps exchange
- **Improves pricing** — Arb activity pushes Pacifica's funding rates closer to market consensus
- **Attracts liquidity** — Where arb bots trade, market makers follow

---

## Quick start

### Option 1: Demo only (no backend needed)

The frontend dashboard works standalone with realistic simulated data:

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:3000
```

### Option 2: Full stack (with Pacifica API)

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env — add your PACIFICA_API_KEY

# 2. Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload

# 3. Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

### Option 3: Docker

```bash
cp .env.example .env
docker-compose up --build
# Open http://localhost:8000
```

---

## Architecture

```
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│ Pacifica API │  │ Binance API │  │ Bybit/dYdX  │
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘
       │                │                │
       └───────┬────────┴────────┬───────┘
               ▼                 │
      ┌─────────────────┐       │
      │  Rate Collector  │◄──────┘
      │  (async polling) │
      └────────┬────────┘
               ▼
      ┌─────────────────┐     ┌──────────────┐
      │   Arb Scanner   │────▶│ Dashboard API │
      │ (spread detect) │     │  (FastAPI)    │
      └────────┬────────┘     └──────┬───────┘
               ▼                     ▼
      ┌─────────────────┐     ┌──────────────┐
      │  Auto-Executor  │     │ React UI     │
      │ (Pacifica SDK)  │     │ (Recharts)   │
      └─────────────────┘     └──────────────┘
```

### Backend modules

| Module | File | Purpose |
|--------|------|---------|
| **Config** | `config.py` | Single source of truth for all settings |
| **Models** | `models.py` | Clean dataclasses: FundingRate, ArbSignal, Position |
| **Collectors** | `collectors/` | Fetch funding rates from Pacifica + Binance |
| **Arb Scanner** | `engine/arb_scanner.py` | Core logic: detect spreads, generate signals |
| **Position Sizer** | `engine/position_sizer.py` | Quarter-Kelly criterion sizing |
| **Risk Manager** | `executor/risk_manager.py` | Pre-trade checks, stop-loss, exposure limits |
| **Executor** | `executor/pacifica_executor.py` | Place/manage trades via Pacifica API |
| **API Routes** | `api/routes.py` | REST + WebSocket endpoints |

### Frontend

Single-page React dashboard with:
- **Stats cards** — P&L, funding collected, exposure, active signals
- **P&L chart** — 30-day cumulative performance (Recharts)
- **Spread chart** — Cross-exchange spread visualization
- **Signals table** — Live arb opportunities with one-click execute
- **Positions table** — Open/closed position tracking

---

## API endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Health check |
| `GET` | `/api/scan` | Trigger manual scan, returns rates + signals |
| `GET` | `/api/rates` | Current funding rates from all exchanges |
| `GET` | `/api/signals` | Active arbitrage signals |
| `POST` | `/api/execute/{signal_id}` | Execute a signal (opens position) |
| `GET` | `/api/positions` | All positions (filter by `?status=open`) |
| `POST` | `/api/positions/{id}/close` | Close a position |
| `GET` | `/api/portfolio` | Portfolio summary stats |
| `POST` | `/api/settings` | Update capital, auto-mode, min spread |
| `GET` | `/api/history` | Rate history + trade log |
| `WS` | `/api/ws` | WebSocket for live scan updates |

---

## How the arb strategy works

### The core idea

Funding rates are periodic payments between long and short traders in perpetual futures. When the funding rate differs between exchanges, you can:

- **LONG** on the exchange with the lower rate (you receive more / pay less)
- **SHORT** on the exchange with the higher rate (hedges your long)

This creates a **delta-neutral** position: you don't care about price movement, you just collect the spread.

### Example

| | Pacifica | Binance |
|---|---|---|
| BTC-PERP funding rate | -0.01% / 8h | +0.04% / 8h |
| **Action** | LONG (receive 0.01%) | SHORT (receive 0.04%) |
| **Spread** | 0.05% per 8h = **54.75% annualized** |

On a $10,000 position, that's ~$5 every 8 hours, ~$15/day, ~$450/month.

### Risk management

- **Kelly criterion** sizing (quarter-Kelly for safety)
- Max 25% of capital per position
- Max 40% concentration in any single pair
- Stop-loss at 2%, take-profit at 5%
- Max 10 open positions simultaneously
- Confidence scoring based on spread size + liquidity

---

## Tech stack

- **Backend:** Python 3.12, FastAPI, httpx (async HTTP)
- **Frontend:** React 18, Recharts, Vite
- **Pacifica:** Python SDK + REST API
- **Deployment:** Docker, or Vercel (frontend) + any VPS (backend)

---

## Project structure

```
pacifund/
├── backend/
│   ├── main.py                    # FastAPI entry point
│   ├── config.py                  # All settings
│   ├── models.py                  # Domain objects
│   ├── collectors/
│   │   ├── base_collector.py      # Abstract interface
│   │   ├── pacifica_collector.py  # Pacifica API/SDK
│   │   └── binance_collector.py   # Binance Futures API
│   ├── engine/
│   │   ├── arb_scanner.py         # Spread detection
│   │   └── position_sizer.py     # Kelly sizing
│   ├── executor/
│   │   ├── pacifica_executor.py   # Trade execution
│   │   └── risk_manager.py        # Risk checks
│   ├── api/
│   │   └── routes.py              # REST + WebSocket
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── main.jsx
│   │   └── App.jsx                # Full dashboard
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
├── .env.example
├── docker-compose.yml
├── Dockerfile
└── README.md
```

---

## Deploy frontend to Vercel (for demo)

```bash
cd frontend
npm run build
# Upload `dist/` to Vercel, Netlify, or GitHub Pages
```

The dashboard works standalone with simulated data — perfect for hackathon demo day.

---

## Hackathon submission

**Track:** Trading Applications & Bots + Analytics & Data  
**Team:** [Your team name]  
**Built with:** Pacifica API, Pacifica Python SDK, Pacifica Testnet

### Judging criteria alignment

| Criteria | How PaciFund delivers |
|----------|----------------------|
| **Innovation** | First native funding rate arb tool on Pacifica |
| **Technical Execution** | Clean architecture, async Python, real-time WebSocket |
| **User Experience** | Professional trading dashboard, one-click execution |
| **Potential Impact** | Directly drives volume and liquidity to Pacifica |
| **Presentation** | Live demo with real testnet data |

---

## License

MIT — built for [Pacifica Hackathon 2025](https://pacifica.fi)
