"""
BrokerPanel — Configurazione e stato del broker di trading

Permette di selezionare il broker attivo e inserire le credenziali.
Le impostazioni vengono salvate nel file .env del progetto.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Dict, Optional

from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QLineEdit, QGroupBox, QFormLayout, QFrame,
    QScrollArea, QStackedWidget, QSizePolicy,
)

_ENV_PATH = Path(__file__).parent.parent.parent / ".env"

_STYLE_TITLE  = "color:#e6edf3; font-size:13px; font-weight:bold;"
_STYLE_GRAY   = "color:#8b949e; font-size:11px;"
_STYLE_GREEN  = "color:#3fb950; font-weight:bold;"
_STYLE_RED    = "color:#f85149; font-weight:bold;"
_STYLE_YELLOW = "color:#e3b341; font-weight:bold;"

_STYLE_INPUT = (
    "background:#0d1117; color:#e6edf3; border:1px solid #30363d; "
    "border-radius:4px; padding:4px 6px; font-size:11px;"
)
_STYLE_COMBO = (
    "QComboBox { background:#0d1117; color:#e6edf3; border:1px solid #30363d; "
    "border-radius:4px; padding:4px 6px; font-size:11px; } "
    "QComboBox::drop-down { border:none; } "
    "QComboBox QAbstractItemView { background:#161b22; color:#e6edf3; "
    "selection-background-color:#21262d; border:1px solid #30363d; }"
)
_STYLE_BTN_SAVE = (
    "QPushButton { background:#238636; color:white; border-radius:6px; "
    "font-weight:bold; font-size:12px; padding:6px 12px; } "
    "QPushButton:hover { background:#2ea043; } "
    "QPushButton:pressed { background:#1a7f37; }"
)
_STYLE_BTN_TEST = (
    "QPushButton { background:#21262d; color:#e6edf3; border:1px solid #30363d; "
    "border-radius:6px; font-size:12px; padding:6px 12px; } "
    "QPushButton:hover { background:#30363d; }"
)
_STYLE_GROUP = (
    "QGroupBox { color:#8b949e; font-size:11px; border:1px solid #30363d; "
    "border-radius:4px; margin-top:6px; padding-top:6px; background:#0d1117; } "
    "QGroupBox::title { subcontrol-origin:margin; left:8px; color:#58a6ff; }"
)


def _sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet("border:1px solid #21262d;")
    return f


class _PasswordField(QWidget):
    """Campo password con toggle show/hide."""

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self._edit = QLineEdit()
        self._edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._edit.setStyleSheet(_STYLE_INPUT)
        self._btn = QPushButton("👁")
        self._btn.setFixedWidth(28)
        self._btn.setCheckable(True)
        self._btn.setStyleSheet(
            "QPushButton { background:#21262d; color:#8b949e; border:1px solid #30363d; "
            "border-radius:4px; font-size:11px; } "
            "QPushButton:checked { color:#e6edf3; }"
        )
        self._btn.toggled.connect(self._toggle)
        lay.addWidget(self._edit)
        lay.addWidget(self._btn)

    def _toggle(self, show: bool):
        mode = QLineEdit.EchoMode.Normal if show else QLineEdit.EchoMode.Password
        self._edit.setEchoMode(mode)

    def text(self) -> str:
        return self._edit.text()

    def setText(self, t: str):
        self._edit.setText(t)


def _make_input(placeholder: str = "") -> QLineEdit:
    e = QLineEdit()
    e.setPlaceholderText(placeholder)
    e.setStyleSheet(_STYLE_INPUT)
    return e


def _make_label(text: str, style: str = _STYLE_GRAY) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(style)
    return lbl


# ─────────────────────────────────────────────────────────────────────────────

class BrokerPanel(QWidget):
    """Pannello impostazioni broker."""

    # Indice corrispondente al combo broker
    _BROKER_IDS = ["paper", "ig", "oanda", "alpaca", "ccxt"]
    _BROKER_LABELS = ["Paper (Simulazione)", "IG Markets", "OANDA", "Alpaca", "CCXT Crypto"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._status_connected = False
        self._setup_ui()
        self._load_from_settings()

    # ─────────────────────────────────────────────────────────────────────
    # UI setup
    # ─────────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # ── Title ────────────────────────────────────────────────────────
        title = QLabel("Impostazioni Broker")
        title.setStyleSheet(_STYLE_TITLE)
        root.addWidget(title)
        root.addWidget(_sep())

        # ── Status ───────────────────────────────────────────────────────
        status_row = QHBoxLayout()
        status_row.setSpacing(6)
        status_lbl = QLabel("Stato:")
        status_lbl.setStyleSheet(_STYLE_GRAY)
        status_row.addWidget(status_lbl)
        self._lbl_status = QLabel("● Paper — SIMULAZIONE")
        self._lbl_status.setStyleSheet(_STYLE_YELLOW)
        status_row.addWidget(self._lbl_status, 1)
        root.addLayout(status_row)

        root.addWidget(_sep())

        # ── Broker selector ──────────────────────────────────────────────
        broker_row = QFormLayout()
        broker_row.setSpacing(6)
        self._combo_broker = QComboBox()
        self._combo_broker.addItems(self._BROKER_LABELS)
        self._combo_broker.setStyleSheet(_STYLE_COMBO)
        broker_row.addRow(_make_label("Broker attivo:"), self._combo_broker)
        root.addLayout(broker_row)

        # ── Stacked credential panels ────────────────────────────────────
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_paper_panel())   # 0 — paper
        self._stack.addWidget(self._build_ig_panel())      # 1 — ig
        self._stack.addWidget(self._build_oanda_panel())   # 2 — oanda
        self._stack.addWidget(self._build_alpaca_panel())  # 3 — alpaca
        self._stack.addWidget(self._build_ccxt_panel())    # 4 — ccxt
        root.addWidget(self._stack)

        root.addWidget(_sep())

        # ── Buttons ──────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._btn_save = QPushButton("Salva impostazioni")
        self._btn_save.setStyleSheet(_STYLE_BTN_SAVE)
        self._btn_test = QPushButton("Testa connessione")
        self._btn_test.setStyleSheet(_STYLE_BTN_TEST)
        btn_row.addWidget(self._btn_save)
        btn_row.addWidget(self._btn_test)
        root.addLayout(btn_row)

        self._lbl_result = QLabel("")
        self._lbl_result.setStyleSheet(_STYLE_GRAY)
        self._lbl_result.setWordWrap(True)
        root.addWidget(self._lbl_result)

        root.addStretch()

        # ── Connections ──────────────────────────────────────────────────
        self._combo_broker.currentIndexChanged.connect(self._on_broker_changed)
        self._btn_save.clicked.connect(self._on_save)
        self._btn_test.clicked.connect(self._on_test)

    # ─── Credential sub-panels ───────────────────────────────────────────

    def _build_paper_panel(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 4, 0, 4)
        info = QLabel(
            "Nessuna credenziale richiesta.\n"
            "In modalità Paper gli ordini sono simulati senza soldi reali."
        )
        info.setStyleSheet("color:#58a6ff; font-size:11px;")
        info.setWordWrap(True)
        lay.addWidget(info)
        return w

    def _build_ig_panel(self) -> QWidget:
        grp = QGroupBox("IG Markets — CFD (forex, indici, oro)")
        grp.setStyleSheet(_STYLE_GROUP)
        form = QFormLayout(grp)
        form.setContentsMargins(8, 12, 8, 8)
        form.setSpacing(6)

        self._ig_api_key  = _make_input("es. abc123def456...")
        self._ig_username = _make_input("email@esempio.com")
        self._ig_password = _PasswordField()
        self._ig_account_type = QComboBox()
        self._ig_account_type.addItems(["demo", "live"])
        self._ig_account_type.setStyleSheet(_STYLE_COMBO)
        self._ig_account_id = _make_input("lascia vuoto per default")

        form.addRow(_make_label("API Key:"),       self._ig_api_key)
        form.addRow(_make_label("Username:"),      self._ig_username)
        form.addRow(_make_label("Password:"),      self._ig_password)
        form.addRow(_make_label("Account type:"),  self._ig_account_type)
        form.addRow(_make_label("Account ID:"),    self._ig_account_id)

        note = QLabel(
            "Conto demo gratuito: ig.com/it → Conto Demo\n"
            "API key: labs.ig.com → My Applications"
        )
        note.setStyleSheet("color:#484f58; font-size:10px;")
        note.setWordWrap(True)
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addWidget(grp)
        lay.addWidget(note)
        return w

    def _build_oanda_panel(self) -> QWidget:
        grp = QGroupBox("OANDA — Forex + XAU/USD")
        grp.setStyleSheet(_STYLE_GROUP)
        form = QFormLayout(grp)
        form.setContentsMargins(8, 12, 8, 8)
        form.setSpacing(6)

        self._oanda_token      = _make_input("es. abc123-def456-ghi789")
        self._oanda_account_id = _make_input("es. 101-004-XXXXXXX-001")
        self._oanda_env = QComboBox()
        self._oanda_env.addItems(["practice", "live"])
        self._oanda_env.setStyleSheet(_STYLE_COMBO)

        form.addRow(_make_label("API Token:"),    self._oanda_token)
        form.addRow(_make_label("Account ID:"),   self._oanda_account_id)
        form.addRow(_make_label("Ambiente:"),     self._oanda_env)

        note = QLabel(
            "Conto practice gratuito: oanda.com\n"
            "Token: MyAccount → Manage API Access"
        )
        note.setStyleSheet("color:#484f58; font-size:10px;")
        note.setWordWrap(True)
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addWidget(grp)
        lay.addWidget(note)
        return w

    def _build_alpaca_panel(self) -> QWidget:
        grp = QGroupBox("Alpaca — Azioni USA")
        grp.setStyleSheet(_STYLE_GROUP)
        form = QFormLayout(grp)
        form.setContentsMargins(8, 12, 8, 8)
        form.setSpacing(6)

        self._alpaca_key    = _make_input("API Key ID")
        self._alpaca_secret = _PasswordField()
        self._alpaca_paper  = QComboBox()
        self._alpaca_paper.addItems(["Paper (simulato)", "Live"])
        self._alpaca_paper.setStyleSheet(_STYLE_COMBO)

        form.addRow(_make_label("API Key:"),    self._alpaca_key)
        form.addRow(_make_label("Secret:"),     self._alpaca_secret)
        form.addRow(_make_label("Modalità:"),   self._alpaca_paper)
        return grp

    def _build_ccxt_panel(self) -> QWidget:
        grp = QGroupBox("CCXT — Crypto Exchanges")
        grp.setStyleSheet(_STYLE_GROUP)
        form = QFormLayout(grp)
        form.setContentsMargins(8, 12, 8, 8)
        form.setSpacing(6)

        self._ccxt_exchange = _make_input("es. binance, coinbase, kraken")
        self._ccxt_key      = _make_input("API Key")
        self._ccxt_secret   = _PasswordField()
        self._ccxt_sandbox  = QComboBox()
        self._ccxt_sandbox.addItems(["Sandbox (simulato)", "Live"])
        self._ccxt_sandbox.setStyleSheet(_STYLE_COMBO)

        form.addRow(_make_label("Exchange:"),  self._ccxt_exchange)
        form.addRow(_make_label("API Key:"),   self._ccxt_key)
        form.addRow(_make_label("Secret:"),    self._ccxt_secret)
        form.addRow(_make_label("Modalità:"),  self._ccxt_sandbox)
        return grp

    # ─────────────────────────────────────────────────────────────────────
    # Load / Save
    # ─────────────────────────────────────────────────────────────────────

    def _load_from_settings(self):
        """Popola i campi con i valori correnti da config/settings."""
        try:
            from config.settings import settings
            b = settings.broker

            # Broker combo
            broker_id = b.active_broker.lower()
            idx = self._BROKER_IDS.index(broker_id) if broker_id in self._BROKER_IDS else 0
            self._combo_broker.setCurrentIndex(idx)
            self._stack.setCurrentIndex(idx)

            # IG
            self._ig_api_key.setText(b.ig_api_key)
            self._ig_username.setText(b.ig_username)
            self._ig_password.setText(b.ig_password)
            acct_idx = 1 if b.ig_account_type == "live" else 0
            self._ig_account_type.setCurrentIndex(acct_idx)
            self._ig_account_id.setText(b.ig_account_id)

            # OANDA
            self._oanda_token.setText(b.oanda_api_token)
            self._oanda_account_id.setText(b.oanda_account_id)
            env_idx = 1 if b.oanda_environment == "live" else 0
            self._oanda_env.setCurrentIndex(env_idx)

            # Alpaca
            self._alpaca_key.setText(b.alpaca_api_key)
            self._alpaca_secret.setText(b.alpaca_secret_key)
            paper_idx = 0 if b.alpaca_paper else 1
            self._alpaca_paper.setCurrentIndex(paper_idx)

            # CCXT
            self._ccxt_exchange.setText(b.ccxt_exchange)
            self._ccxt_key.setText(b.ccxt_api_key)
            self._ccxt_secret.setText(b.ccxt_secret)
            sandbox_idx = 0 if b.ccxt_sandbox else 1
            self._ccxt_sandbox.setCurrentIndex(sandbox_idx)

            self._update_status_label(broker_id)
        except Exception as e:
            self._lbl_result.setText(f"Errore caricamento impostazioni: {e}")

    def _on_broker_changed(self, idx: int):
        self._stack.setCurrentIndex(idx)
        broker_id = self._BROKER_IDS[idx]
        self._update_status_label(broker_id)

    def _update_status_label(self, broker_id: str):
        if broker_id == "paper":
            self._lbl_status.setText("● Paper — SIMULAZIONE")
            self._lbl_status.setStyleSheet(_STYLE_YELLOW)
        else:
            label = self._BROKER_LABELS[self._BROKER_IDS.index(broker_id)]
            self._lbl_status.setText(f"○ {label} — non connesso")
            self._lbl_status.setStyleSheet(_STYLE_GRAY)

    # ─────────────────────────────────────────────────────────────────────
    # Save to .env
    # ─────────────────────────────────────────────────────────────────────

    @pyqtSlot()
    def _on_save(self):
        """Salva le credenziali nel file .env."""
        idx = self._combo_broker.currentIndex()
        broker_id = self._BROKER_IDS[idx]

        updates: Dict[str, str] = {
            "BROKER_ACTIVE_BROKER": broker_id,
        }

        if broker_id == "ig":
            updates.update({
                "BROKER_IG_API_KEY":       self._ig_api_key.text(),
                "BROKER_IG_USERNAME":      self._ig_username.text(),
                "BROKER_IG_PASSWORD":      self._ig_password.text(),
                "BROKER_IG_ACCOUNT_TYPE":  self._ig_account_type.currentText(),
                "BROKER_IG_ACCOUNT_ID":    self._ig_account_id.text(),
            })
        elif broker_id == "oanda":
            updates.update({
                "BROKER_OANDA_API_TOKEN":    self._oanda_token.text(),
                "BROKER_OANDA_ACCOUNT_ID":  self._oanda_account_id.text(),
                "BROKER_OANDA_ENVIRONMENT": self._oanda_env.currentText(),
            })
        elif broker_id == "alpaca":
            updates.update({
                "BROKER_ALPACA_API_KEY":    self._alpaca_key.text(),
                "BROKER_ALPACA_SECRET_KEY": self._alpaca_secret.text(),
                "BROKER_ALPACA_PAPER":      "true" if self._alpaca_paper.currentIndex() == 0 else "false",
            })
        elif broker_id == "ccxt":
            updates.update({
                "BROKER_CCXT_EXCHANGE": self._ccxt_exchange.text(),
                "BROKER_CCXT_API_KEY":  self._ccxt_key.text(),
                "BROKER_CCXT_SECRET":   self._ccxt_secret.text(),
                "BROKER_CCXT_SANDBOX":  "true" if self._ccxt_sandbox.currentIndex() == 0 else "false",
            })

        try:
            self._write_env(updates)
            # Aggiorna settings in memoria per la sessione corrente
            self._apply_to_settings(broker_id)
            self._lbl_result.setStyleSheet(_STYLE_GREEN)
            self._lbl_result.setText(
                "Impostazioni salvate in .env. Riavvia l'app per applicarle."
            )
        except Exception as e:
            self._lbl_result.setStyleSheet(_STYLE_RED)
            self._lbl_result.setText(f"Errore salvataggio: {e}")

    def _write_env(self, updates: Dict[str, str]):
        """Aggiorna le righe corrispondenti nel file .env."""
        if not _ENV_PATH.exists():
            raise FileNotFoundError(f".env non trovato: {_ENV_PATH}")

        lines = _ENV_PATH.read_text(encoding="utf-8").splitlines(keepends=True)
        changed_keys = set()

        new_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#") or "=" not in stripped:
                new_lines.append(line)
                continue
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}\n")
                changed_keys.add(key)
            else:
                new_lines.append(line)

        # Aggiungi le chiavi non trovate nel file
        for key, val in updates.items():
            if key not in changed_keys:
                new_lines.append(f"{key}={val}\n")

        _ENV_PATH.write_text("".join(new_lines), encoding="utf-8")

    def _apply_to_settings(self, broker_id: str):
        """Aggiorna settings in-memory (no riavvio per active_broker)."""
        try:
            from config.settings import settings
            settings.broker.active_broker = broker_id
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────────────
    # Test connection
    # ─────────────────────────────────────────────────────────────────────

    @pyqtSlot()
    def _on_test(self):
        idx = self._combo_broker.currentIndex()
        broker_id = self._BROKER_IDS[idx]

        if broker_id == "paper":
            self._lbl_result.setStyleSheet(_STYLE_GREEN)
            self._lbl_result.setText("Paper broker: nessuna connessione necessaria.")
            self._lbl_status.setText("● Paper — SIMULAZIONE")
            self._lbl_status.setStyleSheet(_STYLE_YELLOW)
            return

        self._btn_test.setEnabled(False)
        self._lbl_result.setStyleSheet(_STYLE_GRAY)
        self._lbl_result.setText("Test connessione in corso...")
        asyncio.ensure_future(self._async_test(broker_id))

    async def _async_test(self, broker_id: str):
        try:
            ok, msg = await self._do_test(broker_id)
            if ok:
                self._lbl_status.setText(f"● {broker_id.upper()} — CONNESSO")
                self._lbl_status.setStyleSheet(_STYLE_GREEN)
                self._lbl_result.setStyleSheet(_STYLE_GREEN)
                self._lbl_result.setText(f"Connessione riuscita: {msg}")
            else:
                self._lbl_status.setText(f"○ {broker_id.upper()} — ERRORE")
                self._lbl_status.setStyleSheet(_STYLE_RED)
                self._lbl_result.setStyleSheet(_STYLE_RED)
                self._lbl_result.setText(f"Connessione fallita: {msg}")
        except Exception as e:
            self._lbl_result.setStyleSheet(_STYLE_RED)
            self._lbl_result.setText(f"Errore test: {e}")
        finally:
            self._btn_test.setEnabled(True)

    async def _do_test(self, broker_id: str):
        if broker_id == "ig":
            from brokers.ig_broker import IGBroker
            b = IGBroker(
                api_key=self._ig_api_key.text(),
                username=self._ig_username.text(),
                password=self._ig_password.text(),
                account_type=self._ig_account_type.currentText(),
                account_id=self._ig_account_id.text() or None,
            )
            ok = await b.connect()
            if ok:
                await b.disconnect()
                return True, "IG Markets connesso con successo"
            return False, "Credenziali IG non valide o server non raggiungibile"

        elif broker_id == "oanda":
            from brokers.oanda_broker import OANDABroker
            b = OANDABroker(
                api_token=self._oanda_token.text(),
                account_id=self._oanda_account_id.text(),
                environment=self._oanda_env.currentText(),
            )
            ok = await b.connect()
            if ok:
                await b.disconnect()
                return True, "OANDA connesso con successo"
            return False, "Token OANDA non valido o account ID errato"

        elif broker_id == "alpaca":
            from brokers.alpaca_broker import AlpacaBroker
            b = AlpacaBroker()
            ok = await b.connect()
            if ok:
                await b.disconnect()
                return True, "Alpaca connesso"
            return False, "Credenziali Alpaca non valide"

        elif broker_id == "ccxt":
            try:
                import ccxt.async_support as ccxt
                exchange_name = self._ccxt_exchange.text().strip() or "binance"
                cls = getattr(ccxt, exchange_name)
                exchange = cls({
                    "apiKey": self._ccxt_key.text() or None,
                    "secret": self._ccxt_secret.text() or None,
                    "sandbox": self._ccxt_sandbox.currentIndex() == 0,
                    "enableRateLimit": True,
                })
                await exchange.load_markets()
                await exchange.close()
                return True, f"{exchange_name} connesso — {len(exchange.markets)} mercati"
            except Exception as e:
                return False, str(e)

        return False, f"Test non implementato per {broker_id}"
