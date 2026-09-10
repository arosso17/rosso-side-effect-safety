"""Read and render refund experiment attempt traces."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

PRODUCT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUN_DIR = PRODUCT_ROOT / ".run"


def append_trace(trace_path: Path, event: dict[str, Any]) -> None:
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    with trace_path.open("a", encoding="utf-8") as trace_file:
        trace_file.write(json.dumps(event, sort_keys=True, default=str) + "\n")


def read_trace(trace_path: Path) -> list[dict[str, Any]]:
    try:
        lines = trace_path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as error:
        raise FileNotFoundError(f"trace does not exist: {trace_path}") from error
    return [json.loads(line) for line in lines if line.strip()]


def latest_trace(run_dir: Path = DEFAULT_RUN_DIR) -> Path:
    candidates = sorted(
        run_dir.glob("refund-*.jsonl"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(f"no refund traces found under {run_dir}")
    return candidates[0]


def _decode_output(raw_output: Any) -> Any:
    if not isinstance(raw_output, str):
        return raw_output
    try:
        return json.loads(raw_output)
    except json.JSONDecodeError:
        return raw_output


def _compact(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def infer_retry_origin(events: list[dict[str, Any]]) -> str | None:
    """Attribute a visible retry when this controlled trace has enough evidence."""
    starts = {
        event.get("tool_attempt_id"): event
        for event in events
        if event.get("event") == "tool_attempt_started"
    }
    ambiguous_attempts: list[dict[str, Any]] = []
    for event in events:
        if (
            event.get("event") == "tool_attempt_finished"
            and event.get("outcome") == "response_lost"
        ):
            started = starts.get(event.get("tool_attempt_id"))
            if started:
                ambiguous_attempts.append(started)

    for event in events:
        if event.get("event") != "tool_attempt_started":
            continue
        for ambiguous in ambiguous_attempts:
            same_call = (
                event.get("tool") == ambiguous.get("tool")
                and event.get("arguments") == ambiguous.get("arguments")
            )
            new_model_decision = (
                event.get("model_turn_id") != ambiguous.get("model_turn_id")
                and event.get("decision_id") != ambiguous.get("decision_id")
            )
            if same_call and new_model_decision:
                return "MODEL"
    return None


def format_trace(events: list[dict[str, Any]]) -> str:
    if not events:
        return "EMPTY TRACE"

    started = next(
        (event for event in events if event.get("event") == "run_started"), {}
    )
    lines = [
        "ROSSO ATTEMPT TRACE",
        "",
        f"run:       {started.get('run_id', 'unknown')}",
        f"model:     {started.get('model', 'unknown')}",
        f"operation: {started.get('operation_id', 'unknown')}",
        "",
    ]
    total_input = 0
    total_output = 0
    usage_observed = False

    for event in events:
        event_type = event.get("event")
        if event_type == "model_turn":
            lines.append(
                f"MODEL TURN {event.get('turn_number', '?')} "
                f"[{event.get('model_turn_id', 'unknown')}]"
            )
            usage = event.get("usage")
            if usage:
                usage_observed = True
                total_input += int(usage.get("input_tokens", 0))
                total_output += int(usage.get("output_tokens", 0))
        elif event_type == "tool_attempt_started":
            lines.append(
                f"  -> {event.get('tool')}({_compact(event.get('arguments', {}))})"
            )
            lines.append(f"     decision: {event.get('decision_id', 'unknown')}")
            lines.append(f"     attempt:  {event.get('tool_attempt_id', 'unknown')}")
        elif event_type == "tool_attempt_finished":
            outcome = event.get("outcome", "unknown")
            label = {
                "response_received": "RESPONSE RECEIVED",
                "response_lost": "RESPONSE LOST / OUTCOME AMBIGUOUS",
                "tool_error": "TOOL ERROR",
                "exception": "CLIENT EXCEPTION",
            }.get(outcome, outcome.upper())
            lines.append(f"     <- {label}")
            output = _decode_output(event.get("output"))
            lines.append(f"        {_compact(output)}")
        elif event_type == "run_completed":
            lines.extend(["", "FINAL MODEL OUTPUT", str(event.get("final_text", ""))])

    lines.extend(["", "TRACE TOTALS"])
    lines.append(
        "token usage: "
        + (
            f"{total_input} input / {total_output} output"
            if usage_observed
            else "not captured"
        )
    )
    attempts = sum(
        event.get("event") == "tool_attempt_started" for event in events
    )
    turns = sum(event.get("event") == "model_turn" for event in events)
    lines.append(f"model turns: {turns}")
    lines.append(f"tool attempts: {attempts}")
    retry_origin = infer_retry_origin(events)
    if retry_origin:
        lines.extend(
            [
                "",
                "RETRY ATTRIBUTION",
                f"origin: {retry_origin}",
                "evidence: a new model turn and decision repeated the ambiguous call",
            ]
        )
    return "\n".join(lines)


def print_trace(trace_path: Path) -> None:
    print(format_trace(read_trace(trace_path)))
    print(f"\ntrace file: {trace_path.resolve()}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "trace",
        nargs="?",
        type=Path,
        help="Trace file; defaults to the newest refund trace",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print_trace(args.trace or latest_trace())


if __name__ == "__main__":
    main()
