#!/usr/bin/env python3
"""Replace this starter with the durable store described in the instructions."""
import argparse
import json
import sys

parser = argparse.ArgumentParser()
parser.add_argument("--dir", required=True)
parser.parse_args()
for line in sys.stdin:
    print(json.dumps({"error": "UNIMPLEMENTED"}), flush=True)
