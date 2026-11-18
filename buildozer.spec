[app]

title = DarkVault
package.name = darkvault
package.domain = org.darkvault

source.dir = GAME
source.include_exts = py,png,jpg,txt,json,ttf
source.exclude_dirs = __pycache__,.build_venv,.build_venv_win,.build_venv_linux,.build_venv_android,.pyinstaller_build,.pyinstaller_spec

version = 1.0.0

requirements = python3,pygame

icon.filename = GAME/darkvault.png
presplash.filename = GAME/darkvault_presplash.jpg
presplash.color = #050505

orientation = landscape
fullscreen = 1
android.display_cutout = shortEdges

android.permissions = VIBRATE, INTERNET, ACCESS_NETWORK_STATE, ACCESS_WIFI_STATE
android.api = 33
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True
android.accept_sdk_license = True
android.release_artifact = apk
p4a.branch = v2023.09.16

[buildozer]
log_level = 2
warn_on_root = 0
