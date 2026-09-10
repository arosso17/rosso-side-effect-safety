"""MCP v2 server for the idempotent fake refund operation."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.server import MCPServer

from demo.refund.faults import (
    DEFAULT_FAULT_STATE,
    FAULT_NONE,
    disconnect_after_commit_if_armed,
)
from demo.refund.store import DEFAULT_DB_PATH, RefundStore

mcp = MCPServer("Rosso Idempotent Refund Demo")


def _store() -> RefundStore:
    return RefundStore(Path(os.environ.get("ROSSO_REFUND_DB", DEFAULT_DB_PATH)))


def _fault_state_path() -> Path:
    return Path(os.environ.get("ROSSO_REFUND_FAULT_STATE", DEFAULT_FAULT_STATE))


@mcp.tool()
def get_order(order_id: str) -> dict[str, Any]:
    """Read the authoritative state of a fake order and its refund effects."""
    state = _store().observe_order(order_id)
    return {
        "order_id": state["order_id"],
        "total": state["total_cents"] // 100,
        "refunded": state["refunded_cents"] // 100,
        "refund_count": state["refund_count"],
    }


@mcp.tool()
def refund_order(
    order_id: str, amount: int, operation_id: str
) -> dict[str, Any]:
    """Refund once per stable business operation ID, returning cached receipts."""
    if isinstance(amount, bool) or not isinstance(amount, int):
        raise TypeError("amount must be a whole-dollar integer")
    receipt = _store().refund_order_idempotently(
        order_id,
        amount * 100,
        operation_id=operation_id,
    )
    disconnect_after_commit_if_armed(
        receipt,
        fault=os.environ.get("ROSSO_REFUND_FAULT", FAULT_NONE),
        state_path=_fault_state_path(),
    )
    return {
        "refund_id": receipt["refund_id"],
        "order_id": receipt["order_id"],
        "amount": amount,
        "committed": receipt["committed"],
        "operation_id": receipt["operation_id"],
        "reused": receipt["reused"],
    }


if __name__ == "__main__":
    mcp.run()
