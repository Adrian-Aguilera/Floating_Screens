def main() -> None:
    import sys

    if sys.platform != "win32":
        raise SystemExit("Floating Screens requiere Windows.")

    import tkinter as tk

    from .ui.main_window import MainWindow

    root = tk.Tk()
    MainWindow(root)
    root.mainloop()
