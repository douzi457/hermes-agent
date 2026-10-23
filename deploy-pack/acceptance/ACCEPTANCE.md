# 新机部署八项验收清单

每台新机部署完逐项执行，全过才算交付。命令以仓库已核实的子命令为准；
标「以 --help 为准」处在部署机上先确认再执行。建议按顺序做，后项依赖前项。

## 1. 首启种入

- **步骤**：在全新 HERMES_HOME 完成 `hermes setup` 与首启；检查
  `$HERMES_HOME/SOUL.md`、`$HERMES_HOME/memories/` 是否就位；若已按装配包
  步骤 4 铺个人版 SOUL，核对 SOUL.md 内容与填好的模板一致。
- **通过标准**：SOUL.md 存在且为预期版本（个人版或出厂中文纪律版，
  二选一必须明确，不许含糊）；memories/ 目录存在。
- **不通过查**：HERMES_HOME 是否指错（`hermes config path`）；
  setup 是否真正跑完。

## 2. 体检落档

- **步骤**：运行 `hermes doctor --fix`；再跑 `hermes config get machine.tier`
  与 `hermes config get machine.summary`；检查与 config.yaml 同目录的
  ENVIRONMENT.md。
- **通过标准**：tier 非空（T0–T3 之一）；ENVIRONMENT.md 存在且档位与
  config 一致；本机实测数字（核数/内存）与机器真实规格对得上。
  NVIDIA 机器另注：Linux 下显存走 D 批 nvidia-smi 兜底，定档低于预期时
  先查 nvidia-smi 在部署机上是否可执行，不要先怀疑定档逻辑。
- **不通过查**：`hermes doctor`（不带 --fix）的完整输出。

## 3. 技能种入

- **步骤**：确认 `$HERMES_HOME/skills/` 下有 `first-run-tour`（内置，随
  CLI 启动自动同步）、`duty-officer`、`memory-hygiene`（装配包复制）；
  再用 `hermes skills --help` 确认列表子命令并实际列一次（以 --help 为准）。
- **通过标准**：三个技能目录都在且 SKILL.md 可读；起一个新会话说
  「新机怎么配」，能触发 first-run-tour 的讲解流程。
- **不通过查**：复制是否漏了整个目录（只复制 SKILL.md 一个文件不行，
  技能是一个目录）；`platforms` 是否把本机系统排除在外。

## 4. 系统提示摘要

- **步骤**：全新会话里问：「你跑在什么机器上？把你的机器摘要原样报给我。」
- **通过标准**：回答包含与第 2 项一致的档位摘要（形如
  `Machine: T1 (standard) · 2 cores · 7.7G RAM · GPU: none · ...`）；
  说明 B 批的摘要注入在真会话里生效，而非只有档案文件好看。
- **不通过查**：第 2 项是否真落档（摘要注入读的是 machine 档案）。

## 5. cron 命令面与值班 job 就位

- **步骤**：`hermes cron status`、`hermes cron list`。
- **通过标准**：status 显示调度在运行（它依赖 gateway 常驻，见第 7 项
  前提）；list 里六个 job（patrol-draft、delivery-filter、evening-digest、
  memory-consolidate、memory-health-weekly、goals-relations-weekly）
  全部在册且启用。
- **不通过查**：gateway 是否在跑；登记命令是否报错被忽略。

## 6. 记忆跨进程读回

- **步骤**：会话 A 里让 Hermes 用 memory 工具记一条带暗号的测试事实
  （如「测试暗号：紫色河马 2026」）；若 write_approval 拦截，按提示用
  `/memory pending` 批准；完全退出会话 A；开全新会话 B 问暗号是什么；
  最后 `read_file` 或直接查看 `$HERMES_HOME/memories/MEMORY.md`。
- **通过标准**：会话 B 能答出暗号；MEMORY.md 盘上有该条且带日期与来源
  标注；说明写入、落盘、跨会话注入三段都通。
- **不通过查**：待批区是否还有未批准的写入；条目是否被写进了 journal
  而不是 MEMORY.md（分层错误）。

## 7. 值班 job 干跑（备稿 → 筛选 → 模拟投递）

- **前提**：gateway 在跑（`hermes cron run` 是「下一 tick 执行」，无常驻
  调度则不会触发）。
- **步骤**：在 WATCHLIST 登记一条可当场命中的测试事项（如盯某个本地
  文件的变化）；`hermes cron run <patrol-draft 的 job_id>`，查
  `duty/drafts/` 当日备稿；再 `hermes cron run <delivery-filter 的 job_id>`；
  最后查投递结果与台账。
- **通过标准**：备稿文件生成且带来源与时间戳；筛选后测试事项被投递
  （或被正确攒/归档并写明原因）；WATCHLIST 对应行「最近交付」已回写。
  三段缺一不算过——只备稿不投递是闹钟，只投递不回写是没台账。
- **不通过查**：`hermes cron runs` 与 `hermes cron incidents` 的最近记录。

## 8. 备份回滚演练

- **步骤**：先确认 memories 已 git 化且有至少一次提交、backups/snapshots
  里有至少一份快照；然后故意写坏一条：把 MEMORY.md 里一条测试条目改成
  乱码并保存；执行回滚（`cd $HERMES_HOME/memories && git log --oneline`
  找到写坏前的提交，`git checkout <commit> -- MEMORY.md`）；重新读文件。
- **通过标准**：回滚后被写坏的条目恢复原样，其余条目不受影响；
  快照目录里的那份 MEMORY.md 副本也可读（双保险都在）。
- **不通过查**：git-backup-init.sh 是否真正执行过；整理 job 的
  前后提交是否在发生（git log 里应能看到 pre/post-consolidate 提交）。
