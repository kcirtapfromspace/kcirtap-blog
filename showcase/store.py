"""Private append-only journal and content-addressed originals (stdlib only)."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
from datetime import datetime, timezone


class GateError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else canonical(value)).hexdigest()


def require(condition, message):
    if not condition:
        raise GateError(message)


def now():
    return datetime.now(timezone.utc).isoformat()


def outside_git(path):
    path = Path(path).expanduser().resolve()
    for parent in [path, *path.parents]:
        require(not (parent / ".git").exists(), "Private state and trust files must be outside ALL Git trees")
    return path


class Store:
    def __init__(self, root):
        self.root = outside_git(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.root, 0o700)
        self.blobs = self.root / "objects"
        require(not self.blobs.is_symlink() and not (self.root / "journal.sqlite3").is_symlink(), "Private store paths cannot be symlinks")
        self.blobs.mkdir(mode=0o700, exist_ok=True)
        self.db = sqlite3.connect(self.root / "journal.sqlite3", timeout=30)
        os.chmod(self.root / "journal.sqlite3", 0o600)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS events (
          seq INTEGER PRIMARY KEY, kind TEXT NOT NULL, task TEXT NOT NULL,
          payload TEXT NOT NULL, previous TEXT NOT NULL, hash TEXT NOT NULL UNIQUE
        );
        CREATE TRIGGER IF NOT EXISTS immutable_update BEFORE UPDATE ON events
          BEGIN SELECT RAISE(ABORT, 'events are immutable'); END;
        CREATE TRIGGER IF NOT EXISTS immutable_delete BEFORE DELETE ON events
          BEGIN SELECT RAISE(ABORT, 'events are immutable'); END;
        ''')

    def put(self, data):
        if not isinstance(data, bytes):
            data = canonical(data)
        key = digest(data)
        path = self.blobs / key
        require(not path.is_symlink(), "Private objects cannot be symlinks")
        if not path.exists():
            try:
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as stream:
                    stream.write(data)
            except FileExistsError:
                pass
        require(path.read_bytes() == data, "Object integrity failure")
        return key

    def get(self, key):
        require(len(key) == 64 and all(c in '0123456789abcdef' for c in key), "Invalid object hash")
        require(not (self.blobs / key).is_symlink(), "Private objects cannot be symlinks")
        data = (self.blobs / key).read_bytes()
        require(digest(data) == key, "Object hash changed")
        return data

    def events(self, task=None, kind=None):
        result = []
        previous = "0" * 64
        for seq, k, t, p, prev, h in self.db.execute("SELECT * FROM events ORDER BY seq"):
            require(prev == previous and h == digest({"kind": k, "task": t, "payload": json.loads(p), "previous": prev}), "Journal integrity failure")
            previous = h
            if (task is None or task == t) and (kind is None or kind == k):
                result.append({"seq": seq, "kind": k, "task": t, "payload": json.loads(p), "hash": h})
        return result

    def append(self, kind, task, payload, expected_previous="ANY"):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            if expected_previous != "ANY":
                previous_action = self.db.execute("SELECT hash FROM events WHERE kind=? AND task=? ORDER BY seq DESC LIMIT 1", (kind, task)).fetchone()
                require((previous_action[0] if previous_action else None) == expected_previous, "Signed correction lost a concurrent update; preserve and re-review it")
            self.events()  # verify the chain before extending it
            row = self.db.execute("SELECT hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
            previous = row[0] if row else "0" * 64
            value = {"kind": kind, "task": task, "payload": payload, "previous": previous}
            key = digest(value)
            self.db.execute("INSERT INTO events(kind, task, payload, previous, hash) VALUES(?,?,?,?,?)", (kind, task, canonical(payload).decode(), previous, key))
            self.db.commit()
            return key
        except Exception:
            self.db.rollback()
            raise

    def latest(self, task, kind):
        events = self.events(task, kind)
        return events[-1]["payload"] if events else None


def verify_owner(envelope, signers):
    """A person signs the EXACT canonical payload with ssh-keygen -Y sign.

    Trust is an operator-installed file outside Git; the author cannot change it
    in a PR. No signing operation is provided to agents or HTTP clients.
    """
    import tempfile
    signers = outside_git(signers)
    payload = envelope["payload"]
    require(payload.get("actor") == "owner", "Only an owner may approve")
    require(bool(payload.get("at")), "Signed action needs a timestamp")
    with tempfile.TemporaryDirectory() as tmp:
        sig = Path(tmp) / "signature"
        sig.write_text(envelope["signature"])
        result = subprocess.run([
            "ssh-keygen", "-Y", "verify", "-f", str(signers), "-I", "owner",
            "-n", "kcirtap-showcase", "-s", str(sig)
        ], input=canonical(payload), capture_output=True)
    require(result.returncode == 0, "Missing or invalid owner signature")
    return payload
