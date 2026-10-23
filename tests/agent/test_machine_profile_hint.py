"""The stored machine-profile summary rides along in the environment hints block."""

from __future__ import annotations

from agent.prompt_builder import build_environment_hints
from hermes_constants import get_hermes_home


def test_environment_hints_include_stored_machine_summary() -> None:
    home = get_hermes_home()
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.yaml").write_text(
        "machine:\n"
        "  tier: T2\n"
        "  summary: \"Machine: T2 (roomy) · 4 cores · 16.0G RAM · GPU: none · profile probed 2026-01-01\"\n",
        encoding="utf-8",
    )
    hints = build_environment_hints()
    assert "Machine: T2 (roomy)" in hints


def test_environment_hints_have_no_machine_line_without_a_profile() -> None:
    # Same session home as the test above: overwrite its config with one that
    # carries no probed profile, so the merged machine section stays empty.
    home = get_hermes_home()
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.yaml").write_text("# no machine profile\n", encoding="utf-8")
    hints = build_environment_hints()
    assert "Machine: " not in hints
