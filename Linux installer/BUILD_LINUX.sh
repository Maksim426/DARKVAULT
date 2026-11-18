#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

echo ""
echo "========================================================================"
echo "  ПОДЗЕМЕЛЬЕ ТЬМЫ · DARKVAULT — СБОРКА И УСТАНОВЩИК ДЛЯ LINUX"
echo "========================================================================"
echo ""

if ! command -v python3 >/dev/null 2>&1; then
  echo "[!] Python 3 не найден. Установите python3 (например: sudo apt install python3 python3-venv)"
  exit 1
fi

echo "[1/4] Найден Python: $(python3 --version)"

VENV_DIR=".build_venv_linux"
if [ ! -x "$VENV_DIR/bin/python" ]; then
  echo "[2/4] Создание изолированного окружения ($VENV_DIR)..."
  if ! python3 -m venv "$VENV_DIR"; then
    echo "[!] Не удалось создать venv. На Debian/Ubuntu выполните:"
    echo "    sudo apt update && sudo apt install -y python3-venv python3-pip"
    exit 1
  fi
else
  echo "[2/4] Используется готовое окружение $VENV_DIR..."
fi

BUILD_PY="$VENV_DIR/bin/python"

echo "[3/4] Установка / проверка зависимостей (pygame, Pillow, pyinstaller)..."
"$BUILD_PY" -m pip install --upgrade pip >/dev/null 2>&1 || true
if ! "$BUILD_PY" -m pip install --upgrade pygame Pillow pyinstaller; then
  echo "[!] Не удалось поставить pygame, пробуем совместимый пакет pygame-ce..."
  "$BUILD_PY" -m pip install --upgrade pygame-ce Pillow pyinstaller
fi

echo "[4/4] Сборка DarkVault и установщика DarkVault_Setup.sh..."
echo "      (Обычно занимает 30-90 секунд)"
echo ""
"$BUILD_PY" "Linux installer/build_linux.py" --clean

echo ""
echo "========================================================================"
echo "  СБОРКА ДЛЯ LINUX УСПЕШНО ЗАВЕРШЕНА!"
echo "========================================================================"
echo ""
echo "  1. Установщик Linux : $ROOT_DIR/dist/linux/DarkVault_Setup.sh"
echo "  2. Портативный файл : $ROOT_DIR/dist/linux/DarkVault"
echo ""
echo "  Что вы хотите сделать дальше?"
echo "    [1] Запустить установщик DarkVault_Setup.sh (меню приложений + иконка)"
echo "    [2] Сразу запустить игру dist/linux/DarkVault"
echo "    [3] Выход"
echo ""

read -r -p "Выберите действие [1-3]: " CHOICE || true
case "${CHOICE:-3}" in
  1)
    exec "$ROOT_DIR/dist/linux/DarkVault_Setup.sh"
    ;;
  2)
    exec "$ROOT_DIR/dist/linux/DarkVault"
    ;;
  *)
    exit 0
    ;;
esac
