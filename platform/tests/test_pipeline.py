import asyncio
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from server.exchange_calendar import XNYSCalendar
from server.market_data import SourceObservation, SourceRequirement, source_rejection_reasons
from server.storage import Store
from server.strategy import StrategyVersion, evaluate_readiness
from server.unusual_whales import CHANNELS, UnusualWhalesCollector, UnusualWhalesREST


FIXTURES = Path(__file__).parent / "fixtures"


class ReplaySocket:
    def __init__(self, frames, stop_event):
        self.frames = list(frames)
        self.index = 0
        self.stop_event = stop_event
        self.sent = []

    async def send(self, value):
        self.sent.append(json.loads(value))

    async def recv(self):
        if self.index >= len(self.frames):
            await asyncio.sleep(10)
            raise AssertionError("Unexpected replay receive")
        frame = self.frames[self.index]
        self.index += 1
        if self.index == len(self.frames):
            self.stop_event.set()
        return frame


class SocketContext:
    def __init__(self, socket):
        self.socket = socket

    async def __aenter__(self):
        return self.socket

    async def __aexit__(self, *_):
        return False


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.store = Store(str(Path(self.folder.name) / "pipeline.sqlite"))
        self.now = datetime(2026, 11, 6, 16, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self.folder.cleanup()

    def test_rest_adapter_uses_allowlisted_routes_and_bearer_auth(self):
        requests = []

        async def handler(request):
            requests.append(request)
            return httpx.Response(200, json={"data": []})

        async def run():
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                adapter = UnusualWhalesREST("fixture-token", client)
                self.assertEqual(await adapter.fetch("SPY", "greek_exposure"), {"data": []})
                with self.assertRaises(ValueError):
                    await adapter.fetch("AAPL", "greek_exposure")
                with self.assertRaises(ValueError):
                    await adapter.fetch("SPY", "unknown")

        asyncio.run(run())
        self.assertEqual(requests[0].url.path, "/api/stock/SPY/greek-exposure/strike")
        self.assertEqual(requests[0].headers["authorization"], "Bearer " + "fixture-token")

    def test_rest_adapter_limits_concurrency(self):
        active = 0
        maximum = 0

        async def handler(_request):
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            await asyncio.sleep(0.01)
            active -= 1
            return httpx.Response(200, json=[])

        async def run():
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                adapter = UnusualWhalesREST("fixture-token", client, max_concurrency=3)
                await asyncio.gather(*(
                    adapter.fetch(symbol, "net_premium")
                    for symbol in ("SPY", "QQQ", "SPY", "QQQ", "SPY")
                ))

        asyncio.run(run())
        self.assertLessEqual(maximum, 3)

    def test_rest_collection_archives_first_seen_snapshot(self):
        requests = []

        async def handler(request):
            requests.append(request)
            return httpx.Response(200, json={"fixture_only": True, "data": []})

        stamps = [self.now]

        async def run():
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                adapter = UnusualWhalesREST(
                    "fixture-token", client, archive=self.store, clock=lambda: stamps[0]
                )
                first = await adapter.collect("QQQ", "net_premium")
                stamps[0] += timedelta(minutes=1)
                second = await adapter.collect("QQQ", "net_premium")
                return first, second

        first, second = asyncio.run(run())
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(first["first_seen_at"], second["first_seen_at"])
        self.assertEqual(requests[0].url.path, "/api/stock/QQQ/net-prem-ticks")

    def test_replay_archives_only_verified_channels_and_keeps_first_seen(self):
        fixture_path = FIXTURES / "unusual_whales_replay.jsonl"
        frames = [line for line in fixture_path.read_text().splitlines()]
        stop = asyncio.Event()
        socket = ReplaySocket(frames, stop)

        def connect(*_args, **_kwargs):
            return SocketContext(socket)

        collector = UnusualWhalesCollector(
            "fixture-token", self.store, connect=connect, clock=lambda: self.now
        )
        asyncio.run(collector.run(stop))
        self.assertEqual([item["channel"] for item in socket.sent], list(CHANNELS))
        archived = self.store.list_source_events()
        self.assertEqual({row["symbol"] for row in archived}, {"SPY", "QQQ"})
        first_seen = archived[0]["first_seen_at"]
        replayed = self.store.record_source_event(
            "unusual_whales", archived[0]["channel"], archived[0]["symbol"],
            archived[0]["payload"], self.now + timedelta(minutes=2),
        )
        self.assertEqual(replayed["first_seen_at"], first_seen)

    def test_reconnects_and_gap_reconciliation_are_bounded(self):
        attempts, delays, recoveries = 0, [], []

        def connect(*_args, **_kwargs):
            nonlocal attempts
            attempts += 1
            raise OSError("network failure")

        async def sleep(delay):
            delays.append(delay)

        async def reconcile(symbol, last_seen):
            recoveries.append((symbol, last_seen))

        collector = UnusualWhalesCollector(
            "fixture-token", self.store, connect=connect, sleep=sleep,
            max_reconnects=1, backoff_base=2, backoff_max=5,
        )
        asyncio.run(collector.run(asyncio.Event(), reconcile))
        self.assertEqual(attempts, 2)
        self.assertEqual(delays, [2])
        self.assertEqual(len(recoveries), 4)
        self.assertEqual(collector.gap_count, 2)
        self.assertEqual(collector.last_error, "OSError")

    def test_source_quality_requires_fresh_live_complete_and_verified_data(self):
        requirement = SourceRequirement(
            source="uw_gex", max_age_seconds=30, entitlement="advanced"
        )
        observation = SourceObservation(
            source_id="fixture-1", source="uw_gex", symbol="SPY",
            event_at=self.now - timedelta(seconds=10), first_seen_at=self.now,
            mode="live", entitlement="advanced", entitlement_verified=True, complete=True,
        )
        self.assertEqual(source_rejection_reasons([requirement], {"uw_gex": observation}, "SPY", self.now), [])
        stale = observation.model_copy(update={"event_at": self.now - timedelta(seconds=31)})
        self.assertIn("stale_source_uw_gex", source_rejection_reasons(
            [requirement], {"uw_gex": stale}, "SPY", self.now
        ))
        unverified = observation.model_copy(update={"entitlement_verified": False})
        self.assertIn("unverified_entitlement_uw_gex", source_rejection_reasons(
            [requirement], {"uw_gex": unverified}, "SPY", self.now
        ))
        mislabeled = observation.model_copy(update={"source": "other_provider"})
        self.assertIn("wrong_source_uw_gex", source_rejection_reasons(
            [requirement], {"uw_gex": mislabeled}, "SPY", self.now
        ))

    def test_xnys_calendar_observes_holiday_and_early_close(self):
        calendar = XNYSCalendar()
        self.assertFalse(calendar.is_open(datetime(2026, 11, 26, 16, 0, tzinfo=timezone.utc)))
        self.assertTrue(calendar.is_open(datetime(2026, 11, 27, 17, 0, tzinfo=timezone.utc)))
        self.assertFalse(calendar.is_open(datetime(2026, 11, 27, 18, 30, tzinfo=timezone.utc)))
        with self.assertRaises(ValueError):
            calendar.is_open(datetime(2026, 11, 27, 17, 0))

    def test_versioned_readiness_never_emits_a_signal_without_rules(self):
        digest = "a" * 64
        strategy = StrategyVersion(
            version="review-only-v1", definition_hash=digest, approved_hash=digest,
            requirements=(), enabled=True,
        )

        class OpenCalendar:
            def is_open(self, _at):
                return True

        result = evaluate_readiness(strategy, "SPY", {}, self.now, OpenCalendar())
        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.reasons, ("strategy_rules_not_configured",))
        self.assertEqual(result.strategy_version, "review-only-v1")


if __name__ == "__main__":
    unittest.main()
