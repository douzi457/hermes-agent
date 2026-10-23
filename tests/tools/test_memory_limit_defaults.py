"""Memory char-limit fallbacks: every store construction path that bypasses the
merged config defaults must enforce the SAME limits as DEFAULT_CONFIG["memory"].

Regression coverage for the drift where the built-in store's fallbacks still
carried the old upstream numbers after the shipped defaults were raised —
a config path that skipped the defaults merge silently shrank the store.
"""

from __future__ import annotations

import hermes_cli.config as config_mod
from hermes_cli.config_defaults import DEFAULT_CONFIG
from tools import memory_tool
from tools.memory_tool_store import MemoryStore


def test_store_defaults_match_shipped_config_defaults():
    store = MemoryStore()
    assert store.memory_char_limit == DEFAULT_CONFIG["memory"]["memory_char_limit"]
    assert store.user_char_limit == DEFAULT_CONFIG["memory"]["user_char_limit"]


def test_load_on_disk_store_falls_back_to_shipped_defaults(monkeypatch):
    monkeypatch.setattr(config_mod, "load_config", lambda: {"memory": {}})
    store = memory_tool.load_on_disk_store()
    assert store.memory_char_limit == DEFAULT_CONFIG["memory"]["memory_char_limit"]
    assert store.user_char_limit == DEFAULT_CONFIG["memory"]["user_char_limit"]


def test_load_on_disk_store_explicit_config_still_wins(monkeypatch):
    monkeypatch.setattr(
        config_mod, "load_config",
        lambda: {"memory": {"memory_char_limit": 123, "user_char_limit": 45}})
    store = memory_tool.load_on_disk_store()
    assert (store.memory_char_limit, store.user_char_limit) == (123, 45)
