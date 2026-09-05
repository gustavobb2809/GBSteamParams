#!/usr/bin/env python3
"""
steam-boost-gui — app de mesa (PySide6) para configurar visualmente
gamemode, mangohud e gamescope nas Launch Options de cada jogo da Steam.
"""
import subprocess
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
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

from gbsteamparams import core


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
        self.title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self.title)

        self.managed_check = QCheckBox("Gerenciado manualmente (steam-boost nao mexe)")
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
        self.gs_width = QLineEdit()
        self.gs_width.setPlaceholderText("ex: 2560")
        self.gs_height = QLineEdit()
        self.gs_height.setPlaceholderText("ex: 1440")
        self.gs_refresh = QLineEdit()
        self.gs_refresh.setPlaceholderText("ex: 165 (opcional)")
        self.gs_fullscreen = QCheckBox("Tela cheia (-f)")
        self.gs_borderless = QCheckBox("Sem bordas (-b)")
        self.gs_extra = QLineEdit()
        self.gs_extra.setPlaceholderText("flags extras do gamescope (opcional)")
        gs_form.addRow("Largura", self.gs_width)
        gs_form.addRow("Altura", self.gs_height)
        gs_form.addRow("Taxa de atualizacao", self.gs_refresh)
        gs_form.addRow(self.gs_fullscreen)
        gs_form.addRow(self.gs_borderless)
        gs_form.addRow("Extra", self.gs_extra)
        controls_layout.addWidget(self.gamescope_box)

        extra_form = QFormLayout()
        self.extra_edit = QLineEdit()
        self.extra_edit.setPlaceholderText("outras opcoes/env vars, ex: PROTON_LOG=1")
        extra_form.addRow("Opcoes extras", self.extra_edit)
        controls_layout.addLayout(extra_form)

        layout.addWidget(self.controls)

        preview_form = QFormLayout()
        self.preview = QLineEdit()
        self.preview.setReadOnly(True)
        preview_form.addRow("Launch Options resultante", self.preview)
        layout.addLayout(preview_form)

        btn_row = QHBoxLayout()
        self.apply_btn = QPushButton("Aplicar a este jogo")
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
            self.gs_width,
            self.gs_height,
            self.gs_refresh,
            self.gs_fullscreen,
            self.gs_borderless,
            self.gs_extra,
            self.extra_edit,
        ):
            sig = getattr(w, "toggled", None) or getattr(w, "textChanged", None)
            sig.connect(self._refresh_preview)

        self.set_game(None)

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
        self.gs_width.setText(gs["width"] if gs else "")
        self.gs_height.setText(gs["height"] if gs else "")
        self.gs_refresh.setText(gs["refresh"] if gs else "")
        self.gs_fullscreen.setChecked(bool(gs and gs["fullscreen"]))
        self.gs_borderless.setChecked(bool(gs and gs["borderless"]))
        self.gs_extra.setText(gs["extra"] if gs else "")

        self.extra_edit.setText(parsed["extra"])

        self.controls.setEnabled(not game["excluded"])
        self._refresh_preview()

    def _current_gamescope_dict(self):
        if not self.gamescope_box.isChecked():
            return None
        return {
            "enabled": True,
            "width": self.gs_width.text().strip(),
            "height": self.gs_height.text().strip(),
            "refresh": self.gs_refresh.text().strip(),
            "fullscreen": self.gs_fullscreen.isChecked(),
            "borderless": self.gs_borderless.isChecked(),
            "extra": self.gs_extra.text().strip(),
        }

    def _refresh_preview(self, *_):
        if not self.game:
            return
        new = core.build_launch_options(
            self.gamemode_check.isChecked(),
            self.mangohud_check.isChecked(),
            self._current_gamescope_dict(),
            self.extra_edit.text().strip(),
        )
        self.preview.setText(new)

    def _apply(self):
        if not self.game:
            return
        new = self.preview.text()
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

    def _on_row_selected(self):
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
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
