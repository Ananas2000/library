from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from app.gui_treeview_filters import TreeviewGridController

from app.services import (
    Session,
    get_reports_for_role, export_csv, export_json,
    issue_loan, return_loan, update_overdue_statuses,
    make_backup, restore_backup,
    list_users_filtered, admin_register_librarian, set_user_active,
    reset_user_password, update_user_profile, delete_user,
    ru_header, format_cell,
    role_label, roles_label_list,
)

from app.services_catalog import (
    list_books, list_copies_for_book,
    list_books_reader_view,
    list_publishers, list_locations,
    list_authors, get_book_author_ids,
    create_book, update_book, delete_book,
    create_copy, update_copy, delete_copy
)

from app.gui_catalog_dialogs import BookDialog, CopyDialog
from app.gui_users_dialogs import RegisterLibrarianDialog, ResetPasswordDialog, EditUserDialog

from app.gui_reserve import ReserveDialog
from app.services_reservations import (
    expire_old_reservations,
    list_reservations_for_reader, list_reservations_for_librarian,
    cancel_reservation, extend_reservation, fulfill_reservation
)


COPY_STATUS_RU = {
    "available": "В наличии",
    "loaned": "Выдан",
    "reserved": "В резерве",
    "lost": "Утерян",
    "damaged": "Повреждён",
}
COPY_STATUS_EN = {v: k for k, v in COPY_STATUS_RU.items()}

LOAN_STATUS_RU = {
    "open": "Выдана",
    "overdue": "Просрочена",
    "returned": "Возвращена",
    "cancelled": "Отменена",
}

RES_STATUS_RU = {
    "active": "Активен",
    "fulfilled": "Выдано",
    "expired": "Истёк",
    "cancelled": "Отменён",
}


def _yes_no(v) -> str:
    return "Да" if bool(v) else "Нет"


