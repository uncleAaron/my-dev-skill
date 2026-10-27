import unittest,sys,json,subprocess
from common import repo
from engine import initialize
from storage import atomic_write_json
from evidence import fingerprint,run_verification,validate_evidence,parse_test_result

class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp,self.root=repo(); self.addCleanup(self.tmp.cleanup); initialize(self.root,'f1')
    def define(self,code,**kw):
        argv=[sys.executable,'-c',code]
        self.definition=dict(id='V001',task_ids=['T001'],ac_ids=['AC-01'],kind='static',downstream='none',argv=argv,cwd='.',required=True,expected_artifacts=[],**kw)
        atomic_write_json(self.root/'docs/features/f1/verifications.json',{'schema_version':1,'verifications':[self.definition]})
        return argv
    def run(self,*a,**kw):
        # unittest.TestCase.run is not the runner under test.
        return super().run(*a,**kw)
    def test_success_literal_argv_and_redaction(self):
        argv=self.define('print("token=secret123 ; $(whoami)")')
        e=run_verification(self.root,'f1','V001',argv,'static',5)
        self.assertEqual(e['result'],'passed'); self.assertFalse(validate_evidence(self.root,'f1',e))
        self.assertNotIn('secret123',(self.root/e['log']).read_text())
        self.assertNotIn('secret123',json.dumps(e))
    def test_nonzero_missing_timeout(self):
        for code,expected in [('raise SystemExit(7)','failed'),('import time; time.sleep(5)','timed_out')]:
            e=run_verification(self.root,'f1','V001',self.define(code),'static',0.1)
            self.assertEqual(e['result'],expected); self.assertTrue(validate_evidence(self.root,'f1',e))
        argv=self.define('print(1)'); argv[0]='nonexistent-command-123'
        self.definition['argv']=argv
        atomic_write_json(self.root/'docs/features/f1/verifications.json',{'schema_version':1,'verifications':[self.definition]})
        self.assertEqual(run_verification(self.root,'f1','V001',argv,'static',1)['result'],'error')
    def test_stale_and_mutated_input(self):
        e=run_verification(self.root,'f1','V001',self.define('print(1)'),'static',5)
        (self.root/'app.py').write_text('new code')
        self.assertTrue(validate_evidence(self.root,'f1',e))
        argv=self.define('from pathlib import Path; Path("app.py").write_text("changed")')
        e=run_verification(self.root,'f1','V001',argv,'static',5)
        self.assertNotEqual(e['before'],e['after']); self.assertTrue(validate_evidence(self.root,'f1',e))
    def test_zero_unknown_and_skips_not_pass(self):
        for code in ['print("Ran 0 tests in 0s\\nOK")','print("hello")','print("Ran 2 tests in 0s\\nOK (skipped=1)")']:
            argv=self.define(code); self.definition['kind']='unit'; self.definition['adapter']='unittest'
            atomic_write_json(self.root/'docs/features/f1/verifications.json',{'schema_version':1,'verifications':[self.definition]})
            e=run_verification(self.root,'f1','V001',argv,'unit',5)
            self.assertTrue(validate_evidence(self.root,'f1',e))
    def test_missing_artifact_and_mock(self):
        argv=self.define('print(1)'); self.definition.update(expected_artifacts=['missing.xml'],downstream='mock')
        atomic_write_json(self.root/'docs/features/f1/verifications.json',{'schema_version':1,'verifications':[self.definition]})
        e=run_verification(self.root,'f1','V001',argv,'static',5)
        self.assertEqual(e['downstream'],'mock'); self.assertTrue(validate_evidence(self.root,'f1',e))
    def test_junit(self):
        p=self.root/'result.xml'; p.write_text('<testsuites><testsuite tests="3" failures="0" errors="0" skipped="0"/></testsuites>')
        self.assertEqual(parse_test_result('junit',[p])['tests'],3)
    def test_shell_mismatch_and_escape_rejected(self):
        argv=self.define('print(1)')
        with self.assertRaises(ValueError): run_verification(self.root,'f1','V001',argv+[';touch x'],'static',1)
