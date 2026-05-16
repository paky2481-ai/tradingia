"""
SettingsWorkspace — configurazione preferenze, broker e parametri di rischio.

Layout: QScrollArea con QVBoxLayout di sezioni QGroupBox.
Sezioni:
    A. Generale  — lingua interfaccia + tema (placeholder)
    B. Broker    — apre BrokerPanel in popup QDialog
    C. Rischio   — capitale iniziale, risk/trade, max drawdown (persiste su .env)
    D. Info      — versione, Python, PyQt6, percorsi .env e DB
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gui.i18n import tr
from gui.state.app_state import AppState

# Percorsi costanti
_ENV_PATH = Path(os.getcwd()) / ".env"
_DB_PATH  = Path(os.getcwd()) / "data" / "tradingia.db"

# ---------------------------------------------------------------------------
# Stili interni (palette Bloomberg-style usata in tutta la GUI)
# ---------------------------------------------------------------------------
_STYLE_LABEL = "color:#e6edf3; font-size:12px;"
_STYLE_GRAY  = "color:#8b949e; font-size:11px;"
_STYLE_BTN   = (
    "QPushButton { background:#21262d; color:#e6edf3; border:1px solid #30363d; "
    "border-radius:4px; padding:6px 14px; font-size:11px; } "
    "QPushButton:hover { background:#30363d; } "
    "QPushButton:pressed { background:#161b22; }"
)
_STYLE_COMBO = (
    "QComboBox { background:#0d1117; color:#e6edf3; border:1px solid #30363d; "
    "border-radius:4px; padding:4px 8px; font-size:11px; } "
    "QComboBox::drop-down { border:none; } "
    "QComboBox QAbstractItemView { background:#161b22; color:#e6edf3; "
    "selection-background-color:#21262d; border:1px solid #30363d; }"
)
_STYLE_SPINBOX = (
    "QDoubleSpinBox { background:#0d1117; color:#e6edf3; border:1px solid #30363d; "
    "border-radius:4px; padding:4px 8px; font-size:11px; } "
    "QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { "
    "background:#21262d; border:none; width:16px; }"
)
_STYLE_GROUP = (
    "QGroupBox { color:#8b949e; font-size:11px; font-weight:bold; "
    "border:1px solid #21262d; border-radius:6px; margin-top:8px; padding:8px 6px; } "
    "QGroupBox::title { subcontrol-origin:margin; left:10px; padding:0 4px; }"
)


# ---------------------------------------------------------------------------
# Helper: legge variabili .env manualmente (fallback se dotenv non presente)
# ---------------------------------------------------------------------------

def _read_env_var(key: str, default: str = "") -> str:
    """Legge una variabile dal file .env senza importare dotenv."""
    if not _ENV_PATH.exists():
        return default
    try:
        for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            if k.strip() == key:
                return v.strip().strip('"').strip("'")
    except Exception:
        pass
    return default


def _write_env_vars(updates: dict[str, str]) -> None:
    """Aggiorna/aggiunge variabili nel file .env — prima tenta dotenv, poi manuale."""
    try:
        from dotenv import set_key
        for k, v in updates.items():
            set_key(str(_ENV_PATH), k, v)
        return
    except ImportError:
        pass

    # Fallback manuale: legge il file, aggiorna righe esistenti, aggiunge le mancanti
    lines: list[str] = []
    if _ENV_PATH.exists():
        lines = _ENV_PATH.read_text(encoding="utf-8").splitlines()

    found = {k: False for k in updates}
    new_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("#") and "=" in stripped:
            k, _, _ = stripped.partition("=")
            k = k.strip()
            if k in updates:
                new_lines.append(f'{k}="{updates[k]}"')
                found[k] = True
                continue
        new_lines.append(line)

    for k, v in updates.items():
        if not found[k]:
            new_lines.append(f'{k}="{v}"')

    _ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# BrokerDialog — popup che wrappa BrokerPanel
# ---------------------------------------------------------------------------

class _BrokerDialog(QDialog):
    """Dialog modale che ospita BrokerPanel come popup."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("settings.broker_dialog_title"))
        self.setMinimumSize(600, 500)
        self.resize(700, 580)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        try:
            from gui.panels.broker_panel import BrokerPanel
            panel = BrokerPanel()
            lay.addWidget(panel)
        except Exception as e:
            lay.addWidget(QLabel(f"BrokerPanel non disponibile: {e}"))

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(self.accept)
        lay.addWidget(btn_box)


# ---------------------------------------------------------------------------
# SettingsWorkspace
# ---------------------------------------------------------------------------

