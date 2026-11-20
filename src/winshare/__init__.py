def main() -> None:
    import sys

    if sys.platform != "win32":
        raise SystemExit("Floating Screens requiere Windows.")

    import tkinter as tk

    from .display.windows import enable_dpi_awareness
    from .ui.main_window import MainWindow

    enable_dpi_awareness()
    root = tk.Tk()
    MainWindow(root)
    root.mainloop()
