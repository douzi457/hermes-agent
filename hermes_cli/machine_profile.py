"""Machine profile: probe this machine once, grade it into a tier, and record the result.

Facts come from ``hermes_platform.host`` (never re-measured here); this module only assembles
them into a profile, classifies the tier, and persists it — the ``machine:`` section of
``config.yaml`` (machine-readable) plus a human-readable ``ENVIRONMENT.md`` in HERMES_HOME.
The tier is advisory: it seeds sensible defaults for low-end machines and is injected into
the system prompt as a one-line summary, but no behaviour reads it yet beyond display.

Probe entry point: :func:`run_machine_probe`. ``hermes doctor --fix`` runs it when no
profile exists yet; it can also be re-run any time the hardware changes.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

_GIB = 2**30

# Tier thresholds (bytes where applicable). A machine is graded by its weakest measured
# fact: failing any floor drops it to the lower tier, and an unmeasured fact can never
# qualify a machine for a higher tier.
_T0_MAX_RAM = int(1.5 * _GIB)   # T0: <= 1 core OR <= 1.5G RAM
_T1_MIN_RAM = 2 * _GIB          # T1: >= 2 cores AND >= 2G RAM
_T2_MIN_CORES, _T2_MIN_RAM = 4, 8 * _GIB
_T3_MIN_VRAM = 8 * _GIB         # T3: T2 hardware AND >= 8G dedicated VRAM
_LOW_DISK_FREE = 5 * _GIB       # below this, warn on any tier (deps + caches need room)

TIER_NAMES = {"T0": "micro", "T1": "standard", "T2": "roomy", "T3": "gpu"}


@dataclass(frozen=True)
class MachineFacts:
    """One probe's raw measurements; ``None`` means the fact could not be measured."""

    cpu_cores: int | None
    cpu_model: str
    ram_bytes: int | None
    disk_free_bytes: int | None
    gpu_class: str  # hermes_platform.host.facts.gpu_class(): nvidia | amd | intel | none | unknown
    gpu_name: str
    gpu_vram_bytes: int | None
    os_family: str
    os_release: str
    native_arch: str
    is_wsl: bool
    is_container: bool


@dataclass(frozen=True)
class TierDecision:
    tier: str
    warnings: tuple[str, ...] = field(default_factory=tuple)


def classify_tier(*, cpu_cores: int | None, ram_bytes: int | None,
                  gpu_vram_bytes: int | None = None,
                  disk_free_bytes: int | None = None) -> TierDecision:
    """Grade measured facts into T0–T3. Pure function of its arguments.

    Order matters: CPU/RAM set the base tier first; a GPU can only raise a T2 machine
    to T3, never lift a low-CPU or low-RAM machine out of its base tier.
    """
    warnings = []
    if disk_free_bytes is not None and disk_free_bytes < _LOW_DISK_FREE:
        warnings.append("low_disk")
    if cpu_cores is None or ram_bytes is None or cpu_cores <= 1 or ram_bytes <= _T0_MAX_RAM:
        return TierDecision("T0", tuple(warnings))
    if cpu_cores >= _T2_MIN_CORES and ram_bytes >= _T2_MIN_RAM:
        if gpu_vram_bytes is not None and gpu_vram_bytes >= _T3_MIN_VRAM:
            return TierDecision("T3", tuple(warnings))
        return TierDecision("T2", tuple(warnings))
    if cpu_cores >= 2 and ram_bytes >= _T1_MIN_RAM:
        return TierDecision("T1", tuple(warnings))
    return TierDecision("T0", tuple(warnings))


def probe_machine_facts(home: Path | None = None) -> MachineFacts:
    """Measure this machine through ``hermes_platform.host``; disk is measured on *home*."""
    from hermes_platform.host import facts as host
    from hermes_platform.host import runtime

    if home is None:
        from hermes_constants import get_hermes_home

        home = get_hermes_home()
    target = home
    while not target.exists() and target.parent != target:  # a fresh HERMES_HOME may not exist yet
        target = target.parent
    try:
        disk_free = shutil.disk_usage(target).free
    except OSError:
        disk_free = None
    nvidia = host.nvidia_gpus()
    return MachineFacts(
        cpu_cores=host.cpu_count(),
        cpu_model=host.cpu_model(),
        ram_bytes=host.ram_total_bytes(),
        disk_free_bytes=disk_free,
        gpu_class=host.gpu_class(),
        gpu_name=nvidia[0].name if nvidia else "",
        gpu_vram_bytes=host.gpu_vram_bytes(),
        os_family=host.os_family(),
        os_release=_os_release(host.os_family()),
        native_arch=host.native_arch(),
        is_wsl=runtime.is_wsl(),
        is_container=runtime.is_container(),
    )


def _os_release(os_family: str) -> str:
    import platform

    return (platform.mac_ver()[0] if os_family == "darwin" else "") or platform.release()


def _fmt_gb(num_bytes: int | None) -> str:
    return "unknown" if num_bytes is None else f"{num_bytes / _GIB:.1f}G"


