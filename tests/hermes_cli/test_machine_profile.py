"""Machine profile: tier classification boundaries, probe persistence, prompt summary."""

from __future__ import annotations

import pytest

from hermes_cli.machine_profile import (
    classify_tier, format_summary, load_machine_profile, run_machine_probe,
)
from hermes_constants import get_hermes_home

_GIB = 2**30


@pytest.mark.parametrize(("cores", "ram", "vram", "expected"), [
    (1, 16 * _GIB, 16 * _GIB, "T0"),    # core floor beats RAM and GPU
    (8, 1 * _GIB, 16 * _GIB, "T0"),     # RAM floor beats cores and GPU
    (2, int(1.5 * _GIB), None, "T0"),   # exactly at the T0 RAM ceiling
    (None, 16 * _GIB, None, "T0"),      # unmeasured facts never qualify upward
    (16, None, None, "T0"),
    (2, 2 * _GIB, None, "T1"),          # T1 floor, both facts exactly at the minimum
    (2, 7 * _GIB, 12 * _GIB, "T1"),     # a big GPU cannot lift a T1 machine
    (3, 4 * _GIB, None, "T1"),
    (4, 4 * _GIB, None, "T1"),          # T2 also needs the RAM floor
    (4, 8 * _GIB, None, "T2"),          # T2 floor, both facts exactly at the minimum
    (8, 16 * _GIB, 4 * _GIB, "T2"),     # VRAM below the T3 floor
    (4, 8 * _GIB, 8 * _GIB, "T3"),      # every floor met exactly
    (8, 32 * _GIB, 24 * _GIB, "T3"),
])
def test_classify_tier_boundaries(cores, ram, vram, expected) -> None:
    decision = classify_tier(cpu_cores=cores, ram_bytes=ram, gpu_vram_bytes=vram)
    assert decision.tier == expected


def test_classify_tier_low_disk_warns_on_any_tier() -> None:
    roomy = classify_tier(cpu_cores=8, ram_bytes=16 * _GIB, disk_free_bytes=4 * _GIB)
    assert roomy.tier == "T2" and "low_disk" in roomy.warnings
    micro = classify_tier(cpu_cores=1, ram_bytes=_GIB, disk_free_bytes=_GIB)
    assert micro.tier == "T0" and "low_disk" in micro.warnings
    fine = classify_tier(cpu_cores=2, ram_bytes=4 * _GIB, disk_free_bytes=50 * _GIB)
    assert fine.warnings == ()


def test_probe_persists_profile_and_environment_md() -> None:
    home = get_hermes_home()
    result = run_machine_probe()
    profile = result["profile"]

    assert (home / "ENVIRONMENT.md").is_file()
    assert profile["tier"] in ("T0", "T1", "T2", "T3")
    assert (home / "ENVIRONMENT.md").read_text(encoding="utf-8").find(profile["tier"]) >= 0

    stored = load_machine_profile()
    assert stored["tier"] == profile["tier"]
    assert stored["probed_at"] == profile["probed_at"]
    # The recorded tier is the classification of the recorded measurements (a relationship
    # between two outputs of the same probe, not a snapshot of this host).
    facts = result["facts"]
    expected = classify_tier(cpu_cores=facts.cpu_cores, ram_bytes=facts.ram_bytes,
                             gpu_vram_bytes=facts.gpu_vram_bytes,
                             disk_free_bytes=facts.disk_free_bytes)
    assert profile["tier"] == expected.tier
    assert result["warnings"] == list(expected.warnings)
    assert stored["summary"] == format_summary(stored)
    assert stored["summary"].startswith("Machine: ")
