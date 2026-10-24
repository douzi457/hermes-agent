"""Semantic-memory batch: bigram similarity primitive, write-time duplicate
advisory, over-limit relevance-ranked injection, consolidation candidates.

Behaviour contracts pinned here:
- under the limit, the system-prompt snapshot is byte-identical with the
  relevance feature on or off (legacy rendering);
- the write advisory NEVER blocks a write and never fires for exact
  duplicates (exact dedup is unchanged);
- over-limit selection is relevance/recency based, marks the omitted count,
  and the legacy inject-all behaviour returns when the switch is off.
"""

from __future__ import annotations

import pytest

from hermes_cli.config_defaults import DEFAULT_CONFIG
from tools import memory_similarity as sim
from tools.memory_tool_store import ENTRY_DELIMITER, MemoryStore

COFFEE = "用户住在深圳，喜欢喝美式咖啡"
COFFEE_V2 = "用户住在深圳，平时喜欢喝美式咖啡"
UNRELATED = "今天天气晴朗适合出门散步和骑行"


@pytest.fixture
def store_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("tools.memory_tool.get_memory_dir", lambda: tmp_path)
    return tmp_path


def _write_entries(store_dir, target_file: str, entries: list[str]):
    (store_dir / target_file).write_text(ENTRY_DELIMITER.join(entries), encoding="utf-8")


# ---------------------------------------------------------------------------
# Similarity primitive (same 口径 as deploy-pack/memory_health.py)
# ---------------------------------------------------------------------------

class TestSimilarityPrimitive:
    def test_near_duplicate_scores_above_default_threshold(self):
        threshold = DEFAULT_CONFIG["memory"]["similarity_threshold"]
        assert sim.similarity(COFFEE, COFFEE_V2) >= threshold

    def test_unrelated_scores_below_threshold(self):
        threshold = DEFAULT_CONFIG["memory"]["similarity_threshold"]
        assert sim.similarity(COFFEE, UNRELATED) < threshold

    def test_dates_and_digits_do_not_dilute(self):
        # Two versions of one fact differing only in their date stamps must
        # still read as the same entry (stamps are stripped before scoring).
        a = "用户喜欢喝美式咖啡（2026-10-01）"
        b = "用户喜欢喝美式咖啡（2026-11-05）"
        assert sim.similarity(a, b) >= 0.99

    def test_candidate_pairs_finds_exact_and_similar(self):
        report = sim.candidate_pairs([COFFEE, COFFEE_V2, UNRELATED, COFFEE], 0.6)
        assert report["exact_groups"] == [[0, 3]]
        pair_indices = {(i, j) for i, j, _ in report["similar_pairs"]}
        assert (0, 1) in pair_indices
        assert all(2 not in pair for pair in pair_indices)


# ---------------------------------------------------------------------------
# Write-time advisory (never blocks, exact dedup unchanged)
# ---------------------------------------------------------------------------

