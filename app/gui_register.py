import tkinter as tk
from tkinter import ttk, messagebox

from app.services import register_self


class RegisterWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Регистрация читателя")
        self.resizable(False, False)

        self.result_login = None

        frm = ttk.Frame(self, padding=16)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Фамилия:").grid(row=0, column=0, sticky="w")
        ttk.Label(frm, text="Имя:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Label(frm, text="Отчество:").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Label(frm, text="Телефон:").grid(row=3, column=0, sticky="w", pady=(8, 0))
        ttk.Label(frm, text="(формат +7xxxxxxxxxx)").grid(row=4, column=1, sticky="w", padx=(8, 0), pady=(2, 0))
        ttk.Label(frm, text="Логин:").grid(row=5, column=0, sticky="w", pady=(8, 0))
        ttk.Label(frm, text="Пароль:").grid(row=6, column=0, sticky="w", pady=(8, 0))
        ttk.Label(frm, text="Повтори пароль:").grid(row=7, column=0, sticky="w", pady=(8, 0))

        self.last_name_var = tk.StringVar()
        self.first_name_var = tk.StringVar()
        self.patronymic_var = tk.StringVar()
        self.phone_var = tk.StringVar()
        self.login_var = tk.StringVar()
        self.pass1_var = tk.StringVar()
        self.pass2_var = tk.StringVar()

        ttk.Entry(frm, textvariable=self.last_name_var, width=34).grid(row=0, column=1, sticky="w", padx=(8, 0))
        ttk.Entry(frm, textvariable=self.first_name_var, width=34).grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        ttk.Entry(frm, textvariable=self.patronymic_var, width=34).grid(row=2, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        ttk.Entry(frm, textvariable=self.phone_var, width=34).grid(row=3, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        ttk.Entry(frm, textvariable=self.login_var, width=34).grid(row=5, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        ttk.Entry(frm, textvariable=self.pass1_var, show="*", width=34).grid(row=6, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        ttk.Entry(frm, textvariable=self.pass2_var, show="*", width=34).grid(row=7, column=1, sticky="w", padx=(8, 0), pady=(8, 0))

        btns = ttk.Frame(frm)
        btns.grid(row=8, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Отмена", command=self._cancel).pack(side="right")
        ttk.Button(btns, text="Создать", command=self._do_register).pack(side="right", padx=(0, 8))

        self.grab_set()
        self.transient(parent)
        self.wait_visibility()
        self.focus_set()

        self.bind("<Return>", lambda e: self._do_register())
        self.bind("<Escape>", lambda e: self._cancel())

    def _do_register(self):
        last_name = self.last_name_var.get().strip()
        first_name = self.first_name_var.get().strip()
        patronymic = self.patronymic_var.get().strip()
        phone = self.phone_var.get().strip() or None

        login = self.login_var.get().strip()
        p1 = self.pass1_var.get()
        p2 = self.pass2_var.get()

        if not last_name or not first_name or not login or not p1:
            messagebox.showwarning("Ошибка", "Заполните фамилию, имя, логин и пароль.")
            return
        if p1 != p2:
            messagebox.showwarning("Ошибка", "Пароли не совпадают.")
            return

        full_name = f"{last_name} {first_name}" + (f" {patronymic}" if patronymic else "")

        ok, msg = register_self(login=login, full_name=full_name, phone=phone, password=p1)
        if not ok:
            messagebox.showerror("Ошибка", msg)
            return

        messagebox.showinfo("Готово", msg)
        self.result_login = login
        self.destroy()

    def _cancel(self):
        self.result_login = None
        self.destroy()
