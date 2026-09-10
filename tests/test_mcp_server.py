import asyncio
from pathlib import Path

from mcp import Client

from demo.refund.server import mcp
from demo.refund.store import DEMO_ORDER_ID, RefundStore


def test_mcp_tools_read_and_commit_authoritative_state(
    tmp_path: Path, monkeypatch
) -> None:
    db_path = tmp_path / "store.db"
    store = RefundStore(db_path)
    store.reset()
    monkeypatch.setenv("ROSSO_REFUND_DB", str(db_path))

    async def exercise_server() -> None:
        async with Client(mcp) as client:
            initial = await client.call_tool(
                "get_order", {"order_id": DEMO_ORDER_ID}
            )
            refund = await client.call_tool(
                "refund_order",
                {
                    "order_id": DEMO_ORDER_ID,
                    "amount": 200,
                    "operation_id": "refund:order_1234:test_mcp_server",
                },
            )
            assert initial.is_error is False
            assert refund.is_error is False

    asyncio.run(exercise_server())

    assert store.observe_order(DEMO_ORDER_ID)["refund_count"] == 1
    assert store.observe_order(DEMO_ORDER_ID)["refunded_cents"] == 20_000
