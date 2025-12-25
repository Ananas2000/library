from app.db import db
from app.gui_login import LoginWindow
from app.gui_main import MainWindow


def run():
    db.connect(reuse_if_open=True)
    try:
        while True:
            box = {"session": None}

            def on_success(session):
                box["session"] = session

            login = LoginWindow(on_success=on_success)
            login.mainloop()

            session = box.get("session")
            if session is None:
                break

            app = MainWindow(session)
            app.mainloop()

            if not getattr(app, "logged_out", False):
                break
    finally:
        if not db.is_closed():
            db.close()


if __name__ == "__main__":
    run()
