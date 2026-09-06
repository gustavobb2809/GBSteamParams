#!/usr/bin/env python3
"""
steam-boost-gui — app de mesa (PySide6) para configurar visualmente
gamemode, mangohud e gamescope nas Launch Options de cada jogo da Steam.
"""
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
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


def summary_for(value_pairs, appid, excluded):
    if appid in excluded:
        return "gerenciado manualmente"
    raw = core.find(value_pairs, "LaunchOptions") or ""
    if not raw:
        return "— (padrao da Steam)"
    parsed, _ = core.parse_launch_options(raw)
    parts = []
    if parsed["gamemode"]:
        parts.append("gamemode")
    if parsed["mangohud"]:
        parts.append("mangohud")
    if parsed["gamescope"]:
        parts.append("gamescope")
    if parsed["extra"]:
        parts.append("extra")
    return " + ".join(parts) if parts else "customizado"


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
        self.managed_check.setProperty("accent", "neutral")
        self.managed_check.toggled.connect(self._on_managed_toggled)
        layout.addWidget(self.managed_check)

        self.controls = QWidget()
        controls_layout = QVBoxLayout(self.controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)

        self.gamemode_check = QCheckBox("gamemode (gamemoderun)")
        self.mangohud_check = QCheckBox("MangoHud (overlay de desempenho)")
        controls_layout.addWidget(self.gamemode_check)
        controls_layout.addWidget(self.mangohud_check)

        self.gamescope_box = QGroupBox("gamescope")
        self.gamescope_box.setCheckable(True)
        gs_form = QFormLayout(self.gamescope_box)
        self.gs_render_width = QLineEdit()
        self.gs_render_width.setPlaceholderText("ex: 1280 (renderiza menor, upscale p/ Largura)")
        self.gs_render_height = QLineEdit()
        self.gs_render_height.setPlaceholderText("ex: 800 (opcional)")
        self.gs_width = QLineEdit()
        self.gs_width.setPlaceholderText("ex: 2560")
        self.gs_height = QLineEdit()
        self.gs_height.setPlaceholderText("ex: 1440")
        self.gs_refresh = QLineEdit()
        self.gs_refresh.setPlaceholderText("ex: 165 (opcional)")

        self.gs_filter_group, filter_row = _make_segmented(self, GAMESCOPE_FILTERS)
        self.gs_scaler_group, scaler_row = _make_segmented(self, GAMESCOPE_SCALERS)

        self.gs_fullscreen = QCheckBox("Tela cheia (-f)")
        self.gs_fullscreen.setProperty("accent", "teal")
        self.gs_borderless = QCheckBox("Sem bordas (-b)")
        self.gs_borderless.setProperty("accent", "teal")
        self.gs_grab = QCheckBox("Capturar teclado (-g)")
        self.gs_grab.setProperty("accent", "teal")
        self.gs_force_grab_cursor = QCheckBox("Prender o cursor / mouse relativo (--force-grab-cursor)")
        self.gs_force_grab_cursor.setProperty("accent", "teal")
        self.gs_steam = QCheckBox("Integracao com overlay da Steam (-e)")
        self.gs_steam.setProperty("accent", "teal")
        self.gs_adaptive_sync = QCheckBox("Adaptive Sync / VRR (--adaptive-sync)")
        self.gs_adaptive_sync.setProperty("accent", "teal")
        self.gs_framerate_limit = QLineEdit()
        self.gs_framerate_limit.setPlaceholderText("ex: 60 (opcional)")
        self.gs_extra = QLineEdit()
        self.gs_extra.setPlaceholderText("flags extras do gamescope (opcional)")
        gs_form.addRow("Resolucao interna (largura)", self.gs_render_width)
        gs_form.addRow("Resolucao interna (altura)", self.gs_render_height)
        gs_form.addRow("Largura", self.gs_width)
        gs_form.addRow("Altura", self.gs_height)
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
        controls_layout.addWidget(self.gamescope_box)

        self.proton_box = QGroupBox()
        self._proton_box_base_title = "Proton / Wine (avancado)"
        self.proton_box.setTitle(self._proton_box_base_title)
        proton_form = QFormLayout(self.proton_box)
        self.proton_no_esync = QCheckBox("Desativar ESync (PROTON_NO_ESYNC)")
        self.proton_no_esync.setProperty("accent", "teal")
        self.proton_no_fsync = QCheckBox("Desativar FSync (PROTON_NO_FSYNC)")
        self.proton_no_fsync.setProperty("accent", "teal")
        self.proton_nvapi = QCheckBox("Habilitar NVAPI / DLSS (PROTON_ENABLE_NVAPI)")
        self.proton_nvapi.setProperty("accent", "teal")
        self.proton_vkd3d = QLineEdit()
        self.proton_vkd3d.setPlaceholderText("ex: dxr,dxr11 (ray tracing DX12, opcional)")
        proton_form.addRow(self.proton_no_esync)
        proton_form.addRow(self.proton_no_fsync)
        proton_form.addRow(self.proton_nvapi)
        proton_form.addRow("VKD3D_CONFIG", self.proton_vkd3d)
        controls_layout.addWidget(self.proton_box)

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
            self.extra_edit,
        ):
            sig = getattr(w, "toggled", None) or getattr(w, "textChanged", None)
            sig.connect(self._refresh_preview)
        self.gs_filter_group.buttonToggled.connect(self._refresh_preview)
        self.gs_scaler_group.buttonToggled.connect(self._refresh_preview)

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

        self.set_game(None)

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

    def _refresh_preview(self, *_):
        if not self.game:
            return
        proton = self._current_proton_dict()
        new = core.build_launch_options(
            self.gamemode_check.isChecked(),
            self.mangohud_check.isChecked(),
            self._current_gamescope_dict(),
            self.extra_edit.text().strip(),
            proton=proton,
        )
        self._preview_text = new
        self.preview.setText(theme.colorize_command(new))

        active = sum([proton["no_esync"], proton["no_fsync"], proton["enable_nvapi"], bool(proton["vkd3d_config"])])
        title = self._proton_box_base_title
        if active:
            title += f" — {active} ativa{'s' if active != 1 else ''}"
        self.proton_box.setTitle(title)

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
        self.resize(1000, 600)

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

        self.status_label = QLabel()
        main_layout.addWidget(self.status_label)

        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter, 1)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Jogo", "AppID", "Opcoes"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._on_row_selected)
        splitter.addWidget(self.table)

        self.detail = DetailPanel(on_apply=self._on_game_applied)
        splitter.addWidget(self.detail)
        splitter.setSizes([550, 450])

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
    def _steam_status_text(self):
        running = core.is_steam_running()
        return (
            "Steam ABERTA — feche antes de salvar para evitar que ela sobrescreva o arquivo."
            if running
            else "Steam fechada — seguro para salvar."
        )

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
            if core.SKIP_NAME_RE.search(name):
                continue
            self.games.append({
                "appid": appid,
                "name": name or "(sem nome conhecido)",
                "value": value,
                "excluded": appid in self.excluded,
                "dirty": False,
            })
        self.games.sort(key=lambda g: (g["name"].startswith("("), g["name"].lower()))

        self._refresh_table()
        self.status_label.setText(f"{self.cfg_path}  —  {self._steam_status_text()}")
        self.detail.set_game(None)

    def _refresh_table(self):
        self.table.setRowCount(len(self.games))
        for row, game in enumerate(self.games):
            self.table.setItem(row, 0, QTableWidgetItem(game["name"]))
            self.table.setItem(row, 1, QTableWidgetItem(game["appid"]))
            self.table.setItem(
                row, 2, QTableWidgetItem(summary_for(game["value"], game["appid"], self.excluded))
            )

    def _flush_detail(self):
        """Grava no jogo selecionado o que esta no painel, mesmo sem clicar
        em 'Aplicar a este jogo' — evita perder edicoes ao trocar de jogo
        ou salvar."""
        game = self.detail.game
        if game and not game["excluded"]:
            self.detail._apply()

    def _on_row_selected(self):
        self._flush_detail()
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            self.detail.set_game(None)
            return
        game = self.games[rows[0].row()]
        self.detail.set_game(game)

    def _on_game_applied(self, game):
        if game["excluded"]:
            self.excluded.add(game["appid"])
        else:
            self.excluded.discard(game["appid"])
        row = self.games.index(game)
        self.table.item(row, 2).setText(summary_for(game["value"], game["appid"], self.excluded))

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
        self._refresh_table()
        if self.detail.game:
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
        self.status_label.setText(f"{self.cfg_path}  —  {self._steam_status_text()}")


def main():
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(str(ICON_PATH)))
    app.setStyleSheet(theme.STYLESHEET)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
