import { useState, useEffect, useCallback, useRef } from 'react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar, Cell,
} from 'recharts'

/* ───────── MOCK DATA ENGINE ───────── */
/* Generates realistic-looking data so the demo works standalone
   without the backend. When backend is live, swap with fetch() calls. */

const PAIRS = ['BTC-PERP', 'ETH-PERP', 'SOL-PERP', 'ARB-PERP', 'AVAX-PERP']
const EXCHANGES = ['pacifica', 'binance']

const rand = (min, max) => Math.random() * (max - min) + min

function generateRates() {
  return PAIRS.flatMap(pair =>
    EXCHANGES.map(ex => ({
      exchange: ex,
      pair,
      rate: (rand(-0.0005, 0.0008)).toFixed(6),
      rate_pct: '',
      annualized_pct: '',
      next_funding: new Date(Date.now() + rand(1, 8) * 3600000).toISOString(),
    }))
  ).map(r => ({
    ...r,
    rate: parseFloat(r.rate),
    rate_pct: (parseFloat(r.rate) * 100).toFixed(4) + '%',
    annualized_pct: (parseFloat(r.rate) * 100 * 3 * 365).toFixed(2) + '%',
  }))
}

function generateSignals(rates) {
  const signals = []
  for (const pair of PAIRS) {
    const pRates = rates.filter(r => r.pair === pair)
    const pac = pRates.find(r => r.exchange === 'pacifica')
    const bin = pRates.find(r => r.exchange === 'binance')
    if (!pac || !bin) continue

    const spread = Math.abs(pac.rate - bin.rate)
    if (spread < 0.00005) continue

    const longEx = pac.rate < bin.rate ? 'pacifica' : 'binance'
    const shortEx = pac.rate < bin.rate ? 'binance' : 'pacifica'

    signals.push({
      id: `sig_${Math.random().toString(36).slice(2, 10)}`,
      pair,
      long_exchange: longEx,
      short_exchange: shortEx,
      long_rate: Math.min(pac.rate, bin.rate),
      short_rate: Math.max(pac.rate, bin.rate),
      spread,
      spread_pct: (spread * 100).toFixed(4) + '%',
      annualized_yield: (spread * 3 * 365 * 100).toFixed(2) + '%',
      estimated_profit_8h: +(10000 * spread).toFixed(2),
      confidence: +rand(0.45, 0.95).toFixed(2),
      sizing: {
        recommended_size_usd: +(rand(500, 2500)).toFixed(0),
        leverage: [1, 1.5, 2][Math.floor(rand(0, 3))],
      },
    })
  }
  return signals.sort((a, b) => b.spread - a.spread)
}

function generatePnlHistory(days = 30) {
  let cumPnl = 0
  let cumFunding = 0
  return Array.from({ length: days }, (_, i) => {
    const dailyPnl = rand(-15, 45)
    const dailyFunding = rand(2, 20)
    cumPnl += dailyPnl
    cumFunding += dailyFunding
    const d = new Date()
    d.setDate(d.getDate() - (days - i))
    return {
      date: d.toLocaleDateString('en', { month: 'short', day: 'numeric' }),
      pnl: +cumPnl.toFixed(2),
      funding: +cumFunding.toFixed(2),
    }
  })
}

function generatePositions() {
  const statuses = ['open', 'open', 'open', 'closed', 'closed', 'closed', 'closed']
  return statuses.map((status, i) => {
    const pair = PAIRS[i % PAIRS.length]
    const pnl = +(rand(-30, 80)).toFixed(2)
    const size = +(rand(800, 3000)).toFixed(0)
    return {
      id: `pos_${Math.random().toString(36).slice(2, 10)}`,
      pair,
      long_exchange: Math.random() > 0.5 ? 'pacifica' : 'binance',
      short_exchange: Math.random() > 0.5 ? 'binance' : 'pacifica',
      size_usd: size,
      pnl_usd: pnl,
      funding_collected: +(rand(1, 25)).toFixed(2),
      total_return_pct: ((pnl / size) * 100).toFixed(2) + '%',
      status,
      opened_at: new Date(Date.now() - rand(1, 20) * 86400000).toISOString(),
    }
  })
}