class SettingsWorkspace(QWidget):
    """
    Workspace impostazioni — selettore lingua, broker, parametri rischio, info.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Scroll area contenitore
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border:none; background:#0d1117; }")

        container = QWidget()
        container.setStyleSheet("background:#0d1117;")
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(24, 20, 24, 20)
        vbox.setSpacing(16)

        # Titolo workspace
        title_lbl = QLabel(tr("workspace.settings"))
        title_lbl.setStyleSheet("color:#e6edf3; font-size:18px; font-weight:bold;")
        sub_lbl = QLabel(tr("workspace.subtitle.settings"))
        sub_lbl.setStyleSheet("color:#8b949e; font-size:12px;")
        vbox.addWidget(title_lbl)
        vbox.addWidget(sub_lbl)

        # Separatore visivo
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background:#21262d;")
        vbox.addWidget(sep)

        # Sezioni
        vbox.addWidget(self._build_general_section())
        vbox.addWidget(self._build_broker_section())
        vbox.addWidget(self._build_risk_section())
        vbox.addWidget(self._build_info_section())

        vbox.addStretch(1)

        scroll.setWidget(container)
        outer.addWidget(scroll)

    # ── A. Sezione Generale ───────────────────────────────────────────────────

    def _build_general_section(self) -> QGroupBox:
        group = QGroupBox(tr("settings.section.general"))
        group.setStyleSheet(_STYLE_GROUP)
        form = QFormLayout(group)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setSpacing(10)
        form.setContentsMargins(12, 16, 12, 12)

        # --- Lingua ---
        lang_lbl = QLabel(tr("settings.lang_label"))
        lang_lbl.setStyleSheet(_STYLE_LABEL)

        self._lang_combo = QComboBox()
        self._lang_combo.setStyleSheet(_STYLE_COMBO)
        self._lang_combo.addItem("Italiano", "it")
        self._lang_combo.addItem("English", "en")
        # Seleziona lingua corrente
        current_lang = AppState.instance().language
        idx = self._lang_combo.findData(current_lang)
        if idx >= 0:
            self._lang_combo.setCurrentIndex(idx)
        self._lang_combo.currentIndexChanged.connect(self._on_lang_changed)
        form.addRow(lang_lbl, self._lang_combo)

        # --- Tema (placeholder disabilitato) ---
        theme_lbl = QLabel(tr("settings.theme_label"))
        theme_lbl.setStyleSheet(_STYLE_LABEL)

        theme_combo = QComboBox()
        theme_combo.setStyleSheet(_STYLE_COMBO)
        theme_combo.addItem(tr("settings.theme_dark"))
        theme_combo.addItem(tr("settings.theme_light_soon"))
        theme_combo.setEnabled(False)
        theme_combo.setToolTip("Disponibile nelle prossime versioni")
        form.addRow(theme_lbl, theme_combo)

        return group

    def _on_lang_changed(self, index: int) -> None:
        code = self._lang_combo.itemData(index)
        if not code:
            return
        # Salva in QSettings
        qs = QSettings("TradingIA", "TradingIA")
        qs.setValue("language", code)
        qs.sync()
        # Aggiorna AppState
        AppState.instance().language = code
        # Informa l'utente che serve riavvio
        QMessageBox.information(
            self,
            tr("settings.lang_restart_title"),
            tr("settings.lang_restart_body"),
        )

    # ── B. Sezione Broker ─────────────────────────────────────────────────────

    def _build_broker_section(self) -> QGroupBox:
        group = QGroupBox(tr("settings.section.broker"))
        group.setStyleSheet(_STYLE_GROUP)
        lay = QHBoxLayout(group)
        lay.setContentsMargins(12, 16, 12, 12)

        btn = QPushButton(tr("settings.btn_open_broker"))
        btn.setStyleSheet(_STYLE_BTN)
        btn.clicked.connect(self._open_broker_dialog)
        btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        lay.addWidget(btn)
        lay.addStretch()

        return group

    def _open_broker_dialog(self) -> None:
        dlg = _BrokerDialog(self)
        dlg.exec()

    # ── C. Sezione Rischio ────────────────────────────────────────────────────

    def _build_risk_section(self) -> QGroupBox:
        group = QGroupBox(tr("settings.section.risk"))
        group.setStyleSheet(_STYLE_GROUP)
        form = QFormLayout(group)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setSpacing(10)
        form.setContentsMargins(12, 16, 12, 12)

        # Capitale iniziale
        cap_lbl = QLabel(tr("settings.risk.initial_capital"))
        cap_lbl.setStyleSheet(_STYLE_LABEL)
        self._spin_capital = QDoubleSpinBox()
        self._spin_capital.setStyleSheet(_STYLE_SPINBOX)
        self._spin_capital.setRange(100.0, 1_000_000.0)
        self._spin_capital.setDecimals(2)
        self._spin_capital.setSuffix(" €")
        self._spin_capital.setMaximumWidth(180)
        _cap_str = _read_env_var("INITIAL_CAPITAL", "10000")
        try:
            self._spin_capital.setValue(float(_cap_str))
        except ValueError:
            self._spin_capital.setValue(10_000.0)
        form.addRow(cap_lbl, self._spin_capital)

        # Risk per trade %
        rpt_lbl = QLabel(tr("settings.risk.per_trade_pct"))
        rpt_lbl.setStyleSheet(_STYLE_LABEL)
        self._spin_risk = QDoubleSpinBox()
        self._spin_risk.setStyleSheet(_STYLE_SPINBOX)
        self._spin_risk.setRange(0.1, 10.0)
        self._spin_risk.setDecimals(2)
        self._spin_risk.setSuffix(" %")
        self._spin_risk.setMaximumWidth(180)
        _rpt_str = _read_env_var("RISK_PER_TRADE_PCT", "1.0")
        try:
            self._spin_risk.setValue(float(_rpt_str))
        except ValueError:
            self._spin_risk.setValue(1.0)
        form.addRow(rpt_lbl, self._spin_risk)

        # Max drawdown %
        dd_lbl = QLabel(tr("settings.risk.max_drawdown"))
        dd_lbl.setStyleSheet(_STYLE_LABEL)
        self._spin_drawdown = QDoubleSpinBox()
        self._spin_drawdown.setStyleSheet(_STYLE_SPINBOX)
        self._spin_drawdown.setRange(5.0, 50.0)
        self._spin_drawdown.setDecimals(2)
        self._spin_drawdown.setSuffix(" %")
        self._spin_drawdown.setMaximumWidth(180)
        _dd_str = _read_env_var("MAX_DRAWDOWN_PCT", "20.0")
        try:
            self._spin_drawdown.setValue(float(_dd_str))
        except ValueError:
            self._spin_drawdown.setValue(20.0)
        form.addRow(dd_lbl, self._spin_drawdown)

        # Riga status + pulsante salva
        self._risk_status_lbl = QLabel("")
        self._risk_status_lbl.setStyleSheet(_STYLE_GRAY)

        btn_save = QPushButton(tr("settings.btn_save_env"))
        btn_save.setStyleSheet(_STYLE_BTN)
        btn_save.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        btn_save.clicked.connect(self._save_risk_to_env)

        btn_row = QHBoxLayout()
        btn_row.addWidget(btn_save)
        btn_row.addWidget(self._risk_status_lbl)
        btn_row.addStretch()
        form.addRow("", btn_row)

        return group

    def _save_risk_to_env(self) -> None:
        try:
            _write_env_vars({
                "INITIAL_CAPITAL": f"{self._spin_capital.value():.2f}",
                "RISK_PER_TRADE_PCT": f"{self._spin_risk.value():.2f}",
                "MAX_DRAWDOWN_PCT": f"{self._spin_drawdown.value():.2f}",
            })
            msg = tr("settings.env_saved", path=str(_ENV_PATH))
            self._risk_status_lbl.setText(msg)
            self._risk_status_lbl.setStyleSheet("color:#3fb950; font-size:11px;")
        except Exception as e:
            msg = tr("settings.env_error", error=str(e))
            self._risk_status_lbl.setText(msg)
            self._risk_status_lbl.setStyleSheet("color:#f85149; font-size:11px;")

    # ── D. Sezione Info ───────────────────────────────────────────────────────

    def _build_info_section(self) -> QGroupBox:
        group = QGroupBox(tr("settings.section.info"))
        group.setStyleSheet(_STYLE_GROUP)
        form = QFormLayout(group)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setSpacing(8)
        form.setContentsMargins(12, 16, 12, 12)

        # Versione app
        from PyQt6.QtWidgets import QApplication
        app_ver = QApplication.applicationVersion() or "2.0.0"
        self._add_info_row(form, tr("settings.info.version"), app_ver)

        # Python
        py_ver = sys.version.split()[0]
        self._add_info_row(form, tr("settings.info.python"), py_ver)

        # PyQt6
        try:
            from PyQt6.QtCore import PYQT_VERSION_STR
            pyqt_ver = PYQT_VERSION_STR
        except ImportError:
            pyqt_ver = "n/d"
        self._add_info_row(form, tr("settings.info.pyqt"), pyqt_ver)

        # Percorso .env
        self._add_info_row(form, tr("settings.info.env_path"), str(_ENV_PATH))

        # Percorso DB
        self._add_info_row(form, tr("settings.info.db_path"), str(_DB_PATH))

        return group

    @staticmethod
    def _add_info_row(form: QFormLayout, label: str, value: str) -> None:
        lbl_key = QLabel(label)
        lbl_key.setStyleSheet(_STYLE_LABEL)
        lbl_val = QLabel(value)
        lbl_val.setStyleSheet(_STYLE_GRAY)
        lbl_val.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        form.addRow(lbl_key, lbl_val)
