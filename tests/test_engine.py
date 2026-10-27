import unittest,json,sys
from common import repo
from test_model import task
from storage import atomic_write_json,read_json,state_path,WorkflowConflict,WorkflowBlocked
from engine import initialize,begin_call,set_task_status,advance,resume,revise,validate_attempt
from evidence import run_verification

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp,self.root=repo(); self.addCleanup(self.tmp.cleanup); initialize(self.root,'f1')
        self.folder=self.root/'docs/features/f1'; self.sp=state_path(self.root,'f1')
    def setup_task(self,tasks=None):
        atomic_write_json(self.folder/'tasks.json',{'schema_version':1,'tasks':tasks or [task()]})
        argv=[sys.executable,'-c','print("valid")']
        atomic_write_json(self.folder/'verifications.json',{'schema_version':1,'verifications':[dict(id='V001',task_ids=['T001'],ac_ids=['AC-01'],kind='static',downstream='none',argv=argv,cwd='.',required=True,expected_artifacts=[])]})
        s=read_json(self.sp); s['stage']='implement'; atomic_write_json(self.sp,s)
        return argv
    def test_begin_and_repeat_start(self):
        self.setup_task(); call=begin_call(self.root,'f1','new request')['active_call_id']
        a=set_task_status(self.root,'f1','T001','running',call)
        b=set_task_status(self.root,'f1','T001','running',call)
        self.assertEqual(a['attempt_id'],b['attempt_id']); self.assertEqual(read_json(self.sp)['calls'][call]['consumed_attempts'],1)
    def test_dependencies_and_evidence_required(self):
        self.setup_task([task(),task('T002',['T001'])]); call=begin_call(self.root,'f1','new')['active_call_id']
        with self.assertRaises(WorkflowConflict): set_task_status(self.root,'f1','T002','running',call)
        set_task_status(self.root,'f1','T001','running',call)
        with self.assertRaises(WorkflowBlocked): set_task_status(self.root,'f1','T001','passed',call)
    def test_repair_budget_and_resume(self):
        self.setup_task(); call=begin_call(self.root,'f1','new')['active_call_id']
        for i in range(4):
            set_task_status(self.root,'f1','T001','running',call,repair=i>0)
            set_task_status(self.root,'f1','T001','blocked',call)
        with self.assertRaises(WorkflowBlocked): set_task_status(self.root,'f1','T001','running',call,repair=True)
        resume(self.root,'f1'); new=begin_call(self.root,'f1','continue user request')['active_call_id']
        with self.assertRaises(WorkflowBlocked): set_task_status(self.root,'f1','T001','running',new,repair=True)
        self.assertEqual(read_json(self.sp)['calls'][call]['consumed_attempts'],4)
    def test_call_limit_and_unbound_run(self):
        self.setup_task(); call=begin_call(self.root,'f1','new')['active_call_id']
        s=read_json(self.sp); s['calls'][call]['consumed_attempts']=30; atomic_write_json(self.sp,s)
        with self.assertRaises(WorkflowBlocked): set_task_status(self.root,'f1','T001','running',call)
        self.assertEqual(read_json(self.sp)['status'],'blocked')
        with self.assertRaises(WorkflowConflict): validate_attempt(self.root,'f1','missing','V001')
    def test_stale_pass_and_revision(self):
        argv=self.setup_task(); call=begin_call(self.root,'f1','new')['active_call_id']
        a=set_task_status(self.root,'f1','T001','running',call)
        run_verification(self.root,'f1','V001',argv,'static',5,a['attempt_id'])
        set_task_status(self.root,'f1','T001','passed',call)
        (self.root/'app.py').write_text('user change')
        s=resume(self.root,'f1')
        self.assertEqual(read_json(self.folder/'tasks.json')['tasks'][0]['status'],'pending')
        self.assertEqual(s['stage'],'implement'); self.assertEqual((self.root/'app.py').read_text(),'user change')
        s=revise(self.root,'f1','changed requirement'); self.assertEqual(s['revision'],2); self.assertEqual(s['stage'],'specify')
    def test_advance_requires_semantics_and_structure(self):
        with self.assertRaises(WorkflowBlocked): advance(self.root,'f1',{})
        (self.folder/'intake.md').write_text('# 项目侦察\n来源：用户\n范围：规则\n环境：检查\n基线：空\n假设：无\n关键问题：无\n')
        review=dict(schema_version=1,stage='intake',revision=1,scope='intake',basis='reviewed repo',reviewer='self',conclusion='passed',findings=[])
        self.assertEqual(advance(self.root,'f1',review)['stage'],'specify')
        with self.assertRaises(WorkflowBlocked): advance(self.root,'f1',review)
    def test_resume_interrupted_and_corrupt(self):
        self.setup_task(); call=begin_call(self.root,'f1','new')['active_call_id']; set_task_status(self.root,'f1','T001','running',call)
        resume(self.root,'f1')
        self.assertEqual(read_json(self.folder/'tasks.json')['tasks'][0]['status'],'pending')
        self.sp.write_text('broken')
        with self.assertRaises(ValueError): resume(self.root,'f1')
