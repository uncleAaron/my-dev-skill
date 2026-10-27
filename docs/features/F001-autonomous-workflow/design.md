# F001：OpenCode 自驱动开发工作流详细设计

日期：2026-10-27；关联：[特性文档](feature.md)；状态：待审阅。

## 一、架构与方案选择

已选方案：主控 Skill＋按需加载的阶段文档＋Python 标准库 CLI＋持久化状态。相比纯提示词，CLI 能确定性检查状态、追踪关系与执行证据；相比外部执行器，部署更轻，可先在 Windows 内网落地。外部执行器留待后续。

主控负责语义判断、文档编写、开发、测试分析与推进。CLI 负责文件初始化、状态变更、命令执行记录、指纹、结构门禁、恢复检查。CLI 不调用模型，不自动生成业务实现，也不能证明文字的业务正确性。

## 二、仓库与安装布局

本仓库将提供 `skills/autonomous-dev/SKILL.md`、`references/`、`templates/`、`scripts/workflow.py`，以及 `scripts/install.py`、`tests/`、`examples/`、`docs/`。

安装器将一个完整 Skill 目录复制到目标业务仓库 `.opencode/skills/autonomous-dev/`。相对路径基于 Skill 所在目录；命令中引用脚本绝对路径，业务根目录显式传入。禁止默认覆盖已存在目录；更新需显式选项并保留备份。安装只接受本地资源，不改模型、权限或全局配置。

官方当前 v2 文档确认 `.opencode/skills/<skill-id>/SKILL.md` 以及同目录脚本和引用资源形式。它不等于对 v2.0.26 的兼容证明；具体版本需实机验证。前置检查记录 `opencode --version`、Python 和 Git 版本；Skill 无法发现时先解决安装阻塞。首版不生成版本敏感的权限 JSON。

## 三、运行时产物与真源

| 路径（业务仓库内） | 真源与职责 |
|---|---|
| `docs/features/<id>/feature.md` | 业务意图、AC、假设、范围 |
| `docs/features/<id>/design.md` | 实现契约、权衡、适用的设计细节 |
| `docs/features/<id>/tasks.json` | 任务编号、依赖、AC、状态、验证映射的机器真源 |
| `docs/features/<id>/tasks.md` | 由 tasks.json 渲染的可读计划；不独立手改状态 |
| `docs/features/<id>/test-cases.md` | 场景、测试文件、造数与清理、Mock/真实下游、回归入口 |
| `docs/features/<id>/verification.md` | AC → 测试 → 证据映射与语义审查结论 |
| `docs/features/<id>/delivery.md` | 变更、验证、限制、恢复/发布建议 |
| `docs/knowledge/index.md`、主题条目 | 可复用经验；入口只存索引和触发条件 |
| `.workflow/<id>/state.json` | 调度阶段、修复预算、revision、阻塞、文档指纹 |
| `.workflow/<id>/evidence/<run-id>/` | 一次执行的元数据和脱敏日志 |

规格、设计、计划、用例、总结和知识建议纳入业务 Git 历史。运行日志默认忽略，交付材料保留脱敏摘要、指纹和证据引用；需要审计归档时显式复制至项目授权目录。无归档的证据在新机器不可用，应重跑或标为不可验证。状态目录需要保留才能恢复；丢失时从资料重建到最早未验证阶段，不能伪造旧执行。

特性 ID 仅允许小写字母、数字和连字符，长度 1–64，必须以字母或数字开始结束；任务 ID 为 `T001` 形式，AC 为 `AC-01` 形式。所有路径解析后必须处于业务根目录内；拒绝 `..`、绝对特性 ID 和符号链接逃逸。

## 四、阶段与门禁

| 阶段 | 输入 | 可检查的退出条件 | 语义审查 |
|---|---|---|---|
| intake | 用户需求、仓库 | 环境、需求来源、基线与假设已记录 | 是否遗漏关键业务歧义 |
| specify | intake 记录 | feature.md 的 AC 唯一、必需章节完整 | AC 是否可观察、覆盖异常 |
| design | 特性与代码 | design.md 的 AC 引用有效、适用项齐全 | 技术契约、影响范围是否充分 |
| plan | 特性、设计 | tasks.json 合法、依赖无环、所有 AC 被覆盖 | 任务粒度与验证是否有意义 |
| implement | 就绪任务 | 所有任务完成且有有效任务验证 | 实现是否遵循规则、测试是否被削弱 |
| verify | 完整变更 | 必需 AC 有当前有效通过证据 | 用例是否实际断言了 AC；Mock 是否足够 |
| consolidate | 验收结果 | 文档/用例/知识处理结论和交付报告齐全 | 文档与行为一致、经验可复用 |
| complete | 门禁与审查 | 所有必需门禁通过、无未解决必需阻塞 | 汇总证据与实际剩余风险 |

