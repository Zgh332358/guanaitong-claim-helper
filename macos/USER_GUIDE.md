# 使用说明书

适用对象：在 **macOS** 上使用自己账号、具备网站领取资格的用户。本工具是非官方的本机自动化脚本，不代表关爱通或所在公司；请先确认目标平台与公司的使用规则允许此类自动化。

## 1. 功能与边界

- 每天按**电脑本机时区 20:30** 启动一次，后台打开独立的无头 Chrome，尝试领取今日时段的权益。
- 手动领取允许时间为 **20:30（含）至次日 00:00（不含）**。这是执行窗口，不是持续运行到午夜，也不是每隔几分钟重试。
- 只定位今日卡片的领取按钮，最多尝试 5 次；成功、定位失败、验证要求或不确定状态会提前停止。
- 不判断 CPU、键鼠活跃度；**锁屏不等于睡眠**，锁屏但未睡眠时仍可能执行。
- 不自动唤醒电脑；自动任务遇到睡眠/关机期间错过的时刻会跳过。手动运行不检查此前的唤醒历史。
- 不依赖 AI Agent 或终端常驻。正常自动执行不弹出 Chrome 窗口，但登录、定位授权和故障提醒需要用户交互。
- 不处理验证码、不伪造位置、不绕过公司网络或领取资格，不保证每次领取成功。

## 2. 环境要求

| 条件 | 要求 |
|---|---|
| 操作系统 | macOS，使用当前用户的普通图形桌面会话；不使用 root 安装 |
| 浏览器 | 已安装 Google Chrome；无需另行下载 Playwright Chromium |
| Python | 安装流程通过 `uv` 创建独立 Python 3.13 环境，不修改系统 Python |
| 工具与网络 | `uv` 可用；首次安装需联网下载 Python/依赖，运行时需能访问目标网站及定位服务 |
| 账号与资格 | 本人手动登录，满足网站及公司的领取条件 |
| 定位 | 本人明确同意仅向领取站点提供真实位置，且 macOS/Chrome 定位服务可用 |

暂未建立完整的 macOS 版本与 Intel/Apple Silicon 兼容矩阵。Windows、Linux 不能直接使用本安装器。

## 3. 首次安装：先准备，不急于启用定时器

### 第一步：检查已有安装

将源码解压到自己有写入权限的目录。以下示例中的路径需要替换为实际目录：

```sh
cd "/path/to/guanaitong-claim-helper/macos"
command -v uv
```

如果没有 `uv`，按其官方安装文档或本机受信任的软件管理方式安装，再继续。不要为了安装关闭系统安全保护。

先检查是否已有同名运行目录或任务：

```sh
launchctl print "gui/$(id -u)/com.local.guanaitong-autoclaim"
```

首次安装时提示找不到服务是正常的。有旧安装时先确认其来源和是否正在运行，不覆盖不明代码、登录资料或任务。

### 第二步：安装依赖并测试

```sh
uv venv .venv --python 3.13
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python install.py --prepare-only
```

当前自动化测试基线是 **51 项**，全部通过后再继续。测试采用本地模拟页面，不会实际领取。

`--prepare-only` 会准备运行副本、独立环境和 5 个快捷入口，**本次不更改任务的启用状态**。如果原来已经有定时任务，它不会因此被停用。

### 第三步：人工登录

双击源码目录内的 **`重新登录.command`**。这是一次人工操作，会打开终端和专用 Chrome。

1. 在专用窗口中使用自己的账号登录，不把密码、验证码或 Cookie 发给 Agent。
2. 请不要提前关闭窗口。进入今日领取页面后，脚本会保存会话并自动关闭专用 Chrome。
3. 登录不会自动领取，也不会关闭日常使用的 Chrome。

若窗口一直不关闭，检查是否仍停留在登录/验证页面，或网站结构已变化。登录等待约 15 分钟；失败后重新打开即可，不要盲目反复运行领取。

### 第四步：确认真实定位授权

双击 **`授权真实定位.command`**，阅读并确认弹窗。授权仅保存在当前设备，只允许 `https://c.guanaitong.com` 在任务执行期间使用浏览器真实定位，不会填入虚拟坐标。

