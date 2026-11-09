# 测试方法与验证边界

本文件是可公开的验证说明，不包含个人账号、真实余额、精确运行时间、位置、运行日志或页面截图。开发阶段的私人报告不进入公开包。

## 1. 本地测试

在源码目录准备独立环境后执行：

```sh
.venv/bin/python -m py_compile *.py tests/*.py
.venv/bin/python -m unittest discover -s tests -v
```

当前基线：**51 项用例**。浏览器测试使用 Google Chrome，并拦截页面网络请求返回本地模拟内容；不会向真实领取服务提交操作。测试可能生成本地模拟截图，仍放在被忽略的 `artifacts/` 中，不纳入发布包。

| 文件 | 数量 | 类型 |
|---|---:|---|
| `tests/test_engine.py` | 19 | 本地浏览器交互与页面状态 |
| `tests/test_location.py` | 10 | 本机授权、权限范围与诊断（含 mock） |
| `tests/test_runtime.py` | 10 | 调度配置、互斥、会话与监督机制（含 mock） |
| `tests/test_schedule.py` | 12 | 时间边界、电源状态分支 |

`--check` 是真实网站的只读检查，与离线测试不同：它会访问网站和恢复本机会话，不点击领取，也不主动定位。使用前仍需本人登录；它不能证明当前位置具备领取资格。

## 2. 现有覆盖

| 使用场景 → 规则 | 预期行为（含拒绝路径） | 实现 / 用例依据 | 状态 |
|---|---|---|---|
| 到点执行 → 明确时间窗口 | 20:30 允许，次日 00:00 拒绝，午夜前最后一瞬允许 | `scheduling.py`；`test_before_start_is_rejected`、`test_last_microsecond_before_midnight_is_allowed`、`test_midnight_and_next_morning_are_rejected` | 现有 |
| 自动错过 → 不补跑 | 睡眠/关机后唤醒不触发补领；未知电源状态拒绝 | `scheduling.py`；`test_sleep_and_boot_catchup_are_still_skipped`、`test_missing_power_state_fails_closed` | 现有 |
| 手动与只读 → 区别对待 | 手动检查时间但不读电源历史；只读绕过时间且不授权/探测定位 | `claim.py`；`test_manual_mode_does_not_read_power_state`、`test_check_never_grants_or_probes_location` | 现有 |
| 锁定今日卡片 → 不误点 | 只点今日，不点明日；重复今日卡片拒绝 | `engine.py`；`test_exactly_five_when_still_available`、`test_duplicate_today_cards_fail_closed` | 现有 |
| 点击预算 → 有限尝试 | 持续可用时最多 5 次；首次成功立即停 | `engine.py`；`test_exactly_five_when_still_available`、`test_success_stops_after_one` | 现有 |
| 成功判定 → 不靠按钮消失 | 已核验今日图片/文字判成功，明日/未知印章和单纯缺按钮不算成功 | `engine.py`；`test_claimed_image_stamp_is_success_without_button`、`test_tomorrow_stamp_does_not_mark_today_claimed`、`test_unknown_stamp_is_not_assumed_to_be_success`、`test_absent_button_alone_is_not_success` | 现有 |
| 登录/验证阻断 → 停止 | 跳转登录或出现验证文案时不继续 | `engine.py`；`test_login_redirect_stops`、`test_login_expiry_midway_stops`、`test_verification_does_not_bypass` | 现有 |
| 定位弹窗 → 明确报错 | 网页定位遮罩不再误报普通点击异常，不继续点击遮挡按钮 | `engine.py`；`test_location_dialog_after_click_is_reported`、`test_existing_location_dialog_prevents_click` | 现有 |
| 定位授权 → 默认拒绝 | 缺失/损坏/其他 origin 的同意不生效；撤销阻止后续授予 | `location_access.py`；`test_missing_or_corrupt_consent_denies`、`test_consent_cannot_authorize_another_origin`、`test_revoke_prevents_future_grants` | 现有 |
| 真实位置不可用 → 不点击 | 未授权或定位不可用时返回明确状态；不注入虚拟坐标 | `claim.py`；`test_worker_does_not_click_without_consent`、`test_worker_does_not_click_when_real_location_unavailable` | 现有 |
| 互斥与私有文件 → 本机隔离 | 登录和领取不能同时拿锁；会话文件 600 权限 | `settings.py`、`browser_state.py`；`test_profile_lock_prevents_concurrent_login_and_claim`、`test_auth_snapshot_is_private_and_restores_session_cookies` | 现有 |
| 有界运行与提醒 → 不常驻 | 超时触发清理调用；提醒只打开对应人工入口，不自动领取 | `launcher.py`；`test_worker_timeout_triggers_cleanup`、`test_popup_can_open_manual_login_but_never_claims`、`test_location_reminder_never_starts_claim` | 现有，部分为 mock |
| 安全日志 → 最小结果字段 | 保留固定诊断，不透传任意私有字段 | `launcher.py`；`test_supervisor_preserves_safe_diagnostics_only` | 现有 |

开发环境还进行过带本人授权的真实登录、原生定位、领取后页面核验，以及系统任务注册/退出检查。这里只说明已做过的验证类型，不发布私人证据，也不将其视为其他设备已验证。

## 3. 建议补充但尚未实现的测试

| 用例 | 测试类型 | 目标 |
|---|---|---|
| 完整监督进程实际超时与子进程树退出 | 自动化集成 | 当前 mock 清理调用之外，验证真实异常进程的回收 |
| 真机睡眠、Dark Wake、关机后重新登录 | 受控人工 / 真机 | 验证内核时间与 `launchd` 行为，不能为了测试擅自影响用户工作 |
| 多版本 macOS、Intel/Apple Silicon 与 Chrome 升级 | 兼容性测试 | 建立明确支持矩阵 |
| 网站改版、印章资源变化、异步响应较慢 | 本地模拟 + 经授权真实验证 | 避免把新状态误判成功，并校准超时策略 |
| 日志保留策略与新增敏感字段回归 | 自动化 / 人工审查 | 确保未来代码不会写入坐标、Cookie 或请求正文 |
| 定位权限在系统层撤销后的恢复 | 经本人同意的真实测试 | 区分本机同意开关与系统提供位置的能力 |

## 4. 仍未覆盖的保证

1. **高影响：网站规则/可用性。** 没有对未来网站变更、服务器资格校验或到账强一致性的保证；最终结果必须以平台为准。
2. **高影响：设备被入侵。** 本机文件权限不是加密或恶意软件隔离，不能保证同一用户权限下的程序无法读取会话。
3. **中影响：长期运行与多设备。** 一次通过不等于连续多日或每台机器都可靠；用户需能查看失败日志并处理授权。
4. **中影响：异常系统资源。** 极端负载、系统权限变化或进程树异常下的清理，需要真实集成验证，不能只凭单元测试宣称完全覆盖。

## 5. 发布与真实测试门槛

当前没有 CI 配置或合并保护规则。建议发布前至少：语法检查、51 项测试、文档/归档校验、人工审查隐私材料与许可证。

真实测试必须单独取得使用者同意，区分“只读检查”“使用真实定位”“实际领取”三类操作。不得伪造位置、借用他人会话、为了验证擅自唤醒/休眠电脑，或将点击次数/退出码当成成功证据。

参考：[使用说明](USER_GUIDE.md) · [架构](ARCHITECTURE.md) · [开源清单](../docs/RELEASING.md)
