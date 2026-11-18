import argparse
import os
import shutil
import sys

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
    run_pyinstaller,
)

WIN_DIST_DIR = os.path.join(DIST_ROOT, "windows")


def build_windows_setup(game_exe_path: str, icon_path: str) -> str:
    installer_entry = os.path.join(HERE, "installer_windows.py")
    args = [
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name",
        "DarkVault_Setup",
        "--distpath",
        WIN_DIST_DIR,
        "--workpath",
        os.path.join(BUILD_WORK_DIR, "win_setup"),
        "--specpath",
        SPEC_DIR,
        "--add-data",
        f"{game_exe_path};.",
    ]
    if icon_path and os.path.exists(icon_path):
        args.extend(["--icon", icon_path, "--add-data", f"{icon_path};."])

    args.append(installer_entry)
    run_pyinstaller(args)

    out_setup = os.path.join(WIN_DIST_DIR, "DarkVault_Setup.exe")
    if not os.path.exists(out_setup):
        raise FileNotFoundError(f"Expected Windows installer was not created: {out_setup}")
    print(f"[+] Built Windows installer: {out_setup}")
    return out_setup


def main():
    parser = argparse.ArgumentParser(description="Build DarkVault Windows .exe and DarkVault_Setup.exe")
    parser.add_argument("--icon-only", action="store_true", help="Only generate GAME/darkvault.ico")
    parser.add_argument("--exe-only", action="store_true", help="Build DarkVault.exe only (skip DarkVault_Setup.exe)")
    parser.add_argument("--clean", action="store_true", help="Remove temporary PyInstaller build folders after build")
    args = parser.parse_args()

    ico_path, _ = generate_icons(make_ico=True, make_png=True)
    if args.icon_only:
        return

    if sys.platform != "win32":
        print("[!] Warning: Windows .exe builds must run on Windows (PyInstaller does not cross-compile PE binaries from Linux).")

    game_exe = build_game_binary(WIN_DIST_DIR, "win_game", icon_path=ico_path, windowed=True)
    if not args.exe_only:
        build_windows_setup(game_exe, ico_path)

    if args.clean:
        for folder in (BUILD_WORK_DIR, SPEC_DIR):
            if os.path.exists(folder):
                shutil.rmtree(folder, ignore_errors=True)
        print("[+] Cleaned temporary build folders.")


if __name__ == "__main__":
    main()
