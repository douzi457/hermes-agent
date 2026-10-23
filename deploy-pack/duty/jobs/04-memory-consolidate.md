# Job 04 · 每晚记忆整理（memory-consolidate）

- **用途**：方案 M3。先跑确定性体检脚本拿候选清单，再按《整理规程》合并重复、新替旧、降级细节、归档过期，产出《记忆变更摘要》。整理前后各做一次 git 提交（M4），乱了可回滚。
- **调度**：每晚 23:10：`10 23 * * *`（在晚报之后、安静时段内运行，只落盘不打扰；摘要攒到次日晚报或用户下次交互）。
- **登记命令**：

```bash
hermes cron create "10 23 * * *" "<见下方提示词全文>" \
  --name memory-consolidate --deliver local --skill memory-hygiene
```

前置：`memory_health.py` 已部署到 `$HERMES_HOME/scripts/memory_health.py`；`memories/` 已完成 git 初始化（见装配包 memory/git-backup-init.sh）。

- **验收点**：手动触发一次：memories 的 git 仓库多出两条提交（整理前/整理后）；`$HERMES_HOME/duty/drafts/` 出现当日《记忆变更摘要》；故意预埋的一对重复条目被合并且摘要里有记录。

## 提示词全文

你执行每晚记忆整理，规程以 memory-hygiene 技能与装配包《整理规程》（consolidate-protocol.md）为准。步骤：

1. 经 `terminal` 在 `$HERMES_HOME/memories` 目录执行 `git add -A && git commit -m "pre-consolidate $(date +%F)" --allow-empty`，留整理前快照。git 不可用或目录未初始化时停止并报告，不要继续整理。
2. 经 `terminal` 运行 `python3 "$HERMES_HOME/scripts/memory_health.py" "$HERMES_HOME/memories"`，读它的 Markdown 报告：总量与距上限、重复候选对、无日期条目、超 90 天未动条目。
3. 用 `read_file` 通读 MEMORY.md 与 USER.md 全文（上限内文件不大，必须全读，不许只看脚本摘要下判断）。
4. 按规程逐项处理，判定标准只有四种：
   - 合并：同一事实的多个版本合成一条，保留信息量最大、日期最新的表述；
   - 新替旧：新旧冲突时以新为准改旧条，被替代的细节追加进 `memories/journal/<今天>.md`；
   - 降级：细节性、一次性内容从 MEMORY.md 移到 journal，长期层只留结论；
   - 归档：已失效且无保留价值的条目移到 `memories/archive/` 对应文件，注明归档日期与原因。
   疑似矛盾但无法判定谁对谁错的，不许擅自删除，列入摘要的「待用户裁决」区。
5. 所有改动用 `memory` 工具或 `patch` 完成；部署初期 write_approval 开着，后台写入进待批区是正常流程，在摘要中注明待批条数，不要试图绕过。
6. 产出《记忆变更摘要》写入 `$HERMES_HOME/duty/drafts/<今天>-memory.md`：合并了哪些、新替旧了哪些、降级/归档了哪些、待裁决清单、整理后总量与距上限百分比。
7. 最后在 memories 目录执行 `git add -A && git commit -m "post-consolidate $(date +%F)"`。任一步失败：停止后续步骤，在摘要里写清失败位置与原因（失败要上报，不许默默烂掉）。
