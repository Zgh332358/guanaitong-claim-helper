# 同事电脑迁移与 Agent 交接

## 先读这段

这是**纯源码包，仅支持 macOS**。原电脑上的定时任务不会随着解压自动迁移。Intel Mac / Apple Silicon Mac 应分别在接收电脑安装依赖；本次未在其他硬件实测，不承诺 Windows 兼容。

包内没有原用户的账号、登录 Cookie、Chrome 配置目录、日志、截图、虚拟环境，也不包含带原电脑绝对路径的 `.command` 快捷入口。`install.py` 根据接收方 `Path.home()` 重新生成运行目录、快捷入口和 LaunchAgent；**每位同事必须用自己的账号人工登录**。

本说明适用于仓库的 `macos/` 子目录。公开验证范围见 `TESTING.md`，不附带私人运行报告或真实截图。依赖需联网下载。通过仓库打包工具生成的 ZIP 会在包根目录附带 `PACKAGE_MANIFEST.json` 用于完整性检查；Git 检出不要求存在此文件。清单不是身份签名。

## 可以直接发给同事 Agent 的话

> 请把关爱通领取辅助工具的 macOS 版本安装到我这台电脑。先阅读仓库总 README，再进入 macos/ 阅读本文件和平台 README；检查代码，若使用 ZIP，再核对包根目录的 PACKAGE_MANIFEST.json。不要直接执行不明脚本。
>
> 先确认这台电脑是 macOS、已安装 Google Chrome，并核对本机时区。若是 Windows，请先说明无法直接使用，不要照搬 launchd。若有同名运行目录/定时任务，先向我说明并确认处理方式，不覆盖已有登录资料。
>
> 保持现有逻辑：每天本机时间 20:30 自动触发一次，允许领取的时间为 20:30（含）至次日 00:00（不含），不是持续循环运行到午夜。手动入口在此窗口内可用，不检查是否错过定时时刻；--check 全天可用、不点击。无 CPU/键鼠活跃度判断；自动任务关机或睡眠错过后不补跑、不唤醒；正常领取使用无头 Chrome、不弹浏览器；只点击今日 20:30 卡片，最多 5 次，已成功或按钮不可用就停止。公司网络和领取资格由网站判断，不绕过验证或限制。
>
> 请按本文的分阶段步骤准备独立 Python 环境并运行测试，先用 install.py --prepare-only 准备运行目录，不先启用定时器。然后打开专用 Chrome，由我手动登录；不要读取、索要或输出账号密码、Cookie、会话文件内容。登录窗口自动保存并关闭后，运行 --check，只检查、不领取。网站还要求真实定位：先向我明确说明只对 c.guanaitong.com 授权，并询问我是否同意；同意后再使用“授权真实定位.command”。不要复制别人的定位授权，不设置虚拟坐标，不输出坐标。
>
> 只读检查正常后，再向我确认是否启用每日 20:30 的任务。登录过期应弹窗提醒；重新登录后由我手动运行一次领取，不自动补领。未获我另行确认，不为了测试真实点击领取、不 kickstart 定时任务，也不让电脑睡眠/关机。
>
> 最后告诉我测试结果、是否已启用定时器、五个快捷入口、日志位置、停用方式以及尚未验证的事项。不要把测试通过或点击完成说成领取到账。

## 接收方 Agent 的安装顺序

### 1. 检查环境与现有安装

- 解压到当前用户拥有、可写的目录，用该用户的普通 GUI 会话操作，不使用 `sudo` 安装。
- 确认是 macOS；检查 Chrome、`uv`、磁盘空间和下载依赖所需网络。缺失的依赖先说明安装方式，遵循用户和工具的权限批准；不关闭系统安全保护、不修改系统 Python。
- 检查 `~/Library/Application Support/GuanaitongAutoClaim/` 和对应 LaunchAgent 是否存在。有旧任务时先确认：`--prepare-only` **不会停用已存在的任务**，不能将其误当隔离环境。
- 核对本机时区：任务用本机 20:30，不是固定北京时间。

### 2. 建立接收电脑自己的环境并测试

在**解压后的源码根目录**执行，路径含空格时保持引号：

```sh
uv venv .venv --python 3.13
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python install.py --prepare-only
```

51 项用例是当前版本的预期基线；失败时先诊断，不把原电脑的成功结论套用过来。用例中的浏览器网络请求全部拦截，不会实际领取；测试可能生成本地模拟截图，不要把测试产物再次打包分享。

### 3. 人工登录，然后无头只读检查

`--prepare-only` 完成后才会出现五个 `.command` 快捷入口。可双击“重新登录.command”，或从终端执行：

```sh
"$HOME/Library/Application Support/GuanaitongAutoClaim/.venv/bin/python" \
  "$HOME/Library/Application Support/GuanaitongAutoClaim/code/login.py"
```

此步骤必须由本人在专用 Chrome 中登录。**不要提前手动关窗口**；识别到今日领取卡片后脚本会保存会话并自动关闭。如果窗口未自动关闭，先查看页面/安全状态，不盲目重复登录或领取。

```sh
"$HOME/Library/Application Support/GuanaitongAutoClaim/.venv/bin/python" \
  "$HOME/Library/Application Support/GuanaitongAutoClaim/code/launcher.py" --check
```

`ready`、`not_started`、`already_claimed` 可说明识别到相应页面状态；均需核对 `clicks: 0`。若是 `login_required`、网络失败或结构不匹配，先解决，不启用一个已知会失败的定时任务。

