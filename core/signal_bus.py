"""
[Paky] Signal Bus — Event bridge tra Engine e GUI

Il bus è l'unico punto di contatto tra il motore di trading (asyncio)
e l'interfaccia grafica (PyQt6).

Engine emette eventi → Bus li converte in Qt signals → GUI aggiorna la UI.
GUI invia comandi → Bus li mette in queue → Engine li esegue.

Eventi emessi dall'engine:
  - engine_started / engine_stopped
  - scan_result       ← segnale analizzato per ogni strumento
  - trade_opened      ← nuovo trade eseguito
  - trade_closed      ← posizione chiusa (SL/TP/manuale)
  - position_update   ← P&L live aggiornato
  - trend_alert       ← cambio di trend rilevato
  - engine_status     ← heartbeat ogni 30s (equity, DD, ecc.)

Comandi inviati dalla GUI:
  - open_trade(symbol, direction, qty, sl, tp)
  - close_trade(symbol)
  - set_mode(paper|live)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from PyQt6.QtCore import QObject, pyqtSignal


# ─────────────────────────────────────────────────────────────────────────────
# Data classes per gli eventi
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ScanResultEvent:
    symbol: str
    display: str
    direction: str          # "buy" | "sell" | "none"
    confidence: float
    strategy: str
    reason: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class TradeOpenedEvent:
    symbol: str
    display: str
    direction: str
    quantity: float
    entry_price: float
    stop_loss: float
    take_profit: float
    strategy: str
    risk_eur: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class TradeClosedEvent:
    symbol: str
    display: str
    direction: str
    quantity: float
    entry_price: float
    exit_price: float
    pnl: float
    reason: str             # "stop_loss" | "take_profit" | "manual"
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class PositionUpdateEvent:
    symbol: str
    display: str
    direction: str
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    pnl_pct: float
    stop_loss: float
    take_profit: float


@dataclass
class TrendAlertEvent:
    symbol: str
    display: str
    alert_type: str         # "reversal_bull" | "reversal_bear" | "trend_weakening"
    confidence: float       # 0–100
    signals: List[str]      # lista segnali che hanno scattato
    description: str
    timeframe: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class PatternAlertEvent:
    symbol: str
    pattern_name: str
    direction: str          # "bullish" | "bearish" | "neutral"
    status: str             # "forming" | "confirmed" | "failed" | "expired"
    confidence: float
    timeframe: str
    target_price: Optional[float] = None
    observation_id: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class EngineStatusEvent:
    running: bool
    mode: str
    equity: float
    daily_pnl: float
    drawdown_pct: float
    open_positions: int
    total_return_pct: float
    last_scan: str


# ─────────────────────────────────────────────────────────────────────────────
# Eventi Fase 5 — AI / Risk / Loop heartbeat / Correlazioni
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AIResultEvent:
    """Payload AutoConfigResult: emesso da orchestrator quando AutoConfig termina."""
    symbol: str
    regime: str             # "trending" | "choppy" | "cycling" | "unknown"
    hurst: float            # esponente Hurst [0, 1]
    confidence: float       # confidenza modello AI [0, 1]
    prediction: str         # "long" | "short" | "neutral"
    price_direction: float  # ritorno atteso a 20 barre (firmato)
    strategy: str = ""      # nome strategia scelta
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class KellyUpdateEvent:
    """Kelly % suggerito da RiskManager."""
    kelly_pct: float        # [0, 1] frazione Kelly raccomandata
    win_rate: float = 0.0   # win rate corrente usato nel calcolo
    avg_win_loss_ratio: float = 0.0  # avg_win / avg_loss
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RegimeUpdateEvent:
    """Regime + hurst per il simbolo corrente (broadcast ad ogni scan)."""
    symbol: str
    regime: str             # "trending" | "choppy" | "cycling" | "unknown"
    hurst: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class LoopHeartbeatEvent:
    """Heartbeat di un loop async (per StatusDot pulse)."""
    loop_name: str          # "4h_scan" | "1h_scan" | "trend_detect" | "position_check"
    state: str = "active"   # "idle" | "active" | "error" | "loading"
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CorrelationUpdateEvent:
    """Matrice correlazioni tra posizioni aperte (numpy o list of lists)."""
    matrix: Any             # np.ndarray N×N oppure list[list[float]]
    symbols: List[str]      # etichette assi (in ordine matrice)
    timestamp: datetime = field(default_factory=datetime.utcnow)


# ─────────────────────────────────────────────────────────────────────────────
# Comandi GUI → Engine
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class OpenTradeCommand:
    symbol: str
    direction: str
    quantity: float
    stop_loss: float
    take_profit: float


@dataclass
class CloseTradeCommand:
    symbol: str


# ─────────────────────────────────────────────────────────────────────────────
# Qt Signal Emitter (deve vivere nel thread Qt)
# ─────────────────────────────────────────────────────────────────────────────

class _BusQtEmitter(QObject):
    """Qt signals per comunicare dal thread asyncio al thread Qt."""

    scan_result     = pyqtSignal(object)   # ScanResultEvent
    trade_opened    = pyqtSignal(object)   # TradeOpenedEvent
    trade_closed    = pyqtSignal(object)   # TradeClosedEvent
    position_update = pyqtSignal(object)   # PositionUpdateEvent
    trend_alert     = pyqtSignal(object)   # TrendAlertEvent
    engine_status   = pyqtSignal(object)   # EngineStatusEvent
    pattern_alert   = pyqtSignal(object)   # PatternAlertEvent
    engine_started  = pyqtSignal()
    engine_stopped  = pyqtSignal()
    log_message     = pyqtSignal(str, str)  # message, color

    # Fase 5 — AI / Risk / Loop / Correlazioni
    ai_result          = pyqtSignal(object)        # AIResultEvent
    kelly_update       = pyqtSignal(float)         # frazione Kelly suggerita (semplice)
    regime_update      = pyqtSignal(str, float)    # (regime, hurst) per simbolo corrente
    loop_heartbeat     = pyqtSignal(str)           # loop_name (es. "4h_scan")
    correlation_update = pyqtSignal(object)        # CorrelationUpdateEvent

    # Fase A.1 — simbolo correntemente scansionato dal backend
    current_scan_symbol = pyqtSignal(str, str)     # (symbol_yf, loop_name)

    # Signal Registry — S2
    registry_changed = pyqtSignal()                # segnale registrato/rimosso/abilitato
    weight_updated   = pyqtSignal(str, float)      # (signal_id, new_weight)


# ─────────────────────────────────────────────────────────────────────────────
# Signal Bus Singleton
# ─────────────────────────────────────────────────────────────────────────────

class SignalBus:
    """
    Singleton bus. Usato sia dall'engine (asyncio) che dalla GUI (Qt).

    Usage nell'engine:
        bus = get_bus()
        bus.emit_scan_result(ScanResultEvent(...))

    Usage nella GUI:
        bus = get_bus()
        bus.qt.scan_result.connect(my_slot)
        bus.qt.trade_opened.connect(my_other_slot)

    Comandi dalla GUI all'engine:
        await bus.send_command(OpenTradeCommand(...))
    """

    def __init__(self):
        self.qt = _BusQtEmitter()
        self._command_queue: asyncio.Queue = asyncio.Queue()

    # ── Engine → GUI (thread-safe via QMetaObject) ─────────────────────────

    def emit_scan_result(self, event: ScanResultEvent):
        self.qt.scan_result.emit(event)

    def emit_trade_opened(self, event: TradeOpenedEvent):
        self.qt.trade_opened.emit(event)

    def emit_trade_closed(self, event: TradeClosedEvent):
        self.qt.trade_closed.emit(event)

    def emit_position_update(self, event: PositionUpdateEvent):
        self.qt.position_update.emit(event)

    def emit_trend_alert(self, event: TrendAlertEvent):
        self.qt.trend_alert.emit(event)

    def emit_pattern_alert(self, event: PatternAlertEvent):
        self.qt.pattern_alert.emit(event)

    def emit_engine_status(self, event: EngineStatusEvent):
        self.qt.engine_status.emit(event)

    def emit_log(self, message: str, color: str = "#8b949e"):
        self.qt.log_message.emit(message, color)

    def emit_started(self):
        self.qt.engine_started.emit()

    def emit_stopped(self):
        self.qt.engine_stopped.emit()

    # ── Fase 5: AI / Risk / Loop / Correlazioni ───────────────────────────

    def emit_ai_result(self, event: AIResultEvent):
        """Emette risultato AutoConfig. Anche scatena regime_update separato."""
        self.qt.ai_result.emit(event)
        self.qt.regime_update.emit(event.regime, event.hurst)

    def emit_kelly_update(self, kelly_pct: float):
        """Kelly% suggerito (frazione [0, 1])."""
        self.qt.kelly_update.emit(float(kelly_pct))

    def emit_regime_update(self, regime: str, hurst: float):
        """Regime + hurst per simbolo corrente (standalone, senza AIResult completo)."""
        self.qt.regime_update.emit(regime, float(hurst))

    def emit_loop_heartbeat(self, loop_name: str):
        """Heartbeat di un loop async per StatusDot pulse."""
        self.qt.loop_heartbeat.emit(loop_name)

    def emit_correlation_update(self, event: CorrelationUpdateEvent):
        """Matrice correlazioni posizioni aperte."""
        self.qt.correlation_update.emit(event)

    def emit_current_scan_symbol(self, symbol: str, loop_name: str):
        """Emette il simbolo che il backend sta elaborando adesso (Fase A.1)."""
        self.qt.current_scan_symbol.emit(symbol, loop_name)

    # ── S2: Signal Registry ───────────────────────────────────────────────

    def emit_registry_changed(self):
        """Segnale registrato/rimosso/abilitato nel SignalRegistry."""
        self.qt.registry_changed.emit()

    def emit_weight_updated(self, signal_id: str, weight: float):
        """Peso di un segnale aggiornato nel SignalRegistry."""
        self.qt.weight_updated.emit(signal_id, float(weight))

    # ── GUI → Engine ───────────────────────────────────────────────────────

    async def send_command(self, cmd):
        """GUI invia comando all'engine. Thread-safe."""
        await self._command_queue.put(cmd)

    def send_command_sync(self, cmd):
        """Versione sincrona per slot Qt (usa loop corrente)."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self._command_queue.put(cmd))
            else:
                loop.run_until_complete(self._command_queue.put(cmd))
        except Exception:
            pass

    async def get_command(self) -> Any:
        """Engine chiama questo per ricevere comandi dalla GUI."""
        return await self._command_queue.get()

    async def get_command_nowait(self):
        """Non-blocking: ritorna None se nessun comando."""
        try:
            return self._command_queue.get_nowait()
        except asyncio.QueueEmpty:
            return None


# Singleton globale
_bus: Optional[SignalBus] = None


def get_bus() -> SignalBus:
    global _bus
    if _bus is None:
        _bus = SignalBus()
    return _bus
