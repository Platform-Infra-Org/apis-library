"""Uptime metric background task."""

import asyncio
import time

from prometheus_client import Gauge

_start_time = time.time()

UPTIME = Gauge("app_uptime_seconds", "Application uptime in seconds")
UPTIME.set_function(lambda: time.time() - _start_time)

