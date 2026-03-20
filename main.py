"""
TradingIA - Main Entry Point
AI-powered multi-asset trading system

Usage:
    python main.py trade          # Live/paper trading
    python main.py backtest       # Run backtests
    python main.py train          # Train AI models
    python main.py dashboard      # Launch dashboard only
    python main.py scan           # One-shot signal scan
"""

import asyncio
import sys
import os

import click
import uvicorn

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(__file__))

from config.settings import settings
from utils.logger import get_logger

logger = get_logger.bind(name="main")


@click.group()
def cli():
    """TradingIA - AI-powered trading system"""
    pass


@cli.command()
@click.option("--paper", is_flag=True, default=True, help="Paper trading mode (default)")
@click.option("--live", is_flag=True, default=False, help="Live trading (requires broker API keys)")
@click.option("--broker", type=click.Choice(["paper", "alpaca", "ccxt"]), default="paper")
@click.option("--port", default=8080, help="Dashboard port")
def trade(paper, live, broker, port):
    """Start the trading engine with live dashboard."""
    paper_mode = not live
    click.echo(f"\n{'='*50}")
    click.echo(f"  TradingIA v{settings.version}")
    click.echo(f"  Mode: {'PAPER' if paper_mode else '🔴 LIVE'}")
    click.echo(f"  Broker: {broker}")
    click.echo(f"  Dashboard: http://localhost:{port}")
    click.echo(f"{'='*50}\n")

    if not paper_mode:
        click.confirm("⚠️  LIVE TRADING MODE — real money at risk. Continue?", abort=True)

    asyncio.run(_run_trading(paper_mode, broker, port))


@cli.command()
@click.option("--symbol", default="AAPL", help="Symbol to backtest")
@click.option("--strategy", type=click.Choice([
    "trend_following", "mean_reversion", "breakout", "scalping", "ai_ensemble"
]), default="trend_following")
@click.option("--timeframe", default="1h")
@click.option("--capital", default=100_000.0, help="Initial capital")
def backtest(symbol, strategy, timeframe, capital):
    """Run backtest for a symbol and strategy."""
    asyncio.run(_run_backtest(symbol, strategy, timeframe, capital))


@cli.command()
@click.option("--symbols", default="AAPL,MSFT,BTC-USD,ETH-USD", help="Comma-separated symbols")
@click.option("--timeframe", default="1h")
def train(symbols, timeframe):
    """Train AI models on historical data."""
    symbol_list = [s.strip() for s in symbols.split(",")]
    asyncio.run(_run_training(symbol_list, timeframe))


@cli.command()
@click.option("--port", default=8080)
def dashboard(port):
    """Launch dashboard only (no trading)."""
    from dashboard.api import create_app
    app = create_app()
    uvicorn.run(app, host=settings.dashboard.host, port=port, log_level="warning")


@cli.command()
def gui():
    """Launch the desktop GUI application."""
    from gui.app import run
    run()


@cli.command()
@click.option("--symbols", default="", help="Specific symbols (empty = all)")
def scan(symbols):
    """One-shot signal scan across all instruments."""
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()] if symbols else None
    asyncio.run(_run_scan(symbol_list))


# ── Async runners ──────────────────────────────────────────────────────────

async def _run_trading(paper_mode: bool, broker_type: str, port: int):
    broker = _create_broker(broker_type)

    from core.orchestrator import TradingOrchestrator
    from dashboard.api import create_app, manager

    orchestrator = TradingOrchestrator(broker=broker, paper_mode=paper_mode)
    orchestrator._ws_broadcast = manager.broadcast

    app = create_app(orchestrator)

    config = uvicorn.Config(
        app,
        host=settings.dashboard.host,
        port=port,
        log_level="warning",
    )
    server = uvicorn.Server(config)

    await asyncio.gather(
        orchestrator.start(),
        server.serve(),
    )


async def _run_backtest(symbol: str, strategy_name: str, timeframe: str, capital: float):
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
    cls = strategy_map[strategy_name]
    strategy = cls(timeframe=timeframe)

    logger.info(f"Fetching data for {symbol}...")
    df = await data_feed.get_ohlcv(symbol, timeframe, limit=2000)

    if df is None or df.empty:
        logger.error(f"No data for {symbol}")
        return

    bt = Backtester(initial_capital=capital)
    result = bt.run(df, strategy, symbol)
    print(result.summary())
    await data_feed.close()


async def _run_training(symbols, timeframe):
    from core.orchestrator import TradingOrchestrator
    orch = TradingOrchestrator()
    await orch.train_all_models(symbols, timeframe)
    await orch.data_feed.close()


async def _run_scan(symbols=None):
    from data.feed import data_feed
    from strategies.strategy_manager import StrategyManager

    targets = symbols or settings.all_symbols[:20]
    logger.info(f"Scanning {len(targets)} symbols...")

    data = {}
    for symbol in targets:
        df = await data_feed.get_ohlcv(symbol, settings.primary_timeframe, limit=500)
        if df is not None:
            data[symbol] = {settings.primary_timeframe: df}

    sm = StrategyManager()
    all_signals = await sm.evaluate_all(data)

    print(f"\n{'='*60}")
    print(f"  SIGNAL SCAN RESULTS")
    print(f"{'='*60}")
    total = 0
    for symbol, signals in all_signals.items():
        for s in signals:
            direction_icon = "▲" if s.direction == "buy" else "▼"
            print(f"  {direction_icon} {s.direction.upper():4s} {symbol:12s}  conf={s.confidence:.2f}  strategy={s.strategy_name}")
            total += 1
    print(f"{'─'*60}")
    print(f"  Total signals: {total}")
    print(f"{'='*60}\n")

    await data_feed.close()


def _create_broker(broker_type: str):
    if broker_type == "paper":
        from brokers.paper_broker import PaperBroker
        return PaperBroker()
    elif broker_type == "alpaca":
        from brokers.alpaca_broker import AlpacaBroker
        return AlpacaBroker()
    elif broker_type == "ccxt":
        from brokers.ccxt_broker import CCXTBroker
        return CCXTBroker()
    return None


if __name__ == "__main__":
    cli()
