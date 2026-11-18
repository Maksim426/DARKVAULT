# Linux Installer · Подземелье Тьмы (DarkVault)

## Вариант 1 — Собрать автономный бинарник и установщик (`BUILD_LINUX.sh`)
```bash
chmod +x BUILD_LINUX.sh
./BUILD_LINUX.sh
```
Скрипт создаст в `../dist/linux/`:
- **`DarkVault_Setup.sh`** — самораспаковывающийся установщик (поддерживает окно `zenity` и терминальный режим):
  - устанавливает игру в `~/.local/share/DarkVault`;
  - добавляет команду запуска `darkvault` в `~/.local/bin`;
  - устанавливает иконку `darkvault.png` в `hicolor` и `pixmaps` и создаёт `.desktop`-файл, благодаря чему **иконка игры сразу появляется в меню приложений** (GNOME, KDE, XFCE, Cinnamon, SteamOS) и на док-панели;
  - при желании создаёт ярлык на Рабочем столе и скрипт удаления `uninstall.sh`.
- **`DarkVault`** — портативный автономный бинарный файл Linux.

## Вариант 2 — Быстрая установка сразу из исходников (`install_from_source.sh`)
Если нужно сразу установить игру с иконкой в меню приложений без сборки одного бинарника PyInstaller:
```bash
chmod +x install_from_source.sh
./install_from_source.sh
```
