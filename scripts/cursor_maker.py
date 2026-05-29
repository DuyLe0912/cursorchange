import ctypes
import os
import sys
import traceback
import winreg
from pathlib import Path
from tkinter import (
    BooleanVar,
    Button,
    Checkbutton,
    END,
    Frame,
    HORIZONTAL,
    Label,
    Listbox,
    Radiobutton,
    Scale,
    Scrollbar,
    SINGLE,
    StringVar,
    Tk,
    filedialog,
    messagebox,
)
from tkinter import ttk

from PIL import Image, ImageTk

from img_to_cur import image_to_cur


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


COLLECTION_DIR = app_dir().parent / "cur collection"
SUPPORTED = [
    ("Images", "*.png *.webp *.jpg *.jpeg *.bmp *.gif *.tiff"),
    ("All files", "*.*"),
]

SPI_SETCURSORS = 0x0057
SPIF_UPDATEINIFILE = 0x0001
SPIF_SENDCHANGE = 0x0002

# Display label -> registry value name under Control Panel\Cursors
CURSOR_ROLES = {"Normal Select": "Arrow", "Link Select": "Hand"}


def _role_label(value: str) -> str:
    for label, val in CURSOR_ROLES.items():
        if val == value:
            return label
    return value


def apply_cursor(cur_path: Path, role: str = "Arrow"):
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Control Panel\Cursors",
        0,
        winreg.KEY_SET_VALUE,
    ) as key:
        winreg.SetValueEx(key, role, 0, winreg.REG_EXPAND_SZ, str(cur_path))
    ctypes.windll.user32.SystemParametersInfoW(
        SPI_SETCURSORS, 0, None, SPIF_UPDATEINIFILE | SPIF_SENDCHANGE
    )


def build_role_selector(parent: Frame, var: StringVar) -> Frame:
    frame = Frame(parent)
    Label(frame, text="Apply to:", font=("Segoe UI", 9)).pack(side="left", padx=(0, 6))
    for label, value in CURSOR_ROLES.items():
        Radiobutton(frame, text=label, variable=var, value=value,
                    font=("Segoe UI", 9)).pack(side="left", padx=2)
    return frame


class BrowseTab:
    def __init__(self, parent: ttk.Notebook):
        self.frame = Frame(parent)
        self.preview_img = None
        self.selected_path: Path | None = None
        self._cur_files: list[Path] = []
        self.target = StringVar(value="Arrow")
        self._build()
        self.refresh()

    def _build(self):
        f = self.frame

        Label(f, text="Your cursor collection:", font=("Segoe UI", 10)).pack(
            pady=(12, 4), anchor="w", padx=16
        )

        list_frame = Frame(f)
        list_frame.pack(fill="both", expand=True, padx=16, pady=4)
        scrollbar = Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")
        self.listbox = Listbox(
            list_frame, yscrollcommand=scrollbar.set, selectmode=SINGLE,
            font=("Segoe UI", 10), height=7,
        )
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.listbox.yview)
        self.listbox.bind("<<ListboxSelect>>", self._on_select)

        self.preview = Label(f, text="No cursor selected", width=18, height=7,
                             relief="groove", bg="#f4f4f4", fg="#888")
        self.preview.pack(pady=8)

        build_role_selector(f, self.target).pack(pady=4)

        btn_frame = Frame(f)
        btn_frame.pack(pady=4)
        Button(btn_frame, text="Refresh", command=self.refresh, width=12).pack(
            side="left", padx=6
        )
        self.apply_btn = Button(
            btn_frame, text="Apply", command=self.apply, width=12,
            bg="#1a5fa8", fg="white", font=("Segoe UI", 10, "bold"), state="disabled",
        )
        self.apply_btn.pack(side="left", padx=6)

        self.status = StringVar(value="")
        Label(f, textvariable=self.status, font=("Segoe UI", 9), fg="#2d7d46",
              wraplength=360, justify="center").pack(pady=4)

    def refresh(self):
        self.listbox.delete(0, END)
        COLLECTION_DIR.mkdir(parents=True, exist_ok=True)
        self._cur_files = sorted(COLLECTION_DIR.glob("*.cur"))
        for p in self._cur_files:
            self.listbox.insert(END, p.name)
        self.selected_path = None
        self.apply_btn.config(state="disabled")
        self.preview.config(image="", text="No cursor selected", width=18, height=7)
        self.preview_img = None
        count = len(self._cur_files)
        self.status.set(f"{count} cursor{'s' if count != 1 else ''} in collection")

    def _on_select(self, _event):
        sel = self.listbox.curselection()
        if not sel:
            return
        self.selected_path = self._cur_files[sel[0]]
        self.apply_btn.config(state="normal")
        self._show_preview()

    def _show_preview(self):
        try:
            img = Image.open(self.selected_path).convert("RGBA")
            img = img.resize((96, 96), Image.LANCZOS)
            self.preview_img = ImageTk.PhotoImage(img)
            self.preview.config(image=self.preview_img, text="", width=96, height=96)
        except Exception:
            self.preview.config(image="", text="(no preview)", width=18, height=7)

    def apply(self):
        if not self.selected_path:
            return
        try:
            role_label = _role_label(self.target.get())
            apply_cursor(self.selected_path, self.target.get())
            self.status.set(f"Applied {self.selected_path.name} to {role_label}")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Apply failed", f"{type(e).__name__}: {e}")


