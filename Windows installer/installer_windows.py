import base64
import os
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP_NAME = "DarkVault"
APP_TITLE_RU = "Подземелье Тьмы · DarkVault"
APP_TITLE_EN = "DarkVault · Dungeon of Gloom"
APP_VERSION = "1.0.0"
PUBLISHER = "DarkVault"
EXE_NAME = "DarkVault.exe"
ICON_NAME = "darkvault.ico"


def resource_path(relative_path: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    candidate = os.path.join(base, relative_path)
    if os.path.exists(candidate):
        return candidate
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)


def default_install_dir() -> str:
    local_app = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(local_app, "Programs", APP_NAME)


def get_desktop_dir() -> str:
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
            ) as key:
                val, _ = winreg.QueryValueEx(key, "Desktop")
                expanded = os.path.expandvars(val)
                if expanded and os.path.isdir(expanded):
                    return expanded
        except Exception:
            pass
    return os.path.join(os.path.expanduser("~"), "Desktop")


def _ps_single_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def create_windows_shortcut(
    target_exe: str,
    shortcut_path: str,
    icon_path: str = "",
    working_dir: str = "",
    description: str = "",
):
    if sys.platform != "win32":
        return
    os.makedirs(os.path.dirname(shortcut_path), exist_ok=True)
    work = working_dir or os.path.dirname(target_exe)
    lines = [
        "$WshShell = New-Object -ComObject WScript.Shell",
        f"$Shortcut = $WshShell.CreateShortcut({_ps_single_quote(shortcut_path)})",
        f"$Shortcut.TargetPath = {_ps_single_quote(target_exe)}",
        f"$Shortcut.WorkingDirectory = {_ps_single_quote(work)}",
        f"$Shortcut.Description = {_ps_single_quote(description)}",
    ]
    if icon_path and os.path.exists(icon_path):
        lines.append(f"$Shortcut.IconLocation = {_ps_single_quote(icon_path)}")
    lines.append("$Shortcut.Save()")
    ps_script = "; ".join(lines)
    encoded = base64.b64encode(ps_script.encode("utf-16le")).decode("ascii")
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded],
        check=False,
        creationflags=creation_flags,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def register_windows_uninstaller(install_dir: str, exe_path: str, uninstall_bat: str, icon_path: str):
    if sys.platform != "win32":
        return
    try:
        import winreg

        key_path = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_NAME}"
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE) as key:
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_TITLE_RU)
            winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, APP_VERSION)
            winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, PUBLISHER)
            winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, install_dir)
            winreg.SetValueEx(
                key, "DisplayIcon", 0, winreg.REG_SZ, icon_path if os.path.exists(icon_path) else exe_path
            )
            winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, f'"{uninstall_bat}"')
            winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
    except Exception:
        pass


def write_uninstaller_bat(install_dir: str, desktop_lnk: str, start_menu_dir: str) -> str:
    uninstall_path = os.path.join(install_dir, "Uninstall_DarkVault.bat")
    lines = [
        "@echo off",
        "chcp 65001 >nul",
        "echo Удаление Подземелье Тьмы · DarkVault...",
        'cd /d "%TEMP%"',
        f'if exist "{desktop_lnk}" del /f /q "{desktop_lnk}"',
        f'if exist "{start_menu_dir}" rmdir /s /q "{start_menu_dir}"',
        f'reg delete "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{APP_NAME}" /f >nul 2>&1',
        'set "CLEANUP=%TEMP%\\darkvault_cleanup.bat"',
        'echo @echo off > "%CLEANUP%"',
        'echo timeout /t 2 /nobreak ^>nul >> "%CLEANUP%"',
        f'echo rmdir /s /q "{install_dir}" >> "%CLEANUP%"',
        'echo del /f /q "%CLEANUP%" >> "%CLEANUP%"',
        'start "" /b cmd /c "%CLEANUP%"',
        "exit /b 0",
    ]
    with open(uninstall_path, "w", encoding="utf-8", newline="\r\n") as fh:
        fh.write("\n".join(lines) + "\n")
    return uninstall_path


