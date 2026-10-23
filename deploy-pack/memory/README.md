# 记忆包（M1–M6 装配说明）

本目录是方案《值班系统还原 + 记忆防乱防丢方案》的记忆部分落地件：
M1 分层约定（本文）、M2 写入纪律（skills/memory-hygiene）、M3 整理规程
（consolidate-protocol.md + Job 04）、M4 版本备份（git-backup-init.sh +
snapshot.sh）、M5 单写者+审批（配置模板里 memory.write_approval: true）、
M6 每周体检（memory_health.py + Job 05）。

## M1 分层落位（约定，写死不商量）

部署位置：`$HERMES_HOME/memories/`

```
memories/
MEMORY.md 长期层只放结论：偏好、决定、承诺、已核实结果
USER.md 画像层只放用户画像：身份、习惯、雷区
journal/YYYY-MM-DD.md 轨迹层只追加：当日细节、被替代的旧结论原文
people/<姓名>.md 关系层一人一页：事实 + 关系性质 + 最后互动日期
archive/ 归档层失效条目移入，文件名带日期，不删除
.git/ M4 版本库（git-backup-init.sh 初始化）
```

要点：

- 框架原生只认 MEMORY.md / USER.md 两个文件（`tools/memory_tool.py` 的
get_memory_dir() → `$HERMES_HOME/memories`），并按字符上限**拒绝超限写入**
且全文注入系统提示。journal / people / archive 是约定层：不进系统提示、
不占上限，靠 `read_file` 按需读取——分层的意义就是给整理留降级空间，
不必为了腾位删历史。
- 预算：MEMORY.md 目标用量 ≤ 上限的 80%（个人部署 8000 → 目标 ≤6400）；
USER.md 同理（3000 → ≤2400）。体检脚本（memory_health.py）的占用百分比
就是按这个预算看的：≥80% 黄灯，≥95% 红灯。
- 条目格式沿用框架原生：条目间以单独一行 `§` 分隔（代码里是
`"\n§\n"`，见 tools/memory_tool_store.py 的 ENTRY_DELIMITER）；
不要在 MEMORY.md 里自己发明标题层级结构，会干扰框架的条目切分与注入。

## 部署顺序（本包内）

1. 把 memory_health.py 复制到 `$HERMES_HOME/scripts/memory_health.py`
（值班 Job 04/05 按这个路径引用它）。
2. 执行 `bash git-backup-init.sh`（HERMES_HOME 以环境变量为准）。
3. 把 snapshot.sh 挂到系统 cron 每日一次，或在晚报 job 前手动执行；
验证 `$HERMES_HOME/backups/snapshots/` 出现第一份快照。
4. 把 skills/memory-hygiene 整个目录复制到 `$HERMES_HOME/skills/`。
5. 建空目录 `memories/journal/`、`memories/people/`、`memories/archive/`。
6. 跑一次 `python3 memory_health.py` 留基线报告（部署当天数字就是基线）。

## 防丢逻辑速查

- 条目级回滚：`memories/` 的 git 历史（整理 job 前后各一次提交）。
- 整机级灾备：snapshot.sh 的 30 份轮转快照（含 state.db）。
- 单写者：同一 HERMES_HOME 只跑一个 gateway（框架有锁，别绕）；
手改 MEMORY.md 后什么都不用做，下一轮整理 job 以文件现状为准对账。
