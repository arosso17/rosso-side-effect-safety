"""Authoritative SQLite state for the unsafe and idempotent refund demos."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

DEMO_ORDER_ID = "1234"
DEMO_ORDER_TOTAL_CENTS = 50_000
DEFAULT_DB_PATH = Path(__file__).with_name("store.db")
SCHEMA_PATH = Path(__file__).with_name("schema.sql")


class IdempotencyConflictError(ValueError):
    """One operation ID was reused for different business arguments."""


class RefundStore:
    """Fake ecommerce state with explicit unsafe and idempotent operations."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    def reset(self) -> dict[str, Any]:
        """Replace demo business state with one unrefunded $500 order."""
        self.initialize()
        with self._connect() as connection:
            connection.execute("DELETE FROM idempotency_receipts")
            connection.execute("DELETE FROM refunds")
            connection.execute("DELETE FROM orders")
            connection.execute(
                "INSERT INTO orders (order_id, total_cents) VALUES (?, ?)",
                (DEMO_ORDER_ID, DEMO_ORDER_TOTAL_CENTS),
            )
        return self.observe_order(DEMO_ORDER_ID)

    def observe_order(self, order_id: str) -> dict[str, Any]:
        """Read authoritative order and refund effect state."""
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    orders.order_id,
                    orders.total_cents,
                    COUNT(refunds.refund_id) AS refund_count,
                    COALESCE(SUM(refunds.amount_cents), 0) AS refunded_cents
                FROM orders
                LEFT JOIN refunds ON refunds.order_id = orders.order_id
                WHERE orders.order_id = ?
                GROUP BY orders.order_id, orders.total_cents
                """,
                (order_id,),
            ).fetchone()

        if row is None:
            raise LookupError(f"order {order_id!r} does not exist")
        return dict(row)

    def list_refunds(self, order_id: str) -> list[dict[str, Any]]:
        """List the authoritative refund effects for an order."""
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT refund_id, order_id, amount_cents, operation_id, created_at
                FROM refunds
                WHERE order_id = ?
                ORDER BY created_at, refund_id
                """,
                (order_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def refund_order(
        self,
        order_id: str,
        amount_cents: int,
        *,
        operation_id: str | None = None,
    ) -> dict[str, Any]:
        """Commit one refund effect.

        This method is intentionally unsafe: repeating one intended operation
        inserts another refund even when `operation_id` is reused.
        """
        if isinstance(amount_cents, bool) or not isinstance(amount_cents, int):
            raise TypeError("amount_cents must be an integer")
        if amount_cents <= 0:
            raise ValueError("amount_cents must be positive")

        self.initialize()
        refund_id = f"refund_{uuid4().hex}"
        with self._connect() as connection:
            order = connection.execute(
                "SELECT order_id FROM orders WHERE order_id = ?", (order_id,)
            ).fetchone()
            if order is None:
                raise LookupError(f"order {order_id!r} does not exist")

            connection.execute(
                """
                INSERT INTO refunds (refund_id, order_id, amount_cents, operation_id)
                VALUES (?, ?, ?, ?)
                """,
                (refund_id, order_id, amount_cents, operation_id),
            )

        return {
            "refund_id": refund_id,
            "order_id": order_id,
            "amount_cents": amount_cents,
            "operation_id": operation_id,
            "committed": True,
            "reused": False,
        }

    def refund_order_idempotently(
        self,
        order_id: str,
        amount_cents: int,
        *,
        operation_id: str,
    ) -> dict[str, Any]:
        """Commit one refund or return its durable receipt on a retry."""
        if isinstance(amount_cents, bool) or not isinstance(amount_cents, int):
            raise TypeError("amount_cents must be an integer")
        if amount_cents <= 0:
            raise ValueError("amount_cents must be positive")
        if not isinstance(operation_id, str) or not operation_id.strip():
            raise ValueError("operation_id must be a non-empty string")

        self.initialize()
        with self._connect() as connection:
            # Serialize claim/check/commit across concurrent SQLite writers.
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """
                SELECT operation_id, order_id, amount_cents, refund_id
                FROM idempotency_receipts
                WHERE operation_id = ?
                """,
                (operation_id,),
            ).fetchone()
            if existing is not None:
                if (
                    existing["order_id"] != order_id
                    or existing["amount_cents"] != amount_cents
                ):
                    raise IdempotencyConflictError(
                        "operation_id was already used with different arguments"
                    )
                return {
                    "refund_id": existing["refund_id"],
                    "order_id": existing["order_id"],
                    "amount_cents": existing["amount_cents"],
                    "operation_id": existing["operation_id"],
                    "committed": True,
                    "reused": True,
                }

            order = connection.execute(
                "SELECT order_id FROM orders WHERE order_id = ?", (order_id,)
            ).fetchone()
            if order is None:
                raise LookupError(f"order {order_id!r} does not exist")

            refund_id = f"refund_{uuid4().hex}"
            connection.execute(
                """
                INSERT INTO refunds (refund_id, order_id, amount_cents, operation_id)
                VALUES (?, ?, ?, ?)
                """,
                (refund_id, order_id, amount_cents, operation_id),
            )
            connection.execute(
                """
                INSERT INTO idempotency_receipts (
                    operation_id, tool_name, order_id, amount_cents, refund_id
                ) VALUES (?, 'refund_order', ?, ?, ?)
                """,
                (operation_id, order_id, amount_cents, refund_id),
            )

        return {
            "refund_id": refund_id,
            "order_id": order_id,
            "amount_cents": amount_cents,
            "operation_id": operation_id,
            "committed": True,
            "reused": False,
        }

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()
