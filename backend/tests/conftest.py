"""Shared test setup: a test client that uses the test database."""
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.db import get_db
from app.main import app


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
    if settings.test_database_url is None:
        pytest.skip("TEST_DATABASE_URL is not set in .env")
    yield client_with_database(settings.test_database_url)
    app.dependency_overrides.clear()


@pytest.fixture
def client_without_database() -> Iterator[TestClient]:
    # Nothing listens on port 1, so every connection attempt fails at once.
    yield client_with_database("postgresql+pg8000://nobody:wrong@localhost:1/none")
    app.dependency_overrides.clear()
