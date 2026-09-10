import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from mcp import Client

from demo.refund.agent import (
    BASE_INSTRUCTIONS,
    CONTROLLED_RETRY_INSTRUCTION,
    DEFAULT_MODEL,
    RETRY_POLICY_CONTROLLED,
    RETRY_POLICY_NEUTRAL,
    instructions_for_retry_policy,
    run_agent,
)
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


def test_neutral_retry_policy_removes_only_retry_advice() -> None:
    controlled = instructions_for_retry_policy(RETRY_POLICY_CONTROLLED)
    neutral = instructions_for_retry_policy(RETRY_POLICY_NEUTRAL)

    assert controlled == BASE_INSTRUCTIONS + CONTROLLED_RETRY_INSTRUCTION
    assert neutral == BASE_INSTRUCTIONS
    assert "retry that same tool call once" in controlled
    assert "retry that same tool call once" not in neutral


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
    effects = store.list_refunds(DEMO_ORDER_ID)
    assert effects[0]["operation_id"].startswith("refund:order_1234:run_")
    assert len(fake_openai.responses.requests) == 3
    assert all(
        request["instructions"]
        == instructions_for_retry_policy(RETRY_POLICY_CONTROLLED)
        for request in fake_openai.responses.requests
    )

    events = [json.loads(line) for line in trace_path.read_text().splitlines()]
    attempts = [event for event in events if event["event"] == "tool_attempt_started"]
    model_turns = [event for event in events if event["event"] == "model_turn"]
    assert [attempt["tool"] for attempt in attempts] == [
        "get_order",
        "refund_order",
    ]
    assert attempts[1]["arguments"]["operation_id"] == effects[0]["operation_id"]
    assert all(turn["usage"] is None for turn in model_turns)
    assert events[-1]["event"] == "run_completed"
