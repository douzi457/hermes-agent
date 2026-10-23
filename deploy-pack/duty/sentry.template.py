#!/usr/bin/env python3
"""哨兵脚本模板（D2 触发矩阵 · 条件轮询）。

职责：只读检查 ONE 个条件，不做任何判断之外的动作。
  - 命中：第一行打印 `WAKE <一句话说明>`，随后可附证据（每行一条）。
  - 未命中：只打印 `SILENT`。
调用方按第一行决定是否唤起 agent —— 未命中时 agent 根本不该被叫醒。

三种接法（命令语义以 `hermes cron create --help` 为准）：
  1) 经典看门狗：`hermes cron create "*/10 * * * *" --script <本文件> --no-agent`
     —— stdout 原样投递，SILENT 时请在脚本外层约定空输出即静默；
     注意 --no-agent 模式下本脚本的 SILENT 行也会被投递，
     更推荐接法 2。
  2) 监控模式：`hermes cron create "*/10 * * * *" "<唤起后的提示词>" --monitor-script <本文件>`
     —— 输出逐字节哈希不变时框架直接跳过 agent 轮次；只有输出变化
     （如条件从未命中变命中、或证据数值变了）才唤起 agent 并注入 diff。
     因此本脚本的输出必须稳定：禁止打印当前时间、随机数等每次必变的字样。
  3) 普通 --script：stdout 注入 agent 提示词，由 agent 读第一行自行决定。

部署：复制到 $HERMES_HOME/scripts/ 下改名为实际用途（如 watch_price.py），
      cron 的 --script 只接受该目录下的脚本（见 hermes_cli/subcommands/cron.py）。
改造点：只改 check() 一个函数与顶部常量；保持纯标准库、只读、无副作用、
      运行时间 < 10 秒（它会被高频调用）。
状态：需要跨轮比较时，把上次的值写在 $HERMES_HOME/scripts/.sentry-state/
      下以脚本名命名的 json 里（模板已含读写骨架），不要写进记忆或台账。
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

# ---- 可调常量 -------------------------------------------------------------
# 被监视的文件（示例条件：某文件内容发生变化）。改成你的真实条件来源。
_TARGET_RAW = os.environ.get("SENTRY_TARGET", "").strip()
TARGET_FILE = Path(_TARGET_RAW).expanduser() if _TARGET_RAW else None
STATE_DIR = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")) / "scripts" / ".sentry-state"


def _state_path() -> Path:
    return STATE_DIR / (Path(__file__).stem + ".json")


def _load_state() -> dict:
    try:
        return json.loads(_state_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_state(state: dict) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        _state_path().write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass  # 状态写不进去时宁可下轮重复报告，也不让哨兵自己崩掉并刷屏


def check() -> tuple[bool, list[str]]:
    """返回 (是否命中, 证据行列表)。示例：目标文件内容哈希与上轮不同 = 命中。

    换成真实条件时保持三条纪律：只读、不抛异常到顶层（内部异常按未命中处理
    并在证据里注明）、输出稳定（同状态同输出，监控模式靠哈希判变）。
    """
    if TARGET_FILE is None:
        return False, ["SENTRY_TARGET 未设置，哨兵未配置"]
    try:
        data = TARGET_FILE.read_bytes()
    except OSError as exc:
        return False, [f"目标不可读: {exc}"]
    digest = hashlib.sha256(data).hexdigest()
    state = _load_state()
    if state.get("sha256") == digest:
        return False, []
    _save_state({"sha256": digest})
    return True, [f"文件内容已变化: {TARGET_FILE}", f"sha256: {digest[:16]}…"]


def main() -> int:
    hit, evidence = check()
    if hit:
        print("WAKE " + (evidence[0] if evidence else "条件命中"))
        for line in evidence[1:]:
            print(line)
    else:
        print("SILENT")
        for line in evidence:  # 未命中但值得留痕的信息走 stderr，不污染哈希面
            print(line, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
