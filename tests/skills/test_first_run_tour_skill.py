"""first-run-tour bundled skill: discoverable by the bundled-skills scanner and
carries the four tour beats (current tier, three questions, live config changes,
conclusions recorded into ENVIRONMENT.md)."""

from __future__ import annotations

import re
from pathlib import Path

import hermes_yaml as yaml

REPO = Path(__file__).resolve().parents[2]
SKILL = REPO / "skills" / "productivity" / "first-run-tour" / "SKILL.md"


def _frontmatter(text: str) -> dict:
    assert text.startswith("---")
    m = re.search(r"\n---\s*\n", text[3:])
    assert m
    return yaml.safe_load(text[3 : m.start() + 3])


def test_bundled_first_run_tour_is_discoverable() -> None:
    assert SKILL.is_file()
    from agent.skill_utils import is_excluded_skill_path

    assert not is_excluded_skill_path(SKILL)
    fm = _frontmatter(SKILL.read_text(encoding="utf-8"))
    assert fm["name"] == SKILL.parent.name == "first-run-tour"


def test_tour_covers_the_four_beats() -> None:
    text = SKILL.read_text(encoding="utf-8")
    for marker in ("ENVIRONMENT.md", "hermes doctor --fix", "hermes config set", "首启对话结论"):
        assert marker in text
