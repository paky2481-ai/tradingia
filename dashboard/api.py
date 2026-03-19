"""
FastAPI Dashboard + REST API + WebSocket
Real-time trading dashboard with live updates.
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from config.settings import settings
from utils.logger import get_logger

logger = get_logger.bind(name="dashboard")


# ── Pydantic schemas ───────────────────────────────────────────────────────

class TradeRequest(BaseModel):
    symbol: str
    direction: str
    quantity: float
    order_type: str = "market"
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None


class BacktestRequest(BaseModel):
    symbol: str
    strategy: str
    timeframe: str = "1h"
    initial_capital: float = 100_000.0


class TrainRequest(BaseModel):
    symbols: List[str]
    timeframe: str = "1h"


# ── WebSocket Manager ──────────────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)
        logger.info(f"WebSocket connected. Total: {len(self.active)}")

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, data: Dict):
        msg = json.dumps(data)
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


# ── App factory ────────────────────────────────────────────────────────────

def create_app(orchestrator=None) -> FastAPI:
    """
    Create the FastAPI application.
    `orchestrator` is the TradingOrchestrator instance.
    """
    app = FastAPI(
        title="TradingIA",
        description="AI-powered multi-asset trading system",
        version=settings.version,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Health ────────────────────────────────────────────────────────────

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": settings.version, "time": datetime.utcnow().isoformat()}

    # ── Portfolio ─────────────────────────────────────────────────────────

    @app.get("/api/portfolio")
    async def get_portfolio():
        if orchestrator is None:
            return {"error": "orchestrator not initialized"}
        return orchestrator.portfolio.full_report()

    @app.get("/api/positions")
    async def get_positions():
        if orchestrator is None:
            return []
        df = orchestrator.portfolio.get_positions_df()
        return df.to_dict(orient="records") if not df.empty else []

    @app.get("/api/trades")
    async def get_trades(limit: int = 50):
        if orchestrator is None:
            return []
        df = orchestrator.portfolio.get_trades_df()
        if df.empty:
            return []
        return df.tail(limit).to_dict(orient="records")

    # ── Market data ───────────────────────────────────────────────────────

    @app.get("/api/quotes")
    async def get_quotes(symbols: str = ""):
        from data.feed import data_feed
        symbol_list = [s.strip() for s in symbols.split(",") if s.strip()] if symbols else settings.stock_symbols[:5]
        quotes = await data_feed.get_multiple_quotes(symbol_list)
        return quotes

    @app.get("/api/ohlcv/{symbol}")
    async def get_ohlcv(symbol: str, timeframe: str = "1h", limit: int = 200):
        from data.feed import data_feed
        df = await data_feed.get_ohlcv(symbol, timeframe, limit)
        if df is None:
            raise HTTPException(status_code=404, detail=f"No data for {symbol}")
        df_reset = df.reset_index()
        df_reset["timestamp"] = df_reset["timestamp"].astype(str)
        return df_reset.to_dict(orient="records")

    @app.get("/api/signals")
    async def get_signals():
        if orchestrator is None:
            return []
        return [
            {
                "symbol": s.symbol,
                "direction": s.direction,
                "confidence": s.confidence,
                "strategy": s.strategy_name,
                "price": s.price,
                "timestamp": s.timestamp.isoformat(),
            }
            for s in getattr(orchestrator, "_last_signals", [])
        ]

    # ── Risk ──────────────────────────────────────────────────────────────

    @app.get("/api/risk")
    async def get_risk():
        if orchestrator is None:
            return {}
        rm = orchestrator.risk_manager
        can_trade, reason = rm.can_trade()
        return {
            "can_trade": can_trade,
            "reason": reason,
            "drawdown_pct": rm.drawdown_pct,
            "portfolio_heat": rm.portfolio_heat,
            "open_positions": len(rm._open_positions),
            "max_positions": settings.risk.max_open_positions,
            "max_drawdown_pct": settings.risk.max_drawdown_pct,
        }

    # ── Manual trading ────────────────────────────────────────────────────

    @app.post("/api/trade")
    async def place_trade(req: TradeRequest):
        if orchestrator is None:
            raise HTTPException(status_code=503, detail="Orchestrator not running")
        result = await orchestrator.broker.place_order(
            req.symbol, req.direction, req.quantity,
            req.order_type, req.limit_price, req.stop_price,
        )
        return {"success": result.success, "order_id": result.order_id, "message": result.message}

    @app.post("/api/close/{symbol}")
    async def close_position(symbol: str):
        if orchestrator is None:
            raise HTTPException(status_code=503, detail="Orchestrator not running")
        result = await orchestrator.broker.close_position(symbol)
        return {"success": result.success, "message": result.message}

    # ── Backtesting ───────────────────────────────────────────────────────

    @app.post("/api/backtest")
    async def run_backtest(req: BacktestRequest):
        from data.feed import data_feed
        from backtesting.backtester import Backtester
        from strategies.technical_strategy import (
            TrendFollowingStrategy, MeanReversionStrategy,
            BreakoutStrategy, ScalpingStrategy,
        )
        from strategies.ai_strategy import AIStrategy

        strategy_map = {
            "trend_following": TrendFollowingStrategy,
            "mean_reversion": MeanReversionStrategy,
            "breakout": BreakoutStrategy,
            "scalping": ScalpingStrategy,
            "ai_ensemble": AIStrategy,
        }
        cls = strategy_map.get(req.strategy)
        if cls is None:
            raise HTTPException(status_code=400, detail=f"Unknown strategy: {req.strategy}")

        df = await data_feed.get_ohlcv(req.symbol, req.timeframe, limit=2000)
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"No data for {req.symbol}")

        strategy = cls(timeframe=req.timeframe)
        bt = Backtester(initial_capital=req.initial_capital)
        result = await asyncio.to_thread(bt.run, df, strategy, req.symbol)
        return result.to_dict()

    # ── Model training ────────────────────────────────────────────────────

    @app.post("/api/train")
    async def train_models(req: TrainRequest):
        from data.feed import data_feed
        from models.ensemble_model import EnsembleModel

        results = {}
        for symbol in req.symbols:
            df = await data_feed.get_ohlcv(symbol, req.timeframe, limit=5000)
            if df is None or df.empty:
                results[symbol] = {"error": "no_data"}
                continue
            model = EnsembleModel(name=f"ensemble_{symbol.replace('/', '_')}")
            metrics = await asyncio.to_thread(model.train, df)
            results[symbol] = metrics
        return results

    # ── WebSocket live feed ───────────────────────────────────────────────

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        await manager.connect(ws)
        try:
            while True:
                data = await ws.receive_text()
                # Echo back or handle commands
                if data == "ping":
                    await ws.send_text(json.dumps({"type": "pong"}))
        except WebSocketDisconnect:
            manager.disconnect(ws)
            logger.info("WebSocket disconnected")

    # ── Dashboard HTML ────────────────────────────────────────────────────

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return _dashboard_html()

    return app


def _dashboard_html() -> str:
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TradingIA Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: #0d1117; color: #c9d1d9; font-family: 'Segoe UI', sans-serif; }
        header { background: #161b22; padding: 16px 24px; border-bottom: 1px solid #30363d;
                 display: flex; align-items: center; gap: 12px; }
        header h1 { font-size: 1.4rem; color: #58a6ff; }
        .badge { background: #238636; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; }
        .container { max-width: 1400px; margin: 0 auto; padding: 24px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }
        .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; }
        .card h3 { color: #8b949e; font-size: 0.8rem; text-transform: uppercase; margin-bottom: 8px; }
        .card .value { font-size: 1.8rem; font-weight: 700; }
        .positive { color: #3fb950; }
        .negative { color: #f85149; }
        .neutral { color: #58a6ff; }
        .section { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin-bottom: 24px; }
        .section h2 { color: #c9d1d9; margin-bottom: 16px; font-size: 1rem; }
        table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
        th { color: #8b949e; text-align: left; padding: 8px; border-bottom: 1px solid #30363d; }
        td { padding: 10px 8px; border-bottom: 1px solid #21262d; }
        tr:hover td { background: #1c2128; }
        .status-dot { width: 8px; height: 8px; border-radius: 50%; background: #3fb950;
                      display: inline-block; margin-right: 6px; animation: pulse 2s infinite; }
        @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
        .btn { padding: 8px 16px; border: none; border-radius: 6px; cursor: pointer; font-size: 0.85rem; }
        .btn-primary { background: #238636; color: white; }
        .btn-danger { background: #da3633; color: white; }
        #ws-status { font-size: 0.75rem; color: #8b949e; margin-left: auto; }
    </style>
</head>
<body>
    <header>
        <span>⚡</span>
        <h1>TradingIA</h1>
        <span class="badge">LIVE</span>
        <span id="ws-status"><span class="status-dot"></span>Connecting...</span>
    </header>
    <div class="container">
        <div class="grid" id="metrics">
            <div class="card"><h3>Total Equity</h3><div class="value neutral" id="equity">—</div></div>
            <div class="card"><h3>Daily P&L</h3><div class="value" id="daily-pnl">—</div></div>
            <div class="card"><h3>Open Positions</h3><div class="value neutral" id="open-pos">—</div></div>
            <div class="card"><h3>Win Rate</h3><div class="value neutral" id="win-rate">—</div></div>
            <div class="card"><h3>Drawdown</h3><div class="value negative" id="drawdown">—</div></div>
            <div class="card"><h3>Total Trades</h3><div class="value neutral" id="total-trades">—</div></div>
        </div>

        <div class="section">
            <h2>Open Positions</h2>
            <table id="positions-table">
                <thead><tr>
                    <th>Symbol</th><th>Type</th><th>Dir</th><th>Qty</th>
                    <th>Entry</th><th>Current</th><th>P&L</th><th>P&L%</th><th>Strategy</th>
                </tr></thead>
                <tbody id="positions-body"><tr><td colspan="9" style="color:#8b949e">No open positions</td></tr></tbody>
            </table>
        </div>

        <div class="section">
            <h2>Recent Signals</h2>
            <table><thead><tr>
                <th>Symbol</th><th>Direction</th><th>Confidence</th><th>Strategy</th><th>Price</th><th>Time</th>
            </tr></thead>
            <tbody id="signals-body"><tr><td colspan="6" style="color:#8b949e">Waiting for signals...</td></tr></tbody></table>
        </div>

        <div class="section">
            <h2>Trade History</h2>
            <table><thead><tr>
                <th>Symbol</th><th>Dir</th><th>Entry</th><th>Exit</th><th>P&L</th><th>P&L%</th><th>Strategy</th>
            </tr></thead>
            <tbody id="trades-body"><tr><td colspan="7" style="color:#8b949e">No closed trades yet</td></tr></tbody></table>
        </div>
    </div>

    <script>
        const fmt = (n, d=2) => n != null ? Number(n).toFixed(d) : '—';
        const fmtUSD = n => n != null ? '$' + Number(n).toLocaleString('en', {minimumFractionDigits: 2}) : '—';
        const colorClass = n => n > 0 ? 'positive' : n < 0 ? 'negative' : 'neutral';

        async function refreshPortfolio() {
            try {
                const r = await fetch('/api/portfolio');
                const d = await r.json();
                document.getElementById('equity').textContent = fmtUSD(d.equity);
                const pnl = d.daily_pnl;
                const pnlEl = document.getElementById('daily-pnl');
                pnlEl.textContent = (pnl >= 0 ? '+' : '') + fmtUSD(pnl);
                pnlEl.className = 'value ' + colorClass(pnl);
                document.getElementById('open-pos').textContent = d.open_positions ?? '—';
                document.getElementById('win-rate').textContent = fmt(d.win_rate) + '%';
                document.getElementById('drawdown').textContent = '-' + fmt(d.drawdown_pct) + '%';
                document.getElementById('total-trades').textContent = d.total_trades ?? '—';
            } catch(e) {}
        }

        async function refreshPositions() {
            try {
                const r = await fetch('/api/positions');
                const data = await r.json();
                const tbody = document.getElementById('positions-body');
                if (!data.length) {
                    tbody.innerHTML = '<tr><td colspan="9" style="color:#8b949e">No open positions</td></tr>';
                    return;
                }
                tbody.innerHTML = data.map(p => `<tr>
                    <td><b>${p.symbol}</b></td>
                    <td>${p.type || ''}</td>
                    <td class="${p.direction === 'buy' ? 'positive' : 'negative'}">${p.direction?.toUpperCase()}</td>
                    <td>${fmt(p.quantity, 4)}</td>
                    <td>${fmt(p.entry, 5)}</td>
                    <td>${fmt(p.price, 5)}</td>
                    <td class="${colorClass(p.pnl)}">${p.pnl >= 0 ? '+' : ''}${fmt(p.pnl, 2)}</td>
                    <td class="${colorClass(p['pnl%'])}">${p['pnl%'] >= 0 ? '+' : ''}${fmt(p['pnl%'], 2)}%</td>
                    <td style="color:#8b949e">${p.strategy || ''}</td>
                </tr>`).join('');
            } catch(e) {}
        }

        async function refreshSignals() {
            try {
                const r = await fetch('/api/signals');
                const data = await r.json();
                const tbody = document.getElementById('signals-body');
                if (!data.length) return;
                tbody.innerHTML = data.map(s => `<tr>
                    <td><b>${s.symbol}</b></td>
                    <td class="${s.direction === 'buy' ? 'positive' : 'negative'}">${s.direction?.toUpperCase()}</td>
                    <td>${(s.confidence * 100).toFixed(1)}%</td>
                    <td style="color:#8b949e">${s.strategy}</td>
                    <td>${fmt(s.price, 5)}</td>
                    <td style="color:#8b949e">${new Date(s.timestamp).toLocaleTimeString()}</td>
                </tr>`).join('');
            } catch(e) {}
        }

        async function refreshTrades() {
            try {
                const r = await fetch('/api/trades?limit=20');
                const data = await r.json();
                const tbody = document.getElementById('trades-body');
                if (!data.length) return;
                tbody.innerHTML = [...data].reverse().map(t => `<tr>
                    <td><b>${t.symbol}</b></td>
                    <td class="${t.direction === 'buy' ? 'positive' : 'negative'}">${t.direction?.toUpperCase()}</td>
                    <td>${fmt(t.entry_price, 5)}</td>
                    <td>${fmt(t.exit_price, 5)}</td>
                    <td class="${colorClass(t.pnl)}">${t.pnl >= 0 ? '+' : ''}${fmt(t.pnl, 2)}</td>
                    <td class="${colorClass(t.pnl_pct)}">${t.pnl_pct >= 0 ? '+' : ''}${fmt(t.pnl_pct, 2)}%</td>
                    <td style="color:#8b949e">${t.strategy || ''}</td>
                </tr>`).join('');
            } catch(e) {}
        }

        // WebSocket for live updates
        function connectWS() {
            const ws = new WebSocket('ws://' + location.host + '/ws');
            ws.onopen = () => {
                document.getElementById('ws-status').innerHTML = '<span class="status-dot"></span>Live';
            };
            ws.onmessage = (e) => {
                const msg = JSON.parse(e.data);
                if (msg.type === 'portfolio_update') refreshPortfolio();
                if (msg.type === 'signal') refreshSignals();
                if (msg.type === 'trade') { refreshPortfolio(); refreshPositions(); refreshTrades(); }
            };
            ws.onclose = () => {
                document.getElementById('ws-status').innerHTML = '<span style="color:#f85149">●</span> Reconnecting...';
                setTimeout(connectWS, 3000);
            };
        }

        // Initial load + polling fallback
        async function refresh() {
            await Promise.all([refreshPortfolio(), refreshPositions(), refreshSignals(), refreshTrades()]);
        }

        refresh();
        setInterval(refresh, 5000);
        connectWS();
    </script>
</body>
</html>
"""
