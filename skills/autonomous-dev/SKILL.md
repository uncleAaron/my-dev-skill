---
name: autonomous-dev
description: Use when OpenCode should complete a feature, fix a defect, or resume interrupted development through specification-driven development, detailed design, task planning, implementation, tests, documentation and reusable knowledge in an existing Git repository.
---

# 自驱动开发工作流

在当前会话完成用户授权范围内的开发闭环。用规格约束实现，用当前代码对应的执行证据证明结果，把回归测试和经验留在业务仓库。

## 入口与工具

先定位 Git 业务根目录与本 Skill 的绝对路径。控制脚本仅依赖 Python 3.10+ 标准库和 Git；运行 `python "<skill>/scripts/workflow.py" --help`。Windows 使用环境中已验证的 `python` 或 `py -3`，路径含空格时加引号。

以下 `wf` 是命令简写，不是真实安装的程序：

```text
python "<skill>/scripts/workflow.py" --root "<business-root>" <command>
```

在 `.workflow/<feature-id>/state.json` 已存在时从 status/resume 进入；否则选择小写 kebab-case 特性 ID，执行 init。读取仓库已有 AGENTS.md、构建与测试规则，保留用户改动。

## 执行循环

1. 检查 Python、Git、OpenCode 版本及项目依赖；记录 Git HEAD、工作区变化、测试基线和缺失环境。读取 docs/knowledge/index.md，只加载命中主题。
2. 新特性执行 `init <id>`。新用户请求执行 `begin-call <id> --reason "请求摘要"`，保存返回的 active_call_id。上下文压缩和自动恢复沿用原 call_id；不能借重启绕过预算。
3. 按 state.stage 加载下表唯一当前阶段指导，完成该阶段产物。执行 check，阅读所有错误；完成结构检查和语义自审。
4. 将审查记录保存到 `.workflow/<id>/reviews/current.json`，内容见下。执行 `advance <id> --review "<absolute-review-file>"`，成功后自动进入下一阶段并继续循环。
5. 在 implement/verify 为就绪任务执行 `task <id> T001 --status running --call <call-id>`。在返回 attempt_id 后才编辑代码或运行任务验证。后续修复加 `--repair`。已运行任务的重复 start 幂等，不重复扣费。
6. 按声明执行 `run <id> --attempt <attempt-id> --verification V001 --kind unit`；默认使用 verifications.json 的参数数组。显式传参放在 `--` 后且必须与声明一致。读取退出码、validation_errors 和日志。验证通过后执行 task --status passed。
7. 验证失败先定位根因，结束旧尝试为 blocked，再开启修复尝试。单任务默认最多 3 次修复；同一用户调用最多 30 次任务尝试；单命令默认超时 600 秒。预算耗尽保存现场并输出解除条件。
8. 所有阶段通过才输出完成。必需验证被跳过、零用例、无环境、真实下游不可访问或关键业务决定未解决时，结果为部分完成/blocked，附恢复入口。

| 当前阶段 | 按需读取 | 主要产物 |
|---|---|---|
| intake | [需求接收](references/intake.md) | intake.md |
| specify | [特性规格](references/specification.md) | feature.md、acceptance.json |
| design | [详细设计](references/design.md) | design.md |
| plan | [任务拆分](references/planning.md) | tasks.json、tasks.md、verifications.json |
| implement | [实现](references/implementation.md) | 代码、测试、任务证据 |
| verify | [验证](references/verification.md) | verification.md、当前回归证据 |
| consolidate | [知识](references/knowledge.md)、[交付](references/delivery.md) | test-cases.md、knowledge.json/md、delivery.md、知识索引 |
| 中断/输入变化 | [恢复](references/recovery.md) | 恢复决定、失效证据、修订记录 |

## 语义审查记录

先核对业务规则、断言、副作用、兼容与文档，再填写实际结论。单 Agent 评审 reviewer 写 self。

```json
{"schema_version":1,"stage":"design","revision":1,"scope":"模块/接口/事务及AC-01","basis":"实际读取的文件、契约和证据","reviewer":"self","conclusion":"passed","findings":[]}
```

有发现时逐项记录描述、依据、处理结果和 status；所有必需问题解决后才能标记 passed。CLI 只验证结构，不能证明你的语义判断正确。

## 自主性与阻塞

普通可逆技术选择记录理由后继续；阶段通过后直接推进。业务语义、兼容、数据归属等关键歧义写入 block，并向用户提出能解除阻塞的问题；继续无依赖工作。问题解决后 `unblock <id> --index <n> --reason "解决依据"`，其他任务成功不会清除它。

尊重宿主权限与项目授权。提交/推送按现有授权处理；合并、生产发布或生产数据变更须明确授权。缺少依赖时列出具体内网准备项，不自行联网安装或放宽权限。

## 收口检查

- 当前规格、实现和证据一致；后续代码变化使旧证据失效，必须重跑。
- 真实联调与 Mock 分开记录；修复缺陷有失败复现和通过回归。
- 文档、任务、测试案例完整，知识已合并或解释无新增；执行 consolidate-knowledge。
- 输出变更、真实验证、未验证/阻塞、产物路径和恢复方式。进程退出后需用户重新调用本 Skill；它不提供后台唤醒。