class MainWindow(tk.Tk):
    def __init__(self, session: Session):
        super().__init__()
        self.session = session
        self.logged_out = False

        role_ru = role_label(session.primary_role)
        self.title(f"Библиотека — {session.user.full_name} ({role_ru})")
        self.geometry("1120x740")

        topbar = ttk.Frame(self, padding=(10, 8))
        topbar.pack(fill="x")
        ttk.Label(
            topbar,
            text=f"Пользователь: {session.user.full_name}   Роль: {role_ru}",
        ).pack(side="left")
        ttk.Button(topbar, text="Выйти", command=self._logout).pack(side="right")

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)

        self.tabs = {}
        self._tv = {}

        expire_old_reservations()

        self._build_catalog_tab()
        self._build_loans_tab()
        self._build_reservations_tab()
        self._build_reports_tab()
        self._build_backup_tab()
        self._build_users_tab()

        self._apply_rights_rules()

    def _enable_grid(self, tree: ttk.Treeview) -> TreeviewGridController:
        if tree in self._tv:
            return self._tv[tree]
        ctl = TreeviewGridController(tree)
        self._tv[tree] = ctl
        return ctl

    def _set_tree_data(self, tree: ttk.Treeview, rows_as_tuples):
        ctl = self._enable_grid(tree)
        ctl.set_data(rows_as_tuples)

    def _add_search_box(self, parent: ttk.Frame, tree: ttk.Treeview, label: str = "Поиск:"):
        var = tk.StringVar(value="")
        ttk.Label(parent, text=label).pack(side="left", padx=(12, 4))
        ent = ttk.Entry(parent, textvariable=var, width=28)
        ent.pack(side="left")

        ctl = self._enable_grid(tree)

        var.trace_add("write", lambda *_: ctl.set_search(var.get()))
        ent.bind("<Escape>", lambda e: (var.set(""), ctl.clear_search(), "break"))

        return var, ent

    # Спрятать заголовки и вкладки
    def _hide_tab(self, title: str):
        tab = self.tabs.get(title)
        if tab:
            self.notebook.forget(tab)

    def _hide_widget(self, w):
        if not w:
            return
        mgr = w.winfo_manager()
        if mgr == "pack":
            w.pack_forget()
        elif mgr == "grid":
            w.grid_remove()
        elif mgr == "place":
            w.place_forget()

    def _apply_rights_rules(self):
        s = self.session

        # --- вкладка Пользователи
        if not s.can("manage_users"):
            self._hide_tab("Пользователи")

        # --- вкладка Бэкап
        if not s.can("backup"):
            self._hide_tab("Бэкап")

        # --- вкладка Отчёты
        if not s.can("view_reports"):
            self._hide_tab("Отчёты")

        # --- Каталог: если нет manage_catalog -> прячем
        if not s.can("manage_catalog"):
            self._hide_widget(self.copies_frame)
            self._hide_widget(self.btn_book_add)
            self._hide_widget(self.btn_book_edit)
            self._hide_widget(self.btn_book_del)
            self._hide_widget(self.btn_copy_add)
            self._hide_widget(self.btn_copy_edit)
            self._hide_widget(self.btn_copy_del)

        # --- Кнопка "Резерв" показывается только если есть create_reservation
        if not s.can("create_reservation"):
            self._hide_widget(self.btn_reserve)

        # --- Выдачи: если нет manage_loans -> прячем оформление/возврат и переименуем вкладку
        if not s.can("manage_loans"):
            self._hide_widget(self.controls_loans_frame)
            self.notebook.tab(self.tabs["Выдачи"], text="Ваши выдачи")

        # --- Резервы:
        # если может управлять своими резервами -> reader-кнопки
        # если может управлять резервами (выдать) -> staff-кнопка
        can_own = s.can("manage_own_reservations")
        can_staff = s.can("manage_reservations")

        if not can_own and not can_staff:
            self._hide_tab("Резервы")
        else:
            if can_own and not can_staff:
                self.notebook.tab(self.tabs["Резервы"], text="Ваши резервы")

            if hasattr(self, "btn_res_cancel") and not can_own:
                self._hide_widget(self.btn_res_cancel)
            if hasattr(self, "btn_res_extend") and not can_own:
                self._hide_widget(self.btn_res_extend)
            if hasattr(self, "btn_res_fulfill") and not can_staff:
                self._hide_widget(self.btn_res_fulfill)

    # Вкладка каталог
    def _build_catalog_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Каталог")
        self.tabs["Каталог"] = tab

        self.books_tree = ttk.Treeview(tab, show="headings", height=14)
        self._enable_grid(self.books_tree)

        top = ttk.Frame(tab)
        top.pack(fill="x")

        ttk.Button(top, text="Обновить", command=self._load_books).pack(side="left")

        self.btn_reserve = ttk.Button(top, text="Зарезервировать выбранную книгу", command=self._ui_reserve_book)
        self.btn_reserve.pack(side="left", padx=8)

        self._add_search_box(top, self.books_tree, "Поиск книг:")

        self.catalog_info = ttk.Label(top, text="")
        self.catalog_info.pack(side="left", padx=12)

        self.btn_book_add = ttk.Button(top, text="Добавить книгу", command=self._ui_add_book)
        self.btn_book_edit = ttk.Button(top, text="Редактировать книгу", command=self._ui_edit_book)
        self.btn_book_del = ttk.Button(top, text="Удалить книгу", command=self._ui_delete_book)

        self.btn_book_add.pack(side="right")
        self.btn_book_edit.pack(side="right", padx=8)
        self.btn_book_del.pack(side="right", padx=8)

        self.books_tree.pack(fill="x", pady=(10, 0))
        self.books_tree.bind("<<TreeviewSelect>>", lambda e: self._load_copies_for_selected_book())

        mid = ttk.LabelFrame(tab, text="Экземпляры выбранной книги", padding=8)
        self.copies_frame = mid
        mid.pack(fill="both", expand=True, pady=(10, 0))

        self.copies_tree = ttk.Treeview(
            mid,
            columns=("id", "inventory_code", "status", "price", "branch", "location", "note"),
            show="headings",
            height=12
        )
        headers = {
            "id": "ID",
            "inventory_code": "Инв. код",
            "status": "Статус",
            "price": "Цена",
            "branch": "Филиал",
            "location": "Локация",
            "note": "Примечание",
        }
        for c, w in [
            ("id", 60),
            ("inventory_code", 150),
            ("status", 120),
            ("price", 90),
            ("branch", 220),
            ("location", 120),
            ("note", 300),
        ]:
            self.copies_tree.heading(c, text=headers.get(c, c))
            self.copies_tree.column(c, width=w, anchor="w")
        self._enable_grid(self.copies_tree)

        mid_top = ttk.Frame(mid)
        mid_top.pack(fill="x")

        self._add_search_box(mid_top, self.copies_tree, "Поиск экземпляров:")

        self.btn_copy_add = ttk.Button(mid_top, text="Добавить экземпляр", command=self._ui_add_copy)
        self.btn_copy_edit = ttk.Button(mid_top, text="Редактировать экземпляр", command=self._ui_edit_copy)
        self.btn_copy_del = ttk.Button(mid_top, text="Удалить экземпляр", command=self._ui_delete_copy)

        self.btn_copy_add.pack(side="right")
        self.btn_copy_edit.pack(side="right", padx=8)
        self.btn_copy_del.pack(side="right", padx=8)

        self.copies_tree.pack(fill="both", expand=True, pady=(8, 0))

        self._load_books()

    def _configure_books_tree_reader(self):
        cols = ("id", "title", "authors", "publisher", "year", "available", "status")
        self.books_tree["columns"] = cols
        headers = {
            "id": "ID",
            "title": "Название",
            "authors": "Авторы",
            "publisher": "Издательство",
            "year": "Год",
            "available": "Доступно",
            "status": "Наличие",
        }
        for c, w in [
            ("id", 70),
            ("title", 320),
            ("authors", 210),
            ("publisher", 160),
            ("year", 80),
            ("available", 110),
            ("status", 260),
        ]:
            self.books_tree.heading(c, text=headers.get(c, c))
            self.books_tree.column(c, width=w, anchor="w")

    def _configure_books_tree_staff(self):
        cols = ("id", "title", "authors", "publisher", "year", "lang", "pages")
        self.books_tree["columns"] = cols
        headers = {
            "id": "ID",
            "title": "Название",
            "authors": "Авторы",
            "publisher": "Издательство",
            "year": "Год",
            "lang": "Язык",
            "pages": "Страниц",
        }
        for c, w in [
            ("id", 70),
            ("title", 280),
            ("authors", 220),
            ("publisher", 170),
            ("year", 80),
            ("lang", 80),
            ("pages", 80),
        ]:
            self.books_tree.heading(c, text=headers.get(c, c))
            self.books_tree.column(c, width=w, anchor="w")

    def _get_selected_book_id(self):
        sel = self.books_tree.selection()
        if not sel:
            return None
        vals = self.books_tree.item(sel[0], "values")
        return int(vals[0])

    def _get_selected_book_title(self):
        sel = self.books_tree.selection()
        if not sel:
            return None
        vals = self.books_tree.item(sel[0], "values")
        return str(vals[1])

    def _get_selected_copy_id(self):
        sel = self.copies_tree.selection()
        if not sel:
            return None
        return int(self.copies_tree.item(sel[0], "values")[0])

    def _load_books(self):
        # Если нет прав manage_catalog -> показываем читательский вид
        if not self.session.can("manage_catalog"):
            self._configure_books_tree_reader()
            rows = list_books_reader_view()

            data = []
            for r in rows:
                avail = int(r.get("available_count") or 0)
                next_due = r.get("next_due")
                if avail > 0:
                    status = "В наличии"
                else:
                    status = "Нет в наличии"
                    if next_due:
                        status += f" (ожидается после {next_due})"

                data.append((
                    r["id"],
                    r["title"],
                    r.get("authors") or "—",
                    r.get("publisher") or "—",
                    r.get("publish_year") or "",
                    avail,
                    status
                ))

            self._set_tree_data(self.books_tree, data)
            self.catalog_info.config(text=f"Книг: {len(rows)}")
            self._set_tree_data(self.copies_tree, [])
            return

        self._configure_books_tree_staff()
        rows = list_books()
        data = []
        for r in rows:
            data.append((
                r["id"],
                r["title"],
                r.get("authors") or "—",
                r.get("publisher") or "—",
                r.get("publish_year") or "",
                r.get("language") or "",
                r.get("pages_count") or "",
            ))
        self._set_tree_data(self.books_tree, data)
        self.catalog_info.config(text=f"Книг: {len(rows)}")
        self._set_tree_data(self.copies_tree, [])

    def _load_copies_for_selected_book(self):
        if not self.session.can("manage_catalog"):
            return

        book_id = self._get_selected_book_id()
        if not book_id:
            self._set_tree_data(self.copies_tree, [])
            return

        rows = list_copies_for_book(book_id)
        data = []
        for r in rows:
            data.append((
                r["id"],
                r["inventory_code"],
                COPY_STATUS_RU.get(r["status"], r["status"]),
                r.get("price") or "",
                r.get("branch_name") or "—",
                r.get("location_code") or "—",
                r.get("condition_note") or ""
            ))
        self._set_tree_data(self.copies_tree, data)

    def _ui_reserve_book(self):
        if not self.session.can("create_reservation"):
            return
        book_id = self._get_selected_book_id()
        if not book_id:
            messagebox.showwarning("Ошибка", "Выберите книгу.")
            return
        title = self._get_selected_book_title() or ""
        dlg = ReserveDialog(self, self.session.user, book_id, title)
        self.wait_window(dlg)
        if getattr(dlg, "result_ok", False):
            self._load_books()
            self._load_reservations()

    def _ui_add_book(self):
        if not self.session.can("manage_catalog"):
            return
        pubs = list_publishers()
        authors = list_authors()
        dlg = BookDialog(self, pubs, authors, initial=None)
        self.wait_window(dlg)
        if not dlg.result:
            return
        ok, msg = create_book(**dlg.result)
        messagebox.showinfo("Ок", msg) if ok else messagebox.showerror("Ошибка", msg)
        if ok:
            self._load_books()

    def _ui_edit_book(self):
        if not self.session.can("manage_catalog"):
            return
        book_id = self._get_selected_book_id()
        if not book_id:
            messagebox.showwarning("Ошибка", "Выберите книгу.")
            return

        sel = self.books_tree.selection()[0]
        vals = self.books_tree.item(sel, "values")

        current = {
            "id": int(vals[0]),
            "title": vals[1],
            "publisher": vals[3] if vals[3] != "—" else None,
            "publish_year": int(vals[4]) if str(vals[4]).strip() else None,
            "language": vals[5],
            "pages_count": int(vals[6]) if str(vals[6]).strip() else None,
            "author_ids": get_book_author_ids(book_id),
        }

        pubs = list_publishers()
        authors = list_authors()
        dlg = BookDialog(self, pubs, authors, initial=current)
        self.wait_window(dlg)
        if not dlg.result:
            return

        ok, msg = update_book(book_id=book_id, **dlg.result)
        messagebox.showinfo("Ок", msg) if ok else messagebox.showerror("Ошибка", msg)
        if ok:
            self._load_books()

    def _ui_delete_book(self):
        if not self.session.can("manage_catalog"):
            return
        book_id = self._get_selected_book_id()
        if not book_id:
            messagebox.showwarning("Ошибка", "Выберите книгу.")
            return
        if not messagebox.askyesno("Подтверди", "Удалить книгу?"):
            return
        ok, msg = delete_book(book_id)
        messagebox.showinfo("Ок", msg) if ok else messagebox.showerror("Ошибка", msg)
        if ok:
            self._load_books()

    def _ui_add_copy(self):
        if not self.session.can("manage_catalog"):
            return
        book_id = self._get_selected_book_id()
        if not book_id:
            messagebox.showwarning("Ошибка", "Сначала выберите книгу.")
            return
        locs = list_locations()
        dlg = CopyDialog(self, locs, initial=None)
        self.wait_window(dlg)
        if not dlg.result:
            return
        ok, msg = create_copy(book_id=book_id, **dlg.result)
        messagebox.showinfo("Ок", msg) if ok else messagebox.showerror("Ошибка", msg)
        if ok:
            self._load_copies_for_selected_book()

    def _ui_edit_copy(self):
        if not self.session.can("manage_catalog"):
            return
        copy_id = self._get_selected_copy_id()
        if not copy_id:
            messagebox.showwarning("Ошибка", "Выберите экземпляр.")
            return

        sel = self.copies_tree.selection()[0]
        vals = self.copies_tree.item(sel, "values")

        status_code = COPY_STATUS_EN.get(vals[2], vals[2])

        current = {
            "id": int(vals[0]),
            "inventory_code": vals[1],
            "status": status_code,
            "price": float(vals[3]) if str(vals[3]).strip() else None,
            "branch_name": vals[4] if vals[4] != "—" else None,
            "location_code": vals[5] if vals[5] != "—" else None,
            "condition_note": vals[6] or None,
        }

        locs = list_locations()
        dlg = CopyDialog(self, locs, initial=current)
        self.wait_window(dlg)
        if not dlg.result:
            return

        ok, msg = update_copy(copy_id=copy_id, **dlg.result)
        messagebox.showinfo("Ок", msg) if ok else messagebox.showerror("Ошибка", msg)
        if ok:
            self._load_copies_for_selected_book()

    def _ui_delete_copy(self):
        if not self.session.can("manage_catalog"):
            return
        copy_id = self._get_selected_copy_id()
        if not copy_id:
            messagebox.showwarning("Ошибка", "Выберите экземпляр.")
            return
        if not messagebox.askyesno("Подтверди", "Удалить экземпляр?"):
            return
        ok, msg = delete_copy(copy_id)
        messagebox.showinfo("Ок", msg) if ok else messagebox.showerror("Ошибка", msg)
        if ok:
            self._load_copies_for_selected_book()

    # Вкладка выдачи
    def _build_loans_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Выдачи")
        self.tabs["Выдачи"] = tab

        controls = ttk.LabelFrame(tab, text="Оформление / возврат", padding=10)
        self.controls_loans_frame = controls
        controls.pack(fill="x")

        ttk.Label(controls, text="Инв. код:").grid(row=0, column=0, sticky="w")
        ttk.Label(controls, text="Читатель (логин):").grid(row=0, column=2, sticky="w", padx=(16, 0))

        self.issue_inv_var = tk.StringVar()
        self.issue_reader_var = tk.StringVar()

        self.issue_inv_entry = ttk.Entry(controls, textvariable=self.issue_inv_var, width=20)
        self.issue_reader_entry = ttk.Entry(controls, textvariable=self.issue_reader_var, width=20)

        self.issue_inv_entry.grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.issue_reader_entry.grid(row=0, column=3, sticky="w", padx=(8, 0))

        self.btn_issue = ttk.Button(controls, text="Выдать", command=self._ui_issue_loan)
        self.btn_issue.grid(row=0, column=4, sticky="w", padx=(16, 0))

        self.btn_return = ttk.Button(controls, text="Вернуть выбранную выдачу", command=self._ui_return_loan)
        self.btn_return.grid(row=1, column=0, columnspan=3, sticky="w", pady=(10, 0))

        self.btn_overdue = ttk.Button(controls, text="Обновить просрочки", command=self._ui_update_overdue)
        self.btn_overdue.grid(row=1, column=3, sticky="w", padx=(8, 0), pady=(10, 0))

        self.loan_info = ttk.Label(controls, text="", foreground="#444")
        self.loan_info.grid(row=1, column=4, sticky="w", padx=(12, 0), pady=(10, 0))

        top2 = ttk.Frame(tab)
        top2.pack(fill="x", pady=(10, 0))
        ttk.Button(top2, text="Обновить список", command=self._load_loans).pack(side="left")

        self.loans_tree = ttk.Treeview(
            tab,
            columns=("id", "status", "inv", "book", "reader", "due"),
            show="headings",
            height=18
        )
        headers = {
            "id": "ID",
            "status": "Статус",
            "inv": "Инв. код",
            "book": "Книга",
            "reader": "Читатель",
            "due": "Срок",
        }
        for c, w in [
            ("id", 70),
            ("status", 120),
            ("inv", 120),
            ("book", 420),
            ("reader", 160),
            ("due", 110),
        ]:
            self.loans_tree.heading(c, text=headers.get(c, c))
            self.loans_tree.column(c, width=w, anchor="w")
        self._enable_grid(self.loans_tree)

        self._add_search_box(top2, self.loans_tree, "Поиск:")
        self.loans_tree.pack(fill="both", expand=True, pady=(8, 0))

        self._load_loans()

    def _load_loans(self):
        from app.models import Loan, Copy, Book, User

        q = (Loan
             .select(Loan.id, Loan.status, Loan.due_date,
                     Copy.inventory_code, Book.title,
                     User.login)
             .join(Copy)
             .join(Book)
             .switch(Loan)
             .join(User, on=(Loan.reader == User.id))
             .order_by(Loan.due_date.asc()))

        if not self.session.can("manage_loans"):
            q = q.where(Loan.reader == self.session.user)

        data = []
        for row in q.dicts():
            data.append((
                row["id"],
                LOAN_STATUS_RU.get(row["status"], row["status"]),
                row["inventory_code"],
                row["title"],
                row["login"],
                str(row["due_date"]) if row.get("due_date") else ""
            ))

        self._set_tree_data(self.loans_tree, data)

    def _ui_issue_loan(self):
        if not self.session.can("manage_loans"):
            return
        ok, msg = issue_loan(
            copy_inventory_code=self.issue_inv_var.get(),
            reader_login=self.issue_reader_var.get(),
            librarian_user=self.session.user
        )
        if not ok:
            messagebox.showerror("Не вышло", msg)
            return
        messagebox.showinfo("Готово", msg)
        self.issue_inv_var.set("")
        self.issue_reader_var.set("")
        self._load_books()
        self._load_loans()

    def _ui_return_loan(self):
        if not self.session.can("manage_loans"):
            return
        sel = self.loans_tree.selection()
        if not sel:
            messagebox.showwarning("Ошибка", "Сначала выберите выдачу.")
            return
        loan_id = int(self.loans_tree.item(sel[0], "values")[0])
        ok, msg = return_loan(loan_id, self.session.user)
        if not ok:
            messagebox.showerror("Не вышло", msg)
            return
        messagebox.showinfo("Готово", msg)
        self._load_books()
        self._load_loans()

    def _ui_update_overdue(self):
        if not self.session.can("manage_loans"):
            return
        n = update_overdue_statuses()
        self.loan_info.config(text=f"Обновлено: {n}")
        self._load_loans()

    # Вкладка резервы
    def _build_reservations_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Резервы")
        self.tabs["Резервы"] = tab

        top = ttk.Frame(tab)
        top.pack(fill="x")

        ttk.Button(top, text="Обновить", command=self._load_reservations).pack(side="left")

        self.res_tree = ttk.Treeview(tab, show="headings", height=20)
        self._enable_grid(self.res_tree)
        self.res_tree.pack(fill="both", expand=True, pady=(10, 0))

        self._add_search_box(top, self.res_tree, "Поиск:")

        btns = ttk.Frame(tab)
        btns.pack(fill="x", pady=(10, 0))

        self.btn_res_cancel = ttk.Button(btns, text="Отменить выбранный резерв", command=self._ui_cancel_reservation)
        self.btn_res_extend = ttk.Button(btns, text="Продлить на 1 день (1 раз)", command=self._ui_extend_reservation)
        self.btn_res_fulfill = ttk.Button(btns, text="Выдать по резерву", command=self._ui_fulfill_reservation)

        if self.session.can("manage_own_reservations"):
            self.btn_res_cancel.pack(side="left")
            self.btn_res_extend.pack(side="left", padx=8)

        if self.session.can("manage_reservations"):
            self.btn_res_fulfill.pack(side="left")

        self._load_reservations()

    def _configure_res_tree_reader(self):
        cols = ("id", "status", "book", "branch", "pickup", "expires", "extended")
        self.res_tree["columns"] = cols
        headers = {
            "id": "ID",
            "status": "Статус",
            "book": "Книга",
            "branch": "Филиал",
            "pickup": "Дата получения",
            "expires": "Истекает",
            "extended": "Продлён",
        }
        for c, w in [
            ("id", 70),
            ("status", 120),
            ("book", 360),
            ("branch", 280),
            ("pickup", 120),
            ("expires", 170),
            ("extended", 90),
        ]:
            self.res_tree.heading(c, text=headers.get(c, c))
            self.res_tree.column(c, width=w, anchor="w")

    def _configure_res_tree_staff(self):
        cols = ("id", "status", "book", "inv", "branch", "pickup", "expires", "reader", "phone")
        self.res_tree["columns"] = cols
        headers = {
            "id": "ID",
            "status": "Статус",
            "book": "Книга",
            "inv": "Инв. код",
            "branch": "Филиал",
            "pickup": "Дата получения",
            "expires": "Истекает",
            "reader": "Читатель",
            "phone": "Телефон",
        }
        for c, w in [
            ("id", 70),
            ("status", 120),
            ("book", 320),
            ("inv", 120),
            ("branch", 240),
            ("pickup", 120),
            ("expires", 170),
            ("reader", 200),
            ("phone", 140),
        ]:
            self.res_tree.heading(c, text=headers.get(c, c))
            self.res_tree.column(c, width=w, anchor="w")

    def _get_selected_reservation_id(self):
        sel = self.res_tree.selection()
        if not sel:
            return None
        vals = self.res_tree.item(sel[0], "values")
        return int(vals[0])

    def _load_reservations(self):
        expire_old_reservations()

        if self.session.can("manage_reservations"):
            self._configure_res_tree_staff()
            rows = list_reservations_for_librarian()

            data = []
            for r in rows:
                data.append((
                    r["id"],
                    RES_STATUS_RU.get(r["status"], r["status"]),
                    r.get("book_title") or "",
                    r.get("inv") or "",
                    f"{r.get('branch_name') or ''} | {r.get('branch_address') or ''}",
                    str(r.get("pickup_date") or ""),
                    str(r.get("expires_at") or ""),
                    r.get("reader_name") or r.get("reader_login") or "",
                    r.get("reader_phone") or "",
                ))
            self._set_tree_data(self.res_tree, data)
            return

        if self.session.can("manage_own_reservations"):
            self._configure_res_tree_reader()
            rows = list_reservations_for_reader(self.session.user)

            data = []
            for r in rows:
                data.append((
                    r["id"],
                    RES_STATUS_RU.get(r["status"], r["status"]),
                    r.get("book_title") or "",
                    f"{r.get('branch_name') or ''} | {r.get('branch_address') or ''}",
                    str(r.get("pickup_date") or ""),
                    str(r.get("expires_at") or ""),
                    _yes_no(r.get("extended_once")),
                ))
            self._set_tree_data(self.res_tree, data)
            return

        self._set_tree_data(self.res_tree, [("Нет данных",)])

    def _ui_cancel_reservation(self):
        if not self.session.can("manage_own_reservations"):
            return
        rid = self._get_selected_reservation_id()
        if not rid:
            messagebox.showwarning("Ошибка", "Выберите резерв.")
            return
        ok, msg = cancel_reservation(self.session.user, rid)
        messagebox.showinfo("Ок", msg) if ok else messagebox.showerror("Ошибка", msg)
        self._load_books()
        self._load_reservations()

    def _ui_extend_reservation(self):
        if not self.session.can("manage_own_reservations"):
            return
        rid = self._get_selected_reservation_id()
        if not rid:
            messagebox.showwarning("Ошибка", "Выберите резерв.")
            return
        ok, msg = extend_reservation(self.session.user, rid)
        messagebox.showinfo("Ок", msg) if ok else messagebox.showerror("Ошибка", msg)
        self._load_reservations()

    def _ui_fulfill_reservation(self):
        if not self.session.can("manage_reservations"):
            return
        rid = self._get_selected_reservation_id()
        if not rid:
            messagebox.showwarning("Ошибка", "Выберите резерв.")
            return
        ok, msg = fulfill_reservation(self.session.user, rid, loan_days=14)
        messagebox.showinfo("Ок", msg) if ok else messagebox.showerror("Ошибка", msg)
        self._load_books()
        self._load_loans()
        self._load_reservations()

    # Вкладка Отчеты
    def _build_reports_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Отчёты")
        self.tabs["Отчёты"] = tab

        top = ttk.Frame(tab)
        top.pack(fill="x")

        ttk.Label(top, text="Отчёт:").pack(side="left")

        self.reports = get_reports_for_role(self.session)
        first_report = next(iter(self.reports.keys()), "")
        self.report_var = tk.StringVar(value=first_report)

        cb = ttk.Combobox(top, textvariable=self.report_var, values=list(self.reports.keys()),
                          state="readonly", width=40)
        cb.pack(side="left", padx=8)
        cb.bind("<<ComboboxSelected>>", lambda e: self._show_report())

        ttk.Button(top, text="Экспорт CSV", command=self._export_csv).pack(side="left", padx=8)
        ttk.Button(top, text="Экспорт JSON", command=self._export_json).pack(side="left", padx=8)

        self.report_tree = ttk.Treeview(tab, show="headings", height=22)
        self._enable_grid(self.report_tree)

        self._add_search_box(top, self.report_tree, "Поиск:")
        self.report_tree.pack(fill="both", expand=True, pady=(10, 0))

        self._show_report()

    def _get_report_rows(self):
        name = self.report_var.get()
        fn = getattr(self, 'reports', {}).get(name)
        if not fn:
            return []
        return fn()

    def _show_report(self):
        rows = self._get_report_rows()
        self._fill_tree(self.report_tree, rows)

    def _export_csv(self):
        rows = self._get_report_rows()
        path = filedialog.asksaveasfilename(defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")],
                                            title="Сохранить CSV")
        if not path:
            return
        try:
            export_csv(rows, path)
            messagebox.showinfo("Готово", f"Сохранено: {path}")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def _export_json(self):
        rows = self._get_report_rows()
        path = filedialog.asksaveasfilename(defaultextension=".json",
                                            filetypes=[("JSON", "*.json")],
                                            title="Сохранить JSON")
        if not path:
            return
        try:
            export_json(rows, path)
            messagebox.showinfo("Готово", f"Сохранено: {path}")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def _fill_tree(self, tree: ttk.Treeview, rows):
        if not rows:
            tree["columns"] = ("empty",)
            tree["show"] = "headings"
            tree.heading("empty", text="Нет данных")
            tree.column("empty", width=900, anchor="w")
            self._set_tree_data(tree, [("Нет данных",)])
            return

        cols = list(rows[0].keys())
        tree["columns"] = cols
        tree["show"] = "headings"

        for c in cols:
            tree.heading(c, text=ru_header(c))
            tree.column(c, width=180, anchor="w")

        data = []
        for r in rows:
            row_vals = []
            for c in cols:
                row_vals.append(format_cell(c, r.get(c), row=r))
            data.append(tuple(row_vals))
        self._set_tree_data(tree, data)

    # Вкладка бэкап
    def _build_backup_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Бэкап")
        self.tabs["Бэкап"] = tab

        box = ttk.LabelFrame(tab, text="pg_dump (сделать бэкап)", padding=12)
        box.pack(fill="x")

        ttk.Label(box, text="Файл бэкапа (.dump):").grid(row=0, column=0, sticky="w")

        self.backup_path_var = tk.StringVar(value="backup/library_backup.dump")
        ttk.Entry(box, textvariable=self.backup_path_var, width=60).grid(row=0, column=1, sticky="w", padx=(8, 0))

        ttk.Button(box, text="Выбрать...", command=self._choose_backup_path).grid(row=0, column=2, sticky="w",
                                                                                 padx=(8, 0))
        ttk.Button(box, text="Сделать бэкап", command=self._do_backup).grid(row=1, column=1, sticky="w",
                                                                            pady=(10, 0))

        self.backup_info = ttk.Label(box, text="Лог: logs/backup.log", foreground="#444")
        self.backup_info.grid(row=2, column=0, columnspan=3, sticky="w", pady=(10, 0))

        box2 = ttk.LabelFrame(tab, text="pg_restore (восстановить из дампа)", padding=12)
        box2.pack(fill="x", pady=(12, 0))

        ttk.Label(box2, text="Дамп для восстановления (.dump):").grid(row=0, column=0, sticky="w")

        self.restore_path_var = tk.StringVar(value="backup/library_backup.dump")
        ttk.Entry(box2, textvariable=self.restore_path_var, width=60).grid(row=0, column=1, sticky="w", padx=(8, 0))

        ttk.Button(box2, text="Выбрать...", command=self._choose_restore_path).grid(row=0, column=2, sticky="w",
                                                                                   padx=(8, 0))

        ttk.Label(
            box2,
            text="ВНИМАНИЕ: восстановление перезатрёт текущую базу (clean).",
            foreground="#a00"
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 0))

        ttk.Button(box2, text="Восстановить из дампа", command=self._do_restore).grid(row=2, column=1, sticky="w",
                                                                                     pady=(10, 0))

    def _choose_backup_path(self):
        path = filedialog.asksaveasfilename(defaultextension=".dump",
                                            filetypes=[("PostgreSQL dump", "*.dump"), ("All files", "*.*")],
                                            title="Куда сохранить бэкап")
        if path:
            self.backup_path_var.set(path)

    def _choose_restore_path(self):
        path = filedialog.askopenfilename(filetypes=[("PostgreSQL dump", "*.dump"), ("All files", "*.*")],
                                          title="Выберите дамп для восстановления")
        if path:
            self.restore_path_var.set(path)

    def _do_backup(self):
        ok, msg = make_backup(self.session, self.backup_path_var.get())
        messagebox.showinfo("Готово", msg) if ok else messagebox.showerror("Ошибка", msg)

    def _do_restore(self):
        path = self.restore_path_var.get().strip()
        if not path:
            messagebox.showwarning("Ошибка", "Укажи файл дампа.")
            return
        if not messagebox.askyesno(
            "Подтверждение",
            "Точно восстановить БД из дампа?\nТекущие данные будут перезаписаны.",
        ):
            return
        ok, msg = restore_backup(self.session, path)
        messagebox.showinfo("Готово", msg) if ok else messagebox.showerror("Ошибка", msg)

    # Вкладка пользователи
    def _build_users_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Пользователи")
        self.tabs["Пользователи"] = tab

        self.users_tree = ttk.Treeview(
            tab,
            columns=("id", "login", "full_name", "phone", "is_active", "roles"),
            show="headings",
            height=22
        )
        headers = {
            "id": "ID",
            "login": "Логин",
            "full_name": "ФИО",
            "phone": "Телефон",
            "is_active": "Активен",
            "roles": "Роли",
        }
        for c, w in [
            ("id", 70),
            ("login", 140),
            ("full_name", 300),
            ("phone", 160),
            ("is_active", 100),
            ("roles", 220),
        ]:
            self.users_tree.heading(c, text=headers.get(c, c))
            self.users_tree.column(c, width=w, anchor="w")
        self._enable_grid(self.users_tree)

        top = ttk.Frame(tab)
        top.pack(fill="x")

        ttk.Button(top, text="Обновить", command=self._load_users).pack(side="left")
        self._add_search_box(top, self.users_tree, "Поиск:")

        ttk.Label(top, text="Показать:").pack(side="left", padx=(12, 4))
        self.user_filter_var = tk.StringVar(value="Все")

        cb = ttk.Combobox(
            top,
            textvariable=self.user_filter_var,
            values=["Все", "Только библиотекари", "Только читатели"],
            state="readonly",
            width=22
        )
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda e: self._load_users())

        self.btn_reg_lib = ttk.Button(top, text="Регистрация нового библиотекаря", command=self._ui_register_librarian)
        self.btn_reg_lib.pack(side="right")

        self.btn_edit_user = ttk.Button(top, text="Редактировать (ФИО/телефон)", command=self._ui_edit_user)
        self.btn_edit_user.pack(side="right", padx=8)

        self.btn_user_toggle = ttk.Button(top, text="Вкл/Выкл выбранного", command=self._ui_toggle_user)
        self.btn_user_toggle.pack(side="right", padx=8)

        self.btn_user_reset_pw = ttk.Button(top, text="Сбросить пароль", command=self._ui_reset_password)
        self.btn_user_reset_pw.pack(side="right", padx=8)

        self.btn_user_delete = ttk.Button(top, text="Удалить пользователя", command=self._ui_delete_user)
        self.btn_user_delete.pack(side="right", padx=8)

        self.users_tree.pack(fill="both", expand=True, pady=(10, 0))

        self._load_users()

    def _filter_to_role(self):
        v = self.user_filter_var.get()
        if v == "Только библиотекари":
            return "Librarian"
        if v == "Только читатели":
            return "Reader"
        return None

    def _load_users(self):
        role = self._filter_to_role()
        rows = list_users_filtered(role)

        data = []
        for r in rows:
            roles_ru = roles_label_list(r.get("roles") or "")
            data.append((
                r["id"],
                r["login"],
                r["full_name"],
                r.get("phone") or "",
                "Да" if r["is_active"] else "Нет",
                roles_ru
            ))
        self._set_tree_data(self.users_tree, data)

    def _get_selected_user_row(self):
        sel = self.users_tree.selection()
        if not sel:
            return None
        return self.users_tree.item(sel[0], "values")

    def _get_selected_user_id(self):
        vals = self._get_selected_user_row()
        if not vals:
            return None
        return int(vals[0])

    def _ui_register_librarian(self):
        dlg = RegisterLibrarianDialog(self)
        self.wait_window(dlg)
        if not dlg.result:
            return

        ok, msg = admin_register_librarian(
            session=self.session,
            login=dlg.result["login"],
            full_name=dlg.result["full_name"],
            phone=dlg.result["phone"],
            password=dlg.result["password"]
        )
        messagebox.showinfo("Ок", msg) if ok else messagebox.showerror("Ошибка", msg)
        if ok:
            self._load_users()

    def _ui_toggle_user(self):
        user_id = self._get_selected_user_id()
        if not user_id:
            messagebox.showwarning("Ошибка", "Выберите пользователя.")
            return

        vals = self._get_selected_user_row()
        current_active = (vals[4] == "Да")
        new_active = not current_active

        ok, msg = set_user_active(self.session, user_id, new_active)
        messagebox.showinfo("Ок", msg) if ok else messagebox.showerror("Ошибка", msg)
        if ok:
            self._load_users()

    def _ui_reset_password(self):
        user_id = self._get_selected_user_id()
        if not user_id:
            messagebox.showwarning("Ошибка", "Выберите пользователя.")
            return

        dlg = ResetPasswordDialog(self)
        self.wait_window(dlg)
        if not dlg.result:
            return

        ok, msg = reset_user_password(self.session, user_id, dlg.result)
        messagebox.showinfo("Ок", msg) if ok else messagebox.showerror("Ошибка", msg)

    def _ui_edit_user(self):
        vals = self._get_selected_user_row()
        if not vals:
            messagebox.showwarning("Ошибка", "Выберите пользователя.")
            return

        user_id = int(vals[0])
        current_full_name = vals[2]
        current_phone = vals[3]

        dlg = EditUserDialog(self, current_full_name, current_phone)
        self.wait_window(dlg)
        if not dlg.result:
            return

        ok, msg = update_user_profile(self.session, user_id, dlg.result["full_name"], dlg.result["phone"])
        messagebox.showinfo("Ок", msg) if ok else messagebox.showerror("Ошибка", msg)
        if ok:
            self._load_users()

    def _ui_delete_user(self):
        user_id = self._get_selected_user_id()
        if not user_id:
            messagebox.showwarning("Ошибка", "Выберите пользователя.")
            return

        vals = self._get_selected_user_row()
        login = vals[1] if vals else str(user_id)

        if not messagebox.askyesno(
            "Подтверждение",
            f"Точно удалить пользователя '{login}'?\nЭто действие необратимо.",
        ):
            return

        ok, msg = delete_user(self.session, user_id)
        messagebox.showinfo("Ок", msg) if ok else messagebox.showerror("Ошибка", msg)
        if ok:
            self._load_users()

    def _logout(self):
        if messagebox.askyesno("Выход", "Выйти из аккаунта?"):
            self.logged_out = True
            self.destroy()