def _gpu_summary(facts: MachineFacts) -> str:
    """The ``machine.gpu`` config string: class, model and VRAM as far as they were measured."""
    if facts.gpu_class in ("none", ""):
        return "none"
    parts = [facts.gpu_class]
    if facts.gpu_name:
        parts.append(facts.gpu_name)
    if facts.gpu_vram_bytes is not None:
        parts.append(f"{round(facts.gpu_vram_bytes / 2**20)} MB VRAM")
    return " · ".join(parts)


def format_summary(profile: dict) -> str:
    """The one-line summary injected into the system prompt, from a stored profile dict."""
    tier = profile.get("tier") or "?"
    name = TIER_NAMES.get(tier, "")
    cores = profile.get("cpu_cores")
    ram_mb = profile.get("ram_mb")
    ram = "unknown RAM" if ram_mb is None else f"{ram_mb / 1024:.1f}G RAM"
    gpu = profile.get("gpu") or "GPU unknown"
    probed = (profile.get("probed_at") or "")[:10]
    line = f"Machine: {tier}" + (f" ({name})" if name else "")
    line += f" · {cores if cores is not None else '?'} cores · {ram} · GPU: {gpu}"
    return line + (f" · profile probed {probed}" if probed else "")


def build_profile(facts: MachineFacts, *, probed_at: str | None = None) -> dict:
    """Assemble the stored profile (the ``machine:`` config section) from measured facts."""
    decision = classify_tier(cpu_cores=facts.cpu_cores, ram_bytes=facts.ram_bytes,
                             gpu_vram_bytes=facts.gpu_vram_bytes,
                             disk_free_bytes=facts.disk_free_bytes)
    profile = {
        "tier": decision.tier,
        "probed_at": probed_at or datetime.now(UTC).isoformat(timespec="seconds"),
        "cpu_cores": facts.cpu_cores,
        "ram_mb": round(facts.ram_bytes / 2**20) if facts.ram_bytes is not None else None,
        "disk_free_gb": round(facts.disk_free_bytes / _GIB, 1) if facts.disk_free_bytes is not None else None,
        "gpu": _gpu_summary(facts),
    }
    profile["summary"] = format_summary(profile)
    return {"profile": profile, "facts": facts, "warnings": list(decision.warnings)}


def render_environment_md(result: dict) -> str:
    """ENVIRONMENT.md: the human-readable probe report (regenerated on every probe)."""
    facts: MachineFacts = result["facts"]
    profile: dict = result["profile"]
    env_bits = [bit for bit, on in (("WSL", facts.is_wsl), ("容器", facts.is_container)) if on]
    rows = [
        ("档位", f"{profile['tier']}（{TIER_NAMES.get(profile['tier'], '')}）"),
        ("操作系统", f"{facts.os_family} {facts.os_release} · {facts.native_arch}" + (f" · {'/'.join(env_bits)}" if env_bits else "")),
        ("CPU", f"{facts.cpu_cores if facts.cpu_cores is not None else '未知'} 核" + (f" · {facts.cpu_model}" if facts.cpu_model else "")),
        ("内存", _fmt_gb(facts.ram_bytes)),
        ("磁盘可用（HERMES_HOME 所在盘）", _fmt_gb(facts.disk_free_bytes)),
        ("GPU", profile["gpu"]),
        ("体检时间", profile["probed_at"]),
    ]
    lines = ["# 本机环境档案（ENVIRONMENT）", "",
             "由机器体检自动生成，换机器或升配后重跑体检即覆盖（`hermes doctor --fix`）。", "",
             "| 项目 | 值 |", "|---|---|"]
    lines += [f"| {key} | {value} |" for key, value in rows]
    if result["warnings"]:
        lines += ["", "## 告警", ""]
        if "low_disk" in result["warnings"]:
            lines.append("- 磁盘可用不足 5G：依赖与缓存可能装不下，建议先清盘或扩容。")
    lines += ["", "档位含义：T0 微型（低配保底）· T1 标准 · T2 充裕 · T3 带 GPU。"
                  "档位按最弱的一项硬件定，GPU 只能把 T2 抬到 T3，不能把低 CPU/内存的机器抬档。", ""]
    return "\n".join(lines)


def run_machine_probe(*, home: Path | None = None, write: bool = True) -> dict:
    """Probe, grade, and (unless ``write=False``) persist the profile.

    Persistence: the ``machine:`` section of the profile's ``config.yaml`` via the config
    writer seam, plus ``ENVIRONMENT.md`` beside it. Returns the :func:`build_profile` dict.
    """
    if home is None:
        from hermes_constants import get_hermes_home

        home = get_hermes_home()
    result = build_profile(probe_machine_facts(home))
    if write:
        from hermes_cli.config import atomic_config_write, get_config_path, read_raw_config
        from utils import atomic_write_text

        raw = read_raw_config()
        raw["machine"] = result["profile"]
        atomic_config_write(get_config_path(), raw)
        atomic_write_text(home / "ENVIRONMENT.md", render_environment_md(result))
    return result


def load_machine_profile() -> dict:
    """The stored ``machine:`` profile via the merged config; ``{}`` fields when never probed."""
    from hermes_cli.config import load_config_readonly

    machine = load_config_readonly().get("machine")
    return machine if isinstance(machine, dict) else {}
