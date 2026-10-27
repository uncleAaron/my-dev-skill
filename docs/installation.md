# Windows 内网安装与使用

## 一、准备环境

在能获取源文件的电脑下载本仓库完整目录，再按公司流程带入内网。运行只需已有 Python 3.10+、Git、OpenCode 和业务项目依赖，不依赖在线 pip/npm 安装。Java、Maven、Node 等业务依赖及下游测试环境仍需项目自行预置。

PowerShell 检查：

```powershell
py -3 --version
git --version
opencode --version
```

如果电脑使用 `python` 而非 `py -3`，先验证 `python --version` 达到 3.10，再替换后续命令。若任意工具不存在，先由内部软件渠道准备，不直接在生产机器联网下载。

OpenCode 当前官方支持项目目录 `.opencode/skills/<id>/SKILL.md`；具体 v2.0.26 仍需下文实机检查。保留现有 DeepSeek 连接配置；本 Skill 不设置模型名、上下文或自动批准。

## 二、安装到业务仓库

进入本仓库目录，执行（业务路径可以含中文或空格）：

```powershell
py -3 .\scripts\install.py --target 'D:\项目\权益平台服务'
```

目标必须是已有 Git 仓库/工作树根目录。安装后应存在：

```text
D:\项目\权益平台服务\.opencode\skills\autonomous-dev\SKILL.md
```

重复安装会拒绝覆盖。更新：

```powershell
py -3 .\scripts\install.py --target 'D:\项目\权益平台服务' --update
```

原版本备份在目标 `.opencode/autonomous-dev-backups/autonomous-dev.backup-<唯一标识>`。恢复前确认没有工作流运行，保留当前目录后，将所选备份移回 autonomous-dev。备份和 staging 均位于 skills 发现树外，避免旧版本被重复发现。

## 三、首次调用

在业务仓库启动 OpenCode：

```text
使用 autonomous-dev 实现：库存调整接口必须幂等，重复请求不能重复扣减。
沿用项目现有技术栈，完成特性、详细设计、任务计划、代码、验证和沉淀。
```

Agent 应先读取项目约定与现有代码、检查 Git 状态和测试基线。会自动创建 `docs/features/<id>/` 和 `.workflow/<id>/`。特性与计划建议纳入 Git；原始运行日志默认不提交，可在项目 `.gitignore` 加 `.workflow/`。状态需保留，清理前先确认任务已交付。

如未自动加载，明确让 OpenCode 读取 `.opencode/skills/autonomous-dev/SKILL.md` 并按照它执行，检查是否发现了重复版本、当前工作目录是否正确、Skill 工具是否可用以及宿主权限。加载失败不属于业务测试失败。

## 四、手动检查与恢复

下面使用真实脚本路径，不需要额外的 wf 程序：

```powershell
py -3 '.opencode\skills\autonomous-dev\scripts\workflow.py' --root '.' status inventory-adjustment
py -3 '.opencode\skills\autonomous-dev\scripts\workflow.py' --root '.' resume inventory-adjustment
```

在 OpenCode 输入：`使用 autonomous-dev 恢复 inventory-adjustment，核对用户改动并继续。`

只有新的用户启动/继续请求才开启新 call_id；上下文压缩或程序恢复沿用已有 call_id。修复预算耗尽需用户明确允许后再重置；begin-call 只新建调用预算。

## 五、测试工具适配

verifications.json 的 argv 是参数数组。普通 Python/JDK/Node 可直接执行；Windows `.cmd/.bat` 包装器需声明显式 shell 适配器，例如 `['cmd.exe','/d','/c','mvnw.cmd','test']`，该参数数组须结合项目路径与命令内容人工审查。本脚本不默默启用 shell，也不是命令沙箱。

自动测试使用 unittest 输出或 JUnit XML。Maven/Gradle 产生的报告可加入 expected_artifacts，adapter 设为 junit；报告路径为相对业务根目录的显式文件路径，不支持通配符；执行前已存在且本次未重新生成的报告会被拒绝。构建输出目录应被项目 .gitignore 忽略，源码、测试和锁文件必须保留在指纹范围内。纯静态检查用 kind=static；不能为绕过零测试检查把业务测试改为 static。

## 六、实机验收清单

- [ ] 记录 Windows、OpenCode、Python、Git、模型的真实版本。
- [ ] 中文/空格路径安装、重复安装、更新及回退正常。
- [ ] OpenCode 发现并实际加载 autonomous-dev。
- [ ] 模型能完成一个小需求并调用实际 CLI、测试、文档与收口。
- [ ] 新会话能恢复中断任务，旧代码证据不能满足新代码验收。
- [ ] 超时终止仅清理本次进程树。
- [ ] 内网业务构建、造数、清理与真实/Mock 依赖策略明确。

以上尚未在用户的 Windows OpenCode v2.0.26 环境验证，不能视为已勾选。
