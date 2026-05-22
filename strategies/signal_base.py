"""
Abstract interface for pluggable signal generators — the atomic unit of the
composable strategy framework.

Design intent
-------------
A Signal is NOT a strategy: it computes a directional score for one or more
assets given market data, without knowing about portfolio construction or
execution.  The SignalRegistry (Paky) handles composition, weighting, and
the translation back to TradeSignal for the Backtester.

Relationship with BaseStrategy
-------------------------------
Signal is a SIBLING of BaseStrategy, not a subclass.  BaseStrategy remains
the Backtester-facing contract ("generate_signals → List[TradeSignal]").
A SignalStrategy adapter (also here) wraps any Signal into a BaseStrategy so
the existing Backtester.run() and StrategyManager continue to work unchanged.

Why not extend BaseStrategy directly?
  BaseStrategy.generate_signals takes a SINGLE symbol and a SINGLE DataFrame.
  Cross-sectional signals (momentum ranking) need a PANEL of assets at once.
  Forcing a cross-sectional signal through the per-symbol interface would
  require calling it once per symbol and then re-aggregating the panel
  externally — that breaks the ranking semantics (the score of asset i is
  meaningful only relative to the scores of assets j ≠ i computed on the
  same bar).  A separate compute() method that accepts either a single
  (symbol, df) pair or a dict of {symbol: df} panels solves this cleanly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

import pandas as pd

from strategies.base_strategy import BaseStrategy, TradeSignal


# ── Enumerations ──────────────────────────────────────────────────────────────

class SignalCategory(str, Enum):
    """Broad family a signal belongs to.  Used by the registry for filtering."""
    MOMENTUM        = "momentum"
    MEAN_REVERSION  = "mean_reversion"
    PATTERN         = "pattern"
    TECHNICAL       = "technical"
    FUNDAMENTAL     = "fundamental"
    VOLATILITY      = "volatility"
    SENTIMENT       = "sentiment"


class SignalScope(str, Enum):
    """
    Whether the signal operates per-asset or on a panel of assets.

    PER_ASSET   — receives one (symbol, OHLCV DataFrame) at a time.
                  Examples: RSI mean-reversion, pattern recognition.
    CROSS_ASSET — receives a Dict[symbol → DataFrame]; rankings are computed
                  relative to the full panel.
                  Example: momentum cross-sectional (long top decile,
                  short bottom decile).  The score of each asset is only
                  meaningful within the context of the full universe.
    PAIR        — receives exactly two series (a spread / cointegrated pair).
                  Example: pairs mean reversion on a z-score spread.
    """
    PER_ASSET   = "per_asset"
    CROSS_ASSET = "cross_asset"
    PAIR        = "pair"


# ── Parameter descriptor ──────────────────────────────────────────────────────

@dataclass
class ParamSpec:
    """
    Descriptor of a single configurable parameter.

    The GUI reads this list to render controls automatically.
    The SignalRegistry uses it to validate incoming configuration updates.

    Attributes
    ----------
    name        : internal attribute name on the Signal instance.
    dtype       : Python type hint string; used for GUI widget selection.
                  Supported: 'int', 'float', 'bool', 'str'.
    default     : value used when no override is provided.
    lo, hi      : inclusive bounds for numeric types (None = unbounded).
    choices     : allowed values for categorical str parameters.
    description : human-readable label for the GUI tooltip.
    """
    name:        str
    dtype:       Literal["int", "float", "bool", "str"]
    default:     Any
    lo:          Optional[Union[int, float]] = None
    hi:          Optional[Union[int, float]] = None
    choices:     Optional[List[Any]]         = None
    description: str                         = ""


# ── Output dataclass ──────────────────────────────────────────────────────────

@dataclass
class SignalOutput:
    """
    Normalised output of a single signal evaluation for one asset.

    score       : continuous value in [-1, +1].
                  -1 = maximum short conviction.
                   0 = flat / no opinion.
                  +1 = maximum long conviction.
                  The score is what the SignalRegistry multiplies by the
                  signal weight when composing an ensemble.

    confidence  : in [0, 1].
                  Represents how reliable the score estimate is, NOT its
                  direction.  A score of +0.9 with confidence 0.3 means
                  "mildly long, but the setup is noisy".  The risk engine
                  (Kelly, position sizing) uses confidence, not score.

    direction   : derived from sign(score), provided explicitly to avoid
                  floating-point sign ambiguity near zero.  'flat' when
                  |score| < direction_threshold (defined by the Signal).

    symbol      : asset this output refers to.  For CROSS_ASSET signals the
                  caller receives one SignalOutput per asset in the panel.

    metadata    : arbitrary key-value pairs for logging, GUI display, and
                  VALIDATION_PROTOCOL tracing (e.g. z_score, half_life,
                  mom_rank, adf_pvalue).  These flow into TradeSignal.metadata
                  when the adapter converts the output.
    """
    symbol:     str
    score:      float                        # in [-1, +1]
    confidence: float                        # in [0,  1]
    direction:  Literal["long", "short", "flat"]
    metadata:   Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not (-1.0 <= self.score <= 1.0):
            raise ValueError(f"SignalOutput.score must be in [-1, 1], got {self.score}")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"SignalOutput.confidence must be in [0, 1], got {self.confidence}"
            )
        if self.direction not in ("long", "short", "flat"):
            raise ValueError(f"Invalid direction: {self.direction}")


# ── Abstract base ─────────────────────────────────────────────────────────────

class Signal(ABC):
    """
    Abstract interface for every pluggable signal in the framework.

    Concrete subclasses must implement:
      - compute()        — the actual mathematical logic.
      - param_specs      — class-level list of ParamSpec descriptors.

    Concrete subclasses should NOT implement order sizing, portfolio
    construction, or execution logic; those belong to the risk engine.

    Thread safety
    -------------
    compute() may be called from asyncio.to_thread() by the SignalRegistry.
    Implementations must be stateless with respect to the current bar (i.e.
    do not cache bar-level intermediate results as instance attributes).
    Rolling state (e.g. online mean/std for the z-score) is acceptable if
    guarded with a lock, but the simpler design is to recompute it from the
    DataFrame window passed in.
    """

    # ── Class-level metadata (override in each concrete class) ─────────────

    # Unique snake_case identifier.  Must be stable across releases because
    # it is used as the registry key and persisted to the database.
    signal_id: str = ""

    # Human-readable label for the GUI.
    label: str = ""

    # Determines which overload of compute() is called.
    scope: SignalScope = SignalScope.PER_ASSET

    category: SignalCategory = SignalCategory.TECHNICAL

    # Weight assigned when the registry is first initialised.
    # The user can override it via SignalRegistry.set_weight().
    default_weight: float = 1.0

    # Whether the signal is active when the registry loads it.
    default_enabled: bool = True

    # Parameter descriptors.  The GUI iterates this to build config panels.
    param_specs: List[ParamSpec] = []

    # ── Instance state ──────────────────────────────────────────────────────

    def __init__(self, **kwargs: Any) -> None:
        """
        Initialise with optional parameter overrides.

        Any key in kwargs must match a name in self.param_specs; others are
        silently ignored to allow forward-compatible config blobs.
        """
        self.enabled: bool  = self.default_enabled
        self.weight:  float = self.default_weight

        # Apply declared defaults first, then caller overrides.
        for spec in self.param_specs:
            setattr(self, spec.name, spec.default)
        for spec in self.param_specs:
            if spec.name in kwargs:
                setattr(self, spec.name, kwargs[spec.name])

    # ── Core computation — three overloads dispatched by scope ─────────────

    @abstractmethod
    def compute(
        self,
        data: Union[
            Tuple[str, pd.DataFrame],           # PER_ASSET
            Dict[str, pd.DataFrame],            # CROSS_ASSET
            Tuple[str, pd.DataFrame,            # PAIR: (sym_a, df_a, sym_b, df_b)
                  str, pd.DataFrame],
        ],
    ) -> List[SignalOutput]:
        """
        Compute normalised signal outputs.

        Parameters
        ----------
        data :
            - PER_ASSET  → (symbol: str, df: pd.DataFrame)
              df is a standard OHLCV DataFrame, index = DatetimeIndex.
            - CROSS_ASSET → Dict[symbol, df]
              All DataFrames share the same DatetimeIndex (aligned by caller).
              The signal receives the full panel and must return one
              SignalOutput per symbol.
            - PAIR → (sym_a, df_a, sym_b, df_b)
              Two aligned DataFrames.  The signal returns exactly two
              SignalOutput objects (one per leg of the trade).

        Returns
        -------
        List[SignalOutput]
            One entry per asset.  Return an empty list if the signal cannot
            produce a reliable estimate (e.g. insufficient history, failed
            stationarity test).  Never raise; log and return [].
        """
        ...

    # ── Parameter introspection for GUI ────────────────────────────────────

    def get_params(self) -> Dict[str, Any]:
        """Return current parameter values, keyed by param name."""
        return {spec.name: getattr(self, spec.name) for spec in self.param_specs}

    def set_params(self, **kwargs: Any) -> None:
        """
        Update parameters at runtime (called by the GUI config panel).

        Only recognised param names are applied; unknown keys are ignored.
        Raises ValueError if a value violates the ParamSpec bounds.
        """
        spec_map = {s.name: s for s in self.param_specs}
        for key, value in kwargs.items():
            if key not in spec_map:
                continue
            spec = spec_map[key]
            if spec.dtype in ("int", "float"):
                if spec.lo is not None and value < spec.lo:
                    raise ValueError(
                        f"Parameter '{key}' = {value} is below minimum {spec.lo}"
                    )
                if spec.hi is not None and value > spec.hi:
                    raise ValueError(
                        f"Parameter '{key}' = {value} exceeds maximum {spec.hi}"
                    )
            if spec.choices is not None and value not in spec.choices:
                raise ValueError(
                    f"Parameter '{key}' = {value!r} not in {spec.choices}"
                )
            setattr(self, key, value)

    def registry_metadata(self) -> Dict[str, Any]:
        """
        Serialisable dict consumed by SignalRegistry.register() and the GUI.

        Contains everything needed to reconstruct the signal config and to
        render a description card in the plugin browser.
        """
        return {
            "signal_id":       self.signal_id,
            "label":           self.label,
            "scope":           self.scope.value,
            "category":        self.category.value,
            "default_weight":  self.default_weight,
            "default_enabled": self.default_enabled,
            "params":          [
                {
                    "name":        s.name,
                    "dtype":       s.dtype,
                    "default":     s.default,
                    "lo":          s.lo,
                    "hi":          s.hi,
                    "choices":     s.choices,
                    "description": s.description,
                }
                for s in self.param_specs
            ],
        }


# ── BaseStrategy adapter ──────────────────────────────────────────────────────

class SignalStrategy(BaseStrategy):
    """
    Adapter: wraps a PER_ASSET or PAIR Signal into a BaseStrategy so that
    the existing Backtester.run() and StrategyManager continue to work
    without modification.

    Behaviour
    ---------
    - Calls signal.compute((symbol, df)) and maps each SignalOutput to a
      TradeSignal using the direction/confidence semantics.
    - CROSS_ASSET signals cannot be wrapped by this adapter; they need a
      dedicated portfolio-level runner (future work).
    - The `score` is stored in TradeSignal.metadata["score"] for downstream
      risk sizing that wants a continuous input rather than a binary direction.

    Usage
    -----
        registry = SignalRegistry()
        registry.register(MyCrossSignal())
        # For Backtester compatibility:
        adapter = SignalStrategy(MyPerAssetSignal())
        backtester.run(df, adapter)
    """

    def __init__(self, signal: Signal, timeframe: str = "1h") -> None:
        if signal.scope == SignalScope.CROSS_ASSET:
            raise TypeError(
                "SignalStrategy cannot wrap a CROSS_ASSET signal.  "
                "Use a portfolio-level runner instead."
            )
        super().__init__(timeframe=timeframe)
        self.signal = signal
        self.name   = signal.signal_id

    def generate_signals(self, symbol: str, df: pd.DataFrame) -> List[TradeSignal]:
        if not self.signal.enabled:
            return []

        if self.signal.scope == SignalScope.PAIR:
            # A PAIR signal wrapped as a per-symbol strategy is only useful
            # when the caller passes pre-spread data as df.  The pair partner
            # symbol is stored in df.attrs["pair_symbol"] by convention.
            pair_symbol = df.attrs.get("pair_symbol", symbol + "_PAIR")
            pair_df     = df.attrs.get("pair_df", df)
            data = (symbol, df, pair_symbol, pair_df)
        else:
            data = (symbol, df)

        outputs = self.signal.compute(data)

        result: List[TradeSignal] = []
        for out in outputs:
            if out.direction == "flat":
                continue
            result.append(TradeSignal(
                symbol        = out.symbol,
                direction     = "buy" if out.direction == "long" else "sell",
                confidence    = out.confidence,
                strategy_name = self.signal.signal_id,
                timeframe     = self.timeframe,
                metadata      = {
                    "score":    out.score,
                    "scope":    self.signal.scope.value,
                    "category": self.signal.category.value,
                    **out.metadata,
                },
            ))
        return result


# ── Concrete signal signatures (stub — body NOT implemented) ──────────────────
# These show Paky the expected class structure for the first two signals
# defined in VALIDATION_PROTOCOL §1.  Uncomment and fill compute() when
# the signal passes the statistical protocol.

class MomentumCrossSectionalSignal(Signal):
    """
    Cross-sectional momentum ranking signal (VALIDATION_PROTOCOL §1, Signal A).

    Math
    ----
    Mom_adj(i, t) = P(i, t-S) / P(i, t-L) - 1
    S = lookback_skip (neutralises short-term reversal)
    L = lookback_long

    Universe is ranked by Mom_adj.  Assets in the top `top_quantile` fraction
    receive score ≈ +1; assets in the bottom fraction receive score ≈ -1.
    The raw rank is linearly rescaled to [-1, +1] so that score carries
    relative conviction within the panel.

    Regime filter: z-score rolling of VIX (column "vix" in the panel df for
    "VIX" symbol, or passed via df.attrs["vix_zscore"]).  When vix_zscore
    exceeds `vix_z_threshold`, all scores are zeroed (flat regime).
    VIX z-score uses a rolling window, not a fixed threshold, to avoid
    implicit in-sample optimisation.

    Scope: CROSS_ASSET — the full universe panel must be passed at once.
    """

    signal_id       = "momentum_cross_sectional"
    label           = "Momentum Cross-Sectional"
    scope           = SignalScope.CROSS_ASSET
    category        = SignalCategory.MOMENTUM
    default_weight  = 1.0
    default_enabled = False   # disabled until VALIDATION_PROTOCOL §4 is passed

    param_specs = [
        ParamSpec("lookback_long",   "int",   252, lo=60,  hi=504,
                  description="Bars for the long momentum window (L)"),
        ParamSpec("lookback_skip",   "int",   5,   lo=1,   hi=20,
                  description="Recent bars to skip to avoid short-term reversal (S)"),
        ParamSpec("top_quantile",    "float", 0.2, lo=0.05, hi=0.5,
                  description="Fraction of universe in long/short legs"),
        ParamSpec("vix_z_threshold", "float", 2.0, lo=1.0,  hi=4.0,
                  description="VIX z-score above which momentum is turned off"),
        ParamSpec("vix_window",      "int",   252, lo=60,  hi=504,
                  description="Rolling window for VIX z-score normalisation"),
    ]

    def compute(
        self,
        data: Dict[str, pd.DataFrame],
    ) -> List[SignalOutput]:
        """
        Parameters
        ----------
        data : Dict[symbol, OHLCV DataFrame]
            All DataFrames must share the same DatetimeIndex.
            The VIX series is expected as data["VIX"] or via
            df.attrs["vix_zscore"] on any member DataFrame.

        Returns
        -------
        One SignalOutput per symbol.  score in [-1, +1] represents
        cross-sectional rank percentile rescaled linearly.
        Empty list if the universe has fewer than 10 assets (ranking is
        meaningless on a small panel) or if VIX filter is active.
        """
        raise NotImplementedError(
            "MomentumCrossSectionalSignal.compute() is not implemented yet. "
            "Implement only after VALIDATION_PROTOCOL §4 PASS."
        )


class PairsMeanReversionSignal(Signal):
    """
    Pairs mean-reversion signal on a cointegrated spread (VALIDATION_PROTOCOL §1, Signal B).

    Math
    ----
    Step 1 — cointegration test (must pass before any trade):
        ADF on log(P_a), ADF on log(P_b) → both I(1).
        OLS: log(P_a) = beta * log(P_b) + alpha + epsilon
        ADF on epsilon (residuals) → stationary.

    Step 2 — spread construction:
        spread(t) = log(P_a(t)) - beta_hat * log(P_b(t))
        beta_hat estimated on a rolling IS window (never full-sample, to
        avoid look-ahead bias documented in VALIDATION_PROTOCOL §6 rule 1).

    Step 3 — z-score with rolling mean/std:
        z(t) = (spread(t) - mu_rolling(t)) / sigma_rolling(t)

    Step 4 — half-life check:
        tau = -log(2) / log(rho_AR1_of_spread)
        If tau > max_half_life_bars: return [] (pair too slow, not tradeable).

    Scope: PAIR — compute() receives (sym_a, df_a, sym_b, df_b).
    Returns two SignalOutput objects, one per leg.
    """

    signal_id       = "pairs_mean_reversion"
    label           = "Pairs Mean Reversion"
    scope           = SignalScope.PAIR
    category        = SignalCategory.MEAN_REVERSION
    default_weight  = 1.0
    default_enabled = False   # disabled until VALIDATION_PROTOCOL §4 is passed

    param_specs = [
        ParamSpec("z_entry",           "float", 2.0,  lo=1.0, hi=4.0,
                  description="|z-score| threshold to open a position"),
        ParamSpec("z_exit",            "float", 0.5,  lo=0.0, hi=2.0,
                  description="|z-score| threshold to close (mean reversion)"),
        ParamSpec("z_stop",            "float", 3.5,  lo=2.0, hi=6.0,
                  description="|z-score| at which the trade is stopped out"),
        ParamSpec("coint_window",      "int",   252,  lo=60,  hi=756,
                  description="Rolling bars for beta_hat estimation (IS window)"),
        ParamSpec("zscore_window",     "int",   60,   lo=20,  hi=252,
                  description="Rolling bars for z-score mean and std"),
        ParamSpec("max_half_life_bars","int",   30,   lo=5,   hi=120,
                  description="Maximum acceptable mean-reversion half-life in bars"),
        ParamSpec("adf_pvalue_thresh", "float", 0.05, lo=0.01, hi=0.10,
                  description="Max p-value for ADF residual stationarity test"),
    ]

    def compute(
        self,
        data: Tuple[str, pd.DataFrame, str, pd.DataFrame],
    ) -> List[SignalOutput]:
        """
        Parameters
        ----------
        data : (sym_a, df_a, sym_b, df_b)
            Both DataFrames must be aligned to the same DatetimeIndex.
            Must contain at least a 'close' column.

        Returns
        -------
        Two SignalOutput objects:
          - leg_a: score in [-1, +1], direction long/short/flat.
          - leg_b: score = -leg_a.score (opposite leg of the spread).
        metadata keys: z_score, beta_hat, half_life_bars, adf_pvalue,
                       spread_mean, spread_std.
        Empty list if cointegration test fails or half-life is too large.
        """
        raise NotImplementedError(
            "PairsMeanReversionSignal.compute() is not implemented yet. "
            "Implement only after VALIDATION_PROTOCOL §4 PASS."
        )
