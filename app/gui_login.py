import tkinter as tk
from tkinter import ttk, messagebox

from app.services import authenticate
from app.gui_register import RegisterWindow


class LoginWindow(tk.Tk):
    def __init__(self, on_success):
        super().__init__()
        self.title("Библиотека — вход")
        self.geometry("390x240")
        self.resizable(False, False)
        self.on_success = on_success

        frm = ttk.Frame(self, padding=16)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Логин:").grid(row=0, column=0, sticky="w")
        ttk.Label(frm, text="Пароль:").grid(row=1, column=0, sticky="w", pady=(8, 0))

        self.login_var = tk.StringVar()
        self.pass_var = tk.StringVar()

        e1 = ttk.Entry(frm, textvariable=self.login_var)
        e2 = ttk.Entry(frm, textvariable=self.pass_var, show="*")
        e1.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        e2.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        frm.columnconfigure(1, weight=1)

        btnrow = ttk.Frame(frm)
        btnrow.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        btnrow.columnconfigure(0, weight=1)
        btnrow.columnconfigure(1, weight=1)

        ttk.Button(btnrow, text="Войти", command=self._do_login).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(btnrow, text="Регистрация читателя", command=self._open_register).grid(row=0, column=1, sticky="ew", padx=(6, 0))

        self.bind("<Return>", lambda e: self._do_login())
        e1.focus_set()

    def _open_register(self):
        dlg = RegisterWindow(self)
        self.wait_window(dlg)
        if dlg.result_login:
            self.login_var.set(dlg.result_login)
            self.pass_var.set("")
            messagebox.showinfo("Ок", "Читатель создан.")

    def _do_login(self):
        ok, msg, session = authenticate(self.login_var.get(), self.pass_var.get())
        if not ok or session is None:
            messagebox.showerror("Ошибка", msg)
            return
        self.destroy()
        self.on_success(session)
