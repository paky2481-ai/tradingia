"""
TestClient — client per il TestServer di TradingIA.

Uso:
    python scripts/test_client.py ping
    python scripts/test_client.py get_ohlcv AAPL 1h
    python scripts/test_client.py run_indicators AAPL 1h
    python scripts/test_client.py run_backtest AAPL trend_following 1h 60
    python scripts/test_client.py run_signal AAPL trend_following 1h
    python scripts/test_client.py get_status
    python scripts/test_client.py get_logs 30
    python scripts/test_client.py monitor        # stream log in tempo reale

Il client esce automaticamente dopo aver ricevuto la risposta.
In modalità 'monitor' rimane in ascolto finché non si preme Ctrl+C.
"""

import asyncio
import json
import sys

HOST = "127.0.0.1"
PORT = 7779


async def send_command(cmd: dict, monitor: bool = False) -> None:
    try:
        reader, writer = await asyncio.open_connection(HOST, PORT)
    except ConnectionRefusedError:
        print(f"[ERRORE] Impossibile connettersi a {HOST}:{PORT}")
        print("  Assicurati che l'app TradingIA sia in esecuzione.")
        return

    # Invia il comando
    writer.write((json.dumps(cmd) + "\n").encode())
    await writer.drain()

    # Leggi le risposte
    got_response = False
    try:
        while True:
            line = await asyncio.wait_for(reader.readline(), timeout=30.0)
            if not line:
                break
            try:
                msg = json.loads(line.decode().strip())
            except json.JSONDecodeError:
                continue

            if msg.get("type") == "log":
                # Log entry dallo stream (buffer iniziale o real-time)
                level = msg.get("level", "")
                color = {
                    "DEBUG":    "\033[90m",
                    "INFO":     "\033[36m",
                    "SUCCESS":  "\033[32m",
                    "WARNING":  "\033[33m",
                    "ERROR":    "\033[31m",
                    "CRITICAL": "\033[35m",
                }.get(level, "")
                reset = "\033[0m"
                print(f"{color}[LOG] {msg['time']} {level:8s} {msg['name']} — {msg['msg']}{reset}")

            elif "status" in msg:
                # Risposta al comando
                got_response = True
                if msg["status"] == "ok":
                    result = msg["result"]
                    print(f"\n{'─'*60}")
                    print(f"  RISULTATO: {cmd.get('cmd', '?').upper()}")
                    print(f"{'─'*60}")
                    _pretty_print(result)
                    print(f"{'─'*60}\n")
                else:
                    print(f"\n[ERRORE] {msg.get('message', 'Errore sconosciuto')}\n")

                if not monitor:
                    break

    except asyncio.TimeoutError:
        if not got_response:
            print("[TIMEOUT] Nessuna risposta dal server entro 30s")
    except KeyboardInterrupt:
        print("\n[Interrotto]")
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


def _pretty_print(obj, indent: int = 2) -> None:
    """Stampa un dict in modo leggibile."""
    prefix = " " * indent
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                print(f"{prefix}{k}:")
                _pretty_print(v, indent + 2)
            else:
                print(f"{prefix}{k}: {v}")
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            print(f"{prefix}[{i}]")
            _pretty_print(item, indent + 2)
    else:
        print(f"{prefix}{obj}")


def _build_command(args: list) -> tuple[dict, bool]:
    """Costruisce il comando JSON dagli argomenti CLI."""
    monitor = False
    if not args:
        return {"cmd": "ping"}, False

    name = args[0].lower()

    if name == "ping":
        return {"cmd": "ping"}, False

    elif name == "get_logs":
        n = int(args[1]) if len(args) > 1 else 50
        return {"cmd": "get_logs", "n": n}, False

    elif name == "get_ohlcv":
        symbol = args[1] if len(args) > 1 else "AAPL"
        tf     = args[2] if len(args) > 2 else "1h"
        limit  = int(args[3]) if len(args) > 3 else 100
        return {"cmd": "get_ohlcv", "symbol": symbol, "timeframe": tf, "limit": limit}, False

    elif name == "run_indicators":
        symbol = args[1] if len(args) > 1 else "AAPL"
        tf     = args[2] if len(args) > 2 else "1h"
        return {"cmd": "run_indicators", "symbol": symbol, "timeframe": tf}, False

    elif name == "run_backtest":
        symbol   = args[1] if len(args) > 1 else "AAPL"
        strategy = args[2] if len(args) > 2 else "trend_following"
        tf       = args[3] if len(args) > 3 else "1h"
        days     = int(args[4]) if len(args) > 4 else 60
        capital  = float(args[5]) if len(args) > 5 else 10000.0
        return {
            "cmd": "run_backtest",
            "symbol": symbol, "strategy": strategy,
            "timeframe": tf, "days": days, "capital": capital,
        }, False

    elif name == "run_signal":
        symbol   = args[1] if len(args) > 1 else "AAPL"
        strategy = args[2] if len(args) > 2 else "trend_following"
        tf       = args[3] if len(args) > 3 else "1h"
        return {"cmd": "run_signal", "symbol": symbol, "strategy": strategy, "timeframe": tf}, False

    elif name == "get_status":
        return {"cmd": "get_status"}, False

    elif name == "monitor":
        # Connessione persistente: stampa solo i log in real-time
        monitor = True
        return {"cmd": "ping"}, True  # manda ping per ricevere il buffer iniziale

    else:
        print(f"Comando sconosciuto: {name}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    args = sys.argv[1:]
    cmd, monitor = _build_command(args)
    asyncio.run(send_command(cmd, monitor=monitor))
