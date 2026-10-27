# OpenCode 自驱动开发工作流 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. 首版默认由当前执行者顺序实现；不依赖多 Agent。

**Goal:** 实现可在 OpenCode 中驱动规格、开发、验证与沉淀全链路的首版 Skill。

**Architecture:** 主控 Skill 进行语义分析及开发，标准库 CLI 管理状态、验证与恢复。规格、任务、证据和知识均归属业务仓库；结构门禁与语义审查分别记录。

**Tech Stack:** Python 3.10+ 标准库、Git、Markdown、JSON；Windows 为首要平台。

**Spec:** [特性](../../features/F001-autonomous-workflow/feature.md)；[详细设计](../../features/F001-autonomous-workflow/design.md)。

## Global Constraints

- 首要部署环境：Windows、公司纯内网、OpenCode、内部 DeepSeek；v2.0.26 尚未实机验证。
- Python 3.10+ 标准库、Git；控制脚本运行不下载依赖，不调用外部服务。
- 单个工作流写入一个业务工作区，使用根目录写锁；多特性排队。
- 默认单任务最多 3 次自动修复，单次调用最多 30 个任务执行尝试，单命令默认超时 600 秒。
- 不自动改模型/权限，不自动合并或生产发布；不把自审称为独立评审。
- 所有任务当前均未实施；勾选必须有对应验证证据。

## Review Focus

1. 中文/空格路径、路径穿越与符号链接逃逸 → Task 1/6。
2. 中断写入、遗留锁及用户未提交改动 → Task 1/3。
3. 退出码成功但零用例、Mock 替代真实联调 → Task 2/4。
4. 代码或规格变化导致旧证据仍显示通过 → Task 2/3。
5. 反复重启会话逃避预算、超时子进程残留 → Task 2/3。

## 文件职责与共享接口

Skill 根目录：`skills/autonomous-dev/`。下面的模块均位于其 `scripts/`：

- `workflow.py`：argparse CLI，提供设计约定的命令和退出码。
- `storage.py`：安全路径、根锁、原子读写与状态版本。
- `model.py`：任务、验证定义、审查记录及门禁结构校验。
- `evidence.py`：工作区指纹、命令执行、日志与证据时效。
- `engine.py`：阶段/任务推进、预算和恢复。
- `templates/`：产物模板；`references/`：按阶段加载的执行指导。
- `scripts/install.py`：仓库根目录下的独立本地安装器。
- `tests/test_*.py`：标准库 unittest；`examples/`：可重复的离线演练。

公共接口约定：路径使用 pathlib.Path；JSON 对象使用 dict；参数错误用 ValueError，状态冲突用 WorkflowConflict，依赖阻塞用 WorkflowBlocked。CLI 统一捕获并映射退出码。只在 CLI 打印用户消息，模块返回数据。所有 JSON 输出为 UTF-8，路径记录相对于业务根目录。

## Task 1：安全存储、数据模型与初始化（AC-01/02/03/04/11/13）

**Files:** 创建 `storage.py`、`model.py`、`workflow.py`、`templates/*`、`tests/test_storage.py`、`tests/test_model.py`、`tests/test_init.py`。

**Interfaces:** `resolve_feature(root: Path, feature_id: str) -> Path`；`atomic_write_json(path: Path, data: dict) -> None`；`root_lock(root: Path)` 上下文管理器；`validate_tasks(data: dict, ac_ids: set[str]) -> list[str]`；`initialize(root: Path, feature_id: str) -> dict`。初始 schema_version=1、stage=intake、status=active、revision=1。

- [ ] 写失败测试：重复 init 不覆盖；`../x`、绝对 ID 和符号链接逃逸拒绝；中文/空格路径成功；中途 replace 失败原文件完整；锁冲突拒绝；未知 schema 拒绝；依赖环和重复编号拒绝。
- [ ] 运行 `python -m unittest discover -s tests -p "test_storage.py" -v`，确认因缺实现失败，再实现存储。
- [ ] 实现任务及验证定义结构、规格模板、init/status 命令；特性与设计模板包含验收标准、异常分支、非功能要求和适用/不适用说明。
- [ ] 运行上述三个测试模块，全部通过；检查无占位符被判作已完成，已有文件未被覆盖。
- [ ] 提交该任务代码和测试，保持后续模块能够调用这里定义的接口。

