# Ledger recovery engine

Implement `/app/store.py`, a Python 3.12 standard-library-only transactional
key/value database. Do not use SQLite, another database, external services or
third-party dependencies. Your program runs as:

```
python /app/store.py --dir /path/to/database
```

Read one JSON object per stdin line and immediately flush exactly one JSON
response per line to stdout. Diagnostics belong on stderr. A clean EOF exits
with status 0 and discards uncommitted transactions. Database directories are
fresh or were previously written using this specification. There is one writer
process; multiple transactions may be interleaved within that process. A second
process opening the same directory must exit 2 with `LOCKED` on stderr without
changing persistent files. Use an exclusive nonblocking advisory lock on `LOCK`.

## Protocol

Transaction IDs and keys are arbitrary nonempty Unicode strings. Values are any
JSON value, including null, nested objects, arrays, booleans and numbers. Valid
requests have exactly the documented fields; malformed requests are out of scope.
JSON object field order and whitespace are immaterial.

| Request | Response |
| --- | --- |
| `{"op":"begin","tx":"a"}` | `{"ok":true,"version":V}` |
| `{"op":"put","tx":"a","key":"k","value":42}` | `{"ok":true}` |
| `{"op":"delete","tx":"a","key":"k"}` | `{"ok":true}` |
| `{"op":"get","tx":"a","key":"k"}` | `{"found":true,"value":42}` or `{"found":false}` |
| `{"op":"scan","tx":"a","prefix":"p"}` | `{"items":[["p1",42],["p2",null]]}` |
| `{"op":"commit","tx":"a"}` | `{"ok":true,"version":V}` or `{"error":"CONFLICT"}` |
| `{"op":"abort","tx":"a"}` | `{"ok":true}` |
| `{"op":"checkpoint"}` | `{"ok":true,"version":V}` or `{"error":"BUSY"}` |

Starting an already active ID returns `{"error":"EXISTS"}`. A transaction
operation for an inactive ID returns `{"error":"NO_TX"}`. Both are nonfatal and
leave all other state unchanged. IDs can be reused after commit or abort.

## Isolation and conflict semantics

The initial committed version is zero. Begin captures the current committed
state and version. Reads see that snapshot plus the transaction's own writes;
other commits never change an existing transaction's reads. Delete hides a key,
including one written earlier in the same transaction. A null value is present,
not a deletion. Scan returns all visible prefix matches sorted by Python's
Unicode string order. Empty prefix means all keys.

On commit, reject if *any* key read or written by that transaction has been
written by another committed transaction since its snapshot. Also reject if any
key matching any scanned prefix has been written since its snapshot. This
includes keys created and subsequently deleted, deletes of absent keys, and
writes that restore the original value. A rejected transaction is closed and
has no effect. This deliberately conservative validation prevents write skew
and phantom reads. Disjoint transactions can commit successfully.

A successful transaction with at least one put/delete increments the global
version by exactly one, atomically applies its final write set, and makes it
durable before responding. Read-only commits validate too, but do not increment
the version or append a log record. Abort does neither. A checkpoint is BUSY
while any transaction is active and must not change those transactions.

## Disk format (part of the public interface)

Use `wal.bin` for committed transactions and `snapshot.bin` for checkpoints.
Each file consists of frames. A frame is a 4-byte unsigned big-endian payload
length, a 4-byte unsigned big-endian CRC32 of the payload, then that many bytes
of UTF-8 JSON. Use zlib.crc32; maximum payload length is 16 MiB, minimum 1 byte.
No magic prefix. The snapshot contains exactly one frame:

```
{"version":7,"data":{"key":"value","nullable":null}}
```

Each WAL frame represents one committed write transaction:

```
{"version":8,"writes":[["put","key",123],["delete","old"]]}
```

Each key appears once per record, reflecting its final staged operation. Write
order is immaterial. Versions in the WAL must be strictly consecutive positive
integers. If a snapshot exists, the WAL may still contain a consecutive suffix
of old records ending at the snapshot version (checkpoint interrupted before
log truncation). Skip records already covered by the snapshot. The first record
newer than the snapshot must have version snapshot+1. Without a snapshot, the
first WAL record must have version 1. Empty WAL is allowed.

At startup, a partial final WAL header or payload is an interrupted append:
discard that incomplete frame, truncate the file to the last complete frame and
fsync it before accepting commands. A complete bad checksum, invalid length,
malformed JSON, wrong record shape, duplicate write keys, invalid operation or
version gap is corruption: exit 2, print `CORRUPT` on stderr and do not change
the WAL or snapshot. Validate the whole log before repairing a torn tail.
Any incomplete, invalid or extra snapshot frame is corruption, never a torn-tail
repair. Missing WAL/snapshot files mean an empty WAL/no checkpoint respectively.

Checkpoint must persist a new snapshot with a temporary file, fsync, atomic
rename and directory fsync *before* truncating and fsyncing the WAL. Afterwards
the WAL must be zero bytes. Leftover temporary files are ignored on recovery.
No active transactions survive a process restart. fsync committed WAL records
before acknowledging them. SIGKILL after an acknowledgment must not lose that
commit. Recovery must tolerate any prefix truncation of a final WAL frame.

## Example

Input:
```
{"op":"begin","tx":"a"}
{"op":"put","tx":"a","key":"balance","value":100}
{"op":"commit","tx":"a"}
{"op":"begin","tx":"b"}
{"op":"get","tx":"b","key":"balance"}
```

Output:
```
{"ok":true,"version":0}
{"ok":true}
{"ok":true,"version":1}
{"ok":true,"version":1}
{"found":true,"value":100}
```

Evaluation exercises transactions, predicate conflicts, persistence, truncated
frames, corruption refusal, checkpoint crash windows, process locking and
deterministic randomized histories. Workloads are modest (hundreds of keys and
transactions); a snapshot copy at begin is acceptable. No throughput target is
implied. Change or add files under `/app` only.
