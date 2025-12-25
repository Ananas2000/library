from typing import List, Dict, Any, Optional, Tuple

from peewee import fn, JOIN, Case, IntegrityError

from app.db import db
from app.models import (
    Book, Publisher,
    Author, BookAuthor,
    Copy, Location, Branch, Loan
)

# Допустимые статусы экземпляра
_ALLOWED_COPY_STATUSES = ("available", "loaned", "reserved", "lost", "damaged")


def _generate_next_inventory_code(prefix: str = "INV-", width: int = 4) -> str:
    """Генерирует следующий инвентарный код вида INV-0001"""
    sql = """
        SELECT COALESCE(
            MAX(CAST(SUBSTRING(inventory_code FROM '([0-9]+)$') AS INT)),
            0
        )
        FROM copies
        WHERE inventory_code ~ %s
    """

    prefix_re = prefix.replace("\\", "\\\\").replace("-", "\\-")
    full_regex = r"^" + prefix_re + r"[0-9]+$"

    cur = db.execute_sql(sql, (full_regex,))
    max_n = cur.fetchone()[0] or 0
    return f"{prefix}{str(max_n + 1).zfill(width)}"


# -------------------
# AUTHORS
# -------------------
def list_authors() -> List[Dict[str, Any]]:
    """
    Справочник авторов для GUI: id + full_name.
    """
    q = Author.select(Author.id, Author.full_name).order_by(Author.full_name.asc())
    return list(q.dicts())


def get_book_author_ids(book_id: int) -> List[int]:
    q = (BookAuthor
         .select(BookAuthor.author_id)
         .where(BookAuthor.book_id == book_id))
    return [r.author_id for r in q]


def _authors_subquery():
    """
    Подзапрос: book_id -> "Автор1, Автор2"
    """
    return (
        BookAuthor
        .select(
            BookAuthor.book.alias("book_id"),
            fn.STRING_AGG(Author.full_name, ", ").alias("authors")
        )
        .join(Author)
        .group_by(BookAuthor.book)
        .alias("ba")
    )


def _reader_stats_subquery():
    """
    Подзапрос: book_id -> available_count + ближайшая due_date по open/overdue
    """
    avail_count = fn.SUM(
        Case(None, ((Copy.status == "available", 1),), 0)
    ).alias("available_count")

    next_due = fn.MIN(Loan.due_date).alias("next_due")

    return (
        Copy
        .select(
            Copy.book.alias("book_id"),
            avail_count,
            next_due
        )
        .join(
            Loan,
            JOIN.LEFT_OUTER,
            on=((Loan.copy == Copy.id) & (Loan.status.in_(("open", "overdue"))))
        )
        .group_by(Copy.book)
        .alias("st")
    )


# ---------- справочники ----------
def list_publishers() -> List[Dict[str, Any]]:
    return list(Publisher.select(Publisher.id, Publisher.name).order_by(Publisher.name).dicts())


def list_locations() -> List[Dict[str, Any]]:
    q = (Location
         .select(Location.id, Location.code, Branch.name.alias("branch_name"))
         .join(Branch)
         .order_by(Branch.name, Location.code))
    return list(q.dicts())


# ---------- книги ----------
def list_books() -> List[Dict[str, Any]]:
    """
    Для staff/admin: книга + издательство + авторы.
    """
    ba = _authors_subquery()

    q = (Book
         .select(
             Book.id, Book.title, Book.language, Book.publish_year, Book.pages_count,
             Publisher.name.alias("publisher"),
             ba.c.authors.alias("authors")
         )
         .join(Publisher, join_type=JOIN.LEFT_OUTER)
         .switch(Book)
         .join(ba, JOIN.LEFT_OUTER, on=(ba.c.book_id == Book.id))
         .order_by(Book.title.asc()))
    return list(q.dicts())


def list_books_reader_view() -> List[Dict[str, Any]]:
    """
    Для читателя: книга + авторы + издательство + сколько available + ближайшая due_date
    """
    ba = _authors_subquery()
    st = _reader_stats_subquery()

    q = (Book
         .select(
             Book.id, Book.title, Book.publish_year,
             Publisher.name.alias("publisher"),
             ba.c.authors.alias("authors"),
             fn.COALESCE(st.c.available_count, 0).alias("available_count"),
             st.c.next_due.alias("next_due")
         )
         .join(Publisher, JOIN.LEFT_OUTER)
         .switch(Book)
         .join(ba, JOIN.LEFT_OUTER, on=(ba.c.book_id == Book.id))
         .switch(Book)
         .join(st, JOIN.LEFT_OUTER, on=(st.c.book_id == Book.id))
         .order_by(Book.title.asc()))

    return list(q.dicts())


def create_book(
    title: str,
    language: str,
    publish_year: Optional[int],
    pages_count: Optional[int],
    publisher_id: Optional[int],
    author_ids: Optional[List[int]] = None
) -> Tuple[bool, str]:
    title = (title or "").strip()
    language = (language or "ru").strip()
    author_ids = author_ids or []

    if not title:
        return False, "Название книги пустое."

    publisher = Publisher.get_or_none(Publisher.id == publisher_id) if publisher_id else None

    with db.atomic():
        book = Book.create(
            title=title,
            language=language or "ru",
            publish_year=publish_year,
            pages_count=pages_count,
            publisher=publisher
        )

        # привязка авторов
        for aid in author_ids:
            if Author.get_or_none(Author.id == aid):
                BookAuthor.get_or_create(book=book, author=aid)

    return True, "Книга добавлена."


