"""
theme - stylesheet escuro (QSS) usado pela GUI, com cores derivadas do
icone do app (preto/branco/laranja) + um acento teal para gamescope/proton.
Nao mexe em logica, so aparencia.
"""
import html

BG = "#0f0d0a"
SURFACE = "#191714"
SURFACE_2 = "#24211d"
SURFACE_3 = "#2e2b26"
BORDER = "rgba(255, 255, 255, 23)"
BORDER_STRONG = "rgba(255, 255, 255, 41)"
TEXT = "#edebe8"
TEXT_MUTED = "#a8a49e"
TEXT_FAINT = "#918b84"
ACCENT = "#f7a224"
ACCENT_HOVER = "#ffbc5e"
ACCENT_INK = "#1f1306"
ACCENT_2 = "#17d0d8"
ACCENT_2_TEXT = "#92f1f6"

STYLESHEET = f"""
QWidget {{
    background: {BG};
    color: {TEXT};
    font-size: 13px;
}}
QMainWindow, QSplitter {{ background: {BG}; }}
QSplitter::handle {{ background: {BORDER}; }}
QSplitter::handle:horizontal {{ width: 1px; }}

QLabel {{
    color: {TEXT_MUTED};
    font-weight: 600;
    background: transparent;
}}

QCheckBox {{
    color: {TEXT};
    font-weight: 600;
    spacing: 10px;
    background: transparent;
    padding: 4px 0;
}}
QCheckBox::indicator {{
    width: 34px;
    height: 18px;
    border-radius: 9px;
    background: {SURFACE_3};
    border: 1px solid {BORDER};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}
QCheckBox[accent="teal"]::indicator:checked {{
    background: {ACCENT_2};
    border-color: {ACCENT_2};
}}
QCheckBox[accent="neutral"]::indicator:checked {{
    background: #55504a;
    border-color: #6a655d;
}}
QCheckBox:disabled {{ color: {TEXT_FAINT}; }}

QGroupBox {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 14px;
    margin-top: 16px;
    padding: 20px 16px 14px 16px;
    font-weight: 800;
    font-size: 14px;
    color: {TEXT};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    top: 3px;
    padding: 0 6px;
    background: {SURFACE};
}}
QGroupBox::indicator {{
    width: 34px;
    height: 18px;
    border-radius: 9px;
    background: {SURFACE_3};
    border: 1px solid {BORDER};
}}
QGroupBox::indicator:checked {{
    background: {ACCENT_2};
    border-color: {ACCENT_2};
}}

QLineEdit, QComboBox {{
    background: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 10px;
    color: {TEXT};
    selection-background-color: {ACCENT};
    selection-color: {ACCENT_INK};
}}
QLineEdit:focus, QComboBox:focus {{ border: 1px solid {BORDER_STRONG}; }}
QLineEdit:read-only {{ color: {TEXT_MUTED}; }}
QLineEdit:disabled, QComboBox:disabled {{ color: {TEXT_FAINT}; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    background: {SURFACE_2};
    color: {TEXT};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT};
    selection-color: {ACCENT_INK};
}}

QPushButton {{
    background: {SURFACE_2};
    border: 1px solid {BORDER_STRONG};
    border-radius: 9px;
    padding: 8px 16px;
    color: {TEXT};
    font-weight: 700;
}}
QPushButton:hover {{ border-color: {ACCENT}; }}
QPushButton:pressed {{ background: {SURFACE_3}; }}
QPushButton:disabled {{ color: {TEXT_FAINT}; border-color: {BORDER}; }}
QPushButton[role="primary"] {{
    background: {ACCENT};
    border-color: {ACCENT};
    color: {ACCENT_INK};
}}
QPushButton[role="primary"]:hover {{ background: {ACCENT_HOVER}; border-color: {ACCENT_HOVER}; }}
QPushButton[role="primary"]:disabled {{ background: {SURFACE_3}; border-color: {BORDER}; color: {TEXT_FAINT}; }}

QPushButton[role="segment"] {{
    padding: 6px 13px;
    font-size: 12.5px;
    border-radius: 8px;
    color: {TEXT_MUTED};
}}
QPushButton[role="segment"]:checked {{
    background: rgba(23, 208, 216, 40);
    border-color: {ACCENT_2};
    color: {ACCENT_2_TEXT};
}}

QTableWidget {{
    background: {BG};
    border: none;
    gridline-color: transparent;
    color: {TEXT};
}}
QTableWidget::item {{ padding: 10px 8px; border-bottom: 1px solid {BORDER}; }}
QTableWidget::item:selected {{ background: rgba(247, 162, 36, 28); color: {TEXT}; }}
QHeaderView::section {{
    background: {BG};
    color: {TEXT_FAINT};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 8px;
    font-weight: 700;
}}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {SURFACE_3}; border-radius: 5px; min-height: 24px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {SURFACE_3}; border-radius: 5px; min-width: 24px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

QLabel#cmdPreview {{
    background: #0b0a08;
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 10px 12px;
    font-family: "JetBrains Mono", "Fira Code", monospace;
    color: {TEXT};
}}
QLabel#detailTitle {{
    color: {TEXT};
    font-weight: 800;
    font-size: 16px;
}}
QMessageBox {{ background: {SURFACE}; }}
"""

_TOKEN_COLORS = {
    "cmd": ACCENT,
    "flag": ACCENT_2_TEXT,
    "muted": TEXT_FAINT,
    "value": TEXT,
}

_COMMAND_NAMES = {"gamemoderun", "gamescope", "mangohud", "%command%"}


def colorize_command(cmd):
    """Devolve o HTML da string de Launch Options com destaque de sintaxe
    (wrappers, flags e valores em cores diferentes) para o preview."""
    if not cmd:
        return f'<span style="color:{TEXT_FAINT};">— (padrao da Steam)</span>'
    spans = []
    for tok in cmd.split(" "):
        if not tok:
            continue
        if tok == "--" or "=" in tok:
            cls = "muted"
        elif tok in _COMMAND_NAMES:
            cls = "cmd"
        elif tok.startswith("-"):
            cls = "flag"
        else:
            cls = "value"
        spans.append(f'<span style="color:{_TOKEN_COLORS[cls]};">{html.escape(tok)}</span>')
    return " ".join(spans)