### 4. 本人确认真实定位授权

`--check` 不主动定位，`ready` 只代表识别到按钮，不能证明能够领取。先询问接收方是否允许将真实定位用于本站手动/每日任务；同意后双击“授权真实定位.command”并由本人确认。授权文件 `location-consent.json` 只保存在本机，默认不授权、不会随包发送，也不包含坐标。

需要在不领取的情况下验证定位时，在接收方明确同意后，使用 `location_access.configure_location(context)` 仅对指定站点授权，再在已登录的领取页调用 `probe_real_location(page)`；该方法只返回状态。不要设置 Playwright 虚拟位置、修改页面定位结果或关闭系统安全保护。不支持真实定位时先说明问题，不承诺后台领取可用。

可以通过运行目录的 `location_access.py --revoke` 撤销后续任务的授权，完整命令见 README。撤销不会强制中断正在执行的任务。

### 5. 获接收方确认后启用

```sh
.venv/bin/python install.py
plutil -lint "$HOME/Library/LaunchAgents/com.local.guanaitong-autoclaim.plist"
launchctl print "gui/$(id -u)/com.local.guanaitong-autoclaim"
```

安装本身不立即领取；注册后到达定时时间会自动执行。不要为了验证而 `kickstart` 或运行没有 `--check` 的领取命令，尤其在 20:30 窗口内。第一次真实领取需要另外确认，结果以网站为准。

## 交接给使用者

- “重新登录.command”：只登录，不领取；登录后由本人另行双击“立即领取.command”。
- “立即领取.command”：仅在本机 20:30–24:00 窗口内手动运行一次，可能产生真实领取点击，只有本人明确要执行时才用；不读取唤醒时间。
- “授权真实定位.command”：只对关爱通站点授权真实定位，不自动领取。需要接收方单独同意，不能继承打包者的同意。
- “仅检查.command”：全天可用，只检查状态，不领取、不主动定位、不弹窗。
- “停用定时.command”：停用本工具定时器，保留登录资料和日志。
- 日志：`~/Library/Application Support/GuanaitongAutoClaim/run.log`。
- 实际运行：Application Support 中的安装副本；改源码后需重新安装才能生效。关掉 Agent 不影响已注册的任务；删除解压目录不等于停用任务。

## 维护者技术地图与权限边界

| 入口/模块 | 数据与副作用 | 权限与停止条件 |
|---|---|---|
| `install.py` | 安装独立依赖、复制代码、生成快捷入口/LaunchAgent | 当前 macOS 用户；不使用 root。启用前取得接收方确认，同名非预期任务拒绝覆盖 |
| `login.py` → `browser_state.py` | 人工打开专用 Chrome，向官网登录，保存本机会话 | 本人输入登录资料；不代填、不输出凭证，不领取；窗口识别成功后自动关闭 |
| `location_access.py` | 本机站点授权开关；通过原生浏览器定位判断是否可用 | 默认拒绝，接收方明确同意后仅授权 c.guanaitong.com；不返回坐标、不使用虚拟位置。定位失败则停止并提醒 |
| `launcher.py` → `claim.py` → `engine.py` | 后台浏览器访问官网并点击，写安全状态日志 | 使用当前用户专用会话与定位授权；网页服务端决定账号/资格；登录失效、定位失败、验证码、目标不唯一时停止 |
| `scheduling.py` | 检查 20:30–24:00 窗口；仅自动模式读取内核启动/唤醒时间 | 只读；自动模式无法确认电源状态或睡眠补跑时拒绝执行；手动/自动领取超过窗口均拒绝，--check 不受时间限制 |

没有自建服务端、数据库或角色系统；数据边界是“本机用户 → 私有浏览器会话 → 第三方网站”。共享源码不授予他人原用户的账号权限。Agent 安装建议与实际领取动作分开，代码不内置 AI、邮件、Webhook 或公开 SEO 页面。

配置来自 `settings.py` 的 `ROOT`、`PROFILE`、`TARGET_URL`，以及 `install.py` 的本地 20:30 调度；没有需要接收方配置的 API Key。`auth-state.json` 与 `chrome-profile/` 是本机凭证，失效后由本人重新登录刷新；若泄露，应通过平台退出/撤销会话并重新登录，不分享凭证文件。日志最多 256 KiB × 4，字段不包含凭证。

定时工作：LaunchAgent → `launcher.py --scheduled`，无 KeepAlive/RunAtLoad，最多 5 次、worker 最多 120 秒。互斥锁防并发，页面“已领取”阻止重复操作；不保证服务端全局 exactly-once。日志路径、弹窗超时、锁屏限制详见 README.md。

**验证地图**：现有测试与失败分支见 `tests/test_engine.py`、`tests/test_schedule.py`、`tests/test_runtime.py`、`tests/test_location.py` 和 TESTING.md。接收电脑重跑测试与只读页面检查是启用前检查项；原报告不能代替。待确认项：接收方的真实领取（需另行授权）、不同 macOS/芯片下的行为、真实睡眠/关机边界、长期会话过期和网站后续改版。这些不是已验证通过的能力。

**相关文档**：README.md（日常行为/配置/停用）、TESTING.md（公开测试范围及缺口）、本文件（接收方安装/权限流程）、PACKAGE_MANIFEST.json（文件完整性）。沿用项目根目录 Markdown 文档布局，没有新增另一套 documentation 目录。
