"""
[Paky] gui/i18n/strings.py — Dizionari IT/EN con 118 chiavi

Generato in Fase 1.6.2 (2026-05-15).
Sorgenti:
  - 50 chiavi base da docs/SPRINT.md sezione 1.6.2
  - 68 chiavi nuove da docs/i18n_audit.md sezione "Mapping NUOVE chiavi"
  - 5 discrepanze risolte con la versione tabella SPRINT.md (decisione Max 2026-05-15)

Termini tecnici invariati (non tradurre): AI, ML, LSTM, RNN, RSI, MACD, ATR,
FFT, VWAP, OHLC, P&L, TP, SL, BID, ASK, UTC, API, CFD, ETF, EUR, USD, GBP,
JPY, ms, %, Hurst, Kelly, Sharpe, Sortino, Calmar, long, short, trend,
breakout, scalping, swing, watchlist, spread, slippage, drawdown, equity,
ticker, broker, leverage, margin, lot, pip, BUY, SELL, STOP, LIMIT, MARKET,
PAPER, LIVE, DEMO, READY, ERROR, IDLE, RUNNING.
"""

from __future__ import annotations
from typing import Any


# =============================================================================
# Dizionario ITALIANO (default)
# =============================================================================

IT: dict[str, str] = {

    # ---- app ------------------------------------------------------------------
    "app.title":                   "TradingIA — Terminale di Trading",

    # ---- workspace labels -----------------------------------------------------
    "workspace.dashboard":         "Cruscotto",
    "workspace.order":             "Ordini",
    "workspace.order_ticket":      "Ordini",
    "workspace.analysis":          "Analisi",
    "workspace.backtest":          "Backtest",
    "workspace.patterns":          "Pattern",
    "workspace.settings":          "Impostazioni",

    # ---- top bar --------------------------------------------------------------
    "topbar.start":                "▶ AVVIA",
    "topbar.stop":                 "⏸ FERMA",
    "topbar.equity":               "CAPITALE",
    "topbar.pnl_day":              "P&L OGGI",
    "topbar.positions":            "POSIZIONI",
    "topbar.win_rate":             "VITTORIE",
    "topbar.help":                 "Aiuto",
    "topbar.engine_start_tip":     "Avvia il motore di trading automatico",
    "topbar.engine_stop_tip":      "Ferma il motore di trading automatico",

    # ---- regime ---------------------------------------------------------------
    "regime.trending":             "IN TREND",
    "regime.choppy":               "LATERALE",
    "regime.cycling":              "CICLICO",
    "regime.unknown":              "SCONOSCIUTO",

    # ---- regime tooltips ------------------------------------------------------
    "regime.tooltip.trending":     "Mercato direzionale. Hurst > 0.6: momentum persistente.",
    "regime.tooltip.choppy":       "Mercato laterale rumoroso. Hurst ~0.5: random walk.",
    "regime.tooltip.cycling":      "Mercato ciclico mean-reverting. Hurst < 0.4: anti-persistente.",
    "regime.tooltip.unknown":      "Regime non determinato. Dati insufficienti.",

    # ---- dashboard ------------------------------------------------------------
    "dashboard.watchlist":         "LISTA STRUMENTI",
    "dashboard.positions_open":    "POSIZIONI APERTE",
    "dashboard.no_positions":      "Nessuna posizione aperta. Il motore sta scansionando i mercati...",
    "dashboard.chart_placeholder": "AREA GRAFICO",
    "dashboard.chart_subtitle":    "Il grafico a candele verrà integrato qui",
    "dashboard.ai_panel":          "ANALISI AI",
    "dashboard.confidence":        "CONFIDENZA",
    "dashboard.ai_prediction":     "Previsione AI",
    "dashboard.history":           "STORICO (50 PRED.)",
    "dashboard.strategy_label":    "Strategia:",
    "dashboard.last_signal":       "Ultimo segnale: {n}m fa",

    # ---- gauge labels ---------------------------------------------------------
    "gauge.hurst":                 "ESPONENTE DI HURST",
    "gauge.kelly":                 "KELLY %",
    "gauge.volatility":            "VOLATILITÀ",

    # ---- positions headers ----------------------------------------------------
    "positions.header.symbol":     "STRUMENTO",
    "positions.header.dir":        "DIR",
    "positions.header.entry":      "ENTRATA → CORRENTE",
    "positions.header.pnl":        "P&L",

    # ---- positions buttons ----------------------------------------------------
    "positions.btn_close":         "Chiudi",

    # ---- status bar -----------------------------------------------------------
    "status.ready":                "Pronto",
    "status.workspace":            "Spazio di lavoro",
    "status.ready_workspace":      "Pronto · Spazio di lavoro: {workspace}",

    # ---- mode -----------------------------------------------------------------
    "mode.paper":                  "PAPER",
    "mode.live":                   "LIVE",

    # ---- broker ---------------------------------------------------------------
    "broker.connected":            "Connesso · {ms}ms",
    "broker.disconnected":         "Disconnesso",
    "broker.pill_connected":       "• {ms}ms",
    "broker.pill_disconnected":    "• ---",
    "broker.settings_title":       "Impostazioni Broker",
    "broker.status_label":         "Stato:",
    "broker.paper_status":         "● Paper — SIMULAZIONE",
    "broker.active_label":         "Broker attivo:",
    "broker.btn_save":             "Salva impostazioni",
    "broker.btn_test":             "Testa connessione",
    "broker.paper_info":           "Nessuna credenziale richiesta.\nIn modalità Paper gli ordini sono simulati senza soldi reali.",
    "broker.ig_title":             "IG Markets — CFD (forex, indici, oro)",
    "broker.ig_note":              "Conto demo gratuito: ig.com/it → Conto Demo\nAPI key: labs.ig.com → My Applications",
    "broker.oanda_title":          "OANDA — Forex + XAU/USD",
    "broker.oanda_note":           "Conto practice gratuito: oanda.com\nToken: MyAccount → Manage API Access",
    "broker.alpaca_title":         "Alpaca — Azioni USA",
    "broker.alpaca_mode_paper":    "Paper (simulato)",
    "broker.ccxt_title":           "CCXT — Crypto Exchanges",
    "broker.ccxt_mode_sandbox":    "Sandbox (simulato)",
    "broker.field.environment":    "Ambiente:",
    "broker.field.mode":           "Modalità:",
    "broker.field.account_type":   "Account type:",
    "broker.disconnected_status":  "○ {broker} — non connesso",
    "broker.save_ok":              "Impostazioni salvate in .env. Riavvia l'app per applicarle.",
    "broker.save_error":           "Errore salvataggio: {error}",
    "broker.load_error":           "Errore caricamento impostazioni: {error}",
    "broker.paper_no_connect":     "Paper broker: nessuna connessione necessaria.",
    "broker.test_in_progress":     "Test connessione in corso...",
    "broker.connected_status":     "● {broker} — CONNESSO",
    "broker.test_ok":              "Connessione riuscita: {msg}",
    "broker.error_status":         "○ {broker} — ERRORE",
    "broker.test_fail":            "Connessione fallita: {msg}",
    "broker.test_error":           "Errore test: {error}",

    # ---- engine ---------------------------------------------------------------
    "engine.status_active":        "● ATTIVO",
    "engine.btn_stop":             "■  Ferma Engine",
    "engine.status_stopped":       "⏸ FERMO",
    "engine.btn_start":            "▶  Avvia Engine",
    "engine.signals_count":        "{n} segnali:",

    # ---- help dialogs ---------------------------------------------------------
    "help.f1.title":               "TradingIA — Aiuto",
    "help.f1.body":                "F1: questo aiuto · Ctrl+K: cerca · F11: schermo intero. Premi ▶ AVVIA in alto per partire.",
    "help.search.title":           "Cerca comando",
    "help.search.body":            "La palette comandi sarà disponibile nelle prossime versioni.",
    "help.shortcuts.title":        "Shortcut tastiera",
    "help.shortcuts.body":         "F1 = Aiuto contestuale\nCtrl+K = Ricerca comandi\nF11 = Schermo intero\nCtrl+R = Avvia/Ferma motore\nCtrl+W = Chiudi tab corrente\nCtrl+1..9 = Cambia workspace",
    "help.hurst.body":             "Misura la persistenza di un trend. Sotto 0.4 il prezzo tende a tornare alla media (mean-reverting). Vicino a 0.5 è random walk. Sopra 0.6 c'è trend persistente.",
    "help.kelly.body":             "Percentuale ottimale del capitale da rischiare in un singolo trade. Più alta = più aggressivo. Sopra il 5% considerato pericoloso.",
    "help.volatility.body":        "ATR percentile rispetto allo storico 6 mesi. >0.7 = volatilità alta, prudenza. <0.3 = mercato fermo.",
    "help.confidence.body":        "Quanto il modello AI è sicuro della sua previsione. Sopra 0.7 considerato affidabile.",

    # ---- tooltips (KPI badge) -------------------------------------------------
    "tooltip.equity":              "Capitale totale (cash + valore posizioni aperte). La sparkline mostra l'andamento delle ultime 50 osservazioni.",
    "tooltip.pnl_day":             "Profitto/perdita realizzato + non realizzato di oggi. Resettato a mezzanotte UTC.",
    "tooltip.positions":           "Posizioni attualmente aperte / massimo configurato.",
    "tooltip.win_rate":            "Percentuale di trade chiusi in profitto sugli ultimi 30 giorni.",
    "tooltip.mode":                "PAPER = simulato (nessun rischio). LIVE = soldi reali sul conto broker.",
    "tooltip.broker":              "Latency ping al broker. <50ms ottimo, >200ms degradato.",
    "tooltip.clock":               "Ora UTC corrente. I mercati usano UTC come riferimento.",

    # ---- watchlist ------------------------------------------------------------
    "watchlist.row_tooltip":       "Clicca per selezionare {symbol}",
    "watchlist.status.updating":   "Aggiornamento in corso…",
    "watchlist.status.updated":    "Aggiornato — {n} simboli",
    "watchlist.status.error":      "Errore: {error}",

    # ---- backtest -------------------------------------------------------------
    "backtest.metric.return":      "Rendimento",
    "backtest.metric.ann_return":  "Rendim. Ann.",
    "backtest.metric.n_trades":    "N. Trade",
    "backtest.metric.final_capital": "Capitale Fin.",
    "backtest.metric.bars_per_trade": "Barre/Trade",
    "backtest.axis.capital":       "Capitale (€)",
    "backtest.axis.bars":          "Barre",
    "backtest.pyqtgraph_missing":  "pyqtgraph non installato\n(pip install pyqtgraph)",
    "backtest.status.downloading": "Download {symbol} [{tf}] · {days} giorni...",
    "backtest.status.running":     "Simulazione in corso... {pct}%",
    "backtest.status.done":        "Completato · {trades} trade · {return_pct}%",
    "backtest.status.error":       "Errore: {msg}",
    "backtest.export_dialog_title": "Esporta Trade Log",

    # ---- AI analysis panel ----------------------------------------------------
    "ai.empty_state":              "Carica un simbolo e clicca\n\"Avvia Analisi AI\"",
    "ai.btn_run":                  "Avvia Analisi AI  [{symbol}]",
    "ai.analysis_error":           "Errore analisi:\n{error}",
    "ai.hurst_bias.trending":      "In trend",
    "ai.hurst_bias.reverting":     "Mean-reverting",
    "ai.hurst_bias.random":        "Casuale",
    "ai.fund_support.yes":         "Sì",
    "ai.fund_support.negative":    "Negativo",
    "ai.fund_support.neutral":     "Neutro",

    # ---- chart ----------------------------------------------------------------
    "chart.empty_state":           "Seleziona un simbolo e clicca\n\"Carica Dati Storici\"",

    # ---- data panel -----------------------------------------------------------
    "data.error.no_symbol":        "Inserisci prima un simbolo.",
    "data.btn_stop_live":          "Ferma Feed Live",
    "data.btn_start_live":         "Avvia Feed Live",
    "data.status.live_stopped":    "Feed live fermato.",

    # ---- pattern panel --------------------------------------------------------
    "pattern.col.direction":       "Direzione",
    "pattern.col.age_min":         "Da (min)",
    "pattern.title":               "Pattern Attivi",
    "pattern.btn_clear":           "Pulisci",
    "pattern.count_label":         "{n} pattern",

    # ---- order ticket workspace -----------------------------------------------
    "order.group_title":           "Nuovo Ordine",
    "order.field.symbol":          "Strumento",
    "order.field.direction":       "Direzione",
    "order.field.quantity":        "Quantità",
    "order.field.type":            "Tipo",
    "order.field.price":           "Prezzo",
    "order.sl_label":              "Stop Loss",
    "order.tp_label":              "Take Profit",
    "order.btn_submit":            "Invia Ordine",
    "order.risk_capital":          "Capitale a rischio",
    "order.risk_rr":               "R:R atteso",
    "order.risk_kelly":            "Kelly suggerito",
    "order.header.time":           "ORARIO",
    "order.header.symbol":         "STRUMENTO",
    "order.header.direction":      "DIR",
    "order.header.type":           "TIPO",
    "order.header.quantity":       "QTÀ",
    "order.header.price":          "PREZZO",
    "order.header.status":         "STATO",
    "order.header.pnl":            "P&L",
    "order.placeholder.symbol":    "es. AAPL, EURUSD=X, BTC-USD",
    "workspace.subtitle.order_ticket": "Crea e gestisci ordini",

    # ---- workspace subtitles (altri workspace) --------------------------------
    "workspace.subtitle.dashboard":    "Panoramica live di mercato e posizioni",
    "workspace.subtitle.analysis":     "Analisi AI, grafico e dati fondamentali",
    "workspace.subtitle.backtest":     "Simulazione storica strategie",
    "workspace.subtitle.patterns":     "Riconoscimento pattern grafici",
    "workspace.subtitle.settings":     "Configura preferenze, broker e parametri di rischio",

    # ---- settings — sezioni ---------------------------------------------------
    "settings.section.general":        "Generale",
    "settings.section.broker":         "Broker",
    "settings.section.risk":           "Rischio",
    "settings.section.info":           "Informazioni",

    # ---- settings — lingua ----------------------------------------------------
    "settings.lang_label":             "Lingua interfaccia",
    "settings.lang_restart_title":     "Riavvio richiesto",
    "settings.lang_restart_body":      "La lingua sarà completamente applicata al prossimo avvio dell'applicazione.",

    # ---- settings — tema -------------------------------------------------------
    "settings.theme_label":            "Tema",
    "settings.theme_dark":             "Scuro (default)",
    "settings.theme_light_soon":       "Chiaro (presto)",

    # ---- settings — broker -----------------------------------------------------
    "settings.btn_open_broker":        "Apri impostazioni broker",
    "settings.broker_dialog_title":    "Impostazioni Broker",

    # ---- settings — rischio ----------------------------------------------------
    "settings.risk.initial_capital":   "Capitale iniziale",
    "settings.risk.per_trade_pct":     "Rischio per trade",
    "settings.risk.max_drawdown":      "Drawdown massimo",
    "settings.btn_save_env":           "Salva su .env",
    "settings.env_saved":              "Impostazioni salvate in {path}. Riavvia l'app per applicarle.",
    "settings.env_error":              "Errore salvataggio: {error}",

    # ---- settings — info -------------------------------------------------------
    "settings.info.version":           "Versione app",
    "settings.info.python":            "Python",
    "settings.info.pyqt":              "PyQt6",
    "settings.info.env_path":          "Percorso .env",
    "settings.info.db_path":           "Percorso DB",
}


