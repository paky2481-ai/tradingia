"""
[Max] Validazione: AI System vs EMA Crossover semplice
Confronto su dati reali — nessuna GUI necessaria.

Strumenti testati: AAPL, BTC-USD, EURUSD=X (stock, crypto, forex)
Periodo: 2 anni, timeframe 1d
Metriche: Total Return, Sharpe Ratio, Max Drawdown, Win Rate, # Trade
"""

import sys
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

sys.path.insert(0, "/home/user/tradingia")

# ─────────────────────────────────────────────
# UTILITY
# ─────────────────────────────────────────────

def download(symbol: str, period: str = "2y", interval: str = "1d") -> pd.DataFrame:
    df = yf.download(symbol, period=period, interval=interval,
                     auto_adjust=True, progress=False)
    df.columns = [c.lower() if isinstance(c, str) else c[0].lower() for c in df.columns]
    df = df.dropna()
    return df


def compute_metrics(returns: pd.Series, trades: list, label: str) -> dict:
    """Calcola le metriche principali dato un array di rendimenti giornalieri."""
    equity = (1 + returns).cumprod()
    total_return = equity.iloc[-1] - 1
    peak = equity.cummax()
    drawdown = (equity - peak) / peak
    max_dd = drawdown.min()
    ann_ret = (1 + total_return) ** (252 / len(returns)) - 1
    ann_vol = returns.std() * np.sqrt(252)
    sharpe = ann_ret / ann_vol if ann_vol > 0 else 0

    wins = [t for t in trades if t > 0]
    losses = [t for t in trades if t <= 0]
    win_rate = len(wins) / len(trades) if trades else 0
    avg_win = np.mean(wins) if wins else 0
    avg_loss = np.mean(losses) if losses else 0
    profit_factor = (sum(wins) / abs(sum(losses))) if losses and sum(losses) != 0 else np.inf

    return {
        "label": label,
        "total_return": total_return,
        "ann_return": ann_ret,
        "ann_vol": ann_vol,
        "sharpe": sharpe,
        "max_drawdown": max_dd,
        "n_trades": len(trades),
        "win_rate": win_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": profit_factor,
    }


# ─────────────────────────────────────────────
# STRATEGIA 1: EMA CROSSOVER SEMPLICE
# EMA9 > EMA21 → long; EMA9 < EMA21 → flat
# ─────────────────────────────────────────────

def ema_crossover(df: pd.DataFrame, fast: int = 9, slow: int = 21) -> dict:
    close = df["close"]
    ema_f = close.ewm(span=fast).mean()
    ema_s = close.ewm(span=slow).mean()

    position = 0
    returns = []
    trades = []
    entry_price = None

    for i in range(1, len(close)):
        signal = 1 if ema_f.iloc[i] > ema_s.iloc[i] else 0
        daily_ret = close.iloc[i] / close.iloc[i - 1] - 1

        if signal == 1 and position == 0:
            position = 1
            entry_price = close.iloc[i]
        elif signal == 0 and position == 1:
            position = 0
            trade_ret = close.iloc[i] / entry_price - 1
            trades.append(trade_ret)
            entry_price = None

        returns.append(daily_ret * position)

    # Chiudi posizione finale
    if position == 1 and entry_price:
        trades.append(close.iloc[-1] / entry_price - 1)

    return compute_metrics(pd.Series(returns), trades,
                           f"EMA({fast},{slow}) Crossover")


# ─────────────────────────────────────────────
# STRATEGIA 2: TREND FOLLOWING AI-LIKE
# EMA cross + RSI + MACD + ATR stop loss
# (replica la TrendFollowingStrategy del sistema)
# ─────────────────────────────────────────────

