#!/usr/bin/env python3
"""Local checks and targeted verifier mutation tests; not a Harbor substitute."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
TASK = ROOT / "tasks/ledger-recovery"
REFERENCE = (TASK / "solution/store.py").read_text()
CASES = {
    "reference": (REFERENCE, True),
    "starter": ((TASK / "environment/store.py").read_text(), False),
    "missing-conflict-check": (REFERENCE.replace(
        'if version > tx["version"] and (k in touched or any(',
        'if False and (k in touched or any('), False),
    "missing-crc-check": (REFERENCE.replace(
        'if zlib.crc32(payload) != checksum:', 'if False:'), False),
    "missing-torn-tail-truncation": (REFERENCE.replace(
        'self.wal.truncate(valid_end)', 'pass  # deliberately broken'), False),
}


def main():
    output = ROOT / "validation-logs"
    output.mkdir(exist_ok=True)
    results = {}
    with tempfile.TemporaryDirectory(prefix="ledger-mutations-") as tmp:
        for name, (source, expected_success) in CASES.items():
            path = Path(tmp) / (name + ".py")
            path.write_text(source)
            env = dict(os.environ, LEDGER_TEST_SCRIPT=str(path), PYTHONDONTWRITEBYTECODE="1")
            run = subprocess.run([sys.executable, str(TASK / "tests/verify.py")],
                                 env=env, capture_output=True, text=True, timeout=180)
            (output / (name + ".log")).write_text(run.stdout + run.stderr)
            results[name] = {"exit_code": run.returncode,
                             "expected_behavior_observed": (run.returncode == 0) == expected_success}
            print(name, results[name], flush=True)
    (output / "summary.json").write_text(json.dumps(results, indent=2) + "\n")
    return 0 if all(r["expected_behavior_observed"] for r in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
