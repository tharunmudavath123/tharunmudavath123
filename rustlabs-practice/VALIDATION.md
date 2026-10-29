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
| Docker image build | NOT RUN — Docker unavailable in authoring environment |
| `harbor run -p tasks/ledger-recovery -a oracle` | NOT RUN — Harbor and Docker unavailable |
| `harbor run -p tasks/ledger-recovery -a nop` | NOT RUN — Harbor and Docker unavailable |

Actual checker output:

```
FSWE-CHECK v1 PASS tharunmudavath123/ledger-recovery 04777cce0df1
```

The checker was downloaded from
https://experts.rustlabs.ai/tools/frontierswe-check.py and executed against the
task folder. The fingerprint applies to these exact task-file contents.

The host interpreter was Python 3.12.14. The Dockerfile specifies Python 3.12.8;
that container runtime has not been exercised. See
[reference.log](validation-logs/reference.log) and
[summary.json](validation-logs/summary.json). Reproduce the local checks with
`python3 check_local.py`. Mutation logs are generated locally by that script;
only the compact summary and passing reference log are committed.

## Coverage and limits

Tests cover Unicode/null/nested values, overlays, snapshot reads, disjoint
transactions, write collisions, write skew, missing-key reads, phantom changes,
deletion history, read-only versions, aborts, restart, SIGKILL after acknowledged
commit, process locking, every truncation offset of a sample final frame, bad
checksums, malformed record shapes, version gaps, snapshot damage, stale WAL after
checkpoint and 100 deterministic randomized write batches with restarts.

The local tests execute the implementation as a subprocess. This is not an
end-to-end test of Harbor packaging, container permissions or reward collection.
SIGKILL and synthetic crash-window fixtures do not simulate physical power loss,
all filesystem failure modes or all instruction-level crash points. Difficulty,
agent success rate, performance and resistance to benchmark tampering have not
been independently calibrated. The configured 20-hour maximum is not a claim
that solving this task requires that duration.

## Submission status

**Not submission-ready.** No Harbor Mean scores have been measured. Do not enter
1.000 or 0.000 into an application form as if they were observed here.

The package is predominantly AI-generated and therefore does not satisfy the
RustLabs email's stated authorship restriction. The static checker does not
establish eligibility. Any submission must disclose this authorship and first
resolve eligibility with RustLabs; this repository does not claim acceptance.
