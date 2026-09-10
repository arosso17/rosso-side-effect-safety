"""Reset the fake store to a known initial state."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from demo.refund.store import DEFAULT_DB_PATH, RefundStore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="SQLite database path",
    )
    return parser.parse_args()


def main() -> None:
    state = RefundStore(parse_args().db).reset()
    print(json.dumps(state, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
