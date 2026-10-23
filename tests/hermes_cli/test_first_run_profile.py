"""First-run tier presets and the setup tail hook: presets only name shipped config
keys, apply once, and never overwrite a key the user set explicitly."""

from __future__ import annotations

import hermes_cli.machine_profile as mp
from hermes_cli.config import (
    atomic_config_write, get_config_path, load_config_readonly, read_raw_config,
)
from hermes_cli.config_defaults import DEFAULT_CONFIG
from hermes_cli.machine_profile import (
    apply_first_run_machine_profile, apply_tier_presets, load_machine_profile, tier_presets,
)
from hermes_constants import get_hermes_home

_GIB = 2**30

_T0_FACTS = mp.MachineFacts(
    cpu_cores=1, cpu_model="test cpu", ram_bytes=_GIB, disk_free_bytes=50 * _GIB,
    gpu_class="none", gpu_name="", gpu_vram_bytes=None, os_family="linux",
    os_release="test", native_arch="x86_64", is_wsl=False, is_container=False,
)


def _raw_set(dotpath: str, value) -> None:
    raw = read_raw_config()
    node = raw
    parts = dotpath.split(".")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value
    atomic_config_write(get_config_path(), raw)


def test_every_preset_key_exists_in_default_config() -> None:
    """The presets' iron rule: every key they write is a shipped DEFAULT_CONFIG key."""
    for tier in ("T0", "T1", "T2", "T3"):
        for dotpath in tier_presets(tier):
            node = DEFAULT_CONFIG
            for part in dotpath.split("."):
                assert isinstance(node, dict) and part in node, f"{tier}: {dotpath} missing"
                node = node[part]


def test_tier_preset_shape() -> None:
    assert tier_presets("T1") == {}  # T1 is the shipped default posture
    assert tier_presets("") == {}
    assert tier_presets("T3") == tier_presets("T2")
    t0 = tier_presets("T0")
    assert t0["delegation.max_concurrent_children"] == 1  # serial delegation on micro
    assert "browser" in t0["agent.disabled_toolsets"]


def test_apply_tier_presets_writes_absent_keys() -> None:
    lines = apply_tier_presets({"tier": "T0"})
    assert lines
    cfg = load_config_readonly()
    assert cfg["delegation"]["max_concurrent_children"] == 1
    assert cfg["delegation"]["max_iterations"] == 100
    assert cfg["agent"]["disabled_toolsets"] == tier_presets("T0")["agent.disabled_toolsets"]
    assert cfg["compression"]["protect_last_n"] == 10
    assert cfg["memory"]["memory_char_limit"] == 2200


def test_apply_tier_presets_never_overwrites_user_keys() -> None:
    _raw_set("compression.protect_last_n", 7)  # user-owned before first run
    lines = apply_tier_presets({"tier": "T0"})
    cfg = load_config_readonly()
    assert cfg["compression"]["protect_last_n"] == 7  # untouched
    assert any("protect_last_n" in line and "未覆盖" in line for line in lines)
    assert cfg["delegation"]["max_concurrent_children"] == 1  # other keys still applied


def test_first_run_applies_once_then_skips(monkeypatch) -> None:
    monkeypatch.setattr(mp, "probe_machine_facts", lambda home=None: _T0_FACTS)
    home = get_hermes_home()

    line = apply_first_run_machine_profile()
    assert "T0" in line
    assert load_machine_profile()["tier"] == "T0"
    assert load_config_readonly()["delegation"]["max_concurrent_children"] == 1
    env_text = (home / "ENVIRONMENT.md").read_text(encoding="utf-8")
    assert "首启预设" in env_text

    _raw_set("compression.protect_last_n", 42)  # the user tunes a preset key afterwards
    line2 = apply_first_run_machine_profile()
    assert "已存在" in line2  # existing profile = already applied; nothing re-runs
    assert load_config_readonly()["compression"]["protect_last_n"] == 42
    assert (home / "ENVIRONMENT.md").read_text(encoding="utf-8").count("首启预设") == 1


def test_setup_hook_swallows_probe_failure(monkeypatch) -> None:
    """The setup tail hook is fault-isolated: a broken probe warns, never raises."""
    from hermes_cli import setup

    def _boom(**_kwargs):
        raise RuntimeError("probe exploded")

    monkeypatch.setattr(mp, "apply_first_run_machine_profile", _boom)
    setup._apply_first_run_machine_profile()  # must not raise


def test_setup_hook_prints_summary_line(monkeypatch, capsys) -> None:
    from hermes_cli import setup

    monkeypatch.setattr(mp, "apply_first_run_machine_profile", lambda **_k: "Machine: T1 · ok")
    setup._apply_first_run_machine_profile()
    assert "Machine: T1" in capsys.readouterr().out
