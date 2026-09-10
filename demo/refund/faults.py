"""One-shot fault state for the refund demonstration."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

FAULT_NONE = "none"
FAULT_COMMIT_THEN_DISCONNECT = "commit_then_disconnect"
FAULTS = (FAULT_NONE, FAULT_COMMIT_THEN_DISCONNECT)
PRODUCT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FAULT_STATE = PRODUCT_ROOT / ".run" / "commit-then-disconnect.used"


def claim_fault_once(state_path: Path, evidence: dict[str, Any]) -> bool:
    """Atomically claim a one-shot fault, returning false if already consumed."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with state_path.open("x", encoding="utf-8") as state_file:
            json.dump(evidence, state_file, sort_keys=True)
            state_file.write("\n")
    except FileExistsError:
        return False
    return True


def reset_fault_state(state_path: Path = DEFAULT_FAULT_STATE) -> None:
    state_path.unlink(missing_ok=True)


def disconnect_after_commit_if_armed(
    receipt: dict[str, Any], *, fault: str, state_path: Path
) -> None:
    """Consume the one-shot fault and exit after a durable business commit."""
    if fault != FAULT_COMMIT_THEN_DISCONNECT:
        return
    if not claim_fault_once(
        state_path,
        {
            "fault": FAULT_COMMIT_THEN_DISCONNECT,
            "refund_id": receipt["refund_id"],
            "operation_id": receipt.get("operation_id"),
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
