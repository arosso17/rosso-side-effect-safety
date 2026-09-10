"""Stdio MCP client used for one isolated refund-tool attempt at a time."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcp import Client, StdioServerParameters

from demo.refund.faults import FAULT_COMMIT_THEN_DISCONNECT, FAULT_NONE

PRODUCT_ROOT = Path(__file__).resolve().parents[2]


class ResponseLostError(RuntimeError):
    """The MCP connection closed without revealing the operation outcome."""


@dataclass(frozen=True)
class RefundMCPClient:
    """Launch a fresh local MCP server process for each model tool attempt."""

    db_path: Path
    fault: str = FAULT_NONE
    fault_state_path: Path | None = None
    read_timeout_seconds: float = 10.0

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        state_path = self.fault_state_path
        state_existed_before = bool(state_path and state_path.exists())
        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("OPENAI_")
        }
        environment["ROSSO_REFUND_DB"] = str(self.db_path.resolve())
        environment["ROSSO_REFUND_FAULT"] = self.fault
        environment["PYTHONUNBUFFERED"] = "1"
        if state_path is not None:
            environment["ROSSO_REFUND_FAULT_STATE"] = str(state_path.resolve())

        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "demo.refund.server"],
            env=environment,
            cwd=PRODUCT_ROOT,
        )

        try:
            async with Client(
                parameters,
                raise_exceptions=True,
                read_timeout_seconds=self.read_timeout_seconds,
            ) as client:
                return await client.call_tool(name, arguments)
        except Exception as error:
            fault_was_consumed = bool(
                self.fault == FAULT_COMMIT_THEN_DISCONNECT
                and state_path
                and not state_existed_before
                and state_path.exists()
            )
            if fault_was_consumed:
                raise ResponseLostError(
                    "The MCP connection closed before a tool result was received. "
                    "The operation outcome is unknown."
                ) from error
            raise
