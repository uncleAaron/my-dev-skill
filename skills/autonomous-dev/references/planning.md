# 任务拆分

以 tasks.json 为任务真源，运行 render 生成 tasks.md。任务字段见下：

```json
{"schema_version":1,"tasks":[{"id":"T001","title":"实现规则","depends_on":[],"ac_ids":["AC-01"],"design_refs":["design.md#接口与数据"],"files":["src/app.py","tests/test_app.py"],"inputs":["AC-01 与设计契约"],"outputs":["实现及回归测试"],"done_when":["正常和错误输入的断言通过"],"verification_ids":["V001"],"status":"pending"}]}
```

一个任务应能独立验证；按依赖排序，先打通可测试的纵向切片。单独的“写代码”“写测试”“写文档”通常不是合适的业务任务边界。文档工作与所服务的变更一起完成。

在 verifications.json 声明每个验证：id、task_ids、ac_ids、kind、downstream、argv、cwd、required、expected_artifacts，自动测试加 adapter（unittest 或 junit）。命令为参数数组，路径相对业务根目录；推荐优先使用项目现有测试入口。已有失败需要记录与隔离，不归罪于本次变更，也不能隐藏。

在 acceptance.json 将每个 AC 映射到必需验证。不得留下没有验证或引用不存在的任务。依赖无环、任务输入输出明确、每项 AC 有必需验证才进入开发。
