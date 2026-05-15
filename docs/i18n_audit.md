# i18n Audit — Fase 1.6.1

> Report di audit prodotto da Marco il 2026-05-15.
> Input per Fase 1.6.2 (Paky crea `gui/i18n/`) e Fase 1.6.3 (Marco sostituisce stringhe con `tr()`).
> Riferimento normativo: `docs/SPRINT.md` sezioni 1.6.1 → 1.6.5.

## Conteggio finale

- File `.py` scansionati: 27
- File con stringhe UI rilevanti: 12
- Stringhe totali da gestire con `tr()`: ~87 occorrenze
- Chiavi già in tabella SPRINT.md: 50
- NUOVE chiavi da aggiungere: 68
- File `.ui` NON scansionati: 7 in `gui/ui/` (richiedono audit XML separato — Paky in 1.6.2)

## Discrepanze risolte (decisione Max 2026-05-15)

| Chiave | Versione scelta | Motivazione |
|--------|----------------|-------------|
| `dashboard.no_positions` | "Nessuna posizione aperta. Il motore sta scansionando i mercati..." | Versione tabella SPRINT.md (più formale, "motore" > "engine" in IT) |
| `dashboard.chart_subtitle` | "Il grafico a candele verrà integrato qui" | Versione tabella SPRINT.md (no "CandlestickChart" tecnico) |
| `positions.header.entry` | "ENTRATA → CORRENTE" | Versione tabella SPRINT.md (più coerente con "POSIZIONI APERTE") |
| `topbar.win_rate` | Una sola chiave `topbar.win_rate` → label "WIN" | Rinominare il badge usando la chiave tabella, NON aggiungere `topbar.win` |
| `help.f1.body` | Versione tabella SPRINT.md (F1+Ctrl+K+F11) | Aggiornare `main_window.py` con testo tabella |

## File coinvolti

### gui/main_window.py
- `app.title`, `help.f1.title`, `help.f1.body`, `help.search.title`, `help.search.body` (tutte in tabella)
- NUOVA: `status.ready_workspace` = "Pronto · Spazio di lavoro: {workspace}"

### gui/widgets/top_bar.py
- Chiavi in tabella: `topbar.equity`, `topbar.start`, `topbar.stop`, `topbar.pnl_day`, `topbar.positions`, `topbar.win_rate`, `tooltip.equity`, `tooltip.pnl_day`, `tooltip.positions`, `tooltip.win_rate`, `tooltip.mode`, `tooltip.broker`, `tooltip.clock`
- NUOVE: `topbar.engine_start_tip`, `topbar.engine_stop_tip`, `help.shortcuts.title`, `help.shortcuts.body`, `broker.pill_connected` = "• {ms}ms", `broker.pill_disconnected` = "• ---"

### gui/workspaces/dashboard.py
- Chiavi in tabella: `dashboard.watchlist`, `dashboard.positions_open`, `dashboard.no_positions`, `dashboard.chart_placeholder`, `dashboard.chart_subtitle`, `dashboard.confidence`, `dashboard.ai_prediction`, `dashboard.history`, `dashboard.strategy_label`, `dashboard.last_signal`, `gauge.hurst`, `gauge.kelly`, `gauge.volatility`, `positions.header.*`, `help.hurst.body`, `help.kelly.body`, `help.volatility.body`, `help.confidence.body`
- NUOVE: `watchlist.row_tooltip` = "Clicca per selezionare {symbol}"

### gui/panels/broker_panel.py (panel più denso — 28 nuove chiavi)
- `broker.settings_title`, `broker.status_label`, `broker.paper_status`, `broker.active_label`, `broker.btn_save`, `broker.btn_test`, `broker.paper_info`, `broker.ig_title`, `broker.ig_note`, `broker.oanda_title`, `broker.oanda_note`, `broker.alpaca_title`, `broker.alpaca_mode_paper`, `broker.ccxt_title`, `broker.ccxt_mode_sandbox`, `broker.field.environment`, `broker.field.mode`, `broker.field.account_type`, `broker.disconnected_status`, `broker.save_ok`, `broker.save_error`, `broker.load_error`, `broker.paper_no_connect`, `broker.test_in_progress`, `broker.connected_status`, `broker.test_ok`, `broker.error_status`, `broker.test_fail`, `broker.test_error`

### gui/panels/engine_panel.py
- `engine.status_active`, `engine.btn_stop`, `engine.status_stopped`, `engine.btn_start`, `engine.signals_count`

### gui/panels/backtest_panel.py
- `backtest.metric.return`, `backtest.metric.ann_return`, `backtest.metric.n_trades`, `backtest.metric.final_capital`, `backtest.metric.bars_per_trade`, `backtest.axis.capital`, `backtest.axis.bars`, `backtest.pyqtgraph_missing`, `backtest.status.downloading`, `backtest.status.running`, `backtest.status.done`, `backtest.status.error`, `backtest.export_dialog_title`

