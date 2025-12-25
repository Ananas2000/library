from __future__ import annotations

from datetime import date, timedelta
from typing import Optional, List, Tuple, Dict

from app.db import db
from app.auth import hash_password
from app.models import (
    Role, User, UserRole,
    Publisher, Author, Genre, Book,
    BookAuthor, BookGenre,
    Branch, Location, Copy,
    Loan
)

DEFAULT_USERS: List[Tuple[str, str, Optional[str], str, str]] = [
    ("admin",     "Калашников Егор Олегович",           "+70000000001", "admin123", "Admin"),
    ("lib", "Черкизов Никита",    "+70000000002", "lib123",   "Librarian"),
    ("kap213",    "Сарделькин Валерий Сидорович", "+70000000003", "1234",  "Reader"),
]

# Права системы (ключи):
# - manage_users: управление пользователями (только админ)
# - manage_catalog: CRUD книг/экземпляров
# - manage_loans: выдача/возврат/просрочки
# - view_reports: доступ к вкладке отчётов
# - export_tables: доп. отчёты-таблицы (только админ)
# - backup: бэкап/восстановление
# - create_reservation: создавать резервы
# - manage_own_reservations: отмена/продление своих резервов
# - manage_reservations: выдача по резерву (staff)
ROLE_RIGHTS: Dict[str, Dict[str, bool]] = {
    "Admin": {
        "all": True,
        "manage_users": True,
        "manage_catalog": True,
        "manage_loans": True,
        "view_reports": True,
        "export_tables": True,
        "backup": True,
        "create_reservation": True,
        "manage_own_reservations": True,
        "manage_reservations": True,
    },
    "Librarian": {
        "manage_catalog": True,
        "manage_loans": True,
        "view_reports": True,
        "backup": False,         # только админ
        "export_tables": False,  # только админ
        "manage_users": False,
        "manage_reservations": True,
    },
    "Reader": {
        "view_reports": False,
        "manage_catalog": False,
        "manage_loans": False,
        "backup": False,
        "manage_users": False,
        "export_tables": False,
        "create_reservation": True,
        "manage_own_reservations": True,
    }
}


def upsert_role(name: str, rights: Dict[str, bool]):
    Role.get_or_create(name=name, defaults={"rights": rights})


def upsert_user(login: str, full_name: str, phone: Optional[str], password: str) -> User:
    user, created = User.get_or_create(
        login=login,
        defaults={
            "full_name": full_name,
            "phone": phone,
            "password_hash": hash_password(password),
            "is_active": True,
        }
    )
    if not created:
        user.full_name = full_name
        user.phone = phone
        user.password_hash = hash_password(password)
        user.is_active = True
        user.save()
    return user


def assign_role(user: User, role_name: str):
    role = Role.get(Role.name == role_name)
    UserRole.get_or_create(user=user, role=role)


def get_or_create_publisher(name: str, city: Optional[str] = None, country: Optional[str] = None) -> Publisher:
    p, _ = Publisher.get_or_create(name=name, defaults={"city": city, "country": country})
    return p


def get_or_create_author(full_name: str, birth_year: Optional[int] = None, death_year: Optional[int] = None) -> Author:
    a, _ = Author.get_or_create(full_name=full_name, defaults={"birth_year": birth_year, "death_year": death_year})
    return a


def get_or_create_genre(name: str) -> Genre:
    g, _ = Genre.get_or_create(name=name)
    return g


def get_or_create_book(
    title: str,
    publisher: Optional[Publisher],
    publish_year: Optional[int] = None,
    pages_count: Optional[int] = None,
    language: str = "ru",
) -> Book:
    b, _ = Book.get_or_create(
        title=title,
        defaults={
            "publisher": publisher,
            "publish_year": publish_year,
            "pages_count": pages_count,
            "language": language,
        }
    )
    return b


def link_book_author(book: Book, author: Author):
    BookAuthor.get_or_create(book=book, author=author)


def link_book_genre(book: Book, genre: Genre):
    BookGenre.get_or_create(book=book, genre=genre)


def get_or_create_branch(name: str, address: Optional[str], phone: Optional[str]) -> Branch:
    br, _ = Branch.get_or_create(name=name, defaults={"address": address, "phone": phone})
    return br