每阶段有 pending/running/passed/blocked 状态。工作流保存 active/blocked/complete。任务保存 pending/running/passed/blocked，只有依赖 passed 的任务可运行。阶段转换必须写入结构门禁结果和 Agent 审查结论；审查记录包含范围、结论、依据、发现及解决状态。单 Agent 自审标为 self，不能称独立评审。

CLI 拒绝跳阶段、悬空引用、环依赖、重复编号及无证据完成。结构通过不能代替语义通过。文档章节写“不适用”时必须附理由，不能用空占位符冒充完成。

## 五、核心数据与 CLI 契约

`state.json` 保存 schema_version=1、feature_id、revision、stage、status、root、baseline、spec_fingerprint、workspace_fingerprint、attempts、calls、active_call_id、blockers、history。history 每条记录时间、事件、旧/新阶段与依据。一次完整 JSON 原子替换，历史与阶段一同写入，避免双文件提交不一致。

`tasks.json` 为 schema_version=1 和 tasks 数组；每项包含 id、title、depends_on、ac_ids、design_refs、files、inputs、outputs、done_when、verification_ids、status。字段类型与必填条件由共享校验函数维护；未知 schema_version 拒绝读写并说明版本。

CLI 统一形式：`python <skill>/scripts/workflow.py --root <business-repo> <command> ...`。

| 命令 | 参数与行为 |
|---|---|
| `init <id>` | 初始化文档与状态；已有特性拒绝覆盖 |
| `status <id>` | 输出阶段、就绪任务、预算、阻塞与建议下一动作 |
| `begin-call <id> --reason <text>` | 仅在新用户请求开始时创建 call_id，保留旧调用历史；进程启动或恢复不自动新建 |
| `check <id>` | 无写入地检查结构、追踪、文件存在与证据时效 |
| `advance <id> --review <file>` | 读取 JSON 审查记录并检查当前门禁；通过才转换到下一阶段 |
| `task <id> <task-id> --status <value> --call <call-id> [--repair]` | 转 running 时原子预扣任务尝试预算并返回 attempt_id；第二次及后续尝试要求 --repair 且扣修复预算；passed 时检查当前证据 |
| `run <id> --attempt <attempt-id> --verification <id> --kind <kind> --timeout <seconds> -- <argv...>` | 绑定仍活动的任务尝试，无 shell 执行命令，保存结果，执行前后计算指纹 |
| `resume <id>` | 核对工作区与状态，将陈旧通过标记失效，输出恢复动作 |
| `revise <id> --reason <text>` | revision+1，保留历史、使验证失效，回到 specify；由 Agent 重做影响分析 |
| `block <id> --reason <text>` | 保存阻塞与下一动作，允许继续无依赖任务 |
| `render <id>` | 从 tasks.json 更新 tasks.md；不修改任务语义 |

退出码：0=该操作成功；1=业务验证失败；2=输入/结构/状态冲突；3=缺依赖或阻塞；4=执行超时。run 保留被执行程序的原始退出码，CLI 使用上述规范映射。status 可以成功输出 blocked 状态，不能将命令退出码等同工作流完成。

## 六、证据、命令与指纹

验证定义文件 `verifications.json` 放在特性目录，保存 verification_id、ac_ids、task_ids、kind、argv、cwd、required、expected_artifacts。只运行已审查的显式参数列表；禁止拼接 shell 文本。Windows `.cmd`/`.bat` 工具需显式配置适配器，不能暗中启用 shell。脚本自身不承担安全沙箱职责，执行权限由宿主与项目授权控制。

kind 为 unit/integration/contract/e2e/static/manual。下游模式另记 real/mock/none。每次执行元数据包含 run_id、verification_id、argv、cwd、起止时间、超时、原始退出码、结果、Git HEAD、revision、执行前后指纹、日志路径和脱敏标记。result 为 passed/failed/error/timed_out/interrupted/skipped。

指纹使用 SHA-256，包含工作区跟踪文件、非忽略的未跟踪文件、特性规格与验证定义；排除 `.git`、`.workflow`、知识及渲染报告等明确的运行/总结输出，保留测试代码、构建配置与锁文件。记录排除集合；业务生成目录由项目显式声明。构建若修改输入导致前后指纹不同，本次证据判为 stale，先定位变化再重跑。

证据通过需要：原始退出码为 0、预期产物存在、前后指纹一致、当前指纹与证据一致。仅退出码 0 无法证明执行了测试；适配器应提取测试发现数/失败/跳过数。对于要求自动测试却无法确认测试实际执行的命令，结果需审查后才可接受；零用例、未知结果不得自动满足测试 AC。manual 记录观察过程与附件，不能冒充自动测试。

超时后终止受控子进程树并记录 timed_out；Windows 使用受限于已启动 PID 的进程树终止，POSIX 使用独立进程组；不得按程序名批量杀进程。环境值和日志默认按敏感模式脱敏；密钥不进入命令参数，脱敏不是完整保密证明，外发前审查。

## 七、恢复、并发与预算