/* ───────── STYLES ───────── */

const CSS = `
:root {
  --bg-0: #0a0b0e;
  --bg-1: #12141a;
  --bg-2: #1a1d26;
  --bg-3: #242834;
  --border: #2a2e3a;
  --border-h: #3a3f50;
  --text-0: #f0f1f4;
  --text-1: #b0b4c0;
  --text-2: #6b7084;
  --green: #00d68f;
  --green-dim: #00d68f22;
  --red: #ff6b6b;
  --red-dim: #ff6b6b22;
  --blue: #5b8def;
  --blue-dim: #5b8def22;
  --amber: #ffb84d;
  --amber-dim: #ffb84d22;
  --purple: #a78bfa;
  --font: 'DM Sans', -apple-system, sans-serif;
  --mono: 'JetBrains Mono', monospace;
}

* { margin: 0; padding: 0; box-sizing: border-box; }

html, body, #root {
  height: 100%;
  background: var(--bg-0);
  color: var(--text-0);
  font-family: var(--font);
  font-size: 14px;
  -webkit-font-smoothing: antialiased;
}

.app { min-height: 100vh; }

/* ── Header ── */
.header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 28px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-1);
  position: sticky; top: 0; z-index: 50;
}
.logo { display: flex; align-items: center; gap: 10px; }
.logo-mark {
  width: 32px; height: 32px; border-radius: 8px;
  background: linear-gradient(135deg, var(--blue), var(--green));
  display: flex; align-items: center; justify-content: center;
  font-weight: 600; font-size: 15px; color: #fff;
}
.logo-text { font-size: 18px; font-weight: 600; letter-spacing: -0.3px; }
.logo-tag {
  font-size: 11px; color: var(--text-2);
  background: var(--bg-3); padding: 3px 8px;
  border-radius: 4px; margin-left: 4px;
}
.header-right { display: flex; align-items: center; gap: 12px; }
.status-dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: var(--green); box-shadow: 0 0 6px var(--green);
}
.status-text { font-size: 12px; color: var(--text-2); }

/* ── Layout ── */
.main { padding: 24px 28px; max-width: 1400px; margin: 0 auto; }
.grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 24px; }
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 24px; }

/* ── Cards ── */
.card {
  background: var(--bg-1); border: 1px solid var(--border);
  border-radius: 12px; padding: 18px 20px;
}
.card-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 16px;
}
.card-title { font-size: 13px; font-weight: 500; color: var(--text-2); text-transform: uppercase; letter-spacing: 0.5px; }

/* ── Stat Cards ── */
.stat-card { padding: 16px 20px; }
.stat-label { font-size: 12px; color: var(--text-2); margin-bottom: 6px; letter-spacing: 0.3px; }
.stat-value { font-size: 24px; font-weight: 600; font-family: var(--mono); letter-spacing: -0.5px; }
.stat-sub { font-size: 12px; color: var(--text-2); margin-top: 4px; }
.stat-change {
  display: inline-flex; align-items: center; gap: 3px;
  font-size: 12px; font-family: var(--mono); padding: 2px 6px;
  border-radius: 4px; margin-top: 6px;
}
.stat-change.up { color: var(--green); background: var(--green-dim); }
.stat-change.down { color: var(--red); background: var(--red-dim); }

/* ── Tables ── */
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { text-align: left; padding: 10px 14px; color: var(--text-2); font-weight: 500; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid var(--border); }
td { padding: 12px 14px; border-bottom: 1px solid var(--border); vertical-align: middle; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: var(--bg-2); }
.mono { font-family: var(--mono); font-size: 13px; }
.green { color: var(--green); }
.red { color: var(--red); }
.blue { color: var(--blue); }
.amber { color: var(--amber); }

/* ── Badges ── */
.badge {
  display: inline-block; padding: 3px 8px; border-radius: 4px;
  font-size: 11px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.3px;
}
.badge-green { background: var(--green-dim); color: var(--green); }
.badge-red { background: var(--red-dim); color: var(--red); }
.badge-blue { background: var(--blue-dim); color: var(--blue); }
.badge-amber { background: var(--amber-dim); color: var(--amber); }

/* ── Buttons ── */
.btn {
  padding: 7px 14px; border-radius: 6px; font-size: 12px; font-weight: 500;
  cursor: pointer; border: 1px solid var(--border); background: var(--bg-2);
  color: var(--text-0); transition: all 0.15s;
}
.btn:hover { border-color: var(--border-h); background: var(--bg-3); }
.btn-primary { background: var(--blue); border-color: var(--blue); color: #fff; }
.btn-primary:hover { opacity: 0.85; }
.btn-green { background: var(--green-dim); border-color: var(--green); color: var(--green); }
.btn-green:hover { background: var(--green); color: #000; }
.btn-sm { padding: 4px 10px; font-size: 11px; }

/* ── Exchange pills ── */
.ex-pill {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 500;
}
.ex-pacifica { background: var(--blue-dim); color: var(--blue); }
.ex-binance { background: var(--amber-dim); color: var(--amber); }

/* ── Confidence bar ── */
.conf-bar { width: 60px; height: 5px; background: var(--bg-3); border-radius: 3px; overflow: hidden; }
.conf-fill { height: 100%; border-radius: 3px; transition: width 0.3s; }

/* ── Toggle ── */
.toggle { position: relative; width: 40px; height: 22px; cursor: pointer; }
.toggle input { opacity: 0; width: 0; height: 0; }
.toggle-track {
  position: absolute; inset: 0; background: var(--bg-3);
  border-radius: 11px; transition: 0.2s;
}
.toggle input:checked + .toggle-track { background: var(--green); }
.toggle-thumb {
  position: absolute; top: 3px; left: 3px; width: 16px; height: 16px;
  background: #fff; border-radius: 50%; transition: 0.2s;
}
.toggle input:checked ~ .toggle-thumb { left: 21px; }

/* ── Tabs ── */
.tabs { display: flex; gap: 0; border-bottom: 1px solid var(--border); margin-bottom: 16px; }
.tab {
  padding: 10px 16px; font-size: 13px; font-weight: 500; cursor: pointer;
  color: var(--text-2); border-bottom: 2px solid transparent;
  transition: all 0.15s;
}
.tab:hover { color: var(--text-1); }
.tab.active { color: var(--text-0); border-bottom-color: var(--blue); }

/* ── Scanner pulse ── */
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
.scanning { animation: pulse 1.5s ease-in-out infinite; }

/* ── Responsive ── */
@media (max-width: 900px) {
  .grid-4 { grid-template-columns: repeat(2, 1fr); }
  .grid-2 { grid-template-columns: 1fr; }
  .main { padding: 16px; }
  .header { padding: 12px 16px; }
}
`


