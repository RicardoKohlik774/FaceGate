"""Fill the development database with demo data.

Run from the database/ folder, after "python -m alembic upgrade head":

    python seed.py            # only into an empty database
    python seed.py --reset    # first delete ALL data in the development database

What it creates:
- three membership plans;
- two devices (door cameras): entry and exit. Their secret keys are printed
  once; the database stores only their hashes. The door program needs them
  from step 4 on. If a key is lost, run with --reset to get new ones;
- three demo users: one with a valid membership, one with an expired one, one
  without. No face data: faces are added by enrolling, never by this script.

It always uses DATABASE_URL from .env, never the test database.
"""
import argparse
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Lets this script import the backend's settings and tables.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import create_engine, func, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.config import settings  # noqa: E402
from app.models import Base, Device, Membership, MembershipPlan, User  # noqa: E402
from app.security import hash_device_key, new_device_key  # noqa: E402

PLANS = [
    # name, days, price in crowns
    ("Day pass", 1, 150),
    ("Month", 30, 899),
    ("Year", 365, 7990),
]

DEVICES = [
    # name, direction
    ("Front door - outside", "entry"),
    ("Front door - inside", "exit"),
]


def seed(session: Session, now: datetime) -> dict[str, str]:
    """Add the demo rows. Returns the new device keys by device name."""
    plans = [MembershipPlan(name=name, duration_days=days, price_czk=price)
             for name, days, price in PLANS]
    session.add_all(plans)

    device_keys = {}
    for name, direction in DEVICES:
        key = new_device_key()
        session.add(Device(name=name, direction=direction, api_key_hash=hash_device_key(key)))
        device_keys[name] = key

    valid = User(first_name="Jan", last_name="Novák", email="jan.novak@example.com", status="active")
    expired = User(first_name="Eva", last_name="Svobodová", email="eva.svobodova@example.com", status="active")
    without = User(first_name="Petr", last_name="Dvořák", email="petr.dvorak@example.com", status="active")
    session.add_all([valid, expired, without])
    session.flush()  # gives the new rows their ids

    month = plans[1]
    session.add_all([
        # Bought 10 days ago, valid for 20 more days.
        Membership(user_id=valid.id, plan_id=month.id, status="active",
                   valid_from=now - timedelta(days=10), valid_until=now + timedelta(days=20)),
        # Bought 40 days ago, ran out 10 days ago.
        Membership(user_id=expired.id, plan_id=month.id, status="active",
                   valid_from=now - timedelta(days=40), valid_until=now - timedelta(days=10)),
    ])
    session.flush()
    return device_keys


def is_empty(session: Session) -> bool:
    return all(session.scalar(select(func.count()).select_from(table)) == 0
               for table in Base.metadata.sorted_tables)


def delete_all_data(session: Session) -> None:
    """Empty every table and restart the ids at 1. The tables themselves stay."""
    names = ", ".join(table.name for table in Base.metadata.sorted_tables)
    session.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Fill the development database with demo data.")
    parser.add_argument("--reset", action="store_true",
                        help="first delete ALL data in the development database")
    args = parser.parse_args()

    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        if args.reset:
            delete_all_data(session)
        elif not is_empty(session):
            print("The database already has data, nothing was changed.")
            print("Run 'python seed.py --reset' to delete ALL data and seed again.")
            return 1

        device_keys = seed(session, datetime.now(UTC))
        session.commit()

    print("Demo data added: 3 plans, 2 devices, 3 users "
          "(Jan Novák: valid membership, Eva Svobodová: expired, Petr Dvořák: none).")
    print()
    print("Device keys - shown only now, the database keeps only their hashes.")
    print("Keep them for the door program (step 4); never commit them.")
    for name, key in device_keys.items():
        print(f"    {name}: {key}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
