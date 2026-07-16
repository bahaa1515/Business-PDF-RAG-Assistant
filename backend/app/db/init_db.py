"""
Database initialization script.
Run this to set up the PostgreSQL database.
"""
from app.db.database import init_db

if __name__ == "__main__":
    print("Initializing database...")
    init_db()
    print("Database initialized successfully!")
