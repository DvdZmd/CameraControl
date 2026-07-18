#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

git_safe() {
    git -c safe.directory="$PROJECT_DIR" "$@"
}

choose_python() {
    if [ -x "./.venv/bin/python" ]; then
        echo "./.venv/bin/python"
    elif [ -x "./venv/bin/python" ]; then
        echo "./venv/bin/python"
    else
        echo ""
    fi
}

echo "Buscando actualizaciones en origin/main..."
git_safe fetch origin main

LOCAL_HEAD="$(git_safe rev-parse HEAD)"
REMOTE_HEAD="$(git_safe rev-parse FETCH_HEAD)"

if [ "$LOCAL_HEAD" = "$REMOTE_HEAD" ]; then
    echo "No hay cambios disponibles. El sistema ya esta actualizado."
    exit 0
fi

echo "Hay cambios disponibles. Actualizando repositorio..."
git_safe pull origin main

PYTHON_BIN="$(choose_python)"

if [ -z "$PYTHON_BIN" ]; then
    echo "No se encontro un entorno virtual. Creando .venv..."
    python3 -m venv .venv
    PYTHON_BIN="./.venv/bin/python"
fi

echo "Actualizando dependencias con $PYTHON_BIN..."
"$PYTHON_BIN" -m pip install --upgrade pip
"$PYTHON_BIN" -m pip install --upgrade -r requirements.txt

echo "Verificando que tuya_iot pueda importarse..."
"$PYTHON_BIN" - <<'PY'
import tuya_iot
print("tuya_iot OK")
PY

if sudo systemctl list-unit-files 2>/dev/null | grep -q '^cameracontrol.service'; then
    echo "Reiniciando servicio cameracontrol.service..."
    sudo systemctl restart cameracontrol.service
else
    echo "No se encontro el servicio cameracontrol.service; se omite el reinicio."
fi
