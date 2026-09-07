#!/usr/bin/env python3
"""
steam-boost-gui — app de mesa (PySide6) para configurar visualmente
gamemode, mangohud e gamescope nas Launch Options de cada jogo da Steam.
"""
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from gbsteamparams import core, theme

ICON_PATH = Path(__file__).parent / "resources" / "icon.svg"

GAMESCOPE_FILTERS = [
    ("Padrao", ""),
    ("Linear", "linear"),
    ("Nearest", "nearest"),
    ("FSR", "fsr"),
    ("NIS", "nis"),
    ("Pixel", "pixel"),
]

GAMESCOPE_SCALERS = [
    ("Padrao", ""),
    ("Integer", "integer"),
    ("Fit", "fit"),
    ("Fill", "fill"),
    ("Esticar (4:3)", "stretch"),
]

LSFG_MULTIPLIERS = [
    ("Padrao", ""),
    ("2x", "2"),
    ("3x", "3"),
    ("4x", "4"),
]

# Icones inline (stroke-based, grid 24x24) usados nos cabecalhos de card e
# nas linhas de toggle. Cores sao aplicadas na hora de renderizar (ver
# _svg_pixmap), entao um mesmo icone serve pra qualquer widget.
ICONS = {
    "gamemode": (
        '<path d="M7 8c-2.2 0-4 1.8-4 4.5S4.6 18 6.5 18c1.2 0 1.6-.6 2.3-1.5'
        'l1-1.3c.5-.6 1-.9 1.8-.9h1.6c.8 0 1.3.3 1.8.9l1 1.3c.7.9 1.1 1.5 2.3'
        ' 1.5 1.9 0 3.5-1.2 3.5-5.5S19.2 8 17 8H7Z"/><path d="M7.5 12.5h3M9'
        ' 11v3"/>'
    ),
    "mangohud": '<path d="M4 13h2.5l2-6.5 3 13 2.2-9.5 1.8 3h4.5"/>',
    "gamescope": '<rect x="3" y="5" width="18" height="12" rx="2"/><path d="M8 20h8M12 17v3"/>',
    "proton": '<path d="M8 3h8l-1 6.2a3 3 0 0 1-2.2 2.7v3.1h2.4"/><path d="M12 12v7M9 21h6"/>',
    "lsfg": (
        '<rect x="3" y="8" width="13" height="13" rx="2.5"/>'
        '<path d="M8 8V5.5A2.5 2.5 0 0 1 10.5 3H18a3 3 0 0 1 3 3v10.5a2.5 2.5'
        ' 0 0 1-2.5 2.5H16"/>'
    ),
    "lock": '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
    "disable": '<circle cx="12" cy="12" r="8"/><path d="M7 7l10 10"/>',
    "fullscreen": '<path d="M9 4H4v5M15 4h5v5M9 20H4v-5M15 20h5v-5"/>',
    "borderless": '<rect x="4" y="4" width="16" height="16" rx="2" stroke-dasharray="3 3"/>',
    "keyboard": '<rect x="4" y="5" width="16" height="10" rx="2"/><path d="M8 19h8M9 15v4M15 15v4"/>',
    "cursor": '<rect x="6" y="3" width="12" height="18" rx="6"/><path d="M12 7v4"/>',
    "steam": '<path d="M12 3 3 8l9 5 9-5-9-5Z"/><path d="M3 13l9 5 9-5"/>',
    "sync": '<path d="M4 12a8 8 0 0 1 14-5M20 4v5h-5"/><path d="M20 12a8 8 0 0 1-14 5M4 20v-5h5"/>',
    "bolt": '<path d="M13 2 4 14h6l-1 8 9-12h-6l1-8Z"/>',
    "arrow": '<path d="M5 12h14M13 6l6 6-6 6"/>',
}


def _svg_pixmap(svg_body, color, size=18):
    """Renderiza um icone inline (viewBox 0 0 24 24, so stroke) num
    QPixmap monocromatico da cor pedida."""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        f'fill="none" stroke="{color}" stroke-width="1.75" '
        f'stroke-linecap="round" stroke-linejoin="round">{svg_body}</svg>'
    )
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap


def _set_icon(widget, name, color=None):
    widget.setIcon(QIcon(_svg_pixmap(ICONS[name], color or theme.TEXT_MUTED)))
    widget.setIconSize(QSize(18, 18))


def _make_segmented(group_parent, options):
    """Cria um QButtonGroup exclusivo com um QPushButton checavel por
    opcao (estilo 'pills'), devolvendo (QButtonGroup, QHBoxLayout)."""
    button_group = QButtonGroup(group_parent)
    button_group.setExclusive(True)
    row = QHBoxLayout()
    row.setSpacing(6)
    for label, value in options:
        btn = QPushButton(label)
        btn.setCheckable(True)
        btn.setProperty("role", "segment")
        btn.setProperty("value", value)
        button_group.addButton(btn)
        row.addWidget(btn)
    row.addStretch(1)
    button_group.buttons()[0].setChecked(True)
    return button_group, row


