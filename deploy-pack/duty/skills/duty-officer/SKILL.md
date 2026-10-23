---
name: duty-officer
description: "值班官规程: 台账、备稿筛选投递与失败上报."
version: 1.0.0
author: douzi457
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [duty, proactive, cron, delivery]
    category: productivity
---

# Duty Officer Skill

本技能是值班系统的操作规程：管台账（WATCHLIST）、管备稿→筛选→投递管线、管失败上报。它不替代 cron——cron 只负责按时唤起一轮会话，判断、筛选、回写台账全靠本规程执行。它也不发明新的投递渠道：投递走登记 job 时约定的渠道。

## When to Use

- 任何值班 cron job 被唤起时（巡检备稿、筛选投递、晚间汇总）。
- 准备主动给用户推送任何非回复性消息之前。
- 用户登记、暂停或取消一件「帮我盯着」的事时。
- 值班 job 失败、体检脚本报错、gateway 异常被发现时。

## Prerequisites

- 值班目录在 `$HERMES_HOME/duty/`：`WATCHLIST.md`（台账）与 `PREFERENCES.md`（偏好）必须存在；不存在时先从部署装配包的模板复制并请用户确认内容，不要凭空编造事项。
- 备稿目录 `$HERMES_HOME/duty/drafts/` 存在（巡检 job 首次运行时创建）。
- 相关命令经 `terminal` 执行；执行前用 `hermes cron --help` 确认子命令存在（本规程用到的：`list`、`status`、`runs`、`incidents`、`doctor`、`run`、`edit`、`pause`、`resume`，出自 `hermes_cli/subcommands/cron.py`，部署时以实际 --help 为准）。

## How to Run

值班工作只有两个入口：被 cron 唤起时，按 Quick Reference 找到本次 job 的职责段执行；被用户当面交办时，先登记台账再谈执行。全程用 `read_file` 读台账与偏好、用 `patch` 回写，禁止整文件重写台账（会冲掉用户手改的行）。

## Quick Reference

- 台账：`$HERMES_HOME/duty/WATCHLIST.md`；偏好：`$HERMES_HOME/duty/PREFERENCES.md`
- 备稿：`$HERMES_HOME/duty/drafts/YYYY-MM-DD-<来源>.md`，每条备稿带来源与时间戳
- 筛选五发：时敏、已变、被要求、待决策、新机会
- 筛选五不发：已失效、已处理、未证实、偏好排除、暂不值得（攒晚报）
- 自查：`hermes cron list`、`hermes cron incidents`、`hermes cron doctor`、`hermes gateway status`

## Procedure

### A. 登记事项（用户说「帮我盯着 X」时）

1. 用 `read_file` 读 WATCHLIST.md，先查销项存档与在册行，确认不是重复登记。
2. 向用户确认四件事再落笔：触发条件、交付去向、停止条件、安静时段是否豁免。
3. 用 `patch` 在在册表追加一行；需要定时唤起的，另行登记 cron job，并在「负责 job」列写 job 名。

### B. 备稿（巡检 job 执行）

1. 按 job 提示词搜集，只把命中触发条件的内容写成备稿，逐条注明来源（链接/文件/命令输出）与采集时间。
2. 没有命中就写一行「本轮无命中」并结束，不许凑数。
3. 备稿只写 drafts，不直接投递——投递是筛选段的事。

### C. 筛选与投递（筛选 job 或当面推送前）

1. 读 WATCHLIST.md 与 PREFERENCES.md，再读待投递的备稿。
2. 逐条复核五问：还新鲜吗？情况与上次交付相比变了吗？用户可能已自行处理吗（先查最近会话与相关文件状态）？与偏好冲突吗？证据是单源还是已核实？
3. 按五发/五不发分档：直发 / 攒入晚报 / 静默归档。未证实的单源信息最多进晚报「待核实」区，禁止单独推送。
4. 安静时段内只攒稿；时敏破例要在正文第一行写明破例原因。
5. 投递正文格式：先结论、再证据（含出处）、最后「需要你做什么」（没有就写无）。

### D. 投递后回写

1. 用 `patch` 更新台账对应行的「最近交付」为本次时间+一句话摘要。
2. 停止条件已满足的，当场把行移到销项存档并写明原因。
3. 本轮被静默归档的备稿在 drafts 文件尾部标注归档原因，便于事后审计。

### E. 失败上报

1. job 失败、脚本非零退出、gateway 状态异常：先自查 `hermes cron runs` 与 `hermes cron incidents` 定位是偶发还是持续。
2. 偶发且下轮可自愈：在台账对应行备注，不打扰用户。
3. 持续失败或影响投递：在下一次与用户的交互开头主动报告——什么坏了、影响什么、你已做了什么、建议怎么处理；不许等用户发现。
4. 需要停用某 job 时用 `hermes cron pause`，并回写台账注明，不许直接删 job 蒙混。

## Pitfalls

- 抢跑投递：巡检段顺手把备稿发了，绕过筛选——这是值班系统退化成闹钟的最常见路径。
- 整文件重写台账：会冲掉用户手改与销项存档，一律用 `patch` 增改行。
- 拿旧备稿充数：备稿超过其时效（默认 24 小时，时敏类 2 小时）必须重新核实，不能直接投递。
- 审批误判：值班 job 里遇到危险命令被拒（approvals 的无人场景默认 deny）是正确行为，应调整 job 内容绕开，而不是建议放开审批。

## Verification

- 任意抽一条最近投递：能在台账里找到对应行且「最近交付」与实际投递时间一致。
- 任意抽一条被归档的备稿：文件尾部有归档原因，且原因属于五不发之一。
- 模拟一次失败（如暂停 gateway 后触发 job）：下一轮交互或晚报中能看到失败报告，且台账有备注。
