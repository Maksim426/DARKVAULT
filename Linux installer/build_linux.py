import argparse
import os
import shutil
import stat
import sys
import tarfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(HERE)
GAME_DIR = os.path.join(ROOT_DIR, "GAME")
if GAME_DIR not in sys.path:
    sys.path.insert(0, GAME_DIR)

from build_common import (
    BUILD_WORK_DIR,
    DIST_ROOT,
    SPEC_DIR,
    build_game_binary,
    generate_icons,
)

LINUX_DIST_DIR = os.path.join(DIST_ROOT, "linux")

INSTALLER_HEADER = r"""#!/usr/bin/env bash
set -euo pipefail

APP_NAME="DarkVault"
APP_TITLE="Подземелье Тьмы · DarkVault"
DEFAULT_DIR="${HOME}/.local/share/DarkVault"
BIN_LINK="${HOME}/.local/bin/darkvault"
APPLICATIONS_DIR="${HOME}/.local/share/applications"
DESKTOP_ENTRY="${APPLICATIONS_DIR}/darkvault.desktop"
HICOLOR_DIR="${HOME}/.local/share/icons/hicolor"
ICON_TARGET="${HICOLOR_DIR}/256x256/apps/darkvault.png"
PIXMAP_TARGET="${HOME}/.local/share/pixmaps/darkvault.png"

INSTALL_DIR="$DEFAULT_DIR"
CREATE_DESKTOP=1
AUTO_YES=0
LAUNCH_AFTER=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dir)
      INSTALL_DIR="$2"
      shift 2
      ;;
    --yes|-y)
      AUTO_YES=1
      shift
      ;;
    --no-desktop)
      CREATE_DESKTOP=0
      shift
      ;;
    --launch)
      LAUNCH_AFTER=1
      shift
      ;;
    --help|-h)
      echo "Usage: $0 [--dir PATH] [--yes] [--no-desktop] [--launch]"
      exit 0
      ;;
    *)
      shift
      ;;
  esac
done

HAS_GUI=0
if [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ] && command -v zenity >/dev/null 2>&1 && [ "$AUTO_YES" -eq 0 ]; then
  HAS_GUI=1
fi

if [ "$HAS_GUI" -eq 1 ]; then
  zenity --question \
    --title="$APP_TITLE — Установщик Linux" \
    --width=460 \
    --text="Установить игру «$APP_TITLE» на компьютер?\n\nБудет добавлен ярлык с иконкой в меню приложений.\n\nПапка по умолчанию:\n$DEFAULT_DIR" \
    --ok-label="Выбрать папку / Далее" \
    --cancel-label="Отмена" || exit 0

  CHOSEN_DIR="$(zenity --file-selection --directory --title="Выберите папку установки DarkVault" --filename="$DEFAULT_DIR/" || true)"
  if [ -n "$CHOSEN_DIR" ]; then
    case "$(basename "$CHOSEN_DIR")" in
      DarkVault|darkvault) INSTALL_DIR="$CHOSEN_DIR" ;;
      *) INSTALL_DIR="${CHOSEN_DIR}/DarkVault" ;;
    esac
  fi

  if ! zenity --question \
    --title="$APP_TITLE" \
    --width=420 \
    --text="Создать ярлык на Рабочем столе (помимо меню приложений)?" \
    --ok-label="Да" --cancel-label="Нет"; then
    CREATE_DESKTOP=0
  fi
elif [ "$AUTO_YES" -eq 0 ]; then
  echo "================================================================"
  echo "  $APP_TITLE — Установщик Linux"
  echo "================================================================"
  read -r -p "Папка установки [$DEFAULT_DIR]: " USER_DIR || true
  if [ -n "${USER_DIR:-}" ]; then
    INSTALL_DIR="$USER_DIR"
  fi
  read -r -p "Создать ярлык на Рабочем столе? [Y/n]: " DESK_ANS || true
  case "${DESK_ANS:-Y}" in
    n|N|н|Н) CREATE_DESKTOP=0 ;;
  esac
fi

ARCHIVE_LINE="$(awk '/^__ARCHIVE_BELOW__$/{print NR + 1; exit 0;}' "$0")"
TMP_EXTRACT="$(mktemp -d)"
trap 'rm -rf "$TMP_EXTRACT"' EXIT

tail -n +"$ARCHIVE_LINE" "$0" | tar -xz -C "$TMP_EXTRACT"

mkdir -p "$INSTALL_DIR" "${HOME}/.local/bin" "$APPLICATIONS_DIR" "$(dirname "$ICON_TARGET")" "$(dirname "$PIXMAP_TARGET")"

cp -f "$TMP_EXTRACT/DarkVault" "$INSTALL_DIR/DarkVault"
chmod +x "$INSTALL_DIR/DarkVault"

if [ -f "$TMP_EXTRACT/darkvault.png" ]; then
  cp -f "$TMP_EXTRACT/darkvault.png" "$ICON_TARGET"
  cp -f "$TMP_EXTRACT/darkvault.png" "$PIXMAP_TARGET"
  cp -f "$TMP_EXTRACT/darkvault.png" "$INSTALL_DIR/darkvault.png"
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

ln -sf "$INSTALL_DIR/DarkVault" "$BIN_LINK"

ICON_VALUE="$ICON_TARGET"
if [ ! -f "$ICON_VALUE" ]; then
  ICON_VALUE="darkvault"
fi

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
Exec="$INSTALL_DIR/DarkVault"
Path=$INSTALL_DIR
Icon=$ICON_VALUE
Terminal=false
Categories=Game;ActionGame;AdventureGame;
StartupNotify=true
StartupWMClass=DarkVault
EOF
chmod +x "$DESKTOP_ENTRY"

if [ "$CREATE_DESKTOP" -eq 1 ]; then
  if command -v xdg-user-dir >/dev/null 2>&1; then
    DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || echo "${HOME}/Desktop")"
  else
    DESKTOP_DIR="${HOME}/Desktop"
  fi
  if [ -d "$DESKTOP_DIR" ]; then
    cp -f "$DESKTOP_ENTRY" "$DESKTOP_DIR/DarkVault.desktop"
    chmod +x "$DESKTOP_DIR/DarkVault.desktop"
    if command -v gio >/dev/null 2>&1; then
      gio set "$DESKTOP_DIR/DarkVault.desktop" metadata::trusted true >/dev/null 2>&1 || true
    fi
  fi
fi

cat > "$INSTALL_DIR/uninstall.sh" <<EOF
#!/usr/bin/env bash
set -e
rm -f "$BIN_LINK" "$DESKTOP_ENTRY" "$ICON_TARGET" "$PIXMAP_TARGET"
if command -v xdg-user-dir >/dev/null 2>&1; then
  DESKTOP_DIR="\$(xdg-user-dir DESKTOP 2>/dev/null || echo "\${HOME}/Desktop")"
else
  DESKTOP_DIR="\${HOME}/Desktop"
fi
rm -f "\$DESKTOP_DIR/DarkVault.desktop"
rm -rf "$INSTALL_DIR"
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f -t "$HICOLOR_DIR" >/dev/null 2>&1 || true
echo "DarkVault удалён."
EOF
chmod +x "$INSTALL_DIR/uninstall.sh"

command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f -t "$HICOLOR_DIR" >/dev/null 2>&1 || true
command -v xdg-desktop-menu >/dev/null 2>&1 && xdg-desktop-menu forceupdate >/dev/null 2>&1 || true

if [ "$HAS_GUI" -eq 1 ]; then
  if zenity --question \
    --title="$APP_TITLE" \
    --width=460 \
    --text="Установка завершена!\n\nИконка добавлена в меню приложений.\nПапка: $INSTALL_DIR\nУдаление: $INSTALL_DIR/uninstall.sh\n\nЗапустить игру сейчас?" \
    --ok-label="Играть!" --cancel-label="Закрыть"; then
    nohup "$INSTALL_DIR/DarkVault" >/dev/null 2>&1 &
  fi
else
  echo ""
  echo "[+] Установка завершена! Игра добавлена в меню приложений."
  echo "    Папка игры  : $INSTALL_DIR"
  echo "    Запуск      : $INSTALL_DIR/DarkVault (или darkvault)"
  echo "    Удаление    : $INSTALL_DIR/uninstall.sh"
  if [ "$LAUNCH_AFTER" -eq 1 ]; then
    nohup "$INSTALL_DIR/DarkVault" >/dev/null 2>&1 &
  elif [ "$AUTO_YES" -eq 0 ]; then
    read -r -p "Запустить игру сейчас? [Y/n]: " RUN_NOW || true
    case "${RUN_NOW:-Y}" in
      n|N|н|Н) ;;
      *) nohup "$INSTALL_DIR/DarkVault" >/dev/null 2>&1 & ;;
    esac
  fi
fi

exit 0
__ARCHIVE_BELOW__
"""


