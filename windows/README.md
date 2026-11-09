# 关爱通自动领取 · Windows 版

> 本文命令从仓库的 `windows/` 目录执行。双平台总览见 [README.md](../README.md)。

**状态：Windows 实机待验证的候选版本。** 已通过本地通用逻辑测试和微软 Task Scheduler XSD 校验，但尚未在 Windows 电脑上实际安装、定位、显示弹窗或完成领取。不能把这些检查等同于“Windows 实测通过”。

这是独立 Windows 项目，不会改动已有 macOS 版本。非官方工具，仅用于本人账号、符合网站及公司规则的正常领取；不绕过验证码、地理位置或领取资格。

## 1. 保留的功能

- 每天按**电脑本机时间 20:30**自动触发一次。
- 手动领取允许窗口：**20:30（含）至次日 00:00（不含）**；只读检查全天可用。
- 独立 Chrome 登录目录；正常领取使用无头模式，定时入口使用 `pythonw.exe`，worker 隐藏控制台。
- 只点击今日卡片的“领取 / 立即领取 / 点击领取”，最多 5 次，成功或遇到阻断就停止。
- 登录失效、定位不可用时用 Windows 原生信息框提醒；处理后仍需本人手动重跑。
- 需要本人明确授权**真实定位**，只授予 `https://c.guanaitong.com`；不设置虚拟坐标、不记录坐标。
- 不检查 CPU 或键鼠活跃度；用户必须已登录 Windows。锁屏但未睡眠仍可能执行，注销后不执行。

## 2. 环境要求

- Windows 10/11，使用本人桌面账号；标准 x64 为主要验证目标，其他架构需另外实测。
- 已安装 Google Chrome（系统标准目录或当前用户目录）。
- `uv` 可在终端调用，首次安装需要网络下载 Python 3.13 和依赖。
- Windows 定位服务和 Chrome 能返回真实位置。
- 组织策略允许当前用户创建自己的计划任务、读取 System 电源事件和运行脚本。