class CreateTab:
    def __init__(self, parent: ttk.Notebook):
        self.frame = Frame(parent)
        self.input_path: Path | None = None
        self.last_output: Path | None = None
        self.preview_img = None
        self.target = StringVar(value="Arrow")
        self._build()

    def _build(self):
        f = self.frame

        self.preview = Label(f, text="No image selected", width=18, height=7,
                             relief="groove", bg="#f4f4f4", fg="#888")
        self.preview.pack(pady=(12, 6))

        Button(f, text="Choose Image…", command=self.choose_image,
               width=20).pack(pady=4)

        self.file_label = Label(f, text="", font=("Segoe UI", 8), fg="#777", wraplength=380)
        self.file_label.pack(pady=(0, 4))

        size_frame = Frame(f)
        size_frame.pack(pady=4)
        Label(size_frame, text="Cursor size (px):", font=("Segoe UI", 10)).pack(
            side="left", padx=(0, 8)
        )
        self.size_scale = Scale(size_frame, from_=16, to=256, orient=HORIZONTAL,
                                length=190, resolution=16)
        self.size_scale.set(64)
        self.size_scale.pack(side="left")

        self.center_hotspot = BooleanVar(value=True)
        Checkbutton(f, text="Center the click point (hotspot)",
                    variable=self.center_hotspot, font=("Segoe UI", 9)).pack(pady=2)

        Button(f, text="Convert to .cur", command=self.convert,
               width=24, height=2, bg="#2d7d46", fg="white",
               font=("Segoe UI", 11, "bold")).pack(pady=(10, 4))

        build_role_selector(f, self.target).pack(pady=(8, 0))

        self.apply_btn = Button(f, text="Apply as cursor", command=self.apply,
                                width=24, height=2, bg="#1a5fa8", fg="white",
                                font=("Segoe UI", 11, "bold"), state="disabled")
        self.apply_btn.pack(pady=4)

        self.status = StringVar(value="")
        Label(f, textvariable=self.status, font=("Segoe UI", 9), fg="#2d7d46",
              wraplength=380, justify="center").pack(pady=4)

    def choose_image(self):
        path = filedialog.askopenfilename(title="Choose an image", filetypes=SUPPORTED)
        if not path:
            return
        self.input_path = Path(path)
        self.file_label.config(text=str(self.input_path))
        self.status.set("")
        self.apply_btn.config(state="disabled")
        self._show_preview()

    def _show_preview(self):
        try:
            img = Image.open(self.input_path).convert("RGBA")
            img.thumbnail((112, 112), Image.LANCZOS)
            self.preview_img = ImageTk.PhotoImage(img)
            self.preview.config(image=self.preview_img, text="", width=112, height=112)
        except Exception:
            self.preview.config(image="", text="Can't preview", width=18, height=7)

    def convert(self):
        if not self.input_path:
            messagebox.showwarning("No image", "Please choose an image first.")
            return
        try:
            COLLECTION_DIR.mkdir(parents=True, exist_ok=True)
            size = int(self.size_scale.get())
            hotspot = size // 2 if self.center_hotspot.get() else 0
            output = COLLECTION_DIR / (self.input_path.stem + ".cur")
            image_to_cur(str(self.input_path), str(output), size=size,
                         hotspot_x=hotspot, hotspot_y=hotspot)
            self.last_output = output
            self.apply_btn.config(state="normal")
            self.status.set(f'Saved: {output.name}\nClick "Apply as cursor" to use it now.')
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Conversion failed", f"{type(e).__name__}: {e}")

    def apply(self):
        if not self.last_output or not self.last_output.exists():
            messagebox.showwarning("No cursor", "Convert an image first.")
            return
        try:
            role_label = _role_label(self.target.get())
            apply_cursor(self.last_output, self.target.get())
            self.status.set(f"Applied {self.last_output.name} to {role_label}\nYour cursor is now active!")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Apply failed", f"{type(e).__name__}: {e}")


class CursorMakerApp:
    def __init__(self, root: Tk):
        root.title("Cursor Maker")
        root.geometry("420x620")
        root.resizable(False, False)

        Label(root, text="Cursor Maker", font=("Segoe UI", 16, "bold")).pack(pady=(14, 6))

        notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True, padx=12, pady=4)

        self.browse_tab = BrowseTab(notebook)
        self.create_tab = CreateTab(notebook)

        notebook.add(self.browse_tab.frame, text="  Browse Collection  ")
        notebook.add(self.create_tab.frame, text="  Create New  ")

        # Refresh browse list whenever the user switches to that tab
        notebook.bind("<<NotebookTabChanged>>", lambda e: (
            self.browse_tab.refresh()
            if notebook.index(notebook.select()) == 0 else None
        ))

        Button(root, text="Open collection folder", command=self.open_folder,
               width=22, font=("Segoe UI", 8)).pack(side="bottom", pady=8)

    def open_folder(self):
        COLLECTION_DIR.mkdir(parents=True, exist_ok=True)
        os.startfile(COLLECTION_DIR)


if __name__ == "__main__":
    root = Tk()
    CursorMakerApp(root)
    root.mainloop()
