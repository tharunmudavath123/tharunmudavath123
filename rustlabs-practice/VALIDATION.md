# Validation report — 29 October 2026

## Observed results

| Check | Observed result |
| --- | --- |
| Official RustLabs static checker | PASS, no WARN or FAIL lines |
| Reference implementation, local Python verifier | 9 test methods passed |
| Unmodified starter, local Python verifier | Rejected, process exit 1 |
| Reference with conflict validation disabled | Rejected |
| Reference with CRC validation disabled | Rejected |
| Reference with torn-tail truncation disabled | Rejected |
| Python syntax, TOML parsing, shell syntax | Passed |
| Docker image build | Passed on GitHub Actions |
| `harbor run -p tasks/ledger-recovery -a oracle` | Mean **1.000**, 1 trial, 0 exceptions |
| `harbor run -p tasks/ledger-recovery -a nop` | Mean **0.000**, 1 trial, 0 exceptions |

Actual checker output:

```
FSWE-CHECK v1 PASS tharunmudavath123/ledger-recovery 04777cce0df1
```

The checker was downloaded from
https://experts.rustlabs.ai/tools/frontierswe-check.py and executed against the
task folder. The fingerprint applies to these exact task-file contents.

The original local interpreter was Python 3.12.14. The Docker image based on
Python 3.12.8 was subsequently built and tested in the cloud. See
[reference.log](validation-logs/reference.log) and
[summary.json](validation-logs/summary.json). Reproduce the local checks with
`python3 check_local.py`. Mutation logs are generated locally by that script;
only the compact summary and passing reference log are committed.

## Harbor cloud run

[Successful GitHub Actions run](https://github.com/tharunmudavath123/tharunmudavath123/actions/runs/40837665742)
completed on 29 October 2026 at approximately 13:18 IST. Tested commit:
`95368680aae11068c081ca362502ab10367e9aa6`.

Runtime: GitHub-hosted Ubuntu 24.04, Harbor 0.25.0, host Python 3.12.15,
and Docker. Full Docker version output is in the job logs. The task files were
unchanged, so the checker fingerprint remains `04777cce0df1`.

- Oracle log: `1/1 Mean: 1.000`; reward artifact independently asserted as 1.
- Nop log: `1/1 Mean: 0.000`; reward artifact independently asserted as 0.
- Both jobs completed successfully with zero Harbor exceptions.
- Full logs and job results are attached to the run as `ledger-harbor-oracle`
  and `ledger-harbor-nop`, with a 14-day artifact retention period.

The workflow in `.github/workflows/ledger-harbor.yml` runs automatically when
its file or task files change on the `ai-practice-ledger-recovery` branch.
No local Docker or Harbor installation is necessary for that cloud workflow.

## Coverage and limits

Tests cover Unicode/null/nested values, overlays, snapshot reads, disjoint
transactions, write collisions, write skew, missing-key reads, phantom changes,
deletion history, read-only versions, aborts, restart, SIGKILL after acknowledged
commit, process locking, every truncation offset of a sample final frame, bad
checksums, malformed record shapes, version gaps, snapshot damage, stale WAL after
checkpoint and 100 deterministic randomized write batches with restarts.

Local tests execute the implementation as a subprocess. The subsequent GitHub
Actions run additionally exercised Docker builds, Harbor oracle/nop execution,
the verifier and reward collection.
SIGKILL and synthetic crash-window fixtures do not simulate physical power loss,
all filesystem failure modes or all instruction-level crash points. Difficulty,
agent success rate, performance and resistance to benchmark tampering have not
been independently calibrated. The configured 20-hour maximum is not a claim
that solving this task requires that duration.

## Submission status

The three requested technical checks now pass.** This does not resolve the
separate authorship restriction or establish long-horizon difficulty.

