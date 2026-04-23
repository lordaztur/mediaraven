"""Testes do módulo de métricas."""
import metrics


def setup_function():
    # Reset do estado global entre testes.
    metrics._metrics.platforms.clear()


def test_record_success_increments():
    metrics.record_success('youtube', 1.5)
    metrics.record_success('youtube', 2.5)
    snap = metrics.snapshot()
    assert snap['platforms']['youtube']['success'] == 2
    assert snap['platforms']['youtube']['failure'] == 0
    assert snap['platforms']['youtube']['avg_duration_s'] == 2.0


def test_record_failure_and_multilang_coexist():
    metrics.record_failure('reddit', 3.0)
    metrics.record_multilang('youtube')
    snap = metrics.snapshot()
    assert snap['platforms']['reddit']['failure'] == 1
    assert snap['platforms']['youtube']['multilang'] == 1
    assert snap['platforms']['youtube']['total'] == 1


def test_avg_duration_ignores_multilang():
    """multilang não entra no cálculo de duração média (não tem sentido)."""
    metrics.record_success('x', 4.0)
    metrics.record_multilang('x')
    snap = metrics.snapshot()
    assert snap['platforms']['x']['avg_duration_s'] == 4.0


def test_format_summary_empty():
    out = metrics.format_summary()
    assert "sem downloads" in out.lower()


def test_format_summary_with_data():
    metrics.record_success('youtube', 10.0)
    metrics.record_failure('reddit', 5.0)
    out = metrics.format_summary()
    assert "youtube" in out
    assert "reddit" in out
    assert "ok=1" in out


def test_snapshot_is_copy_not_reference():
    """snapshot deve isolar o estado interno — mutar o snapshot não afeta o real."""
    metrics.record_success('y', 1.0)
    snap = metrics.snapshot()
    snap['platforms']['y']['success'] = 999
    assert metrics.snapshot()['platforms']['y']['success'] == 1