如果仍无法定位，检查 macOS“隐私与安全性 → 定位服务”、Chrome 的系统权限及网络。仅有网站授权，并不能保证系统一定能返回位置。

### 第五步：只读检查

双击 **`仅检查.command`**，或执行安装副本：

```sh
APP="$HOME/Library/Application Support/GuanaitongAutoClaim"
"$APP/.venv/bin/python" "$APP/code/launcher.py" --check
```

检查模式全天可用，不点击领取、不主动授权或探测位置，也不弹出故障提醒。`ready` 仅表示识别到了按钮，**不代表定位和领取资格已通过**。

### 第六步：本人确认后启用每日任务

在源码目录执行：

```sh
.venv/bin/python install.py
plutil -lint "$HOME/Library/LaunchAgents/com.local.guanaitong-autoclaim.plist"
launchctl print "gui/$(id -u)/com.local.guanaitong-autoclaim"
```

确认配置为 `Hour=20`、`Minute=30`。安装不会立即领取，但启用后每天到点会自动执行。不要用 `kickstart` 做无副作用测试：在允许窗口内，它可能真的领取。

## 4. 日常使用

| 入口 | 会做什么 | 是否可能真实领取 |
|---|---|---|
| `重新登录.command` | 打开专用 Chrome，人工登录并保存会话 | 否 |
| `授权真实定位.command` | 本人确认当前设备的站点定位授权 | 否 |
| `立即领取.command` | 在 20:30–24:00 内手动运行一次 | **是** |
| `仅检查.command` | 全天检查登录和页面状态 | 否 |
| `停用定时.command` | 停用本工具的每日任务，保留本机数据 | 否 |

正常自动执行不需要事先打开 Chrome、终端或 Agent。电脑需要开机、清醒且用户已登录 macOS；登录和定位有效、网站条件满足时才能成功。

收到登录或定位提醒后，先完成处理，再自行运行一次“立即领取”。程序不会因为你重新登录或授权而自动补领。提醒约 60 秒自动关闭；锁屏期间可能看不到，之后需查日志。

## 5. 如何确认是否成功

**启动成功、进程退出码为 0、出现 `ready`、或点击了 5 次，都不能单独证明领取成功。**

优先查看网站的今日卡片/领取记录。脚本只把明确的已领取文字或已验证的今日图片印章识别为 `already_claimed`，并设置 `verified: true`；它不会仅凭按钮消失、总领取人数或余额变化判定成功。

日志位于：

```text
~/Library/Application Support/GuanaitongAutoClaim/run.log
```

脱敏示例（不是实际运行记录）：

```json
{"status":"already_claimed","clicks":0,"verified":true,"mode":"check","time":"<本机时间>"}
```

`clicks` 是本次的点击尝试数，不是到账次数；`mode` 区分 `scheduled`、`manual`、`check`。失败时可能有 `phase` 和 `error` 分类。日志还可能出现提醒是否显示成功的文本行，因此不是严格的纯 JSONL 文件。

## 6. 常见状态与故障处理

| 状态/现象 | 含义与处理 |
|---|---|
| `already_claimed` / `verified: true` | 今日页面显示已领取，不要重复点击 |
| `ready` | 找到可领取按钮；只读检查没有验证定位、资格和到账 |
| `not_started` | 网站尚未开放领取；不要强制点击 |
| `login_required` | 用“重新登录”处理，随后自行重跑 |
| `location_permission_required` | 未同意定位，或网页要求打开定位权限；先授权并检查系统设置 |
| `location_unavailable` / `location_timeout` | 未取得真实位置；检查定位服务、Chrome 权限及网络 |
| `outside_schedule_window` | 不在本机 20:30–24:00 的领取窗口内 |
| `missed_while_asleep` / `missed_while_off` | 自动任务错过时刻，不补跑；需要时可在窗口内手动运行 |
| `profile_busy` | 专用浏览器正登录或有另一个任务；等待该操作结束，不要删除锁文件或强杀日常 Chrome |
| `power_state_unknown` | 无法读取系统电源时间，自动任务保守跳过 |
| `manual_verification_required` / `dialog_requires_user` | 需要人工处理网站验证/确认，不尝试绕过 |
| `card_missing_or_ambiguous` / `button_missing_or_ambiguous` | 网站结构可能变化，需要维护者检查，不盲点坐标 |
| `click_result_uncertain` | 先检查网站是否已经领取，再决定重试，避免重复请求 |
| `attempts_complete` / `verified: false` | 已尝试满 5 次但未确认成功，仍以网站为准 |
| `execution_timeout` / `worker_failed` / `browser_or_network_error` | 运行、浏览器或网络失败；查看诊断信息，不无限重试 |

