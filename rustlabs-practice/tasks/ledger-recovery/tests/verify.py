"""Black-box behavioral checks. No reference implementation is imported."""
import json
import os
from pathlib import Path
import pwd
import random
import select
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

SCRIPT = os.environ.get("LEDGER_TEST_SCRIPT", "/app/store.py")
try:
    AGENT = pwd.getpwnam("agent") if os.getuid() == 0 else None
except KeyError:
    AGENT = None  # Local non-container developer checks.


def frame(obj):
    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode()
    return struct.pack(">II", len(raw), zlib.crc32(raw)) + raw


def record(v, *writes):
    return frame({"version": v, "writes": list(writes)})


class Process:
    def __init__(self, directory):
        kwargs = {}
        if AGENT:
            kwargs = {"user": AGENT.pw_uid, "group": AGENT.pw_gid, "extra_groups": []}
        self.p = subprocess.Popen([sys.executable, SCRIPT, "--dir", str(directory)],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True, **kwargs)

    def cmd(self, op, **args):
        self.p.stdin.write(json.dumps(dict(op=op, **args)) + "\n")
        self.p.stdin.flush()
        ready, _, _ = select.select([self.p.stdout], [], [], 5)
        if not ready:
            raise AssertionError("response timeout")
        line = self.p.stdout.readline()
        if not line:
            raise AssertionError("candidate exited without a response")
        return json.loads(line)

    def close(self):
        if self.p.poll() is None:
            self.p.stdin.close()
            self.p.wait(timeout=5)
        for pipe in (self.p.stdin, self.p.stdout, self.p.stderr):
            pipe.close()

    def kill(self):
        self.p.kill()
        self.p.wait(timeout=5)
        self.close()


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ledger-test-")
        self.directory = Path(self.tmp.name)
        if AGENT:
            os.chown(self.directory, AGENT.pw_uid, AGENT.pw_gid)
        self.processes = []

    def tearDown(self):
        for p in self.processes:
            if p.p.poll() is None:
                p.kill()
            else:
                p.close()
        self.tmp.cleanup()

    def start(self):
        p = Process(self.directory)
        self.processes.append(p)
        return p

    def ok(self, p, op, **args):
        self.assertEqual(p.cmd(op, **args), {"ok": True})

    def begin(self, p, tx, v):
        self.assertEqual(p.cmd("begin", tx=tx), {"ok": True, "version": v})

    def commit(self, p, tx, v):
        self.assertEqual(p.cmd("commit", tx=tx), {"ok": True, "version": v})

    def write(self, p, k, value, v, tx="w"):
        self.begin(p, tx, v - 1)
        self.ok(p, "put", tx=tx, key=k, value=value)
        self.commit(p, tx, v)

    def fixture(self, name, data):
        path = self.directory / name
        path.write_bytes(data)
        if AGENT:
            os.chown(path, AGENT.pw_uid, AGENT.pw_gid)

    def test_protocol_snapshot_and_overlay(self):
        p = self.start()
        self.begin(p, "a", 0)
        self.assertEqual(p.cmd("begin", tx="a"), {"error": "EXISTS"})
        self.assertEqual(p.cmd("abort", tx="absent"), {"error": "NO_TX"})
        self.ok(p, "put", tx="a", key="నమస్తే", value=None)
        self.assertEqual(p.cmd("get", tx="a", key="నమస్తే"), {"found": True, "value": None})
        self.ok(p, "put", tx="a", key="a", value={"nested": [True, 2, "é"]})
        self.ok(p, "delete", tx="a", key="a")
        self.assertEqual(p.cmd("get", tx="a", key="a"), {"found": False})
        self.assertEqual(p.cmd("scan", tx="a", prefix=""), {"items": [["నమస్తే", None]]})
        self.assertEqual(p.cmd("checkpoint"), {"error": "BUSY"})
        self.commit(p, "a", 1)
        self.assertEqual(p.cmd("get", tx="a", key="a"), {"error": "NO_TX"})
        self.begin(p, "a", 1)
        self.write(p, "నమస్తే", 100, 2)
        self.assertEqual(p.cmd("get", tx="a", key="నమస్తే"), {"found": True, "value": None})
        self.assertEqual(p.cmd("commit", tx="a"), {"error": "CONFLICT"})
        self.begin(p, "r", 2)
        before = (self.directory / "wal.bin").read_bytes()
        self.commit(p, "r", 2)
        self.assertEqual((self.directory / "wal.bin").read_bytes(), before)

    def test_write_conflicts_and_disjoint_commits(self):
        p = self.start()
        self.begin(p, "a", 0)
        self.begin(p, "b", 0)
        self.ok(p, "put", tx="a", key="x", value=1)
        self.ok(p, "put", tx="b", key="y", value=2)
        self.commit(p, "a", 1)
        self.commit(p, "b", 2)
        self.begin(p, "a", 2)
        self.begin(p, "b", 2)
        self.ok(p, "delete", tx="a", key="missing")
        self.ok(p, "put", tx="b", key="missing", value=3)
        self.commit(p, "a", 3)
        self.assertEqual(p.cmd("commit", tx="b"), {"error": "CONFLICT"})
        self.begin(p, "a", 3)
        self.begin(p, "b", 3)
        self.assertEqual(p.cmd("get", tx="a", key="y"), {"found": True, "value": 2})
        self.assertEqual(p.cmd("get", tx="b", key="x"), {"found": True, "value": 1})
        self.ok(p, "put", tx="a", key="x", value=5)
        self.ok(p, "put", tx="b", key="y", value=5)
        self.commit(p, "a", 4)
        self.assertEqual(p.cmd("commit", tx="b"), {"error": "CONFLICT"})

    def test_phantoms_aba_and_missing_reads(self):
        p = self.start()
        self.begin(p, "scan", 0)
        self.assertEqual(p.cmd("scan", tx="scan", prefix="p/"), {"items": []})
        self.write(p, "p/new", 1, 1)
        self.begin(p, "d", 1)
        self.ok(p, "delete", tx="d", key="p/new")
        self.commit(p, "d", 2)
        self.assertEqual(p.cmd("commit", tx="scan"), {"error": "CONFLICT"})
        self.begin(p, "r", 2)
        self.assertEqual(p.cmd("get", tx="r", key="ghost"), {"found": False})
        self.begin(p, "d", 2)
        self.ok(p, "delete", tx="d", key="ghost")
        self.commit(p, "d", 3)
        self.assertEqual(p.cmd("commit", tx="r"), {"error": "CONFLICT"})
        self.begin(p, "outside", 3)
        self.assertEqual(p.cmd("scan", tx="outside", prefix="p/"), {"items": []})
        self.write(p, "q/outside", 7, 4)
        self.commit(p, "outside", 4)

    def test_restart_sigkill_and_lock(self):
        p = self.start()
        self.write(p, "durable", [1, None, {"x": False}], 1)
        other = self.start()
        out, err = other.p.communicate(timeout=5)
        self.assertEqual(other.p.returncode, 2)
        self.assertIn("LOCKED", err)
        self.assertEqual(out, "")
        self.begin(p, "uncommitted", 1)
        self.ok(p, "put", tx="uncommitted", key="lost", value=True)
        p.kill()
        q = self.start()
        self.begin(q, "r", 1)
        self.assertEqual(q.cmd("scan", tx="r", prefix=""),
                         {"items": [["durable", [1, None, {"x": False}]]]})
        self.ok(q, "abort", tx="r")
        self.assertEqual(q.cmd("checkpoint"), {"ok": True, "version": 1})
        self.assertEqual((self.directory / "wal.bin").stat().st_size, 0)
        q.close()
        r = self.start()
        self.begin(r, "r", 1)
        self.assertEqual(r.cmd("get", tx="r", key="durable"),
                         {"found": True, "value": [1, None, {"x": False}]})

    def test_every_truncation_of_final_frame(self):
        first = record(1, ["put", "first", "kept"])
        last = record(2, ["put", "second", "torn"])
        for cut in range(len(last)):
            with self.subTest(cut=cut):
                self.fixture("wal.bin", first + last[:cut])
                p = self.start()
                self.begin(p, "r", 1)
                self.assertEqual(p.cmd("scan", tx="r", prefix=""), {"items": [["first", "kept"]]})
                self.ok(p, "abort", tx="r")
                self.write(p, "after", cut, 2)
                p.close()
                q = self.start()
                self.begin(q, "r", 2)
                self.assertEqual(q.cmd("get", tx="r", key="after"), {"found": True, "value": cut})
                q.close()

    def test_corruption_refusal_without_modification(self):
        good = record(1, ["put", "a", 1])
        bad_crc = bytearray(good)
        bad_crc[7] ^= 1
        cases = [bytes(bad_crc), good + record(3, ["put", "b", 2]),
                 record(2, ["put", "b", 2]), struct.pack(">II", 0, 0),
                 struct.pack(">II", 16777217, 0),
                 frame({"version": True, "writes": [["put", "a", 1]]}),
                 frame({"version": 1, "writes": [["put", "a", 1], ["delete", "a"]]}),
                 frame({"version": 1, "writes": [["unknown", "a"]]}),
                 frame({"version": 1, "writes": []}), frame([]),
                 good + good, bytes(bad_crc) + b"partial"]
        for raw in cases:
            with self.subTest(raw=raw):
                self.fixture("wal.bin", raw)
                p = self.start()
                out, err = p.p.communicate(timeout=5)
                self.assertEqual(p.p.returncode, 2)
                self.assertIn("CORRUPT", err)
                self.assertEqual(out, "")
                self.assertEqual((self.directory / "wal.bin").read_bytes(), raw)

    def test_snapshot_corruption(self):
        good = frame({"version": 1, "data": {"a": 1}})
        for raw in [b"", good[:-1], good + good, frame({"version": -1, "data": {}}),
                    frame({"version": 1, "data": []})]:
            with self.subTest(raw=raw):
                self.fixture("snapshot.bin", raw)
                p = self.start()
                _, err = p.p.communicate(timeout=5)
                self.assertEqual(p.p.returncode, 2)
                self.assertIn("CORRUPT", err)
                self.assertEqual((self.directory / "snapshot.bin").read_bytes(), raw)

    def test_checkpoint_crash_windows(self):
        old = record(1, ["put", "deleted", 1]) + record(2, ["delete", "deleted"], ["put", "a", 2])
        for tail in [b"", record(3, ["put", "b", 3])]:
            with self.subTest(tail=tail):
                self.fixture("snapshot.bin", frame({"version": 2, "data": {"a": 2}}))
                self.fixture("snapshot.tmp", b"interrupted temporary snapshot")
                self.fixture("wal.bin", old + tail)
                p = self.start()
                v = 3 if tail else 2
                self.begin(p, "r", v)
                expected = [["a", 2]] + ([["b", 3]] if tail else [])
                self.assertEqual(p.cmd("scan", tx="r", prefix=""), {"items": expected})
                self.ok(p, "abort", tx="r")
                self.assertEqual(p.cmd("checkpoint"), {"ok": True, "version": v})
                self.assertEqual((self.directory / "wal.bin").read_bytes(), b"")
                p.close()

    def test_randomized_histories(self):
        # Independent simple state model: checks protocol/persistence across varied batches.
        rng = random.Random(679129)
        model, version = {}, 0
        p = self.start()
        for batch in range(100):
            self.begin(p, "t", version)
            staged = model.copy()
            writes = 0
            for _ in range(rng.randrange(1, 9)):
                k = rng.choice(["p/", "q/", "é/"]) + str(rng.randrange(30))
                if rng.randrange(3):
                    value = rng.choice([None, True, batch, [batch, "value"], {"n": batch}])
                    self.ok(p, "put", tx="t", key=k, value=value)
                    staged[k] = value
                else:
                    self.ok(p, "delete", tx="t", key=k)
                    staged.pop(k, None)
                writes += 1
            self.assertEqual(p.cmd("scan", tx="t", prefix=""),
                             {"items": [[k, staged[k]] for k in sorted(staged)]})
            if batch % 7 == 0:
                self.ok(p, "abort", tx="t")
            else:
                version += bool(writes)
                self.commit(p, "t", version)
                model = staged
            if batch % 10 == 0:
                self.assertEqual(p.cmd("checkpoint"), {"ok": True, "version": version})
            if batch % 9 == 0:
                p.close()
                p = self.start()
                self.begin(p, "r", version)
                self.assertEqual(p.cmd("scan", tx="r", prefix=""), {"items": [[k, model[k]] for k in sorted(model)]})
                self.commit(p, "r", version)


if __name__ == "__main__":
    unittest.main(verbosity=2)
