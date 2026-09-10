import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from mcp import Client

from demo.refund.agent import DEFAULT_MODEL, run_agent
from demo.refund.server import mcp
from demo.refund.store import DEMO_ORDER_ID, RefundStore


class FakeResponses:
    def __init__(self, responses: list[Any]) -> None:
        self._responses = iter(responses)
        self.requests: list[dict[str, Any]] = []

    async def create(self, **request: Any) -> Any:
        self.requests.append(request)
        return next(self._responses)


class FakeOpenAI:
    def __init__(self, responses: list[Any]) -> None:
        self.responses = FakeResponses(responses)


def test_default_model_is_cost_sensitive_openai_model() -> None:
    assert DEFAULT_MODEL == "gpt-5.6-luna"


def function_call(call_id: str, name: str, arguments: dict[str, Any]) -> Any:
    return SimpleNamespace(
        type="function_call",
        call_id=call_id,
        name=name,
        arguments=json.dumps(arguments),
    )


def model_response(response_id: str, output: list[Any], text: str = "") -> Any:
    return SimpleNamespace(id=response_id, output=output, output_text=text)


def test_openai_agent_uses_mcp_to_process_one_refund(
    tmp_path: Path, monkeypatch: Any
) -> None:
    db_path = tmp_path / "store.db"
    trace_path = tmp_path / "trace.jsonl"
    store = RefundStore(db_path)
    store.reset()
    monkeypatch.setenv("ROSSO_REFUND_DB", str(db_path))

    fake_openai = FakeOpenAI(
        [
            model_response(
                "turn_1",
                [function_call("call_1", "get_order", {"order_id": "1234"})],
            ),
            model_response(
                "turn_2",
                [
                    function_call(
                        "call_2",
                        "refund_order",
                        {"order_id": "1234", "amount": 200},
                    )
                ],
            ),
            model_response("turn_3", [], "The $200 refund was processed."),
        ]
    )

    async def run() -> None:
        async with Client(mcp) as mcp_client:
            result = await run_agent(
                fake_openai,
                mcp_client,
                model="test-model",
                trace_path=trace_path,
            )
            assert result.final_text == "The $200 refund was processed."

    asyncio.run(run())

    state = store.observe_order(DEMO_ORDER_ID)
    assert state["refund_count"] == 1
    assert state["refunded_cents"] == 20_000
    assert len(fake_openai.responses.requests) == 3

    events = [json.loads(line) for line in trace_path.read_text().splitlines()]
    attempts = [event for event in events if event["event"] == "tool_attempt_started"]
    model_turns = [event for event in events if event["event"] == "model_turn"]
    assert [attempt["tool"] for attempt in attempts] == [
        "get_order",
        "refund_order",
    ]
    assert all(turn["usage"] is None for turn in model_turns)
    assert events[-1]["event"] == "run_completed"
