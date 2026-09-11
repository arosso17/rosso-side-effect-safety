# Can one retry policy survive both sides of an uncertain outcome?

This folder contains the public preregistration and complete structured evidence
for a 240-trial study of recovery policy at the side-effect boundary.

The agent will receive the same lost-result message after two different events:

- the fault layer disconnects before sending the refund upstream, so no refund
  exists; or
- the refund commits upstream and the fault layer disconnects before returning
  the result, so one refund already exists.

Four prompt policies were tested 30 times under each fault. The primary outcome
was whether authoritative SQLite state contained exactly one $200 refund.

## Result

| Policy | Before-effect loss | After-commit loss |
| --- | ---: | ---: |
| Explicit retry | 30 of 30 exactly once | 0 of 30; 30 duplicates |
| No guidance | 27 of 30 exactly once; 3 zero | 30 of 30 exactly once |
| Do not retry | 0 of 30; 30 zero | 30 of 30 exactly once |
| State-aware | 30 of 30 exactly once | 30 of 30 exactly once |

The state-aware result is bounded evidence for this toy environment, not proof
of safety. Its read tool returned immediate, authoritative SQLite state.

- [Full preregistration](PREREGISTRATION.md)
- [Results and limitations](RESULTS.md)
- [Machine-readable plan](data/plan.json)
- [Frozen trial order](data/order.json)
- [All 240 structured trial records](data/trials.jsonl)
- [Final-report audit](data/final-report-coding.json)
- [Checksums](SHA256SUMS)
- [Standalone verifier](verify_results.py)

The preregistration is immutable at commit
[`517d1b15`](https://github.com/arosso17/rosso-side-effect-safety/commit/517d1b15f89b2301fc5d43d5a681150359a08a03),
which precedes every live model trial. Run the verifier from the repository root
without an API key or third-party package:

```bash
python studies/0003-retry-boundary/verify_results.py
```
