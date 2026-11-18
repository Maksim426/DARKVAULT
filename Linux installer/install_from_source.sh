#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
GAME_SRC="$ROOT_DIR/GAME"

INSTALL_DIR="${HOME}/.local/share/DarkVault"
BIN_LINK="${HOME}/.local/bin/darkvault"
APPLICATIONS_DIR="${HOME}/.local/share/applications"
DESKTOP_ENTRY="${APPLICATIONS_DIR}/darkvault.desktop"
HICOLOR_DIR="${HOME}/.local/share/icons/hicolor"
ICON_TARGET="${HICOLOR_DIR}/256x256/apps/darkvault.png"
PIXMAP_TARGET="${HOME}/.local/share/pixmaps/darkvault.png"

echo ""
echo "================================================================"
echo "  Подземелье Тьмы · DarkVault — Быстрая установка из исходников"
echo "================================================================"
echo ""

if ! command -v python3 >/dev/null 2>&1; then
  echo "[!] Python 3 не найден. Установите python3 и python3-venv."
  exit 1
fi

mkdir -p "$INSTALL_DIR" "${HOME}/.local/bin" "$APPLICATIONS_DIR" "$(dirname "$ICON_TARGET")" "$(dirname "$PIXMAP_TARGET")"

rm -rf "$INSTALL_DIR/GAME"
cp -R "$GAME_SRC" "$INSTALL_DIR/GAME"

if [ ! -x "$INSTALL_DIR/venv/bin/python" ]; then
  echo "[1/3] Создание виртуального окружения..."
  python3 -m venv "$INSTALL_DIR/venv"
fi

echo "[2/3] Установка зависимостей (pygame, Pillow)..."
"$INSTALL_DIR/venv/bin/python" -m pip install --upgrade pip >/dev/null 2>&1 || true
if ! "$INSTALL_DIR/venv/bin/python" -m pip install -r "$INSTALL_DIR/GAME/requirements.txt"; then
  "$INSTALL_DIR/venv/bin/python" -m pip install pygame-ce Pillow
fi

echo "[3/3] Генерация иконки и добавление в меню приложений..."
"$INSTALL_DIR/venv/bin/python" "$SCRIPT_DIR/build_linux.py" --icon-only || true

if [ -f "$GAME_SRC/darkvault.png" ]; then
  cp -f "$GAME_SRC/darkvault.png" "$ICON_TARGET"
  cp -f "$GAME_SRC/darkvault.png" "$PIXMAP_TARGET"
  cp -f "$GAME_SRC/darkvault.png" "$INSTALL_DIR/GAME/darkvault.png"
fi

if [ ! -f "${HICOLOR_DIR}/index.theme" ]; then
  cat > "${HICOLOR_DIR}/index.theme" <<'THEME_EOF'
[Icon Theme]
Name=Hicolor
Comment=Fallback icon theme
Directories=256x256/apps

[256x256/apps]
Size=256
Context=Applications
Type=Threshold
THEME_EOF
fi

cat > "$INSTALL_DIR/darkvault-launch" <<EOF
#!/usr/bin/env bash
exec "$INSTALL_DIR/venv/bin/python" "$INSTALL_DIR/GAME/main.py" "\$@"
EOF
chmod +x "$INSTALL_DIR/darkvault-launch"
ln -sf "$INSTALL_DIR/darkvault-launch" "$BIN_LINK"

ICON_VALUE="$ICON_TARGET"
[ -f "$ICON_VALUE" ] || ICON_VALUE="darkvault"

cat > "$DESKTOP_ENTRY" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=DarkVault
Name[ru]=Подземелье Тьмы · DarkVault
GenericName=Roguelike Game
GenericName[ru]=Нуар-рогалик
Comment=Monochrome noir roguelike dungeon crawler
Comment[ru]=Процедурный монохромный нуар-рогалик
Exec="$INSTALL_DIR/darkvault-launch"
Path=$INSTALL_DIR/GAME
Icon=$ICON_VALUE
Terminal=false
Categories=Game;ActionGame;AdventureGame;
StartupNotify=true
StartupWMClass=DarkVault
EOF
chmod +x "$DESKTOP_ENTRY"

if command -v xdg-user-dir >/dev/null 2>&1; then
  DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || echo "${HOME}/Desktop")"
else
  DESKTOP_DIR="${HOME}/Desktop"
fi
if [ -d "$DESKTOP_DIR" ]; then
  cp -f "$DESKTOP_ENTRY" "$DESKTOP_DIR/DarkVault.desktop"
  chmod +x "$DESKTOP_DIR/DarkVault.desktop"
  command -v gio >/dev/null 2>&1 && gio set "$DESKTOP_DIR/DarkVault.desktop" metadata::trusted true >/dev/null 2>&1 || true
fi

cat > "$INSTALL_DIR/uninstall.sh" <<EOF
#!/usr/bin/env bash
set -e
rm -f "$BIN_LINK" "$DESKTOP_ENTRY" "$ICON_TARGET" "$PIXMAP_TARGET" "$DESKTOP_DIR/DarkVault.desktop"
rm -rf "$INSTALL_DIR"
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f -t "$HICOLOR_DIR" >/dev/null 2>&1 || true
echo "DarkVault удалён."
EOF
chmod +x "$INSTALL_DIR/uninstall.sh"

command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f -t "$HICOLOR_DIR" >/dev/null 2>&1 || true
command -v xdg-desktop-menu >/dev/null 2>&1 && xdg-desktop-menu forceupdate >/dev/null 2>&1 || true

echo ""
echo "[+] Готово! Игра и иконка добавлены в меню приложений (DarkVault)."
echo "    Удаление: $INSTALL_DIR/uninstall.sh"