若缺少 `uv`，先按照[官方安装说明](https://docs.astral.sh/uv/getting-started/installation/)安装，再重新打开终端。不要关闭安全软件、修改全局执行策略或借管理员权限绕过组织限制。本工具不要求 PowerShell `Bypass`。

## 3. 安装步骤

1. 解压源码包到自己拥有的目录，**不要复制其他人的登录目录**。
2. 双击 **`install.cmd`**。它默认仅安装依赖、设置本机目录权限和生成管理入口，**不会启用定时任务，也不会领取**。
3. 安装完成后，双击 **`重新登录.cmd`**，在专用 Chrome 中人工登录。不要提前关窗口；识别到今日领取页后会保存并自动关闭。
4. 双击 **`授权真实定位.cmd`**，阅读提示，由本人选择是否同意。
5. 双击 **`仅检查.cmd`**，确认能识别网页。`ready` 只表示按钮可用，不证明定位/资格已通过。
6. 确认后双击 **`启用定时.cmd`**，再用 **`查看状态.cmd`** 检查任务已启用。

首次安装会生成以下 7 个入口（源码包中一开始只有 `install.cmd`，其他由安装器生成）：

| 入口 | 行为 |
|---|---|
| `重新登录.cmd` | 人工登录并保存当前会话，不领取 |
| `授权真实定位.cmd` | 本人授权该站点使用真实定位，不领取 |
| `立即领取.cmd` | 在 20:30–24:00 窗口内实际运行一次 |
| `仅检查.cmd` | 全天只读检查，不点击、不主动定位、不弹错误提醒 |
| `启用定时.cmd` | 注册/更新本人每日 20:30 的任务，不立即领取 |
| `停用定时.cmd` | 禁止未来定时执行，保留任务项、登录资料和日志 |
| `查看状态.cmd` | 检查任务配置是否存在且启用 |

手动入口会打开终端让你查看结果，结束后按键关闭；这与正常定时任务的无控制台后台运行不同。

## 4. 关于“每天先登录，晚上自动领取”

可以这样使用，但要在**接近领取时间**时确认登录，例如当天 20:00 左右。不要假设早上登录后晚上一定仍有效。

当前“重新登录”会先尝试已有会话：如果仍有效，可能直接保存并关闭；它不是强制重新认证，也不保证延长服务器有效期。保存 Cookie 不等于续期。网站要求重新认证时，必须本人处理。

20:30 之后才登录或授权，不会自动补领；需要本人再运行 `立即领取.cmd`。登录、定位和资格有效才可能成功。

## 5. 睡眠、关机和进程控制

- 任务计划程序配置为 `InteractiveToken`、`LeastPrivilege`、`IgnoreNew`，不保存 Windows 密码。
- `WakeToRun=false`、`StartWhenAvailable=false`：不唤醒电脑，不让任务计划程序补跑错过的时刻。
- 自动模式额外读取 System 电源事件/系统运行时间；无法读取或状态不明确时保守跳过。运行期间用包含/排除睡眠的时钟差检测挂起恢复。
- 手动运行不读取此前电源历史，但仍受时间窗口限制。
- worker 最多 120 秒；超时尝试使用 `taskkill /PID <本次worker> /T /F` 清理本次子进程树，不按 Chrome 名称全局结束进程。
- 原生提醒最多约 60 秒，超时结束本次提醒子进程。任务计划程序另设 4 分钟上限。

**电源事件、Modern Standby、Fast Startup、真实进程回收和桌面提醒行为都需要 Windows 实机验证。** “查看状态”只表示配置存在，不代表它已经成功执行过。

## 6. 数据位置与隐私

```text
%LOCALAPPDATA%\GuanaitongAutoClaim\
  code\                 运行副本
  .venv\                本机 Python 依赖
  chrome-profile\       专用浏览器资料（不可公开）
  auth-state.json        会话材料（明文，不可公开）
  location-consent.json  本机定位同意，不随包迁移
  profile.lock          Windows 文件锁
  run.log               状态日志及轮转备份
  install-info.json     本机安装标识
  task.xml              本机任务配置，含本机路径/SID
```

安装器只对本工具目录设置 NTFS ACL，保留当前用户、SYSTEM 和管理员的访问权限；不修改整个 LocalAppData。ACL 不是加密，也不能防止同一用户权限的恶意软件。

任务名为 `GuanaitongAutoClaim-<当前用户SID>`，避免其他 Windows 账号混用同一任务。不要把生成的任务 XML、`.cmd` 入口、定位同意、会话文件或日志发给别人。

## 7. 如何判断成功、如何排错

日志包含 `time`、`mode`、`status`、`clicks`、`verified`，失败时可能有固定的 `phase` / `error` 分类；提醒响应另占文本行，不是严格纯 JSONL。

- **成功依据：** `already_claimed` 且 `verified: true`，再以网站今日卡片/领取记录核实。
- `ready` 不是成功；进程退出码 0、任务存在或点击了 5 次也不是到账证明。
- `login_required`：重新在专用 Chrome 登录，之后自行重跑。
- `location_permission_required`：确认本机授权与 Windows/Chrome 定位设置。
- `location_unavailable` / `location_timeout`：未取得真实位置，检查定位服务和网络，不填虚拟位置。
- `power_state_unknown`：系统电源状态不可读或不明确，自动模式保守跳过；联系 IT 检查 System 日志读取权限。
- `missed_while_asleep` / `missed_while_off` / `resumed_during_run`：由于电源状态跳过，不自动补领。
- `outside_schedule_window`：不在 20:30–24:00 窗口。
- `profile_busy`：另一个登录/领取占用专用目录，等待结束，不删除锁文件。
- `click_result_uncertain`：先看网站是否已经领到，再决定重试。
- `button_missing_or_ambiguous`：页面可能改版，不要改成固定坐标盲点。
- `execution_timeout`，尤其伴随 `cleanup_failed`：需在 Windows 检查本次进程是否退出，不能宣称已经自动回收。

## 8. 撤销、更新与停用

撤销后续定位同意（PowerShell）：

```powershell
$app = Join-Path $env:LOCALAPPDATA 'GuanaitongAutoClaim'
& "$app\.venv\Scripts\python.exe" "$app\code\location_access.py" --revoke
```

只读检查安装版：

```powershell
$app = Join-Path $env:LOCALAPPDATA 'GuanaitongAutoClaim'
& "$app\.venv\Scripts\python.exe" "$app\code\launcher.py" --check
```

更新源码后，在没有任务/登录正在运行时重新执行新目录的 `install.cmd`，再确认任务状态；复制源码不等于运行副本已更新。停用任务使用 `停用定时.cmd`，不会删除会话，也不强制结束正在执行的任务。

如需彻底移除，先停用、确认专用进程退出，再由本人决定是否从任务计划程序删除自己的任务项，以及删除运行目录。不要全局结束 Chrome，也不要误删其他用户的任务或资料。

## 9. 验证与交接

- [Windows 实机验证清单](WINDOWS_VALIDATION.md)
- [发给同事 Agent 的安装说明](AGENT_HANDOFF.md)

当前环境完成了 42 项本地测试、Python 语法检查、模拟页面截图检查，以及生成 XML 对微软官方 Task Scheduler XSD 的校验。**尚未在 Windows 原生环境完成验证，也没有用此 Windows 版本实际领取。**

许可证尚未指定。若要公开开源，先确认代码权属、目标平台/公司规则并选择许可证；本包不包含任何人的凭证或定位授权。

## 技术参考

- [微软 Task Scheduler Schema](https://learn.microsoft.com/zh-cn/windows/win32/taskschd/task-scheduler-schema)
- [QueryUnbiasedInterruptTime](https://learn.microsoft.com/zh-cn/windows/win32/api/realtimeapiset/nf-realtimeapiset-queryunbiasedinterrupttime)
- [wevtutil](https://learn.microsoft.com/zh-cn/windows-server/administration/windows-commands/wevtutil)
