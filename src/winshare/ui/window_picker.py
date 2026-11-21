"""Choose an open desktop window by its title."""

import tkinter as tk
from tkinter import ttk

from ..display.windows import open_windows


def choose_window(parent):
    dialog = tk.Toplevel(parent)
    dialog.title("Elegir ventana abierta")
    dialog.transient(parent)
    dialog.minsize(440, 260)
    body = ttk.Frame(dialog, padding=14)
    body.pack(fill="both", expand=True)
    ttk.Label(body, text="Selecciona la ventana que quieres compartir.").pack(anchor="w")
    table = ttk.Frame(body)
    table.pack(fill="both", expand=True, pady=8)
    items = tk.Listbox(table, exportselection=False, height=8)
    items.pack(side="left", fill="both", expand=True)
    scroll = ttk.Scrollbar(table, command=items.yview)
    scroll.pack(side="right", fill="y")
    items.configure(yscrollcommand=scroll.set)
    status = ttk.Label(body)
    status.pack(anchor="w")
    actions = ttk.Frame(body)
    actions.pack(fill="x", pady=(8, 0))

    candidates = []
    selected = None

    def update_button(_event=None):
        share.configure(state="normal" if items.curselection() else "disabled")

    def refresh():
        index = items.curselection()
        previous = candidates[index[0]][0] if index else None
        candidates[:] = open_windows()
        items.delete(0, tk.END)
        for hwnd, title in candidates:
            items.insert(tk.END, title)
            if hwnd == previous:
                items.selection_set(tk.END)
                items.see(tk.END)
        status.configure(text="" if candidates else "No hay ventanas disponibles. Abre una y pulsa Actualizar.")
        update_button()

    def accept(_event=None):
        nonlocal selected
        index = items.curselection()
        if index:
            selected = candidates[index[0]][0]
            dialog.destroy()

    ttk.Button(actions, text="Actualizar", command=refresh).pack(side="left")
    share = ttk.Button(actions, text="Compartir", command=accept)
    share.pack(side="right")
    items.bind("<<ListboxSelect>>", update_button)
    items.bind("<Double-Button-1>", accept)
    dialog.bind("<Return>", accept)
    dialog.bind("<Escape>", lambda _event: dialog.destroy())
    refresh()
    dialog.grab_set()
    items.focus_set()
    dialog.wait_window()
    return selected
