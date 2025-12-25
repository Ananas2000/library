from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Callable, Union

from peewee import fn, JOIN, IntegrityError, Case

from app.db import db, DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT
from app.auth import verify_password, hash_password
from app.models import (
    User, Role, UserRole,
    Publisher, Author, Genre,
    Book, BookAuthor, BookGenre,
    Branch, Location, Copy,
    Loan, Reservation,
)


# Русификация заголовков/статусов/ролей (GUI + экспорт)
RU_COL = {
    "id": "ID",
    "name": "Название",
    "title": "Название",
    "status": "Статус",
    "created_at": "Создано",
    "is_active": "Активен",
    "login": "Логин",
    "full_name": "ФИО",
    "phone": "Телефон",
    "roles": "Роли",
    "rights": "Права",
    "role": "Роль",
    "user_id": "ID пользователя",
    "role_id": "ID роли",
    "user_login": "Логин пользователя",
    "book_id": "ID книги",
    "book_title": "Книга",
    "authors": "Авторы",
    "publisher": "Издательство",
    "publisher_id": "ID издательства",
    "publisher_name": "Издательство",
    "publish_year": "Год издания",
    "pages_count": "Страниц",
    "language": "Язык",
    "author_id": "ID автора",
    "author_full_name": "Автор",
    "genre_id": "ID жанра",
    "genre_name": "Жанр",
    "inventory_code": "Инв. код",
    "price": "Цена",
    "condition_note": "Примечание",
    "location_id": "ID локации",
    "location_code": "Локация",
    "branch_id": "ID филиала",
    "branch_name": "Филиал",
    "branch_address": "Адрес филиала",
    "loan_id": "ID выдачи",
    "start_date": "Дата выдачи",
    "due_date": "Срок до",
    "return_date": "Дата возврата",
    "copy_id": "ID экземпляра",
    "reader_id": "ID читателя",
    "reader_login": "Логин читателя",
    "reader_name": "Читатель",
    "reader_phone": "Телефон читателя",
    "librarian_id": "ID библиотекаря",
    "librarian_login": "Логин библиотекаря",
    "librarian_name": "Библиотекарь",
    "reservation_id": "ID резерва",
    "pickup_date": "Дата получения",
    "expires_at": "Действует до",
    "extended_once": "Продлевали",
    "inv": "Инв. код",
    "available_count": "Доступно",
    "next_due": "Ближайший возврат",
    "total": "Всего",
    "available": "В наличии",
    "loaned": "Выдано",
    "reserved": "В резерве",
    "lost": "Утеряно",
    "damaged": "Повреждено",
}

ROLE_RU = {
    "Admin": "Администратор",
    "Librarian": "Библиотекарь",
    "Reader": "Читатель",
}
ROLE_EN = {v: k for k, v in ROLE_RU.items()}


def role_label(role_code: Any) -> str:
    s = "" if role_code is None else str(role_code)
    return ROLE_RU.get(s, s)


def roles_label_list(roles_value: Any) -> str:
    if roles_value is None:
        return ""
    if isinstance(roles_value, (list, tuple, set)):
        parts = [str(x).strip() for x in roles_value if str(x).strip()]
    else:
        s = str(roles_value).strip()
        if not s:
            return ""
        parts = [p.strip() for p in s.split(",") if p.strip()]
    return ", ".join(role_label(p) for p in parts)


COPY_STATUS_RU = {
    "available": "В наличии",
    "loaned": "Выдан",
    "reserved": "В резерве",
    "lost": "Утерян",
    "damaged": "Повреждён",
}
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


def ru_header(key: str) -> str:
    return RU_COL.get(key, key)


def _yes_no(v: Any) -> str:
    return "Да" if bool(v) else "Нет"


def _detect_status_domain(row: Optional[Dict[str, Any]]) -> str:
    if not row:
        return ""
    keys = set(row.keys())
    if "loan_id" in keys or "due_date" in keys or "start_date" in keys or "return_date" in keys:
        return "loan"
    if "reservation_id" in keys or "pickup_date" in keys or "expires_at" in keys:
        return "reservation"
    if "inventory_code" in keys and ("condition_note" in keys or "location_code" in keys or "location_id" in keys):
        return "copy"
    return ""


