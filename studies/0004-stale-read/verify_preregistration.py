"""Verify the frozen stale-read preregistration using only the standard library."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
EXPECTED_PLAN_SHA256 = (
    "eaf378954205c060950e52116ec8ab7eb0cc8131fb8830cfa53aa1ac1807ab2c"
)
EXPECTED_ORDER_DOCUMENT_SHA256 = (
    "38aaef3ecc8f1da8f4cf655f3a71411e9ccb10ecce880d90a3887cb2da6f79c5"
)
EXPECTED_TRIAL_ORDER_SHA256 = (
    "608607d8ffcd30de050bc744cfe4a6afbe880fbccddfd0f3f49b2aa387e55f8f"
)
EXPECTED_CELL_IDS = {
    "state_aware_unsafe_postcommit_lag_0p0",
    "state_aware_unsafe_postcommit_lag_2p3",
    "state_aware_unsafe_postcommit_lag_2p4",
    "state_aware_unsafe_postcommit_lag_2p5",
    "state_aware_unsafe_postcommit_lag_2p8",
    "state_aware_unsafe_postcommit_lag_8p0",
    "neutral_unsafe_postcommit_lag_0p0",
    "neutral_unsafe_postcommit_lag_8p0",
    "state_aware_safe_postcommit_lag_8p0",
    "state_aware_unsafe_preeffect_lag_8p0",
}


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"verification failed: {message}")


def main() -> int:
    plan = json.loads((ROOT / "plan.json").read_text(encoding="utf-8"))
    order_document = json.loads((ROOT / "order.json").read_text(encoding="utf-8"))
    require(
        canonical_digest(plan) == EXPECTED_PLAN_SHA256,
        "plan.json canonical digest changed",
    )
    require(
        canonical_digest(order_document) == EXPECTED_ORDER_DOCUMENT_SHA256,
        "order.json canonical digest changed",
    )
    require(plan["study_id"] == "0004-stale-read", "unexpected study ID")
    require(plan["runs_per_cell"] == 30, "runs per cell is not 30")
    require(plan["total_planned_trials"] == 300, "planned total is not 300")
    require(plan["seed"] == 20260912, "unexpected randomization seed")
    require(
        plan["order_sha256"] == EXPECTED_TRIAL_ORDER_SHA256,
        "plan order digest changed",
    )
    require(
        order_document["sha256"] == EXPECTED_TRIAL_ORDER_SHA256,
        "order document digest changed",
    )
    trials = order_document["trials"]
    require(len(trials) == 300, "order does not contain 300 trials")
    require(
        canonical_digest(trials) == EXPECTED_TRIAL_ORDER_SHA256,
        "trial order does not match its registered digest",
    )

    cells = {cell["cell_id"]: cell for cell in plan["cells"]}
    require(set(cells) == EXPECTED_CELL_IDS, "registered cell set changed")
    counts = Counter(trial["cell_id"] for trial in trials)
    require(
        counts == Counter({cell_id: 30 for cell_id in EXPECTED_CELL_IDS}),
        "every cell must occur exactly 30 times",
    )
    running_counts: Counter[str] = Counter()
    for expected_number, trial in enumerate(trials, start=1):
        require(
            trial["trial_number"] == expected_number,
            f"trial number mismatch at position {expected_number}",
        )
        cell_id = trial["cell_id"]
        running_counts[cell_id] += 1
        require(
            trial["cell_trial_number"] == running_counts[cell_id],
            f"cell trial number mismatch at trial {expected_number}",
        )
        require(
            {
                key: value
                for key, value in trial.items()
                if key not in {"trial_number", "block", "cell_trial_number"}
            }
            == cells[cell_id],
            f"cell parameters mismatch at trial {expected_number}",
        )

    for block in range(1, 31):
        block_cells = {trial["cell_id"] for trial in trials if trial["block"] == block}
        require(block_cells == EXPECTED_CELL_IDS, f"block {block} is incomplete")

    contract = plan["prompt_contract"]
    require(
        canonical_digest(contract) == plan["prompt_contract_sha256"],
        "prompt contract digest mismatch",
    )
    zero_control = plan["read_indistinguishability_control"]
    zero_digest = hashlib.sha256(
        zero_control["canonical_zero_output"].encode("utf-8")
    ).hexdigest()
    require(
        zero_digest == zero_control["canonical_zero_output_sha256"],
        "canonical zero-read output digest mismatch",
    )

    print("preregistration verified")
    print("study: 0004-stale-read")
    print("cells: 10")
    print("planned valid trials: 300")
    print(f"order SHA-256: {EXPECTED_TRIAL_ORDER_SHA256}")
    print("no model calls were made")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
