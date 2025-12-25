from peewee_migrate import Migrator
from app.models import (
    Role, User, UserRole,
    Publisher, Author, Genre, Book, BookAuthor, BookGenre,
    Branch, Location, Copy, Loan
)

def migrate(migrator: Migrator, database, fake=False, **kwargs):
    migrator.create_model(Role)
    migrator.create_model(User)
    migrator.create_model(UserRole)

    migrator.create_model(Publisher)
    migrator.create_model(Author)
    migrator.create_model(Genre)
    migrator.create_model(Book)
    migrator.create_model(BookAuthor)
    migrator.create_model(BookGenre)

    migrator.create_model(Branch)
    migrator.create_model(Location)
    migrator.create_model(Copy)
    migrator.create_model(Loan)

    migrator.sql("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_one_open_loan_per_copy
        ON loans(copy_id)
        WHERE status IN ('open','overdue');
    """)

def rollback(migrator: Migrator, database, fake=False, **kwargs):
    migrator.drop_model(Loan)
    migrator.drop_model(Copy)
    migrator.drop_model(Location)
    migrator.drop_model(Branch)

    migrator.drop_model(BookGenre)
    migrator.drop_model(BookAuthor)
    migrator.drop_model(Book)
    migrator.drop_model(Genre)
    migrator.drop_model(Author)
    migrator.drop_model(Publisher)

    migrator.drop_model(UserRole)
    migrator.drop_model(User)
    migrator.drop_model(Role)
