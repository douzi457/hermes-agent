"""Machine profile: tier classification boundaries, probe persistence, prompt summary."""

from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest

import hermes_cli.machine_profile as mp
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


_PRESET_SECTION = (
    "## 首启预设（按档位自动应用，仅首启一次）\n"
    "\n"
    "- `delegation.max_concurrent_children` = `1`：子 Agent 改为串行，避免并发请求压垮小机器\n"
    "- `compression.protect_last_n` = `10`：压缩时原样保留的最近消息条数"
)
_CONCLUSION_SECTION = (
    "## 首启对话结论\n"
    "\n"
    "- 日期：2026-10-23\n"
    "- 主要用途：写代码与文档\n"
    "- 本次调整：无"
)


def _append_sections(*sections: str) -> None:
    env_path = get_hermes_home() / "ENVIRONMENT.md"
    text = env_path.read_text(encoding="utf-8").rstrip("\n")
    env_path.write_text(text + "\n\n" + "\n\n".join(sections) + "\n", encoding="utf-8")


def test_reprobe_preserves_appended_sections_verbatim_and_once() -> None:
    """doctor --fix re-probes: the report regenerates, the appended sections survive."""
    run_machine_probe()
    _append_sections(_PRESET_SECTION, _CONCLUSION_SECTION)

    run_machine_probe()  # the re-probe that used to wipe both sections
    text = (get_hermes_home() / "ENVIRONMENT.md").read_text(encoding="utf-8")
    assert _PRESET_SECTION in text  # verbatim, not paraphrased or truncated
    assert _CONCLUSION_SECTION in text
    assert text.count("## 首启预设") == 1
    assert text.count("## 首启对话结论") == 1
    assert text.index("## 首启预设") < text.index("## 首启对话结论")  # original order

    run_machine_probe()  # a second re-probe must not stack copies
    text = (get_hermes_home() / "ENVIRONMENT.md").read_text(encoding="utf-8")
    assert _PRESET_SECTION in text and _CONCLUSION_SECTION in text
    assert text.count("## 首启预设") == 1
    assert text.count("## 首启对话结论") == 1


def test_reprobe_collapses_duplicate_appended_sections() -> None:
    run_machine_probe()
    _append_sections(_CONCLUSION_SECTION, _CONCLUSION_SECTION)  # recorded twice somehow
    run_machine_probe()
    text = (get_hermes_home() / "ENVIRONMENT.md").read_text(encoding="utf-8")
    assert text.count("## 首启对话结论") == 1
    assert _CONCLUSION_SECTION in text


def test_reprobe_does_not_invent_sections() -> None:
    run_machine_probe()
    run_machine_probe()
    text = (get_hermes_home() / "ENVIRONMENT.md").read_text(encoding="utf-8")
    assert "## 首启预设" not in text and "## 首启对话结论" not in text  # headings, not the header's mention


# ---------------------------------------------------------------------------
# Linux NVIDIA VRAM fallback: host facts cannot measure it (no sysfs total,
# and that package never spawns), so the probe asks nvidia-smi — located via
# hermes_platform.resolver — and degrades to None on any failure.
# ---------------------------------------------------------------------------


def _fake_resolution(command: tuple[str, ...]):
    from hermes_platform.resolver.core import Candidate, Resolution

    candidates = tuple(Candidate(cmd, "PATH", True) for cmd in command)
    return Resolution("path_executable" if candidates else "missing", candidates)


def test_nvidia_smi_vram_parses_largest_gpu(monkeypatch) -> None:
    monkeypatch.setattr("hermes_platform.resolver.locate_command",
                        lambda name, **kw: _fake_resolution(("/usr/bin/nvidia-smi",)))
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: SimpleNamespace(
        returncode=0, stdout="8192\n24576\n", stderr=""))
    assert mp._nvidia_smi_vram_bytes() == 24576 << 20


def test_nvidia_smi_vram_missing_binary_never_spawns(monkeypatch) -> None:
    monkeypatch.setattr("hermes_platform.resolver.locate_command",
                        lambda name, **kw: _fake_resolution(()))

    def _boom(*a, **kw):
        raise AssertionError("must not spawn when nvidia-smi is absent")

    monkeypatch.setattr(subprocess, "run", _boom)
    assert mp._nvidia_smi_vram_bytes() is None


@pytest.mark.parametrize("result", [
    SimpleNamespace(returncode=9, stdout="24576\n", stderr="boom"),   # driver error
    SimpleNamespace(returncode=0, stdout="N/A\n", stderr=""),         # unmeasurable card
    SimpleNamespace(returncode=0, stdout="", stderr=""),              # empty output
])
def test_nvidia_smi_vram_failures_degrade_to_none(monkeypatch, result) -> None:
    monkeypatch.setattr("hermes_platform.resolver.locate_command",
                        lambda name, **kw: _fake_resolution(("/usr/bin/nvidia-smi",)))
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: result)
    assert mp._nvidia_smi_vram_bytes() is None


def test_nvidia_smi_vram_spawn_error_degrades_to_none(monkeypatch) -> None:
    monkeypatch.setattr("hermes_platform.resolver.locate_command",
                        lambda name, **kw: _fake_resolution(("/usr/bin/nvidia-smi",)))

    def _boom(*a, **kw):
        raise OSError("nvidia-smi vanished")

    monkeypatch.setattr(subprocess, "run", _boom)
    assert mp._nvidia_smi_vram_bytes() is None


def _patch_roomy_nvidia_host(monkeypatch, *, sysfs_vram: int | None) -> None:
    """Host facts for a roomy Linux box whose NVIDIA VRAM sysfs cannot measure."""
    from hermes_platform.host import facts

    monkeypatch.setattr(facts, "gpu_vram_bytes", lambda: sysfs_vram)
    monkeypatch.setattr(facts, "gpu_class", lambda: "nvidia")
    monkeypatch.setattr(facts, "cpu_count", lambda: 8)
    monkeypatch.setattr(facts, "ram_total_bytes", lambda: 32 * _GIB)


def test_probe_falls_back_to_nvidia_smi_and_reaches_t3(monkeypatch) -> None:
    _patch_roomy_nvidia_host(monkeypatch, sysfs_vram=None)
    monkeypatch.setattr(mp, "_nvidia_smi_vram_bytes", lambda: 24 * _GIB)
    result = run_machine_probe()
    assert result["profile"]["tier"] == "T3"
    assert "24576 MB VRAM" in result["profile"]["gpu"]


def test_probe_nvidia_smi_failure_leaves_tier_at_t2(monkeypatch) -> None:
    _patch_roomy_nvidia_host(monkeypatch, sysfs_vram=None)
    monkeypatch.setattr(mp, "_nvidia_smi_vram_bytes", lambda: None)
    result = run_machine_probe()
    assert result["profile"]["tier"] == "T2"  # unmeasured GPU never qualifies upward


def test_probe_skips_fallback_when_sysfs_measured(monkeypatch) -> None:
    _patch_roomy_nvidia_host(monkeypatch, sysfs_vram=12 * _GIB)

    def _boom():
        raise AssertionError("fallback must not run when sysfs already measured VRAM")

    monkeypatch.setattr(mp, "_nvidia_smi_vram_bytes", _boom)
    result = run_machine_probe()
    assert result["profile"]["tier"] == "T3"
