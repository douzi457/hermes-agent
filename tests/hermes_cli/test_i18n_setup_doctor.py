"""i18n wiring for the setup wizard and doctor surfaces.

The setup/doctor strings wired through ``agent.i18n.t`` in this batch must
satisfy three contracts:

* default language (en) output is byte-identical to the pre-i18n literals, so
  every existing output-asserting test keeps passing unchanged;
* with ``display.language: zh`` (or HERMES_LANGUAGE=zh) the wired surfaces
  render the bundled Simplified Chinese catalog;
* a key missing from the active catalog falls back to the English source
  string, and an invalid configured language resolves back to English.
"""

from __future__ import annotations

import pytest

import hermes_cli.doctor as doctor_mod
import hermes_cli.gateway as gateway_mod
import hermes_cli.setup as setup_mod
from agent import i18n
from agent.i18n import t
from hermes_cli import doctor_platform, doctor_state
from hermes_cli.doctor_report import Finding
from hermes_cli.gateway import GatewayRuntimeSnapshot


@pytest.fixture(autouse=True)
def _reset_language():
    yield
    i18n.reset_language_cache()


def _force_english(monkeypatch):
    """No env var and no config language -> the en default."""
    monkeypatch.delenv("HERMES_LANGUAGE", raising=False)
    monkeypatch.setattr(i18n, "_config_language", lambda: None)
    i18n.reset_language_cache()


def _force_chinese(monkeypatch):
    monkeypatch.setenv("HERMES_LANGUAGE", "zh")
    i18n.reset_language_cache()


# ---------------------------------------------------------------------------
# en default: wired strings equal the pre-i18n literals
# ---------------------------------------------------------------------------


def test_en_catalog_values_match_original_literals(monkeypatch):
    _force_english(monkeypatch)
    assert t("setup.frame.cancelled") == "Setup cancelled."
    assert t("setup.frame.yes") == "Yes"
    assert t("setup.label.gateway") == "Messaging Platforms (Gateway)"
    assert t("doctor.summary.all_passed") == "  All checks passed! 🎉"
    assert t("doctor.section.gateway_residency") == "Gateway Residency"
    assert t("doctor.check.gateway.not_resident") == "Gateway is not resident"
    assert (
        t("doctor.check.memory.none")
        == "No built-in memory files yet (memories/ is empty)"
    )


def test_en_setup_section_label_and_guidance(monkeypatch, capsys):
    _force_english(monkeypatch)
    assert setup_mod._section_label("model", "Model & Provider") == "Model & Provider"
    assert setup_mod._section_label("gateway", "Messaging Platforms (Gateway)") == (
        "Messaging Platforms (Gateway)"
    )
    setup_mod.print_noninteractive_setup_guidance()
    out = capsys.readouterr().out
    assert "Hermes Setup — Non-interactive mode" in out
    assert "The interactive wizard cannot be used here." in out


def test_en_doctor_summary_all_passed(monkeypatch, capsys):
    _force_english(monkeypatch)
    doctor_mod._print_summary(False, Finding())
    assert "All checks passed! 🎉" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# zh: wired surfaces render Chinese
# ---------------------------------------------------------------------------


def test_zh_catalog_values_are_translated(monkeypatch):
    _force_chinese(monkeypatch)
    assert t("setup.frame.cancelled") == "设置已取消。"
    assert t("setup.label.gateway") == "消息平台（网关）"
    assert t("doctor.summary.all_passed") == "  所有检查均已通过！🎉"
    assert t("doctor.section.gateway_residency") == "网关驻留"
    # Command names inside advice strings stay literal.
    assert "hermes gateway install" in t("doctor.check.gateway.install_issue")


def test_zh_setup_guidance_and_labels(monkeypatch, capsys):
    _force_chinese(monkeypatch)
    assert setup_mod._section_label("model", "Model & Provider") == "模型与供应商"
    setup_mod.print_noninteractive_setup_guidance()
    out = capsys.readouterr().out
    assert "Hermes 设置 — 非交互模式" in out
    assert "此处无法使用交互式向导。" in out


def test_zh_doctor_summary_all_passed(monkeypatch, capsys):
    _force_chinese(monkeypatch)
    doctor_mod._print_summary(False, Finding())
    assert "所有检查均已通过！🎉" in capsys.readouterr().out


