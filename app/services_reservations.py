from __future__ import annotations

from datetime import date, datetime, time, timedelta

from peewee import fn, JOIN

from app.db import db
from app.models import Reservation, Copy, Location, Branch, Book, Loan, User

ACTIVE_LOAN_STATUSES = ("open", "overdue")


def _end_of_day(d: date) -> datetime:
    return datetime.combine(d, time(23, 59, 59))


def expire_old_reservations() -> int:
    """Снимает истёкшие резервы и возвращает копии в available"""
    now = datetime.now()
    with db.atomic():
        q = (Reservation
             .select(Reservation.id, Reservation.copy_id)
             .where((Reservation.status == "active") & (Reservation.expires_at < now)))

        ids = []
        copy_ids = []
        for r in q:
            ids.append(r.id)
            copy_ids.append(r.copy_id)

        if not ids:
            return 0

        Reservation.update(status="expired").where(Reservation.id.in_(ids)).execute()
        Copy.update(status="available").where((Copy.id.in_(copy_ids)) & (Copy.status == "reserved")).execute()
        return len(ids)


def list_available_branches_for_book(book_id: int):
    q = (Branch
         .select(
             Branch.id.alias("branch_id"),
             Branch.name,
             Branch.address,
             Branch.phone,
             fn.COUNT(Copy.id).alias("available_count"),
         )
         .join(Location, JOIN.LEFT_OUTER)
         .join(Copy, JOIN.LEFT_OUTER, on=(Copy.location == Location.id))
         .where((Copy.book == book_id) & (Copy.status == "available"))
         .group_by(Branch.id)
         .order_by(Branch.name.asc()))
    return list(q.dicts())


def create_reservation(reader: User, book_id: int, branch_id: int, pickup_date: date):
    today = date.today()
    if pickup_date < today or pickup_date > today + timedelta(days=3):
        return False, "Дату можно выбрать от сегодня до сегодня+3 дня.", None

    expire_old_reservations()

    with db.atomic():
        copy_q = (Copy
                  .select(Copy)
                  .join(Location)
                  .where(
                      (Copy.book == book_id) &
                      (Copy.status == "available") &
                      (Location.branch == branch_id)
                  )
                  .order_by(Copy.id.asc())
                  .for_update())

        copy_obj = copy_q.first()
        if not copy_obj:
            return False, "В этом филиале уже нет свободных экземпляров.", None

        copy_obj.status = "reserved"
        copy_obj.save()

        res = Reservation.create(
            reader=reader,
            copy=copy_obj,
            branch=branch_id,
            pickup_date=pickup_date,
            expires_at=_end_of_day(pickup_date),
            status="active",
            extended_once=False,
        )
        return True, f"Резерв создан до конца дня {pickup_date}.", res.id


def list_reservations_for_reader(reader: User):
    expire_old_reservations()

    q = (Reservation
         .select(
             Reservation.id,
             Reservation.status,
             Reservation.pickup_date,
             Reservation.expires_at,
             Reservation.extended_once,
             Book.title.alias("book_title"),
             Copy.inventory_code.alias("inv"),
             Branch.name.alias("branch_name"),
             Branch.address.alias("branch_address"),
         )
         .join(Copy)
         .join(Book)
         .switch(Reservation)
         .join(Branch)
         .where(Reservation.reader == reader)
         .order_by(Reservation.created_at.desc()))
    return list(q.dicts())


def list_reservations_for_librarian():
    expire_old_reservations()

    q = (Reservation
         .select(
             Reservation.id,
             Reservation.status,
             Reservation.pickup_date,
             Reservation.expires_at,
             Reservation.extended_once,
             Book.title.alias("book_title"),
             Copy.inventory_code.alias("inv"),
             Branch.name.alias("branch_name"),
             Branch.address.alias("branch_address"),
             User.full_name.alias("reader_name"),
             User.phone.alias("reader_phone"),
             User.login.alias("reader_login"),
         )
         .join(Copy)
         .join(Book)
         .switch(Reservation)
         .join(Branch)
         .switch(Reservation)
         .join(User, on=(Reservation.reader == User.id))
         .order_by(Reservation.created_at.desc()))
    return list(q.dicts())


def cancel_reservation(reader: User, reservation_id: int):
    expire_old_reservations()

    with db.atomic():
        res = Reservation.get_or_none(Reservation.id == reservation_id)
        if not res:
            return False, "Резерв не найден."
        if res.reader_id != reader.id:
            return False, "Это не ваш резерв."
        if res.status != "active":
            return False, "Резерв уже не активен."

        res.status = "cancelled"
        res.save()

        Copy.update(status="available").where((Copy.id == res.copy_id) & (Copy.status == "reserved")).execute()
        return True, "Резерв отменён."


def extend_reservation(reader: User, reservation_id: int):
    expire_old_reservations()

    with db.atomic():
        res = Reservation.get_or_none(Reservation.id == reservation_id)
        if not res:
            return False, "Резерв не найден."
        if res.reader_id != reader.id:
            return False, "Это не ваш резерв."
        if res.status != "active":
            return False, "Резерв уже не активен."
        if res.extended_once:
            return False, "Продлить можно только один раз."

        new_pick = res.pickup_date + timedelta(days=1)
        res.pickup_date = new_pick
        res.expires_at = _end_of_day(new_pick)
        res.extended_once = True
        res.save()
        return True, f"Продлено до {new_pick}."


def fulfill_reservation(librarian: User, reservation_id: int, loan_days: int = 14):
    expire_old_reservations()

    with db.atomic():
        res = (Reservation
               .select(Reservation, Copy)
               .join(Copy)
               .where(Reservation.id == reservation_id)
               .for_update()
               .first())

        if not res:
            return False, "Резерв не найден."
        if res.status != "active":
            return False, "Резерв не активен."

        copy_obj = res.copy
        if copy_obj.status != "reserved":
            return False, "Экземпляр не зарезервирован."

        exists_open = (Loan
                       .select()
                       .where((Loan.copy == copy_obj.id) & (Loan.status.in_(ACTIVE_LOAN_STATUSES)))
                       .exists())
        if exists_open:
            return False, "На этот экземпляр уже есть активная выдача."

        start = date.today()
        due = start + timedelta(days=loan_days)

        Loan.create(
            copy=copy_obj,
            reader=res.reader,
            librarian=librarian,
            status="open",
            start_date=start,
            due_date=due,
            return_date=None,
        )

        res.status = "fulfilled"
        res.save()

        copy_obj.status = "loaned"
        copy_obj.save()

        return True, f"Выдано до {due}."
