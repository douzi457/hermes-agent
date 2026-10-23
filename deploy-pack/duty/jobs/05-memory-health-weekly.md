# Job 05 · 每周记忆体检（memory-health-weekly）

- **用途**：方案 M6。把记忆质量变成可见指标：总量、条目数、距上限、重复率估计、陈旧条目、待裁矛盾——先有数，才谈优化。只报告不改记忆（改归 Job 04）。
- **调度**：每周一 09:00：`0 9 * * 1`。
- **登记命令**：

```bash
hermes cron create "0 9 * * 1" "<见下方提示词全文>" \
  --name memory-health-weekly --deliver origin --skill memory-hygiene
```

- **验收点**：手动触发后收到一份周报，数字与手动运行 `python3 "$HERMES_HOME/scripts/memory_health.py" "$HERMES_HOME/memories"` 的输出对得上；报告末尾有与上周对比一行（第一周写「无上周数据」）。

## 提示词全文

你做每周记忆体检，只读不改。步骤：

1. 经 `terminal` 运行 `python3 "$HERMES_HOME/scripts/memory_health.py" "$HERMES_HOME/memories"`，拿到确定性数据（字符数、条目数、距上限百分比、重复候选对、无日期条目、超 90 天未动条目）。
2. 读上周报告（`$HERMES_HOME/duty/drafts/` 里最近一份 memory-health 周报，没有就跳过对比）。
3. 产出周报写入本轮输出，结构：
   - `## 记忆体检（<日期>）`：MEMORY 与 USER 的条目数、字符数、距上限百分比，各带与上周的增减；
   - `## 本周变化`：新增条目数、整理 job 本周合并/归档数（从本周《记忆变更摘要》汇总，取不到就写取不到，不许估算冒充）；
   - `## 风险提示`：距上限 ≥85% 预警、重复候选对数量、待裁矛盾是否积压（有就列条数并指路最近一份变更摘要）；
   - `## 建议`：最多两条，要具体（如「people 档案有 3 页超 90 天未更新」），不许写「继续保持」式空话。
4. 全程禁止修改 MEMORY.md / USER.md 任何内容；发现脚本报错时如实报告错误输出。
