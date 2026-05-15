"""
[Paky] AppState — Singleton stato globale GUI

Fonte unica di verità per tutti i panel. I panel si abbonano ai segnali
di AppState invece di ascoltare SignalBus direttamente.

Uso tipico (panel):
    state = AppState.instance()
    state.equity_changed.connect(self._on_equity)

Uso tipico (main_window):
    from core.signal_bus import get_bus
    AppState.instance().connect_signal_bus(get_bus())
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal


class AppState(QObject):
    """Singleton stato globale GUI. Fonte unica di verità."""

    # ------------------------------------------------------------------
    # Segnali — emessi quando la property corrispondente cambia valore
    # ------------------------------------------------------------------
    engine_running_changed   = pyqtSignal(bool)
    broker_connected_changed = pyqtSignal(bool)
    equity_changed           = pyqtSignal(float)
    daily_pnl_changed        = pyqtSignal(float)
    open_positions_changed   = pyqtSignal(int)
    win_rate_changed         = pyqtSignal(float)
    current_symbol_changed   = pyqtSignal(str)
    current_regime_changed   = pyqtSignal(str)   # "trending"|"choppy"|"cycling"|"unknown"
    current_hurst_changed    = pyqtSignal(float)
    mode_changed             = pyqtSignal(str)   # "paper" | "live"
    broker_latency_changed   = pyqtSignal(int)   # ms
    language_changed         = pyqtSignal(str)   # "it" | "en"

    _instance: "AppState | None" = None

    # ------------------------------------------------------------------
    # Singleton
    # ------------------------------------------------------------------

    @classmethod
    def instance(cls) -> "AppState":
        """Ritorna l'istanza singleton (la crea se non esiste ancora)."""
        if cls._instance is None:
            cls._instance = AppState()
        return cls._instance

    # ------------------------------------------------------------------
    # Costruttore
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        super().__init__()
        # Valori di default sensati
        self._engine_running    = False
        self._broker_connected  = False
        self._equity            = 0.0
        self._daily_pnl         = 0.0
        self._open_positions    = 0
        self._win_rate          = 0.0
        self._current_symbol    = "EURUSD=X"
        self._current_regime    = "unknown"
        self._current_hurst     = 0.5
        self._mode              = "paper"
        self._broker_latency    = 0
        self._language          = "it"

    # ------------------------------------------------------------------
    # Properties con guard di cambio
    # ------------------------------------------------------------------

    @property
    def engine_running(self) -> bool:
        return self._engine_running

    @engine_running.setter
    def engine_running(self, v: bool) -> None:
        if v != self._engine_running:
            self._engine_running = v
            self.engine_running_changed.emit(v)

    # ------------------------------------------------------------------

    @property
    def broker_connected(self) -> bool:
        return self._broker_connected

    @broker_connected.setter
    def broker_connected(self, v: bool) -> None:
        if v != self._broker_connected:
            self._broker_connected = v
            self.broker_connected_changed.emit(v)

    # ------------------------------------------------------------------

    @property
    def equity(self) -> float:
        return self._equity

    @equity.setter
    def equity(self, v: float) -> None:
        if v != self._equity:
            self._equity = v
            self.equity_changed.emit(v)

    # ------------------------------------------------------------------

    @property
    def daily_pnl(self) -> float:
        return self._daily_pnl

    @daily_pnl.setter
    def daily_pnl(self, v: float) -> None:
        if v != self._daily_pnl:
            self._daily_pnl = v
            self.daily_pnl_changed.emit(v)

    # ------------------------------------------------------------------

    @property
    def open_positions(self) -> int:
        return self._open_positions

    @open_positions.setter
    def open_positions(self, v: int) -> None:
        if v != self._open_positions:
            self._open_positions = v
            self.open_positions_changed.emit(v)

    # ------------------------------------------------------------------

    @property
    def win_rate(self) -> float:
        return self._win_rate

    @win_rate.setter
    def win_rate(self, v: float) -> None:
        if v != self._win_rate:
            self._win_rate = v
            self.win_rate_changed.emit(v)

    # ------------------------------------------------------------------

    @property
    def current_symbol(self) -> str:
        return self._current_symbol

    @current_symbol.setter
    def current_symbol(self, v: str) -> None:
        if v != self._current_symbol:
            self._current_symbol = v
            self.current_symbol_changed.emit(v)

    # ------------------------------------------------------------------

    @property
    def current_regime(self) -> str:
        return self._current_regime

    @current_regime.setter
    def current_regime(self, v: str) -> None:
        if v != self._current_regime:
            self._current_regime = v
            self.current_regime_changed.emit(v)

    # ------------------------------------------------------------------

    @property
    def current_hurst(self) -> float:
        return self._current_hurst

    @current_hurst.setter
    def current_hurst(self, v: float) -> None:
        if v != self._current_hurst:
            self._current_hurst = v
            self.current_hurst_changed.emit(v)

    # ------------------------------------------------------------------

    @property
    def mode(self) -> str:
        return self._mode

    @mode.setter
    def mode(self, v: str) -> None:
        if v != self._mode:
            self._mode = v
            self.mode_changed.emit(v)

    # ------------------------------------------------------------------

    @property
    def broker_latency(self) -> int:
        return self._broker_latency

    @broker_latency.setter
    def broker_latency(self, v: int) -> None:
        if v != self._broker_latency:
            self._broker_latency = v
            self.broker_latency_changed.emit(v)

    # ------------------------------------------------------------------

    @property
    def language(self) -> str:
        return self._language

    @language.setter
    def language(self, v: str) -> None:
        if v not in ("it", "en"):
            return
        if v != self._language:
            self._language = v
            from gui.i18n import set_language
            set_language(v)
            self.language_changed.emit(v)

    # ------------------------------------------------------------------
    # Bridge SignalBus → AppState
    # ------------------------------------------------------------------

    def connect_signal_bus(self, bus) -> None:
        """
        Collega i segnali Qt del SignalBus a questo AppState.

        Da chiamare UNA SOLA VOLTA in main_window.py dopo la creazione
        dell'istanza singleton:

            from core.signal_bus import get_bus
            AppState.instance().connect_signal_bus(get_bus())

        Args:
            bus: istanza di SignalBus (da core.signal_bus.get_bus())
        """
        bus.qt.engine_started.connect(self._on_engine_started)
        bus.qt.engine_stopped.connect(self._on_engine_stopped)
        bus.qt.engine_status.connect(self._on_engine_status)

    # ------------------------------------------------------------------
    # Slot interni (privati)
    # ------------------------------------------------------------------

    def _on_engine_started(self) -> None:
        self.engine_running = True

    def _on_engine_stopped(self) -> None:
        self.engine_running = False

    def _on_engine_status(self, ev) -> None:
        """Gestisce EngineStatusEvent: aggiorna equity, P&L, posizioni e mode."""
        self.equity          = ev.equity
        self.daily_pnl       = ev.daily_pnl
        self.open_positions  = ev.open_positions
        self.mode            = ev.mode