def _looks_like_roles_table_row(row: Optional[Dict[str, Any]]) -> bool:
    if not row:
        return False
    if "rights" not in row:
        return False
    keys = set(row.keys())
    return ("name" in keys) and ("rights" in keys)


def format_cell(key: str, value: Any, row: Optional[Dict[str, Any]] = None) -> Any:
    if value is None:
        return ""

    if key == "role":
        return role_label(value)
    if key == "roles":
        return roles_label_list(value)
    if key == "name" and _looks_like_roles_table_row(row):
        return role_label(value)

    if key in ("is_active", "extended_once"):
        return _yes_no(value)

    if key == "status":
        domain = _detect_status_domain(row)
        s = str(value)
        if domain == "copy":
            return COPY_STATUS_RU.get(s, s)
        if domain == "loan":
            return LOAN_STATUS_RU.get(s, s)
        if domain == "reservation":
            return RES_STATUS_RU.get(s, s)
        return COPY_STATUS_RU.get(s, LOAN_STATUS_RU.get(s, RES_STATUS_RU.get(s, s)))

    if hasattr(value, "isoformat"):
        try:
            return value.isoformat(sep=" ")
        except TypeError:
            return value.isoformat()

    return value


def translate_rows_values(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append({k: format_cell(k, v, r) for k, v in r.items()})
    return out


def translate_rows_for_export(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r in rows:
        nr: Dict[str, Any] = {}
        for k, v in r.items():
            nr[ru_header(k)] = format_cell(k, v, r)
        out.append(nr)
    return out


# ПРАВА (roles.rights -> session.can())
def _normalize_rights(v: Any) -> Dict[str, Any]:
    if v is None:
        return {}
    if isinstance(v, dict):
        return dict(v)
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return {}
        try:
            obj = json.loads(s)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}
    return {}


def get_user_roles(user: User) -> List[str]:
    q = Role.select(Role.name).join(UserRole).where(UserRole.user == user)
    return [r.name for r in q]


def get_user_rights(user: User) -> Dict[str, Any]:
# если где-то all=true -> всё разрешено
# иначе смотрим булевые флаги
    q = (
        Role.select(Role.rights)
        .join(UserRole)
        .where(UserRole.user == user)
    )

    merged: Dict[str, Any] = {}
    for r in q:
        d = _normalize_rights(r.rights)
        if d.get("all") is True:
            return {"all": True}
        for k, val in d.items():
            if k == "all":
                continue
            if isinstance(val, bool):
                if val:
                    merged[k] = True
                else:
                    merged.setdefault(k, False)
            else:
                merged[k] = val

    return merged


ROLE_PRIORITY = ["Admin", "Librarian", "Reader"]


@dataclass
class Session:
    user: User
    roles: List[str]
    rights: Dict[str, Any]

    @property
    def primary_role(self) -> str:
        for r in ROLE_PRIORITY:
            if r in self.roles:
                return r
        return self.roles[0] if self.roles else "Reader"

    def can(self, perm: str) -> bool:
        d = self.rights or {}
        if d.get("all") is True:
            return True
        return bool(d.get(perm))


def authenticate(login: str, password: str) -> Tuple[bool, str, Optional[Session]]:
    login = (login or "").strip()
    password = password or ""

    if not login or not password:
        return False, "Логин/пароль пустые.", None

    user = User.get_or_none(User.login == login)
    if not user:
        return False, "Неверный логин или пароль.", None
    if not user.is_active:
        return False, "Пользователь отключён.", None

    if not verify_password(password, user.password_hash):
        return False, "Неверный логин или пароль.", None

    roles = get_user_roles(user)
    if not roles:
        roles = ["Reader"]

    rights = get_user_rights(user)
    return True, "OK", Session(user=user, roles=roles, rights=rights)


# Пользователи / регистрация
def _ensure_base_roles():
    Role.get_or_create(name="Admin", defaults={"rights": {}})
    Role.get_or_create(name="Librarian", defaults={"rights": {}})
    Role.get_or_create(name="Reader", defaults={"rights": {}})


def _map_user_integrity_error(e: IntegrityError) -> str:
    msg = str(e)

    if "users_login" in msg or ("unique" in msg.lower() and "login" in msg.lower()):
        return "Такой логин уже занят."

    if "ck_users_phone_ru" in msg:
        return "Телефон должен быть в формате +7xxxxxxxxxx (после +7 ровно 10 цифр)."

    if "ck_users_full_name_ru" in msg:
        return "ФИО должно быть русскими буквами: Фамилия Имя [Отчество]."

    return f"Ошибка БД: {msg}"


def _create_user_with_role(
    login: str,
    full_name: str,
    phone: Optional[str],
    password: str,
    role_name: str,
) -> Tuple[bool, str]:
    login = (login or "").strip()
    full_name = (full_name or "").strip()
    phone = (phone or "").strip() or None
    password = password or ""

    if not login or not full_name or not password:
        return False, "Заполните логин, ФИО и пароль."
    if len(password) < 4:
        return False, "Пароль минимум 4 символа."

    _ensure_base_roles()
    role = Role.get(Role.name == role_name)

    try:
        with db.atomic():
            user = User.create(
                login=login,
                full_name=full_name,
                phone=phone,
                password_hash=hash_password(password),
                is_active=True,
            )
            UserRole.create(user=user, role=role)
        return True, f"Пользователь создан ({role_label(role_name)})."
    except IntegrityError as e:
        return False, _map_user_integrity_error(e)
    except Exception as e:
        return False, f"Ошибка создания пользователя: {e}"


def register_self(login: str, full_name: str, phone: Optional[str], password: str) -> Tuple[bool, str]:
    return _create_user_with_role(login, full_name, phone, password, "Reader")


def admin_register_librarian(
    session: Session,
    login: str,
    full_name: str,
    phone: Optional[str],
    password: str,
) -> Tuple[bool, str]:
    if not session.can("manage_users"):
        return False, "Нет прав: управление пользователями."
    return _create_user_with_role(login, full_name, phone, password, "Librarian")


def list_users_with_roles() -> List[Dict[str, Any]]:
    users = list(User.select().order_by(User.id).dicts())
    if not users:
        return []

    q = UserRole.select(UserRole.user_id.alias("user_id"), Role.name.alias("role")).join(Role)
    role_map: Dict[int, List[str]] = {}
    for r in q.dicts():
        role_map.setdefault(r["user_id"], []).append(r["role"])

    for u in users:
        roles = role_map.get(u["id"], [])
        u["roles"] = ", ".join(sorted(roles))
    return users


def list_users_filtered(role_name: Optional[str] = None) -> List[Dict[str, Any]]:
    rows = list_users_with_roles()
    if not role_name:
        return rows
    role_name = role_name.strip()
    return [r for r in rows if role_name in (r.get("roles") or "")]


def update_user_profile(session: Session, user_id: int, full_name: str, phone: Optional[str]) -> Tuple[bool, str]:
    if not session.can("manage_users"):
        return False, "Нет прав: управление пользователями."

    user = User.get_or_none(User.id == user_id)
    if not user:
        return False, "Пользователь не найден."

    full_name = (full_name or "").strip()
    phone = (phone or "").strip() or None
    if not full_name:
        return False, "ФИО пустое."

    user.full_name = full_name
    user.phone = phone
    try:
        user.save()
    except IntegrityError as e:
        return False, _map_user_integrity_error(e)

    return True, "Профиль обновлён."


def set_user_active(session: Session, user_id: int, is_active: bool) -> Tuple[bool, str]:
    if not session.can("manage_users"):
        return False, "Нет прав: управление пользователями."

    user = User.get_or_none(User.id == user_id)
    if not user:
        return False, "Пользователь не найден."

    if user.id == session.user.id and not is_active:
        return False, "Нельзя отключить самого себя."

    if not is_active:
        admin_role = Role.get_or_none(Role.name == "Admin")
        if admin_role:
            is_admin = (
                UserRole.select()
                .where((UserRole.user == user) & (UserRole.role == admin_role))
                .exists()
            )
            if is_admin:
                return False, "Нельзя отключить администратора."

    user.is_active = bool(is_active)
    user.save()
    return True, "Статус обновлён."


def reset_user_password(session: Session, user_id: int, new_password: str) -> Tuple[bool, str]:
    if not session.can("manage_users"):
        return False, "Нет прав: управление пользователями."

    user = User.get_or_none(User.id == user_id)
    if not user:
        return False, "Пользователь не найден."

    new_password = new_password or ""
    if len(new_password) < 4:
        return False, "Пароль минимум 4 символа."

    user.password_hash = hash_password(new_password)
    user.save()
    return True, "Пароль обновлён."


def delete_user(session: Session, user_id: int) -> Tuple[bool, str]:
    if not session.can("manage_users"):
        return False, "Нет прав: управление пользователями."

    user = User.get_or_none(User.id == user_id)
    if not user:
        return False, "Пользователь не найден."

    if user.id == session.user.id:
        return False, "Нельзя удалить самого себя."

    admin_role = Role.get_or_none(Role.name == "Admin")
    if admin_role:
        is_admin = (
            UserRole.select()
            .where((UserRole.user == user) & (UserRole.role == admin_role))
            .exists()
        )
        if is_admin:
            return False, "Нельзя удалить администратора."

    has_loans = (
        Loan.select(Loan.id)
        .where((Loan.reader == user) | (Loan.librarian == user))
        .limit(1)
        .exists()
    )
    if has_loans:
        return False, "Нельзя удалить: у пользователя есть выдачи (история). Лучше его отключить."

    try:
        with db.atomic():
            user.delete_instance()
        return True, "Пользователь удалён."
    except IntegrityError as e:
        return False, f"Ошибка БД при удалении: {e}"
    except Exception as e:
        return False, f"Ошибка удаления: {e}"


# Выдачи
DEFAULT_LOAN_DAYS = 14


def issue_loan(copy_inventory_code: str, reader_login: str, librarian_user: User) -> Tuple[bool, str]:
    copy_inventory_code = (copy_inventory_code or "").strip()
    reader_login = (reader_login or "").strip()

    if not copy_inventory_code or not reader_login:
        return False, "Нужно указать инвентарный код и читателя."

    copy = Copy.get_or_none(Copy.inventory_code == copy_inventory_code)
    if not copy:
        return False, f"Экземпляр {copy_inventory_code} не найден."

    if copy.status != "available":
        return False, f"Экземпляр сейчас не доступен (status={copy.status})."

    reader = User.get_or_none(User.login == reader_login)
    if not reader:
        return False, f"Читатель {reader_login} не найден."

    start = date.today()
    due = start + timedelta(days=DEFAULT_LOAN_DAYS)

    try:
        with db.atomic():
            copy = Copy.select().where(Copy.id == copy.id).for_update().get()
            if copy.status != "available":
                return False, f"Кто-то уже успел забрать (status={copy.status})."

            loan = Loan.create(
                copy=copy,
                reader=reader,
                librarian=librarian_user,
                status="open",
                start_date=start,
                due_date=due,
                return_date=None,
            )
            copy.status = "loaned"
            copy.save()
        return True, f"Выдача оформлена. Loan ID={loan.id}, до {due}."
    except IntegrityError as e:
        return False, f"Ошибка БД: {e}"


def return_loan(loan_id: int, librarian_user: User) -> Tuple[bool, str]:
    loan = Loan.get_or_none(Loan.id == loan_id)
    if not loan:
        return False, "Выдача не найдена."

    if loan.status not in ("open", "overdue"):
        return False, f"Нельзя вернуть выдачу со статусом {loan.status}."

    with db.atomic():
        loan = Loan.select().where(Loan.id == loan_id).for_update().get()
        if loan.status not in ("open", "overdue"):
            return False, f"Уже изменили статус на {loan.status}."

        loan.status = "returned"
        loan.return_date = date.today()
        loan.librarian = librarian_user
        loan.save()

        copy = loan.copy
        copy.status = "available"
        copy.save()

    return True, "Возврат оформлен."


def update_overdue_statuses() -> int:
    today = date.today()
    return Loan.update(status="overdue").where((Loan.status == "open") & (Loan.due_date < today)).execute()


# Отчёты + экспорт
def _authors_subquery():
    return (
        BookAuthor
        .select(
            BookAuthor.book.alias("book_id"),
            fn.STRING_AGG(Author.full_name, ", ").alias("authors"),
        )
        .join(Author)
        .group_by(BookAuthor.book)
        .alias("ba")
    )


def report_active_loans() -> List[Dict[str, Any]]:
    ba = _authors_subquery()

    q = (
        Loan.select(
            Loan.id.alias("loan_id"),
            Loan.status,
            Loan.start_date,
            Loan.due_date,
            Copy.inventory_code.alias("inventory_code"),
            Book.title.alias("book_title"),
            ba.c.authors.alias("authors"),
            User.login.alias("reader_login"),
            User.full_name.alias("reader_name"),
        )
        .join(Copy)
        .join(Book)
        .join(ba, JOIN.LEFT_OUTER, on=(ba.c.book_id == Book.id))
        .switch(Loan)
        .join(User, on=(Loan.reader == User.id))
        .where(Loan.status.in_(["open", "overdue"]))
        .order_by(Loan.due_date.asc())
    )
    return list(q.dicts())


def report_copies_by_book() -> List[Dict[str, Any]]:
    ba = _authors_subquery()

    q = (
        Book.select(
            Book.id.alias("book_id"),
            Book.title.alias("title"),
            ba.c.authors.alias("authors"),
            fn.COUNT(Copy.id).alias("total"),
            fn.SUM(Case(None, ((Copy.status == "available", 1),), 0)).alias("available"),
            fn.SUM(Case(None, ((Copy.status == "loaned", 1),), 0)).alias("loaned"),
            fn.SUM(Case(None, ((Copy.status == "reserved", 1),), 0)).alias("reserved"),
            fn.SUM(Case(None, ((Copy.status == "lost", 1),), 0)).alias("lost"),
            fn.SUM(Case(None, ((Copy.status == "damaged", 1),), 0)).alias("damaged"),
        )
        .join(Copy, on=(Copy.book == Book.id), join_type=JOIN.LEFT_OUTER)
        .switch(Book)
        .join(ba, JOIN.LEFT_OUTER, on=(ba.c.book_id == Book.id))
        .group_by(Book.id, ba.c.authors)
        .order_by(Book.title.asc())
    )
    return list(q.dicts())


def report_table_roles() -> List[Dict[str, Any]]:
    q = Role.select(Role.id, Role.name, Role.rights).order_by(Role.id.asc())
    return list(q.dicts())


def report_table_users() -> List[Dict[str, Any]]:
    q = User.select(User.id, User.login, User.full_name, User.phone, User.is_active, User.created_at).order_by(
        User.id.asc()
    )
    return list(q.dicts())


def report_table_user_roles() -> List[Dict[str, Any]]:
    q = (
        UserRole.select(
            UserRole.user_id.alias("user_id"),
            User.login.alias("user_login"),
            Role.name.alias("role"),
        )
        .join(Role)
        .switch(UserRole)
        .join(User)
        .order_by(UserRole.user_id.asc(), Role.name.asc())
    )
    return list(q.dicts())


def report_table_publishers() -> List[Dict[str, Any]]:
    q = Publisher.select(Publisher.id, Publisher.name, Publisher.city, Publisher.country).order_by(Publisher.id.asc())
    return list(q.dicts())


def report_table_authors() -> List[Dict[str, Any]]:
    q = Author.select(Author.id, Author.full_name, Author.birth_year, Author.death_year).order_by(Author.id.asc())
    return list(q.dicts())


def report_table_genres() -> List[Dict[str, Any]]:
    q = Genre.select(Genre.id, Genre.name).order_by(Genre.id.asc())
    return list(q.dicts())


def report_table_books() -> List[Dict[str, Any]]:
    q = (
        Book.select(
            Book.id,
            Book.title,
            Book.language,
            Book.publish_year,
            Book.pages_count,
            Book.publisher_id.alias("publisher_id"),
            Publisher.name.alias("publisher_name"),
        )
        .join(Publisher, JOIN.LEFT_OUTER)
        .order_by(Book.id.asc())
    )
    return list(q.dicts())


def report_table_book_authors() -> List[Dict[str, Any]]:
    q = (
        BookAuthor.select(
            BookAuthor.book_id.alias("book_id"),
            Book.title.alias("book_title"),
            BookAuthor.author_id.alias("author_id"),
            Author.full_name.alias("author_full_name"),
        )
        .join(Book)
        .switch(BookAuthor)
        .join(Author)
        .order_by(Book.title.asc(), Author.full_name.asc())
    )
    return list(q.dicts())


def report_table_book_genres() -> List[Dict[str, Any]]:
    q = (
        BookGenre.select(
            BookGenre.book_id.alias("book_id"),
            Book.title.alias("book_title"),
            BookGenre.genre_id.alias("genre_id"),
            Genre.name.alias("genre_name"),
        )
        .join(Book)
        .switch(BookGenre)
        .join(Genre)
        .order_by(Book.title.asc(), Genre.name.asc())
    )
    return list(q.dicts())


def report_table_branches() -> List[Dict[str, Any]]:
    q = Branch.select(Branch.id, Branch.name, Branch.address, Branch.phone).order_by(Branch.id.asc())
    return list(q.dicts())


def report_table_locations() -> List[Dict[str, Any]]:
    q = (
        Location.select(
            Location.id,
            Location.branch_id.alias("branch_id"),
            Branch.name.alias("branch_name"),
            Location.code,
            Location.description,
        )
        .join(Branch)
        .order_by(Location.id.asc())
    )
    return list(q.dicts())


def report_table_copies() -> List[Dict[str, Any]]:
    q = (
        Copy.select(
            Copy.id,
            Copy.inventory_code,
            Copy.status,
            Copy.price,
            Copy.condition_note,
            Copy.book_id.alias("book_id"),
            Book.title.alias("book_title"),
            Copy.location_id.alias("location_id"),
            Location.code.alias("location_code"),
            Branch.id.alias("branch_id"),
            Branch.name.alias("branch_name"),
        )
        .join(Book)
        .switch(Copy)
        .join(Location, JOIN.LEFT_OUTER)
        .join(Branch, JOIN.LEFT_OUTER)
        .order_by(Copy.id.asc())
    )
    return list(q.dicts())


def report_table_loans() -> List[Dict[str, Any]]:
    reader = User.alias()
    librarian = User.alias()

    q = (
        Loan.select(
            Loan.id.alias("loan_id"),
            Loan.status,
            Loan.start_date,
            Loan.due_date,
            Loan.return_date,
            Loan.copy_id.alias("copy_id"),
            Copy.inventory_code.alias("inventory_code"),
            Book.title.alias("book_title"),
            reader.id.alias("reader_id"),
            reader.login.alias("reader_login"),
            reader.full_name.alias("reader_name"),
            librarian.id.alias("librarian_id"),
            librarian.login.alias("librarian_login"),
            librarian.full_name.alias("librarian_name"),
        )
        .join(Copy)
        .join(Book)
        .switch(Loan)
        .join(reader, on=(Loan.reader == reader.id))
        .switch(Loan)
        .join(librarian, on=(Loan.librarian == librarian.id))
        .order_by(Loan.id.asc())
    )
    return list(q.dicts())


def report_table_reservations() -> List[Dict[str, Any]]:
    reader = User.alias()

    q = (
        Reservation.select(
            Reservation.id.alias("reservation_id"),
            Reservation.status,
            Reservation.pickup_date,
            Reservation.created_at,
            Reservation.expires_at,
            Reservation.extended_once,
            Reservation.reader_id.alias("reader_id"),
            reader.login.alias("reader_login"),
            reader.full_name.alias("reader_name"),
            Reservation.copy_id.alias("copy_id"),
            Copy.inventory_code.alias("inventory_code"),
            Book.title.alias("book_title"),
            Reservation.branch_id.alias("branch_id"),
            Branch.name.alias("branch_name"),
            Branch.address.alias("branch_address"),
        )
        .join(Copy)
        .join(Book)
        .switch(Reservation)
        .join(Branch)
        .switch(Reservation)
        .join(reader, on=(Reservation.reader == reader.id))
        .order_by(Reservation.id.asc())
    )
    return list(q.dicts())


BASE_REPORTS: Dict[str, Callable[[], List[Dict[str, Any]]]] = {
    "Активные выдачи": report_active_loans,
    "Наличие экземпляров по книгам": report_copies_by_book,
}

TABLE_REPORTS: Dict[str, Callable[[], List[Dict[str, Any]]]] = {
    "Таблица: roles": report_table_roles,
    "Таблица: users": report_table_users,
    "Таблица: user_roles": report_table_user_roles,
    "Таблица: publishers": report_table_publishers,
    "Таблица: authors": report_table_authors,
    "Таблица: genres": report_table_genres,
    "Таблица: books": report_table_books,
    "Таблица: book_authors": report_table_book_authors,
    "Таблица: book_genres": report_table_book_genres,
    "Таблица: branches": report_table_branches,
    "Таблица: locations": report_table_locations,
    "Таблица: copies": report_table_copies,
    "Таблица: loans": report_table_loans,
    "Таблица: reservations": report_table_reservations,
}

REPORTS = BASE_REPORTS


def get_reports_for_role(role_or_session: Union[str, Session]) -> Dict[str, Callable[[], List[Dict[str, Any]]]]:
    if isinstance(role_or_session, Session):
        session = role_or_session
        if not session.can("view_reports"):
            return {}
        out: Dict[str, Callable[[], List[Dict[str, Any]]]] = dict(BASE_REPORTS)
        if session.can("export_tables"):
            out.update(TABLE_REPORTS)
        return out

    role = role_or_session
    out: Dict[str, Callable[[], List[Dict[str, Any]]]] = dict(BASE_REPORTS)
    if (role or "") == "Admin":
        out.update(TABLE_REPORTS)
    return out


def export_json(rows: List[Dict[str, Any]], filepath: str) -> None:
    rows = translate_rows_for_export(rows)
    Path(filepath).write_text(
        json.dumps(rows, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def export_csv(rows: List[Dict[str, Any]], filepath: str) -> None:
    import csv

    rows = translate_rows_for_export(rows)
    if not rows:
        Path(filepath).write_text("", encoding="utf-8-sig")
        return

    headers = list(rows[0].keys())
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(
            f,
            fieldnames=headers,
            delimiter=";",
            quoting=csv.QUOTE_MINIMAL,
        )
        w.writeheader()
        w.writerows(rows)


# Бэкап
def run_pg_dump(output_path: str) -> Tuple[bool, str]:
    output_path = str(output_path)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    log_file = logs_dir / "backup.log"

    cmd = [
        "pg_dump",
        "-h", DB_HOST,
        "-p", str(DB_PORT),
        "-U", DB_USER,
        "-F", "c",
        "-f", output_path,
        DB_NAME,
    ]
    env = os.environ.copy()
    if DB_PASSWORD:
        env["PGPASSWORD"] = DB_PASSWORD

    try:
        res = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if res.returncode != 0:
            msg = f"pg_dump fail ({res.returncode}): {res.stderr.strip()}"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"{date.today()} FAIL {msg}\n")
            return False, msg

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{date.today()} OK Backup to {output_path}\n")
        return True, f"Бэкап готов: {output_path}"

    except FileNotFoundError:
        msg = "pg_dump не найден."
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{date.today()} FAIL {msg}\n")
        return False, msg
    except Exception as e:
        msg = f"Ошибка бэкапа: {e}"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{date.today()} FAIL {msg}\n")
        return False, msg


def make_backup(session: Session, output_path: str) -> Tuple[bool, str]:
    if not session.can("backup"):
        return False, "Нет прав: бэкап/восстановление БД."
    return run_pg_dump(output_path)


def run_pg_restore(input_path: str) -> Tuple[bool, str]:
    input_path = str(input_path)

    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    log_file = logs_dir / "backup.log"

    try:
        if not db.is_closed():
            db.close()
    except Exception:
        pass

    cmd = [
        "pg_restore",
        "-h", DB_HOST,
        "-p", str(DB_PORT),
        "-U", DB_USER,
        "-d", DB_NAME,
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-privileges",
        input_path,
    ]

    env = os.environ.copy()
    if DB_PASSWORD:
        env["PGPASSWORD"] = DB_PASSWORD

    try:
        res = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if res.returncode != 0:
            msg = f"pg_restore fail ({res.returncode}): {res.stderr.strip()}"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"{date.today()} FAIL RESTORE {msg}\n")
            return False, msg

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{date.today()} OK RESTORE from {input_path}\n")

        try:
            db.connect(reuse_if_open=True)
        except Exception:
            pass

        return True, f"Восстановление выполнено из: {input_path}."

    except FileNotFoundError:
        msg = "pg_restore не найден."
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{date.today()} FAIL RESTORE {msg}\n")
        return False, msg
    except Exception as e:
        msg = f"Ошибка восстановления: {e}"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{date.today()} FAIL RESTORE {msg}\n")
        return False, msg


def restore_backup(session: Session, input_path: str) -> Tuple[bool, str]:
    if not session.can("backup"):
        return False, "Нет прав: бэкап/восстановление БД."
    return run_pg_restore(input_path)