class TestWriteAdvisory:
    def test_advisory_fires_and_names_existing_entry(self, store_dir):
        store = MemoryStore(memory_char_limit=2000)
        assert "similarity_warning" not in store.add("memory", COFFEE)
        result = store.add("memory", COFFEE_V2)
        assert result["success"] is True  # advisory only — the write went through
        warning = result["similarity_warning"]
        assert warning["similar_entries"][0]["entry"] == COFFEE
        assert warning["similar_entries"][0]["similarity"] >= 0.6
        assert store._entries_for("memory") == [COFFEE, COFFEE_V2]

    def test_no_advisory_for_unrelated_entry(self, store_dir):
        store = MemoryStore(memory_char_limit=2000)
        store.add("memory", COFFEE)
        assert "similarity_warning" not in store.add("memory", UNRELATED)

    def test_advisory_can_be_switched_off(self, store_dir):
        store = MemoryStore(memory_char_limit=2000, write_similarity_warning=False)
        store.add("memory", COFFEE)
        assert "similarity_warning" not in store.add("memory", COFFEE_V2)

    def test_threshold_is_configurable(self, store_dir, monkeypatch):
        # The advisory's knob is write_similarity_threshold (calibration
        # split): strict silences the 0.733 coffee pair, lax keeps it.
        # Separate on-disk dirs per store: stores reload from disk on every
        # write, so two stores sharing one dir would see each other's entries.
        strict_dir = store_dir / "strict"
        strict_dir.mkdir()
        monkeypatch.setattr("tools.memory_tool.get_memory_dir", lambda: strict_dir)
        strict = MemoryStore(memory_char_limit=2000, write_similarity_threshold=0.95)
        strict.add("memory", COFFEE)
        assert "similarity_warning" not in strict.add("memory", COFFEE_V2)
        lax_dir = store_dir / "lax"
        lax_dir.mkdir()
        monkeypatch.setattr("tools.memory_tool.get_memory_dir", lambda: lax_dir)
        lax = MemoryStore(memory_char_limit=2000, write_similarity_threshold=0.5)
        lax.add("memory", COFFEE)
        assert "similarity_warning" in lax.add("memory", COFFEE_V2)

    def test_exact_dedup_unchanged_and_silent(self, store_dir):
        store = MemoryStore(memory_char_limit=2000)
        store.add("memory", COFFEE)
        result = store.add("memory", COFFEE)
        assert result["message"] == "Entry already exists (no duplicate added)."
        assert "similarity_warning" not in result
        assert store._entries_for("memory") == [COFFEE]

    def test_batch_add_advisory_against_final_state(self, store_dir):
        store = MemoryStore(memory_char_limit=2000)
        store.add("memory", COFFEE)
        result = store.apply_batch("memory", [{"action": "add", "content": COFFEE_V2}])
        assert result["success"] is True
        assert result["similarity_warnings"][0]["similar_entries"][0]["entry"] == COFFEE


# ---------------------------------------------------------------------------
# Write-threshold calibration (split from the candidate threshold)
# ---------------------------------------------------------------------------

BADMINTON = "老大每周三晚上去打羽毛球"
BADMINTON_V2 = "老大周三晚上经常去打羽毛球"  # measured 0.533 — the 0.5 band
GRADE = "孩子今年上小学二年级了"
GRADE_V2 = "小孩现在读小学二年级"  # measured 0.267 — heavy rewrite, other facts
SHORT_A = "用户姓王"
SHORT_B = "用户姓李"  # measured 0.500 on 3 bigrams — score noise, different facts


class TestWriteThresholdCalibration:
    def test_mid_band_pair_scores_between_the_two_thresholds(self):
        section = DEFAULT_CONFIG["memory"]
        score = sim.similarity(BADMINTON, BADMINTON_V2)
        assert section["write_similarity_threshold"] <= score < section["similarity_threshold"]

    def test_mid_band_add_warns_under_default_settings(self, store_dir):
        store = MemoryStore(memory_char_limit=2000)
        store.add("memory", BADMINTON)
        result = store.add("memory", BADMINTON_V2)
        assert result["success"] is True
        warning = result["similarity_warning"]
        assert warning["similar_entries"][0]["entry"] == BADMINTON
        # It fired BELOW the candidate bar — that is the point of the split.
        assert warning["similar_entries"][0]["similarity"] < DEFAULT_CONFIG["memory"]["similarity_threshold"]

    def test_low_band_add_stays_silent(self, store_dir):
        assert sim.similarity(GRADE, GRADE_V2) < DEFAULT_CONFIG["memory"]["write_similarity_threshold"]
        store = MemoryStore(memory_char_limit=2000)
        store.add("memory", GRADE)
        assert "similarity_warning" not in store.add("memory", GRADE_V2)

    def test_candidates_keep_the_strict_threshold_on_the_same_pair(self):
        section = DEFAULT_CONFIG["memory"]
        strict = sim.candidate_pairs([BADMINTON, BADMINTON_V2], section["similarity_threshold"])
        assert strict["similar_pairs"] == []
        lax = sim.candidate_pairs([BADMINTON, BADMINTON_V2], section["write_similarity_threshold"])
        assert [(i, j) for i, j, _ in lax["similar_pairs"]] == [(0, 1)]

    def test_candidate_threshold_no_longer_drives_the_advisory(self, store_dir):
        # similarity_threshold is the candidates' knob now: cranking it to
        # 0.95 must not silence a write advisory the write threshold accepts.
        store = MemoryStore(memory_char_limit=2000, similarity_threshold=0.95)
        store.add("memory", COFFEE)
        assert "similarity_warning" in store.add("memory", COFFEE_V2)

    def test_short_entry_guard_silences_noisy_pair(self, store_dir):
        # The pair's score clears the write threshold — only the minimum-
        # length guard keeps this one-character factual difference silent.
        assert sim.similarity(SHORT_A, SHORT_B) >= DEFAULT_CONFIG["memory"]["write_similarity_threshold"]
        store = MemoryStore(memory_char_limit=2000)
        store.add("memory", SHORT_A)
        assert "similarity_warning" not in store.add("memory", SHORT_B)

    def test_candidate_path_has_no_short_entry_guard(self):
        # Same short pair, candidate 口径: reported like any other pair —
        # the guard belongs to the advisory path only.
        report = sim.candidate_pairs([SHORT_A, SHORT_B], 0.45)
        assert [(i, j) for i, j, _ in report["similar_pairs"]] == [(0, 1)]