## Task 2：执行证据与验证门禁（AC-06/07/08）

**Files:** 创建 `evidence.py`、`tests/test_evidence.py`；修改 `workflow.py`、`model.py`。

**Interfaces:** `fingerprint(root: Path) -> str`；`run_verification(root: Path, feature_id: str, verification_id: str, argv: list[str], kind: str, timeout: int) -> dict`；`validate_evidence(root: Path, feature_id: str, evidence: dict) -> list[str]`。元数据、kind、result 和退出码严格按详细设计第五、六节。

- [ ] 写失败测试：成功/非零退出/命令缺失/超时/零用例/预期产物缺失/输入执行中变化/Mock 模式；参数含空格和 shell 元字符仍按字面传递；日志包含模拟密钥时脱敏。
- [ ] 运行 `python -m unittest discover -s tests -p "test_evidence.py" -v`，观察缺实现失败。
- [ ] 实现无 shell 子进程执行、进程树终止、前后指纹及日志；按验证定义审查命令，拒绝未声明命令偷偷改变验证含义。
- [ ] 实现测试计数提取接口 `parse_test_result(adapter: str, artifacts: list[Path]) -> dict`；首版支持 unittest 与 JUnit XML，无法判定执行数量时要求语义审查而非自动通过。
- [ ] 执行该模块测试，确认超时不留本任务子进程；POSIX/Windows 分别验证，缺平台时明确未验证。
- [ ] 提交代码与测试。

## Task 3：自动推进、恢复与预算（AC-05/11/12/14）

**Files:** 创建 `engine.py`、`tests/test_engine.py`、`tests/test_resume.py`；修改 `workflow.py`。

**Interfaces:** `advance(root: Path, feature_id: str, review: dict) -> dict`；`begin_call(root: Path, feature_id: str, reason: str) -> dict`；`set_task_status(root: Path, feature_id: str, task_id: str, status: str, call_id: str, repair: bool = False) -> dict`；`resume(root: Path, feature_id: str) -> dict`；`revise(root: Path, feature_id: str, reason: str) -> dict`；`check(root: Path, feature_id: str) -> list[str]`。Task 2 的 run_verification 扩展为接收 `attempt_id: str`，在执行前核对任务及活动调用。

- [ ] 写失败测试：跳阶段、无审查、未解决必需问题、未完成依赖、无当前证据均不能通过；已有用户改动不被回滚。
- [ ] 写失败测试：中断 running 恢复；代码/规格变更使证据失效；revision 增加回 specify；损坏状态报错；跨主机锁不自动接管。
- [ ] 写失败测试：3 次修复用尽后阻塞；新会话仍保留该计数；同一 call_id 第 31 个任务尝试被阻塞；resume 不重置预算；begin-call 保留旧历史且只创建新调用预算；无 attempt_id 的 run 被拒绝；重复 start 不双扣；崩溃后预扣不返还。
- [ ] 运行上述测试确认失败；实现状态转换、历史、修复前计数落盘及恢复检查。
- [ ] 运行 `python -m unittest discover -s tests -v`；确认无实现暗中授予推送/合并/发布权限。
- [ ] 提交代码与测试。

## Task 4：追踪、文档与知识闭环（AC-02/03/04/08/09/10）

**Files:** 创建 `references/{specification,design,planning,verification,knowledge}.md`、完整 `templates/`、`tests/test_traceability.py`；扩展 `model.py`、`engine.py`。

**Interfaces:** `validate_traceability(feature: str, tasks: dict, verifications: dict) -> list[str]`；`render_tasks(tasks: dict) -> str`；`validate_knowledge(entry: dict) -> list[str]`。Markdown 计划从 tasks.json 单向渲染，统一通过 workflow.py render 调用。

