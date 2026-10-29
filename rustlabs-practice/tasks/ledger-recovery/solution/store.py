#!/usr/bin/env python3
"""AI-generated reference implementation; not distributed to the agent."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import struct
import sys
import zlib

MAX_FRAME = 16 * 1024 * 1024
DELETED = object()


class Corrupt(Exception):
    pass


def integer(x):
    return type(x) is int


def key(x):
    return isinstance(x, str) and bool(x)


def encode(obj):
    payload = json.dumps(obj, ensure_ascii=False, allow_nan=False,
                         separators=(",", ":")).encode("utf-8")
    if not 0 < len(payload) <= MAX_FRAME:
        raise ValueError("frame size")
    return struct.pack(">II", len(payload), zlib.crc32(payload)) + payload


def frames(raw, torn_ok):
    result, offset = [], 0
    while offset < len(raw):
        if len(raw) - offset < 8:
            if torn_ok:
                return result, offset
            raise Corrupt()
        length, checksum = struct.unpack_from(">II", raw, offset)
        if not 0 < length <= MAX_FRAME:
            raise Corrupt()
        end = offset + 8 + length
        if end > len(raw):
            if torn_ok:
                return result, offset
            raise Corrupt()
        payload = raw[offset + 8:end]
        if zlib.crc32(payload) != checksum:
            raise Corrupt()
        try:
            obj = json.loads(payload.decode("utf-8"),
                             parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        except (ValueError, UnicodeError):
            raise Corrupt() from None
        result.append(obj)
        offset = end
    return result, offset


def valid_record(record):
    if not isinstance(record, dict) or set(record) != {"version", "writes"}:
        raise Corrupt()
    if not integer(record["version"]) or record["version"] <= 0:
        raise Corrupt()
    if not isinstance(record["writes"], list) or not record["writes"]:
        raise Corrupt()
    seen = set()
    for entry in record["writes"]:
        if not isinstance(entry, list) or len(entry) not in (2, 3):
            raise Corrupt()
        if not key(entry[1]) or entry[1] in seen:
            raise Corrupt()
        seen.add(entry[1])
        if not ((entry[0] == "put" and len(entry) == 3) or
                (entry[0] == "delete" and len(entry) == 2)):
            raise Corrupt()


class Store:
    def __init__(self, directory):
        self.path = Path(directory)
        self.path.mkdir(parents=True, exist_ok=True)
        self.lock = open(self.path / "LOCK", "a+b")
        fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.version, self.data, self.last, self.tx = 0, {}, {}, {}
        snap = self.path / "snapshot.bin"
        if snap.exists():
            records, _ = frames(snap.read_bytes(), False)
            if len(records) != 1:
                raise Corrupt()
            r = records[0]
            if (not isinstance(r, dict) or set(r) != {"version", "data"} or
                    not integer(r["version"]) or r["version"] < 0 or
                    not isinstance(r["data"], dict) or not all(map(key, r["data"]))):
                raise Corrupt()
            self.version, self.data = r["version"], r["data"]
        log = self.path / "wal.bin"
        raw = log.read_bytes() if log.exists() else b""
        records, valid_end = frames(raw, True)
        previous = None
        for r in records:
            valid_record(r)
            v = r["version"]
            if previous is not None and v != previous + 1:
                raise Corrupt()
            previous = v
            if v <= self.version:
                continue
            if v != self.version + 1:
                raise Corrupt()
            for entry in r["writes"]:
                if entry[0] == "put":
                    self.data[entry[1]] = entry[2]
                else:
                    self.data.pop(entry[1], None)
            self.version = v
        # Transactions begin only after recovery, so old conflict history is unnecessary.
        self.wal = open(log, "a+b", buffering=0)
        if valid_end < len(raw):
            self.wal.truncate(valid_end)
            os.fsync(self.wal.fileno())
        self.sync_dir()

    def sync_dir(self):
        fd = os.open(self.path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def checkpoint(self):
        if self.tx:
            return {"error": "BUSY"}
        temp = self.path / "snapshot.tmp"
        with open(temp, "wb") as f:
            f.write(encode({"version": self.version, "data": self.data}))
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, self.path / "snapshot.bin")
        self.sync_dir()
        self.wal.truncate(0)
        os.fsync(self.wal.fileno())
        return {"ok": True, "version": self.version}

    def command(self, request):
        op = request["op"]
        if op == "checkpoint":
            return self.checkpoint()
        tid = request["tx"]
        if op == "begin":
            if tid in self.tx:
                return {"error": "EXISTS"}
            self.tx[tid] = {"version": self.version, "snapshot": self.data.copy(),
                            "writes": {}, "reads": set(), "prefixes": set()}
            return {"ok": True, "version": self.version}
        if tid not in self.tx:
            return {"error": "NO_TX"}
        tx = self.tx[tid]
        if op == "abort":
            del self.tx[tid]
            return {"ok": True}
        if op == "commit":
            del self.tx[tid]
            touched = tx["reads"] | tx["writes"].keys()
            for k, version in self.last.items():
                if version > tx["version"] and (k in touched or any(
                        k.startswith(p) for p in tx["prefixes"])):
                    return {"error": "CONFLICT"}
            if tx["writes"]:
                version = self.version + 1
                entries = [["delete", k] if v is DELETED else ["put", k, v]
                           for k, v in tx["writes"].items()]
                payload = encode({"version": version, "writes": entries})
                view = memoryview(payload)
                while view:
                    written = self.wal.write(view)
                    if written is None or written <= 0:
                        raise OSError("short WAL write")
                    view = view[written:]
                os.fsync(self.wal.fileno())
                for k, v in tx["writes"].items():
                    if v is DELETED:
                        self.data.pop(k, None)
                    else:
                        self.data[k] = v
                    self.last[k] = version
                self.version = version
            return {"ok": True, "version": self.version}
        if op in ("put", "delete"):
            tx["writes"][request["key"]] = request["value"] if op == "put" else DELETED
            return {"ok": True}
        if op == "get":
            k = request["key"]
            tx["reads"].add(k)
            v = tx["writes"].get(k, tx["snapshot"].get(k, DELETED))
            return {"found": False} if v is DELETED else {"found": True, "value": v}
        if op == "scan":
            prefix = request["prefix"]
            tx["prefixes"].add(prefix)
            visible = tx["snapshot"] | tx["writes"]
            return {"items": [[k, visible[k]] for k in sorted(visible)
                              if k.startswith(prefix) and visible[k] is not DELETED]}
        raise ValueError("unknown operation")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True)
    args = parser.parse_args()
    try:
        db = Store(args.dir)
    except BlockingIOError:
        print("LOCKED", file=sys.stderr)
        return 2
    except Corrupt:
        print("CORRUPT", file=sys.stderr)
        return 2
    for line in sys.stdin:
        response = db.command(json.loads(line))
        print(json.dumps(response, ensure_ascii=False, allow_nan=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
