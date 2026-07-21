"""Create or update a single dashboard/widget user (agent / quality_manager / admin).

Unlike load_mock_data.py (bulk demo roster, all-or-nothing), this adds one real
person to the live DB from .env without touching anything else. Idempotent per
username: rerunning updates the existing user's role/name/password.

Usage (from backend/, venv active):
    python scripts/create_user.py --username sara --email sara@acme.co \
        --full-name "سارة أحمد" --role quality_manager
The password is read from the CREATE_USER_PASSWORD env var, or prompted for
(never echoed, never in shell history).
"""
import argparse
import getpass
import os
import sys

from app.data.auth import ROLE_LEVELS, hash_password
from app.data.db import SessionLocal
from app.data.models import User


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or update one user.")
    parser.add_argument("--username", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--full-name", required=True, help="Arabic display name")
    parser.add_argument("--role", required=True, choices=sorted(ROLE_LEVELS))
    parser.add_argument("--inactive", action="store_true", help="create the user disabled")
    args = parser.parse_args()

    password = os.environ.get("CREATE_USER_PASSWORD") or getpass.getpass("Password: ")
    if len(password) < 8:
        print("password must be at least 8 characters", file=sys.stderr)
        return 1

    with SessionLocal() as db:
        user = db.query(User).filter(User.username == args.username).one_or_none()
        verb = "updated" if user else "created"
        if user is None:
            user = User(username=args.username)
            db.add(user)
        user.email = args.email
        user.full_name = args.full_name
        user.role = args.role
        user.is_active = not args.inactive
        user.hashed_password = hash_password(password)
        db.commit()
        print(f"{verb} user {args.username!r} (role={args.role}, active={user.is_active})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
