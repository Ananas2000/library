from peewee_migrate import Migrator


def migrate(migrator: Migrator, database, fake=False, **kwargs):
    # ФИО: "Фамилия Имя" или "Фамилия Имя Отчество" (только русские буквы)
    migrator.sql(
        """
        DO $$
        BEGIN
            ALTER TABLE users
            ADD CONSTRAINT ck_users_full_name_ru
            CHECK (full_name ~ '^[А-Яа-яЁё]+ [А-Яа-яЁё]+( [А-Яа-яЁё]+)?$');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    # Телефон: +7xxxxxxxxxx
    migrator.sql(
        """
        DO $$
        BEGIN
            ALTER TABLE users
            ADD CONSTRAINT ck_users_phone_ru
            CHECK (phone ~ '^[+]7[0-9]{10}$');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )


def rollback(migrator: Migrator, database, fake=False, **kwargs):
    migrator.sql("ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_phone_ru;")
    migrator.sql("ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_full_name_ru;")
