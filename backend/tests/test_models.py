"""The database itself refuses wrong data, even if the backend code had a bug.

Every test runs in a transaction that is rolled back afterwards (see the db
fixture in conftest.py), so the tests do not affect each other.

The tests look for the name of the broken rule in the error. The exception
type is not enough: the pg8000 driver reports a broken CHECK rule as
ProgrammingError and a duplicate value as IntegrityError. Both are a
DatabaseError.
"""
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DatabaseError

from app.models import (
    AccessEvent,
    Device,
    FaceEmbedding,
    Membership,
    MembershipPlan,
    User,
    Visit,
)

NOW = datetime(2026, 11, 26, 18, 0, tzinfo=UTC)


def add_user(db, email="jan.novak@example.com", **fields) -> User:
    user = User(first_name="Jan", last_name="Novák", email=email, **fields)
    db.add(user)
    db.flush()  # sends the INSERT now, so the database checks it now
    return user


def add_device(db, direction="entry") -> Device:
    device = Device(name=f"Door {direction}", direction=direction, api_key_hash=f"hash-{direction}")
    db.add(device)
    db.flush()
    return device


def add_plan(db) -> MembershipPlan:
    plan = MembershipPlan(name="Month", duration_days=30, price_czk=499)
    db.add(plan)
    db.flush()
    return plan


def test_new_user_gets_defaults_from_the_database(db):
    user = add_user(db)
    db.refresh(user)  # read back what the database filled in
    assert user.status == "pending"
    assert user.created_at is not None


def test_unknown_user_status_is_refused(db):
    with pytest.raises(DatabaseError, match="ck_users_status"):
        add_user(db, status="vip")


def test_two_users_cannot_share_an_email(db):
    add_user(db)
    with pytest.raises(DatabaseError, match="uq_users_email"):
        add_user(db)


def test_device_direction_must_be_entry_or_exit(db):
    with pytest.raises(DatabaseError, match="ck_devices_direction"):
        add_device(db, direction="sideways")


def test_plan_needs_a_positive_duration(db):
    db.add(MembershipPlan(name="Broken", duration_days=0, price_czk=100))
    with pytest.raises(DatabaseError, match="ck_membership_plans_duration_days_positive"):
        db.flush()


def test_membership_cannot_end_before_it_starts(db):
    user, plan = add_user(db), add_plan(db)
    db.add(Membership(user_id=user.id, plan_id=plan.id, status="active",
                      valid_from=NOW, valid_until=NOW - timedelta(days=1)))
    with pytest.raises(DatabaseError, match="ck_memberships_valid_until_after_valid_from"):
        db.flush()


def test_closed_visit_needs_a_close_reason(db):
    db.add(Visit(entered_at=NOW, exited_at=NOW + timedelta(hours=1)))
    with pytest.raises(DatabaseError, match="ck_visits_closed_with_reason"):
        db.flush()


def test_access_event_reason_must_be_known(db):
    device = add_device(db)
    db.add(AccessEvent(device_id=device.id, direction="entry", method="face",
                       result="denied", reason="bad_hair_day"))
    with pytest.raises(DatabaseError, match="ck_access_events_reason"):
        db.flush()


def test_deleting_a_user_removes_personal_data_but_keeps_statistics(db):
    """PLAN.md: personal rows are deleted, event and visit rows lose the link."""
    user, plan, device = add_user(db), add_plan(db), add_device(db)
    db.add_all([
        FaceEmbedding(user_id=user.id, embedding_encrypted=b"secret", model_name="sface_2021dec"),
        Membership(user_id=user.id, plan_id=plan.id),
        AccessEvent(device_id=device.id, direction="entry", user_id=user.id,
                    method="face", result="granted", reason="ok", similarity=0.75),
        Visit(user_id=user.id, entered_at=NOW),
    ])
    db.flush()

    db.delete(user)
    db.flush()
    db.expire_all()  # forget cached rows, read again from the database

    assert db.scalars(select(FaceEmbedding)).all() == []
    assert db.scalars(select(Membership)).all() == []
    event = db.scalars(select(AccessEvent)).one()
    visit = db.scalars(select(Visit)).one()
    assert event.user_id is None and event.result == "granted"
    assert visit.user_id is None and visit.entered_at == NOW
