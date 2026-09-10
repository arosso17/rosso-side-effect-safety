"""Print authoritative state for the fake demo order."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from demo.refund.store import DEFAULT_DB_PATH, DEMO_ORDER_ID, RefundStore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--order-id", default=DEMO_ORDER_ID)
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="SQLite database path",
    )
    parser.add_argument(
        "--details",
        action="store_true",
        help="Include each authoritative refund row",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    store = RefundStore(args.db)
    state = store.observe_order(args.order_id)
    if args.details:
        state["refunds"] = store.list_refunds(args.order_id)
    print(json.dumps(state, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