向维护者反馈时，只提供脱敏状态、操作系统/Chrome 版本和复现步骤。不要公开账号、公司内部信息、会话文件、精确位置或真实页面截图。

## 7. 停用、更新与撤销授权

**停用定时任务：** 双击“停用定时.command”。登录态、定位授权、日志会保留；这不是完整的数据删除操作。

**撤销后续定位授权：**

```sh
APP="$HOME/Library/Application Support/GuanaitongAutoClaim"
"$APP/.venv/bin/python" "$APP/code/location_access.py" --revoke
```

撤销不强制中断已经开始的任务；需要等待其退出。重新允许定位需本人再次确认。

**更新代码：** 在新源码目录先运行测试，确认没有正在执行的任务，再执行 `install.py --prepare-only` 同步代码。它保留任务当前的启用状态；需要明确启用时再运行不带参数的 `install.py`。不要复制他人的运行目录。

**完整移除：** 先停用任务并确认专用进程已退出，再由本人决定是否删除 Application Support 中的运行目录和源码。删除运行目录会丢失会话、授权和日志，操作前确认路径。仅删除源码目录不会停用已安装任务。

## 8. 隐私与公开分享

| 文件/目录 | 是否可公开 |
|---|---|
| Python 源码、自动化测试、公开文档与架构图 | 经审查且选择合适许可证后可以 |
| `chrome-profile/`、`auth-state.json` | **不可公开**，包含会话材料；后者是明文 JSON，不是加密备份 |
| `location-consent.json` | 不公开、不迁移；同意属于当前设备和用户，不可替别人授权 |
| `run.log*`、`artifacts/`、私人测试报告 | 不公开原件，可能包含个人/公司信息 |
| 安装后生成的 `.command`、LaunchAgent plist | 不复制给别人，含本机路径；应由接收方安装器生成 |
| `.venv/`、缓存、旧 ZIP | 不作为源码发布；在接收电脑重建依赖 |

本机资料目录默认按私有权限创建，会话与定位同意文件权限为 600；这不等于数据已加密，也不能防止同一用户权限下的恶意软件。请自行管理设备和磁盘加密。

向同事交付时，使用白名单打包器生成新包。每个人都需要自行安装、登录和确认定位授权。不要直接压缩整个项目文件夹或 Application Support 目录。

## 9. 常见问题

**为什么登录后仍可能无法领取？** 网站还可能检查位置、公司网络、时段、账户资格或要求验证。登录只解决身份，不保证满足其余条件。

**能否让电脑睡眠后自动唤醒领取？** 当前版本不能，也不会这样做。你可以保持清醒，或在允许窗口内自行运行，但不应绕过领取条件。

**能否只关掉终端/Agent？** 可以。已启用的 `launchd` 任务不依赖它们；不要在人工登录未保存完成时关闭专用 Chrome。

**为什么领到后还要检查？** 某些 UI 成功状态是图片而非文字。程序已支持已核验的印章，网站改版仍可能需要维护。最终以网站记录为准。

**能否换个网站直接使用？** 不能仅靠替换网址保证工作。选择器、登录流程、定位授权范围和成功判定都是站点专用的。

## 10. 进一步阅读

- [技术架构与数据边界](ARCHITECTURE.md)
- [测试方法及覆盖缺口](TESTING.md)
- [开源前检查清单](../docs/RELEASING.md)
- [交给 Agent 的安装步骤](AGENT_HANDOFF.md)

当前目录尚未选择许可证。发布者需先确认代码权属、第三方政策和许可证，再公开发布；本说明不构成平台或公司的授权。
