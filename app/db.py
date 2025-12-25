from peewee import PostgresqlDatabase

# === НАСТРОЙКИ БД: правь тут ===
DB_NAME = "library_db"
DB_USER = "postgres"
DB_PASSWORD = "1234"
DB_HOST = "localhost"
DB_PORT = 5432

db = PostgresqlDatabase(
    DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=DB_PORT,
    autorollback=True,
)
