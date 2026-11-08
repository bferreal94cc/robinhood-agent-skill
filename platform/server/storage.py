"""Single-host development persistence. Use PostgreSQL before replicated deployment."""
import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .models import Candidate


def utcnow():
    return datetime.now(timezone.utc)


class Store:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS signals (
                id TEXT PRIMARY KEY, payload TEXT NOT NULL, created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL, status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                available_at TEXT NOT NULL, error_code TEXT, lease_until TEXT,
                provider_request_id TEXT)""")
            db.execute("""CREATE TABLE IF NOT EXISTS source_events (
                id TEXT PRIMARY KEY, provider TEXT NOT NULL, channel TEXT NOT NULL,
                symbol TEXT NOT NULL, received_at TEXT NOT NULL, first_seen_at TEXT NOT NULL,
                payload TEXT NOT NULL)""")

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def enqueue(self, candidate: Candidate, now: datetime):
        payload = candidate.model_dump(mode="json")
        # One alert per symbol/strategy/direction/observation minute, even across retries.
        identity = [candidate.symbol, candidate.strategy_version, candidate.direction,
                    candidate.observed_at.astimezone(timezone.utc).replace(second=0, microsecond=0).isoformat()]
        signal_id = hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:24]
        expires = candidate.observed_at.astimezone(timezone.utc) + timedelta(seconds=120)
        with self.connection() as db:
            result = db.execute("""INSERT OR IGNORE INTO signals
                (id,payload,created_at,expires_at,status,available_at) VALUES (?,?,?,?,?,?)""",
                (signal_id, json.dumps(payload), now.isoformat(), expires.isoformat(), "pending", now.isoformat()))
            inserted = result.rowcount == 1
        return signal_id, inserted

    def list_signals(self):
        with self.connection() as db:
            rows = db.execute("SELECT * FROM signals ORDER BY created_at DESC LIMIT 100").fetchall()
        return [{"id": row["id"], **json.loads(row["payload"]), "created_at": row["created_at"],
                 "expires_at": row["expires_at"], "status": row["status"], "attempts": row["attempts"],
                 "error_code": row["error_code"], "device_delivered": None} for row in rows]

    def claim(self, now: datetime):
        stamp = now.isoformat()
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("UPDATE signals SET status='expired' WHERE status IN ('pending','retry','sending') AND expires_at<=?", (stamp,))
            # A crashed/uncertain send must not be blindly resent: provider may have accepted it.
            db.execute("UPDATE signals SET status='delivery_unknown', error_code='worker_interrupted' WHERE status='sending' AND lease_until<=?", (stamp,))
            row = db.execute("""SELECT * FROM signals WHERE status IN ('pending','retry')
                AND available_at<=? AND attempts<3 ORDER BY created_at LIMIT 1""", (stamp,)).fetchone()
            if row:
                db.execute("UPDATE signals SET status='sending', attempts=attempts+1, lease_until=? WHERE id=?",
                           ((now + timedelta(seconds=60)).isoformat(), row["id"]))
                return dict(row)
        return None

    def finish(self, signal_id, status, now, error_code=None, provider_request_id=None, retry_after_seconds=None):
        with self.connection() as db:
            row = db.execute("SELECT attempts FROM signals WHERE id=?", (signal_id,)).fetchone()
            if row is None:
                return
            if status == "retry" and row["attempts"] >= 3:
                status = "failed"
            db.execute("""UPDATE signals SET status=?, available_at=?, error_code=?,
                provider_request_id=?, lease_until=NULL WHERE id=?""",
                (status, (now + timedelta(seconds=retry_after_seconds if retry_after_seconds is not None else 15 * 2 ** row["attempts"])).isoformat(),
                 error_code, provider_request_id, signal_id))

    def record_source_event(self, provider, channel, symbol, payload, received_at):
        if received_at.tzinfo is None or received_at.utcoffset() is None:
            raise ValueError("Source-event receive time must be timezone-aware")
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        identity = hashlib.sha256(
            f"{provider}\0{channel}\0{symbol}\0{serialized}".encode()
        ).hexdigest()
        stamp = received_at.astimezone(timezone.utc).isoformat()
        with self.connection() as db:
            db.execute("""INSERT OR IGNORE INTO source_events
                (id,provider,channel,symbol,received_at,first_seen_at,payload)
                VALUES (?,?,?,?,?,?,?)""",
                (identity, provider, channel, symbol, stamp, stamp, serialized))
            row = db.execute("SELECT first_seen_at FROM source_events WHERE id=?", (identity,)).fetchone()
        return {"id": identity, "first_seen_at": row["first_seen_at"]}

    def list_source_events(self, limit=100):
        with self.connection() as db:
            rows = db.execute(
                "SELECT * FROM source_events ORDER BY first_seen_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [{**dict(row), "payload": json.loads(row["payload"])} for row in rows]


def create_store(settings):
    if settings.database_url:
        from .postgres import PostgresStore
        return PostgresStore(settings.database_url)
    return Store(settings.database_path)
