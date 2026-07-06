#!/usr/bin/env bash
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

git_safe() {
    git -c safe.directory="$PROJECT_DIR" "$@"
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

if [ -d "./venv" ] && [ -x "./venv/bin/pip" ]; then
    echo "Actualizando dependencias desde ./venv..."
    ./venv/bin/pip install --upgrade -r requirements.txt
else
    echo "No se encontro entorno virtual en ./venv. Se omite instalacion de dependencias."
fi

echo "Reiniciando servicio cameracontrol.service..."
sudo systemctl restart cameracontrol.service
