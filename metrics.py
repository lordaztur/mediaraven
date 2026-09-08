"""Contadores thread-safe de downloads por plataforma."""
import threading
import time

_lock = threading.Lock()
_started_at = time.monotonic()
_platforms: dict[str, dict] = {}


def _bucket(platform: str) -> dict:
    return _platforms.setdefault(
        platform, {'success': 0, 'failure': 0, 'multilang': 0, 'total_duration_s': 0.0},
    )


def record_success(platform: str, duration_s: float) -> None:
    with _lock:
        b = _bucket(platform)
        b['success'] += 1
        b['total_duration_s'] += duration_s


def record_failure(platform: str, duration_s: float) -> None:
    with _lock:
        b = _bucket(platform)
        b['failure'] += 1
        b['total_duration_s'] += duration_s


def record_multilang(platform: str) -> None:
    with _lock:
        _bucket(platform)['multilang'] += 1


def snapshot() -> dict:
    with _lock:
        platforms = {}
        for name, b in _platforms.items():
            completed = b['success'] + b['failure']
            platforms[name] = {
                'success': b['success'],
                'failure': b['failure'],
                'multilang': b['multilang'],
                'total': completed + b['multilang'],
                'avg_duration_s': round(b['total_duration_s'] / completed, 2) if completed else 0.0,
            }
        return {'uptime_s': time.monotonic() - _started_at, 'platforms': platforms}


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
