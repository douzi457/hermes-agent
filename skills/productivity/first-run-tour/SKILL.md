---
name: first-run-tour
description: "首启引导：讲清本机档位与预设，按用途、预算、渠道当场调配置."
version: 1.0.0
author: douzi457
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [onboarding, setup, machine-profile, first-run]
    category: productivity
---

# First-Run Tour Skill

新装 Hermes 的第一次对话由本 skill 引导：先讲清这台机器被定成什么档位、首启预设已经改了什么，再问清用途、预算、渠道三件事，按回答当场调整配置，并把结论记进 ENVIRONMENT.md。它不替代 `hermes setup` 向导（账号、密钥仍在向导里配），只做向导之后的定档讲解与按需微调。

## When to Use

- 用户刚装好 Hermes，这是第一次对话。
- 用户问「新机怎么配」「这台机器能开哪些功能」「为什么浏览器/委派被关了」一类问题。
- 用户换了机器或升了配置，想重新定档（先走 Pitfalls 里的重跑体检，再回到本流程）。

## Prerequisites

- 本机已跑过一次体检：ENVIRONMENT.md 存在（与 config.yaml 同目录，用 `hermes config path` 定位）。若不存在，先在 `terminal` 里运行 `hermes doctor --fix` 生成，再继续。
- 调整配置只用 `hermes config set`（经 `terminal` 执行），改前先 `hermes config get <键>` 看现值。

## How to Run

按 Procedure 的四步顺序走完，不要跳步：先讲现状，再提问，再动手改，最后落盘记录。每改一处配置，当场向用户说明「键、旧值、新值、为什么」。

## Quick Reference

| 档位 | 人话讲解骨架 |
|---|---|
| T0 微型 | 「这台机器配置很低，首启已经关掉浏览器、桌面控制和图像/视频生成，先保聊天和文件处理流畅；想用这些功能需要升配或换机器。」 |
| T1 标准 | 「这台机器是标准档，出厂功能基本全开，浏览器按需启动不预热，日常使用不用改。」 |
| T2 充裕 | 「这台机器比较充裕，首启已把压缩保留的消息数和记忆上限调大，长对话不容易丢上下文。」 |
| T3 带 GPU | 「在充裕档基础上探到了显卡；可以考虑让本地模型（如 Ollama）承担摘要、整理这类辅助活，省云端费用——要不要开由用户决定，不替他装。」 |

常用命令（均已核实存在）：

- `hermes config get machine` — 看机器档案（档位、核数、内存、摘要）
- `hermes config set <键> <值>` — 改配置；列表值用 JSON 写法，如 `hermes config set agent.disabled_toolsets '["browser", "tts"]'`
- `hermes config unset <键>` — 撤掉一处显式设置，回到出厂默认
- `hermes doctor --fix` — 重新体检并刷新档案（会覆盖 ENVIRONMENT.md，见 Pitfalls）
- `hermes gateway setup` — 接入消息渠道时走这个向导，不要手改渠道配置

## Procedure

1. **讲清现状。** 用 `read_file` 读 ENVIRONMENT.md，再用 `terminal` 跑 `hermes config get machine` 核对档位。向用户说明：本机是什么档、依据是哪些数字（核数/内存/显卡）、ENVIRONMENT.md 里「首启预设」一节已经改了哪些键、每处为什么。若有 low_disk 告警，先提醒清盘再谈开功能。
2. **问三件事**（一次问一件，等回答再问下一件；用户不想答的跳过，不追问）：
   - 主要用途：写代码 / 写文档 / 日常助理 / 跑自动化任务，还是几样都有？
   - 模型预算量级：先用免费或低额度跑通 / 每月有固定额度 / 重度使用、效果优先？
   - 想接的渠道：只在本机用，还是要接 Telegram、Discord、微信等消息渠道？
3. **按回答当场调整。** 每处调整都遵循：先 `hermes config get <键>` 报旧值 → 说明为什么改 → `hermes config set <键> <值>` → 再 `get` 一次确认落盘。典型对应关系：
   - T0/T1 但用户要重度写代码、跑长任务：把 `compression.protect_last_n` 适当调大，并提醒代价是上下文更贵。
   - 预算量级低：建议把 `delegation.max_concurrent_children` 压到 1–2、辅助模型用便宜档；预算充足且要并行干活：可调大，但提醒费用随并发线性涨。
   - T0 用户明确要用浏览器：从 `agent.disabled_toolsets` 里去掉 `browser`，并当场说明低配机器上浏览器会慢、可能装不上依赖。
   - 要接渠道：只负责告知并引导去 `hermes gateway setup`，密钥由用户在向导里自己填，本流程不经手任何密钥。
4. **落盘结论。** 用 `patch` 在 ENVIRONMENT.md 文末追加一节「## 首启对话结论」，包含：日期、用户的主要用途、预算量级、渠道意向、本次实际改动的键与新值（没改就写「无调整」）。追加完向用户复述一遍结论，请他确认记的对不对。

## Pitfalls

- `hermes doctor --fix` 重跑体检会**整篇重新生成** ENVIRONMENT.md，「首启预设」和「首启对话结论」两节会被覆盖。重跑后要按本流程把结论节重新补记，并提醒用户这一特性。
- 不要替用户做付费决定：开本地模型、接付费渠道、调高并发都先说明代价，得到明确答复再动手。
- 不要手改 config.yaml 或 ENVIRONMENT.md 的表格部分（体检生成区）；配置一律走 `hermes config set`，记录只往文末追加。
- 用户在 config.yaml 里已显式设过的键是他的地盘：首启预设不会覆盖，本流程调整时也要先报旧值、经他确认再改。

## Verification

- `hermes config get machine` 能读到档位，且与 ENVIRONMENT.md 表格一致。
- 本次每处调整都能用 `hermes config get <键>` 读回新值。
- ENVIRONMENT.md 文末有当天的「首启对话结论」节，内容与用户回答一致。
