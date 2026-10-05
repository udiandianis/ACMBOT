#!/usr/bin/env bash
# 自动准备 Linux 依赖和 NapCat，启动机器人后端。
set -Eeuo pipefail
export PYTHONDONTWRITEBYTECODE=1

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="$PROJECT_DIR/.venv-linux"
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

prepare_system_dependencies() {
    local packages=() privilege=()
    if ! command -v "$PYTHON_BIN" >/dev/null; then
        [[ "$PYTHON_BIN" == python3 ]] || die "Custom Python interpreter not found: $PYTHON_BIN"
        packages+=(python3 python3-venv python3-pip)
    else
        "$PYTHON_BIN" -c 'import venv, ensurepip' >/dev/null 2>&1 || packages+=(python3-venv)
        "$PYTHON_BIN" -c 'import pip' >/dev/null 2>&1 || packages+=(python3-pip)
    fi
    if ! command -v flock >/dev/null || ! command -v setsid >/dev/null; then packages+=(util-linux); fi
    command -v xvfb-run >/dev/null || packages+=(xvfb)
    command -v xauth >/dev/null || packages+=(xauth)
    command -v screen >/dev/null || packages+=(screen)
    command -v curl >/dev/null || packages+=(curl)
    command -v sudo >/dev/null || packages+=(sudo)
    if [[ ${#packages[@]} -gt 0 ]]; then
        command -v apt-get >/dev/null || die "Automatic system dependency installation requires Ubuntu/Debian (apt-get). Missing packages: ${packages[*]}"
        if [[ "$EUID" -ne 0 ]]; then
            command -v sudo >/dev/null || die "Installing system dependencies requires root or sudo. Missing packages: ${packages[*]}"
            privilege=(sudo)
        fi
        echo "Installing missing system dependencies: ${packages[*]}"
        "${privilege[@]}" apt-get update || die 'Cannot update package indexes.'
        "${privilege[@]}" apt-get install -y "${packages[@]}" || die 'System dependency installation failed.'
    fi
    for tool in "$PYTHON_BIN" flock setsid xvfb-run xauth screen curl sudo; do
        command -v "$tool" >/dev/null || die "Missing command after installation: $tool"
    done
    "$PYTHON_BIN" -c 'import sys, venv, ensurepip; assert sys.version_info >= (3, 10)' || die 'Python 3.10 or later with venv support is required; check PYTHON_BIN.'
}

[[ -f config/bot_settings.json ]] || { echo 'ERROR: config/bot_settings.json was not found.' >&2; exit 1; }
prepare_system_dependencies
readarray -t launch_config < <("$PYTHON_BIN" - <<'PYCONFIG'
from pathlib import Path
from src.settings import Settings
settings = Settings.load()
print(settings.port)
print(settings.napcat_webui_port)
print(Path(settings.napcat_linux_qq_path).expanduser())
print(settings.bot_qq)
print(settings.napcat_url)
print(settings.host)
PYCONFIG
)
[[ ${#launch_config[@]} -eq 6 ]] || { echo 'ERROR: Invalid config/bot_settings.json'; exit 1; }
BACKEND_PORT="${launch_config[0]}"
WEBUI_PORT="${launch_config[1]}"
NAPCAT_QQ_BIN="${launch_config[2]}"
BOT_QQ="${launch_config[3]}"
LOG_DIR="$PROJECT_DIR/logs"
managed_pids=()

exec 9>"$PROJECT_DIR/.start-linux.lock"
flock -n 9 || die 'This launcher is already running.'

port_open() {
    "$PYTHON_BIN" - "$1" <<'PY'
import socket
import sys
try:
    with socket.create_connection(('127.0.0.1', int(sys.argv[1])), timeout=1):
        pass
except OSError:
    sys.exit(1)
PY
}

prepare_napcat() {
    [[ -x "$NAPCAT_QQ_BIN" ]] && return
    local installed_qq="$HOME/Napcat/opt/QQ/qq" candidate setup_directory
    for candidate in "$installed_qq" /opt/QQ/qq; do
        if [[ -x "$candidate" && -f "${candidate%/qq}/resources/app/app_launcher/napcat/napcat.mjs" ]]; then
            installed_qq="$candidate"
            break
        fi
    done
    if [[ ! -x "$installed_qq" ]]; then
        [[ ! -e "$HOME/Napcat" && ! -d /opt/QQ/resources/app/app_launcher/napcat ]] || die 'An incomplete NapCat installation exists. Check its QQ path before retrying.'
        mkdir -p "$PROJECT_DIR/output/setup"
        setup_directory=$(mktemp -d "$PROJECT_DIR/output/setup/napcat.XXXXXX")
        echo 'Downloading the official NapCat installer and compatible Linux QQ...'
        curl --fail --location --retry 3 --connect-timeout 20 \
            'https://raw.githubusercontent.com/NapNeko/NapCat-Installer/0520e1d21c4794cd2a1e2fa45a285d9350dc4727/script/install.sh' \
            -o "$setup_directory/install.sh" || die 'NapCat installer download failed.'
        "$PYTHON_BIN" - "$setup_directory/install.sh" <<'VERIFY'
import hashlib
import sys
from pathlib import Path
if hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest() != '8c402d974bbbb3b0402f4c6bab7ef8bdee179a03c54d5e9507f372d3997e09cf':
    raise SystemExit('NapCat installer checksum mismatch')
VERIFY
        (
            cd "$setup_directory"
            bash install.sh --docker n --cli n --proxy 0
        ) || die 'NapCat installation failed.'
    fi
    [[ -x "$installed_qq" && -f "${installed_qq%/qq}/resources/app/app_launcher/napcat/napcat.mjs" ]] || die 'NapCat installation is incomplete.'
    "$PYTHON_BIN" - "$installed_qq" <<'SAVE_CONFIG'
import json
import os
import sys
from pathlib import Path
path = Path('config/bot_settings.json')
config = json.loads(path.read_text(encoding='utf-8-sig'))
config['napcat']['linux_qq_path'] = sys.argv[1]
temporary = path.with_suffix('.tmp.json')
with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w', encoding='utf-8') as stream:
    json.dump(config, stream, ensure_ascii=False, indent=2)
temporary.replace(path)
SAVE_CONFIG
    NAPCAT_QQ_BIN="$installed_qq"
    echo "NapCat ready: $NAPCAT_QQ_BIN"
}

cleanup() {
    trap - EXIT INT TERM
    for pid in "${managed_pids[@]}"; do
        kill -TERM -- "-$pid" 2>/dev/null || true
    done
    for pid in "${managed_pids[@]}"; do
        wait "$pid" 2>/dev/null || true
    done
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

start_napcat=false
start_backend=false
if port_open "$WEBUI_PORT"; then
    echo 'NapCat port is already in use; leaving the existing service running.'
else
    start_napcat=true
    prepare_napcat
fi

if port_open "$BACKEND_PORT"; then
    echo "Port $BACKEND_PORT is already in use; leaving the existing backend running."
else
    start_backend=true
    if [[ ! -x "$VENV_DIR/bin/python" ]]; then
        "$PYTHON_BIN" -m venv "$VENV_DIR" || die 'Cannot create venv; install the Python venv package.'
    fi
    if [[ ! -f "$VENV_DIR/.bjgbot-requirements" ]] || ! cmp -s requirements.txt "$VENV_DIR/.bjgbot-requirements"; then
        "$VENV_DIR/bin/python" -m pip install -r requirements.txt
        cp requirements.txt "$VENV_DIR/.bjgbot-requirements"
    fi
    export MPLBACKEND=Agg
    "$VENV_DIR/bin/python" -c 'import src.main; print("BJGBOT imports OK")'
fi

mkdir -p "$LOG_DIR"
if "$start_backend"; then
    setsid "$VENV_DIR/bin/python" -u -m src.main >>"$LOG_DIR/bjgbot.log" 2>&1 &
    managed_pids+=("$!")
    backend_ready=false
    for ((attempt=0; attempt<30; attempt++)); do
        if port_open "$BACKEND_PORT"; then backend_ready=true; break; fi
        kill -0 "${managed_pids[0]}" 2>/dev/null || die "Backend exited; see $LOG_DIR/bjgbot.log"
        sleep 1
    done
    "$backend_ready" || die "Backend startup timed out; see $LOG_DIR/bjgbot.log"
fi
if "$start_napcat"; then
    qq_args=(--no-sandbox)
    if [[ -n "${BOT_QQ:-}" ]]; then qq_args+=(-q "$BOT_QQ"); fi
    setsid xvfb-run -a "$NAPCAT_QQ_BIN" "${qq_args[@]}" >>"$LOG_DIR/napcat.log" 2>&1 &
    managed_pids+=("$!")
    echo "NapCat starting; login URL and QR information: $LOG_DIR/napcat.log"
fi

echo "NapCat API: ${launch_config[4]}; event callback: http://${launch_config[5]}:$BACKEND_PORT/"
echo 'Configure these endpoints in NapCat WebUI with array messages and self-message reporting disabled.'
if [[ ${#managed_pids[@]} -eq 0 ]]; then
    echo 'Both ports are already in use. Nothing was started.'
    exit 0
fi
echo "Logs: $LOG_DIR. Keep this terminal open. Ctrl+C stops only services started by this launcher."
status=0
wait -n "${managed_pids[@]}" || status=$?
echo "A managed service exited (status $status); stopping the other managed services."
exit "$status"
