"""PostgreSQL persistence for shared outbox and source-event archive."""
import hashlib
import json
from datetime import timedelta, timezone
from pathlib import Path

class PostgresStore:
    def __init__(self, dsn, connect=None):
        self.dsn = dsn
        self._connect = connect
        self.migrate()

    def _connection(self):
        if self._connect is not None:
            return self._connect(self.dsn)
        import psycopg
        return psycopg.connect(self.dsn)

    def migrate(self):
        migration = Path(__file__).with_name("migrations").joinpath("001_initial.sql").read_text()
        with self._connection() as db:
            with db.transaction():
                with db.cursor() as cursor:
                    for statement in migration.split(";"):
                        if statement.strip():
                            cursor.execute(statement)

    def enqueue(self, candidate, now):
        payload = candidate.model_dump(mode="json")
        observed = candidate.observed_at.astimezone(timezone.utc)
        identity = [candidate.symbol, candidate.strategy_version, candidate.direction,
                    observed.replace(second=0, microsecond=0).isoformat()]
        signal_id = hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:24]
        expires = observed + timedelta(seconds=120)
        with self._connection() as db:
            with db.cursor() as cursor:
                cursor.execute("""INSERT INTO signals
                    (id,payload,created_at,expires_at,status,available_at)
                    VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING""",
                    (signal_id, json.dumps(payload), now, expires, "pending", now))
                inserted = cursor.rowcount == 1
        return signal_id, inserted

    def list_signals(self):
        with self._connection() as db:
            with db.cursor() as cursor:
                cursor.execute("""SELECT id,payload,created_at,expires_at,status,attempts,error_code
                    FROM signals ORDER BY created_at DESC LIMIT 100""")
                rows = cursor.fetchall()
        return [{"id": row[0], **json.loads(row[1]), "created_at": row[2].isoformat(),
                 "expires_at": row[3].isoformat(), "status": row[4], "attempts": row[5],
                 "error_code": row[6], "device_delivered": None} for row in rows]

    def claim(self, now):
        with self._connection() as db:
            with db.cursor() as cursor:
                cursor.execute("""UPDATE signals SET status='expired'
                    WHERE status IN ('pending','retry','sending') AND expires_at<=%s""", (now,))
                cursor.execute("""UPDATE signals
                    SET status='delivery_unknown', error_code='worker_interrupted'
                    WHERE status='sending' AND lease_until<=%s""", (now,))
                cursor.execute("""SELECT id,payload,created_at,expires_at,status,attempts,
                    available_at,error_code,lease_until,provider_request_id
                    FROM signals WHERE status IN ('pending','retry') AND available_at<=%s
                    AND attempts<3 ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED""", (now,))
                row = cursor.fetchone()
                if row is None:
                    return None
                cursor.execute("""UPDATE signals SET status='sending', attempts=attempts+1,
                    lease_until=%s WHERE id=%s""", (now + timedelta(seconds=60), row[0]))
        names = ("id", "payload", "created_at", "expires_at", "status", "attempts",
                 "available_at", "error_code", "lease_until", "provider_request_id")
        return dict(zip(names, row))

    def finish(self, signal_id, status, now, error_code=None, provider_request_id=None,
               retry_after_seconds=None):
        with self._connection() as db:
            with db.cursor() as cursor:
                cursor.execute("SELECT attempts FROM signals WHERE id=%s", (signal_id,))
                row = cursor.fetchone()
                if row is None:
                    return
                attempts = row[0]
                if status == "retry" and attempts >= 3:
                    status = "failed"
                delay = retry_after_seconds if retry_after_seconds is not None else 15 * 2 ** attempts
                cursor.execute("""UPDATE signals SET status=%s, available_at=%s,
                    error_code=%s, provider_request_id=%s, lease_until=NULL WHERE id=%s""",
                    (status, now + timedelta(seconds=delay), error_code,
                     provider_request_id, signal_id))

    def record_source_event(self, provider, channel, symbol, payload, received_at):
        if received_at.tzinfo is None or received_at.utcoffset() is None:
            raise ValueError("Source-event receive time must be timezone-aware")
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        identity = hashlib.sha256(
            f"{provider}\0{channel}\0{symbol}\0{serialized}".encode()
        ).hexdigest()
        stamp = received_at.astimezone(timezone.utc)
        with self._connection() as db:
            with db.cursor() as cursor:
                cursor.execute("""INSERT INTO source_events
                    (id,provider,channel,symbol,received_at,first_seen_at,payload)
                    VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING""",
                    (identity, provider, channel, symbol, stamp, stamp, serialized))
                cursor.execute("SELECT first_seen_at FROM source_events WHERE id=%s", (identity,))
                first_seen = cursor.fetchone()[0]
        return {"id": identity, "first_seen_at": first_seen.isoformat()}

    def list_source_events(self, limit=100):
        with self._connection() as db:
            with db.cursor() as cursor:
                cursor.execute("""SELECT id,provider,channel,symbol,received_at,first_seen_at,payload
                    FROM source_events ORDER BY first_seen_at DESC LIMIT %s""", (limit,))
                rows = cursor.fetchall()
        return [{"id": row[0], "provider": row[1], "channel": row[2], "symbol": row[3],
                 "received_at": row[4].isoformat(), "first_seen_at": row[5].isoformat(),
                 "payload": json.loads(row[6])} for row in rows]
