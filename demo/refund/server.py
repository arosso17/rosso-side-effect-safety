"""MCP v2 server for the intentionally unsafe fake refund operation."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from mcp.server import MCPServer

from demo.refund.faults import (
    DEFAULT_FAULT_STATE,
    FAULT_COMMIT_THEN_DISCONNECT,
    claim_fault_once,
)
from demo.refund.store import DEFAULT_DB_PATH, RefundStore

mcp = MCPServer("Rosso Refund Demo")


def _store() -> RefundStore:
    return RefundStore(Path(os.environ.get("ROSSO_REFUND_DB", DEFAULT_DB_PATH)))


def _fault_state_path() -> Path:
    return Path(os.environ.get("ROSSO_REFUND_FAULT_STATE", DEFAULT_FAULT_STATE))


def _disconnect_after_commit_if_armed(receipt: dict[str, Any]) -> None:
    if os.environ.get("ROSSO_REFUND_FAULT") != FAULT_COMMIT_THEN_DISCONNECT:
        return
    if not claim_fault_once(
        _fault_state_path(),
        {
            "fault": FAULT_COMMIT_THEN_DISCONNECT,
            "refund_id": receipt["refund_id"],
            "committed": receipt["committed"],
        },
    ):
        return

    print(
        "ROSSO FAULT: refund committed; terminating MCP server before response",
        file=sys.stderr,
        flush=True,
    )
    os._exit(86)


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
def refund_order(order_id: str, amount: int) -> dict[str, Any]:
    """Refund a positive whole-dollar amount to a fake order.

    This first server is intentionally non-idempotent. Repeating the call creates
    another committed refund effect.
    """
    if isinstance(amount, bool) or not isinstance(amount, int):
        raise TypeError("amount must be a whole-dollar integer")
    receipt = _store().refund_order(order_id, amount * 100)
    _disconnect_after_commit_if_armed(receipt)
    return {
        "refund_id": receipt["refund_id"],
        "order_id": receipt["order_id"],
        "amount": amount,
        "committed": receipt["committed"],
    }


if __name__ == "__main__":
    mcp.run()