class DarkVaultInstaller(tk.Tk):
    def __init__(self):
        super().__init__()
        self.lang = "ru"
        self.title(APP_TITLE_RU)
        self.geometry("600x430")
        self.resizable(False, False)
        self.configure(bg="#0b0b0b")

        ico = resource_path(ICON_NAME)
        if os.path.exists(ico):
            try:
                self.iconbitmap(ico)
            except Exception:
                pass

        self.install_dir_var = tk.StringVar(value=default_install_dir())
        self.desktop_var = tk.BooleanVar(value=True)
        self.start_menu_var = tk.BooleanVar(value=True)
        self.launch_var = tk.BooleanVar(value=True)
        self.installed_exe_path = ""
        self.is_installing = False
        self.is_done = False

        self._setup_styles()
        self._build_ui()
        self._refresh_texts()

    def _setup_styles(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(
            "Dark.Horizontal.TProgressbar",
            troughcolor="#1a1a1a",
            background="#e8e8e8",
            bordercolor="#363636",
            lightcolor="#ffffff",
            darkcolor="#c8c8c8",
        )

    def _build_ui(self):
        header = tk.Frame(self, bg="#141414", height=78, highlightbackground="#333333", highlightthickness=1)
        header.pack(fill="x", padx=16, pady=(16, 10))
        header.pack_propagate(False)

        left_hdr = tk.Frame(header, bg="#141414")
        left_hdr.pack(side="left", fill="y", padx=16, pady=12)

        self.lbl_title = tk.Label(
            left_hdr, text="", bg="#141414", fg="#f5f5f5", font=("Segoe UI", 15, "bold"), anchor="w"
        )
        self.lbl_title.pack(anchor="w")

        self.lbl_sub = tk.Label(
            left_hdr, text="", bg="#141414", fg="#a0a0a0", font=("Segoe UI", 9), anchor="w"
        )
        self.lbl_sub.pack(anchor="w", pady=(2, 0))

        self.btn_lang = tk.Button(
            header,
            text="EN / RU",
            command=self._toggle_lang,
            bg="#222222",
            fg="#e5e5e5",
            activebackground="#323232",
            activeforeground="#ffffff",
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            padx=10,
            pady=4,
            cursor="hand2",
        )
        self.btn_lang.pack(side="right", padx=14)

        body = tk.Frame(self, bg="#111111", highlightbackground="#2c2c2c", highlightthickness=1)
        body.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        self.lbl_path = tk.Label(body, text="", bg="#111111", fg="#d8d8d8", font=("Segoe UI", 10, "bold"), anchor="w")
        self.lbl_path.pack(fill="x", padx=16, pady=(16, 6))

        path_row = tk.Frame(body, bg="#111111")
        path_row.pack(fill="x", padx=16)

        self.entry_path = tk.Entry(
            path_row,
            textvariable=self.install_dir_var,
            bg="#1b1b1b",
            fg="#f2f2f2",
            insertbackground="#ffffff",
            relief="flat",
            highlightbackground="#3e3e3e",
            highlightthickness=1,
            font=("Consolas", 9),
        )
        self.entry_path.pack(side="left", fill="x", expand=True, ipady=6)

        self.btn_browse = tk.Button(
            path_row,
            text="",
            command=self._browse_dir,
            bg="#242424",
            fg="#f0f0f0",
            activebackground="#353535",
            activeforeground="#ffffff",
            relief="flat",
            font=("Segoe UI", 9),
            padx=12,
            pady=5,
            cursor="hand2",
        )
        self.btn_browse.pack(side="left", padx=(8, 0))

        opts = tk.Frame(body, bg="#111111")
        opts.pack(fill="x", padx=16, pady=(16, 8))

        self.chk_desktop = tk.Checkbutton(
            opts,
            text="",
            variable=self.desktop_var,
            bg="#111111",
            fg="#e0e0e0",
            selectcolor="#1d1d1d",
            activebackground="#111111",
            activeforeground="#ffffff",
            font=("Segoe UI", 9),
            anchor="w",
        )
        self.chk_desktop.pack(fill="x", pady=2)

        self.chk_start = tk.Checkbutton(
            opts,
            text="",
            variable=self.start_menu_var,
            bg="#111111",
            fg="#e0e0e0",
            selectcolor="#1d1d1d",
            activebackground="#111111",
            activeforeground="#ffffff",
            font=("Segoe UI", 9),
            anchor="w",
        )
        self.chk_start.pack(fill="x", pady=2)

        self.chk_launch = tk.Checkbutton(
            opts,
            text="",
            variable=self.launch_var,
            bg="#111111",
            fg="#e0e0e0",
            selectcolor="#1d1d1d",
            activebackground="#111111",
            activeforeground="#ffffff",
            font=("Segoe UI", 9),
            anchor="w",
        )
        self.chk_launch.pack(fill="x", pady=2)

        self.lbl_status = tk.Label(body, text="", bg="#111111", fg="#9a9a9a", font=("Segoe UI", 9), anchor="w")
        self.lbl_status.pack(fill="x", padx=16, pady=(14, 4))

        self.progress = ttk.Progressbar(
            body, style="Dark.Horizontal.TProgressbar", orient="horizontal", mode="determinate", maximum=100
        )
        self.progress.pack(fill="x", padx=16, pady=(0, 12))

        footer = tk.Frame(self, bg="#0b0b0b")
        footer.pack(fill="x", padx=16, pady=(0, 16))

        self.btn_cancel = tk.Button(
            footer,
            text="",
            command=self.destroy,
            bg="#1c1c1c",
            fg="#d0d0d0",
            activebackground="#2c2c2c",
            activeforeground="#ffffff",
            relief="flat",
            font=("Segoe UI", 10),
            padx=16,
            pady=7,
            cursor="hand2",
        )
        self.btn_cancel.pack(side="left")

        self.btn_install = tk.Button(
            footer,
            text="",
            command=self._on_action_click,
            bg="#ececec",
            fg="#0b0b0b",
            activebackground="#ffffff",
            activeforeground="#000000",
            relief="flat",
            font=("Segoe UI", 10, "bold"),
            padx=22,
            pady=7,
            cursor="hand2",
        )
        self.btn_install.pack(side="right")

    def _toggle_lang(self):
        self.lang = "en" if self.lang == "ru" else "ru"
        self._refresh_texts()

    def _refresh_texts(self):
        ru = self.lang == "ru"
        self.title(APP_TITLE_RU if ru else APP_TITLE_EN)
        self.lbl_title.config(text=APP_TITLE_RU if ru else APP_TITLE_EN)
        self.lbl_sub.config(
            text=f"Установщик Windows · Версия {APP_VERSION}" if ru else f"Windows Installer · Version {APP_VERSION}"
        )
        self.lbl_path.config(text="Папка установки:" if ru else "Installation folder:")
        self.btn_browse.config(text="Обзор..." if ru else "Browse...")
        self.chk_desktop.config(text="Создать ярлык на Рабочем столе" if ru else "Create Desktop shortcut")
        self.chk_start.config(text="Добавить ярлык в меню «Пуск»" if ru else "Add Start Menu shortcut")
        self.chk_launch.config(text="Запустить игру после установки" if ru else "Launch DarkVault after installation")
        self.btn_cancel.config(text="Закрыть" if self.is_done else ("Отмена" if ru else "Cancel"))
        if self.is_done:
            self.btn_install.config(text="Играть!" if ru else "Play Now!")
            self.lbl_status.config(
                text="Установка успешно завершена. Игра готова к запуску!"
                if ru
                else "Installation complete. Ready to play!"
            )
        elif self.is_installing:
            self.btn_install.config(text="Установка..." if ru else "Installing...")
        else:
            self.btn_install.config(text="Установить игру" if ru else "Install Game")
            self.lbl_status.config(
                text="Нажмите «Установить игру», чтобы распаковать DarkVault на компьютер."
                if ru
                else "Click 'Install Game' to install DarkVault on your PC."
            )

    def _browse_dir(self):
        chosen = filedialog.askdirectory(initialdir=self.install_dir_var.get())
        if chosen:
            if os.path.basename(chosen).lower() != APP_NAME.lower():
                chosen = os.path.join(chosen, APP_NAME)
            self.install_dir_var.set(chosen)

    def _on_action_click(self):
        if self.is_done:
            self._launch_game_and_exit()
            return
        if self.is_installing:
            return
        self.is_installing = True
        self.btn_install.config(state="disabled")
        self.btn_browse.config(state="disabled")
        self.entry_path.config(state="disabled")
        self._refresh_texts()
        threading.Thread(target=self._run_install, daemon=True).start()

    def _set_progress(self, value: int, msg_ru: str, msg_en: str):
        def _upd():
            self.progress["value"] = value
            self.lbl_status.config(text=msg_ru if self.lang == "ru" else msg_en)

        self.after(0, _upd)

    def _run_install(self):
        try:
            target_dir = self.install_dir_var.get().strip() or default_install_dir()
            os.makedirs(target_dir, exist_ok=True)
            self._set_progress(15, "Подготовка файлов...", "Preparing files...")

            src_exe = resource_path(EXE_NAME)
            if not os.path.exists(src_exe):
                raise FileNotFoundError(f"Embedded {EXE_NAME} not found at {src_exe}")

            dst_exe = os.path.join(target_dir, EXE_NAME)
            self._set_progress(35, f"Копирование {EXE_NAME}...", f"Copying {EXE_NAME}...")
            shutil.copy2(src_exe, dst_exe)

            src_ico = resource_path(ICON_NAME)
            dst_ico = os.path.join(target_dir, ICON_NAME)
            if os.path.exists(src_ico):
                shutil.copy2(src_ico, dst_ico)

            desktop_dir = get_desktop_dir()
            desktop_lnk = os.path.join(desktop_dir, f"{APP_NAME}.lnk")
            start_menu_root = os.path.join(
                os.environ.get("APPDATA", os.path.expanduser("~")),
                "Microsoft",
                "Windows",
                "Start Menu",
                "Programs",
                APP_NAME,
            )
            start_lnk = os.path.join(start_menu_root, f"{APP_NAME}.lnk")

            self._set_progress(65, "Создание ярлыков...", "Creating shortcuts...")
            if self.desktop_var.get():
                create_windows_shortcut(
                    dst_exe, desktop_lnk, dst_ico, target_dir, "Подземелье Тьмы · DarkVault"
                )
            if self.start_menu_var.get():
                create_windows_shortcut(
                    dst_exe, start_lnk, dst_ico, target_dir, "Подземелье Тьмы · DarkVault"
                )

            self._set_progress(85, "Регистрация в Windows...", "Registering uninstaller...")
            uninstall_bat = write_uninstaller_bat(target_dir, desktop_lnk, start_menu_root)
            if self.start_menu_var.get():
                create_windows_shortcut(
                    uninstall_bat,
                    os.path.join(start_menu_root, "Удалить DarkVault.lnk"),
                    dst_ico,
                    target_dir,
                    "Uninstall DarkVault",
                )
            register_windows_uninstaller(target_dir, dst_exe, uninstall_bat, dst_ico)

            self.installed_exe_path = dst_exe
            self._set_progress(100, "Готово!", "Done!")

            def _finish():
                self.is_installing = False
                self.is_done = True
                self.btn_install.config(state="normal")
                self._refresh_texts()
                if self.launch_var.get():
                    self._launch_game_and_exit()

            self.after(200, _finish)
        except Exception as exc:
            def _err():
                self.is_installing = False
                self.btn_install.config(state="normal")
                self.btn_browse.config(state="normal")
                self.entry_path.config(state="normal")
                self._refresh_texts()
                messagebox.showerror("DarkVault Setup Error", str(exc))

            self.after(0, _err)

    def _launch_game_and_exit(self):
        if self.installed_exe_path and os.path.exists(self.installed_exe_path):
            try:
                subprocess.Popen([self.installed_exe_path], cwd=os.path.dirname(self.installed_exe_path))
            except Exception:
                pass
        self.destroy()


if __name__ == "__main__":
    app = DarkVaultInstaller()
    app.mainloop()