/* ───────── COMPONENTS ───────── */

function ExPill({ ex }) {
  const cls = ex === 'pacifica' ? 'ex-pacifica' : 'ex-binance'
  return <span className={`ex-pill ${cls}`}>{ex === 'pacifica' ? 'Pacifica' : 'Binance'}</span>
}

function ConfidenceBar({ value }) {
  const color = value > 0.7 ? 'var(--green)' : value > 0.5 ? 'var(--amber)' : 'var(--red)'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div className="conf-bar">
        <div className="conf-fill" style={{ width: `${value * 100}%`, background: color }} />
      </div>
      <span className="mono" style={{ fontSize: 12, color }}>{(value * 100).toFixed(0)}%</span>
    </div>
  )
}

function StatCard({ label, value, sub, change, changeDir }) {
  return (
    <div className="card stat-card">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
      {change && <div className={`stat-change ${changeDir || 'up'}`}>{changeDir === 'down' ? '▼' : '▲'} {change}</div>}
    </div>
  )
}

function RatesTable({ rates }) {
  // Group by pair
  const grouped = {}
  rates.forEach(r => {
    if (!grouped[r.pair]) grouped[r.pair] = {}
    grouped[r.pair][r.exchange] = r
  })

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Pair</th>
            <th>Pacifica</th>
            <th>Binance</th>
            <th>Spread</th>
            <th>Annual yield</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(grouped).map(([pair, exRates]) => {
            const pac = exRates.pacifica?.rate || 0
            const bin = exRates.binance?.rate || 0
            const spread = Math.abs(pac - bin)
            const annual = spread * 3 * 365 * 100
            return (
              <tr key={pair}>
                <td style={{ fontWeight: 500 }}>{pair}</td>
                <td className={`mono ${pac >= 0 ? 'green' : 'red'}`}>{(pac * 100).toFixed(4)}%</td>
                <td className={`mono ${bin >= 0 ? 'green' : 'red'}`}>{(bin * 100).toFixed(4)}%</td>
                <td className="mono blue">{(spread * 100).toFixed(4)}%</td>
                <td className={`mono ${annual > 10 ? 'green' : 'amber'}`}>{annual.toFixed(1)}%</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function SignalsTable({ signals, onExecute }) {
  if (!signals.length) {
    return <div style={{ color: 'var(--text-2)', textAlign: 'center', padding: 32 }}>No signals above threshold — waiting for spread divergence...</div>
  }
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Pair</th>
            <th>Direction</th>
            <th>Spread</th>
            <th>Est. profit/8h</th>
            <th>Confidence</th>
            <th>Size</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {signals.map(s => (
            <tr key={s.id}>
              <td style={{ fontWeight: 500 }}>{s.pair}</td>
              <td>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12 }}>
                  <span style={{ color: 'var(--green)' }}>LONG</span> <ExPill ex={s.long_exchange} />
                  <span style={{ color: 'var(--text-2)', margin: '0 2px' }}>/</span>
                  <span style={{ color: 'var(--red)' }}>SHORT</span> <ExPill ex={s.short_exchange} />
                </div>
              </td>
              <td className="mono blue">{s.spread_pct}</td>
              <td className="mono green">${s.estimated_profit_8h}</td>
              <td><ConfidenceBar value={s.confidence} /></td>
              <td className="mono">${s.sizing.recommended_size_usd} × {s.sizing.leverage}x</td>
              <td>
                <button className="btn btn-green btn-sm" onClick={() => onExecute(s.id)}>Execute</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function PositionsTable({ positions }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Pair</th>
            <th>Direction</th>
            <th>Size</th>
            <th>P&L</th>
            <th>Funding</th>
            <th>Return</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {positions.map(p => (
            <tr key={p.id}>
              <td style={{ fontWeight: 500 }}>{p.pair}</td>
              <td>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12 }}>
                  <span style={{ color: 'var(--green)' }}>L</span> <ExPill ex={p.long_exchange} />
                  <span style={{ color: 'var(--text-2)' }}>/</span>
                  <span style={{ color: 'var(--red)' }}>S</span> <ExPill ex={p.short_exchange} />
                </div>
              </td>
              <td className="mono">${p.size_usd.toLocaleString()}</td>
              <td className={`mono ${p.pnl_usd >= 0 ? 'green' : 'red'}`}>
                {p.pnl_usd >= 0 ? '+' : ''}${p.pnl_usd.toFixed(2)}
              </td>
              <td className="mono green">+${p.funding_collected.toFixed(2)}</td>
              <td className={`mono ${parseFloat(p.total_return_pct) >= 0 ? 'green' : 'red'}`}>{p.total_return_pct}</td>
              <td><span className={`badge ${p.status === 'open' ? 'badge-green' : 'badge-blue'}`}>{p.status}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function PnlChart({ data }) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: -10, bottom: 0 }}>
        <defs>
          <linearGradient id="gPnl" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#00d68f" stopOpacity={0.3} />
            <stop offset="100%" stopColor="#00d68f" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="gFund" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#5b8def" stopOpacity={0.2} />
            <stop offset="100%" stopColor="#5b8def" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="#242834" strokeDasharray="3 3" />
        <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#6b7084' }} axisLine={{ stroke: '#2a2e3a' }} tickLine={false} />
        <YAxis tick={{ fontSize: 11, fill: '#6b7084' }} axisLine={{ stroke: '#2a2e3a' }} tickLine={false} tickFormatter={v => `$${v}`} />
        <Tooltip
          contentStyle={{ background: '#1a1d26', border: '1px solid #2a2e3a', borderRadius: 8, fontSize: 13 }}
          labelStyle={{ color: '#6b7084' }}
          formatter={(val, name) => [`$${val.toFixed(2)}`, name === 'pnl' ? 'Total P&L' : 'Funding collected']}
        />
        <Area type="monotone" dataKey="funding" stroke="#5b8def" strokeWidth={1.5} fill="url(#gFund)" />
        <Area type="monotone" dataKey="pnl" stroke="#00d68f" strokeWidth={2} fill="url(#gPnl)" />
      </AreaChart>
    </ResponsiveContainer>
  )
}

function SpreadChart({ rates }) {
  const grouped = {}
  rates.forEach(r => {
    if (!grouped[r.pair]) grouped[r.pair] = {}
    grouped[r.pair][r.exchange] = r
  })
  const data = Object.entries(grouped).map(([pair, exRates]) => {
    const pac = exRates.pacifica?.rate || 0
    const bin = exRates.binance?.rate || 0
    return { pair: pair.replace('-PERP', ''), spread: Math.abs(pac - bin) * 10000 }
  })

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: -10, bottom: 0 }}>
        <CartesianGrid stroke="#242834" strokeDasharray="3 3" />
        <XAxis dataKey="pair" tick={{ fontSize: 12, fill: '#6b7084' }} axisLine={{ stroke: '#2a2e3a' }} tickLine={false} />
        <YAxis tick={{ fontSize: 11, fill: '#6b7084' }} axisLine={{ stroke: '#2a2e3a' }} tickLine={false} tickFormatter={v => `${v}bp`} />
        <Tooltip
          contentStyle={{ background: '#1a1d26', border: '1px solid #2a2e3a', borderRadius: 8, fontSize: 13 }}
          formatter={val => [`${val.toFixed(2)} bps`, 'Spread']}
        />
        <Bar dataKey="spread" radius={[4, 4, 0, 0]} maxBarSize={48}>
          {data.map((d, i) => (
            <Cell key={i} fill={d.spread > 3 ? '#00d68f' : d.spread > 1 ? '#ffb84d' : '#3a3f50'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}


/* ───────── MAIN APP ───────── */

export default function App() {
  const [rates, setRates] = useState([])
  const [signals, setSignals] = useState([])
  const [positions, setPositions] = useState([])
  const [pnlHistory, setPnlHistory] = useState([])
  const [scanning, setScanning] = useState(false)
  const [autoMode, setAutoMode] = useState(false)
  const [tab, setTab] = useState('signals')
  const [lastScan, setLastScan] = useState(null)
  const [executedIds, setExecutedIds] = useState(new Set())
  const scanInterval = useRef(null)

  // Portfolio stats
  const openPos = positions.filter(p => p.status === 'open')
  const totalPnl = positions.reduce((s, p) => s + p.pnl_usd, 0)
  const totalFunding = positions.reduce((s, p) => s + p.funding_collected, 0)
  const totalExposure = openPos.reduce((s, p) => s + p.size_usd, 0)

  const doScan = useCallback(() => {
    setScanning(true)
    setTimeout(() => {
      const newRates = generateRates()
      const newSignals = generateSignals(newRates)
      setRates(newRates)
      setSignals(newSignals)
      setLastScan(new Date())
      setScanning(false)
    }, 600)
  }, [])

  // Initial load
  useEffect(() => {
    setPnlHistory(generatePnlHistory(30))
    setPositions(generatePositions())
    doScan()
  }, [doScan])

  // Auto-scan every 30s
  useEffect(() => {
    scanInterval.current = setInterval(doScan, 30000)
    return () => clearInterval(scanInterval.current)
  }, [doScan])

  const handleExecute = (sigId) => {
    setExecutedIds(prev => new Set([...prev, sigId]))
    const sig = signals.find(s => s.id === sigId)
    if (!sig) return
    // Add to positions
    setPositions(prev => [{
      id: `pos_${Math.random().toString(36).slice(2, 10)}`,
      pair: sig.pair,
      long_exchange: sig.long_exchange,
      short_exchange: sig.short_exchange,
      size_usd: sig.sizing.recommended_size_usd,
      pnl_usd: 0,
      funding_collected: 0,
      total_return_pct: '0.00%',
      status: 'open',
      opened_at: new Date().toISOString(),
    }, ...prev])
  }

  return (
    <>
      <style>{CSS}</style>
      <div className="app">
        {/* ── Header ── */}
        <header className="header">
          <div className="logo">
            <div className="logo-mark">Pf</div>
            <span className="logo-text">PaciFund</span>
            <span className="logo-tag">Testnet</span>
          </div>
          <div className="header-right">
            <div className={scanning ? 'scanning' : ''} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div className="status-dot" />
              <span className="status-text">
                {scanning ? 'Scanning...' : `Last scan ${lastScan ? lastScan.toLocaleTimeString() : '—'}`}
              </span>
            </div>
            <button className="btn" onClick={doScan}>Scan now</button>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 12, color: 'var(--text-2)' }}>Auto</span>
              <label className="toggle">
                <input type="checkbox" checked={autoMode} onChange={e => setAutoMode(e.target.checked)} />
                <div className="toggle-track" />
                <div className="toggle-thumb" />
              </label>
            </div>
          </div>
        </header>

        {/* ── Main ── */}
        <main className="main">
          {/* Stats */}
          <div className="grid-4">
            <StatCard label="Total P&L" value={`$${totalPnl.toFixed(2)}`} change={`${((totalPnl / 10000) * 100).toFixed(1)}%`} changeDir={totalPnl >= 0 ? 'up' : 'down'} />
            <StatCard label="Funding collected" value={`$${totalFunding.toFixed(2)}`} sub="Cumulative funding income" change={`+$${(totalFunding / 30).toFixed(1)}/day avg`} />
            <StatCard label="Exposure" value={`$${totalExposure.toLocaleString()}`} sub={`${((totalExposure / 10000) * 100).toFixed(1)}% of $10,000 capital`} />
            <StatCard label="Active signals" value={signals.length.toString()} sub={`${openPos.length} open positions`} />
          </div>

          {/* Charts row */}
          <div className="grid-2">
            <div className="card">
              <div className="card-header">
                <span className="card-title">P&L history (30d)</span>
                <div style={{ display: 'flex', gap: 16, fontSize: 12 }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><span style={{ width: 8, height: 3, background: 'var(--green)', borderRadius: 2 }} />P&L</span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><span style={{ width: 8, height: 3, background: 'var(--blue)', borderRadius: 2 }} />Funding</span>
                </div>
              </div>
              <PnlChart data={pnlHistory} />
            </div>
            <div className="card">
              <div className="card-header">
                <span className="card-title">Cross-exchange spread (bps)</span>
              </div>
              <SpreadChart rates={rates} />
              <RatesTable rates={rates} />
            </div>
          </div>

          {/* Tabs: Signals / Positions */}
          <div className="card">
            <div className="tabs">
              <div className={`tab ${tab === 'signals' ? 'active' : ''}`} onClick={() => setTab('signals')}>
                Signals {signals.length > 0 && <span className="badge badge-green" style={{ marginLeft: 6 }}>{signals.length}</span>}
              </div>
              <div className={`tab ${tab === 'positions' ? 'active' : ''}`} onClick={() => setTab('positions')}>
                Positions <span className="badge badge-blue" style={{ marginLeft: 6 }}>{openPos.length} open</span>
              </div>
            </div>

            {tab === 'signals' && (
              <SignalsTable
                signals={signals.filter(s => !executedIds.has(s.id))}
                onExecute={handleExecute}
              />
            )}
            {tab === 'positions' && (
              <PositionsTable positions={positions} />
            )}
          </div>
        </main>
      </div>
    </>
  )
}