def get_or_create_location(branch: Branch, code: str, description: Optional[str]) -> Location:
    loc, _ = Location.get_or_create(branch=branch, code=code, defaults={"description": description})
    return loc


def _inv_code(n: int) -> str:
    return f"INV-{str(n).zfill(4)}"


def _ensure_copy(
    book: Book,
    location: Optional[Location],
    inv: str,
    status: str = "available",
    price: Optional[float] = None,
    condition_note: Optional[str] = None
) -> Copy:
    c, created = Copy.get_or_create(
        inventory_code=inv,
        defaults={
            "book": book,
            "location": location,
            "status": status,
            "price": price,
            "condition_note": condition_note,
        }
    )
    if not created:
        c.book = book
        c.location = location
        c.status = status
        c.price = price
        c.condition_note = condition_note
        c.save()
    return c


def _ensure_loan_for_copy(
    copy: Copy,
    reader: User,
    librarian: User,
    status: str,
    start: date,
    due: date,
    returned: Optional[date] = None
) -> None:
    exists = (
        Loan.select(Loan.id)
        .where((Loan.copy == copy) & (Loan.status.in_(("open", "overdue"))))
        .limit(1)
        .exists()
    )
    if exists:
        return

    Loan.create(
        copy=copy,
        reader=reader,
        librarian=librarian,
        status=status,
        start_date=start,
        due_date=due,
        return_date=returned
    )


