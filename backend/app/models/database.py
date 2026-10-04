from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from ..config import settings

# SQLite with WAL mode for better concurrency
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=settings.DEBUG
)

# Enable WAL mode
from sqlalchemy import event

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency for getting database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)

    # One-off cleanup for the removal of the SPLIT/MERGE task types (kernel v2.9.2 dropped
    # the split/merge commands they wrapped). SQLAlchemy's Enum stores member NAMES, so any
    # legacy rows hold 'SPLIT'/'MERGE'; left in place they raise LookupError on the next
    # Task load. Delete their files first to avoid orphans, then the tasks themselves.
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "DELETE FROM files WHERE task_id IN (SELECT id FROM tasks WHERE type IN ('SPLIT','MERGE'))"
        )
        conn.exec_driver_sql("DELETE FROM tasks WHERE type IN ('SPLIT','MERGE')")
