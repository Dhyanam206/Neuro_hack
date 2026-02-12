"""
NEUROHACK — Database Layer

Handles SQLite initialization, session management, and table creation.
SQLite chosen for zero-setup reproducibility (ships in the zip, judges run instantly).
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session

from core.models import Base


class DatabaseManager:
    """
    Manages the SQLite database connection and sessions.
    
    Usage:
        db = DatabaseManager("neurohack_memory.db")
        with db.session() as session:
            session.add(memory)
            session.commit()
    """

    def __init__(self, db_path: str = "neurohack_memory.db", echo: bool = False):
        self.engine = create_engine(
            f"sqlite:///{db_path}",
            echo=echo,
            connect_args={"check_same_thread": False}  # SQLite thread safety
        )
        # Enable WAL mode for concurrent read/write
        @event.listens_for(self.engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        self._SessionFactory = sessionmaker(bind=self.engine)

    def create_tables(self):
        """Create all tables. Idempotent — safe to call multiple times."""
        Base.metadata.create_all(self.engine)

    def drop_tables(self):
        """Drop all tables. Used for testing and demo reset."""
        Base.metadata.drop_all(self.engine)

    def session(self) -> Session:
        """Get a new session. Use as context manager."""
        return self._SessionFactory()

    def reset(self):
        """Full reset: drop + recreate all tables."""
        self.drop_tables()
        self.create_tables()
