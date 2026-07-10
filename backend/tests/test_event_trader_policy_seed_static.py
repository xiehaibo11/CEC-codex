"""The one-time legacy trader cleanup must be explicit and non-destructive."""

from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "disable_legacy_event_traders.py"


def test_legacy_cleanup_is_dry_run_by_default_and_apply_is_explicit():
    source = SCRIPT.read_text()

    assert "--apply" in source
    assert "dry_run" in source
    assert "--apply is required" in source
    assert 'signal_mode in {"range_boundary", "exhaustion_fade"}' in source


def test_legacy_cleanup_does_not_delete_bets_or_enable_new_traders():
    source = SCRIPT.read_text()

    assert "DELETE" not in source.upper()
    assert "enabled = False" in source
    assert "enabled = True" not in source
    assert "allow_unvalidated" not in source
