import unittest,subprocess,sys,json,tempfile
from pathlib import Path
from common import repo
EXAMPLES=Path(__file__).resolve().parents[1]/'examples'
sys.path.insert(0,str(EXAMPLES))

class EndToEndTests(unittest.TestCase):
    def test_new_feature(self):
        from demo import exercise
        tmp,root=repo(); self.addCleanup(tmp.cleanup)
        result=exercise(root,'new')
        self.assertEqual(result['status'],'complete'); self.assertEqual(result['revision'],1)
    def test_bugfix(self):
        from demo import exercise
        tmp,root=repo(); self.addCleanup(tmp.cleanup)
        result=exercise(root,'bugfix')
        self.assertEqual(result['status'],'complete')
    def test_resume_and_requirement_change(self):
        from demo import exercise
        tmp,root=repo(); self.addCleanup(tmp.cleanup)
        result=exercise(root,'resume')
        self.assertEqual(result['status'],'complete'); self.assertEqual(result['revision'],2)
    def test_cli_requires_attempt(self):
        cli=Path(__file__).resolve().parents[1]/'skills/autonomous-dev/scripts/workflow.py'
        tmp,root=repo(); self.addCleanup(tmp.cleanup)
        p=subprocess.run([sys.executable,str(cli),'--root',str(root),'run','f1','--kind','unit','--verification','V001'],capture_output=True,text=True)
        self.assertEqual(p.returncode,2)
    def test_cli_run_options_after_feature(self):
        from test_engine import EngineTests
        case=EngineTests(); case.setUp(); self.addCleanup(case.doCleanups); case.setup_task()
        from engine import begin_call,set_task_status
        call=begin_call(case.root,'f1','new')['active_call_id']; attempt=set_task_status(case.root,'f1','T001','running',call)['attempt_id']
        cli=Path(__file__).resolve().parents[1]/'skills/autonomous-dev/scripts/workflow.py'
        p=subprocess.run([sys.executable,str(cli),'--root',str(case.root),'run','f1','--attempt',attempt,'--verification','V001','--kind','static'],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr+p.stdout)
