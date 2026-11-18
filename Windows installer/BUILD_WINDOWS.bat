@echo off
setlocal EnableExtensions
chcp 65001 >nul
title Подземелье Тьмы · DarkVault — Сборка для Windows (.EXE)
color 0F

cd /d "%~dp0.."

echo.
echo ========================================================================
echo   ПОДЗЕМЕЛЬЕ ТЬМЫ · DARKVAULT — СБОРКА .EXE И УСТАНОВЩИКА WINDOWS
echo ========================================================================
echo.

set "PY_CMD="

where py >nul 2>&1
if %errorlevel%==0 (
    py -3 -c "import sys; sys.exit(0 if sys.version_info[0]==3 else 1)" >nul 2>&1
    if %errorlevel%==0 set "PY_CMD=py -3"
)

if not defined PY_CMD (
    where python >nul 2>&1
    if %errorlevel%==0 (
        python -c "import sys; sys.exit(0 if sys.version_info[0]==3 else 1)" >nul 2>&1
        if %errorlevel%==0 set "PY_CMD=python"
    )
)

if not defined PY_CMD (
    where python3 >nul 2>&1
    if %errorlevel%==0 (
        python3 -c "import sys; sys.exit(0 if sys.version_info[0]==3 else 1)" >nul 2>&1
        if %errorlevel%==0 set "PY_CMD=python3"
    )
)

if not defined PY_CMD (
    echo [!] Python 3 не найден на этом компьютере.
    echo     Для сборки .exe нужен Python 3.10+ ^(достаточно установить 1 раз^).
    echo.
    choice /C YN /M "Попробовать установить Python 3.12 автоматически через winget (Y/N)"
    if errorlevel 2 (
        echo.
        echo Откроем страницу загрузки Python. При установке обязательно отметьте
        echo галочку "Add Python to PATH", затем снова запустите BUILD_WINDOWS.bat.
        start "" "https://www.python.org/downloads/"
        pause
        exit /b 1
    )
    where winget >nul 2>&1
    if errorlevel 1 (
        echo [!] winget недоступен. Пожалуйста, установите Python с https://www.python.org/downloads/
        start "" "https://www.python.org/downloads/"
        pause
        exit /b 1
    )
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    echo.
    echo [+] Если Python установился, перезапустите BUILD_WINDOWS.bat.
    pause
    exit /b 0
)

echo [1/4] Найден Python: %PY_CMD%

if not exist ".build_venv_win\Scripts\python.exe" (
    echo [2/4] Создание изолированного окружения сборки ^(.build_venv_win^)...
    %PY_CMD% -m venv ".build_venv_win"
    if errorlevel 1 (
        echo [!] Ошибка при создании .build_venv_win. Пробуем пересобрать без venv...
        goto :use_global_python
    )
) else (
    echo [2/4] Используется готовое окружение .build_venv_win...
)

set "BUILD_PY=%CD%\.build_venv_win\Scripts\python.exe"
goto :install_deps

:use_global_python
set "BUILD_PY=%PY_CMD%"

:install_deps
echo [3/4] Установка / проверка зависимостей ^(pygame, Pillow, pyinstaller^)...
"%BUILD_PY%" -m pip install --upgrade pip >nul 2>&1
"%BUILD_PY%" -m pip install --upgrade pygame Pillow pyinstaller
if errorlevel 1 (
    echo [!] Не удалось поставить pygame, пробуем совместимый пакет pygame-ce...
    "%BUILD_PY%" -m pip install --upgrade pygame-ce Pillow pyinstaller
    if errorlevel 1 (
        echo.
        echo [!] Не удалось установить зависимости. Проверьте подключение к интернету.
        pause
        exit /b 1
    )
)

echo [4/4] Сборка DarkVault.exe и установщика DarkVault_Setup.exe...
echo       ^(Обычно занимает 30-90 секунд^)
echo.
"%BUILD_PY%" "Windows installer\build_windows.py" --clean
if errorlevel 1 (
    echo.
    echo [!] Произошла ошибка при сборке .exe файла.
    pause
    exit /b 1
)

echo.
echo ========================================================================
echo   СБОРКА ДЛЯ WINDOWS УСПЕШНО ЗАВЕРШЕНА!
echo ========================================================================
echo.
echo   1. Установщик Windows : "%CD%\dist\windows\DarkVault_Setup.exe"
echo   2. Портативная игра   : "%CD%\dist\windows\DarkVault.exe"
echo.
echo   Что вы хотите сделать дальше?
echo     [1] Запустить установщик DarkVault_Setup.exe ^(установить игру на ПК^)
echo     [2] Сразу запустить игру DarkVault.exe
echo     [3] Открыть папку dist\windows\
echo     [4] Выход
echo.

choice /C 1234 /N /M "Выберите действие [1-4]: "
if errorlevel 4 exit /b 0
if errorlevel 3 (
    explorer "%CD%\dist\windows"
    exit /b 0
)
if errorlevel 2 (
    start "" "%CD%\dist\windows\DarkVault.exe"
    exit /b 0
)
if errorlevel 1 (
    start "" "%CD%\dist\windows\DarkVault_Setup.exe"
    exit /b 0
)
