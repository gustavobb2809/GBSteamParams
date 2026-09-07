"""
core - parser VDF (KeyValues), leitura/escrita de Launch Options
(gamemode, mangohud, gamescope) e lista de exclusao por appid.
"""
import glob
import os
import re
import shutil
import subprocess
import time

WRAPPERS = ["gamemoderun", "mangohud"]

EXCLUDE_FILE = os.path.expanduser("~/.config/steam-boost/exclude.txt")

SKIP_NAME_RE = re.compile(
    r"steam linux runtime|steamworks common redistributables|steam controller "
    r"configs|proton \d|steamvr",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# parser VDF (KeyValues) minimalista: preserva ordem, cobre o que a Steam usa
# ---------------------------------------------------------------------------
def tokenize(text):
    tokens = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if c == "{":
            tokens.append(("OPEN", "{"))
            i += 1
            continue
        if c == "}":
            tokens.append(("CLOSE", "}"))
            i += 1
            continue
        if c == '"':
            j = i + 1
            buf = []
            while j < n and text[j] != '"':
                if text[j] == "\\" and j + 1 < n:
                    buf.append(text[j + 1])
                    j += 2
                else:
                    buf.append(text[j])
                    j += 1
            tokens.append(("STR", "".join(buf)))
            i = j + 1
            continue
        j = i
        while j < n and text[j] not in " \t\r\n{}\"":
            j += 1
        tokens.append(("STR", text[i:j]))
        i = j
    return tokens


def parse_vdf(text):
    tokens = tokenize(text)
    pos = [0]

    def parse_object():
        pairs = []
        while pos[0] < len(tokens):
            ttype, _ = tokens[pos[0]]
            if ttype == "CLOSE":
                pos[0] += 1
                return pairs
            ktype, key = tokens[pos[0]]
            assert ktype == "STR", f"esperava chave, achei {tokens[pos[0]]}"
            pos[0] += 1
            ntype, nval = tokens[pos[0]]
            if ntype == "OPEN":
                pos[0] += 1
                value = parse_object()
            else:
                assert ntype == "STR"
                value = nval
                pos[0] += 1
            pairs.append([key, value])
        return pairs

    return parse_object()


def escape(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def serialize(pairs, depth=0):
    out = []
    indent = "\t" * depth
    for key, value in pairs:
        if isinstance(value, list):
            out.append(f'{indent}"{escape(key)}"\n{indent}{{\n')
            out.append(serialize(value, depth + 1))
            out.append(f"{indent}}}\n")
        else:
            out.append(f'{indent}"{escape(key)}"\t\t"{escape(value)}"\n')
    return "".join(out)


def find(pairs, key):
    for k, v in pairs:
        if k == key:
            return v
    return None


def set_value(pairs, key, value):
    for pair in pairs:
        if pair[0] == key:
            pair[1] = value
            return
    pairs.append([key, value])


# ---------------------------------------------------------------------------
# localizacao da Steam / jogos
# ---------------------------------------------------------------------------
def steam_root():
    for cand in (
        os.path.expanduser("~/.local/share/Steam"),
        os.path.expanduser("~/.steam/steam"),
    ):
        if os.path.isdir(cand):
            return cand
    return None


def find_library_paths(root):
    libs = [os.path.join(root, "steamapps")]
    lf = os.path.join(root, "steamapps", "libraryfolders.vdf")
    if os.path.isfile(lf):
        try:
            pairs = parse_vdf(open(lf, encoding="utf-8", errors="replace").read())
            root_pairs = find(pairs, "libraryfolders")
            if root_pairs:
                for _, entry in root_pairs:
                    if isinstance(entry, list):
                        path = find(entry, "path")
                        if path:
                            libs.append(os.path.join(path, "steamapps"))
        except Exception:
            pass
    return libs


def appid_name_map(root):
    names = {}
    for lib in find_library_paths(root):
        for manifest in glob.glob(os.path.join(lib, "appmanifest_*.acf")):
            m = re.search(r"appmanifest_(\d+)\.acf$", manifest)
            if not m:
                continue
            appid = m.group(1)
            try:
                text = open(manifest, encoding="utf-8", errors="replace").read()
                nm = re.search(r'"name"\s*"([^"]*)"', text)
                if nm:
                    names[appid] = nm.group(1)
            except Exception:
                pass
    return names


def config_paths(root):
    return glob.glob(os.path.join(root, "userdata", "*", "config", "localconfig.vdf"))


def apps_section(root_pairs):
    if not root_pairs:
        return None
    store = root_pairs[0][1]
    software = find(store, "Software")
    valve = find(software, "Valve") if software else None
    steam = find(valve, "Steam") if valve else None
    return find(steam, "apps") if steam else None


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def is_steam_running():
    # A propria Steam mantem esse arquivo com o PID do processo principal
    # enquanto esta rodando (mesmo truque usado por Lutris, ProtonUp etc.).
    # Nao usar "pgrep -f steam": isso faz busca por substring na linha de
    # comando inteira e da falso positivo com o proprio steam-boost-gui.
    root = steam_root()
    candidates = [os.path.expanduser("~/.steam/steam.pid")]
    if root:
        candidates.append(os.path.join(root, "steam.pid"))
    for pid_file in candidates:
        if not os.path.isfile(pid_file):
            continue
        try:
            pid = int(open(pid_file, encoding="utf-8").read().strip())
        except (ValueError, OSError):
            continue
        if _pid_alive(pid):
            return True
    try:
        out = subprocess.run(["pgrep", "-x", "steam"], capture_output=True, text=True)
        return out.returncode == 0
    except FileNotFoundError:
        return False


def which(cmd):
    return shutil.which(cmd) is not None


def backup_and_save(path, root_pairs):
    backup = f"{path}.bak-{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.copy2(path, backup)
    with open(path, "w", encoding="utf-8") as f:
        f.write(serialize(root_pairs))
    return backup


# ---------------------------------------------------------------------------
# lista de exclusao (appids que o steam-boost nao deve tocar)
# ---------------------------------------------------------------------------
def load_exclude_list():
    if not os.path.isfile(EXCLUDE_FILE):
        save_exclude_list(set())
        return set()
    excluded = set()
    with open(EXCLUDE_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.split("#", 1)[0].strip()
            if line:
                excluded.add(line)
    return excluded


def save_exclude_list(excluded):
    os.makedirs(os.path.dirname(EXCLUDE_FILE), exist_ok=True)
    with open(EXCLUDE_FILE, "w", encoding="utf-8") as f:
        f.write(
            "# appids que o steam-boost NAO deve mexer (um por linha, linhas com"
            " # sao comentario)\n"
            "# ex: jogo com gamescope configurado manualmente\n"
        )
        for appid in sorted(excluded, key=lambda x: (len(x), x)):
            f.write(f"{appid}\n")


# ---------------------------------------------------------------------------
# Launch Options: merge simples (usado pelo CLI em massa) e modelo estruturado
# (usado pela GUI, ciente do separador -- do gamescope)
# ---------------------------------------------------------------------------
def merge_launch_options(existing):
    """Garante gamemoderun+mangohud nas Launch Options, preservando o resto.
    Nao entende o separador -- do gamescope: nao usar em jogos com gamescope
    configurado (marque-os na lista de exclusao)."""
    existing = existing or ""
    if "%command%" in existing:
        prefix, suffix = existing.split("%command%", 1)
    else:
        prefix, suffix = existing, ""
    tokens = prefix.split()
    envs = [t for t in tokens if "=" in t]
    rest = [t for t in tokens if t not in envs]

    ordered = []
    for w in WRAPPERS:
        if w in rest:
            rest.remove(w)
        ordered.append(w)
    ordered.extend(rest)

    new_prefix = " ".join(envs + ordered)
    return (new_prefix + " %command%" + suffix).strip()


# env vars de Proton/Wine reconhecidas como toggles estruturados na GUI
PROTON_FLAG_VARS = {
    "PROTON_NO_ESYNC": "no_esync",
    "PROTON_NO_FSYNC": "no_fsync",
    "PROTON_ENABLE_NVAPI": "enable_nvapi",
}

# lsfg-vk (https://lsfg-vk.dev) - camada Vulkan que roda o frame
# generation do Lossless Scaling no Linux. Precisa ser instalada a parte
# (pacote da distro/AUR/build manual) e do proprio Lossless Scaling
# (appid 993090 na Steam) para fornecer a Lossless.dll.
LSFG_FLAG_VARS = {
    "DISABLE_LSFGVK": "disable",
    "LSFGVK_PERFORMANCE_MODE": "performance_mode",
}
LSFG_VALUE_VARS = {
    "LSFGVK_PROFILE": "profile",
    "LSFGVK_MULTIPLIER": "multiplier",
    "LSFGVK_FLOW_SCALE": "flow_scale",
}
# LSFGVK_ENV=1 e sempre recalculado a partir dos outros campos (ver
# build_launch_options), entao so precisa ser reconhecido e descartado
# aqui pra nao duplicar/vazar pro campo de opcoes extras.
LSFG_SKIP_VARS = {"LSFGVK_ENV"}


def parse_launch_options(s):
    """String de LaunchOptions -> dict estruturado {gamemode, mangohud,
    gamescope, proton, lsfg, extra, suffix}. gamescope e None ou dict com
    width/height/render_width/render_height/refresh/filter/scaler/
    fullscreen/borderless/grab/force_grab_cursor/steam/adaptive_sync/
    framerate_limit/extra. proton e dict com
    no_esync/no_fsync/enable_nvapi/vkd3d_config. lsfg e dict com
    disable/profile/multiplier/flow_scale/performance_mode."""
    s = s or ""
    if "%command%" in s:
        prefix, suffix = s.split("%command%", 1)
    else:
        prefix, suffix = s, ""
    tokens = prefix.split()

    if "--" in tokens:
        idx = tokens.index("--")
        outer, inner = tokens[:idx], tokens[idx + 1:]
    else:
        outer, inner = tokens, []

    result = {
        "gamemode": False,
        "mangohud": False,
        "gamescope": None,
        "proton": {
            "no_esync": False,
            "no_fsync": False,
            "enable_nvapi": False,
            "vkd3d_config": "",
        },
        "lsfg": {
            "disable": False,
            "profile": "",
            "multiplier": "",
            "flow_scale": "",
            "performance_mode": False,
        },
        "extra": "",
    }

    # env vars ficam sempre antes de qualquer wrapper, procuradas em outer
    remaining = []
    for tok in outer:
        var, _, val = tok.partition("=")
        if var in PROTON_FLAG_VARS and val == "1":
            result["proton"][PROTON_FLAG_VARS[var]] = True
        elif var == "VKD3D_CONFIG":
            result["proton"]["vkd3d_config"] = val
        elif var in LSFG_FLAG_VARS and val == "1":
            result["lsfg"][LSFG_FLAG_VARS[var]] = True
        elif var in LSFG_VALUE_VARS:
            result["lsfg"][LSFG_VALUE_VARS[var]] = val
        elif var in LSFG_SKIP_VARS:
            pass
        else:
            remaining.append(tok)
    outer = remaining

    if "gamemoderun" in outer:
        result["gamemode"] = True
        outer.remove("gamemoderun")

    if "gamescope" in outer:
        gi = outer.index("gamescope")
        gargs = outer[gi + 1:]
        outer = outer[:gi]
        gs = {
            "enabled": True,
            "width": "",
            "height": "",
            "render_width": "",
            "render_height": "",
            "refresh": "",
            "filter": "",
            "scaler": "",
            "fullscreen": False,
            "borderless": False,
            "grab": False,
            "force_grab_cursor": False,
            "steam": False,
            "adaptive_sync": False,
            "framerate_limit": "",
            "extra": "",
        }
        i = 0
        leftover = []
        while i < len(gargs):
            a = gargs[i]
            if a == "-W" and i + 1 < len(gargs):
                gs["width"] = gargs[i + 1]
                i += 2
            elif a == "-H" and i + 1 < len(gargs):
                gs["height"] = gargs[i + 1]
                i += 2
            elif a == "-w" and i + 1 < len(gargs):
                gs["render_width"] = gargs[i + 1]
                i += 2
            elif a == "-h" and i + 1 < len(gargs):
                gs["render_height"] = gargs[i + 1]
                i += 2
            elif a == "-r" and i + 1 < len(gargs):
                gs["refresh"] = gargs[i + 1]
                i += 2
            elif a == "-F" and i + 1 < len(gargs):
                gs["filter"] = gargs[i + 1]
                i += 2
            elif a == "-S" and i + 1 < len(gargs):
                gs["scaler"] = gargs[i + 1]
                i += 2
            elif a == "-f":
                gs["fullscreen"] = True
                i += 1
            elif a == "-b":
                gs["borderless"] = True
                i += 1
            elif a == "-g":
                gs["grab"] = True
                i += 1
            elif a == "--force-grab-cursor":
                gs["force_grab_cursor"] = True
                i += 1
            elif a == "-e":
                gs["steam"] = True
                i += 1
            elif a == "--adaptive-sync":
                gs["adaptive_sync"] = True
                i += 1
            elif a == "--framerate-limit" and i + 1 < len(gargs):
                gs["framerate_limit"] = gargs[i + 1]
                i += 2
            else:
                leftover.append(a)
                i += 1
        gs["extra"] = " ".join(leftover)
        result["gamescope"] = gs

    if result["gamescope"]:
        if "mangohud" in inner:
            result["mangohud"] = True
            inner.remove("mangohud")
        result["extra"] = " ".join(outer + inner).strip()
    else:
        if "mangohud" in outer:
            result["mangohud"] = True
            outer.remove("mangohud")
        result["extra"] = " ".join(outer + inner).strip()

    return result, suffix.strip()


def build_launch_options(gamemode, mangohud, gamescope, extra, suffix="", proton=None, lsfg=None):
    """Inverso de parse_launch_options: monta a string de LaunchOptions.
    gamescope: None, ou dict com enabled/width/height/render_width/
    render_height/refresh/filter/scaler/fullscreen/borderless/grab/
    force_grab_cursor/steam/adaptive_sync/framerate_limit/extra.
    proton: None, ou dict com
    no_esync/no_fsync/enable_nvapi/vkd3d_config. lsfg: None, ou dict com
    disable/profile/multiplier/flow_scale/performance_mode (LSFGVK_ENV=1
    e adicionado sozinho quando multiplier/flow_scale/performance_mode
    estao presentes, ver docs do lsfg-vk)."""
    tokens = []

    if proton:
        if proton.get("no_esync"):
            tokens.append("PROTON_NO_ESYNC=1")
        if proton.get("no_fsync"):
            tokens.append("PROTON_NO_FSYNC=1")
        if proton.get("enable_nvapi"):
            tokens.append("PROTON_ENABLE_NVAPI=1")
        if proton.get("vkd3d_config"):
            tokens.append(f"VKD3D_CONFIG={proton['vkd3d_config']}")

    if lsfg:
        if lsfg.get("disable"):
            tokens.append("DISABLE_LSFGVK=1")
        if lsfg.get("profile"):
            tokens.append(f"LSFGVK_PROFILE={lsfg['profile']}")
        needs_env = bool(
            lsfg.get("multiplier") or lsfg.get("flow_scale") or lsfg.get("performance_mode")
        )
        if needs_env:
            tokens.append("LSFGVK_ENV=1")
            if lsfg.get("multiplier"):
                tokens.append(f"LSFGVK_MULTIPLIER={lsfg['multiplier']}")
            if lsfg.get("flow_scale"):
                tokens.append(f"LSFGVK_FLOW_SCALE={lsfg['flow_scale']}")
            if lsfg.get("performance_mode"):
                tokens.append("LSFGVK_PERFORMANCE_MODE=1")

    if gamemode:
        tokens.append("gamemoderun")

    use_gamescope = bool(gamescope and gamescope.get("enabled"))
    if use_gamescope:
        tokens.append("gamescope")
        if gamescope.get("render_width"):
            tokens += ["-w", str(gamescope["render_width"])]
        if gamescope.get("render_height"):
            tokens += ["-h", str(gamescope["render_height"])]
        if gamescope.get("width"):
            tokens += ["-W", str(gamescope["width"])]
        if gamescope.get("height"):
            tokens += ["-H", str(gamescope["height"])]
        if gamescope.get("refresh"):
            tokens += ["-r", str(gamescope["refresh"])]
        if gamescope.get("filter"):
            tokens += ["-F", str(gamescope["filter"])]
        if gamescope.get("scaler"):
            tokens += ["-S", str(gamescope["scaler"])]
        if gamescope.get("fullscreen"):
            tokens.append("-f")
        if gamescope.get("borderless"):
            tokens.append("-b")
        if gamescope.get("grab"):
            tokens.append("-g")
        if gamescope.get("force_grab_cursor"):
            tokens.append("--force-grab-cursor")
        if gamescope.get("steam"):
            tokens.append("-e")
        if gamescope.get("adaptive_sync"):
            tokens.append("--adaptive-sync")
        if gamescope.get("framerate_limit"):
            tokens += ["--framerate-limit", str(gamescope["framerate_limit"])]
        if gamescope.get("extra"):
            tokens += gamescope["extra"].split()
        tokens.append("--")

    if mangohud:
        tokens.append("mangohud")
    if extra:
        tokens += extra.split()
    tokens.append("%command%")

    result = " ".join(tokens)
    if suffix:
        result += " " + suffix.strip()
    return result