def update_book(
    book_id: int,
    title: str,
    language: str,
    publish_year: Optional[int],
    pages_count: Optional[int],
    publisher_id: Optional[int],
    author_ids: Optional[List[int]] = None
) -> Tuple[bool, str]:
    book = Book.get_or_none(Book.id == book_id)
    if not book:
        return False, "Книга не найдена."

    title = (title or "").strip()
    language = (language or "ru").strip()
    author_ids = author_ids or []

    if not title:
        return False, "Название книги пустое."

    publisher = Publisher.get_or_none(Publisher.id == publisher_id) if publisher_id else None

    with db.atomic():
        book.title = title
        book.language = language or "ru"
        book.publish_year = publish_year
        book.pages_count = pages_count
        book.publisher = publisher
        book.save()

        # перезаписать авторов
        BookAuthor.delete().where(BookAuthor.book == book).execute()
        for aid in author_ids:
            if Author.get_or_none(Author.id == aid):
                BookAuthor.get_or_create(book=book, author=aid)

    return True, "Книга обновлена."


def delete_book(book_id: int) -> Tuple[bool, str]:
    book = Book.get_or_none(Book.id == book_id)
    if not book:
        return False, "Книга не найдена."

    copies_cnt = Copy.select(fn.COUNT(Copy.id)).where(Copy.book == book).scalar() or 0
    if copies_cnt > 0:
        return False, f"Нельзя удалить: у книги есть экземпляры ({copies_cnt}). Сначала удалите экземпляры."

    with db.atomic():
        BookAuthor.delete().where(BookAuthor.book == book).execute()
        book.delete_instance()
    return True, "Книга удалена."


# ---------- экземпляры ----------
def list_copies_for_book(book_id: int) -> List[Dict[str, Any]]:
    q = (Copy
         .select(
             Copy.id, Copy.inventory_code, Copy.status, Copy.price, Copy.condition_note,
             Location.code.alias("location_code"),
             Branch.name.alias("branch_name")
         )
         .join(Location, join_type=JOIN.LEFT_OUTER)
         .join(Branch, join_type=JOIN.LEFT_OUTER)
         .where(Copy.book_id == book_id)
         .order_by(Copy.inventory_code.asc()))
    return list(q.dicts())


def create_copy(book_id: int, inventory_code: str, status: str, price: Optional[float],
                location_id: Optional[int], condition_note: Optional[str]) -> Tuple[bool, str]:
    inventory_code = (inventory_code or "").strip()
    status = (status or "available").strip()

    if status not in _ALLOWED_COPY_STATUSES:
        return False, "Неверный статус экземпляра."

    book = Book.get_or_none(Book.id == book_id)
    if not book:
        return False, "Книга не найдена."

    loc = Location.get_or_none(Location.id == location_id) if location_id else None

    if inventory_code and Copy.get_or_none(Copy.inventory_code == inventory_code):
        return False, "Такой инвентарный код уже существует."

    with db.atomic():
        code = inventory_code or _generate_next_inventory_code()

        for _ in range(20):
            try:
                Copy.create(
                    book=book,
                    inventory_code=code,
                    status=status,
                    price=price,
                    location=loc,
                    condition_note=condition_note
                )
                return True, f"Экземпляр добавлен. Инв. код: {code}"
            except IntegrityError:
                if inventory_code:
                    return False, "Такой инвентарный код уже существует."
                code = _generate_next_inventory_code()

    return False, "Не удалось сгенерировать уникальный инвентарный код."


def update_copy(copy_id: int, inventory_code: str, status: str, price: Optional[float],
                location_id: Optional[int], condition_note: Optional[str]) -> Tuple[bool, str]:
    copy = Copy.get_or_none(Copy.id == copy_id)
    if not copy:
        return False, "Экземпляр не найден."

    inventory_code = (inventory_code or "").strip()
    status = (status or "available").strip()
    if not inventory_code:
        return False, "Инвентарный код пустой."
    if status not in _ALLOWED_COPY_STATUSES:
        return False, "Неверный статус экземпляра."

    exists = (Copy
              .select(Copy.id)
              .where((Copy.inventory_code == inventory_code) & (Copy.id != copy.id))
              .limit(1)
              .exists())
    if exists:
        return False, "Такой инвентарный код уже существует."

    loc = Location.get_or_none(Location.id == location_id) if location_id else None

    with db.atomic():
        copy.inventory_code = inventory_code
        copy.status = status
        copy.price = price
        copy.location = loc
        copy.condition_note = condition_note
        try:
            copy.save()
        except IntegrityError:
            return False, "Такой инвентарный код уже существует."

    return True, "Экземпляр обновлён."


def delete_copy(copy_id: int) -> Tuple[bool, str]:
    copy = Copy.get_or_none(Copy.id == copy_id)
    if not copy:
        return False, "Экземпляр не найден."

    loans_cnt = Loan.select(fn.COUNT(Loan.id)).where(Loan.copy == copy).scalar() or 0
    if loans_cnt > 0:
        return False, f"Нельзя удалить: у экземпляра есть выдачи ({loans_cnt})."

    with db.atomic():
        copy.delete_instance()
    return True, "Экземпляр удалён."
