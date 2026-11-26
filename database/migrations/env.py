"""Alembic runs this file for every command (upgrade, downgrade, revision).

It tells Alembic which database to use and what the tables should look like.
"""
from alembic import context
from sqlalchemy import create_engine

from app.config import settings
from app.models import Base

# What the tables should look like; used by "alembic revision --autogenerate".
target_metadata = Base.metadata


def database_url() -> str:
    """The development database from .env, unless a caller set another one.

    The tests set sqlalchemy.url to the test database.
    """
    return context.config.get_main_option("sqlalchemy.url") or settings.database_url


def run_migrations() -> None:
    engine = create_engine(database_url())
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Also notice changed column types, not only new or removed columns.
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


run_migrations()
