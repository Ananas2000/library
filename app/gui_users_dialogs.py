import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Dict, Any


class RegisterLibrarianDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Регистрация нового библиотекаря")
        self.resizable(False, False)
        self.result: Optional[Dict[str, Any]] = None

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Фамилия:").grid(row=0, column=0, sticky="w")
        ttk.Label(frm, text="Имя:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Label(frm, text="Отчество:").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Label(frm, text="Телефон:").grid(row=3, column=0, sticky="w", pady=(8, 0))
        ttk.Label(frm, text="(формат +7xxxxxxxxxx)").grid(row=4, column=1, sticky="w", padx=(8, 0), pady=(2, 0))
        ttk.Label(frm, text="Логин:").grid(row=5, column=0, sticky="w", pady=(8, 0))
        ttk.Label(frm, text="Пароль:").grid(row=6, column=0, sticky="w", pady=(8, 0))

        self.last_name_var = tk.StringVar()
        self.first_name_var = tk.StringVar()
        self.patronymic_var = tk.StringVar()
        self.phone_var = tk.StringVar()
        self.login_var = tk.StringVar()
        self.pass_var = tk.StringVar()

        ttk.Entry(frm, textvariable=self.last_name_var, width=38).grid(row=0, column=1, sticky="w", padx=(8, 0))
        ttk.Entry(frm, textvariable=self.first_name_var, width=38).grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        ttk.Entry(frm, textvariable=self.patronymic_var, width=38).grid(row=2, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        ttk.Entry(frm, textvariable=self.phone_var, width=38).grid(row=3, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        ttk.Entry(frm, textvariable=self.login_var, width=38).grid(row=5, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        ttk.Entry(frm, textvariable=self.pass_var, show="*", width=38).grid(row=6, column=1, sticky="w", padx=(8, 0), pady=(8, 0))

        btns = ttk.Frame(frm)
        btns.grid(row=7, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Отмена", command=self._cancel).pack(side="right")
        ttk.Button(btns, text="Создать", command=self._ok).pack(side="right", padx=(0, 8))

        self.grab_set()
        self.transient(parent)
        self.wait_visibility()
        self.focus_set()

    def _ok(self):
        last_name = self.last_name_var.get().strip()
        first_name = self.first_name_var.get().strip()
        patronymic = self.patronymic_var.get().strip()
        login = self.login_var.get().strip()
        password = self.pass_var.get()

        if not last_name or not first_name or not login or not password:
            messagebox.showwarning("Ошибка", "Заполни фамилию, имя, логин и пароль.")
            return
        if len(password) < 4:
            messagebox.showwarning("Ошибка", "Пароль минимум 4 символа.")
            return

        full_name = f"{last_name} {first_name}" + (f" {patronymic}" if patronymic else "")

        self.result = {
            "full_name": full_name,
            "phone": self.phone_var.get().strip() or None,
            "login": login,
            "password": password,
        }
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


class EditUserDialog(tk.Toplevel):
    def __init__(self, parent, initial_full_name: str, initial_phone: str):
        super().__init__(parent)
        self.title("Редактировать пользователя")
        self.resizable(False, False)
        self.result: Optional[Dict[str, Any]] = None

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        parts = (initial_full_name or "").split()
        init_last = parts[0] if len(parts) >= 1 else ""
        init_first = parts[1] if len(parts) >= 2 else ""
        init_pat = " ".join(parts[2:]) if len(parts) >= 3 else ""

        ttk.Label(frm, text="Фамилия:").grid(row=0, column=0, sticky="w")
        ttk.Label(frm, text="Имя:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Label(frm, text="Отчество:").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Label(frm, text="Телефон:").grid(row=3, column=0, sticky="w", pady=(8, 0))
        ttk.Label(frm, text="(формат +7xxxxxxxxxx)").grid(row=4, column=1, sticky="w", padx=(8, 0), pady=(2, 0))

        self.last_name_var = tk.StringVar(value=init_last)
        self.first_name_var = tk.StringVar(value=init_first)
        self.patronymic_var = tk.StringVar(value=init_pat)
        self.phone_var = tk.StringVar(value=initial_phone or "")

        ttk.Entry(frm, textvariable=self.last_name_var, width=42).grid(row=0, column=1, sticky="w", padx=(8, 0))
        ttk.Entry(frm, textvariable=self.first_name_var, width=42).grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        ttk.Entry(frm, textvariable=self.patronymic_var, width=42).grid(row=2, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        ttk.Entry(frm, textvariable=self.phone_var, width=42).grid(row=3, column=1, sticky="w", padx=(8, 0), pady=(8, 0))

        btns = ttk.Frame(frm)
        btns.grid(row=5, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Отмена", command=self._cancel).pack(side="right")
        ttk.Button(btns, text="Сохранить", command=self._ok).pack(side="right", padx=(0, 8))

        self.grab_set()
        self.transient(parent)
        self.wait_visibility()
        self.focus_set()

    def _ok(self):
        last_name = self.last_name_var.get().strip()
        first_name = self.first_name_var.get().strip()
        patronymic = self.patronymic_var.get().strip()
        phone = self.phone_var.get().strip() or None
        if not last_name or not first_name:
            messagebox.showwarning("Ошибка", "Фамилия/имя пустые.")
            return

        full_name = f"{last_name} {first_name}" + (f" {patronymic}" if patronymic else "")
        self.result = {"full_name": full_name, "phone": phone}
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


class ResetPasswordDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Сброс пароля")
        self.resizable(False, False)
        self.result: Optional[str] = None

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Новый пароль:").grid(row=0, column=0, sticky="w")
        ttk.Label(frm, text="Повтори:").grid(row=1, column=0, sticky="w", pady=(8, 0))

        self.p1 = tk.StringVar()
        self.p2 = tk.StringVar()

        ttk.Entry(frm, textvariable=self.p1, show="*", width=30).grid(row=0, column=1, sticky="w", padx=(8, 0))
        ttk.Entry(frm, textvariable=self.p2, show="*", width=30).grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(8, 0))

        btns = ttk.Frame(frm)
        btns.grid(row=2, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Отмена", command=self._cancel).pack(side="right")
        ttk.Button(btns, text="OK", command=self._ok).pack(side="right", padx=(0, 8))

        self.grab_set()
        self.transient(parent)
        self.wait_visibility()
        self.focus_set()

    def _ok(self):
        a = self.p1.get()
        b = self.p2.get()
        if not a or len(a) < 4:
            messagebox.showwarning("Ошибка", "Пароль минимум 4 символа.")
            return
        if a != b:
            messagebox.showwarning("Ошибка", "Пароли не совпадают.")
            return
        self.result = a
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()
