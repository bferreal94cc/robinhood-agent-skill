"""Read-only Unusual Whales REST and WebSocket collection."""
import asyncio
import json
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx
import websockets

SUPPORTED_SYMBOLS = ("SPY", "QQQ")
CHANNELS = {f"gex_strike:{symbol}": symbol for symbol in SUPPORTED_SYMBOLS}
REST_RESOURCES = {
    "ohlc": "/api/stock/{symbol}/ohlc/{candle_size}",
    "net_premium": "/api/stock/{symbol}/net-prem-ticks",
    "greek_exposure": "/api/stock/{symbol}/greek-exposure/strike",
}


class ProviderError(RuntimeError):
    pass


class UnusualWhalesREST:
    def __init__(self, token, client=None, max_concurrency=3, archive=None, clock=None):
        if not token:
            raise ValueError("An Unusual Whales API token is required")
        if not 1 <= max_concurrency <= 3:
            raise ValueError("Concurrency must be between one and three requests")
        self._token = token
        self._client = client
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._archive = archive
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def fetch(self, symbol, resource, params=None, candle_size="1m"):
        if symbol not in SUPPORTED_SYMBOLS:
            raise ValueError("Only SPY and QQQ are supported")
        if resource not in REST_RESOURCES:
            raise ValueError("Unsupported Unusual Whales resource")
        if candle_size not in {"1m", "5m", "15m", "30m", "1h", "1d"}:
            raise ValueError("Unsupported candle size")
        path = REST_RESOURCES[resource].format(symbol=symbol, candle_size=candle_size)
        url = f"https://api.unusualwhales.com{path}"
        async with self._semaphore:
            if self._client is not None:
                response = await self._client.get(
                    url, headers={"Authorization": "Bearer " + self._token}, params=params
                )
            else:
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.get(
                        url, headers={"Authorization": "Bearer " + self._token}, params=params
                    )
        if response.is_error:
            raise ProviderError(f"Unusual Whales REST request failed ({response.status_code})")
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderError("Unusual Whales returned invalid JSON") from exc
        if not isinstance(payload, (dict, list)):
            raise ProviderError("Unusual Whales returned an unsupported payload")
        return payload

    async def collect(self, symbol, resource, params=None, candle_size="1m"):
        if self._archive is None:
            raise RuntimeError("A source-event archive is required for collection")
        payload = await self.fetch(symbol, resource, params, candle_size)
        archived = self._archive.record_source_event(
            "unusual_whales", f"rest:{resource}", symbol, payload, self._clock()
        )
        return {"payload": payload, **archived}


class UnusualWhalesCollector:
    def __init__(self, token, archive, connect=None, clock=None, sleep=None,
                 heartbeat_timeout=45, max_reconnects=5, backoff_base=1, backoff_max=30):
        if not token:
            raise ValueError("An Unusual Whales API token is required")
        if heartbeat_timeout <= 0 or max_reconnects < 0 or backoff_base <= 0 or backoff_max <= 0:
            raise ValueError("Collector limits must be positive")
        self._token = token
        self._archive = archive
        self._connect = connect or websockets.connect
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._sleep = sleep or asyncio.sleep
        self.heartbeat_timeout = heartbeat_timeout
        self.max_reconnects = max_reconnects
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max
        self.gap_count = 0
        self.recovery_failures = 0
        self.last_error = None

    def _url(self):
        return f"wss://api.unusualwhales.com/socket?{urlencode({'token': self._token})}"

    async def run(self, stop_event, reconcile=None):
        reconnects = 0
        last_seen = {symbol: None for symbol in SUPPORTED_SYMBOLS}
        while not stop_event.is_set():
            try:
                async with self._connect(
                    self._url(), open_timeout=10, ping_interval=20, ping_timeout=20,
                    max_size=1_048_576, user_agent_header="spybot-alert-platform/0.1",
                ) as socket:
                    for channel in CHANNELS:
                        await socket.send(json.dumps({"channel": channel, "msg_type": "join"}))
                    await self._receive(socket, stop_event, last_seen)
                if stop_event.is_set():
                    return
                self.last_error = "stream_closed"
            except Exception as exc:
                self.last_error = type(exc).__name__

            if stop_event.is_set():
                return
            self.gap_count += 1
            if reconcile is not None:
                for symbol in SUPPORTED_SYMBOLS:
                    try:
                        await reconcile(symbol, last_seen[symbol])
                    except Exception:
                        self.recovery_failures += 1
            if reconnects >= self.max_reconnects:
                return
            delay = min(self.backoff_base * (2 ** reconnects), self.backoff_max)
            reconnects += 1
            await self._sleep(delay)

    async def _receive(self, socket, stop_event, last_seen):
        while not stop_event.is_set():
            try:
                message = await asyncio.wait_for(socket.recv(), timeout=self.heartbeat_timeout)
            except asyncio.TimeoutError:
                raise ProviderError("Unusual Whales stream heartbeat timed out") from None
            try:
                payload = json.loads(message)
            except (TypeError, ValueError):
                continue
            if not isinstance(payload, dict):
                continue
            message_type = payload.get("msg_type")
            if isinstance(message_type, str) and message_type.lower() in {"heartbeat", "pong"}:
                continue
            channel = payload.get("channel")
            symbol = CHANNELS.get(channel)
            if symbol is None:
                continue
            received_at = self._clock()
            self._archive.record_source_event(
                "unusual_whales", channel, symbol, payload, received_at
            )
            last_seen[symbol] = received_at