def trend_following_ai(df: pd.DataFrame) -> dict:
    close = df["close"]
    high  = df["high"]
    low   = df["low"]

    # Indicatori
    ema9  = close.ewm(span=9).mean()
    ema21 = close.ewm(span=21).mean()
    ema50 = close.ewm(span=50).mean()

    # RSI
    delta = close.diff()
    gain  = delta.clip(lower=0).ewm(com=13).mean()
    loss  = (-delta.clip(upper=0)).ewm(com=13).mean()
    rsi   = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    rsi   = rsi.fillna(50)

    # MACD
    macd  = close.ewm(span=12).mean() - close.ewm(span=26).mean()
    signal_line = macd.ewm(span=9).mean()

    # ATR (stop loss dinamico)
    tr = pd.concat([high - low,
                    (high - close.shift()).abs(),
                    (low  - close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(span=14).mean()

    position = 0
    returns  = []
    trades   = []
    entry_price = None
    stop_loss   = None
    take_profit = None

    for i in range(50, len(close)):
        c = close.iloc[i]
        daily_ret = c / close.iloc[i - 1] - 1

        # Stop / Take profit hit
        if position == 1:
            if c <= stop_loss or c >= take_profit:
                trade_ret = c / entry_price - 1
                trades.append(trade_ret)
                position = 0
                entry_price = stop_loss = take_profit = None

        # Entry: EMA cross bullish + RSI non overbought + MACD positivo
        bull_cross  = ema9.iloc[i] > ema21.iloc[i] > ema50.iloc[i]
        rsi_ok      = 40 < rsi.iloc[i] < 70
        macd_ok     = macd.iloc[i] > signal_line.iloc[i] and macd.iloc[i] > 0

        if bull_cross and rsi_ok and macd_ok and position == 0:
            position    = 1
            entry_price = c
            stop_loss   = c - 2 * atr.iloc[i]
            take_profit = c + 3 * atr.iloc[i]

        # Exit: EMA cross bearish
        bear_cross = ema9.iloc[i] < ema21.iloc[i]
        if bear_cross and position == 1:
            trade_ret = c / entry_price - 1
            trades.append(trade_ret)
            position = 0
            entry_price = stop_loss = take_profit = None

        returns.append(daily_ret * position)

    if position == 1 and entry_price:
        trades.append(close.iloc[-1] / entry_price - 1)

    return compute_metrics(pd.Series(returns), trades,
                           "TrendFollowing AI (EMA+RSI+MACD+ATR)")


# ─────────────────────────────────────────────
# STRATEGIA 3: BUY & HOLD (benchmark)
# ─────────────────────────────────────────────

def buy_and_hold(df: pd.DataFrame) -> dict:
    close = df["close"]
    returns = close.pct_change().fillna(0)
    total = (1 + returns).prod() - 1
    trades = [total]
    return compute_metrics(returns, trades, "Buy & Hold")


# ─────────────────────────────────────────────
# STAMPA RISULTATI
# ─────────────────────────────────────────────

def print_results(symbol: str, results: list):
    print(f"\n{'═'*70}")
    print(f"  {symbol} — Periodo: 2 anni, 1D")
    print(f"{'═'*70}")
    header = f"{'Metrica':<22}"
    for r in results:
        header += f"  {r['label'][:20]:<20}"
    print(header)
    print("─" * 70)

    rows = [
        ("Total Return",   "total_return",   "{:+.1%}"),
        ("Annual Return",  "ann_return",      "{:+.1%}"),
        ("Annual Vol",     "ann_vol",         "{:.1%}"),
        ("Sharpe Ratio",   "sharpe",          "{:.2f}"),
        ("Max Drawdown",   "max_drawdown",    "{:.1%}"),
        ("N. Trade",       "n_trades",        "{:.0f}"),
        ("Win Rate",       "win_rate",        "{:.1%}"),
        ("Avg Win",        "avg_win",         "{:+.2%}"),
        ("Avg Loss",       "avg_loss",        "{:+.2%}"),
        ("Profit Factor",  "profit_factor",   "{:.2f}"),
    ]

    for label, key, fmt in rows:
        row = f"  {label:<20}"
        for r in results:
            v = r[key]
            try:
                row += f"  {fmt.format(v):<20}"
            except Exception:
                row += f"  {'N/A':<20}"
        print(row)

    # Verdetto
    print("─" * 70)
    sharpes = [(r["sharpe"], r["label"]) for r in results]
    best = max(sharpes, key=lambda x: x[0])
    print(f"  ★ Miglior Sharpe: {best[1]} ({best[0]:.2f})")

    # Confronto AI vs EMA semplice
    ema_s = next((r["sharpe"] for r in results if "EMA" in r["label"] and "AI" not in r["label"]), None)
    ai_s  = next((r["sharpe"] for r in results if "AI" in r["label"]), None)
    if ema_s and ai_s:
        diff = ai_s - ema_s
        if diff > 0.1:
            verdict = f"✅ AI BATTE EMA semplice (+{diff:.2f} Sharpe)"
        elif diff < -0.1:
            verdict = f"❌ EMA SEMPLICE BATTE AI ({diff:.2f} Sharpe) — semplificare!"
        else:
            verdict = f"⚖️  EQUIVALENTI (diff {diff:.2f}) — AI non aggiunge valore"
        print(f"  {verdict}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

SYMBOLS = {
    "AAPL":     "Stock",
    "BTC-USD":  "Crypto",
    "EURUSD=X": "Forex",
}

if __name__ == "__main__":
    print("\n[Max] Validazione sistema TradingIA vs EMA Crossover semplice")
    print(f"      Avviata: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    all_verdicts = []

    for symbol, asset_type in SYMBOLS.items():
        try:
            print(f"\n  Scaricando {symbol} ({asset_type})...", end=" ", flush=True)
            df = download(symbol, period="2y", interval="1d")
            print(f"{len(df)} barre")

            bh   = buy_and_hold(df)
            ema  = ema_crossover(df, fast=9, slow=21)
            ai   = trend_following_ai(df)

            results = [bh, ema, ai]
            print_results(symbol, results)

            # Raccogli verdetto
            ema_s = ema["sharpe"]
            ai_s  = ai["sharpe"]
            all_verdicts.append((symbol, ema_s, ai_s))

        except Exception as e:
            print(f"\n  ⚠️  Errore su {symbol}: {e}")

    # Riepilogo finale
    print(f"\n{'═'*70}")
    print("  [Max] RIEPILOGO FINALE")
    print(f"{'═'*70}")
    beats = sum(1 for _, e, a in all_verdicts if a > e + 0.1)
    ties  = sum(1 for _, e, a in all_verdicts if abs(a - e) <= 0.1)
    loses = sum(1 for _, e, a in all_verdicts if a < e - 0.1)
    print(f"  AI batte EMA semplice:  {beats}/{len(all_verdicts)} strumenti")
    print(f"  Equivalenti:            {ties}/{len(all_verdicts)} strumenti")
    print(f"  EMA batte AI:           {loses}/{len(all_verdicts)} strumenti")

    if beats == len(all_verdicts):
        print("\n  ✅ Sistema robusto — la complessità AI è giustificata")
    elif loses >= 2:
        print("\n  ❌ Attenzione — il sistema AI non giustifica la sua complessità")
        print("     Raccomandazione: semplificare e ri-testare")
    else:
        print("\n  ⚖️  Risultato misto — verificare per asset class specifica")

    print(f"\n{'═'*70}\n")