def run_seed():
    db.connect(reuse_if_open=True)
    try:
        with db.atomic():
            # --- Roles
            for role_name, rights in ROLE_RIGHTS.items():
                upsert_role(role_name, rights)

            # --- Users
            users: Dict[str, User] = {}
            for login, full_name, phone, pwd, role in DEFAULT_USERS:
                u = upsert_user(login, full_name, phone, pwd)
                assign_role(u, role)
                users[login] = u

            librarian = users["lib"]
            reader = users["kap213"]

            # --- Publishers
            ast = get_or_create_publisher("АСТ", "Москва", "Россия")
            eksmo = get_or_create_publisher("Эксмо", "Москва", "Россия")
            piter = get_or_create_publisher("Питер", "Санкт-Петербург", "Россия")
            azb = get_or_create_publisher("Азбука", "Санкт-Петербург", "Россия")

            # --- Authors
            dost = get_or_create_author("Достоевский Фёдор", 1821, 1881)
            tolst = get_or_create_author("Толстой Лев", 1828, 1910)
            bulg = get_or_create_author("Булгаков Михаил", 1891, 1940)
            push = get_or_create_author("Пушкин Александр", 1799, 1837)
            gog = get_or_create_author("Гоголь Николай", 1809, 1852)

            # --- Genres
            klass = get_or_create_genre("Классика")
            roman = get_or_create_genre("Роман")
            fantasy = get_or_create_genre("Фантастика")
            poetry = get_or_create_genre("Поэзия")
            drama = get_or_create_genre("Драма")

            # --- Books
            books: List[Book] = []

            b1 = get_or_create_book("Преступление и наказание", ast, 1866, 672)
            link_book_author(b1, dost)
            link_book_genre(b1, klass); link_book_genre(b1, roman)
            books.append(b1)

            b2 = get_or_create_book("Идиот", eksmo, 1869, 640)
            link_book_author(b2, dost)
            link_book_genre(b2, klass); link_book_genre(b2, roman)
            books.append(b2)

            b3 = get_or_create_book("Война и мир", eksmo, 1869, 1225)
            link_book_author(b3, tolst)
            link_book_genre(b3, klass); link_book_genre(b3, roman)
            books.append(b3)

            b4 = get_or_create_book("Анна Каренина", ast, 1877, 864)
            link_book_author(b4, tolst)
            link_book_genre(b4, klass); link_book_genre(b4, roman)
            books.append(b4)

            b5 = get_or_create_book("Мастер и Маргарита", azb, 1967, 480)
            link_book_author(b5, bulg)
            link_book_genre(b5, klass); link_book_genre(b5, roman); link_book_genre(b5, fantasy)
            books.append(b5)

            b6 = get_or_create_book("Собачье сердце", piter, 1925, 240)
            link_book_author(b6, bulg)
            link_book_genre(b6, klass); link_book_genre(b6, roman)
            books.append(b6)

            b7 = get_or_create_book("Евгений Онегин", ast, 1833, 224)
            link_book_author(b7, push)
            link_book_genre(b7, klass); link_book_genre(b7, poetry)
            books.append(b7)

            b8 = get_or_create_book("Капитанская дочка", eksmo, 1836, 192)
            link_book_author(b8, push)
            link_book_genre(b8, klass); link_book_genre(b8, roman)
            books.append(b8)

            b9 = get_or_create_book("Мёртвые души", azb, 1842, 352)
            link_book_author(b9, gog)
            link_book_genre(b9, klass); link_book_genre(b9, roman)
            books.append(b9)

            b10 = get_or_create_book("Ревизор", piter, 1836, 160)
            link_book_author(b10, gog)
            link_book_genre(b10, klass); link_book_genre(b10, drama)
            books.append(b10)

            # --- Branches & Locations
            br1 = get_or_create_branch("Главный филиал", "ул Пушкина 1", "+70000001000")
            br2 = get_or_create_branch("Филиал Север", "пр. Мира 10", "+70000002000")
            br3 = get_or_create_branch("Филиал Юг", "ул Ленина 5", "+70000003000")

            locations: List[Location] = [
                get_or_create_location(br1, "A-1", "Зал A, стеллаж 1"),
                get_or_create_location(br1, "A-2", "Зал A, стеллаж 2"),
                get_or_create_location(br2, "B-1", "Зал B, стеллаж 1"),
                get_or_create_location(br2, "B-2", "Зал B, стеллаж 2"),
                get_or_create_location(br3, "C-1", "Зал C, стеллаж 1"),
                get_or_create_location(br3, "C-2", "Зал C, стеллаж 2"),
            ]

            # --- Copies: много экземпляров
            cur = db.execute_sql(
                """
                SELECT COALESCE(
                    MAX(CAST(SUBSTRING(inventory_code FROM '([0-9]+)$') AS INT)),
                    0
                )
                FROM copies
                WHERE inventory_code ~ '^INV\\-[0-9]+$'
                """
            )
            max_n = cur.fetchone()[0] or 0
            inv_counter = int(max_n)

            def next_inv() -> str:
                nonlocal inv_counter
                inv_counter += 1
                return _inv_code(inv_counter)

            copies_by_book: Dict[int, List[Copy]] = {}
            for idx, book in enumerate(books):
                cnt = 8 + (idx % 5)  # 8..12
                copies: List[Copy] = []
                for i in range(cnt):
                    loc = locations[(idx + i) % len(locations)]
                    inv = next_inv()

                    status = "available"
                    if i == cnt - 1 and idx % 3 == 0:
                        status = "reserved"
                    elif i == cnt - 2 and idx % 7 == 0:
                        status = "damaged"
                    elif i == cnt - 3 and idx % 9 == 0:
                        status = "lost"

                    price = 350 + (idx * 50) + (i * 10)
                    c = _ensure_copy(book, loc, inv, status=status, price=price)
                    copies.append(c)

                copies_by_book[book.id] = copies

            # --- Loans: делаем 1 открытую и 1 просроченную на одного читателя
            open_copy = None
            for book in books:
                for c in copies_by_book[book.id]:
                    if c.status == "available":
                        open_copy = c
                        break
                if open_copy:
                    break

            if open_copy:
                open_copy.status = "loaned"
                open_copy.save()
                start = date.today()
                due = start + timedelta(days=14)
                _ensure_loan_for_copy(open_copy, reader, librarian, "open", start, due)

            overdue_copy = None
            for book in reversed(books):
                for c in copies_by_book[book.id]:
                    if c.status == "available":
                        overdue_copy = c
                        break
                if overdue_copy:
                    break

            if overdue_copy:
                overdue_copy.status = "loaned"
                overdue_copy.save()
                start = date.today() - timedelta(days=30)
                due = date.today() - timedelta(days=7)
                _ensure_loan_for_copy(overdue_copy, reader, librarian, "overdue", start, due)

    finally:
        if not db.is_closed():
            db.close()


if __name__ == "__main__":
    run_seed()
    print("Seed OK.")
    print("Users:")
    print("  admin / admin123")
    print("  lib / lib123")
    print("  kap213 / 1234")