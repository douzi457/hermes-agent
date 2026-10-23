#!/usr/bin/env bash
# M4 配套：state.db + memories 的每日快照轮转（保留最近 30 份）。
# 与 memories 内的 git 仓库分工：git 管条目级回滚，本脚本管整机级灾备
# （文件被截断、state.db 损坏这类 git 救不了的情况）。
# 建议挂系统 cron 每日一次，或并入值班晚报 job 前执行。幂等：重复运行
# 只是多出一份快照，不改源数据。
#
# 一致性提示：state.db 是 WAL 模式（database.journal_mode 出厂 wal），
# 活跃写入时直接拷贝可能差最后几笔未落盘事务——脚本会连 -wal/-shm
# 一并拷贝做尽力而为；严格一致请在 gateway 空闲时段运行。
set -eu

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
KEEP="${KEEP:-30}"
DEST_ROOT="${HERMES_BACKUP_DIR:-$HERMES_HOME/backups}/snapshots"
STAMP="$(date '+%Y%m%d-%H%M%S')"
DEST="$DEST_ROOT/snapshot-$STAMP"

mkdir -p "$DEST"

if [ -d "$HERMES_HOME/memories" ]; then
  cp -a "$HERMES_HOME/memories" "$DEST/memories"
fi

for f in state.db state.db-wal state.db-shm; do
  if [ -f "$HERMES_HOME/$f" ]; then
    cp -a "$HERMES_HOME/$f" "$DEST/$f"
  fi
done

echo "快照完成：$DEST"

# 轮转：按名字排序（时间戳命名即时间序），只留最近 KEEP 份
cd "$DEST_ROOT"
# shellcheck disable=SC2012
old="$(ls -d snapshot-* 2>/dev/null | sort | head -n "-$KEEP" || true)"
if [ -n "$old" ]; then
  printf '%s\n' "$old" | while IFS= read -r d; do
    [ -n "$d" ] && rm -rf -- "$d" && echo "已轮转删除旧快照：$d"
  done
fi
