#!/usr/bin/env python3
"""Run Real-Flight Replay Validation Plan pre-check (Section 0).

Validates replay sample order: oldest-first, monotonic timestamps.
Use before manual UX validation (event timing, phase links, etc.).

Usage:
  python scripts/validate_replay.py <session_id> [session_id ...]
  python scripts/validate_replay.py --all

Requires SQLITE_DB_PATH or default DB. Uses PersistenceService directly.
"""

import argparse
import os
import sys

# Add src to path for standalone run
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from airautomatica.config import get_sqlite_db_path
from airautomatica.db.base import get_engine, init_db
from airautomatica.services.persistence import PersistenceService
from airautomatica.validation.replay_precheck import validate_replay_sample_order


def _print_checklist() -> None:
    """Print Real-Flight Replay Validation Plan checklist."""
    print("Real-Flight Replay Validation Checklist")
    print("=" * 50)
    print()
    print("0. Replay sample order (pre-check) - RUN THIS SCRIPT")
    print("   Samples oldest-first, timestamps monotonic")
    print("   python scripts/validate_replay.py <session_id> [--all]")
    print()
    print("1. Event timing")
    print(
        "   Markers align with event times; scrub to event shows plausible map position"
    )
    print()
    print("2. Dominant phase link")
    print("   Click lands in correct phase; Phase metric and highlight match")
    print()
    print("3. Replay metrics")
    print("   V, Alt, Spd match trends and path at scrub position")
    print()
    print("4. Home/distance (ArduPilot)")
    print("   Peak distance in debrief is plausible")
    print()
    print("5. Home/distance (INAV)")
    print("   Peak distance in debrief is plausible")
    print()
    print("6. Prev event")
    print("   Disabled at start; seeks backward correctly")
    print()
    print("7. Next event")
    print("   Disabled at end; seeks forward correctly")
    print()
    print("When something is off: session ID, scrub time, event/phase name,")
    print("expected vs actual, screenshot if possible.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Replay sample order pre-check (Real-Flight Replay Validation Plan Section 0)"
    )
    parser.add_argument(
        "session_ids",
        nargs="*",
        type=int,
        help="Session ID(s) to validate",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Validate all sessions in DB (requires list endpoint or DB query)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Max samples to fetch per session (default: 5000)",
    )
    parser.add_argument(
        "--checklist",
        action="store_true",
        help="Print full validation checklist (Section 0 + manual steps 1-5) and exit",
    )
    args = parser.parse_args()

    if args.checklist:
        _print_checklist()
        return 0

    db_path = get_sqlite_db_path()
    if not db_path:
        print(
            "Error: SQLite DB path not set. Set SQLITE_DB_PATH.",
            file=sys.stderr,
        )
        return 1

    init_db(db_path)
    if get_engine() is None:
        print("Error: Could not initialize DB.", file=sys.stderr)
        return 1

    persistence = PersistenceService()

    session_ids: list[int] = []
    if args.all:
        # Get recent session IDs from DB
        from sqlalchemy import select

        from airautomatica.db.models import FlightSession
        from airautomatica.db.session import get_session

        with get_session() as db_session:
            if db_session:
                stmt = (
                    select(FlightSession.id).order_by(FlightSession.id.desc()).limit(50)
                )
                session_ids = list(db_session.execute(stmt).scalars().all())
    else:
        session_ids = args.session_ids

    if not session_ids:
        parser.print_help()
        print("\nProvide session IDs or use --all", file=sys.stderr)
        return 1

    any_failed = False
    for sid in session_ids:
        result = validate_replay_sample_order(sid, persistence, limit=args.limit)
        status = "PASS" if result.passed else "FAIL"
        print(f"Session {sid}: {status} (n={result.sample_count})")
        if result.first_timestamp:
            print(f"  first: {result.first_timestamp}")
        if result.last_timestamp:
            print(f"  last:  {result.last_timestamp}")
        if not result.passed:
            print(f"  {result.message}")
            any_failed = True

    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())
