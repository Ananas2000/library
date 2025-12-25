from pathlib import Path

from peewee_migrate import Router
from app.db import db


class Utf8Router(Router):
    def read(self, name):
        migrate_dir = self.migrate_dir
        if not isinstance(migrate_dir, (str, Path)):
            migrate_dir = str(migrate_dir)

        mdir = Path(migrate_dir)
        path = mdir / f"{name}.py"

        code = path.read_text(encoding="utf-8")
        scope = {}
        exec(compile(code, str(path), "exec"), scope)

        migrate = scope.get("migrate")
        rollback = scope.get("rollback")
        return migrate, rollback


def run():
    db.connect(reuse_if_open=True)
    try:
        router = Utf8Router(db, migrate_dir="migrations")
        router.run()
    finally:
        if not db.is_closed():
            db.close()


if __name__ == "__main__":
    run()