def _segmented_value(button_group):
    for btn in button_group.buttons():
        if btn.isChecked():
            return btn.property("value")
    return ""


def _set_segmented_value(button_group, value):
    value = value or ""
    for btn in button_group.buttons():
        btn.setChecked(btn.property("value") == value)


class Card(QWidget):
    """Card com cabecalho (icone + titulo + tag estatica opcional + badge
    dinamico + switch mestre opcional) e corpo em QFormLayout.

    Quando checkable=True, `switch` e um QCheckBox comum — mesma API que
    o resto do codigo ja espera (isChecked/setChecked/toggled) — e o
    corpo do card fica automaticamente habilitado/desabilitado junto com
    ele, do jeito que um QGroupBox checavel nativo ja fazia sozinho."""

    def __init__(self, icon, title, tag=None, checkable=False):
        super().__init__()
        self.setObjectName("card")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(10)
        icon_label = QLabel()
        icon_label.setPixmap(_svg_pixmap(icon, theme.TEXT_MUTED))
        header.addWidget(icon_label)
        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        header.addWidget(title_label)
        if tag:
            tag_label = QLabel(tag)
            tag_label.setObjectName("cardTag")
            header.addWidget(tag_label)
        header.addStretch(1)
        self.badge = QLabel("")
        self.badge.setObjectName("cardBadge")
        header.addWidget(self.badge)
        self.switch = None
        if checkable:
            self.switch = QCheckBox()
            self.switch.setProperty("accent", "teal")
            header.addWidget(self.switch)
        outer.addLayout(header)

        self.body = QWidget()
        self.body.setObjectName("cardBody")
        self.form = QFormLayout(self.body)
        outer.addWidget(self.body)

        if self.switch is not None:
            self.switch.toggled.connect(self.body.setEnabled)
            self.body.setEnabled(False)

    def set_badge(self, text):
        self.badge.setText(text)


class GameRowWidget(QWidget):
    """Uma linha da lista de jogos: nome+appid a esquerda, chips (ou um
    texto descritivo) a direita."""

    def __init__(self, name, appid, chips, meta):
        super().__init__()
        self.setObjectName("gameRow")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(10)

        info = QVBoxLayout()
        info.setSpacing(2)
        name_label = QLabel(name)
        name_label.setObjectName("gameName")
        name_label.setWordWrap(True)
        appid_label = QLabel(f"AppID {appid}")
        appid_label.setObjectName("gameAppid")
        info.addWidget(name_label)
        info.addWidget(appid_label)
        layout.addLayout(info, 1)

        if chips:
            chip_row = QHBoxLayout()
            chip_row.setSpacing(5)
            for label, dashed in chips:
                chip = QLabel(label)
                chip.setObjectName("chip")
                if dashed:
                    chip.setProperty("dashed", "true")
                chip_row.addWidget(chip)
            layout.addLayout(chip_row)
        elif meta:
            meta_label = QLabel(meta)
            meta_label.setObjectName("gameMeta")
            layout.addWidget(meta_label)


def summary_chips_for(value_pairs, appid, excluded):
    """Devolve (chips, meta) pra uma linha da lista de jogos. chips e uma
    lista de (rotulo, tracejado) pra exibir como pilulas; meta e um texto
    descritivo usado so quando nao ha nenhum chip."""
    if appid in excluded:
        return [("gerenciado manualmente", True)], None
    raw = core.find(value_pairs, "LaunchOptions") or ""
    if not raw:
        return [], "padrao da Steam"
    parsed, _ = core.parse_launch_options(raw)
    chips = []
    if parsed["gamemode"]:
        chips.append(("gamemode", False))
    if parsed["mangohud"]:
        chips.append(("mangohud", False))
    if parsed["gamescope"]:
        chips.append(("gamescope", False))
    lsfg = parsed["lsfg"]
    if lsfg["profile"] or lsfg["multiplier"] or lsfg["flow_scale"] or lsfg["performance_mode"]:
        chips.append(("lsfg-vk", False))
    if parsed["extra"]:
        chips.append(("extra", False))
    if chips:
        return chips, None
    return [], "customizado"


