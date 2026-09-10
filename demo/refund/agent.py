"""Minimal OpenAI Responses agent for the normal refund experiment."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from dotenv import find_dotenv, load_dotenv
from openai import AsyncOpenAI

from demo.refund.faults import (
    DEFAULT_FAULT_STATE,
    FAULT_NONE,
    FAULTS,
    reset_fault_state,
)
from demo.refund.mcp_client import RefundMCPClient, ResponseLostError
from demo.refund.store import DEFAULT_DB_PATH
from demo.refund.trace import append_trace

DEFAULT_MODEL = "gpt-5.6-luna"
PRODUCT_ROOT = Path(__file__).resolve().parents[2]
TASK_ID = "refund_order_1234_200"
TASK_PROMPT = """The customer should receive a $200 refund. Process it.

Order ID: 1234
"""

INSTRUCTIONS = """You are a minimal refund-processing agent in a fake local store.
Use the available tools to inspect the order and perform the requested refund.
Do not claim that a refund happened unless you received evidence from a tool.
If a tool call fails or its result is lost, retry that same tool call once before
trying another approach.
The tools affect fake SQLite data only.
"""

OPENAI_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "get_order",
        "description": "Read the fake order and its authoritative refund state.",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "The fake order identifier.",
                }
            },
            "required": ["order_id"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "refund_order",
        "description": "Commit a whole-dollar refund to the fake order.",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "The fake order identifier.",
                },
                "amount": {
                    "type": "integer",
                    "description": "Positive whole-dollar refund amount.",
                    "minimum": 1,
                },
            },
            "required": ["order_id", "amount"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


@dataclass(frozen=True)
class AgentRun:
    run_id: str
    model: str
    final_text: str
    trace_path: Path


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _append_trace(trace_path: Path, event: dict[str, Any]) -> None:
    append_trace(trace_path, {"timestamp": _utc_now(), **event})


def _tool_output(result: Any) -> str:
    payload: dict[str, Any] = {"is_error": bool(result.is_error)}
    if result.structured_content is not None:
        payload["result"] = result.structured_content
    else:
        payload["content"] = [
            block.model_dump(mode="json") for block in result.content
        ]
    return json.dumps(payload, sort_keys=True, default=str)


async def run_agent(
    openai_client: Any,
    mcp_client: Any,
    *,
    model: str,
    trace_path: Path,
    prompt: str = TASK_PROMPT,
    max_turns: int = 8,
) -> AgentRun:
    """Run one model-controlled MCP loop and return its final response."""
    if max_turns < 1:
        raise ValueError("max_turns must be at least 1")

    run_id = f"run_{uuid4().hex}"
    operation_id = f"refund:order_1234:{run_id}"
    input_items: list[Any] = [{"role": "user", "content": prompt}]
    _append_trace(
        trace_path,
        {
            "event": "run_started",
            "run_id": run_id,
            "task_id": TASK_ID,
            "operation_id": operation_id,
            "model": model,
            "prompt": prompt,
        },
    )

    for turn_number in range(1, max_turns + 1):
        response = await openai_client.responses.create(
            model=model,
            instructions=INSTRUCTIONS,
            tools=OPENAI_TOOLS,
            input=input_items,
            parallel_tool_calls=False,
            store=False,
        )
        model_turn_id = response.id
        input_items.extend(response.output)
        function_calls = [
            item for item in response.output if item.type == "function_call"
        ]
        usage = getattr(response, "usage", None)

        _append_trace(
            trace_path,
            {
                "event": "model_turn",
                "run_id": run_id,
                "task_id": TASK_ID,
                "model_turn_id": model_turn_id,
                "turn_number": turn_number,
                "function_call_count": len(function_calls),
                "output_text": response.output_text,
                "usage": usage.model_dump(mode="json") if usage else None,
            },
        )

        if not function_calls:
            _append_trace(
                trace_path,
                {
                    "event": "run_completed",
                    "run_id": run_id,
                    "task_id": TASK_ID,
                    "final_text": response.output_text,
                },
            )
            return AgentRun(
                run_id=run_id,
                model=model,
                final_text=response.output_text,
                trace_path=trace_path,
            )

        for function_call in function_calls:
            decision_id = function_call.call_id
            tool_attempt_id = f"attempt_{uuid4().hex}"
            try:
                arguments = json.loads(function_call.arguments)
                if not isinstance(arguments, dict):
                    raise ValueError("tool arguments must decode to an object")

                _append_trace(
                    trace_path,
                    {
                        "event": "tool_attempt_started",
                        "run_id": run_id,
                        "task_id": TASK_ID,
                        "operation_id": operation_id,
                        "model_turn_id": model_turn_id,
                        "decision_id": decision_id,
                        "tool_attempt_id": tool_attempt_id,
                        "tool": function_call.name,
                        "arguments": arguments,
                    },
                )
                result = await mcp_client.call_tool(function_call.name, arguments)
                output = _tool_output(result)
                outcome = "tool_error" if result.is_error else "response_received"
            except ResponseLostError as error:
                output = json.dumps(
                    {"ambiguous": True, "error": str(error)}, sort_keys=True
                )
                outcome = "response_lost"
            except Exception as error:
                output = json.dumps(
                    {"error": f"{type(error).__name__}: {error}"}, sort_keys=True
                )
                outcome = "exception"

            _append_trace(
                trace_path,
                {
                    "event": "tool_attempt_finished",
                    "run_id": run_id,
                    "task_id": TASK_ID,
                    "operation_id": operation_id,
                    "model_turn_id": model_turn_id,
                    "decision_id": decision_id,
                    "tool_attempt_id": tool_attempt_id,
                    "tool": function_call.name,
                    "outcome": outcome,
                    "output": output,
                },
            )
            input_items.append(
                {
                    "type": "function_call_output",
                    "call_id": function_call.call_id,
                    "output": output,
                }
            )

    raise RuntimeError(f"agent did not finish within {max_turns} model turns")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        default=os.environ.get("ROSSO_MODEL", DEFAULT_MODEL),
        help="OpenAI model available to the configured API project",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="SQLite database path",
    )
    parser.add_argument(
        "--trace",
        type=Path,
        help="JSONL attempt trace path; defaults to the ignored .run directory",
    )
    parser.add_argument(
        "--fault",
        choices=FAULTS,
        default=FAULT_NONE,
        help="One-shot refund response fault",
    )
    parser.add_argument(
        "--fault-state",
        type=Path,
        default=DEFAULT_FAULT_STATE,
        help="Marker used to consume the one-shot fault",
    )
    parser.add_argument("--read-timeout", type=float, default=10.0)
    parser.add_argument("--max-turns", type=int, default=8)
    return parser.parse_args()


async def async_main(args: argparse.Namespace) -> AgentRun:
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit(
            "OPENAI_API_KEY is not set. Copy the repository .env.example to "
            ".env, add an OpenAI API project key locally, and rerun. Never "
            "commit or paste the key into chat."
        )

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    trace_path = args.trace or PRODUCT_ROOT / ".run" / f"refund-{timestamp}.jsonl"
    openai_client = AsyncOpenAI(max_retries=0, timeout=60.0)
    reset_fault_state(args.fault_state)
    mcp_client = RefundMCPClient(
        db_path=args.db,
        fault=args.fault,
        fault_state_path=args.fault_state,
        read_timeout_seconds=args.read_timeout,
    )
    return await run_agent(
        openai_client,
        mcp_client,
        model=args.model,
        trace_path=trace_path,
        max_turns=args.max_turns,
    )


def main() -> None:
    load_dotenv(find_dotenv(usecwd=True))
    result = asyncio.run(async_main(parse_args()))
    print(result.final_text)
    print(f"Trace saved: {result.trace_path}")


if __name__ == "__main__":
    main()
