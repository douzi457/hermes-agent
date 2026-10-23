#!/usr/bin/env bash
# gateway 健康探针（D1 常驻底座的外部自检）。
# 职责：确认 gateway 与 cron 调度还活着；死了只报告并留痕，
# 是否自动拉起由 AUTO_RESTART 控制（默认关，先报告再说，防抖动刷屏）。
#
# 挂法示例（系统 crontab，每 10 分钟）：
#   */10 * * * * HERMES_HOME=$HOME/.hermes /path/to/health-probe.sh >> $HOME/.hermes/duty/health-probe.log 2>&1
# Windows 用任务计划按同等间隔运行等价检查（hermes gateway status），
# 或直接以 `hermes gateway status` 的输出为准人工巡检。
#
# 判定依据：`hermes gateway status` 与 `hermes cron status` 两个官方命令
# （hermes_cli/subcommands/gateway.py、cron.py 均有 status 子命令）。
# 本脚本不解析它们的完整输出语义，只看退出码 + 关键词 crude 匹配；
# 若某版本 status 输出格式变化导致误报，以部署时实际输出为准调整 GREP 词。
set -u

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
export HERMES_HOME
AUTO_RESTART="${AUTO_RESTART:-0}"
STAMP="$(date '+%Y-%m-%d %H:%M:%S')"

fail=0

gw_out="$(hermes gateway status 2>&1)"; gw_rc=$?
if [ $gw_rc -ne 0 ] || printf '%s' "$gw_out" | grep -qiE 'not running|stopped|no gateway'; then
  echo "[$STAMP] FAIL gateway status rc=$gw_rc"
  fail=1
else
  echo "[$STAMP] OK gateway"
fi

cron_out="$(hermes cron status 2>&1)"; cron_rc=$?
if [ $cron_rc -ne 0 ]; then
  echo "[$STAMP] FAIL cron status rc=$cron_rc"
  fail=1
else
  echo "[$STAMP] OK cron"
fi

if [ "$fail" -eq 1 ] && [ "$AUTO_RESTART" = "1" ]; then
  echo "[$STAMP] attempting restart: hermes gateway start"
  hermes gateway start 2>&1 || echo "[$STAMP] restart command failed"
fi

exit "$fail"