class DetailPanel(QWidget):
    def __init__(self, on_apply):
        super().__init__()
        self.on_apply = on_apply
        self.game = None  # dict atual selecionado

        layout = QVBoxLayout(self)

        self.title = QLabel("Selecione um jogo na lista")
        self.title.setObjectName("detailTitle")
        layout.addWidget(self.title)

        self.managed_check = QCheckBox("Gerenciado manualmente (steam-boost nao mexe)")
        _set_icon(self.managed_check, "lock")
        self.managed_check.setProperty("accent", "neutral")
        self.managed_check.toggled.connect(self._on_managed_toggled)
        layout.addWidget(self.managed_check)

        self.controls = QWidget()
        controls_layout = QVBoxLayout(self.controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(14)

        self.gamemode_check = QCheckBox("gamemode (gamemoderun)")
        _set_icon(self.gamemode_check, "gamemode")
        self.mangohud_check = QCheckBox("MangoHud (overlay de desempenho)")
        _set_icon(self.mangohud_check, "mangohud")
        controls_layout.addWidget(self.gamemode_check)
        controls_layout.addWidget(self.mangohud_check)

        gamescope_card = Card(ICONS["gamescope"], "gamescope", checkable=True)
        self.gamescope_card = gamescope_card
        self.gamescope_box = gamescope_card.switch
        gs_form = gamescope_card.form
        self.gs_render_width = QLineEdit()
        self.gs_render_width.setPlaceholderText("1280")
        self.gs_render_height = QLineEdit()
        self.gs_render_height.setPlaceholderText("800")
        self.gs_width = QLineEdit()
        self.gs_width.setPlaceholderText("2560")
        self.gs_height = QLineEdit()
        self.gs_height.setPlaceholderText("1440")
        self.gs_refresh = QLineEdit()
        self.gs_refresh.setPlaceholderText("ex: 165 (opcional)")

        self.gs_filter_group, filter_row = _make_segmented(self, GAMESCOPE_FILTERS)
        self.gs_scaler_group, scaler_row = _make_segmented(self, GAMESCOPE_SCALERS)

        self.gs_fullscreen = QCheckBox("Tela cheia (-f)")
        _set_icon(self.gs_fullscreen, "fullscreen")
        self.gs_fullscreen.setProperty("accent", "teal")
        self.gs_borderless = QCheckBox("Sem bordas (-b)")
        _set_icon(self.gs_borderless, "borderless")
        self.gs_borderless.setProperty("accent", "teal")
        self.gs_grab = QCheckBox("Capturar teclado (-g)")
        _set_icon(self.gs_grab, "keyboard")
        self.gs_grab.setProperty("accent", "teal")
        self.gs_force_grab_cursor = QCheckBox("Prender o cursor / mouse relativo (--force-grab-cursor)")
        _set_icon(self.gs_force_grab_cursor, "cursor")
        self.gs_force_grab_cursor.setProperty("accent", "teal")
        self.gs_steam = QCheckBox("Integracao com overlay da Steam (-e)")
        _set_icon(self.gs_steam, "steam")
        self.gs_steam.setProperty("accent", "teal")
        self.gs_adaptive_sync = QCheckBox("Adaptive Sync / VRR (--adaptive-sync)")
        _set_icon(self.gs_adaptive_sync, "sync")
        self.gs_adaptive_sync.setProperty("accent", "teal")
        self.gs_framerate_limit = QLineEdit()
        self.gs_framerate_limit.setPlaceholderText("ex: 60 (opcional)")
        self.gs_extra = QLineEdit()
        self.gs_extra.setPlaceholderText("flags extras do gamescope (opcional)")
        gs_form.addRow(self._build_resolution_mapper())
        gs_form.addRow("Taxa de atualizacao", self.gs_refresh)
        gs_form.addRow("Filtro de upscaling", filter_row)
        gs_form.addRow("Modo de escala (-S)", scaler_row)
        gs_form.addRow(self.gs_fullscreen)
        gs_form.addRow(self.gs_borderless)
        gs_form.addRow(self.gs_grab)
        gs_form.addRow(self.gs_force_grab_cursor)
        gs_form.addRow(self.gs_steam)
        gs_form.addRow(self.gs_adaptive_sync)
        gs_form.addRow("Limite de FPS", self.gs_framerate_limit)
        gs_form.addRow("Extra", self.gs_extra)
        controls_layout.addWidget(gamescope_card)

        proton_card = Card(ICONS["proton"], "Proton / Wine", tag="avancado", checkable=False)
        self.proton_card = proton_card
        proton_form = proton_card.form
        self.proton_no_esync = QCheckBox("Desativar ESync (PROTON_NO_ESYNC)")
        _set_icon(self.proton_no_esync, "sync")
        self.proton_no_esync.setProperty("accent", "teal")
        self.proton_no_fsync = QCheckBox("Desativar FSync (PROTON_NO_FSYNC)")
        _set_icon(self.proton_no_fsync, "sync")
        self.proton_no_fsync.setProperty("accent", "teal")
        self.proton_nvapi = QCheckBox("Habilitar NVAPI / DLSS (PROTON_ENABLE_NVAPI)")
        _set_icon(self.proton_nvapi, "bolt")
        self.proton_nvapi.setProperty("accent", "teal")
        self.proton_vkd3d = QLineEdit()
        self.proton_vkd3d.setPlaceholderText("ex: dxr,dxr11 (ray tracing DX12, opcional)")
        proton_form.addRow(self.proton_no_esync)
        proton_form.addRow(self.proton_no_fsync)
        proton_form.addRow(self.proton_nvapi)
        proton_form.addRow("VKD3D_CONFIG", self.proton_vkd3d)
        controls_layout.addWidget(proton_card)

        self.lsfg_disable_check = QCheckBox("Desativar lsfg-vk neste jogo (DISABLE_LSFGVK)")
        _set_icon(self.lsfg_disable_check, "disable")
        self.lsfg_disable_check.setProperty("accent", "neutral")
        controls_layout.addWidget(self.lsfg_disable_check)

        lsfg_card = Card(ICONS["lsfg"], "lsfg-vk", tag="Lossless Scaling", checkable=True)
        self.lsfg_card = lsfg_card
        self.lsfg_box = lsfg_card.switch
        lsfg_form = lsfg_card.form
        lsfg_hint = QLabel(
            "Requer lsfg-vk instalado a parte e o Lossless Scaling na sua"
            " biblioteca Steam (fornece a Lossless.dll)."
        )
        lsfg_hint.setObjectName("cardHint")
        lsfg_hint.setWordWrap(True)
        lsfg_form.addRow(lsfg_hint)
        self.lsfg_profile = QLineEdit()
        self.lsfg_profile.setPlaceholderText("nome do perfil no conf.toml (opcional)")
        self.lsfg_multiplier_group, lsfg_multiplier_row = _make_segmented(self, LSFG_MULTIPLIERS)
        self.lsfg_flow_scale = QLineEdit()
        self.lsfg_flow_scale.setPlaceholderText("0.25 a 1.0 (opcional)")
        self.lsfg_performance_mode = QCheckBox("Modo desempenho (mais leve)")
        _set_icon(self.lsfg_performance_mode, "bolt")
        self.lsfg_performance_mode.setProperty("accent", "teal")
        lsfg_form.addRow("Perfil (LSFGVK_PROFILE)", self.lsfg_profile)
        lsfg_form.addRow("Multiplicador de frames", lsfg_multiplier_row)
        lsfg_form.addRow("Flow scale", self.lsfg_flow_scale)
        lsfg_form.addRow(self.lsfg_performance_mode)
        controls_layout.addWidget(lsfg_card)

        extra_form = QFormLayout()
        self.extra_edit = QLineEdit()
        self.extra_edit.setPlaceholderText("outras opcoes/env vars, ex: PROTON_LOG=1")
        extra_form.addRow("Opcoes extras", self.extra_edit)
        controls_layout.addLayout(extra_form)

        layout.addWidget(self.controls)

        layout.addWidget(QLabel("Launch Options resultante"))
        self.preview = QLabel()
        self.preview.setObjectName("cmdPreview")
        self.preview.setTextFormat(Qt.RichText)
        self.preview.setWordWrap(True)
        self.preview.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._preview_text = ""
        layout.addWidget(self.preview)

        btn_row = QHBoxLayout()
        self.apply_btn = QPushButton("Aplicar a este jogo")
        self.apply_btn.setProperty("role", "primary")
        self.apply_btn.clicked.connect(self._apply)
        self.revert_btn = QPushButton("Reverter")
        self.revert_btn.clicked.connect(self._revert)
        btn_row.addWidget(self.apply_btn)
        btn_row.addWidget(self.revert_btn)
        layout.addLayout(btn_row)

        layout.addStretch(1)

        for w in (
            self.gamemode_check,
            self.mangohud_check,
            self.gamescope_box,
            self.gs_render_width,
            self.gs_render_height,
            self.gs_width,
            self.gs_height,
            self.gs_refresh,
            self.gs_fullscreen,
            self.gs_borderless,
            self.gs_grab,
            self.gs_force_grab_cursor,
            self.gs_steam,
            self.gs_adaptive_sync,
            self.gs_framerate_limit,
            self.gs_extra,
            self.proton_no_esync,
            self.proton_no_fsync,
            self.proton_nvapi,
            self.proton_vkd3d,
            self.lsfg_disable_check,
            self.lsfg_box,
            self.lsfg_profile,
            self.lsfg_flow_scale,
            self.lsfg_performance_mode,
            self.extra_edit,
        ):
            sig = getattr(w, "toggled", None) or getattr(w, "textChanged", None)
            sig.connect(self._refresh_preview)
        self.gs_filter_group.buttonToggled.connect(self._refresh_preview)
        self.gs_scaler_group.buttonToggled.connect(self._refresh_preview)
        self.lsfg_multiplier_group.buttonToggled.connect(self._refresh_preview)

        # Preencher qualquer campo do gamescope (ou ligar um dos toggles dele)
        # liga sozinho o switch mestre do card — sem isso, os valores digitados
        # ficam guardados na tela mas nunca entram nas Launch Options, porque o
        # gamescope inteiro so e montado quando esse switch esta marcado.
        for field in (
            self.gs_render_width,
            self.gs_render_height,
            self.gs_width,
            self.gs_height,
            self.gs_refresh,
            self.gs_framerate_limit,
            self.gs_extra,
        ):
            field.textChanged.connect(self._auto_enable_gamescope_on_text)
        for check in (
            self.gs_fullscreen,
            self.gs_borderless,
            self.gs_grab,
            self.gs_force_grab_cursor,
            self.gs_steam,
            self.gs_adaptive_sync,
        ):
            check.toggled.connect(self._auto_enable_gamescope_on_bool)
        self.gs_filter_group.buttonToggled.connect(self._auto_enable_gamescope_on_filter)
        self.gs_scaler_group.buttonToggled.connect(self._auto_enable_gamescope_on_filter)

        # Mesma logica do gamescope: preencher um campo do lsfg-vk liga
        # sozinho o switch mestre do card (sem isso o LSFGVK_ENV=1 nunca
        # seria emitido e os valores digitados nao teriam efeito nenhum).
        for field in (self.lsfg_profile, self.lsfg_flow_scale):
            field.textChanged.connect(self._auto_enable_lsfg_on_text)
        self.lsfg_performance_mode.toggled.connect(self._auto_enable_lsfg_on_bool)
        self.lsfg_multiplier_group.buttonToggled.connect(self._auto_enable_lsfg_on_filter)

        self.set_game(None)

    def _build_resolution_mapper(self):
        """Bloco visual com resolucao interna -> seta -> resolucao de
        saida, no lugar de quatro campos soltos sem relacao visual."""
        box = QWidget()
        box.setObjectName("resMapper")
        row = QHBoxLayout(box)
        row.setContentsMargins(14, 12, 14, 12)
        row.setSpacing(14)

        for edit in (self.gs_render_width, self.gs_render_height, self.gs_width, self.gs_height):
            edit.setFixedWidth(64)
            edit.setAlignment(Qt.AlignCenter)

        def pair_col(label_text, w_edit, h_edit):
            col = QVBoxLayout()
            col.setSpacing(6)
            label = QLabel(label_text)
            label.setObjectName("miniLabel")
            col.addWidget(label)
            pair = QHBoxLayout()
            pair.setSpacing(6)
            pair.addWidget(w_edit)
            times = QLabel("×")
            times.setObjectName("miniLabel")
            pair.addWidget(times)
            pair.addWidget(h_edit)
            col.addLayout(pair)
            return col

        row.addLayout(pair_col("Interna (render)", self.gs_render_width, self.gs_render_height))

        arrow_col = QVBoxLayout()
        arrow_col.setSpacing(3)
        arrow_icon = QLabel()
        arrow_icon.setPixmap(_svg_pixmap(ICONS["arrow"], theme.TEXT_FAINT))
        arrow_col.addWidget(arrow_icon, alignment=Qt.AlignHCenter)
        arrow_text = QLabel("upscale")
        arrow_text.setObjectName("miniLabel")
        arrow_col.addWidget(arrow_text, alignment=Qt.AlignHCenter)
        row.addLayout(arrow_col)

        row.addLayout(pair_col("Saida (tela)", self.gs_width, self.gs_height))
        row.addStretch(1)
        return box

    def _auto_enable_gamescope(self):
        if not self.gamescope_box.isChecked():
            self.gamescope_box.setChecked(True)

    def _auto_enable_gamescope_on_text(self, text):
        if text.strip():
            self._auto_enable_gamescope()

    def _auto_enable_gamescope_on_bool(self, checked):
        if checked:
            self._auto_enable_gamescope()

    def _auto_enable_gamescope_on_filter(self, button, checked):
        if checked and button.property("value"):
            self._auto_enable_gamescope()

    def _auto_enable_lsfg(self):
        if not self.lsfg_box.isChecked():
            self.lsfg_box.setChecked(True)

    def _auto_enable_lsfg_on_text(self, text):
        if text.strip():
            self._auto_enable_lsfg()

    def _auto_enable_lsfg_on_bool(self, checked):
        if checked:
            self._auto_enable_lsfg()

    def _auto_enable_lsfg_on_filter(self, button, checked):
        if checked and button.property("value"):
            self._auto_enable_lsfg()

    def _on_managed_toggled(self, checked):
        self.controls.setEnabled(not checked)
        self.apply_btn.setEnabled(not checked)
        if self.game:
            self.game["excluded"] = checked
            self._refresh_preview()
            self.on_apply(self.game)

    def set_game(self, game):
        self.game = game
        has_game = game is not None
        self.managed_check.setEnabled(has_game)
        self.controls.setEnabled(has_game and not (game and game["excluded"]))
        self.apply_btn.setEnabled(has_game and not (game and game["excluded"]))
        self.revert_btn.setEnabled(has_game)

        if not has_game:
            self.title.setText("Selecione um jogo na lista")
            self._preview_text = ""
            self.preview.setText("")
            return

        self.title.setText(f'{game["name"]}  (appid {game["appid"]})')
        self._load_from_game()

    def _load_from_game(self):
        game = self.game
        raw = core.find(game["value"], "LaunchOptions") or ""
        parsed, _suffix = core.parse_launch_options(raw)

        self.managed_check.blockSignals(True)
        self.managed_check.setChecked(game["excluded"])
        self.managed_check.blockSignals(False)

        self.gamemode_check.setChecked(parsed["gamemode"])
        self.mangohud_check.setChecked(parsed["mangohud"])

        gs = parsed["gamescope"]
        self.gamescope_box.setChecked(bool(gs))
        self.gs_render_width.setText(gs["render_width"] if gs else "")
        self.gs_render_height.setText(gs["render_height"] if gs else "")
        self.gs_width.setText(gs["width"] if gs else "")
        self.gs_height.setText(gs["height"] if gs else "")
        self.gs_refresh.setText(gs["refresh"] if gs else "")
        _set_segmented_value(self.gs_filter_group, gs["filter"] if gs else "")
        _set_segmented_value(self.gs_scaler_group, gs["scaler"] if gs else "")
        self.gs_fullscreen.setChecked(bool(gs and gs["fullscreen"]))
        self.gs_borderless.setChecked(bool(gs and gs["borderless"]))
        self.gs_grab.setChecked(bool(gs and gs["grab"]))
        self.gs_force_grab_cursor.setChecked(bool(gs and gs["force_grab_cursor"]))
        self.gs_steam.setChecked(bool(gs and gs["steam"]))
        self.gs_adaptive_sync.setChecked(bool(gs and gs["adaptive_sync"]))
        self.gs_framerate_limit.setText(gs["framerate_limit"] if gs else "")
        self.gs_extra.setText(gs["extra"] if gs else "")

        proton = parsed["proton"]
        self.proton_no_esync.setChecked(proton["no_esync"])
        self.proton_no_fsync.setChecked(proton["no_fsync"])
        self.proton_nvapi.setChecked(proton["enable_nvapi"])
        self.proton_vkd3d.setText(proton["vkd3d_config"])

        lsfg = parsed["lsfg"]
        self.lsfg_disable_check.setChecked(lsfg["disable"])
        lsfg_active = bool(
            lsfg["profile"] or lsfg["multiplier"] or lsfg["flow_scale"] or lsfg["performance_mode"]
        )
        self.lsfg_box.setChecked(lsfg_active)
        self.lsfg_profile.setText(lsfg["profile"])
        _set_segmented_value(self.lsfg_multiplier_group, lsfg["multiplier"])
        self.lsfg_flow_scale.setText(lsfg["flow_scale"])
        self.lsfg_performance_mode.setChecked(lsfg["performance_mode"])

        self.extra_edit.setText(parsed["extra"])

        self.controls.setEnabled(not game["excluded"])
        self._refresh_preview()

    def _current_gamescope_dict(self):
        if not self.gamescope_box.isChecked():
            return None
        return {
            "enabled": True,
            "render_width": self.gs_render_width.text().strip(),
            "render_height": self.gs_render_height.text().strip(),
            "width": self.gs_width.text().strip(),
            "height": self.gs_height.text().strip(),
            "refresh": self.gs_refresh.text().strip(),
            "filter": _segmented_value(self.gs_filter_group),
            "scaler": _segmented_value(self.gs_scaler_group),
            "fullscreen": self.gs_fullscreen.isChecked(),
            "borderless": self.gs_borderless.isChecked(),
            "grab": self.gs_grab.isChecked(),
            "force_grab_cursor": self.gs_force_grab_cursor.isChecked(),
            "steam": self.gs_steam.isChecked(),
            "adaptive_sync": self.gs_adaptive_sync.isChecked(),
            "framerate_limit": self.gs_framerate_limit.text().strip(),
            "extra": self.gs_extra.text().strip(),
        }

    def _current_proton_dict(self):
        return {
            "no_esync": self.proton_no_esync.isChecked(),
            "no_fsync": self.proton_no_fsync.isChecked(),
            "enable_nvapi": self.proton_nvapi.isChecked(),
            "vkd3d_config": self.proton_vkd3d.text().strip(),
        }

    def _current_lsfg_dict(self):
        disable = self.lsfg_disable_check.isChecked()
        if not self.lsfg_box.isChecked():
            return {"disable": disable} if disable else None
        return {
            "disable": disable,
            "profile": self.lsfg_profile.text().strip(),
            "multiplier": _segmented_value(self.lsfg_multiplier_group),
            "flow_scale": self.lsfg_flow_scale.text().strip(),
            "performance_mode": self.lsfg_performance_mode.isChecked(),
        }

    def _refresh_preview(self, *_):
        if not self.game:
            return
        proton = self._current_proton_dict()
        lsfg = self._current_lsfg_dict()
        new = core.build_launch_options(
            self.gamemode_check.isChecked(),
            self.mangohud_check.isChecked(),
            self._current_gamescope_dict(),
            self.extra_edit.text().strip(),
            proton=proton,
            lsfg=lsfg,
        )
        self._preview_text = new
        self.preview.setText(theme.colorize_command(new))

        proton_active = sum(
            [proton["no_esync"], proton["no_fsync"], proton["enable_nvapi"], bool(proton["vkd3d_config"])]
        )
        self.proton_card.set_badge(
            f"{proton_active} ativa{'s' if proton_active != 1 else ''}" if proton_active else ""
        )

        self.gamescope_card.set_badge("ativo" if self.gamescope_box.isChecked() else "")

        if self.lsfg_box.isChecked():
            lsfg_active = sum(
                [
                    bool(self.lsfg_profile.text().strip()),
                    bool(_segmented_value(self.lsfg_multiplier_group)),
                    bool(self.lsfg_flow_scale.text().strip()),
                    self.lsfg_performance_mode.isChecked(),
                ]
            )
        else:
            lsfg_active = 0
        self.lsfg_card.set_badge(f"{lsfg_active} ativa{'s' if lsfg_active != 1 else ''}" if lsfg_active else "")

    def _apply(self):
        if not self.game:
            return
        new = self._preview_text
        core.set_value(self.game["value"], "LaunchOptions", new)
        self.game["dirty"] = True
        self.on_apply(self.game)

    def _revert(self):
        if not self.game:
            return
        self._load_from_game()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GBSteamParams — gamemode / mangohud / gamescope")
        self.setWindowIcon(QIcon(str(ICON_PATH)))
        self.resize(1100, 680)

        self.root = core.steam_root()
        if not self.root:
            QMessageBox.critical(self, "Steam nao encontrada",
                                  "Nao encontrei ~/.local/share/Steam nem ~/.steam/steam.")
            sys.exit(1)

        configs = core.config_paths(self.root)
        if not configs:
            QMessageBox.critical(self, "Perfil nao encontrado",
                                  "Nenhum localconfig.vdf em userdata/*/config/.")
            sys.exit(1)
        self.cfg_path = configs[0]

        self.names = core.appid_name_map(self.root)
        self.excluded = core.load_exclude_list()

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        status_row = QHBoxLayout()
        self.status_path_label = QLabel()
        self.status_path_label.setObjectName("statusPath")
        status_row.addWidget(self.status_path_label, 1)

        self.status_pill = QWidget()
        self.status_pill.setObjectName("statusPill")
        pill_row = QHBoxLayout(self.status_pill)
        pill_row.setContentsMargins(10, 4, 10, 4)
        pill_row.setSpacing(7)
        self.status_dot = QLabel()
        self.status_dot.setObjectName("statusDot")
        self.status_dot.setFixedSize(8, 8)
        self.status_pill_text = QLabel()
        self.status_pill_text.setObjectName("statusPillText")
        pill_row.addWidget(self.status_dot)
        pill_row.addWidget(self.status_pill_text)
        status_row.addWidget(self.status_pill)
        main_layout.addLayout(status_row)

        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter, 1)

        games_panel = QWidget()
        games_panel_layout = QVBoxLayout(games_panel)
        games_panel_layout.setContentsMargins(14, 12, 14, 8)
        games_panel_layout.setSpacing(8)

        library_header = QHBoxLayout()
        library_title = QLabel("Biblioteca")
        library_title.setObjectName("libraryTitle")
        library_header.addWidget(library_title)
        self.library_count = QLabel("")
        self.library_count.setObjectName("libraryCount")
        library_header.addWidget(self.library_count)
        library_header.addStretch(1)
        games_panel_layout.addLayout(library_header)

        self.games_list = QListWidget()
        self.games_list.setSelectionMode(QListWidget.SingleSelection)
        self.games_list.setEditTriggers(QListWidget.NoEditTriggers)
        self.games_list.setSpacing(2)
        self.games_list.itemSelectionChanged.connect(self._on_row_selected)
        games_panel_layout.addWidget(self.games_list, 1)
        splitter.addWidget(games_panel)

        self.detail = DetailPanel(on_apply=self._on_game_applied)
        splitter.addWidget(self.detail)
        splitter.setSizes([550, 550])

        bottom = QHBoxLayout()
        self.reload_btn = QPushButton("Recarregar")
        self.reload_btn.clicked.connect(self.load_games)
        self.bulk_btn = QPushButton("Aplicar gamemode+mangohud a todos (nao gerenciados)")
        self.bulk_btn.clicked.connect(self._apply_bulk_default)
        self.save_btn = QPushButton("Salvar alteracoes")
        self.save_btn.setProperty("role", "primary")
        self.save_btn.clicked.connect(self._save)
        bottom.addWidget(self.reload_btn)
        bottom.addWidget(self.bulk_btn)
        bottom.addStretch(1)
        bottom.addWidget(self.save_btn)
        main_layout.addLayout(bottom)

        self.games = []
        self.root_pairs = None
        self.load_games()

    # -----------------------------------------------------------------
    def _update_status(self):
        running = core.is_steam_running()
        state = "warn" if running else "ok"
        theme.set_widget_state(self.status_pill, state)
        theme.set_widget_state(self.status_dot, state)
        theme.set_widget_state(self.status_pill_text, state)
        self.status_pill_text.setText(
            "Steam ABERTA — feche antes de salvar" if running else "Steam fechada — seguro para salvar"
        )
        self.status_path_label.setText(str(self.cfg_path))

    def load_games(self):
        text = open(self.cfg_path, encoding="utf-8", errors="replace").read()
        self.root_pairs = core.parse_vdf(text)
        apps = core.apps_section(self.root_pairs)
        if apps is None:
            QMessageBox.critical(self, "Erro", "Secao Software/Valve/Steam/apps nao encontrada.")
            return

        self.games = []
        for appid, value in apps:
            if not isinstance(value, list):
                continue
            name = self.names.get(appid, "")
            if not name:
                # sem entrada em appid_name_map = jogo nao instalado
                # (nenhum appmanifest_<appid>.acf em nenhuma library)
                continue
            if core.SKIP_NAME_RE.search(name):
                continue
            self.games.append({
                "appid": appid,
                "name": name,
                "value": value,
                "excluded": appid in self.excluded,
                "dirty": False,
            })
        self.games.sort(key=lambda g: g["name"].lower())

        self._refresh_games_list()
        self.games_list.setCurrentRow(-1)
        self._update_status()
        self.detail.set_game(None)

    def _refresh_games_list(self):
        self.games_list.clear()
        self.library_count.setText(f"{len(self.games)} jogos")
        for game in self.games:
            chips, meta = summary_chips_for(game["value"], game["appid"], self.excluded)
            row_widget = GameRowWidget(game["name"], game["appid"], chips, meta)
            item = QListWidgetItem()
            item.setSizeHint(row_widget.sizeHint())
            self.games_list.addItem(item)
            self.games_list.setItemWidget(item, row_widget)

    def _flush_detail(self):
        """Grava no jogo selecionado o que esta no painel, mesmo sem clicar
        em 'Aplicar a este jogo' — evita perder edicoes ao trocar de jogo
        ou salvar."""
        game = self.detail.game
        if game and not game["excluded"]:
            self.detail._apply()

    def _on_row_selected(self):
        self._flush_detail()
        row = self.games_list.currentRow()
        if row < 0:
            self.detail.set_game(None)
            return
        game = self.games[row]
        self.detail.set_game(game)

    def _on_game_applied(self, game):
        if game["excluded"]:
            self.excluded.add(game["appid"])
        else:
            self.excluded.discard(game["appid"])
        row = self.games.index(game)
        self._refresh_games_list()
        self.games_list.blockSignals(True)
        self.games_list.setCurrentRow(row)
        self.games_list.blockSignals(False)

    def _apply_bulk_default(self):
        count = 0
        for game in self.games:
            if game["excluded"]:
                continue
            old = core.find(game["value"], "LaunchOptions") or ""
            new = core.merge_launch_options(old)
            if new != old:
                core.set_value(game["value"], "LaunchOptions", new)
                game["dirty"] = True
                count += 1
        current_game = self.detail.game
        self._refresh_games_list()
        if current_game:
            self.games_list.blockSignals(True)
            self.games_list.setCurrentRow(self.games.index(current_game))
            self.games_list.blockSignals(False)
            self.detail._load_from_game()
        QMessageBox.information(self, "Aplicado", f"{count} jogo(s) atualizado(s) com gamemode+mangohud.")

    def _save(self):
        self._flush_detail()
        if core.is_steam_running():
            resp = QMessageBox.warning(
                self, "Steam aberta",
                "A Steam esta aberta e pode sobrescrever o arquivo ao fechar.\n\n"
                "Fechar a Steam agora antes de salvar?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            )
            if resp == QMessageBox.Cancel:
                return
            if resp == QMessageBox.Yes:
                subprocess.Popen(["steam", "-shutdown"])
                QMessageBox.information(self, "Aguarde", "Pedido de fechamento enviado. Clique em Salvar de novo em alguns segundos.")
                return

        backup = core.backup_and_save(self.cfg_path, self.root_pairs)
        core.save_exclude_list(self.excluded)
        for game in self.games:
            game["dirty"] = False
        QMessageBox.information(
            self, "Salvo",
            f"Alteracoes gravadas.\nBackup: {backup}\n\nAbra a Steam para os jogos pegarem as novas opcoes.",
        )
        self._update_status()


def main():
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(str(ICON_PATH)))
    app.setStyleSheet(theme.STYLESHEET)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
