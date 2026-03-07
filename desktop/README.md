# Paula Desktop

Native desktop trading app. Runs locally — no cloud, no latency, no hosting costs.

**Architecture:**
- **Backend:** FastAPI (Python) — wraps the trading engine, serves REST + WebSocket
- **Frontend:** React + Vite — fast, minimal UI
- **Shell:** Tauri (Rust) — native window, ~5MB binary, no Electron bloat

```
paula-desktop/
├── backend/
│   ├── server.py          # FastAPI server (REST + WebSocket)
│   ├── engine.py          # Streamlit-free trading engine wrapper
│   ├── trading.py         # ← copy from your ai-stock-analyzer repo
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx        # Main React app
│   │   ├── App.css        # Styles
│   │   └── main.jsx       # Entry point
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
├── src-tauri/
│   ├── src/main.rs        # Tauri entry
│   ├── Cargo.toml
│   └── tauri.conf.json    # Window config
├── start.sh               # Dev startup script
├── .env.example            # API keys template
└── README.md
```

## Quick Start (Dev Mode — no Tauri needed)

This runs the app in your browser while developing. No Rust toolchain required.

### 1. Clone and copy the engine

```bash
git clone <this-repo> paula-desktop
cd paula-desktop

# Copy trading.py from your existing repo
cp /path/to/ai-stock-analyzer/trading.py backend/trading.py
```

### 2. Set up backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Set your API keys
cp ../.env.example ../.env
# Edit .env with your keys, then:
export $(cat ../.env | xargs)   # Windows: use set commands
```

### 3. Set up frontend

```bash
cd ../frontend
npm install
```

### 4. Run it

```bash
# Terminal 1 — Backend
cd backend
python server.py
# → http://127.0.0.1:3141
# → API docs at http://127.0.0.1:3141/docs

# Terminal 2 — Frontend
cd frontend
npm run dev
# → http://localhost:1420
```

Or use the start script:
```bash
chmod +x start.sh
./start.sh
```

Open http://localhost:1420 in your browser. That's it — full trading app running locally.

## Native Desktop App (with Tauri)

For a proper native window (no browser needed):

### Prerequisites

- [Rust](https://rustup.rs/) — `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`
- [Node.js](https://nodejs.org/) v18+
- System deps (macOS): `xcode-select --install`
- System deps (Ubuntu): `sudo apt install libwebkit2gtk-4.0-dev build-essential libssl-dev libgtk-3-dev libayatana-appindicator3-dev librsvg2-dev`

### Build & Run

```bash
cd frontend
npm install
npm run tauri dev          # Dev mode with hot reload
npm run tauri build        # Production binary
```

The built binary will be in `src-tauri/target/release/`.

## API Endpoints

All endpoints are at `http://127.0.0.1:3141`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Server status + time |
| GET | `/api/account` | Alpaca account info |
| GET | `/api/positions` | Open positions |
| GET | `/api/orders` | Recent orders |
| GET | `/api/price/{ticker}` | Current price |
| GET | `/api/analyze/{ticker}` | Full daily analysis |
| GET | `/api/analyze-intraday/{ticker}` | 5min bar analysis |
| GET | `/api/chart/{ticker}` | OHLCV chart data |
| GET | `/api/market-regime` | Market regime check |
| GET | `/api/spy-trend` | SPY intraday trend |
| POST | `/api/chat` | Send chat message |
| POST | `/api/buy` | Buy stock |
| POST | `/api/sell` | Sell stock |
| POST | `/api/short` | Short stock |
| POST | `/api/cover` | Cover short |
| POST | `/api/close-all` | Close all positions |
| POST | `/api/autopilot/start` | Start autopilot |
| POST | `/api/autopilot/stop` | Stop autopilot |
| GET | `/api/autopilot/status` | Autopilot status |
| WS | `/ws` | Real-time updates |

## WebSocket Events

Connect to `ws://127.0.0.1:3141/ws` for real-time updates:

- `connected` — initial state (autopilot status, chat history)
- `chat` — new assistant message
- `autopilot` — scan results, status changes
- `trade` — trade executed

## Why This Over Streamlit

| | Streamlit | Paula Desktop |
|---|---|---|
| Response time | 500ms-2s (full rerun) | <50ms (API call) |
| Autopilot | Sleep loop hack, needs tab open | Real async background task |
| WebSocket | None — polling via rerun | Real-time push updates |
| Hosting | $0-20/mo Streamlit Cloud | Free (your machine) |
| State | Lost on rerun/refresh | Persistent in backend |
| UI | Limited to Streamlit widgets | Full React — build anything |
