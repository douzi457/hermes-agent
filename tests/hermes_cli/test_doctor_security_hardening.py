"""Doctor security-hardening checks (fork batch security):

- ``_check_env_permissions``: the .env holds every API key; on POSIX it must
  not be group/other-accessible, and --fix tightens it to 0600 (the same
  chmod the env-file check applies to a .env it creates). Windows has no
  POSIX mode bits: information only, never a finding.
- ``_check_secret_exposure``: suspected secrets in memories/ or logs/ are
  reported masked (file + line + pattern label + at most 4 leading chars);
  the full value must never reach doctor output, and ordinary prose that
  merely discusses key names must not trigger.
- ``_check_gateway_residency`` privilege context: a running gateway's owner
  is reported only when it can be resolved reliably (canonical cmdline
  match); root/Administrator earns a warning, an unresolvable owner earns
  one generic tip line and no verdict.

All secret-looking fixtures below are obviously synthetic strings (they carry
FAKE / SYNTHETIC markers); no real credential shape is reproduced.
"""

from __future__ import annotations

import os
import stat

import pytest

import hermes_cli.doctor as doctor_mod
import hermes_cli.gateway as gateway_mod
from hermes_cli import doctor_config, doctor_platform, doctor_state
from hermes_cli.gateway import GatewayRuntimeSnapshot

FAKE_SK = "sk-FAKE00000000000000000000000000"
FAKE_GHP = "ghp_FAKE000000000000000000000000000000"
FAKE_AWS = "AKIAFAKE000000000000"
FAKE_ASSIGNMENT_VALUE = "SYNTHETIC-TEST-VALUE-0000"


def _home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir(parents=True)
    monkeypatch.setattr(doctor_mod, "HERMES_HOME", home)
    return home


# ---------------------------------------------------------------------------
# .env permissions
# ---------------------------------------------------------------------------


def test_env_mode_exposed_truth_table():
    assert doctor_config._env_mode_exposed(0o600) is False
    assert doctor_config._env_mode_exposed(0o400) is False
    assert doctor_config._env_mode_exposed(0o644) is True
    assert doctor_config._env_mode_exposed(0o640) is True
    assert doctor_config._env_mode_exposed(0o777) is True


def test_env_permissions_missing_file_is_silent(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)
    f = doctor_config._check_env_permissions(True)
    assert f.issues == [] and f.manual_issues == [] and f.fixed == 0


@pytest.mark.platforms("posix")
def test_env_permissions_group_readable_warns(tmp_path, monkeypatch, capsys):
    home = _home(tmp_path, monkeypatch)
    env = home / ".env"
    env.write_text("AGNES_API_KEY=x\n", encoding="utf-8")
    os.chmod(env, 0o644)
    f = doctor_config._check_env_permissions(False)
    assert any("chmod 600" in issue for issue in f.issues)
    assert "mode 644" in capsys.readouterr().out
    assert stat.S_IMODE(env.stat().st_mode) == 0o644  # untouched without --fix


@pytest.mark.platforms("posix")
def test_env_permissions_group_read_only_also_warns(tmp_path, monkeypatch):
    home = _home(tmp_path, monkeypatch)
    env = home / ".env"
    env.write_text("AGNES_API_KEY=x\n", encoding="utf-8")
    os.chmod(env, 0o640)
    f = doctor_config._check_env_permissions(False)
    assert f.issues != []


@pytest.mark.platforms("posix")
def test_env_permissions_fix_tightens_to_600(tmp_path, monkeypatch, capsys):
    home = _home(tmp_path, monkeypatch)
    env = home / ".env"
    env.write_text("AGNES_API_KEY=x\n", encoding="utf-8")
    os.chmod(env, 0o644)
    f = doctor_config._check_env_permissions(True)
    assert f.fixed == 1 and f.issues == []
    assert stat.S_IMODE(env.stat().st_mode) == 0o600
    assert "chmod 600" in capsys.readouterr().out


@pytest.mark.platforms("posix")
def test_env_permissions_owner_only_passes(tmp_path, monkeypatch, capsys):
    home = _home(tmp_path, monkeypatch)
    env = home / ".env"
    env.write_text("AGNES_API_KEY=x\n", encoding="utf-8")
    os.chmod(env, 0o600)
    f = doctor_config._check_env_permissions(False)
    assert f.issues == [] and f.manual_issues == [] and f.fixed == 0
    assert "owner-only" in capsys.readouterr().out


@pytest.mark.platforms("windows")
def test_env_permissions_windows_is_info_only(tmp_path, monkeypatch, capsys):
    home = _home(tmp_path, monkeypatch)
    (home / ".env").write_text("AGNES_API_KEY=x\n", encoding="utf-8")
    f = doctor_config._check_env_permissions(True)
    assert f.issues == [] and f.manual_issues == [] and f.fixed == 0
    assert "Windows" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Suspected-secret scan
# ---------------------------------------------------------------------------


