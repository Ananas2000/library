def migrate(migrator, database, **kwargs):
    migrator.sql("""
    ALTER TABLE copies
    DROP CONSTRAINT IF EXISTS copies_status_check;
    """)

    migrator.sql("""
    ALTER TABLE copies
    ADD CONSTRAINT copies_status_check
    CHECK (status IN ('available','loaned','reserved','lost','damaged'));
    """)

    migrator.sql("""
    CREATE TABLE IF NOT EXISTS reservations (
        id            BIGSERIAL PRIMARY KEY,
        reader_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        copy_id       BIGINT NOT NULL REFERENCES copies(id) ON DELETE RESTRICT,
        branch_id     BIGINT NOT NULL REFERENCES branches(id) ON DELETE RESTRICT,

        pickup_date   DATE NOT NULL,
        created_at    TIMESTAMP NOT NULL DEFAULT now(),
        expires_at    TIMESTAMP NOT NULL,

        status        TEXT NOT NULL DEFAULT 'active',
        extended_once BOOLEAN NOT NULL DEFAULT FALSE,

        CONSTRAINT chk_reservation_status
          CHECK (status IN ('active','fulfilled','expired','cancelled'))
    );
    """)

    migrator.sql("""
    CREATE UNIQUE INDEX IF NOT EXISTS uq_reservation_active_copy
    ON reservations(copy_id)
    WHERE status = 'active';
    """)


def rollback(migrator, database, **kwargs):
    migrator.sql("DROP INDEX IF EXISTS uq_reservation_active_copy;")
    migrator.sql("DROP TABLE IF EXISTS reservations;")

    migrator.sql("""
    ALTER TABLE copies
    DROP CONSTRAINT IF EXISTS copies_status_check;
    """)

    migrator.sql("""
    ALTER TABLE copies
    ADD CONSTRAINT copies_status_check
    CHECK (status IN ('available','loaned','lost','damaged'));
    """)
