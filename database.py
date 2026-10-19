import os
import sqlite3
from typing import Generator
from contextlib import contextmanager

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "products.db")

def get_db_path() -> str:
    """Return the active database path from environment or default."""
    return os.environ.get("DATABASE_PATH", DEFAULT_DB_PATH)

def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Create a new SQLite connection configured with Row factory and foreign keys."""
    target_path = db_path or get_db_path()
    conn = sqlite3.connect(target_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    # WAL mode improves concurrent read performance
    if target_path != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL;")
    return conn

@contextmanager
def get_db_context(db_path: str | None = None) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for database operations."""
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db(db_path: str | None = None) -> None:
    """Initialize products table and indexes."""
    with get_db_context(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                price REAL NOT NULL,
                stock INTEGER NOT NULL,
                rating REAL NOT NULL,
                createdAt TEXT NOT NULL
            );
        """)
        
        # Create indexes for commonly filtered and sorted columns
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_price ON products(price);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_stock ON products(stock);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_rating ON products(rating);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_created_at ON products(createdAt);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_category_price ON products(category, price);")
