# 贡献指南

感谢帮助改进这个非官方、本机运行的领取辅助工具。提交前请先读 [README.md](README.md) 和 [SECURITY.md](SECURITY.md)。

## 本地结构

- `macos/` 与 `windows/` 各自包含安装器、系统适配层及测试。
- 两个平台使用同名顶层模块，**请在各自目录中启动独立的测试进程**，不要在一个 Python 进程内混合导入两套模块。
- 当前仓库整理没有做共享模块重构；修改网页识别逻辑时，应检查两个平台是否需要同步，并分别测试。

## 运行测试

macOS，从仓库根目录开始：

```sh
cd macos
uv venv .venv --python 3.13
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python -m py_compile *.py tests/*.py
.venv/bin/python -m unittest discover -s tests -v
```

Windows，在 PowerShell 中进入仓库后：

```powershell
Set-Location windows
uv venv .venv --python 3.13
uv pip install --python .venv/Scripts/python.exe -r requirements.txt
& ./.venv/Scripts/python.exe -m unittest discover -s tests -v
```

当前基线：macOS 51 项，Windows 42 项。浏览器测试使用本地模拟内容，不向真实领取服务提交操作。Windows 的本地/模拟测试不代表原生任务调度、定位或进程回收已验证。

## 变更要求

1. 先用最小测试复现问题，再修改行为；成功和拒绝路径都要覆盖。
2. 不增加未经本人同意的定位，不改成固定位置或绕过网站资格检查。
3. 不把 `ready`、退出码 0、点击数或按钮消失当作领取成功。
4. 不向日志加入 Cookie、精确坐标、原始响应正文、带令牌的 URL 或账号资料。
5. 保留时间窗口、有界重试、同用户隔离和现有安装资料保护。
6. 不为了自动化测试擅自登录、定位、领取、唤醒/休眠电脑或启用定时任务。
7. 说明测试在哪个平台实际运行；未验证的原生能力必须列出来。
8. 修改安装、管理入口或行为后，同步更新对应平台文档和仓库 README。

## 提交问题

请给出：平台/版本、Chrome 版本、最小复现步骤、脱敏的状态分类和预期行为。不要附原始登录目录、私人运行报告、完整任务配置或真实公司页面截图。

当前没有 CI 或分支保护配置；本地测试和人工审查是必要步骤，但不能视为完整安全审计。许可证尚未由维护者确认，公开协作前需完成该事项。
