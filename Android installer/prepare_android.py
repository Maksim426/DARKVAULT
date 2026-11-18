import argparse
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(HERE)
GAME_DIR = os.path.join(ROOT_DIR, "GAME")
DIST_ANDROID = os.path.join(ROOT_DIR, "dist", "android")
APK_MARKER_PATH = os.path.join(GAME_DIR, "android_build.json")
if GAME_DIR not in sys.path:
    sys.path.insert(0, GAME_DIR)

from build_common import _render_emblem_image


def generate_android_assets():
    try:
        from PIL import Image, ImageDraw, ImageFilter
    except ImportError:
        print("[!] Pillow is not installed, skipping Android icon/presplash generation.")
        return

    icon_path = os.path.join(GAME_DIR, "darkvault.png")
    emblem = _render_emblem_image(256).resize((512, 512), Image.Resampling.LANCZOS)
    emblem.save(icon_path, format="PNG")
    print(f"[+] Generated Android icon (512x512): {icon_path}")

    presplash_path = os.path.join(GAME_DIR, "darkvault_presplash.jpg")
    preview_jpg = os.path.join(ROOT_DIR, "preview.jpg")
    canvas = Image.new("RGBA", (1280, 720), (5, 5, 5, 255))
    if os.path.exists(preview_jpg):
        try:
            pv = Image.open(preview_jpg).convert("RGBA")
            pv.thumbnail((1120, 560), Image.Resampling.LANCZOS)
            mask = Image.new("L", pv.size, 0)
            draw = ImageDraw.Draw(mask)
            pad_x = max(24, min(48, pv.width // 10))
            pad_y = max(24, min(48, pv.height // 8))
            draw.rounded_rectangle(
                [pad_x, pad_y, pv.width - pad_x, pv.height - pad_y],
                radius=28,
                fill=255,
            )
            mask = mask.filter(ImageFilter.GaussianBlur(24))
            pv.putalpha(mask)
            px = (1280 - pv.width) // 2
            py = (720 - pv.height) // 2
            canvas.paste(pv, (px, py), pv)
        except Exception:
            canvas.paste(emblem, ((1280 - emblem.width) // 2, (720 - emblem.height) // 2), emblem)
    else:
        canvas.paste(emblem, ((1280 - emblem.width) // 2, (720 - emblem.height) // 2), emblem)
    canvas.convert("RGB").save(presplash_path, format="JPEG", quality=92, optimize=True)
    print(f"[+] Generated Android presplash (1280x720 JPEG): {presplash_path}")

    legacy_png = os.path.join(GAME_DIR, "darkvault_presplash.png")
    if os.path.exists(legacy_png):
        os.remove(legacy_png)

    apk_profile = {
        "target": "android_apk",
        "fullscreen": True,
        "ui_scale": "phone",
        "touch_controls": "on",
        "wide_mode": "auto",
    }
    with open(APK_MARKER_PATH, "w", encoding="utf-8") as mf:
        json.dump(apk_profile, mf, indent=2)
    print(f"[+] Generated APK-bound phone profile marker: {APK_MARKER_PATH}")


def collect_apks():
    apks = []
    candidate_dirs = [
        os.path.join(ROOT_DIR, "bin"),
        os.path.join(HERE, "bin"),
    ]
    for cdir in candidate_dirs:
        if os.path.isdir(cdir):
            for file in sorted(os.listdir(cdir)):
                if file.endswith(".apk") and "unpacked" not in file and "unsigned" not in file:
                    apks.append(os.path.join(cdir, file))
    if not apks:
        for root, dirs, files in os.walk(ROOT_DIR):
            dirs[:] = [d for d in dirs if d not in (".buildozer", "dist", ".git", "node_modules", ".build_venv_android")]
            for file in files:
                if file.endswith(".apk") and "unpacked" not in file and "unsigned" not in file:
                    apks.append(os.path.join(root, file))
    if not apks:
        # Fallback to any apk
        for root, dirs, files in os.walk(ROOT_DIR):
            dirs[:] = [d for d in dirs if d not in (".buildozer", "dist", ".git", "node_modules", ".build_venv_android")]
            for file in files:
                if file.endswith(".apk"):
                    apks.append(os.path.join(root, file))

    apks = sorted(set(apks))
    print(f"[+] Found APK files: {apks}")
    if not apks:
        raise FileNotFoundError(f"No .apk files found under {ROOT_DIR}")

    os.makedirs(DIST_ANDROID, exist_ok=True)
    for stale in os.listdir(DIST_ANDROID):
        if stale.endswith(".apk"):
            os.remove(os.path.join(DIST_ANDROID, stale))

    # Take the latest built APK directly as signed by Buildozer/Gradle
    latest = apks[-1]
    dest_clean = os.path.join(DIST_ANDROID, "DarkVault.apk")
    shutil.copy2(latest, dest_clean)

    # Verify zip integrity
    res = subprocess.run(["unzip", "-tq", dest_clean], capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"APK zip integrity check failed:\n{res.stdout}\n{res.stderr}")
    print(f"[+] APK zip integrity verified successfully: {dest_clean} ({os.path.getsize(dest_clean)} bytes)")

    if os.path.exists(APK_MARKER_PATH):
        try:
            os.remove(APK_MARKER_PATH)
        except OSError:
            pass


def main():
    parser = argparse.ArgumentParser(description="Prepare DarkVault Android assets and collect built .apk files.")
    parser.add_argument("--assets-only", action="store_true", help="Only generate icon and presplash assets")
    parser.add_argument("--collect-only", action="store_true", help="Only copy built APK from bin/ to dist/android/")
    args = parser.parse_args()

    if not args.collect_only:
        generate_android_assets()
    if not args.assets_only:
        collect_apks()


if __name__ == "__main__":
    main()
