# 关爱通 macOS 自动领取

> 本文命令从仓库的 `macos/` 目录执行。双平台总览见 [README.md](../README.md)。

**迁移到同事电脑：先读 [AGENT_HANDOFF.md](AGENT_HANDOFF.md)。** 源码包不含登录态、截图或本机快捷方式；安装器会在接收电脑重新生成 `.command` 入口。每个人都需要自行登录，原电脑的测试记录不代表接收电脑已验证。

如需分享整个仓库，可在仓库根目录运行 `python3 tools/package_source.py --output ../source-draft.zip`。打包工具采用文件白名单；不要直接压缩整个工作目录或 Application Support 运行目录。

每天 **本机时区 20:30**，由 macOS `launchd` 的 `StartCalendarInterval` 触发一次。不依赖 StepCode 保持打开，不常驻 Python 或自动化 Chrome。

## 当前行为

- **可领取时间窗口：本机时间 20:30:00 起，至次日 00:00:00 前**，即 `20:30 ≤ 当前时间 < 24:00`。手动和自动领取均受此限制；窗口外直接跳过，不启动浏览器。`--check` / “仅检查”是例外：全天可用，只检查、不点击。
- 时间窗口扩大不代表持续运行到午夜；每天仍只自动触发一次，单次执行仍限时 120 秒。
- **不检查 CPU、不检查键鼠活跃度，不因锁屏而跳过**；用户需要已登录 macOS，电脑保持清醒。
- 自动任务仍只在每天 20:30 触发一次。关机时不能运行；不主动唤醒睡眠电脑。检查内核启动/最后唤醒时间，拒绝 20:30 时关机或睡眠、之后开机/唤醒触发的补跑。
- **手动运行不检查电源时间**，只检查时间窗口，便于在 20:30–24:00 之间随时测试。
- 正常任务使用无头 Chrome，不打开可见窗口、不抢当前浏览器焦点。只使用独立配置目录，不读写日常 Chrome 的登录资料。
- **领取还需要真实定位，不只是登录。** 首次使用请本人点击“授权真实定位.command”确认，仅允许 `https://c.guanaitong.com` 使用浏览器真实位置。未授权、定位失败或超时时会停止并弹窗；不使用虚拟坐标，也不绕过公司领取范围。
- 领取前会检查真实定位是否可用；只返回状态，不把坐标写入日志。`--check` 不授权、不主动探测定位，也不领取。
- 成功后既支持按钮文字，也识别今日卡片的“已领取”图片印章；不会把按钮消失、总领取人数或未知图片当作成功。
- 打开领取网址，仅定位 **“今天 20:30”** 卡片中的 `.allowance-btn`。领取按钮持续可用时，最多点击 **5 次**，每次间隔约 2 秒。
- 已领取、按钮不可用、结构不明确、验证码或结果不确定时停止，不强制点击、不调用私有接口、不绕过公司网络或资格限制。点击次数不等于领取成功。
- 登录失效时，关闭无头浏览器后显示系统信息弹窗。选择“打开登录窗口”会启动人工登录；**登录后不会自动补领，需手动运行一次“立即领取”**。
- 弹窗 60 秒后自动关闭，运行日志仍保留。锁屏时不能保证你当场看到弹窗；如果期间无人响应，请之后查看日志。
- 普通执行由监督进程限时 120 秒；超时清理本次 worker 和浏览器子进程。登录提醒最多额外等待 65 秒。人工登录窗口单独最多等待 15 分钟。

## 日常使用

安装后，在本仓库的 `macos/` 目录内双击生成的入口：

| 入口 | 作用 |
|---|---|
| `重新登录.command` | 人工登录专用 Chrome。不要提前关窗口；识别到领取页后自动保存会话并关闭。不会领取。 |
| `授权真实定位.command` | 本人确认仅向关爱通提供真实定位；授权只存本机，不自动领取。 |
| `立即领取.command` | 在本机 20:30–24:00 之间手动后台运行一次；仍遵守页面开放状态，窗口外不启动浏览器。 |
| `仅检查.command` | 全天可用，只检查登录和今日按钮，不点击、不弹窗。 |
| `停用定时.command` | 停用并移除本工具的 LaunchAgent，保留登录资料和日志。 |

登录页和领取页在不同域名：从 `https://c.guanaitong.com/overtime?scene_type=1` 自动跳到 `https://m.igeidao.com/passport`。人工登录后若回到首页，登录工具会自动导航回领取页。

