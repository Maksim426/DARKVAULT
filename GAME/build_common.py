import os
import subprocess
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_ROOT = os.path.join(ROOT_DIR, "dist")
BUILD_WORK_DIR = os.path.join(ROOT_DIR, ".pyinstaller_build")
SPEC_DIR = os.path.join(ROOT_DIR, ".pyinstaller_spec")
ICON_ICO_PATH = os.path.join(GAME_DIR, "darkvault.ico")
ICON_PNG_PATH = os.path.join(GAME_DIR, "darkvault.png")

GAME_MODULES = [
    "accounts",
    "achievements",
    "ai_mod_agent",
    "boss_profiles",
    "bosses",
    "bullet",
    "codex",
    "console",
    "cutscene",
    "dungeon",
    "enemy",
    "heroes",
    "i18n",
    "items",
    "lan_coop",
    "lighting",
    "mods",
    "player",
    "quests",
    "room",
    "saves",
    "settings",
    "sound",
    "touch_controls",
    "ui",
]


def _render_emblem_image(size: int = 256):
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (size, size), (10, 10, 10, 255))
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle(
        [8, 8, size - 9, size - 9],
        radius=28,
        fill=(14, 14, 14, 255),
        outline=(230, 230, 230, 255),
        width=7,
    )
    draw.rounded_rectangle(
        [22, 22, size - 23, size - 23],
        radius=18,
        fill=(10, 10, 10, 255),
        outline=(95, 95, 95, 255),
        width=3,
    )

    draw.arc([52, 36, size - 52, 180], start=180, end=360, fill=(135, 135, 135, 255), width=5)

    cx = size // 2
    draw.ellipse([cx - 34, 62, cx + 34, 130], fill=(242, 242, 242, 255))
    draw.polygon(
        [
            (cx - 18, 118),
            (cx + 18, 118),
            (cx + 34, 206),
            (cx - 34, 206),
        ],
        fill=(242, 242, 242, 255),
    )

    draw.ellipse([cx - 14, 82, cx + 14, 110], fill=(14, 14, 14, 255))
    draw.polygon(
        [
            (cx - 6, 110),
            (cx + 6, 110),
            (cx + 12, 186),
            (cx - 12, 186),
        ],
        fill=(14, 14, 14, 255),
    )
    return img


def generate_icons(make_ico: bool = True, make_png: bool = True) -> tuple[str, str]:
    try:
        img = _render_emblem_image(256)
    except ImportError:
        print("[!] Pillow is not installed, skipping icon generation.")
        return "", ""

    ico_out = ""
    png_out = ""
    if make_ico:
        sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
        img.save(ICON_ICO_PATH, format="ICO", sizes=sizes)
        ico_out = ICON_ICO_PATH
        print(f"[+] Generated Windows icon: {ico_out}")

    if make_png:
        img.save(ICON_PNG_PATH, format="PNG")
        png_out = ICON_PNG_PATH
        print(f"[+] Generated Linux PNG icon: {png_out}")

    return ico_out, png_out


def run_pyinstaller(args: list[str]):
    cmd = [sys.executable, "-m", "PyInstaller"] + args
    print("[>] Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)


def build_game_binary(dist_dir: str, work_tag: str, icon_path: str = "", windowed: bool = True) -> str:
    os.makedirs(dist_dir, exist_ok=True)
    os.makedirs(BUILD_WORK_DIR, exist_ok=True)
    os.makedirs(SPEC_DIR, exist_ok=True)

    entry = os.path.join(GAME_DIR, "main.py")
    args = [
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        "DarkVault",
        "--distpath",
        dist_dir,
        "--workpath",
        os.path.join(BUILD_WORK_DIR, work_tag),
        "--specpath",
        SPEC_DIR,
        "--paths",
        GAME_DIR,
        "--hidden-import",
        "PIL",
        "--hidden-import",
        "PIL.Image",
        "--hidden-import",
        "PIL.ImageFilter",
        "--hidden-import",
        "pygame",
        "--collect-data",
        "pygame",
    ]
    if windowed:
        args.append("--windowed")
    for mod in GAME_MODULES:
        args.extend(["--hidden-import", mod])
    if icon_path and os.path.exists(icon_path):
        args.extend(["--icon", icon_path])
    sep = ";" if sys.platform == "win32" else ":"
    if os.path.exists(ICON_PNG_PATH):
        args.extend(["--add-data", f"{ICON_PNG_PATH}{sep}."])
    preview_jpg = os.path.join(ROOT_DIR, "preview.jpg")
    if os.path.exists(preview_jpg):
        args.extend(["--add-data", f"{preview_jpg}{sep}."])
    shared_seeds = os.path.join(GAME_DIR, "shared_seeds.json")
    if os.path.exists(shared_seeds):
        args.extend(["--add-data", f"{shared_seeds}{sep}."])
    community_mods = os.path.join(GAME_DIR, "community_mods")
    if os.path.isdir(community_mods):
        args.extend(["--add-data", f"{community_mods}{sep}community_mods"])
    fonts_dir = os.path.join(GAME_DIR, "fonts")
    if os.path.isdir(fonts_dir):
        args.extend(["--add-data", f"{fonts_dir}{sep}fonts"])
    # Include readable .py source files for the in-game Mod & Source Browser
    for fname in sorted(os.listdir(GAME_DIR)):
        if fname.endswith(".py") and not fname.startswith("build_"):
            src_py = os.path.join(GAME_DIR, fname)
            if os.path.isfile(src_py):
                args.extend(["--add-data", f"{src_py}{sep}."])

    args.append(entry)
    run_pyinstaller(args)

    ext = ".exe" if sys.platform == "win32" else ""
    out_bin = os.path.join(dist_dir, f"DarkVault{ext}")
    if not os.path.exists(out_bin):
        raise FileNotFoundError(f"Expected output binary was not created: {out_bin}")
    print(f"[+] Built standalone game: {out_bin}")
    return out_bin