def build_linux_self_extracting_installer(game_bin_path: str, icon_png_path: str) -> str:
    os.makedirs(LINUX_DIST_DIR, exist_ok=True)
    payload_tgz = os.path.join(BUILD_WORK_DIR, "linux_payload.tar.gz")
    os.makedirs(BUILD_WORK_DIR, exist_ok=True)

    with tarfile.open(payload_tgz, "w:gz") as tar:
        tar.add(game_bin_path, arcname="DarkVault")
        if icon_png_path and os.path.exists(icon_png_path):
            tar.add(icon_png_path, arcname="darkvault.png")

    installer_path = os.path.join(LINUX_DIST_DIR, "DarkVault_Setup.sh")
    with open(installer_path, "wb") as out_f:
        out_f.write(INSTALLER_HEADER.lstrip("\n").encode("utf-8"))
        with open(payload_tgz, "rb") as tar_f:
            shutil.copyfileobj(tar_f, out_f)

    st = os.stat(installer_path)
    os.chmod(installer_path, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f"[+] Built Linux self-extracting installer: {installer_path}")
    return installer_path


def main():
    parser = argparse.ArgumentParser(description="Build DarkVault Linux binary and DarkVault_Setup.sh installer")
    parser.add_argument("--icon-only", action="store_true", help="Only generate GAME/darkvault.png")
    parser.add_argument("--bin-only", action="store_true", help="Build DarkVault binary only (skip DarkVault_Setup.sh)")
    parser.add_argument("--clean", action="store_true", help="Remove temporary PyInstaller build folders after build")
    args = parser.parse_args()

    _, png_path = generate_icons(make_ico=False, make_png=True)
    if args.icon_only:
        return

    if sys.platform.startswith("win"):
        print("[!] Warning: Linux ELF binaries must be built on Linux (or WSL/GitHub Actions).")

    game_bin = build_game_binary(LINUX_DIST_DIR, "linux_game", icon_path=png_path, windowed=True)
    if not args.bin_only:
        build_linux_self_extracting_installer(game_bin, png_path)

    if args.clean:
        for folder in (BUILD_WORK_DIR, SPEC_DIR):
            if os.path.exists(folder):
                shutil.rmtree(folder, ignore_errors=True)
        print("[+] Cleaned temporary build folders.")


if __name__ == "__main__":
    main()
