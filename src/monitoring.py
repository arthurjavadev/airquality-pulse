"""Lightweight process-local HTTP request instrumentation using Prometheus."""

from collections import deque
from threading import Lock
from time import monotonic

from prometheus_client import CollectorRegistry, Counter, Gauge


class RequestMetrics:
    """Total application requests and rolling-window requests per second.

    Each process has its own counters. The HTTP JSON output is intended for
    this course MVP; multi-worker deployments need metrics aggregation.
    """

    def __init__(self, window_seconds=60, clock=monotonic):
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")

        self.window_seconds = window_seconds
        self._clock = clock
        self._lock = Lock()
        self._recent_requests = deque()
        self._total = 0

        self.registry = CollectorRegistry()
        self._total_counter = Counter(
            "airquality_http_requests",
            "Total non-metrics HTTP requests served by this process",
            registry=self.registry,
        )
        self._rate_gauge = Gauge(
            "airquality_http_requests_per_second",
            "Request rate calculated over a rolling time window",
            registry=self.registry,
        )

    def _expire_old_requests(self, now):
        cutoff = now - self.window_seconds
        while self._recent_requests and self._recent_requests[0] <= cutoff:
            self._recent_requests.popleft()

    def record_request(self):
        """Record a completed application request."""
        with self._lock:
            now = self._clock()
            self._recent_requests.append(now)
            self._total += 1
            self._total_counter.inc()
            self._expire_old_requests(now)
            self._rate_gauge.set(len(self._recent_requests) / self.window_seconds)

    def snapshot(self):
        """Return JSON-serializable metrics and refresh the gauge on idle."""
        with self._lock:
            self._expire_old_requests(self._clock())
            rate = len(self._recent_requests) / self.window_seconds
            self._rate_gauge.set(rate)
            return {
                "status": "ok",
                "requests_total": self._total,
                "requests_per_second": round(rate, 4),
                "window_seconds": self.window_seconds,
                "unit": "requests/second",
            }
