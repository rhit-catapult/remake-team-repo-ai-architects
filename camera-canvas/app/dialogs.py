"""Shared native file-picker helper (tkinter, hidden root)."""


def open_file_dialog(title="Choose an image"):
    """Returns the chosen path, or None if cancelled / unavailable."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        path = filedialog.askopenfilename(
            title=title,
            filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp *.webp")])
        root.update()
        root.destroy()
        return path or None
    except Exception as exc:
        print(f"[dialogs] file dialog unavailable ({exc}); use drag-and-drop instead")
        return None
