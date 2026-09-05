#!/usr/bin/env python3
"""
steam-boost — aplica gamemoderun + mangohud nas Launch Options de todos os
jogos da Steam (edita localconfig.vdf) e confere se gamemode/mangohud/ntsync
estao prontos no sistema.

Uso:
    steam-boost [--dry-run] [--yes]

    --dry-run   mostra o que mudaria, sem gravar nada
    --yes       nao pede confirmacao (ex: continuar com a Steam aberta)

Jogos com opcoes configuradas manualmente (ex: gamescope) devem entrar em
~/.config/steam-boost/exclude.txt para o steam-boost nunca mexer neles —
veja steam-boost-gui para configurar isso visualmente.
"""
import subprocess
import sys

from gbsteamparams import core


def check_system():
    print("== Checagem do sistema ==")
    if core.which("gamemoderun"):
        print("  [ok] gamemode instalado")
    else:
        print("  [FALTA] gamemode nao encontrado -> sudo dnf install -y gamemode")
    if core.which("mangohud"):
        print("  [ok] mangohud instalado")
    else:
        print("  [FALTA] mangohud nao encontrado -> sudo dnf install -y mangohud")
    try:
        lsmod = subprocess.run(["lsmod"], capture_output=True, text=True).stdout
        if "ntsync" in lsmod:
            print("  [ok] modulo ntsync carregado (auto-carrega no boot via kernel-modules-core)")
        else:
            print("  [FALTA] modulo ntsync nao carregado -> sudo modprobe ntsync")
    except FileNotFoundError:
        pass
    print(
        "  (ntsync nao tem 'launch option': basta o modulo estar carregado e usar"
        " Proton Experimental / Proton 9+ / GE-Proton, que o detectam sozinhos)"
    )
    print()


def main():
    dry_run = "--dry-run" in sys.argv
    auto_yes = "--yes" in sys.argv

    check_system()

    root = core.steam_root()
    if not root:
        sys.exit("Nao encontrei a instalacao da Steam (~/.local/share/Steam ou ~/.steam/steam).")

    configs = core.config_paths(root)
    if not configs:
        sys.exit("Nenhum localconfig.vdf encontrado em userdata/*/config/.")

    if core.is_steam_running() and not auto_yes:
        resp = input(
            "A Steam parece estar aberta. Editar agora e arriscado: ela pode "
            "sobrescrever o arquivo ao sair.\nFeche a Steam e rode de novo, ou "
            "digite 'continuar' para prosseguir mesmo assim: "
        )
        if resp.strip().lower() not in ("continuar", "yes", "y", "s"):
            sys.exit("Cancelado. Feche a Steam e rode novamente.")

    names = core.appid_name_map(root)
    excluded = core.load_exclude_list()
    if excluded:
        print(f"Ignorando appids da lista de exclusao ({core.EXCLUDE_FILE}): {', '.join(sorted(excluded))}\n")

    for cfg_path in configs:
        print(f"== {cfg_path} ==")
        text = open(cfg_path, encoding="utf-8", errors="replace").read()
        root_pairs = core.parse_vdf(text)
        if not root_pairs:
            print("  arquivo vazio/ilegivel, pulando")
            continue

        apps = core.apps_section(root_pairs)
        if apps is None:
            print("  secao Software/Valve/Steam/apps nao encontrada, pulando")
            continue

        changes = []
        for appid, value in apps:
            if not isinstance(value, list):
                continue
            if appid in excluded:
                continue
            name = names.get(appid, "")
            if core.SKIP_NAME_RE.search(name):
                continue
            old = core.find(value, "LaunchOptions") or ""
            new = core.merge_launch_options(old)
            if new != old:
                changes.append((appid, name or "(sem nome conhecido)", old, new))
                if not dry_run:
                    core.set_value(value, "LaunchOptions", new)

        if not changes:
            print("  nada para mudar (todos os jogos ja estao com gamemoderun+mangohud)")
            continue

        print(f"  {len(changes)} jogo(s) atualizado(s):")
        for appid, name, old, new in changes:
            print(f"    [{appid}] {name}")
            print(f"        antes: {old or '(vazio)'}")
            print(f"        depois: {new}")

        if dry_run:
            print("  (--dry-run: nada foi gravado)")
            continue

        backup = core.backup_and_save(cfg_path, root_pairs)
        print(f"  backup salvo em {backup}")
        print("  gravado.")

    print("\nPronto. Abra a Steam (ou reabra, se ja estava aberta) para os jogos"
          " pegarem as novas opcoes de lancamento.")


if __name__ == "__main__":
    main()
