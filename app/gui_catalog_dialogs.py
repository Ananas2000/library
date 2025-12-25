import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Dict, Any, List


def _to_int_or_none(s: str) -> Optional[int]:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def _to_float_or_none(s: str) -> Optional[float]:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


class BookDialog(tk.Toplevel):
    def __init__(
        self,
        parent,
        publishers: List[Dict[str, Any]],
        authors: List[Dict[str, Any]],
        initial: Optional[Dict[str, Any]] = None
    ):
        super().__init__(parent)
        self.title("Книга")
        self.resizable(False, False)
        self.result = None

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Название:").grid(row=0, column=0, sticky="w")
        ttk.Label(frm, text="Язык:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Label(frm, text="Год:").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Label(frm, text="Страниц:").grid(row=3, column=0, sticky="w", pady=(8, 0))
        ttk.Label(frm, text="Издательство:").grid(row=4, column=0, sticky="w", pady=(8, 0))
        ttk.Label(frm, text="Авторы:").grid(row=5, column=0, sticky="nw", pady=(8, 0))
        ttk.Label(frm, text="(можно выбрать несколько)").grid(row=6, column=1, sticky="w", padx=(8, 0), pady=(2, 0))

        self.title_var = tk.StringVar(value=(initial.get("title") if initial else ""))
        self.lang_var = tk.StringVar(value=(initial.get("language") if initial else "ru"))
        self.year_var = tk.StringVar(value=str(initial.get("publish_year") or "") if initial else "")
        self.pages_var = tk.StringVar(value=str(initial.get("pages_count") or "") if initial else "")

        self.publisher_map = {"—": None}
        for p in publishers:
            self.publisher_map[p["name"]] = p["id"]

        initial_pub = (initial.get("publisher") if initial else None) or "—"
        if initial_pub not in self.publisher_map:
            initial_pub = "—"
        self.pub_var = tk.StringVar(value=initial_pub)

        ttk.Entry(frm, textvariable=self.title_var, width=50).grid(row=0, column=1, sticky="w", padx=(8, 0))
        ttk.Entry(frm, textvariable=self.lang_var, width=10).grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        ttk.Entry(frm, textvariable=self.year_var, width=10).grid(row=2, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        ttk.Entry(frm, textvariable=self.pages_var, width=10).grid(row=3, column=1, sticky="w", padx=(8, 0), pady=(8, 0))

        cb = ttk.Combobox(frm, textvariable=self.pub_var, values=list(self.publisher_map.keys()),
                          state="readonly", width=30)
        cb.grid(row=4, column=1, sticky="w", padx=(8, 0), pady=(8, 0))

        self._author_items: List[tuple[int, str]] = [(a["id"], a["full_name"]) for a in authors]
        initial_author_ids = set(initial.get("author_ids") or []) if initial else set()

        lb_frame = ttk.Frame(frm)
        lb_frame.grid(row=5, column=1, sticky="w", padx=(8, 0), pady=(8, 0))

        self.authors_list = tk.Listbox(lb_frame, height=6, width=44, selectmode="extended", exportselection=False)
        sb = ttk.Scrollbar(lb_frame, orient="vertical", command=self.authors_list.yview)
        self.authors_list.configure(yscrollcommand=sb.set)

        self.authors_list.grid(row=0, column=0, sticky="nsw")
        sb.grid(row=0, column=1, sticky="ns")

        for i, (aid, name) in enumerate(self._author_items):
            self.authors_list.insert("end", name)
            if aid in initial_author_ids:
                self.authors_list.selection_set(i)

        btns = ttk.Frame(frm)
        btns.grid(row=7, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Отмена", command=self._cancel).pack(side="right")
        ttk.Button(btns, text="OK", command=self._ok).pack(side="right", padx=(0, 8))

        self.grab_set()
        self.transient(parent)
        self.wait_visibility()
        self.focus_set()

    def _ok(self):
        title = self.title_var.get().strip()
        if not title:
            messagebox.showwarning("Ошибка", "Название пустое.")
            return

        selected = list(self.authors_list.curselection())
        author_ids = [self._author_items[i][0] for i in selected]

        self.result = {
            "title": title,
            "language": self.lang_var.get().strip() or "ru",
            "publish_year": _to_int_or_none(self.year_var.get()),
            "pages_count": _to_int_or_none(self.pages_var.get()),
            "publisher_id": self.publisher_map.get(self.pub_var.get(), None),
            "author_ids": author_ids
        }
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


class CopyDialog(tk.Toplevel):
    def __init__(self, parent, locations: List[Dict[str, Any]], initial: Optional[Dict[str, Any]] = None):
        super().__init__(parent)
        self.title("Экземпляр")
        self.resizable(False, False)
        self.result = None

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Инв. код:").grid(row=0, column=0, sticky="w")
        ttk.Label(frm, text="Статус:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Label(frm, text="Цена:").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Label(frm, text="Локация:").grid(row=3, column=0, sticky="w", pady=(8, 0))
        ttk.Label(frm, text="Примечание:").grid(row=4, column=0, sticky="w", pady=(8, 0))

        self.inv_var = tk.StringVar(value=(initial.get("inventory_code") if initial else ""))
        self.status_var = tk.StringVar(value=(initial.get("status") if initial else "available"))
        self.price_var = tk.StringVar(value=str(initial.get("price") or "") if initial else "")
        self.note_var = tk.StringVar(value=(initial.get("condition_note") if initial else ""))

        self.loc_map = {"—": None}
        loc_labels = ["—"]
        for l in locations:
            label = f'{l["branch_name"]} / {l["code"]}'
            self.loc_map[label] = l["id"]
            loc_labels.append(label)

        initial_loc_label = "—"
        if initial and initial.get("branch_name") and initial.get("location_code"):
            initial_loc_label = f'{initial["branch_name"]} / {initial["location_code"]}'
            if initial_loc_label not in self.loc_map:
                initial_loc_label = "—"

        self.loc_var = tk.StringVar(value=initial_loc_label)

        ttk.Entry(frm, textvariable=self.inv_var, width=30).grid(row=0, column=1, sticky="w", padx=(8, 0))
        ttk.Combobox(frm, textvariable=self.status_var,
                     values=["available", "loaned", "reserved", "lost", "damaged"],
                     state="readonly", width=15).grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        ttk.Entry(frm, textvariable=self.price_var, width=15).grid(row=2, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        ttk.Combobox(frm, textvariable=self.loc_var, values=loc_labels,
                     state="readonly", width=35).grid(row=3, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        ttk.Entry(frm, textvariable=self.note_var, width=50).grid(row=4, column=1, sticky="w", padx=(8, 0), pady=(8, 0))

        btns = ttk.Frame(frm)
        btns.grid(row=5, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Отмена", command=self._cancel).pack(side="right")
        ttk.Button(btns, text="OK", command=self._ok).pack(side="right", padx=(0, 8))

        self.grab_set()
        self.transient(parent)
        self.wait_visibility()
        self.focus_set()

    def _ok(self):
        inv = self.inv_var.get().strip()
        if not inv:
            messagebox.showwarning("Ошибка", "Инвентарный код пустой.")
            return
        self.result = {
            "inventory_code": inv,
            "status": self.status_var.get(),
            "price": _to_float_or_none(self.price_var.get()),
            "location_id": self.loc_map.get(self.loc_var.get(), None),
            "condition_note": self.note_var.get().strip() or None
        }
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()
