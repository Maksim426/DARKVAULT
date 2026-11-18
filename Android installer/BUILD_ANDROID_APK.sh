#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo ""
echo "========================================================================"
echo "  ПОДЗЕМЕЛЬЕ ТЬМЫ · DARKVAULT — СБОРКА ANDROID .APK"
echo "========================================================================"
echo ""

if ! command -v python3 >/dev/null 2>&1; then
  echo "[!] Python 3 не найден. Установите python3 и python3-venv."
  exit 1
fi

VENV_DIR="$ROOT_DIR/.build_venv_android"
if [ ! -x "$VENV_DIR/bin/python" ]; then
  echo "[1/4] Создание окружения сборки ($VENV_DIR)..."
  python3 -m venv "$VENV_DIR"
fi

BUILD_PY="$VENV_DIR/bin/python"

echo "[2/4] Установка / проверка зависимостей (buildozer 1.5.0, cython<3, Pillow)..."
"$BUILD_PY" -m pip install --upgrade "pip<25" "setuptools<72" wheel >/dev/null 2>&1 || true
"$BUILD_PY" -m pip install "buildozer==1.5.0" "cython<3" Pillow packaging

echo "[3/4] Подготовка иконки (512x512) и заставки (1280x720)..."
"$BUILD_PY" "$SCRIPT_DIR/prepare_android.py" --assets-only

echo "[4/4] Сборка Android APK через Buildozer..."
echo "      (При первом запуске скачиваются Android SDK/NDK — это займёт 10-20 минут)"
echo ""
cd "$SCRIPT_DIR"
export VIRTUAL_ENV="$VENV_DIR"
export PATH="$VENV_DIR/bin:$PATH"
export ANDROID_ACCEPT_LICENSE=1
"$VENV_DIR/bin/buildozer" -v android debug

"$BUILD_PY" "$SCRIPT_DIR/prepare_android.py" --collect-only

echo ""
echo "========================================================================"
echo "  СБОРКА ANDROID APK ЗАВЕРШЕНА!"
echo "========================================================================"
echo ""
echo "  Готовый файл для установки на телефон: $ROOT_DIR/dist/android/DarkVault.apk"
echo ""
