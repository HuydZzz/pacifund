# Changelog

All notable changes to PaciFund are documented in this file.

## [2.0.0] — April 16, 2026 🚀

### Added
- **🔬 Full Backtest Engine** (`backend/backtest/engine.py`)
  - Simulate strategy performance on historical data
  - Configurable capital, time period, thresholds, and risk parameters
  - Parameter sweep for strategy optimization
  - Computes Sharpe, max drawdown, win rate, profit factor
  - Exports full equity curve and trade log

- **📊 Advanced Analytics Engine** (`backend/analytics/metrics.py`)
  - Institutional-grade performance metrics: Sharpe, Sortino, Calmar ratios
  - Max drawdown duration tracking
  - Per-pair performance breakdown
  - Hourly profit distribution analysis
  - Strategy health score (0-100)

- **🔌 Bybit Exchange Integration** (`backend/collectors/bybit_collector.py`)
  - Third data source expands arb opportunities
  - 7 trading pairs monitored across all exchanges
  - Now monitoring: Pacifica × Binance × Bybit = 3x more spreads

- **🔔 Notification System** (`backend/notifications.py`)
  - In-app toast notifications via WebSocket
  - Telegram bot integration
  - Discord webhook support
  - 5 pre-built templates: signal, execution, stop-loss, take-profit, risk

- **⚙️ Live Settings Panel** (frontend)
  - Adjust capital, thresholds, risk parameters in real-time
  - Toggle exchanges on/off
  - Test Pacifica API connection
  - All settings persist across scans

- **📈 Dashboard Enhancements**
  - New Backtest view with interactive charts
  - New Analytics view with health scoring
  - Funding rate heatmap (7 pairs × 3 exchanges)
  - Exchange spread ranking
  - Pacifica volume contribution tracker (shows impact to Pacifica)
  - Live P&L updates every 2 seconds
  - Trade history view with full event log

- **🎨 UI/UX Improvements**
  - Redesigned hero section with live APY display
  - Professional navigation between 4 views
  - Gradient ambient backgrounds
  - Smooth animations and transitions
  - Toast notifications for all events
  - Auto-mode with confidence-based execution

### Changed
- Configuration now uses sliders for all numeric parameters (better UX)
- Scan interval now adjustable 5-120 seconds
- Max position size range expanded to 5-50%
- Supporting 7 pairs instead of 5

### Performance
- Scanner response time: ~500ms (down from 600ms)
- Dashboard supports 100+ concurrent positions
- Live updates at 2Hz with no lag

---

## [1.0.0] — April 12, 2026 🎉

### Initial Release
- Core arbitrage scanner (Pacifica × Binance)
- Position sizer with quarter-Kelly criterion
- Risk manager with stop-loss and exposure limits
- Pacifica executor via REST API
- FastAPI backend with REST + WebSocket
- React dashboard with Recharts
- Docker deployment
- GitHub Pages demo

---

## Roadmap (Post-Hackathon)

### v2.1 (Planned)
- [ ] Hyperliquid integration (4 exchanges)
- [ ] ML-based confidence scoring
- [ ] Portfolio optimization (correlation-aware sizing)
- [ ] Multi-account support

### v3.0 (Vision)
- [ ] Fully on-chain execution via Pacifica smart contracts
- [ ] Copy-trading: subscribe to top performers
- [ ] Mobile app (iOS + Android)
- [ ] Institutional API for hedge funds
