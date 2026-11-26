"""Tests for database/seed.py and the device key helpers."""
from datetime import UTC, datetime

from sqlalchemy import select

from app.models import Device, FaceEmbedding, Membership, MembershipPlan, User
from app.security import hash_device_key, new_device_key
from seed import delete_all_data, is_empty, seed

NOW = datetime(2026, 11, 26, 18, 0, tzinfo=UTC)


def has_valid_membership(db, user: User) -> bool:
    """PLAN.md: an active membership with valid_from <= now < valid_until."""
    return db.scalar(
        select(Membership).where(
            Membership.user_id == user.id,
            Membership.status == "active",
            Membership.valid_from <= NOW,
            Membership.valid_until > NOW,
        )
    ) is not None


def test_seed_creates_the_demo_data(db):
    assert is_empty(db)
    seed(db, NOW)

    assert len(db.scalars(select(MembershipPlan)).all()) == 3
    assert sorted(d.direction for d in db.scalars(select(Device))) == ["entry", "exit"]
    assert db.scalars(select(FaceEmbedding)).all() == []  # never face data
    users = {user.first_name: user for user in db.scalars(select(User))}
    assert has_valid_membership(db, users["Jan"])
    assert not has_valid_membership(db, users["Eva"])  # expired
    assert not has_valid_membership(db, users["Petr"])  # never bought one


def test_device_keys_are_stored_only_as_hashes(db):
    keys = seed(db, NOW)
    stored = {device.name: device.api_key_hash for device in db.scalars(select(Device))}
    for name, key in keys.items():
        assert stored[name] == hash_device_key(key)
        assert stored[name] != key


def test_reset_empties_every_table(db):
    seed(db, NOW)
    assert not is_empty(db)
    delete_all_data(db)
    assert is_empty(db)


def test_device_keys_are_random_and_long():
    first, second = new_device_key(), new_device_key()
    assert first != second
    assert len(first) >= 40


def test_device_key_hash_is_stable():
    assert hash_device_key("abc") == hash_device_key("abc")
    assert hash_device_key("abc") != hash_device_key("abd")
