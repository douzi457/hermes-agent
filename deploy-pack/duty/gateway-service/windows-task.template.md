# Hermes gateway 常驻 · Windows 方案

## 首选：仓库自带 install

仓库有专门的 Windows 后端 `hermes_cli/gateway_windows.py`（以计划任务监督
gateway，任务名按 profile 生成）。先试官方路径（管理员 PowerShell）：

```powershell
hermes gateway install
hermes gateway status
```

装完用 `hermes gateway status` 验证在跑。官方路径可用时不要再用下面的
手动 schtasks，两套监督并存会抢同一 profile。

## 备选：手动计划任务模板

官方 install 不可用时，用登录触发的计划任务拉起前台 gateway
（`hermes gateway run`，子命令帮助原文：Run gateway in foreground）：

```powershell
# 1) 先确认 hermes 可执行文件路径（按本机实际输出替换 __HERMES_EXE__）
where.exe hermes

# 2) 注册计划任务（当前用户登录时启动，失败自动重启由 gateway 自身的监督逻辑负责；
#    任务本身只负责拉起）
schtasks /Create /TN "Hermes Gateway" /SC ONLOGON /RL LIMITED /F `
  /TR "\"__HERMES_EXE__\" gateway run"

# 3) 立即启动一次并验证
schtasks /Run /TN "Hermes Gateway"
hermes gateway status
```

注意：

- `HERMES_HOME` 若非默认 `%USERPROFILE%\.hermes`，需在任务里先设环境变量，
  或改用包装 .cmd 设置变量后再调用 hermes（schtasks 的 /TR 不直接支持设变量）。
- 注销/重启后任务随登录自启；无人登录的服务器场景改用 `/SC ONSTART` 并以
  服务账户运行，细节以部署时 `schtasks /Create /?` 与
  `hermes gateway install --help` 的实际输出为准。
- 停用：`schtasks /Delete /TN "Hermes Gateway" /F`。