- [ ] 写失败测试：遗漏 AC、无效引用、无理由不适用项、未解决审查发现、将 mock 当 real、回归索引无测试文件时拒绝收口。
- [ ] 实现结构追踪与模板；手工审查清单检查 AC 是否被断言、设计是否匹配代码，而不是仅统计文件存在。
- [ ] 定义知识 active/superseded/expired 的模板和去重/替代步骤；允许无新增知识但必须有理由。
- [ ] 补充 Spring Boot 测试指南：造数、运行 ID 隔离、清理所有权、下游 Mock/真实接口、契约与联调缺口。
- [ ] 运行追踪测试；检查所有 Markdown 相对链接和模板文件引用均可解析。
- [ ] 提交文档、校验和测试。

## Task 5：主控 Skill 与离线演练（AC-01 至 AC-14）

**Files:** 创建 `skills/autonomous-dev/SKILL.md`、`references/{intake,implementation,recovery,delivery}.md`、`examples/`、`tests/test_workflow_e2e.py`。

**Interfaces:** 主控只通过上述 CLI 操作机器状态，阶段指导通过相对指针按需加载；约定用户入口“使用 autonomous-dev 完成需求……”和“使用 autonomous-dev 恢复特性……”。

- [ ] 编写主控：前置检查→恢复/初始化→当前阶段指导→门禁与自审→推进→有界修复→沉淀。普通阶段自动推进，关键业务歧义才询问。
- [ ] 建立三个独立临时样例：新功能、缺陷先失败后修复、中断后恢复并变更需求；每次运行重新生成，不读取上次通过结果。
- [ ] 在未满足 AC 的样例中断言 advance 失败；在完整样例中断言所有必需 AC 有当前证据，且交付总结真实区分自审/Mock/未验证。
- [ ] 运行 `python -m unittest discover -s tests -p "test_workflow_e2e.py" -v`；如有可用 OpenCode，在真实会话演练；脚本模拟不能冒充模型行为验证。
- [ ] 按 Skill 编写规范检查 frontmatter、名称、相对资源和上下文长度；不将编写时使用的其他 Skill 变成运行依赖。
- [ ] 提交主控与演练。

## Task 6：安装、Windows 验收与交付（AC-11/13/14）

**Files:** 创建 `scripts/install.py`、`tests/test_install.py`、`docs/installation.md`、`docs/verification.md`；更新 `README.md`。

**Interfaces:** `python scripts/install.py --target <business-root>`；更新使用 `--update`，先备份；目标 `.opencode/skills/autonomous-dev/`。完全使用本地文件。

- [ ] 写失败测试：初次安装、重复安装拒绝、更新有备份、中文与空格路径、源目标重叠拒绝、复制中断保留原安装。
- [ ] 实现安装器与回退步骤；文档列明 Python/Git 前置依赖和 `py -3`/`python` 的环境检查方法，不自动在线安装。
- [ ] 运行 `python -m unittest discover -s tests -v` 和 `python -m compileall skills/autonomous-dev/scripts scripts`；检查通过后不无理由重复全量测试。
- [ ] Windows OpenCode 实机验证 Skill 发现与触发、完整样例、新会话恢复、超时清理；记录实际版本、模型、路径及限制。缺实机时明确该验收阻塞，不写兼容完成。
- [ ] 更新 AC→证据清单、使用示例与已知限制；交付前对照特性逐项核对。仓库提交/推送及 PR 按授权执行，合并/发布不默认执行。

## 计划自审

- AC-01—14 均映射到上述任务；运行时结构检查与 Agent 语义判断明确分离。
- 共享状态、命令、指纹和退出码仅在详细设计维护，实施修改契约时同步这里和测试。
- Windows 与内部模型尚无真实环境证据，作为实机验收项保留；不得以本地测试替代。
- 阶段按依赖顺序实现，当前不需要并行 Agent 实施或外部执行器。

## 实施方式与当前状态

建议当前执行者顺序实施，完成后统一审查；设计检查意见先修订进文档。当前交付是设计与计划，尚无实现、脚本测试或 OpenCode 实机验证结论。