# ---------------------------------------------------------------------------
# Over-limit relevance-ranked injection
# ---------------------------------------------------------------------------

def _padded(tag: str, total: int) -> str:
    return tag + "·" * (total - len(tag))


class TestRankedInjection:
    ENTRIES = [_padded("旧条目一", 40), _padded("旧条目二", 40), _padded("新条目三", 40)]

    def test_under_limit_snapshot_byte_identical(self, store_dir):
        _write_entries(store_dir, "MEMORY.md", [COFFEE, UNRELATED])
        on = MemoryStore(memory_char_limit=2000, relevance_ranked_injection=True)
        on.load_from_disk()
        off = MemoryStore(memory_char_limit=2000, relevance_ranked_injection=False)
        off.load_from_disk()
        assert on.format_for_system_prompt("memory") == off.format_for_system_prompt("memory")

    def test_over_limit_recency_selection_and_omitted_note(self, store_dir):
        _write_entries(store_dir, "MEMORY.md", self.ENTRIES)
        store = MemoryStore(memory_char_limit=100, relevance_ranked_injection=True)
        store.load_from_disk()
        block = store.format_for_system_prompt("memory")
        # Newest two fit (40 + 3 + 40 = 83 <= 100); the oldest is omitted.
        assert "新条目三" in block and "旧条目二" in block
        assert "旧条目一" not in block
        assert "1 of 3 entries omitted" in block
        # The on-disk store is untouched — omission is snapshot-only.
        assert store._entries_for("memory") == self.ENTRIES

    def test_over_limit_query_relevance_beats_recency(self, store_dir):
        entries = [_padded("用户喜欢喝美式咖啡", 40), _padded("完全无关的填充甲", 40),
                   _padded("完全无关的填充乙", 40)]
        _write_entries(store_dir, "MEMORY.md", entries)
        store = MemoryStore(memory_char_limit=100, relevance_ranked_injection=True)
        store.load_from_disk(query_context="美式咖啡的冲泡方法")
        block = store.format_for_system_prompt("memory")
        assert "用户喜欢喝美式咖啡" in block  # oldest, but the only relevant one

    def test_over_limit_switch_off_is_legacy_inject_all(self, store_dir):
        _write_entries(store_dir, "MEMORY.md", self.ENTRIES)
        store = MemoryStore(memory_char_limit=100, relevance_ranked_injection=False)
        store.load_from_disk()
        block = store.format_for_system_prompt("memory")
        for entry in self.ENTRIES:
            assert entry in block
        assert "entries omitted" not in block


# ---------------------------------------------------------------------------
# Consolidation candidates (report only, never merges)
# ---------------------------------------------------------------------------