单业务根目录写锁保护所有状态和任务变更，锁包含 PID、主机和时间；锁冲突立即退出。崩溃遗留锁仅在同主机 PID 确认退出后显式恢复；跨主机/存疑时阻塞，不自动偷锁。原子写使用同目录临时文件与 replace；写失败保留原文件，不悄悄重建损坏状态。

恢复检查 HEAD、未提交变化、规格版本与证据内容指纹。中断的 running 任务回到待核对状态并查实际文件；命令 running 证据标为 interrupted。有用户新增修改时先确定归属，不回滚或覆盖。任何输入变化使相关证据失效；首版为保证正确性保守失效全部验证，再按依赖重算阶段。

“单次调用”指用户一次启动/继续工作流的明确请求，不是一次 CLI 进程或一次模型工具调用。主控在新用户请求入口执行 begin-call，得到 call_id；上下文压缩、自动续跑及崩溃恢复沿用已有 call_id。resume 本身不能重置预算。calls 记录 id、请求摘要、开始时间和 consumed_attempts；新调用创建新计数，旧调用记录保留。此边界由主控遵守，CLI 不具备验证用户请求真实性的宿主接口，属于协作协议，不是对抗恶意 Agent 的安全边界。

每次 task 转 running 必须携带活动 call_id，根锁内先验证依赖及预算，再写入 attempt_id、首次/修复类型及计数，最后才允许编辑代码或运行验证。重复 start 对同一活动尝试返回原 attempt_id，不重复扣费；run 必须关联该任务尝试及其已声明验证，不能利用 run 绕过任务预算。一个尝试可运行多个必需验证，验证命令本身仍有超时。失败后新一次修复须先结束旧尝试，再以 --repair 预扣预算。

单任务最多 3 次自动修复；失败、异常和中断均不自动返还。首次执行不计入修复次数，但计入单次调用 30 次任务执行预算。预算达到后保存阻塞；新增调用只创建新的调用预算，任务修复预算须用户明确允许后通过 `reset-repairs <id> <task-id> --reason <text>` 重置且写历史；本命令不恢复调用预算。单命令默认超时 600 秒，可按项目显式配置。

## 八、测试、知识与文档沉淀

测试用例以真实可执行代码为主，test-cases.md 是索引而非替代。新缺陷先复现再修复；数据使用唯一运行 ID 隔离，只清理本次拥有的数据。下游真实调用与 Mock 的适用范围分别记录；缺少真实联调不能标为真实集成通过。Spring Boot 指南涵盖单元/切片、数据库集成、HTTP 契约、端到端的选择与依赖准备，不要求固定在线组件。

知识条目包含 id、主题、触发条件、适用版本/范围、结论、来源证据、复核条件、状态(active/superseded/expired)。同一结论合并，冲突结论保留替代关系。没有可复用发现时写“本次无新增经验及理由”，不强行制造 lessons。启动先读索引，只加载关联主题；索引过长时按领域分层。

特性/设计是约定真源，代码是实现事实，验证是证据。发生冲突先分析原因：代码错误修代码；规格变更走 revise，不能为让测试通过任意改验收条件。交付文档区分已实现、已验证、未验证、阻塞；引用实际执行时间和指纹。

## 九、自主性与交付边界

普通技术取舍和阶段完成自动推进，不因本 Skill 额外要求逐阶段人工批准。业务歧义影响用户结果、不可逆操作及宿主本身要求批准时才请求用户输入。第一版不自动放开 OpenCode 权限，不修改生产数据，不将提交、推送、合并或发布授权互相推定。

## 十、验证策略与兼容性

控制脚本使用 unittest + 临时 Git 仓库，覆盖路径逃逸、依赖环、陈旧证据、零用例、超时、崩溃、锁冲突和预算。端到端 fixture 使用 Python 标准库小型业务样例，覆盖新功能、缺陷修复、恢复与需求变更；仅证明工作流机制，不代表 Spring Boot 或内部服务完成联调。

Windows 实机检查包含：带空格与中文路径、安装/重复安装、Skill 发现、脚本调用、Git 状态、命令超时及新会话恢复。测试环境未具备时如实列为未验证，不能以 Linux 测试替代。

## 十一、参考与未决项

- OpenCode v2 Skills：https://opencode.ai/v2/docs/skills/ （核查日期 2026-10-27）。
- OpenCode Agent Skills：https://opencode.ai/docs/skills/ （核查日期 2026-10-27）。
- 具体内部模型名、上下文参数和业务项目测试命令由使用项目提供，不影响本工作流结构设计。
- Windows v2.0.26 的真实行为、PowerShell 与构建工具适配需要实现后实机验证；不预先声称兼容。

## 十二、设计检查记录

2026-10-27：独立只读检查提出“单次调用”的持久化边界和扣费协议缺失。已在第五、七节补充 call_id、begin-call、attempt_id、执行前原子扣费、重复 start 幂等、恢复不重置和显式重置修复预算，并在实施 Task 3 添加对应测试。此为设计检查记录，不是运行验证结论。