### gui/panels/ai_analysis_panel.py
- `ai.empty_state`, `ai.btn_run`, `ai.analysis_error`, `ai.hurst_bias.trending`, `ai.hurst_bias.reverting`, `ai.hurst_bias.random`, `ai.fund_support.yes`, `ai.fund_support.negative`, `ai.fund_support.neutral`

### gui/panels/chart_panel.py
- `chart.empty_state`

### gui/panels/positions_panel.py
- `positions.btn_close`

### gui/panels/data_panel.py
- `data.error.no_symbol`, `data.btn_stop_live`, `data.btn_start_live`, `data.status.live_stopped`

### gui/panels/watchlist_panel.py
- `watchlist.status.updating`, `watchlist.status.updated`, `watchlist.status.error`

### gui/widgets/info/regime_pill.py
- `regime.tooltip.trending`, `regime.tooltip.choppy`, `regime.tooltip.cycling`, `regime.tooltip.unknown`

### gui/panels/pattern_panel.py
- `pattern.col.direction`, `pattern.col.age_min`

## Mapping NUOVE chiavi (IT default + EN)

| Chiave | Italiano | English |
|--------|----------|---------|
| `status.ready_workspace` | Pronto · Spazio di lavoro: {workspace} | Ready · Workspace: {workspace} |
| `broker.pill_connected` | • {ms}ms | • {ms}ms |
| `broker.pill_disconnected` | • --- | • --- |
| `topbar.engine_start_tip` | Avvia il motore di trading automatico | Start the trading engine |
| `topbar.engine_stop_tip` | Ferma il motore di trading automatico | Stop the trading engine |
| `help.shortcuts.title` | Shortcut tastiera | Keyboard shortcuts |
| `help.shortcuts.body` | F1 = Aiuto contestuale\nCtrl+K = Ricerca comandi\nF11 = Schermo intero\nCtrl+R = Avvia/Ferma motore\nCtrl+W = Chiudi tab corrente\nCtrl+1..9 = Cambia workspace | F1 = Contextual help\nCtrl+K = Search commands\nF11 = Fullscreen\nCtrl+R = Start/Stop engine\nCtrl+W = Close current tab\nCtrl+1..9 = Switch workspace |
| `watchlist.row_tooltip` | Clicca per selezionare {symbol} | Click to select {symbol} |
| `broker.settings_title` | Impostazioni Broker | Broker Settings |
| `broker.status_label` | Stato: | Status: |
| `broker.paper_status` | ● Paper — SIMULAZIONE | ● Paper — SIMULATION |
| `broker.active_label` | Broker attivo: | Active broker: |
| `broker.btn_save` | Salva impostazioni | Save settings |
| `broker.btn_test` | Testa connessione | Test connection |
| `broker.paper_info` | Nessuna credenziale richiesta.\nIn modalità Paper gli ordini sono simulati senza soldi reali. | No credentials required.\nIn Paper mode orders are simulated with no real money. |
| `broker.ig_title` | IG Markets — CFD (forex, indici, oro) | IG Markets — CFD (forex, indices, gold) |
| `broker.ig_note` | Conto demo gratuito: ig.com/it → Conto Demo\nAPI key: labs.ig.com → My Applications | Free demo account: ig.com → Demo Account\nAPI key: labs.ig.com → My Applications |
| `broker.oanda_title` | OANDA — Forex + XAU/USD | OANDA — Forex + XAU/USD |
| `broker.oanda_note` | Conto practice gratuito: oanda.com\nToken: MyAccount → Manage API Access | Free practice account: oanda.com\nToken: MyAccount → Manage API Access |
| `broker.alpaca_title` | Alpaca — Azioni USA | Alpaca — US Stocks |
| `broker.alpaca_mode_paper` | Paper (simulato) | Paper (simulated) |
| `broker.ccxt_title` | CCXT — Crypto Exchanges | CCXT — Crypto Exchanges |
| `broker.ccxt_mode_sandbox` | Sandbox (simulato) | Sandbox (simulated) |
| `broker.field.environment` | Ambiente: | Environment: |
| `broker.field.mode` | Modalità: | Mode: |
| `broker.field.account_type` | Account type: | Account type: |
| `broker.disconnected_status` | ○ {broker} — non connesso | ○ {broker} — not connected |
| `broker.save_ok` | Impostazioni salvate in .env. Riavvia l'app per applicarle. | Settings saved to .env. Restart the app to apply. |
| `broker.save_error` | Errore salvataggio: {error} | Save error: {error} |
| `broker.load_error` | Errore caricamento impostazioni: {error} | Error loading settings: {error} |
| `broker.paper_no_connect` | Paper broker: nessuna connessione necessaria. | Paper broker: no connection needed. |
| `broker.test_in_progress` | Test connessione in corso... | Testing connection... |
| `broker.connected_status` | ● {broker} — CONNESSO | ● {broker} — CONNECTED |
| `broker.test_ok` | Connessione riuscita: {msg} | Connection successful: {msg} |
| `broker.error_status` | ○ {broker} — ERRORE | ○ {broker} — ERROR |
| `broker.test_fail` | Connessione fallita: {msg} | Connection failed: {msg} |
| `broker.test_error` | Errore test: {error} | Test error: {error} |
| `engine.status_active` | ● ATTIVO | ● ACTIVE |
| `engine.btn_stop` | ■  Ferma Engine | ■  Stop Engine |
| `engine.status_stopped` | ⏸ FERMO | ⏸ STOPPED |
| `engine.btn_start` | ▶  Avvia Engine | ▶  Start Engine |
| `engine.signals_count` | {n} segnali: | {n} signals: |
| `backtest.metric.return` | Rendimento | Return |
| `backtest.metric.ann_return` | Rendim. Ann. | Ann. Return |
| `backtest.metric.n_trades` | N. Trade | Trades |
| `backtest.metric.final_capital` | Capitale Fin. | Final Capital |
| `backtest.metric.bars_per_trade` | Barre/Trade | Bars/Trade |
| `backtest.axis.capital` | Capitale (€) | Capital (€) |
| `backtest.axis.bars` | Barre | Bars |
| `backtest.pyqtgraph_missing` | pyqtgraph non installato\n(pip install pyqtgraph) | pyqtgraph not installed\n(pip install pyqtgraph) |
| `backtest.status.downloading` | Download {symbol} [{tf}] · {days} giorni... | Downloading {symbol} [{tf}] · {days} days... |
| `backtest.status.running` | Simulazione in corso... {pct}% | Simulation running... {pct}% |
| `backtest.status.done` | Completato · {trades} trade · {return_pct}% | Done · {trades} trades · {return_pct}% |
| `backtest.status.error` | Errore: {msg} | Error: {msg} |
| `backtest.export_dialog_title` | Esporta Trade Log | Export Trade Log |
| `ai.empty_state` | Carica un simbolo e clicca\n"Avvia Analisi AI" | Load a symbol and click\n"Run AI Analysis" |
| `ai.btn_run` | Avvia Analisi AI  [{symbol}] | Run AI Analysis  [{symbol}] |
| `ai.analysis_error` | Errore analisi:\n{error} | Analysis error:\n{error} |
| `ai.hurst_bias.trending` | In trend | Trending |
| `ai.hurst_bias.reverting` | Mean-reverting | Reverting |
| `ai.hurst_bias.random` | Casuale | Random |
| `ai.fund_support.yes` | Sì | Yes |
| `ai.fund_support.negative` | Negativo | Negative |
| `ai.fund_support.neutral` | Neutro | Neutral |
| `chart.empty_state` | Seleziona un simbolo e clicca\n"Carica Dati Storici" | Select a symbol and click\n"Load Historical Data" |
| `positions.btn_close` | Chiudi | Close |
| `data.error.no_symbol` | Inserisci prima un simbolo. | Enter a symbol first. |
| `data.btn_stop_live` | Ferma Feed Live | Stop Live Feed |
| `data.btn_start_live` | Avvia Feed Live | Start Live Feed |
| `data.status.live_stopped` | Feed live fermato. | Live feed stopped. |
| `watchlist.status.updating` | Aggiornamento in corso… | Updating… |
| `watchlist.status.updated` | Aggiornato — {n} simboli | Updated — {n} symbols |
| `watchlist.status.error` | Errore: {error} | Error: {error} |
| `regime.tooltip.trending` | Mercato direzionale. Hurst > 0.6: momentum persistente. | Directional market. Hurst > 0.6: persistent momentum. |
| `regime.tooltip.choppy` | Mercato laterale rumoroso. Hurst ~0.5: random walk. | Noisy sideways market. Hurst ~0.5: random walk. |
| `regime.tooltip.cycling` | Mercato ciclico mean-reverting. Hurst < 0.4: anti-persistente. | Mean-reverting cyclic market. Hurst < 0.4: anti-persistent. |
| `regime.tooltip.unknown` | Regime non determinato. Dati insufficienti. | Regime undetermined. Insufficient data. |
| `pattern.col.direction` | Direzione | Direction |
| `pattern.col.age_min` | Da (min) | Age (min) |

## Per Paky (Fase 1.6.2)

- Audit `.ui` files separato necessario (engine_panel, backtest_panel, ai_analysis_panel, positions_panel, watchlist_panel, pattern_panel, data_panel). Strategia: rendere i `.ui` testi vuoti e popolare via `tr()` in `__init__` del panel.
- `broker_panel.py` ha 28 nuove chiavi (più denso) — eventuale split `gui/i18n/broker.py` se dict principale supera 200 entries.
- 50 chiavi tabella + 68 nuove = 118 chiavi totali. Dict gestibile come singolo file `gui/i18n/strings.py`.
