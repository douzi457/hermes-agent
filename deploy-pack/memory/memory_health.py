#!/usr/bin/env python3
"""记忆体检脚本（M3 整理前体检 / M6 每周体检共用）。纯标准库。

读 $HERMES_HOME/memories 下的 MEMORY.md 与 USER.md，按 Hermes 原生格式解析
条目（条目间分隔符为 "\\n§\\n"，见仓库 tools/memory_tool_store.py 的
ENTRY_DELIMITER），输出一份 Markdown 报告到 stdout：

  - 每文件的条目数、字符数、距上限百分比（上限取值优先级：
    --memory-limit/--user-limit 参数 > 同级 config.yaml 里的
    memory_char_limit/user_char_limit > fork 出厂默认 4400/2200）
  - 近似查重：规范化后完全相同的条目组；以及字符 bigram Jaccard 相似度
    >= 阈值（默认 0.6）的条目对（只报候选，不下"重复"结论）
  - 无日期条目（条目内找不到 YYYY-MM-DD 形式的日期）
  - 超 90 天未动条目（以条目内最后一个日期为该条日期）

只读，不改任何文件。用法：
  python3 memory_health.py [memories目录] [--memory-limit N] [--user-limit N]
                           [--similarity 0.8] [--stale-days 90]
目录省略时取 $HERMES_HOME/memories，再省略取 ~/.hermes/memories。
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

ENTRY_DELIMITER = "\n§\n"  # tools/memory_tool_store.py: ENTRY_DELIMITER
FORK_DEFAULTS = {"MEMORY.md": 4400, "USER.md": 2200}
DATE_RE = re.compile(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})")
MAX_PAIRS_REPORTED = 50


def split_entries(raw: str) -> list[str]:
    """与 MemoryStore 相同的切分：按完整分隔符切，strip 后非空即一条。"""
    return [e for e in (x.strip() for x in raw.split(ENTRY_DELIMITER)) if e]


def normalize(text: str) -> str:
    """粗规范化：小写、去标点空白差异，供近似查重。"""
    folded = text.lower()
    folded = re.sub(r"[^\w]+", " ", folded, flags=re.UNICODE)
    return " ".join(folded.split())


def token_set(text: str) -> set[str]:
    """相似度特征集：去日期与数字后的字符 bigram。

    中文条目没有空格分词，空白分词会把整句压成一个 token、相似度恒为 0；
    字符 bigram 对中英文都稳健。条目尾部的日期/来源标注是纪律要求而非
    内容，先剥掉再比，否则同一事实的两个版本相似度会被日期稀释。
    极短文本退化为字符集。
    """
    no_dates = DATE_RE.sub(" ", text)
    no_digits = re.sub(r"\d+", " ", no_dates)
    squashed = normalize(no_digits).replace(" ", "")
    if len(squashed) < 2:
        return set(squashed)
    return {squashed[i:i + 2] for i in range(len(squashed) - 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def entry_date(text: str) -> date | None:
    """条目内最后一个合法日期；找不到返回 None。"""
    found = None
    for m in DATE_RE.finditer(text):
        try:
            found = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            continue
    return found


def read_config_limits(home: Path) -> dict[str, int]:
    """从 config.yaml 粗解析 memory 上限（无 yaml 库时的行级匹配，够用）。"""
    cfg = home / "config.yaml"
    limits: dict[str, int] = {}
    if not cfg.is_file():
        return limits
    try:
        text = cfg.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return limits
    for key, fname in (("memory_char_limit", "MEMORY.md"), ("user_char_limit", "USER.md")):
        m = re.search(rf"^\s*{key}\s*:\s*(\d+)", text, flags=re.MULTILINE)
        if m:
            limits[fname] = int(m.group(1))
    return limits


def status_for(pct: float) -> str:
    if pct >= 95:
        return "🔴 危险（>=95%，写入随时被拒）"
    if pct >= 80:
        return "🟡 预警（>=80%，该整理腾位）"
    return "🟢 正常"


def analyze(path: Path, limit: int, similarity: float, stale_days: int, today: date) -> dict:
    raw = path.read_text(encoding="utf-8", errors="replace")
    entries = split_entries(raw)
    # 字符口径与 MemoryStore 一致：分隔符拼接后的总长
    joined_len = len(ENTRY_DELIMITER.join(entries)) if entries else 0
    pct = (joined_len / limit * 100) if limit else 0.0

    norms = [normalize(e) for e in entries]
    exact_groups: dict[str, list[int]] = {}
    for i, n in enumerate(norms):
        exact_groups.setdefault(n, []).append(i)
    exact_dups = [idxs for idxs in exact_groups.values() if len(idxs) > 1]

    sets = [token_set(e) for e in entries]
    sim_pairs: list[tuple[int, int, float]] = []
    for i in range(len(entries)):
        for j in range(i + 1, len(entries)):
            if norms[i] == norms[j]:
                continue  # 已在精确重复里
            s = jaccard(sets[i], sets[j])
            if s >= similarity:
                sim_pairs.append((i, j, s))
    sim_pairs.sort(key=lambda t: -t[2])

    no_date: list[int] = []
    stale: list[tuple[int, date]] = []
    for i, e in enumerate(entries):
        d = entry_date(e)
        if d is None:
            no_date.append(i)
        elif (today - d).days > stale_days:
            stale.append((i, d))

    return {
        "entries": entries,
        "joined_len": joined_len,
        "limit": limit,
        "pct": pct,
        "exact_dups": exact_dups,
        "sim_pairs": sim_pairs[:MAX_PAIRS_REPORTED],
        "sim_pairs_total": len(sim_pairs),
        "no_date": no_date,
        "stale": stale,
    }


def snippet(text: str, n: int = 60) -> str:
    one = " ".join(text.split())
    return one[:n] + ("…" if len(one) > n else "")


def main() -> int:
    ap = argparse.ArgumentParser(description="Hermes 记忆体检（只读）")
    ap.add_argument("memories_dir", nargs="?", default=None,
                    help="memories 目录（默认 $HERMES_HOME/memories）")
    ap.add_argument("--memory-limit", type=int, default=None)
    ap.add_argument("--user-limit", type=int, default=None)
    ap.add_argument("--similarity", type=float, default=0.6,
                    help="高相似候选阈值（默认 0.6：宁可多报候选，判定归规程）")
    ap.add_argument("--stale-days", type=int, default=90)
    args = ap.parse_args()

    if args.memories_dir:
        mem_dir = Path(args.memories_dir).expanduser()
    else:
        home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")).expanduser()
        mem_dir = home / "memories"
    home = mem_dir.parent

    cfg_limits = read_config_limits(home)
    limits = {
        "MEMORY.md": args.memory_limit or cfg_limits.get("MEMORY.md") or FORK_DEFAULTS["MEMORY.md"],
        "USER.md": args.user_limit or cfg_limits.get("USER.md") or FORK_DEFAULTS["USER.md"],
    }
    today = datetime.now().date()

    out: list[str] = []
    out.append(f"# 记忆体检报告（{today.isoformat()}）")
    out.append("")
    out.append(f"- 目录：`{mem_dir}`")
    out.append(f"- 相似阈值：{args.similarity}；陈旧界限：{args.stale_days} 天")
    out.append("")
    out.append("| 文件 | 条目数 | 字符数 | 上限 | 占用 | 状态 |")
    out.append("|------|--------|--------|------|------|------|")

    sections: list[str] = []
    for fname in ("MEMORY.md", "USER.md"):
        path = mem_dir / fname
        if not path.is_file():
            out.append(f"| {fname} | — | — | {limits[fname]} | — | ⚪ 文件不存在 |")
            sections.append(f"## {fname}\n\n文件不存在，跳过。")
            continue
        r = analyze(path, limits[fname], args.similarity, args.stale_days, today)
        out.append(
            f"| {fname} | {len(r['entries'])} | {r['joined_len']} | {r['limit']} "
            f"| {r['pct']:.1f}% | {status_for(r['pct'])} |"
        )
        sec = [f"## {fname}", ""]
        if r["exact_dups"]:
            sec.append(f"### 规范化后完全相同的条目组（{len(r['exact_dups'])} 组）")
            for idxs in r["exact_dups"]:
                sec.append(f"- 条目 {'、'.join('#' + str(i + 1) for i in idxs)}：{snippet(r['entries'][idxs[0]])}")
            sec.append("")
        if r["sim_pairs"]:
            sec.append(
                f"### 高相似条目对（共 {r['sim_pairs_total']} 对，列前 {len(r['sim_pairs'])} 对；仅候选，需人工/规程判定）"
            )
            for i, j, s in r["sim_pairs"]:
                sec.append(f"- #{i + 1} 与 #{j + 1}（相似度 {s:.2f}）")
                sec.append(f"  - #{i + 1}：{snippet(r['entries'][i])}")
                sec.append(f"  - #{j + 1}：{snippet(r['entries'][j])}")
            sec.append("")
        if r["no_date"]:
            sec.append(f"### 无日期条目（{len(r['no_date'])} 条，违反「条带日期」纪律，整理时补或降级）")
            for i in r["no_date"]:
                sec.append(f"- #{i + 1}：{snippet(r['entries'][i])}")
            sec.append("")
        if r["stale"]:
            sec.append(f"### 超 {args.stale_days} 天未动条目（{len(r['stale'])} 条，复核是否仍成立）")
            for i, d in r["stale"]:
                sec.append(f"- #{i + 1}（{d.isoformat()}）：{snippet(r['entries'][i])}")
            sec.append("")
        if not (r["exact_dups"] or r["sim_pairs"] or r["no_date"] or r["stale"]):
            sec.append("无重复候选、无无日期条目、无陈旧条目。")
            sec.append("")
        sections.append("\n".join(sec))

    out.append("")
    out.extend(sections)
    out.append("---")
    out.append("说明：字符口径与框架一致（条目以 `§` 分隔符拼接后的总长）；"
               "相似对只是整理候选，合并/替代的判定按《整理规程》执行；本脚本只读，不改任何文件。")
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
