#!/bin/bash
set -euo pipefail
mkdir -p /logs/verifier
printf '0\n' > /logs/verifier/reward.txt
# The verifier runs as root; candidate processes run as the unprivileged agent.
chmod 700 /tests
if python /tests/verify.py; then
    printf '1\n' > /logs/verifier/reward.txt
fi
