#!/usr/bin/env python3
"""One-way data migration: SQLite -> PostgreSQL for DailyFX.

Prerequisites (target must already exist as an empty database):
    1. Create DB/user, e.g. /app/postgresql/scripts/create-db.sh dailyfx dailyfx
    2. Create schema on the empty PG database:
           DATABASE_URL='postgresql+psycopg://...' python -m alembic upgrade head
       (run from the backend/ directory)
    3. STOP the API/scheduler (writes during copy are lost):
           docker stop dailyfx-api   # or: docker compose stop api
    4. Run this script:
           .venv/bin/python scripts/migrate_sqlite_to_postgres.py \
               --sqlite-url 'sqlite:////opt/dailyFX/data/app.db' \
               --postgres-url 'postgresql+psycopg://dailyfx:SECRET@127.0.0.1:5432/dailyfx'
       (password也可 via PG_URL env var to avoid shell history)
    5. Verify counts, switch DATABASE_URL in /opt/dailyFX/.env, start API.

The script is idempotent-ish: it DELETES target table contents before
copying (child tables first) so re-runs start clean. Source is read-only.

Only INTEGER single-column PK tables get their PG sequences reset
via setval(pg_get_serial_sequence(...)).
"""

from __future__ import annotations

import argparse
import os
import sys

from sqlalchemy import create_engine, text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Copy all DailyFX data from SQLite to PostgreSQL.")
    parser.add_argument(
        "--sqlite-url",
        default=os.environ.get("SQLITE_URL", "sqlite:///./data/app.db"),
        help="Source SQLite URL (default: $SQLITE_URL or sqlite:///./data/app.db)",
    )
    parser.add_argument(
        "--postgres-url",
        default=os.environ.get("PG_URL") or os.environ.get("DATABASE_URL", ""),
        help="Target PostgreSQL URL (default: $PG_URL or $DATABASE_URL)",
    )
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--yes", action="store_true", help="Skip the confirmation prompt")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.postgres_url.startswith("postgresql"):
        print("ERROR: --postgres-url must be a postgresql:// URL", file=sys.stderr)
        return 2

    # Import here so --help works without app dependencies.
    import app.models  # noqa: F401
    from app.database import Base

    print(f"Source: {args.sqlite_url}")
    masked = args.postgres_url.split("@")[-1] if "@" in args.postgres_url else args.postgres_url
    print(f"Target: postgresql://***@{masked}")

    tables = [t for t in Base.metadata.sorted_tables]
    print(f"Tables to copy: {len(tables)}")

    if not args.yes:
        answer = input("Target tables will be EMPTIED first. Continue? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("Aborted.")
            return 1

    src = create_engine(args.sqlite_url)
    dst = create_engine(
        args.postgres_url,
        connect_args={"connect_timeout": 10},
        pool_pre_ping=True,
    )

    with src.connect() as sconn, dst.connect() as dconn:
        # 1. Empty target (reverse dependency order).
        print("Emptying target tables...")
        for table in reversed(tables):
            dconn.execute(table.delete())
        dconn.commit()

        # 2. Copy (dependency order).
        grand_total = 0
        for table in tables:
            rows = sconn.execute(table.select()).mappings().all()
            if not rows:
                print(f"  {table.name}: 0 rows (skip)")
                continue
            payload = [dict(r) for r in rows]
            for i in range(0, len(payload), args.batch_size):
                dconn.execute(table.insert(), payload[i : i + args.batch_size])
            dconn.commit()
            print(f"  {table.name}: {len(payload)} rows copied")
            grand_total += len(payload)

        # 3. Reset PG sequences for INTEGER single-column PKs.
        print("Resetting sequences...")
        for table in tables:
            pk_cols = [c for c in table.columns if c.primary_key]
            if len(pk_cols) != 1 or str(pk_cols[0].type) != "INTEGER":
                continue
            col = pk_cols[0].name
            # NOTE: table/col names come from our own metadata, not user input.
            seq_sql = text(
                f"SELECT setval(pg_get_serial_sequence('{table.name}', '{col}'), "
                f"COALESCE((SELECT MAX({col}) FROM {table.name}), 0) + 1, false)"
            )
            result = dconn.execute(seq_sql).scalar()
            dconn.commit()
            print(f"  {table.name}.{col}: next sequence value -> {result}")

        # 4. Verify counts.
        print("Verifying row counts...")
        mismatches = 0
        for table in tables:
            src_n = sconn.execute(text(f'SELECT COUNT(*) FROM "{table.name}"')).scalar()
            dst_n = dconn.execute(text(f'SELECT COUNT(*) FROM "{table.name}"')).scalar()
            status = "OK" if src_n == dst_n else "MISMATCH"
            if src_n != dst_n:
                mismatches += 1
            print(f"  {table.name}: sqlite={src_n} postgres={dst_n} [{status}]")

    print(f"Done. Total rows copied: {grand_total}. Mismatches: {mismatches}")
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
