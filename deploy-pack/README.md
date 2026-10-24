# Hermes E1′ 部署装配包（私有）

把改造版 Hermes（独立仓 main，含 A–D 批）在一台新机器上装成「有值班、
记忆不乱、审批最严」的个人部署，靠的全是这一包：私有配置覆盖、加厚
SOUL、值班包（台账/偏好/技能/6 个 job 模板/哨兵/常驻方案）、记忆包
（分层约定/纪律技能/整理规程/体检脚本/备份脚本）、八项验收清单。

> **私有包**：只放部署者自己的机器与私有存储，**绝不提交进公开仓库**。
> 包里所有配置键、命令、路径均已在独立仓 main（74b9d2d3）的代码/文档里
> 核实；核实清单见各文件内注释。少数平台相关细节标注了「以部署时
> `hermes <命令> --help` 实际输出为准」。

## 包结构与部署去向

| 包内路径 | 部署去向 |
|----------|----------|
| `config/config.private.template.yaml` | 合并进 `$HERMES_HOME/config.yaml`（或逐项 `hermes config set`） |
| `soul/SOUL.private.template.md` | 填好后存为 `$HERMES_HOME/SOUL.md` |
| `duty/WATCHLIST.template.md` / `PREFERENCES.template.md` | `$HERMES_HOME/duty/` 下去掉 `.template` |
| `duty/skills/duty-officer/` | 整个目录复制到 `$HERMES_HOME/skills/` |
| `duty/jobs/01–06` | 部署当天逐条按文件内命令登记（不是复制文件） |
| `duty/sentry.template.py` | 按需改名复制到 `$HERMES_HOME/scripts/` |
| `duty/gateway-service/` | 常驻方案四选一（见步骤 7） |
| `memory/`（README/规程/脚本/技能） | 按 `memory/README.md` 的部署顺序执行 |
| `acceptance/ACCEPTANCE.md` | 最后逐项打勾 |

`$HERMES_HOME` 默认 `~/.hermes`，以 `hermes config path` 的输出为准。

## 主脑选型纪律（先读这条，再填 Key）

复刻体验的第一变量是主脑，不是框架：

- **主脑用你能稳定付费的最强模型**，不要在主脑上省钱——纪律、求真、
  长任务稳定性都随主脑档次涨落，SOUL 写得再好也补不回模型判断力。
- **杂活下放 aux**（配置模板的 auxiliary 段）：compression（压缩摘要）、
  approval（审批分类）、background_review（记忆复盘）、curator（技能整理）、
  title_generation（会话标题）全部指派便宜快模型。仓库自身注释即如此建议
  （approval 任务注："a fast/cheap model is recommended"），且框架在 aux
  不可用时的兜底就是一款 flash 级模型。
- 子代理（delegation）默认继承主脑（config 里 delegation.model 为空 =
  inherit），这是对的，不要给子代理单独降档——子代理干的是正经活。
- fallback 链配一条**跨厂商**备用：主脑限流时值班链不至于整夜哑火。

## 部署顺序（每台新机从零到验收）

0. **前置**：Hermes 已装好（按仓库 README/setup 脚本）、`git`、`python3`
   可用；机器已跑过体检定档（`hermes doctor --fix`，ENVIRONMENT.md 已生成）。
1. **首启向导**：跑 `hermes setup` 完成账号与渠道的官方配置；第一次对话
   让内置 first-run-tour 技能带一遍定档讲解。
2. **填 Key（部署者自填，任何人不经手）**：`hermes config env-path` 找到
   `.env`，按所选 provider 填 Key（如走 OpenRouter 填 `OPENROUTER_API_KEY`，
   变量名以该文件内注释与 provider 文档为准）。Key 只进 `.env`，
   不进 config.yaml、不进记忆、不进本包任何文件。填完顺手收紧 `.env`
   权限：POSIX `chmod 600`、Windows 确认仅本人账户可读——`hermes doctor`
   有专门检查这一项，POSIX 下 `--fix` 会自动 chmod 600。
3. **合并私有配置**：把 `config/config.private.template.yaml` 的段落合并进
   config.yaml（approvals manual、verify_on_stop、max_turns、记忆
   8000/3000 + write_approval、aux 分工、fallback 链），逐项注释里有键出处
   与按档调整法，改完用 `hermes config show` 复核一遍。
4. **铺 SOUL**：把 `soul/SOUL.private.template.md` 填好（至少填文末
   「关于我」小节）存为 `$HERMES_HOME/SOUL.md`。注意：写了个人版 SOUL 后，
   出厂 SOUL 的自动升级不再覆盖它，这是预期行为。
5. **铺记忆包**：按 `memory/README.md` 的部署顺序 1–6 执行（体检脚本就位、
   memories git 化、快照挂上、memory-hygiene 技能就位、分层目录建好、
   基线体检跑一次）。
6. **铺值班包**：建 `$HERMES_HOME/duty/` 与 `duty/drafts/`；WATCHLIST 与
   PREFERENCES 去掉 `.template` 后放入（内容按自己真实情况改，模板里的
   示例行删掉或改掉）；duty-officer 技能复制到 `$HERMES_HOME/skills/`。
7. **gateway 常驻（D1，死前提）**：首选仓库自带 `hermes gateway install`
   （systemd/launchd/Windows 计划任务后端都有），`hermes gateway status`
   确认在跑；官方路径不合用时再看 `duty/gateway-service/` 里的手动模板。
   再把 `health-probe.sh` 挂进系统 cron（每 10 分钟）。**gateway 不常驻，
   cron 值班就不存在**——这一步没过，后面全部免谈。
8. **登记 6 个值班 job**：按 `duty/jobs/01–06` 逐条执行登记命令，
   `hermes cron list` 确认六个都在且启用。登记完先逐个
   `hermes cron run <job_id>` 干跑一遍（run 是「下一 tick 执行」，需
   gateway 在跑），输出不对当场改提示词。
9. **跑八项验收**：按 `acceptance/ACCEPTANCE.md` 逐项打勾，全过才算
   这台机器交付完成。1 核 1G 的机器尤其不许跳过——T0 定档只有合成测试，
   没有真机证据，验收就是它的真机证据。

## 日常运维速查

- 记忆：每晚 Job 04 自动整理并出变更摘要；每周一 Job 05 体检报告；
  待批写入用 `/memory pending` 抽查；回滚见 memory/README.md。
- 值班：台账在 `$HERMES_HOME/duty/WATCHLIST.md`；加一件要盯的事，
  直接对 Hermes 说「帮我盯着 X」并确认触发/去向/停止条件即可
  （duty-officer 技能规程 A 段）。
- 巡检：`hermes cron status` / `hermes cron incidents` /
  `hermes gateway status` 三件套；健康探针日志在
  `$HERMES_HOME/duty/health-probe.log`（按挂载方式）。
