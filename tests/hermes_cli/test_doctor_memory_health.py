"""Doctor memory-health check: built-in memory files measured against their
configured char limits (the same ENTRY_DELIMITER accounting MemoryStore
uses), plus a rough count of entries carrying no YYYY-MM-DD date. --fix
never edits memory content — the remedy it reports is consolidation.
"""

from __future__ import annotations

import hermes_cli.doctor as doctor_mod
from hermes_cli import doctor_state
from tools.memory_tool_store import ENTRY_DELIMITER


def _home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / "memories").mkdir(parents=True)
    monkeypatch.setattr(doctor_mod, "HERMES_HOME", home)
    return home


def test_no_memory_files_is_info_only(tmp_path, monkeypatch, capsys):
    _home(tmp_path, monkeypatch)
    f = doctor_state._check_memory_health(False)
    assert f.issues == [] and f.manual_issues == [] and f.fixed == 0
    assert "No built-in memory files yet" in capsys.readouterr().out


def test_healthy_memory_reports_occupancy(tmp_path, monkeypatch, capsys):
    home = _home(tmp_path, monkeypatch)
    (home / "memories" / "MEMORY.md").write_text("2026-10-23 a dated fact", encoding="utf-8")
    f = doctor_state._check_memory_health(False)
    assert f.manual_issues == []
    out = capsys.readouterr().out
    assert "MEMORY.md at" in out and "of its limit" in out
    assert "without a date" not in out


def test_over_ninety_percent_warns_and_points_at_consolidation(tmp_path, monkeypatch, capsys):
    home = _home(tmp_path, monkeypatch)
    monkeypatch.setattr(doctor_state, "_doctor_memory_config",
                        lambda home=None: {"memory_char_limit": 100, "user_char_limit": 100})
    (home / "memories" / "MEMORY.md").write_text("2026-10-23 " + "x" * 90, encoding="utf-8")
    f = doctor_state._check_memory_health(True)
    assert f.fixed == 0  # --fix never edits memory content
    assert any("Consolidate MEMORY.md" in issue for issue in f.manual_issues)
    assert "101% full" in capsys.readouterr().out


def test_undated_entries_are_counted(tmp_path, monkeypatch, capsys):
    home = _home(tmp_path, monkeypatch)
    entries = ["2026-10-23 dated fact", "undated fact"]
    (home / "memories" / "USER.md").write_text(ENTRY_DELIMITER.join(entries), encoding="utf-8")
    f = doctor_state._check_memory_health(False)
    assert f.manual_issues == []
    assert "1 USER.md entry without a date" in capsys.readouterr().out
