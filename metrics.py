"""Contadores thread-safe de downloads por plataforma."""
import logging
import threading
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class _PlatformStats:
    success: int = 0
    failure: int = 0
    multilang: int = 0
    total_duration_s: float = 0.0

    @property
    def total(self) -> int:
        return self.success + self.failure + self.multilang

    @property
    def avg_duration_s(self) -> float:
        completed = self.success + self.failure
        return (self.total_duration_s / completed) if completed else 0.0


@dataclass
class _Metrics:
    platforms: dict = field(default_factory=dict)
    started_at: float = field(default_factory=time.monotonic)


_lock = threading.Lock()
_metrics = _Metrics()


def _bucket(platform: str) -> _PlatformStats:
    stats = _metrics.platforms.get(platform)
    if stats is None:
        stats = _PlatformStats()
        _metrics.platforms[platform] = stats
    return stats


def record_success(platform: str, duration_s: float) -> None:
    with _lock:
        stats = _bucket(platform)
        stats.success += 1
        stats.total_duration_s += duration_s


def record_failure(platform: str, duration_s: float) -> None:
    with _lock:
        stats = _bucket(platform)
        stats.failure += 1
        stats.total_duration_s += duration_s


def record_multilang(platform: str) -> None:
    with _lock:
        _bucket(platform).multilang += 1


def snapshot() -> dict:
    with _lock:
        return {
            'uptime_s': time.monotonic() - _metrics.started_at,
            'platforms': {
                name: {
                    'success': s.success,
                    'failure': s.failure,
                    'multilang': s.multilang,
                    'total': s.total,
                    'avg_duration_s': round(s.avg_duration_s, 2),
                }
                for name, s in _metrics.platforms.items()
            },
        }


def format_summary() -> str:
    snap = snapshot()
    uptime_h = snap['uptime_s'] / 3600
    if not snap['platforms']:
        return f"📊 Métricas: sem downloads nas últimas {uptime_h:.1f}h."
    parts = [f"📊 Métricas (uptime {uptime_h:.1f}h):"]
    for name, s in sorted(snap['platforms'].items()):
        parts.append(
            f"  {name}: ok={s['success']} fail={s['failure']} ml={s['multilang']} "
            f"total={s['total']} avg={s['avg_duration_s']}s"
        )
    return "\n".join(parts)
