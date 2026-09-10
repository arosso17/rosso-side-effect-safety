import asyncio
from pathlib import Path
from typing import Any

import pytest

from demo.refund.faults import FAULT_COMMIT_THEN_DISCONNECT
from demo.refund.mcp_client import RefundMCPClient, ResponseLostError
from demo.refund.store import DEMO_ORDER_ID, RefundStore


def test_commit_then_disconnect_commits_before_losing_first_response(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "store.db"
    fault_state = tmp_path / "fault.used"
    store = RefundStore(db_path)
    store.reset()
    client = RefundMCPClient(
        db_path=db_path,
        fault=FAULT_COMMIT_THEN_DISCONNECT,
        fault_state_path=fault_state,
    )

    async def call_refund() -> Any:
        return await client.call_tool(
            "refund_order", {"order_id": DEMO_ORDER_ID, "amount": 200}
        )

    with pytest.raises(ResponseLostError, match="outcome is unknown"):
        asyncio.run(call_refund())

    after_lost_response = store.observe_order(DEMO_ORDER_ID)
    assert after_lost_response["refund_count"] == 1
    assert after_lost_response["refunded_cents"] == 20_000
    assert fault_state.exists()

    retry_result = asyncio.run(call_refund())
    assert retry_result.is_error is False
    after_retry = store.observe_order(DEMO_ORDER_ID)
    assert after_retry["refund_count"] == 2
    assert after_retry["refunded_cents"] == 40_000
