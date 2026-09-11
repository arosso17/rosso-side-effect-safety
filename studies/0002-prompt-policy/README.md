# Did the retry prompt cause the double refund?

This folder contains the complete structured evidence for a 90-trial follow-up
to [the original double-refund experiment](../../README.md).

The task and commit-then-disconnect failure stayed fixed. The only experimental
change was the retry-policy suffix in the agent's system instructions:

- explicit retry;
- no retry guidance; or
- explicit do-not-retry guidance with read-only reconciliation allowed.

## Result

| Policy | Duplicate effects | Recovery after lost response | Final report |
| --- | ---: | --- | --- |
| Explicit retry | 30 of 30 | repeated `refund_order` 30 of 30 | false completion 30 of 30 |
| No guidance | 0 of 30 | called `get_order` 30 of 30 | accurate completion 30 of 30 |
| Do not retry | 0 of 30 | called `get_order` 30 of 30 | accurate completion 30 of 30 |

Every controlled trial created two $200 rows totaling $400. Its final answer
reported a successfully processed $200 refund without disclosing the second
row.

`0 of 30` is not `0%` in the population. If the trials are treated as
independent Bernoulli draws, the exact one-sided 95% upper confidence bound is
about 9.5%. The tool path was invariant within each arm, so independence and
generalization to future model or infrastructure changes should not be assumed.

## Inspect the study

- [Protocol](STUDY-PROTOCOL.md)
- [Results and limitations](RESULTS.md)
- [Machine-readable evidence](data/)
- [SHA-256 checksums](SHA256SUMS)
- [Standalone verifier](verify_results.py)

Run the verifier from the repository root without an API key or third-party
packages:

```bash
python studies/0002-prompt-policy/verify_results.py
```

It recomputes the order digest, validates all 90 trial records, checks the
authoritative effect outcomes and tool paths, verifies the final-answer coding,
and prints the aggregate counts and cost total.

`SHA256SUMS` pins the exact file bytes. The repository's `.gitattributes`
enforces LF line endings across platforms, so conventional checksum tools also
work. From the study directory:

```bash
sha256sum -c SHA256SUMS
```

## Evidence boundary

This is a post-run publication package, not a formal preregistration. The
protocol documents the study that was executed, and the trial-level data makes
the reported result auditable.

Raw provider response IDs, local databases, and internal project files are not
included. `trials.jsonl` retains the model controls, ordered tool outcomes,
authoritative effect counts, final user-facing text, token usage, and estimated
cost for every valid trial.

`estimated_cost_usd` is a fixed-precision decimal string, not a mixture of JSON
types. Parse it with `decimal.Decimal` when aggregating. The runner left
`final_report_classification` as `unreviewed` because it did not make
interpretive labels during execution. The canonical post-run human audit is
`data/final-report-coding.json`, and the verifier cross-checks that audit against
every recorded final text.
