"""Shared test setup: the test database, a database session and test clients."""
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.db import get_db
from app.main import app

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "database" / "alembic.ini"


def get_test_database_url() -> str:
    if settings.test_database_url is None:
        pytest.skip("TEST_DATABASE_URL is not set in .env")
    return settings.test_database_url


def alembic_config() -> Config:
    """Alembic set up for the test database instead of the development one."""
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", get_test_database_url())
    return config


@pytest.fixture(scope="session")
def migrated_test_database() -> str:
    """Bring the test database to the newest migration, once per test run."""
    command.upgrade(alembic_config(), "head")
    return get_test_database_url()


@pytest.fixture
def db(migrated_test_database) -> Iterator[Session]:
    """A session whose changes are all undone after the test.

    Everything a test writes happens inside one transaction that is rolled back
    at the end, so every test starts with an empty database.
    """
    engine = create_engine(migrated_test_database)
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    transaction.rollback()
    connection.close()
    engine.dispose()


def client_with_database(database_url: str) -> TestClient:
    """A test client whose requests use the given database instead of the real one."""
    session_factory = sessionmaker(bind=create_engine(database_url))

    def get_test_db() -> Iterator[Session]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = get_test_db
    return TestClient(app)


@pytest.fixture
def client() -> Iterator[TestClient]:
    yield client_with_database(get_test_database_url())
    app.dependency_overrides.clear()


@pytest.fixture
def client_without_database() -> Iterator[TestClient]:
    # Nothing listens on port 1, so every connection attempt fails at once.
    yield client_with_database("postgresql+pg8000://nobody:wrong@localhost:1/none")
    app.dependency_overrides.clear()
