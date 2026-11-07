"""Provision production accounts from a trusted operator shell."""
import argparse
import getpass
import os
import sys
import uuid
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.security.passwords import hash_password


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--role", required=True, choices=["admin", "analyst", "intern", "viewer"])
    args = parser.parse_args()
    database_url = os.environ.get("POSTGRES_URL")
    if not database_url:
        raise SystemExit("Set POSTGRES_URL in the operator environment first.")
    password = getpass.getpass("New password (12+ characters): ")
    if len(password) < 12:
        raise SystemExit("Password must be at least 12 characters.")
    if password != getpass.getpass("Confirm password: "):
        raise SystemExit("Passwords do not match.")

    with psycopg.connect(database_url) as conn:
        conn.execute(
            """INSERT INTO users (user_id, tenant_id, username, email, roles, password_hash)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (str(uuid.uuid4()), args.tenant_id, args.username, args.email,
             [args.role], hash_password(password)),
        )
    print(f"Provisioned user {args.username!r} with role {args.role!r} in tenant {args.tenant_id!r}.")


if __name__ == "__main__":
    main()
