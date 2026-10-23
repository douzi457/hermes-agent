# Job 01 · 巡检备稿（patrol-draft）

- **用途**：定时巡检台账在册事项的触发条件，命中的写成备稿放 drafts，只备稿不投递（投递归 Job 02）。
- **调度**：每 2 小时。`every 2h` 或 5 段 cron `0 */2 * * *`（两种写法均见 `cron/AGENTS.md` 的调度格式说明）。
- **登记命令**（部署时执行一次；引号内提示词可改为从文件粘贴）：

```bash
hermes cron create "every 2h" "<见下方提示词全文>" \
  --name patrol-draft --deliver local --skill duty-officer
```

`--deliver local` = 备稿段不向用户投递任何东西；失败通知仍按 failure 规则走（`hermes cron create --help` 为准）。

- **验收点**：`hermes cron list` 能看到 patrol-draft 且状态启用；手动 `hermes cron run <job_id>` 触发一次后，`$HERMES_HOME/duty/drafts/` 出现当日备稿文件（无命中时文件内只有一行「本轮无命中」）。

## 提示词全文

你是值班巡检员，执行 duty-officer 技能的 B 段（备稿）。步骤：

1. 用 `read_file` 读 `$HERMES_HOME/duty/WATCHLIST.md`，只处理状态为「在册」的行。
2. 逐行核对触发条件：能用工具当场核实的（文件状态、命令输出、网页内容）逐项核实；核实不了的在本轮备稿里标注「未核实」，不要猜。
3. 命中的事项写成备稿，追加到 `$HERMES_HOME/duty/drafts/<今天日期>-patrol.md`（不存在则新建）。每条备稿格式：`## <事项名>` + 一句结论 + 证据（链接、文件路径或命令输出摘要）+ 采集时间（本地时区，精确到分钟）。
4. 没有任何命中时，在当日备稿文件写一行「本轮无命中（HH:MM）」后结束。
5. 本轮只备稿，禁止直接向用户发送任何消息，禁止修改台账（回写是筛选段的职责）。
6. 若台账文件不存在或格式损坏，停止并在输出里报告，不要自行重建台账。
