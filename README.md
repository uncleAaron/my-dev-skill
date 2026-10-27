# my-dev-skill

面向 OpenCode 的自驱动 SDD 开发工作流。交付需求后，在当前会话中依次完成特性文档、详细设计、任务拆分、开发、测试验证、回归案例、知识及交付文档；中断后从仓库状态恢复。

**当前状态：首版 Skill、控制脚本、模板、安装器和离线样例已实现。Linux/Python 测试已运行；Windows OpenCode v2.0.26 与内部 DeepSeek 尚未实机验证。** 这不是无人值守后台执行器，进程退出后需再次调用 Skill。

## 快速安装

前置：Python 3.10+、Git、已有 Git 业务仓库和能够调用工具的 OpenCode。无需安装 pip 包，也不修改现有模型与权限配置。

将本仓库完整复制到电脑；Windows PowerShell 中进入本仓库：

```powershell
py -3 --version
git --version
opencode --version
py -3 .\scripts\install.py --target 'D:\code\benefit-service'
```

然后在业务仓库打开 OpenCode，输入：

```text
使用 autonomous-dev 完成这个需求：……
自动完成特性、详细设计、任务拆分、实现、验证、测试案例和知识沉淀。
```

恢复时输入：`使用 autonomous-dev 恢复特性 <feature-id>，先核对当前代码与证据再继续。`

更新使用 `--update`，会保留原版本备份。详细步骤、中文/空格路径与内网准备见 [安装与使用](docs/installation.md)。

## 机制与产物

- 主控 Skill 按阶段加载指导，普通取舍自动推进，关键业务歧义才询问。
- CLI 检查阶段、任务依赖、验收映射、真实/Mock 模式和证据时效；语义正确性仍由 Agent 审查。
- `.workflow/<id>/` 保存状态、预算、审查和脱敏日志；`docs/features/<id>/` 保存特性、设计、计划、案例与交付资料。
- `docs/knowledge/` 保存按主题与触发条件检索的经验索引，重复结论合并来源。
- 默认单任务最多 3 次修复、单用户调用最多 30 次任务尝试；新会话不自动重置修复预算。
- 支持 unittest/JUnit XML 测试结果；零测试、跳过、未知、超时和陈旧结果不能自动收口。

## 验证本仓库

```powershell
py -3 -m unittest discover -s tests -v
py -3 examples/demo.py --scenario new
py -3 examples/demo.py --scenario bugfix
py -3 examples/demo.py --scenario resume
```

样例使用临时 Git 仓库和真实 unittest，分别演示新功能、先失败后修复及恢复/需求修订；属于确定性脚本演练，不等同 OpenCode 模型实机执行。

## 文档

- [特性与验收标准](docs/features/F001-autonomous-workflow/feature.md)
- [详细设计](docs/features/F001-autonomous-workflow/design.md)
- [实施任务计划](docs/superpowers/plans/2026-10-27-autonomous-workflow.md)
- [安装与使用](docs/installation.md)
- [验证记录与限制](docs/verification.md)

本仓库不内置业务模型服务，不需要运行时访问 GitHub 或外网，也不自动合并、生产发布或修改生产数据。
