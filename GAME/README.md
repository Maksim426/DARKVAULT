# Подземелье Тьмы · DarkVault

Автономная Python/Pygame-версия процедурного нуар-рогалика в единой папке `GAME/`.

## Особенности
- **Монохромный нуар-стиль**: контрастные силуэты врагов и 4x суперсэмплинг (`Lanczos` / `Gaussian`) для героев, боссов, торговцев, машин и лавок.
- **Плавное 2D-освещение** (`lighting.py`): непрерывные радиальные градиенты без ступенек, мягкие тени под объектами и направленный конус фонаря.
- **Процедурные подземелья** (`dungeon.py`, `room.py`): уникальный seed на комнату, 20 планировок с проверкой проходимости (BFS), тематические боевые залы и 4 топологии генерации этажей.
- **Контент**: **14 героев**, **108 артефактов** (RU / EN), быстрый инвентарь `[1–9]` / `[0]`, **19 видов врагов**, **3 мистических НПС**, **8 нищих**, **4 торговца**, **7 машин**, **Древние Монолиты** и **66 боссов/мини-боссов**.
- **Инструменты и лор**: консоль разработчика (`ё` / `` ` `` / `F1`), система статус-эффектов (`effect`), **Редактор комнат** (`editor on` / `F2`), анимированная **«Хроника Подземелья Тьмы»** (12 глав), **Энциклопедия** (7 разделов) и живое превью из 6 комнат. Подробности по командам — в [`CONSOLE_COMMANDS.txt`](CONSOLE_COMMANDS.txt).

## Запуск из исходников
```bash
pip install -r GAME/requirements.txt
python GAME/main.py
```

## Сборка установщиков (Windows и Linux)
- **Windows** — запустите двойным кликом [`Windows installer/BUILD_WINDOWS.bat`](../Windows%20installer/BUILD_WINDOWS.bat) (результат в `dist/windows/`):
  ```bat
  pip install -r GAME\requirements.txt pyinstaller
  python "Windows installer\build_windows.py" --clean
  ```
- **Linux** — запустите [`Linux installer/BUILD_LINUX.sh`](../Linux%20installer/BUILD_LINUX.sh) (результат в `dist/linux/`) или [`Linux installer/install_from_source.sh`](../Linux%20installer/install_from_source.sh) для мгновенной установки с иконкой в меню приложений:
  ```bash
  cd "Linux installer"
  chmod +x BUILD_LINUX.sh
  ./BUILD_LINUX.sh
  ```
- **Android (`.apk`)** — запустите [`Android installer/BUILD_ANDROID_APK.sh`](../Android%20installer/BUILD_ANDROID_APK.sh) (результат в `dist/android/DarkVault.apk`) или скачайте готовую сборку `DarkVault-Android` из GitHub Actions. В игру встроено мультитач-управление (`touch_controls.py`).

## Управление
- <kbd>W</kbd> <kbd>A</kbd> <kbd>S</kbd> <kbd>D</kbd> — перемещение
- <kbd>↑</kbd> <kbd>↓</kbd> <kbd>←</kbd> <kbd>→</kbd> — стрельба
- <kbd>Shift</kbd> / <kbd>C</kbd> — теневой телепорт
- <kbd>Space</kbd> — активация выбранной активной реликвии
- <kbd>1</kbd>–<kbd>9</kbd> / <kbd>0</kbd> / <kbd>[</kbd> <kbd>]</kbd> / клик по ячейке — выбор реликвии и страницы инвентаря
- <kbd>E</kbd> — установка бомбы
- <kbd>`</kbd> / <kbd>~</kbd> / <kbd>ё</kbd> / <kbd>F1</kbd> — консоль разработчика (включается в Настройках; `editor on` открывает редактор по <kbd>F2</kbd>)
- <kbd>F11</kbd> / <kbd>Alt</kbd>+<kbd>Enter</kbd> — оконный / полноэкранный режим
- **Мышь** — клики, наведение и прокрутка колёсиком во всех меню, Энциклопедии и Хронике
- <kbd>Q</kbd> / <kbd>E</kbd> (в меню) — выбор режима игры
- <kbd>1</kbd>–<kbd>6</kbd> / <kbd>H</kbd> (в главном меню) — переключение комнаты живого превью / скрыть интерфейс
- <kbd>P</kbd> / <kbd>Esc</kbd> — пауза и доступ к Энциклопедии
