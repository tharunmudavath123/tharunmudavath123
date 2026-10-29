# Ledger Recovery — Harbor Practice Task

A transactional database implementation challenge covering snapshot isolation,
conflict detection, durable logs, and recovery after interrupted writes.

## What's included

`tasks/ledger-recovery/` is the task folder. It contains:

- `instruction.md`: complete public protocol, conflict rules and disk format.
- `task.toml`: 20-hour agent ceiling, resource limits, authorship metadata.
- `environment/Dockerfile`: Python-only environment; copies only the starter.
- `environment/store.py`: deliberately incomplete agent starting point.
- `solution/solve.sh` and `solution/store.py`: reference implementation.
- `tests/test.sh` and `tests/verify.py`: black-box, all-or-nothing scoring.

The challenge combines snapshot transactions, read/write and predicate conflict
detection, durable framed logs, corruption refusal, checkpoint recovery and
process locking. It is not copied from FrontierSWE's tasks. No claim is made
that originality relative to all published tasks has been exhaustively checked.

## Validation status

The [GitHub Actions run](https://github.com/tharunmudavath123/tharunmudavath123/actions/runs/40837665742)
passed the RustLabs checker and actual Harbor runs: **oracle Mean 1.000** and
**nop Mean 0.000**, each with zero exceptions. See [VALIDATION.md](VALIDATION.md)
for evidence and limitations. A 72000-second budget does not
establish long-horizon difficulty; the task has not been calibrated on agents or
human implementers. Treat this as a practice draft rather than a submission-ready
benchmark. Nine test methods cover many generated and parameterized cases.

## Run the required checks

No local installation is needed for the cloud workflow: changes to task files
on the `ai-practice-ledger-recovery` branch automatically trigger GitHub Actions.
Open the repository's Actions tab to inspect runs and download their evidence.

For a local run, use a Linux machine with Python 3.11+, Docker running,
and Harbor installed using
the [official Harbor instructions](https://github.com/harbor-framework/harbor).
Record the Harbor version and Docker version with your results. From this folder:

```bash
curl -fL https://experts.rustlabs.ai/tools/frontierswe-check.py -o /tmp/frontierswe-check.py
python3 /tmp/frontierswe-check.py tasks/ledger-recovery
harbor run -p tasks/ledger-recovery -a oracle
harbor run -p tasks/ledger-recovery -a nop
```

Required outcomes are checker PASS, actual Harbor oracle Mean 1.000 and actual
Harbor nop Mean 0.000. All three were observed in the linked cloud run. Any
future task changes require fresh validation. Keep the full run logs and job
results. Re-run the checker after any change because its fingerprint covers
task-file contents.

Local behavioral development check (does not need Docker):

```bash
LEDGER_TEST_SCRIPT="$PWD/tasks/ledger-recovery/solution/store.py" \
  PYTHONDONTWRITEBYTECODE=1 python3 tasks/ledger-recovery/tests/verify.py
```

## Isolation and scoring

Only `environment/` is the Docker build context. Neither the answer nor hidden
tests is copied into the agent image. Harbor injects tests for verification and
injects the reference solution only for the oracle run. The verifier sets `/tests`
to root-only and launches candidate processes as `agent`. Reward starts at zero
and becomes one only if the full verifier succeeds. The candidate must not be
given a mounted copy of the whole repository during agent execution.

These measures reduce accidental answer leakage; they are not a proven security
sandbox against an adversarial agent attacking the benchmark infrastructure.
Do not execute unknown candidates on your host; use the container.

## Before considering any application

Obtain a clear answer on the AI-authorship restriction, independently review the
oracle and tests, and calibrate difficulty. Re-run Harbor after task changes.
This repository does not claim selection, payment, or acceptance by RustLabs.