def _snap(**kw) -> GatewayRuntimeSnapshot:
    base = dict(
        manager="systemd (user)",
        service_installed=False,
        service_running=False,
        gateway_pids=(),
    )
    base.update(kw)
    return GatewayRuntimeSnapshot(**base)


def test_zh_gateway_residency_check(monkeypatch, capsys):
    _force_chinese(monkeypatch)
    monkeypatch.setattr(
        gateway_mod, "get_gateway_runtime_snapshot", lambda: _snap()
    )
    finding = doctor_platform._check_gateway_residency(False)
    out = capsys.readouterr().out
    assert "网关未常驻" in out
    assert any("hermes gateway install" in issue for issue in finding.manual_issues)


def test_zh_memory_health_check_empty(monkeypatch, tmp_path, capsys):
    _force_chinese(monkeypatch)
    home = tmp_path / "home"
    (home / "memories").mkdir(parents=True)
    monkeypatch.setattr(doctor_mod, "HERMES_HOME", home)
    finding = doctor_state._check_memory_health(False)
    assert finding.issues == [] and finding.manual_issues == []
    assert "尚无内置记忆文件" in capsys.readouterr().out


def test_zh_memory_health_check_occupancy(monkeypatch, tmp_path, capsys):
    _force_chinese(monkeypatch)
    home = tmp_path / "home"
    (home / "memories").mkdir(parents=True)
    monkeypatch.setattr(doctor_mod, "HERMES_HOME", home)
    (home / "memories" / "MEMORY.md").write_text(
        "2026-10-23 a dated fact", encoding="utf-8"
    )
    doctor_state._check_memory_health(False)
    out = capsys.readouterr().out
    assert "MEMORY.md 已用其上限的" in out
    assert "字符" in out


# ---------------------------------------------------------------------------
# Fallback and language resolution
# ---------------------------------------------------------------------------


def test_missing_translation_falls_back_to_english(tmp_path, monkeypatch):
    fake_locales = tmp_path / "locales"
    fake_locales.mkdir()
    (fake_locales / "en.yaml").write_text(
        'setup:\n  frame:\n    cancelled: "Setup cancelled."\n', encoding="utf-8"
    )
    (fake_locales / "zh.yaml").write_text("# intentionally empty\n", encoding="utf-8")
    monkeypatch.setattr(i18n, "_locales_dir", lambda: fake_locales)
    i18n.reset_language_cache()
    try:
        assert t("setup.frame.cancelled", lang="zh") == "Setup cancelled."
    finally:
        i18n.reset_language_cache()


def test_config_language_zh_is_used(monkeypatch, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    (home / "config.yaml").write_text("display:\n  language: zh\n", encoding="utf-8")
    monkeypatch.delenv("HERMES_LANGUAGE", raising=False)
    monkeypatch.setenv("HERMES_HOME", str(home))
    i18n.reset_language_cache()
    assert i18n.get_language() == "zh"
    assert t("setup.frame.cancelled") == "设置已取消。"


def test_config_language_invalid_falls_back_to_english(monkeypatch, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    (home / "config.yaml").write_text(
        "display:\n  language: not-a-language\n", encoding="utf-8"
    )
    monkeypatch.delenv("HERMES_LANGUAGE", raising=False)
    monkeypatch.setenv("HERMES_HOME", str(home))
    i18n.reset_language_cache()
    assert i18n.get_language() == "en"
    assert t("setup.frame.cancelled") == "Setup cancelled."


# ---------------------------------------------------------------------------
# Catalog parity spot-check for the new namespaces
# ---------------------------------------------------------------------------


def test_new_keys_parity_between_en_and_zh():
    en = i18n._load_bundled("en")
    zh = i18n._load_bundled("zh")
    en_new = {k for k in en if k.startswith(("setup.", "doctor."))}
    zh_new = {k for k in zh if k.startswith(("setup.", "doctor."))}
    assert zh_new == en_new
    # Both surfaces are actually populated in the catalogs.
    assert {
        "setup.frame.cancelled",
        "setup.label.gateway",
        "doctor.summary.all_passed",
        "doctor.check.gateway.not_resident",
        "doctor.check.memory.none",
    } <= en_new
    # The zh catalog is a real translation, not a copy of the English source.
    for key in (
        "setup.frame.cancelled",
        "doctor.summary.all_passed",
        "doctor.check.memory.none",
    ):
        assert zh[key] != en[key]