# =============================================================================
# Dizionario ENGLISH
# =============================================================================

EN: dict[str, str] = {

    # ---- app ------------------------------------------------------------------
    "app.title":                   "TradingIA — Trading Terminal",

    # ---- workspace labels -----------------------------------------------------
    "workspace.dashboard":         "Dashboard",
    "workspace.order":             "Order Ticket",
    "workspace.order_ticket":      "Order Ticket",
    "workspace.analysis":          "Analysis",
    "workspace.backtest":          "Backtest",
    "workspace.patterns":          "Patterns",
    "workspace.settings":          "Settings",

    # ---- top bar --------------------------------------------------------------
    "topbar.start":                "▶ START",
    "topbar.stop":                 "⏸ STOP",
    "topbar.equity":               "EQUITY",
    "topbar.pnl_day":              "P&L DAY",
    "topbar.positions":            "POS",
    "topbar.win_rate":             "WIN",
    "topbar.help":                 "Help",
    "topbar.engine_start_tip":     "Start the trading engine",
    "topbar.engine_stop_tip":      "Stop the trading engine",

    # ---- regime ---------------------------------------------------------------
    "regime.trending":             "TRENDING",
    "regime.choppy":               "CHOPPY",
    "regime.cycling":              "CYCLING",
    "regime.unknown":              "UNKNOWN",

    # ---- regime tooltips ------------------------------------------------------
    "regime.tooltip.trending":     "Directional market. Hurst > 0.6: persistent momentum.",
    "regime.tooltip.choppy":       "Noisy sideways market. Hurst ~0.5: random walk.",
    "regime.tooltip.cycling":      "Mean-reverting cyclic market. Hurst < 0.4: anti-persistent.",
    "regime.tooltip.unknown":      "Regime undetermined. Insufficient data.",

    # ---- dashboard ------------------------------------------------------------
    "dashboard.watchlist":         "WATCHLIST",
    "dashboard.positions_open":    "OPEN POSITIONS",
    "dashboard.no_positions":      "No open positions. The engine is scanning markets...",
    "dashboard.chart_placeholder": "CHART AREA",
    "dashboard.chart_subtitle":    "Candlestick chart will be integrated here",
    "dashboard.ai_panel":          "AI ANALYSIS",
    "dashboard.confidence":        "CONFIDENCE",
    "dashboard.ai_prediction":     "AI Prediction",
    "dashboard.history":           "HISTORY (50 PRED.)",
    "dashboard.strategy_label":    "Strategy:",
    "dashboard.last_signal":       "Last signal: {n}m ago",

    # ---- gauge labels ---------------------------------------------------------
    "gauge.hurst":                 "HURST EXPONENT",
    "gauge.kelly":                 "KELLY %",
    "gauge.volatility":            "VOLATILITY",

    # ---- positions headers ----------------------------------------------------
    "positions.header.symbol":     "SYMBOL",
    "positions.header.dir":        "DIR",
    "positions.header.entry":      "ENTRY → CURRENT",
    "positions.header.pnl":        "P&L",

    # ---- positions buttons ----------------------------------------------------
    "positions.btn_close":         "Close",

    # ---- status bar -----------------------------------------------------------
    "status.ready":                "Ready",
    "status.workspace":            "Workspace",
    "status.ready_workspace":      "Ready · Workspace: {workspace}",

    # ---- mode -----------------------------------------------------------------
    "mode.paper":                  "PAPER",
    "mode.live":                   "LIVE",

    # ---- broker ---------------------------------------------------------------
    "broker.connected":            "Connected · {ms}ms",
    "broker.disconnected":         "Disconnected",
    "broker.pill_connected":       "• {ms}ms",
    "broker.pill_disconnected":    "• ---",
    "broker.settings_title":       "Broker Settings",
    "broker.status_label":         "Status:",
    "broker.paper_status":         "● Paper — SIMULATION",
    "broker.active_label":         "Active broker:",
    "broker.btn_save":             "Save settings",
    "broker.btn_test":             "Test connection",
    "broker.paper_info":           "No credentials required.\nIn Paper mode orders are simulated with no real money.",
    "broker.ig_title":             "IG Markets — CFD (forex, indices, gold)",
    "broker.ig_note":              "Free demo account: ig.com → Demo Account\nAPI key: labs.ig.com → My Applications",
    "broker.oanda_title":          "OANDA — Forex + XAU/USD",
    "broker.oanda_note":           "Free practice account: oanda.com\nToken: MyAccount → Manage API Access",
    "broker.alpaca_title":         "Alpaca — US Stocks",
    "broker.alpaca_mode_paper":    "Paper (simulated)",
    "broker.ccxt_title":           "CCXT — Crypto Exchanges",
    "broker.ccxt_mode_sandbox":    "Sandbox (simulated)",
    "broker.field.environment":    "Environment:",
    "broker.field.mode":           "Mode:",
    "broker.field.account_type":   "Account type:",
    "broker.disconnected_status":  "○ {broker} — not connected",
    "broker.save_ok":              "Settings saved to .env. Restart the app to apply.",
    "broker.save_error":           "Save error: {error}",
    "broker.load_error":           "Error loading settings: {error}",
    "broker.paper_no_connect":     "Paper broker: no connection needed.",
    "broker.test_in_progress":     "Testing connection...",
    "broker.connected_status":     "● {broker} — CONNECTED",
    "broker.test_ok":              "Connection successful: {msg}",
    "broker.error_status":         "○ {broker} — ERROR",
    "broker.test_fail":            "Connection failed: {msg}",
    "broker.test_error":           "Test error: {error}",

    # ---- engine ---------------------------------------------------------------
    "engine.status_active":        "● ACTIVE",
    "engine.btn_stop":             "■  Stop Engine",
    "engine.status_stopped":       "⏸ STOPPED",
    "engine.btn_start":            "▶  Start Engine",
    "engine.signals_count":        "{n} signals:",

    # ---- help dialogs ---------------------------------------------------------
    "help.f1.title":               "TradingIA — Help",
    "help.f1.body":                "F1: this help · Ctrl+K: search · F11: fullscreen. Press ▶ START at the top to begin.",
    "help.search.title":           "Command palette",
    "help.search.body":            "Command palette will be available in upcoming versions.",
    "help.shortcuts.title":        "Keyboard shortcuts",
    "help.shortcuts.body":         "F1 = Contextual help\nCtrl+K = Search commands\nF11 = Fullscreen\nCtrl+R = Start/Stop engine\nCtrl+W = Close current tab\nCtrl+1..9 = Switch workspace",
    "help.hurst.body":             "Measures the persistence of a trend. Below 0.4 the price tends to revert to the mean (mean-reverting). Near 0.5 it is a random walk. Above 0.6 there is persistent trend.",
    "help.kelly.body":             "Optimal percentage of capital to risk in a single trade. Higher = more aggressive. Above 5% considered dangerous.",
    "help.volatility.body":        "ATR percentile versus 6-month history. >0.7 = high volatility, caution. <0.3 = quiet market.",
    "help.confidence.body":        "How confident the AI model is in its prediction. Above 0.7 considered reliable.",

    # ---- tooltips (KPI badge) -------------------------------------------------
    "tooltip.equity":              "Total capital (cash + value of open positions). The sparkline shows the last 50 observations.",
    "tooltip.pnl_day":             "Realized + unrealized profit/loss for today. Reset at midnight UTC.",
    "tooltip.positions":           "Currently open positions / configured maximum.",
    "tooltip.win_rate":            "Percentage of trades closed at a profit over the last 30 days.",
    "tooltip.mode":                "PAPER = simulated (no risk). LIVE = real money on the broker account.",
    "tooltip.broker":              "Latency ping to the broker. <50ms excellent, >200ms degraded.",
    "tooltip.clock":               "Current UTC time. Markets use UTC as reference.",

    # ---- watchlist ------------------------------------------------------------
    "watchlist.row_tooltip":       "Click to select {symbol}",
    "watchlist.status.updating":   "Updating…",
    "watchlist.status.updated":    "Updated — {n} symbols",
    "watchlist.status.error":      "Error: {error}",

    # ---- backtest -------------------------------------------------------------
    "backtest.metric.return":      "Return",
    "backtest.metric.ann_return":  "Ann. Return",
    "backtest.metric.n_trades":    "Trades",
    "backtest.metric.final_capital": "Final Capital",
    "backtest.metric.bars_per_trade": "Bars/Trade",
    "backtest.axis.capital":       "Capital (€)",
    "backtest.axis.bars":          "Bars",
    "backtest.pyqtgraph_missing":  "pyqtgraph not installed\n(pip install pyqtgraph)",
    "backtest.status.downloading": "Downloading {symbol} [{tf}] · {days} days...",
    "backtest.status.running":     "Simulation running... {pct}%",
    "backtest.status.done":        "Done · {trades} trades · {return_pct}%",
    "backtest.status.error":       "Error: {msg}",
    "backtest.export_dialog_title": "Export Trade Log",

    # ---- AI analysis panel ----------------------------------------------------
    "ai.empty_state":              "Load a symbol and click\n\"Run AI Analysis\"",
    "ai.btn_run":                  "Run AI Analysis  [{symbol}]",
    "ai.analysis_error":           "Analysis error:\n{error}",
    "ai.hurst_bias.trending":      "Trending",
    "ai.hurst_bias.reverting":     "Reverting",
    "ai.hurst_bias.random":        "Random",
    "ai.fund_support.yes":         "Yes",
    "ai.fund_support.negative":    "Negative",
    "ai.fund_support.neutral":     "Neutral",

    # ---- chart ----------------------------------------------------------------
    "chart.empty_state":           "Select a symbol and click\n\"Load Historical Data\"",

    # ---- data panel -----------------------------------------------------------
    "data.error.no_symbol":        "Enter a symbol first.",
    "data.btn_stop_live":          "Stop Live Feed",
    "data.btn_start_live":         "Start Live Feed",
    "data.status.live_stopped":    "Live feed stopped.",

    # ---- pattern panel --------------------------------------------------------
    "pattern.col.direction":       "Direction",
    "pattern.col.age_min":         "Age (min)",
    "pattern.title":               "Active Patterns",
    "pattern.btn_clear":           "Clear",
    "pattern.count_label":         "{n} patterns",

    # ---- order ticket workspace -----------------------------------------------
    "order.group_title":           "New Order",
    "order.field.symbol":          "Symbol",
    "order.field.direction":       "Direction",
    "order.field.quantity":        "Quantity",
    "order.field.type":            "Type",
    "order.field.price":           "Price",
    "order.sl_label":              "Stop Loss",
    "order.tp_label":              "Take Profit",
    "order.btn_submit":            "Submit Order",
    "order.risk_capital":          "Risk capital",
    "order.risk_rr":               "Expected R:R",
    "order.risk_kelly":            "Suggested Kelly",
    "order.header.time":           "TIME",
    "order.header.symbol":         "SYMBOL",
    "order.header.direction":      "DIR",
    "order.header.type":           "TYPE",
    "order.header.quantity":       "QTY",
    "order.header.price":          "PRICE",
    "order.header.status":         "STATUS",
    "order.header.pnl":            "P&L",
    "order.placeholder.symbol":    "e.g. AAPL, EURUSD=X, BTC-USD",
    "workspace.subtitle.order_ticket": "Create and manage orders",

    # ---- workspace subtitles (altri workspace) --------------------------------
    "workspace.subtitle.dashboard":    "Live market and positions overview",
    "workspace.subtitle.analysis":     "AI analysis, chart and fundamental data",
    "workspace.subtitle.backtest":     "Historical strategy simulation",
    "workspace.subtitle.patterns":     "Chart pattern recognition",
    "workspace.subtitle.settings":     "Configure preferences, broker and risk parameters",

    # ---- settings — sezioni ---------------------------------------------------
    "settings.section.general":        "General",
    "settings.section.broker":         "Broker",
    "settings.section.risk":           "Risk",
    "settings.section.info":           "Information",

    # ---- settings — lingua ----------------------------------------------------
    "settings.lang_label":             "Interface language",
    "settings.lang_restart_title":     "Restart required",
    "settings.lang_restart_body":      "The language will be fully applied on the next application start.",

    # ---- settings — tema -------------------------------------------------------
    "settings.theme_label":            "Theme",
    "settings.theme_dark":             "Dark (default)",
    "settings.theme_light_soon":       "Light (soon)",

    # ---- settings — broker -----------------------------------------------------
    "settings.btn_open_broker":        "Open broker settings",
    "settings.broker_dialog_title":    "Broker Settings",

    # ---- settings — rischio ----------------------------------------------------
    "settings.risk.initial_capital":   "Initial capital",
    "settings.risk.per_trade_pct":     "Risk per trade",
    "settings.risk.max_drawdown":      "Max drawdown",
    "settings.btn_save_env":           "Save to .env",
    "settings.env_saved":              "Settings saved to {path}. Restart the app to apply.",
    "settings.env_error":              "Save error: {error}",

    # ---- settings — info -------------------------------------------------------
    "settings.info.version":           "App version",
    "settings.info.python":            "Python",
    "settings.info.pyqt":              "PyQt6",
    "settings.info.env_path":          ".env path",
    "settings.info.db_path":           "DB path",
}


# =============================================================================
# Stato corrente e API pubblica
# =============================================================================

_current_dict: dict[str, str] = IT
_current_code: str = "it"


def set_language(code: str) -> None:
    """Imposta la lingua corrente. code: 'it' | 'en'"""
    global _current_dict, _current_code
    _current_code = "it" if code == "it" else "en"
    _current_dict = IT if _current_code == "it" else EN


def current_language() -> str:
    """Ritorna il codice lingua corrente: 'it' o 'en'."""
    return _current_code


def tr(key: str, **kwargs: Any) -> str:
    """
    Traduzione con interpolazione. Fallback alla chiave se manca.

    Esempi:
        tr("topbar.equity")               -> "CAPITALE"  (IT)
        tr("broker.connected", ms=23)     -> "Connesso · 23ms"
        tr("missing.key")                 -> "missing.key"
        tr("broker.connected")            -> "Connesso · {ms}ms"  (no crash)
    """
    s = _current_dict.get(key, key)
    if kwargs:
        try:
            s = s.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return s
