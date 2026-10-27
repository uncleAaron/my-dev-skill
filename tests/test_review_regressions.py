import unittest,json,sys,tempfile
from pathlib import Path
from common import repo
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"examples"))
from engine import initialize,_write_tasks
from evidence import parse_test_result,run_verification,validate_evidence
from storage import atomic_write_json
from test_model import task

class ReviewRegressions(unittest.TestCase):
    def setUp(self): self.tmp,self.root=repo(); self.addCleanup(self.tmp.cleanup); initialize(self.root,'f1'); self.f=self.root/'docs/features/f1'
    def test_unittest_error_counts_are_real(self):
        result=parse_test_result('unittest',[],log='Ran 5 tests in 0.008s\n\nFAILED (failures=2, errors=15, skipped=1)\n')
        self.assertEqual(result['errors'],15); self.assertEqual(result['failures'],2); self.assertEqual(result['skipped'],1)
    def test_stale_junit_file_is_rejected(self):
        report=self.root/'report.xml'; report.write_text('<testsuite tests="8" failures="0" errors="0"/>')
        (self.root/'.gitignore').write_text('report.xml\n')
        argv=[sys.executable,'-c','pass']
        v=dict(id='V001',task_ids=['T001'],ac_ids=['AC-01'],kind='unit',downstream='none',argv=argv,cwd='.',required=True,expected_artifacts=['report.xml'],adapter='junit')
        atomic_write_json(self.f/'verifications.json',{'schema_version':1,'verifications':[v]})
        result=run_verification(self.root,'f1','V001',argv,'unit',5)
        self.assertTrue(validate_evidence(self.root,'f1',result))
    def test_render_does_not_follow_file_symlink(self):
        with tempfile.TemporaryDirectory() as other:
            outside=Path(other)/'owned.md'; outside.write_text('original')
            (self.f/'tasks.md').symlink_to(outside)
            with self.assertRaises(ValueError): _write_tasks(self.root,'f1',{'schema_version':1,'tasks':[task()]})
            self.assertEqual(outside.read_text(),'original')
    def test_installer_backup_is_outside_discovery_tree(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('installer',Path(__file__).resolve().parents[1]/'scripts/install.py'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        dest=m.install(self.root); m.install(self.root,update=True)
        self.assertEqual(len(list(dest.parent.rglob('SKILL.md'))),1)
    def test_windows_liveness_probe_does_not_send_signal(self):
        from unittest.mock import patch
        from storage import pid_alive
        with patch('storage._windows_pid_alive',return_value=True) as probe, patch('storage.os.kill') as kill:
            self.assertTrue(pid_alive(1234,platform='nt')); probe.assert_called_once_with(1234); kill.assert_not_called()
    def test_budget_failure_keeps_business_blockers(self):
        from test_engine import EngineTests
        from engine import begin_call,set_task_status,block
        from storage import read_json,WorkflowBlocked
        case=EngineTests(); case.setUp(); self.addCleanup(case.doCleanups); case.setup_task()
        call=begin_call(case.root,'f1','new')['active_call_id']; block(case.root,'f1','Await business decision')
        state=read_json(case.sp); state['calls'][call]['consumed_attempts']=30; atomic_write_json(case.sp,state)
        with self.assertRaises(WorkflowBlocked): set_task_status(case.root,'f1','T001','running',call)
        self.assertIn('Await business decision',read_json(case.sp)['blockers'])
    def test_direct_spec_edit_returns_to_specification(self):
        from demo import exercise
        from engine import resume
        state=exercise(self.root,'new')
        f=self.root/'docs/features/demo/feature.md'; f.write_text(f.read_text()+'\n新增规则：负数需要拒绝。\n')
        recovered=resume(self.root,'demo')
        self.assertEqual(recovered['stage'],'specify'); self.assertEqual(recovered['revision'],2)
    def test_partial_revision_write_cannot_resume_as_complete(self):
        from demo import exercise
        from engine import resume,revise,check
        from unittest.mock import patch
        exercise(self.root,'new')
        with patch('engine._save',side_effect=OSError('power loss')):
            with self.assertRaises(OSError): revise(self.root,'demo','new requirement')
        recovered=resume(self.root,'demo')
        self.assertNotEqual(recovered['status'],'complete')
