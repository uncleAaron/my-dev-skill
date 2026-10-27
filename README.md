# my-dev-skill

面向 OpenCode 的自驱动、规格驱动开发工作流。

当前阶段：设计与实施计划已编写；Skill、脚本和 OpenCode 运行验证尚未实现。

## 设计入口

- [特性文档](docs/features/F001-autonomous-workflow/feature.md)：目标、范围、验收条件。
- [详细设计](docs/features/F001-autonomous-workflow/design.md)：阶段、状态、证据、恢复、测试与知识沉淀。
- [实施任务计划](docs/superpowers/plans/2026-10-27-autonomous-workflow.md)：文件职责、接口、实施顺序与验证。

第一版采用主控 Skill、按需加载的阶段说明、Python 标准库脚本及仓库持久化状态。在活跃的 OpenCode 会话中自动推进；中断后通过重新调用 Skill 恢复。进程自动重启、自动合并及生产发布不在第一版范围。

首要目标是 Windows 内网 OpenCode；不要求 GitHub、外网、第三方 Skill 或额外在线服务。内部模型沿用用户现有配置。

本文档不是安装指南；安装说明和可运行产物将在实现阶段补齐。
