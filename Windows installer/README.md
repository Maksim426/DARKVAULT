# Windows Installer · Подземелье Тьмы (DarkVault)

## Быстрая сборка в один клик
Откройте двойным кликом **`BUILD_WINDOWS.bat`** из этой папки.

Скрипт автоматически:
1. Проверит наличие Python 3 (при отсутствии предложит установку через `winget`).
2. Создаст изолированное окружение `.build_venv_win` и установит `pygame`, `Pillow`, `pyinstaller`.
3. Сгенерирует многоразмерную иконку `darkvault.ico` и соберёт в `../dist/windows/`:
   - **`DarkVault_Setup.exe`** — графический установщик Windows (выбор папки установки, создание ярлыков с иконкой в **меню «Пуск»** и на **Рабочем столе**, регистрация в «Приложения и возможности» и деинсталлятор `Uninstall_DarkVault.bat`);
   - **`DarkVault.exe`** — портативная версия, не требующая установки.

## Ручная сборка из командной строки
```bat
pip install -r ..\GAME\requirements.txt pyinstaller
python build_windows.py --clean
```
