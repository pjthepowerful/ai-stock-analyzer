# Paula

AI-powered intraday trading assistant. Analyzes stocks using 5-minute VWAP, EMA crossovers, and momentum signals. Goes long and short. Paper trading via Alpaca.

## What It Does

- **Intraday signal engine** — VWAP, 9/20/50 EMA, RSI, MACD on 5-minute bars
- **Long + Short** — buys momentum above VWAP, shorts breakdowns below
- **Autopilot** — scans every 5 minutes, executes trades, manages stops
- **Gap scanner** — finds stocks gapping >1.5% on volume at open
- **SPY filter** — blocks longs when SPY dumps, blocks shorts when SPY rips
- **EOD liquidation** — closes everything at 3:45 PM ET
- **Risk management** — 2x ATR stops, breakeven at +0.5%, time-based kills for flat trades
- **AI chat** — ask about any stock, get analysis with entry/stop/targets

## Architecture

```
├── trading.py              # Streamlit web app (legacy)
├── desktop/
│   ├── backend/
│   │   ├── server.py       # FastAPI REST + WebSocket server
│   │   ├── engine.py       # Streamlit-free engine wrapper
│   │   └── trading.py      # Core trading engine
│   └── frontend/
│       ├── src/
│       │   ├── App.jsx     # Main React app
│       │   ├── Chart.jsx   # TradingView candlestick charts
│       │   └── sounds.js   # Web Audio trade sounds
│       └── src-tauri/      # Native desktop shell (Rust)
```

## Quick Start

### Desktop App (recommended)

**Backend:**
```bash
cd desktop/backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export ALPACA_KEY_ID=your_key
export ALPACA_SECRET=your_secret
export GROQ_API_KEY=your_groq_key
python server.py
```

**Frontend** (new terminal):
```bash
cd desktop/frontend
npm install && npm run dev
```

Open `http://localhost:1420`

### Build Native App (.dmg)

```bash
cd desktop/frontend
npm install
npx tauri build
open src-tauri/target/release/bundle/dmg/
```

### Streamlit (legacy)

```bash
pip install -r requirements.txt
streamlit run trading.py
```

## API Keys

| Key | Where to get it | What it does |
|-----|----------------|--------------|
| `ALPACA_KEY_ID` | [alpaca.markets](https://alpaca.markets) | Paper trading |
| `ALPACA_SECRET` | Same | Paper trading |
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) | AI chat responses |
| `POLYGON_API_KEY` | [polygon.io](https://polygon.io) | Market-wide scanning (optional) |

## Trading Rules

- **No trades first 15 min** (9:30-9:45 AM) — lets VWAP establish
- **No new positions last 30 min** (3:30 PM+)
- **EOD liquidation at 3:45 PM** — everything closed
- **2% daily loss limit** — shuts down if hit
- **Score ≥62** with 3+ confluence categories to enter
- **R:R ≥1.5** minimum on all trades
- **Flat trades killed after 90 min**

## License

Personal use only.
