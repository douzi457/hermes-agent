"""Doctor gateway-residency check: cron/duty jobs only fire while a gateway
process lives, so doctor reports residency from the same runtime snapshot
`hermes gateway status` renders — and never installs or starts anything
itself (installing is a system change; --fix only points at the command).
"""

from __future__ import annotations

import hermes_cli.gateway as gateway_mod
from hermes_cli import doctor_platform
from hermes_cli.gateway import GatewayRuntimeSnapshot


def _snap(**kw) -> GatewayRuntimeSnapshot:
    base = dict(manager="systemd (user)", service_installed=False,
                service_running=False, gateway_pids=())
    base.update(kw)
    return GatewayRuntimeSnapshot(**base)


def _run(monkeypatch, snapshot, should_fix=False):
    monkeypatch.setattr(gateway_mod, "get_gateway_runtime_snapshot", lambda: snapshot)
    return doctor_platform._check_gateway_residency(should_fix)


def test_running_service_is_ok(monkeypatch, capsys):
    f = _run(monkeypatch, _snap(service_installed=True, service_running=True, gateway_pids=(4242,)))
    assert f.issues == [] and f.manual_issues == [] and f.fixed == 0
    assert "Gateway is running" in capsys.readouterr().out


def test_installed_but_stopped_points_at_start(monkeypatch, capsys):
    f = _run(monkeypatch, _snap(service_installed=True))
    assert any("hermes gateway start" in issue for issue in f.manual_issues)
    assert "installed but not running" in capsys.readouterr().out


def test_not_resident_points_at_install_and_fix_never_installs(monkeypatch):
    f = _run(monkeypatch, _snap(manager="manual process"), should_fix=True)
    assert f.fixed == 0
    assert any("hermes gateway install" in issue for issue in f.manual_issues)


def test_manual_process_running_warns_it_is_not_resident(monkeypatch, capsys):
    f = _run(monkeypatch, _snap(manager="manual process", gateway_pids=(777,)))
    assert f.manual_issues == []
    assert "not an installed service" in capsys.readouterr().out
