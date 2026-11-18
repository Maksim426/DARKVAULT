@echo off
chcp 65001 >nul
echo ========================================================
echo   DARKVAULT · СБОРКА ANDROID APK ЧЕРЕЗ DOCKER (НА ПК)
echo ========================================================
echo.

WHERE docker >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
  echo [!] Ошибка: Docker не найден!
  echo Установите Docker Desktop для Windows с официального сайта.
  pause
  exit /b 1
)

docker info >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
  echo [!] Ошибка: Docker Desktop не запущен!
  echo Пожалуйста, запустите приложение "Docker Desktop" через меню Пуск
  echo и дождитесь, пока иконка в трее станет зеленой, затем запустите этот файл снова.
  pause
  exit /b 1
)

echo [1/2] Подготовка ассетов (иконка и заставка)...
python prepare_android.py --assets-only

echo [2/2] Запуск сборки APK в официальном контейнере Buildozer...
echo (При первом запуске скачивается SDK/NDK, это может занять несколько минут)
echo.

cd ..
docker run --rm -v "%CD%/.buildozer:/home/user/.buildozer" -v "%CD%:/home/user/hostcwd" ghcr.io/kivy/buildozer:latest bash -c "cd \"Android installer\" && ANDROID_ACCEPT_LICENSE=1 buildozer -v android debug"
if %ERRORLEVEL% NEQ 0 (
  echo.
  echo [!] Ошибка при сборке APK в Docker. Проверьте вывод выше.
  pause
  exit /b 1
)

python "Android installer/prepare_android.py" --collect-only

echo.
echo ========================================================
echo   ГОТОВО! Файл APK находится в папке: dist\android\DarkVault.apk
echo ========================================================
pause
