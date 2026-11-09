# 跨平台架构与权限边界

## 1. 设计目标

单用户、本机运行的网页领取辅助工具。系统调度负责唤起，Python 监督进程负责边界与生命周期，Playwright 驱动独立 Chrome，第三方网站负责身份与资格判断。

运行路径简图见 [README.md](../README.md#技术架构)。当前保留 `macos/`、`windows/` 两套独立安装器和系统适配层，没有在整理仓库时重构已经验证的网页逻辑。

## 2. 共同执行链路

1. 系统任务或手动入口启动 `launcher.py`，由它启动 worker。
2. 非检查模式验证 `20:30 ≤ 本机时间 < 次日 00:00`；自动模式额外检查电源状态。
3. 获取本机文件锁，避免登录与领取同时占用专用配置目录。
4. 启动 Chrome 并恢复 Cookie / localStorage / sessionStorage。人工登录使用可见窗口，正常领取使用无头模式。
5. 领取前确认本人同意，并探测目标站点的真实定位能力。未授权或定位失败则停止，不注入虚拟坐标。
6. 找到唯一今日卡片，最多尝试 5 次。每次点击前复查时间与状态；出现登录、定位或验证阻断时停止。
7. 观察明确的已领取文字或已核验印章后返回成功标记。按钮消失、余额变化、总领取人数并不单独构成代码的成功依据。
8. 关闭浏览器、释放锁，记录安全状态；必要时显示提醒。人工处理后不会自动补领。

只读检查也会打开网页、恢复并可能保存本机会话，**不是完全不写磁盘**；但不会点击、主动申请/探测定位或弹错误提醒。

## 3. 平台适配

| 能力 | macOS | Windows |
|---|---|---|
| 系统调度 | 用户级 LaunchAgent / `StartCalendarInterval` | 用户级 Task Scheduler / `CalendarTrigger` |
| 运行身份 | 当前图形会话用户 | `InteractiveToken`、`LeastPrivilege`，不存 Windows 密码 |
| 无可见控制台 | 系统直接启动 Python | 任务启动 `pythonw.exe`，worker 用隐藏进程标志 |
| 私有目录 | `~/Library/Application Support/GuanaitongAutoClaim/` | `%LOCALAPPDATA%\GuanaitongAutoClaim\` |
| 文件锁 | `fcntl.flock` | `msvcrt.locking` 单字节非阻塞锁 |
| 电源检查 | `sysctl` 的启动/最后唤醒时间 | System 电源事件、系统运行时间，运行中对比有偏/无偏计时 |
| 不唤醒/不补跑 | 脚本拒绝错过时刻后的唤醒补触发 | 任务设置禁止唤醒与补跑，并有脚本侧检查 |
| 原生提醒 | 有限等待的 `osascript` 信息框 | 限时子进程中的 Windows `MessageBoxW` |
| 超时处理 | 尝试结束本次 worker 子进程树 | 尝试 `taskkill` 本次 worker 及其子树 |
| 文件保护 | 私有目录及会话文件权限 | 本工具目录的 NTFS ACL，不修改整个 LocalAppData |

Windows 的这些原生行为目前尚待实机验证。两平台都不保证在极端资源故障下能完全清理所有进程；需结合状态日志与操作系统检查。

## 4. 模块地图

| 模块 | 角色 |
|---|---|
| `install.py` | 安装运行副本、环境和管理入口，启用或停用调度 |
| `settings.py` | 当前用户目录、目标 URL、文件锁 |
| `launcher.py` | worker 监督、日志、异常提醒 |
| `claim.py` | 时间、会话、定位及页面执行的编排 |
| `engine.py` | 今日卡片、按钮、阻断与成功状态的识别 |
| `browser_state.py` / `login.py` | 会话保存恢复 / 本人可见登录 |
| `location_access.py` | 本机定位同意、真实位置探测和撤销 |
| `scheduling.py` | 时间窗口与电源相关检查 |
| Windows 专用 `win_platform.py` / `task_scheduler.py` / `dialogs.py` | 原生系统调用、任务 XML、信息框 |
| `tools/package_source.py` | 仓库级白名单打包，不参与领取 |

## 5. 授权与数据边界

| 资源 | 谁决定 | 限制 |
|---|---|---|
| 网站身份 | 本人登录、服务端验证 | 不代填密码、不共享会话、不绕过验证码 |
| 定位 | 本人明确同意、系统提供能力 | 仅授予 `https://c.guanaitong.com`；同意不能跨用户继承 |
| 领取资格 | 网站与公司规则 | 不绕过位置、网络或账户限制 |
| 本机任务 | 当前用户主动启用 | 不擅自创建系统级高权限服务 |
| 公开源码 | 维护者审核 | 不包含任何人的会话、授权、任务配置、日志或截图 |

`auth-state.json` 是含认证材料的明文 JSON；`chrome-profile/` 可能包含更多网站缓存。文件权限不能隔离同一用户权限下的恶意软件，Windows 管理员/SYSTEM 也不在该隔离保证内。

`location-consent.json` 仅存 origin、同意开关和更新时间，不包含坐标。探测仅向 Python 返回状态；网站在正常领取流程中仍会接收并使用真实位置。

日志输出时间、模式、状态、点击尝试数、成功标记及固定错误类别，不输出原始 Cookie、坐标或接口正文。系统提醒结果可能另占文本行，因此日志不保证是严格 JSONL。

## 6. 配置与失效处理

- 当前主要参数是代码常量：目标站点、时间窗口、每日触发点、次数和超时。不能只替换 URL 就认为支持其他网站。
- 每日仅自动触发一次，worker 上限 120 秒。时间窗口延长不等于循环保活或不断重试。
- 本工具没有可靠的跨天认证续期保证。保存 Cookie 不会延长服务器有效期；需要本人重新认证时必须停止。
- 已领取印章使用已核验的资源路径识别。页面改版或未知图片时保守失败，不猜测成功。
- 文件锁和 UI 检查只是本机/页面级防重复，不保证服务端 exactly-once。
- 运行副本不自动跟随仓库更新；修改后需测试，再由平台安装器同步。

没有自建数据库、邮件服务、Webhook、云端调度或嵌入式 AI Agent，不为这些不存在的能力承诺安全保证。

## 7. 验证与相关文档

- [macOS 详细架构](../macos/ARCHITECTURE.md)
- [macOS 测试覆盖与缺口](../macos/TESTING.md)
- [Windows 实机清单](../windows/WINDOWS_VALIDATION.md)
- [安全说明](../SECURITY.md)
- [发布前检查](RELEASING.md)
