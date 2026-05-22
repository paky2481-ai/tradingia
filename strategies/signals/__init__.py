"""
Segnali concreti del framework pluggabile.

Ogni modulo espone una classe Signal (sottoclasse di strategies.signal_base.Signal)
e la registra automaticamente quando importato.

Segnali disponibili:
  - MomentumCrossSectionalSignal  (scope CROSS_ASSET)
  - PairsMeanReversionSignal      (scope PAIR)
"""

from strategies.signals.momentum_cross_sectional import MomentumCrossSectionalSignal
from strategies.signals.pairs_mean_reversion import PairsMeanReversionSignal

__all__ = [
    "MomentumCrossSectionalSignal",
    "PairsMeanReversionSignal",
]
