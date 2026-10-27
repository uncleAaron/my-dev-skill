import unittest
from common import repo
from test_model import task
from model import validate_traceability,validate_knowledge
from engine import initialize,check,block,unblock,set_task_status,begin_call
from storage import read_json,atomic_write_json,state_path

class TraceabilityTests(unittest.TestCase):
    def test_uncovered_and_dangling(self):
        feature='| AC-01 | rule | verified |\n| AC-02 | rule | verified |'
        tasks={'schema_version':1,'tasks':[task()]}
        vs={'schema_version':1,'verifications':[{'id':'V001','task_ids':['T001'],'ac_ids':['AC-02'],'required':True}]}
        self.assertTrue(validate_traceability(feature,tasks,vs))
    def test_knowledge_requires_evidence_and_scope(self):
        self.assertTrue(validate_knowledge({'id':'K001'}))
        entry=dict(id='K001',topic='事务',trigger='跨库写',scope='服务v1',conclusion='先留痕',evidence=['V001'],review_when='事务变化',status='active')
        self.assertEqual(validate_knowledge(entry),[])
    def test_mock_cannot_satisfy_real_acceptance(self):
        from test_engine import EngineTests
        case=EngineTests(); case.setUp(); self.addCleanup(case.doCleanups); case.setup_task()
        f=case.folder
        for name,text in [('intake.md','来源 范围 环境 基线 假设 关键问题 '+'内容完整 '*10),('feature.md','范围 业务规则 异常 非功能 验收\n| AC-01 | 规则 | 结果正确 |\n'),('design.md','模块 接口 数据 事务 幂等 异常 权限 观测 兼容 迁移 验证 '+'方案 '*20)]: (f/name).write_text(text)
        v=read_json(f/'verifications.json'); v['verifications'][0]['downstream']='mock'; atomic_write_json(f/'verifications.json',v)
        atomic_write_json(f/'acceptance.json',{'schema_version':1,'criteria':[dict(id='AC-01',verification_ids=['V001'],downstream='real')]})
        self.assertTrue(any('downstream' in e for e in check(case.root,'f1')))
    def test_blocker_not_cleared_by_unrelated_task(self):
        from test_engine import EngineTests
        case=EngineTests(); case.setUp(); self.addCleanup(case.doCleanups); case.setup_task()
        call=begin_call(case.root,'f1','new')['active_call_id']; block(case.root,'f1','business decision pending')
        set_task_status(case.root,'f1','T001','running',call)
        self.assertEqual(read_json(case.sp)['blockers'],['business decision pending'])
        unblock(case.root,'f1',0,'user clarified requirement')
        self.assertEqual(read_json(case.sp)['blockers'],[])
    def test_knowledge_persisted_and_deduplicated(self):
        from knowledge import consolidate_knowledge
        from storage import atomic_write_json
        tmp,root=repo(); self.addCleanup(tmp.cleanup); initialize(root,'f1')
        path=root/'docs/features/f1/knowledge.json'
        entry=dict(id='K001',topic='事务',trigger='跨库写',scope='服务v1',conclusion='留痕与业务同事务',evidence=['verification.md#AC-01'],review_when='事务变化',status='active')
        atomic_write_json(path,{'schema_version':1,'entries':[entry]})
        consolidate_knowledge(root,'f1'); consolidate_knowledge(root,'f1')
        self.assertTrue((root/'docs/knowledge/index.md').is_file())
        self.assertEqual(len(list((root/'docs/knowledge/entries').glob('*.json'))),1)
