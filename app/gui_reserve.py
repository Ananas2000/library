import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, timedelta

from app.services_reservations import list_available_branches_for_book, create_reservation


class ReserveDialog(tk.Toplevel):
    def __init__(self, parent, reader_user, book_id: int, book_title: str):
        super().__init__(parent)
        self.title("Резерв книги")
        self.resizable(False, False)

        self.reader_user = reader_user
        self.book_id = book_id
        self.book_title = book_title
        self.result_ok = False

        frm = ttk.Frame(self, padding=14)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text=f"Книга: {book_title}").grid(row=0, column=0, columnspan=2, sticky="w")

        ttk.Label(frm, text="Филиал:").grid(row=1, column=0, sticky="w", pady=(10, 0))
        self.branch_var = tk.StringVar(value="")
        self.branch_cb = ttk.Combobox(frm, textvariable=self.branch_var, state="readonly", width=52)
        self.branch_cb.grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(10, 0))

        ttk.Label(frm, text="Дата прихода (YYYY-MM-DD):").grid(row=2, column=0, sticky="w", pady=(10, 0))
        self.date_var = tk.StringVar(value=str(date.today()))
        ttk.Entry(frm, textvariable=self.date_var, width=22).grid(row=2, column=1, sticky="w", padx=(8, 0), pady=(10, 0))

        hint = f"Можно выбрать: {date.today()} .. {date.today() + timedelta(days=3)}"
        ttk.Label(frm, text=hint).grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))

        btns = ttk.Frame(frm)
        btns.grid(row=4, column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(btns, text="Отмена", command=self.destroy).pack(side="right")
        ttk.Button(btns, text="Зарезервировать", command=self._do).pack(side="right", padx=(0, 8))

        self._load_branches()

        self.grab_set()
        self.transient(parent)
        self.wait_visibility()
        self.focus_set()
        self.bind("<Escape>", lambda e: self.destroy())

    def _load_branches(self):
        branches = list_available_branches_for_book(self.book_id)
        self._branches = branches

        if not branches:
            messagebox.showwarning("Печаль", "Эта книга сейчас нигде не доступна для резерва.")
            self.destroy()
            return

        items = []
        for b in branches:
            items.append(f"{b['name']} | {b.get('address') or '—'} | доступно: {b['available_count']}")
        self.branch_cb["values"] = items
        self.branch_cb.current(0)

    def _parse_date(self):
        try:
            y, m, d = self.date_var.get().strip().split("-")
            return date(int(y), int(m), int(d))
        except Exception:
            return None

    def _do(self):
        idx = self.branch_cb.current()
        if idx < 0:
            messagebox.showwarning("Ошибка", "Выберите филиал.")
            return

        pickup = self._parse_date()
        if not pickup:
            messagebox.showwarning("Ошибка", "Дата должна быть в формате YYYY-MM-DD.")
            return

        branch_id = int(self._branches[idx]["branch_id"])
        ok, msg, _rid = create_reservation(self.reader_user, self.book_id, branch_id, pickup)
        if not ok:
            messagebox.showerror("Ошибка", msg)
            return

        messagebox.showinfo("Ок", msg)
        self.result_ok = True
        self.destroy()
