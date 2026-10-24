"""Text-similarity primitives for built-in memory (fork batch: semantic memory).

One similarity 口径 for the whole memory surface — the write-time duplicate
advisory, the over-limit relevance-ranked injection and the consolidation
candidate report all call THIS module, and the algorithm is deliberately the
same character-bigram Jaccard the deploy-pack health check
(``deploy-pack/memory/memory_health.py``) ships, so framework and deploy-pack
numbers agree on the same pair of entries.

Honest scope: bigram Jaccard is LEXICAL similarity (same words, similar
spelling), not semantic understanding — it catches near-duplicate phrasings
of the same fact in Chinese or English, it does not know two differently
worded entries contradict each other. That is why every consumer here is
advisory: candidates are reported, a human / the consolidation protocol
decides.

Backend shape: consumers depend on the ``SimilarityBackend`` protocol only.
``bigram`` is the sole implementation because core has no embeddings client
(external memory providers such as mem0 own their vectors inside the
provider). A future ``vector`` backend implements the same two methods by
embedding texts through a provider ``/embeddings`` endpoint behind
``memory.similarity_backend: "vector"`` + an embedding model setting; until
then any non-default backend name resolves to bigram with a logged warning
rather than failing memory writes.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

logger = logging.getLogger("tools.memory_tool")

_DATE_RE = re.compile(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})")


def normalize(text: str) -> str:
    """Rough normalization: lowercase, punctuation/whitespace folded.

    Identical to deploy-pack ``memory_health.normalize`` — keep in lockstep."""
    folded = text.lower()
    folded = re.sub(r"[^\w]+", " ", folded, flags=re.UNICODE)
    return " ".join(folded.split())


def _squash(text: str) -> str:
    """The comparison text: dates/digits stripped, folded, spaces removed."""
    no_dates = _DATE_RE.sub(" ", text)
    no_digits = re.sub(r"\d+", " ", no_dates)
    return normalize(no_digits).replace(" ", "")


def comparison_length(text: str) -> int:
    """Length of the squashed comparison text behind ``token_set`` — the
    score's granularity. A 4-char entry has 3 bigrams, so a one-character
    factual difference （用户姓王 vs 用户姓李） still scores 0.50; advisory
    callers use this to distrust scores computed on very short texts."""
    return len(_squash(text))


def token_set(text: str) -> set[str]:
    """Similarity feature set: character bigrams of the date/digit-stripped text.

    Chinese entries have no word boundaries, so whitespace tokens would crush a
    whole sentence into one token and similarity would read 0; character
    bigrams are robust for both Chinese and English. Trailing date/source
    stamps are a writing-discipline requirement, not content, so they are
    stripped before comparison — otherwise two versions of one fact score
    lower purely because their dates differ. Very short texts degrade to a
    character set. Identical to deploy-pack ``memory_health.token_set``."""
    squashed = _squash(text)
    if len(squashed) < 2:
        return set(squashed)
    return {squashed[i:i + 2] for i in range(len(squashed) - 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@runtime_checkable
class SimilarityBackend(Protocol):
    """Interchangeable similarity scorer. ``score`` returns 0.0–1.0."""

    name: str

    def score(self, text_a: str, text_b: str) -> float:
        ...


class BigramSimilarityBackend:
    """Default backend: character-bigram Jaccard (see module docstring)."""

    name = "bigram"

    def score(self, text_a: str, text_b: str) -> float:
        return jaccard(token_set(text_a), token_set(text_b))


_DEFAULT_BACKEND = BigramSimilarityBackend()


def get_similarity_backend(name: Optional[str] = None) -> SimilarityBackend:
    """Resolve the configured backend; unknown/future names fall back to bigram."""
    if name and name != BigramSimilarityBackend.name:
        logger.warning("memory similarity backend %r is not available in core "
                       "(no embeddings client); falling back to 'bigram'.", name)
    return _DEFAULT_BACKEND


def similarity(text_a: str, text_b: str, backend: Optional[SimilarityBackend] = None) -> float:
    return (backend or _DEFAULT_BACKEND).score(text_a, text_b)


def similar_entries(query: str, entries: list[str], threshold: float,
                    limit: int = 3, backend: Optional[SimilarityBackend] = None) -> list[tuple[int, float]]:
    """``[(index, score)]`` for entries scoring >= *threshold* against *query*,
    best first (ties keep file order)."""
    backend = backend or _DEFAULT_BACKEND
    scored = [(i, backend.score(query, entry)) for i, entry in enumerate(entries)]
    hits = [(i, s) for i, s in scored if s >= threshold]
    hits.sort(key=lambda p: (-p[1], p[0]))
    return hits[:limit]


def candidate_pairs(entries: list[str], threshold: float,
                    backend: Optional[SimilarityBackend] = None) -> dict:
    """Duplicate/contradiction CANDIDATES inside one entry list — never a verdict.

    Returns ``{"exact_groups": [[indices]...], "similar_pairs": [(i, j, score)...]}``:
    normalized-identical groups (the deploy-pack health check's 实锤重复） and
    bigram-similar pairs at or above *threshold*, best first. Exact groups are
    not repeated in similar_pairs."""
    backend = backend or _DEFAULT_BACKEND
    norms = [normalize(e) for e in entries]
    groups: dict[str, list[int]] = {}
    for i, n in enumerate(norms):
        groups.setdefault(n, []).append(i)
    exact_groups = [idxs for idxs in groups.values() if len(idxs) > 1]
    pairs: list[tuple[int, int, float]] = []
    for i in range(len(entries)):
        for j in range(i + 1, len(entries)):
            if norms[i] == norms[j]:
                continue
            score = backend.score(entries[i], entries[j])
            if score >= threshold:
                pairs.append((i, j, score))
    pairs.sort(key=lambda p: (-p[2], p[0], p[1]))
    return {"exact_groups": exact_groups, "similar_pairs": pairs}


def consolidation_candidate_report(memories_dir: Path, threshold: float) -> dict:
    """Candidate pairs for BOTH built-in stores under *memories_dir*.

    The framework-side entry the nightly consolidation job calls (directly or
    via ``hermes memory candidates``): it only REPORTS pairs; merging follows
    the deploy-pack consolidation protocol and human review, never this code."""
    from tools.memory_tool_store import MemoryStore

    report: dict[str, dict] = {}
    for target, filename in (("memory", "MEMORY.md"), ("user", "USER.md")):
        path = Path(memories_dir) / filename
        entries = MemoryStore._read_file(path) if path.is_file() else []
        report[target] = {"file": filename, "entries": entries, **candidate_pairs(entries, threshold)}
    return report


def _snippet(text: str, n: int = 60) -> str:
    one = " ".join(text.split())
    return one[:n] + ("…" if len(one) > n else "")


def render_candidates_markdown(report: dict, threshold: float) -> str:
    """Markdown rendering of ``consolidation_candidate_report`` (read-only)."""
    out = [f"# 记忆整理候选对（相似阈值 {threshold}）", "",
           "仅候选，不自动合并——判定按《记忆整理规程》执行（合并 / 新替旧 / 两条都留 / 待裁决）。", ""]
    for target in ("memory", "user"):
        section = report[target]
        entries = section["entries"]
        out.append(f"## {section['file']}（{len(entries)} 条）")
        out.append("")
        if section["exact_groups"]:
            out.append(f"### 规范化后完全相同的条目组（{len(section['exact_groups'])} 组）")
            for idxs in section["exact_groups"]:
                out.append(f"- 条目 {'、'.join('#' + str(i + 1) for i in idxs)}：{_snippet(entries[idxs[0]])}")
            out.append("")
        if section["similar_pairs"]:
            out.append(f"### 高相似条目对（{len(section['similar_pairs'])} 对，疑似重复或新旧两版）")
            for i, j, score in section["similar_pairs"]:
                out.append(f"- #{i + 1} 与 #{j + 1}（相似度 {score:.2f}）")
                out.append(f"  - #{i + 1}：{_snippet(entries[i])}")
                out.append(f"  - #{j + 1}：{_snippet(entries[j])}")
            out.append("")
        if not section["exact_groups"] and not section["similar_pairs"]:
            out.append("无候选对。")
            out.append("")
    return "\n".join(out)
