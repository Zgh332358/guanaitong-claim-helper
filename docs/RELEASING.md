# 发布前检查

## 项目与远端

项目名称：**`guanaitong-claim-helper`**。

仓库地址：`https://github.com/Zgh332358/guanaitong-claim-helper`。

本项目是站点专用的非官方辅助工具，不应使用“永久免登录”“任何设备已验证”或“保证领取成功”等表述。

## 维护者需要确认

- [ ] 确认有权公开当前代码，并检查平台及公司相关规则。
- [ ] 选择许可证并加入 `LICENSE`。如果希望宽松复用，可考虑 MIT；由维护者决定。
- [ ] 配置私密安全反馈渠道。
- [ ] 完成或明确标注 Windows 实机验证状态。

当前没有 `LICENSE`。公开可见不等于已授予通用开源使用权，也不能宣称“已按 MIT 开源”。

## 每次提交前检查

- [ ] 只提交仓库中的公开源码，不提交系统运行目录。
- [ ] 不含会话、定位同意、账号、日志、私人报告、真实截图或本机生成的启动入口。
- [ ] macOS 与 Windows 的源码/测试在各自目录中完整，链接和命令路径有效。
- [ ] macOS 51 项、Windows 42 项测试通过，执行环境与未验证边界表述准确。
- [ ] 没有把本地/模拟测试误称为 Windows 原生验证。
- [ ] 修改过的行为说明与实际代码一致，不承诺跨天自动续期。

`.gitignore` 和白名单打包器都不能替代实际暂存内容与既有历史的审查。凭证如果已经泄露，应先在平台撤销，不能只删除当前文件。

## Git 操作参考

已有仓库先检查状态与远端，不能重复初始化或强制覆盖历史：

```sh
git status
git remote -v
git diff --stat
```

仅在首次创建新的本地仓库时：

```sh
git init -b main
git remote add origin https://github.com/Zgh332358/guanaitong-claim-helper.git
```

按实际变更暂存公开文件，检查后再提交；如果已经创建许可证，也要审查并暂存该文件：

```sh
git add README.md .gitignore CONTRIBUTING.md SECURITY.md docs macos windows tools
git diff --cached --stat
# 人工审查暂存内容，再执行 git commit。
git push -u origin main
```

如果远端已存在提交，先检查并整合，不要使用 force-push 覆盖。若认证或网络失败，先解决实际问题，不把本地提交成功等同于远端已更新。

## 生成可分享源码包

在仓库根目录使用 Python 3.10+：

```sh
python3 tools/package_source.py --output ../guanaitong-claim-helper-source.zip
```

包内含 `PACKAGE_MANIFEST.json`，外部附 SHA-256 校验文件。清单用于完整性检查，不是签名；Git 检出无需预先存在该清单。