**会话恢复**：该网站仅复用 Chrome 目录不足以稳定保留本次登录；工具在登录成功、关闭浏览器之前额外保存会话 Cookie/存储。服务端仍可使登录失效，工具不延长或伪造有效期。

## 路径与隐私

- 源代码：此文件夹。
- 实际运行目录：`~/Library/Application Support/GuanaitongAutoClaim/`。
- 定时配置：`~/Library/LaunchAgents/com.local.guanaitong-autoclaim.plist`。
- 日志：运行目录的 `run.log`，256 KiB 轮转，最多 3 份备份。仅记录时间、模式、状态、点击次数、成功标记及固定的阶段/错误分类，不记录 Cookie、坐标、页面 URL 参数或接口正文。
- `location-consent.json`：仅保存当前设备对指定站点的定位授权开关和更新时间，不含坐标。默认不授权，不随源码包迁移；同事必须单独确认。
- `chrome-profile/` 和 `auth-state.json` 是**登录凭证**：只保存在本机；目录权限 700，会话文件权限 600。不要上传、发给别人或加入版本控制。本机磁盘加密（FileVault）由你管理。
- `artifacts/` 内截图仅来自开发测试，不会在每日任务中采集；其中真实页面截图可能包含个人信息，不应分享。

运行代码和独立 Python 环境安装在 Application Support 下，避免系统定时任务依赖桌面文件夹权限。删除桌面源代码目录不会停用已安装的任务；请用“停用定时”入口停用。

## 撤销定位授权

```sh
"$HOME/Library/Application Support/GuanaitongAutoClaim/.venv/bin/python" \
  "$HOME/Library/Application Support/GuanaitongAutoClaim/code/location_access.py" --revoke
```

撤销后，后续任务不会授予定位权限；已在执行的任务需等待退出。若允许定位但仍失败，请检查 macOS“隐私与安全性 → 定位服务”及 Chrome 权限、网络；不要填写虚拟坐标。

## 状态说明

| 日志状态 | 含义 |
|---|---|
| `ready` | 已识别可领取按钮；不表示真实定位、领取资格已通过或已经领取 |
| `not_started` | 今日领取尚未开放，没有点击 |
| `already_claimed` / `verified: true` | 今日按钮明确显示已领取，或出现已现场验证的“已领取”图片印章 |
| `location_permission_required` | 未授权或网站要求开启定位；正常运行会提醒，不能靠重复点击解决 |
| `location_unavailable` / `location_timeout` | 未取得真实位置，停止并提醒检查定位服务/权限/网络 |
| `attempts_complete` / `verified: false` | 已点满 5 次，但未观察到已领取，不表示成功 |
| `login_required` | 需要人工登录；正常运行会弹窗提醒 |
| `outside_schedule_window` | 不在本机 20:30（含）至次日 00:00（不含）的领取窗口内，跳过 |
| `missed_while_asleep` / `missed_while_off` | 睡眠或关机期间错过，拒绝补跑 |
| `profile_busy` | 人工登录或另一任务占用专用目录，没有启动第二个浏览器 |
| `power_state_unknown` | 不能确认电源状态，保守跳过 |
| `manual_verification_required` / `dialog_requires_user` | 需要人工验证或处理确认框 |
| `card_missing_or_ambiguous` / `button_missing_or_ambiguous` | 页面结构有变化，未冒险点击 |
| `browser_or_network_error` / `click_result_uncertain` / `execution_timeout` | 失败或结果不确定，需先核实页面，不自动无限重试 |

## 安装、更新与测试

依赖：macOS、已安装的 Google Chrome、`uv`。安装时使用独立 Python 3.13 环境以及 `requirements.txt` 中固定的依赖版本。

```sh
# 在此源码目录中执行；安装/更新只针对本工具，不会立即领取。
.venv/bin/python install.py

# 修改源码后必须重新执行安装，才能更新 Application Support 中的运行副本。
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python launcher.py --check

# 查看调度状态；不会执行领取。
launchctl print gui/$(id -u)/com.local.guanaitong-autoclaim
```

如果在新电脑上部署，需要先用 `uv venv .venv --python 3.13` 及 `uv pip install --python .venv/bin/python -r requirements.txt` 准备源码测试环境，再安装、重新人工登录。不要复制原电脑的登录凭证给其他人。

测试边界和结果见 [TESTING.md](TESTING.md)。本工具不会保证公司福利发放成功，最终结果以网站为准。
