"""
Pattern Strategy — Wrapper per integrare il riconoscimento pattern
nel flusso di segnali esistente (StrategyManager → aggregazione → MetaLearner).

PatternStrategy non ha stato proprio: legge i pattern confermati
dal PatternObserver singleton e li converte in TradeSignal.
Il rilevamento effettivo avviene nei due loop dell'orchestrator
(_pattern_watchlist_loop, _pattern_position_loop).
"""

from typing import List

import pandas as pd

from config.settings import settings
from core.pattern_observer import get_pattern_observer
from indicators.patterns import PatternDetector
from strategies.base_strategy import BaseStrategy, TradeSignal
from utils.logger import get_logger

logger = get_logger.bind(name="strategies.pattern")


class PatternStrategy(BaseStrategy):
    """
    Genera TradeSignal dai pattern tecnici confermati.

    Usata da StrategyManager.evaluate() come qualunque altra strategia,
    così i suoi segnali vengono aggregati e pesati insieme agli altri.
    Richiede pattern.enabled = True in settings.
    """

    name = "pattern_recognition"

    def __init__(self, timeframe: str = "1h"):
        super().__init__(timeframe=timeframe)
        self.active = settings.pattern.enabled

    def generate_signals(self, symbol: str, df: pd.DataFrame) -> List[TradeSignal]:
        """
        1. Rileva pattern sull'ultimo df disponibile
        2. Aggiorna lo stato dell'observer (sincrono, per uso da thread pool)
        3. Ritorna segnali dai pattern già confermati nell'observer

        Nota: `asyncio.run_until_complete` non può essere usato in un thread
        sincrono se il loop è già in esecuzione. Usiamo la versione sincrona
        dell'observer tramite asyncio.get_event_loop().run_until_complete solo
        se non siamo nel thread asyncio principale.
        """
        if not self.active:
            return []

        observer = get_pattern_observer()
        signals: List[TradeSignal] = []

        try:
            # Soglie calibrate per asset class del simbolo
            asset_class = settings.asset_type_map.get(symbol, "stock")
            min_conf, min_sig_conf, _ = settings.pattern.for_asset_class(asset_class)

            # Soglia "istantanea" per candlestick di alta confidenza:
            # +0.10 sopra min_signal_confidence dell'asset class, mai sotto 0.75
            instant_threshold = max(min_sig_conf + 0.10, 0.75)

            # Rileva pattern sull'ultimo df
            raw_patterns = PatternDetector.detect_all(df, self.timeframe)
            raw_filtered = [
                p for p in raw_patterns
                if p.confidence >= min_conf
            ]

            # Recupera pattern già confermati (non consumati) dall'observer
            # Usiamo l'API sincrona di accesso diretto (no await) per sicurezza
            confirmed_in_observer = [
                obs
                for obs in observer._obs.get(symbol, [])
                if obs.status == "confirmed" and obs.id not in observer._delivered
            ]

            current_price = float(df["close"].iloc[-1])
            for obs in confirmed_in_observer:
                if obs.raw.confidence >= min_sig_conf:
                    sig = observer.to_trade_signal(obs, current_price)
                    signals.append(sig)
                    observer._delivered.add(obs.id)

            # Aggiungi anche pattern di altissima confidenza rilevati ora
            # (che non sono ancora nell'observer — es. Marubozu oltre soglia istantanea)
            for raw in raw_filtered:
                if raw.confidence >= instant_threshold and raw.bars_involved <= 3:
                    direction = "buy" if raw.direction == "bullish" else \
                               "sell" if raw.direction == "bearish" else None
                    if direction:
                        signals.append(TradeSignal(
                            symbol=symbol,
                            direction=direction,
                            confidence=raw.confidence,
                            strategy_name=f"pattern_{raw.name.lower().replace(' ', '_')}",
                            price=current_price,
                            stop_loss=raw.invalidation_price,
                            take_profit=raw.target_price,
                            timeframe=self.timeframe,
                            metadata={
                                "pattern_name":  raw.name,
                                "bars_involved": raw.bars_involved,
                                "instant":       True,   # segnale immediato, non da osservazione
                            },
                        ))

        except Exception as e:
            logger.debug(f"PatternStrategy error on {symbol}: {e}")

        if signals:
            logger.info(f"[pattern] {symbol}: {len(signals)} segnali pattern")
        return signals
