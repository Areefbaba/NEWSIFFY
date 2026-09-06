"""Create the local SQLite schema."""

from app.database.connection import create_tables


if __name__ == "__main__":
    create_tables()
    print("Database initialized.")
