#!/usr/bin/env bash
# M4：把 memories 目录 git 化（纯本地仓库）+ 首次提交。
# 幂等：已初始化过就只补一次「当前状态」提交，不重复 init、不覆盖历史。
# 回滚方法：cd $HERMES_HOME/memories && git log --oneline 查看，
#          git checkout <commit> -- MEMORY.md 只恢复单个文件到某版，
#          或 git restore --source=<commit> . 整目录恢复（先确认再执行）。
set -eu

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
MEM_DIR="$HERMES_HOME/memories"

mkdir -p "$MEM_DIR"
cd "$MEM_DIR"

if ! command -v git >/dev/null 2>&1; then
  echo "git 未安装，先装 git 再运行本脚本" >&2
  exit 1
fi

if [ ! -d .git ]; then
  git init -q
  # 只在本仓库内设身份，不污染用户全局 git 配置
  git config user.name "hermes-memory-backup"
  git config user.email "hermes@localhost"
  echo "已初始化 memories 本地 git 仓库：$MEM_DIR"
else
  echo "memories 已是 git 仓库，跳过 init"
fi

git add -A
if git diff --cached --quiet; then
  echo "无变化可提交"
else
  git commit -q -m "memory snapshot $(date '+%Y-%m-%d %H:%M:%S')"
  echo "已提交当前记忆快照：$(git rev-parse --short HEAD)"
fi
