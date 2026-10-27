"""Deterministic offline harness, not a substitute for a real OpenCode/model session."""
import argparse,json,subprocess,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/autonomous-dev/scripts'))
from engine import initialize,advance,begin_call,set_task_status,resume,revise,_state
from evidence import run_verification,validate_evidence
from storage import atomic_write_json
from knowledge import consolidate_knowledge


def exercise(root,scenario):
    root=Path(root); fid='demo'; initialize(root,fid); folder=root/'docs/features'/fid
    (root/'tests').mkdir(exist_ok=True)
    (root/'.gitignore').write_text('.workflow/\n__pycache__/\n*.pyc\n',encoding='utf-8')
    (root/'app.py').write_text('def total(n):\n    '+('raise NotImplementedError()' if scenario=='new' else 'return n + 1')+'\n')
    (root/'tests/test_app.py').write_text('import unittest\nfrom app import total\nclass Rules(unittest.TestCase):\n    def test_zero(self): self.assertEqual(total(0),0)\n    def test_positive(self): self.assertEqual(total(4),8)\n')
    (folder/'intake.md').write_text('# 来源与范围\n用户要求计算两倍值。环境：Python 标准库；基线：错误实现。假设：整数输入；关键问题：无。\n')
    (folder/'feature.md').write_text('# 范围与业务规则\n输入整数，输出两倍；异常输入由上游类型契约约束。非功能：本地纯计算。\n## 验收\n| 编号 | 要求 | 条件 |\n|---|---|---|\n| AC-01 | 双倍计算 | 零值和正数符合定义 |\n')
    (folder/'design.md').write_text('# 模块、接口与数据\napp.total(n) 返回 n*2。事务与幂等：纯函数，无持久化。异常与权限：沿用调用方。观测：测试断言。兼容与迁移：无外部变化。验证：unittest覆盖 AC-01。\n')
    task=dict(id='T001',title='双倍计算及回归',depends_on=[],ac_ids=['AC-01'],design_refs=['design.md#模块、接口与数据'],files=['app.py','tests/test_app.py'],inputs=['AC-01'],outputs=['实现与测试'],done_when=['零值与正数通过'],verification_ids=['V001'],status='pending')
    atomic_write_json(folder/'tasks.json',{'schema_version':1,'tasks':[task]})
    argv=[sys.executable,'-B','-m','unittest','discover','-s','tests','-v']
    verification=dict(id='V001',task_ids=['T001'],ac_ids=['AC-01'],kind='unit',downstream='none',argv=argv,cwd='.',required=True,expected_artifacts=[],adapter='unittest')
    atomic_write_json(folder/'verifications.json',{'schema_version':1,'verifications':[verification]})
    atomic_write_json(folder/'acceptance.json',{'schema_version':1,'criteria':[dict(id='AC-01',verification_ids=['V001'],downstream='none')]})
    def step():
        state=_state(root,fid)
        return advance(root,fid,dict(schema_version=1,stage=state['stage'],revision=state['revision'],scope='fixture '+state['stage'],basis='Deterministic fixture assertions; not independent semantic review',reviewer='self',conclusion='passed',findings=[]))
    for _ in range(4): step()
    call=begin_call(root,fid,'offline fixture request')['active_call_id']
    a=set_task_status(root,fid,'T001','running',call)
    failed=run_verification(root,fid,'V001',argv,'unit',20,a['attempt_id'])
    if failed['result']!='failed': raise AssertionError('Fixture must exhibit failing tests before fix')
    set_task_status(root,fid,'T001','blocked',call)
    if scenario=='resume':
        resume(root,fid); revise(root,fid,'clarify multiplication rule in new user request')
        # Regression contract is unchanged; revision invalidates old evidence and replans.
        for _ in range(3): step()
        call=begin_call(root,fid,'continue after explicit new request')['active_call_id']
    a=set_task_status(root,fid,'T001','running',call,repair=True)
    (root/'app.py').write_text('def total(n):\n    return n * 2\n')
    passed=run_verification(root,fid,'V001',argv,'unit',20,a['attempt_id'])
    if validate_evidence(root,fid,passed): raise AssertionError(passed)
    set_task_status(root,fid,'T001','passed',call)
    step()
    (folder/'verification.md').write_text('# AC-01 执行证据\n'+passed['run_id']+'\n语义：两个断言覆盖零值与正数。Mock：无；真实下游：无。执行时间：'+passed['ended']+'\n指纹：'+passed['after']+'\n')
    step()
    (folder/'test-cases.md').write_text('# AC-01 回归用例\ntests/test_app.py；数据：0与4；期望：0与8；隔离：纯计算；清理：无；下游：无；执行 python -m unittest discover -s tests -v。\n')
    (folder/'delivery.md').write_text('# 交付\n已实现双倍计算，已验证零值与正数。无外部接口；无迁移；代码回退使用版本控制。此为离线脚本夹具，不代表 OpenCode 模型执行。\n')
    atomic_write_json(folder/'knowledge.json',{'schema_version':1,'entries':[],'no_new_reason':'纯计算示例没有新的项目约束或可复用架构知识，已有单元测试模式足够。'})
    (folder/'knowledge.md').write_text('# 知识处理\n检索现有索引，纯计算示例无新增经验；回归代码与验收映射已保留。无重复或冲突条目需要替代。\n')
    consolidate_knowledge(root,fid)
    step()
    return _state(root,fid)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--scenario',choices=['new','bugfix','resume'],default='new'); args=p.parse_args()
    with tempfile.TemporaryDirectory(prefix='autonomous-demo-') as directory:
        root=Path(directory); subprocess.run(['git','init','-q',str(root)],check=True)
        state=exercise(root,args.scenario)
        print(json.dumps({'scenario':args.scenario,'status':state['status'],'revision':state['revision'],'note':'Temporary deterministic harness, no OpenCode/model run'},ensure_ascii=False))
