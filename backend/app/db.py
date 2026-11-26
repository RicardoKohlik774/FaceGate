"""Database connection.

The engine holds a small pool of open connections to PostgreSQL. Every HTTP
request gets its own session (one "conversation" with the database) and closes
it at the end, even when the request fails.
"""
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

# pool_pre_ping: test a pooled connection before using it, so a database
# restart does not break the next request.
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


def get_db() -> Iterator[Session]:
    """Give one request a session and always close it afterwards."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
