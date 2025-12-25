import bcrypt


def hash_password(password: str) -> str:
    pw = password.encode("utf-8")

    # bcrypt ограничивает вход 72 байтами
    if len(pw) > 72:
        pw = pw[:72]

    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(pw, salt)
    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        pw = password.encode("utf-8")
        if len(pw) > 72:
            pw = pw[:72]
        return bcrypt.checkpw(pw, password_hash.encode("utf-8"))
    except Exception:
        return False
