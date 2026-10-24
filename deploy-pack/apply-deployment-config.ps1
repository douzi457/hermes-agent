# apply-deployment-config.ps1 — 个人部署配置一键应用脚本
#
# 目的：全新安装后，不用再逐条跑 hermes config set；除模型与密钥外，
#       部署口径一次落盘。出厂默认不改（2026-10-22 决定③：approvals manual
#       只写个人部署配置，出厂保持官方 smart）。
#
# 值来源：deploy-pack/config/config.private.template.yaml，另含老大
#   2026-10-23 的现定：
#   - agent.max_turns = 120（T2 口径；模板写 90 是 T1 口径）
#   - aux 模型不配置（跟随主模型 auto；主脑即 agnes-3.0-flash，另配属多余）
#
# 用法（Windows）：在已激活的 D:\hermes-agent 窗口执行
#   .\deploy-pack\apply-deployment-config.ps1
# 注意：
#   - 模型与密钥不在此脚本内，须在 hermes setup 里由本人填写。
#   - 全部写入均为幂等（重复执行无害）；改完开新会话才生效。
#   - 任一条 set 失败即停，截图发回，不要改走手改 config.yaml 硬填。

$ErrorActionPreference = 'Stop'

if (-not (Get-Command hermes -ErrorAction SilentlyContinue)) {
    throw 'hermes 不在 PATH：请先在 D:\hermes-agent 窗口执行 .\activate.ps1 再跑本脚本'
}

$sets = @(
    @('display.language', 'zh'),
    @('memory.memory_char_limit', '8000'),
    @('memory.user_char_limit', '3000'),
    @('agent.max_turns', '120'),
    @('agent.verify_on_stop', 'true'),
    @('agent.budget_warning_ratio', '0.75'),
    @('approvals.mode', 'manual'),
    @('memory.write_approval', 'true'),
    @('auxiliary.compression.provider', 'agnes'),
    @('auxiliary.approval.provider', 'agnes'),
    @('auxiliary.background_review.provider', 'agnes'),
    @('auxiliary.curator.provider', 'agnes'),
    @('auxiliary.title_generation.provider', 'agnes')
)

foreach ($kv in $sets) {
    hermes config set $kv[0] $kv[1]
    if ($LASTEXITCODE -ne 0) {
        throw "config set 失败：$($kv[0])，请停下截图，不要继续"
    }
}

Write-Host ''
Write-Host '全部 13 项写入完成。'
Write-Host '验证：新开一个会话，问 agent「审批模式是什么、记忆上限多少」，应答 manual / 8000、3000 即生效。'
