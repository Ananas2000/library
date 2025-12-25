from __future__ import annotations

from datetime import datetime
from peewee import *
from playhouse.postgres_ext import BinaryJSONField

from app.db import db


class BaseModel(Model):
    class Meta:
        database = db


class Role(BaseModel):
    name = TextField(unique=True)
    rights = BinaryJSONField(default={})

    class Meta:
        table_name = "roles"


class User(BaseModel):
    full_name = TextField()
    phone = TextField(null=True)
    login = TextField(unique=True)
    password_hash = TextField()
    is_active = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "users"


class UserRole(BaseModel):
    user = ForeignKeyField(User, backref="user_roles", column_name="user_id", on_delete="CASCADE")
    role = ForeignKeyField(Role, backref="role_users", column_name="role_id", on_delete="RESTRICT")

    class Meta:
        table_name = "user_roles"
        primary_key = CompositeKey("user", "role")


class Publisher(BaseModel):
    name = TextField(unique=True)
    city = TextField(null=True)
    country = TextField(null=True)

    class Meta:
        table_name = "publishers"


class Author(BaseModel):
    full_name = TextField()
    birth_year = IntegerField(null=True)
    death_year = IntegerField(null=True)

    class Meta:
        table_name = "authors"


class Genre(BaseModel):
    name = TextField(unique=True)

    class Meta:
        table_name = "genres"


class Book(BaseModel):
    title = TextField()
    language = TextField(default="ru")
    publish_year = IntegerField(null=True)
    pages_count = IntegerField(null=True)
    publisher = ForeignKeyField(Publisher, backref="books", column_name="publisher_id", null=True, on_delete="SET NULL")

    class Meta:
        table_name = "books"


class BookAuthor(BaseModel):
    book = ForeignKeyField(Book, backref="book_authors", column_name="book_id", on_delete="CASCADE")
    author = ForeignKeyField(Author, backref="author_books", column_name="author_id", on_delete="RESTRICT")

    class Meta:
        table_name = "book_authors"
        primary_key = CompositeKey("book", "author")


class BookGenre(BaseModel):
    book = ForeignKeyField(Book, backref="book_genres", column_name="book_id", on_delete="CASCADE")
    genre = ForeignKeyField(Genre, backref="genre_books", column_name="genre_id", on_delete="RESTRICT")

    class Meta:
        table_name = "book_genres"
        primary_key = CompositeKey("book", "genre")


class Branch(BaseModel):
    name = TextField(unique=True)
    address = TextField(null=True)
    phone = TextField(null=True)

    class Meta:
        table_name = "branches"


class Location(BaseModel):
    branch = ForeignKeyField(Branch, backref="locations", column_name="branch_id", on_delete="CASCADE")
    code = TextField()
    description = TextField(null=True)

    class Meta:
        table_name = "locations"
        indexes = (
            (("branch", "code"), True),
        )


class Copy(BaseModel):
    inventory_code = TextField(unique=True)
    status = TextField(default="available")
    price = FloatField(null=True)
    condition_note = TextField(null=True)

    book = ForeignKeyField(Book, backref="copies", column_name="book_id", on_delete="CASCADE")
    location = ForeignKeyField(Location, backref="copies", column_name="location_id", null=True, on_delete="SET NULL")

    class Meta:
        table_name = "copies"


class Loan(BaseModel):
    status = TextField(default="open")
    start_date = DateField()
    due_date = DateField()
    return_date = DateField(null=True)

    copy = ForeignKeyField(Copy, backref="loans", column_name="copy_id", on_delete="RESTRICT")
    reader = ForeignKeyField(User, backref="loans_reader", column_name="reader_id", on_delete="RESTRICT")
    librarian = ForeignKeyField(User, backref="loans_librarian", column_name="librarian_id", on_delete="RESTRICT")

    class Meta:
        table_name = "loans"


class Reservation(BaseModel):
    status = TextField(default="active")
    pickup_date = DateField()
    created_at = DateTimeField(default=datetime.now)
    expires_at = DateTimeField()
    extended_once = BooleanField(default=False)

    reader = ForeignKeyField(User, backref="reservations", column_name="reader_id", on_delete="RESTRICT")
    copy = ForeignKeyField(Copy, backref="reservations", column_name="copy_id", on_delete="RESTRICT")
    branch = ForeignKeyField(Branch, backref="reservations", column_name="branch_id", on_delete="RESTRICT")

    class Meta:
        table_name = "reservations"