class TestConsolidationCandidates:
    def test_report_and_markdown(self, store_dir):
        memories = store_dir / "memories"
        memories.mkdir()
        _write_entries(memories, "MEMORY.md", [COFFEE, COFFEE_V2, UNRELATED])
        _write_entries(memories, "USER.md", [UNRELATED])
        report = sim.consolidation_candidate_report(memories, 0.6)
        pairs = report["memory"]["similar_pairs"]
        assert [(i, j) for i, j, _ in pairs] == [(0, 1)]
        assert report["user"]["similar_pairs"] == []
        markdown = sim.render_candidates_markdown(report, 0.6)
        assert "高相似条目对" in markdown and "不自动合并" in markdown
        # Read-only: files are byte-identical after the report.
        assert (memories / "MEMORY.md").read_text(encoding="utf-8") == ENTRY_DELIMITER.join(
            [COFFEE, COFFEE_V2, UNRELATED])


    def test_cli_candidates_prints_report(self, store_dir, monkeypatch, capsys, tmp_path):
        import argparse

        import hermes_constants
        from hermes_cli.main_agent_cmds import _cmd_memory_candidates

        home = tmp_path / "home"
        memories = home / "memories"
        memories.mkdir(parents=True)
        _write_entries(memories, "MEMORY.md", [COFFEE, COFFEE_V2, UNRELATED])
        monkeypatch.setattr(hermes_constants, "get_hermes_home", lambda: home)
        _cmd_memory_candidates(argparse.Namespace(threshold=None))
        out = capsys.readouterr().out
        assert "高相似条目对" in out and "不自动合并" in out


# ---------------------------------------------------------------------------
# Config wiring (invariant: settings reach the store through the loaders)
# ---------------------------------------------------------------------------

class TestConfigWiring:
    def test_store_defaults_match_shipped_config_defaults(self):
        store = MemoryStore()
        section = DEFAULT_CONFIG["memory"]
        assert store.similarity_threshold == section["similarity_threshold"]
        assert store.write_similarity_threshold == section["write_similarity_threshold"]
        assert store.write_similarity_warning == section["write_similarity_warning"]
        assert store.relevance_ranked_injection == section["relevance_ranked_injection"]

    def test_load_on_disk_store_reads_config(self, monkeypatch):
        import hermes_cli.config as config_mod
        from tools import memory_tool

        monkeypatch.setattr(config_mod, "load_config", lambda: {"memory": {
            "similarity_threshold": 0.9, "write_similarity_threshold": 0.9,
            "write_similarity_warning": False, "relevance_ranked_injection": False}})
        store = memory_tool.load_on_disk_store()
        assert store.similarity_threshold == 0.9
        assert store.write_similarity_threshold == 0.9
        assert store.write_similarity_warning is False
        assert store.relevance_ranked_injection is False

    def test_malformed_threshold_falls_back_to_default(self):
        from tools.memory_tool import get_builtin_memory_similarity_settings

        settings = get_builtin_memory_similarity_settings({"memory": {"similarity_threshold": "high"}})
        assert settings["similarity_threshold"] == DEFAULT_CONFIG["memory"]["similarity_threshold"]
        clamped = get_builtin_memory_similarity_settings({"memory": {"similarity_threshold": 7}})
        assert clamped["similarity_threshold"] == 1.0

    def test_malformed_write_threshold_falls_back_to_default(self):
        from tools.memory_tool import get_builtin_memory_similarity_settings

        section = DEFAULT_CONFIG["memory"]
        settings = get_builtin_memory_similarity_settings(
            {"memory": {"write_similarity_threshold": "low"}})
        assert settings["write_similarity_threshold"] == section["write_similarity_threshold"]
        clamped = get_builtin_memory_similarity_settings(
            {"memory": {"write_similarity_threshold": 7}})
        assert clamped["write_similarity_threshold"] == 1.0
        # The two thresholds coerce independently: one malformed key must not
        # drag the other off its configured value.
        mixed = get_builtin_memory_similarity_settings(
            {"memory": {"similarity_threshold": 0.9, "write_similarity_threshold": "low"}})
        assert mixed["similarity_threshold"] == 0.9
        assert mixed["write_similarity_threshold"] == section["write_similarity_threshold"]
