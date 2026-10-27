# 知识沉淀

先检索 docs/knowledge/index.md；按主题与触发条件加载相关条目。经验与当前代码冲突时优先检查适用版本及证据，不能机械遵循旧结论。

只沉淀可复用规则、有效诊断、真实约束或测试模式。每条 knowledge.json entry 包含 id、topic、trigger、scope、conclusion、evidence（引用已核对的证据）、review_when、status。active 可用；superseded 必须有 replaced_by；expired 不出现在活跃索引。

相同主题/范围/结论由 consolidate-knowledge 合并来源和证据；不同结论由 Agent 比较证据并显式替代旧条目。命令不会自动判断语义冲突。需要替代已有条目时更新 docs/knowledge/entries 中的状态并重新生成索引。索引超过易读范围时分主题拆分，并更新入口指针。

没有值得复用的经验时 entries=[]，no_new_reason 写清理由，仍执行 consolidate-knowledge。knowledge.md 记录检索、合并、替代及处理结果。经验引用不能包含密钥、客户数据或生产凭证。