def test_scan_line_formats_and_masks():
    assert doctor_state._scan_line_for_secret(f"note {FAKE_SK} end") == ("API key (sk-…)", "sk-F…")
    assert doctor_state._scan_line_for_secret(FAKE_GHP)[0] == "GitHub token"
    assert doctor_state._scan_line_for_secret(FAKE_AWS)[0] == "AWS access key ID"
    assert doctor_state._scan_line_for_secret("-----BEGIN OPENSSH PRIVATE KEY-----")[0] == "private key block"
    label, mask = doctor_state._scan_line_for_secret(f"AGNES_API_KEY={FAKE_ASSIGNMENT_VALUE}")
    assert label == "credential assignment" and mask == "SYNT…"


def test_scan_line_ignores_prose_and_placeholders():
    quiet_lines = [
        "2026-10-23 AGNES_API_KEY 由老大在仓库 Secrets 自填，任何人不经手 key 值本身。",
        "讨论：token 的命名规范与 API_KEY 的轮换节奏，还没有结论。",
        "task-oriented, risk-based design notes — no values here.",
        "OPENAI_API_KEY=your-key-here-please",
        'config example: "api_key": "not-a-real-value-at-all"',
    ]
    for line in quiet_lines:
        assert doctor_state._scan_line_for_secret(line) is None, line


def test_secret_in_memory_flagged_and_redacted(tmp_path, monkeypatch, capsys):
    home = _home(tmp_path, monkeypatch)
    mem = home / "memories"
    mem.mkdir()
    (mem / "MEMORY.md").write_text(f"2026-10-23 误存：key 是 {FAKE_SK}\n", encoding="utf-8")
    f = doctor_state._check_secret_exposure(False)
    out = capsys.readouterr().out
    assert f.issues == [] and f.fixed == 0  # report-only, even the summary is manual
    assert any("rotate" in issue for issue in f.manual_issues)
    assert "memories/MEMORY.md:1" in out and "sk-F…" in out
    assert FAKE_SK not in out  # the full value never reaches any output


def test_secret_assignment_in_log_flagged_and_redacted(tmp_path, monkeypatch, capsys):
    home = _home(tmp_path, monkeypatch)
    logs = home / "logs"
    logs.mkdir()
    (logs / "agent.log").write_text(f"AGNES_API_KEY={FAKE_ASSIGNMENT_VALUE}\n", encoding="utf-8")
    f = doctor_state._check_secret_exposure(True)  # --fix must not delete anything either
    out = capsys.readouterr().out
    assert f.fixed == 0 and f.manual_issues != []
    assert "logs/agent.log:1" in out and "SYNT…" in out
    assert FAKE_ASSIGNMENT_VALUE not in out
    assert (logs / "agent.log").read_text(encoding="utf-8") != ""  # content untouched


def test_normal_chinese_memory_does_not_trigger(tmp_path, monkeypatch, capsys):
    home = _home(tmp_path, monkeypatch)
    mem = home / "memories"
    mem.mkdir()
    (mem / "MEMORY.md").write_text(
        "2026-10-23 AGNES_API_KEY 由老大自填；讨论了 token 轮换与密钥管理纪律。\n"
        "2026-10-23 普通条目：今天修了 doctor 的检查。\n",
        encoding="utf-8")
    f = doctor_state._check_secret_exposure(False)
    assert f.issues == [] and f.manual_issues == []
    assert "No suspected secrets" in capsys.readouterr().out


def test_secret_scan_without_dirs_is_info_only(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)
    f = doctor_state._check_secret_exposure(False)
    assert f.issues == [] and f.manual_issues == [] and f.fixed == 0


# ---------------------------------------------------------------------------
# Gateway privilege context
# ---------------------------------------------------------------------------


def _snap(**kw) -> GatewayRuntimeSnapshot:
    base = dict(manager="systemd (user)", service_installed=True,
                service_running=True, gateway_pids=(4242,))
    base.update(kw)
    return GatewayRuntimeSnapshot(**base)


def _run_residency(monkeypatch, owner):
    monkeypatch.setattr(gateway_mod, "get_gateway_runtime_snapshot", lambda: _snap())
    monkeypatch.setattr(doctor_platform, "_gateway_process_owner", lambda pid: owner)
    return doctor_platform._check_gateway_residency(False)


def test_gateway_running_as_root_warns(monkeypatch, capsys):
    f = _run_residency(monkeypatch, ("root", True))
    out = capsys.readouterr().out
    assert "full privileges" in out and "root" in out
    assert any("low-privilege" in issue for issue in f.manual_issues)


def test_gateway_running_as_user_is_info(monkeypatch, capsys):
    f = _run_residency(monkeypatch, ("alice", False))
    assert "runs as alice" in capsys.readouterr().out
    assert f.manual_issues == []


def test_gateway_owner_unresolvable_is_generic_tip_only(monkeypatch, capsys):
    f = _run_residency(monkeypatch, None)
    assert "could not be verified" in capsys.readouterr().out
    assert f.manual_issues == [] and f.issues == []


# ---------------------------------------------------------------------------
# Registration: both new checks ride in the doctor run (and its summary)
# ---------------------------------------------------------------------------


def test_new_checks_registered_in_doctor():
    checks = [check for _title, check in doctor_mod.DOCTOR_CHECKS]
    assert doctor_config._check_env_permissions in checks
    assert doctor_state._check_secret_exposure in checks
