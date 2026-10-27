import unittest
from common import repo
from model import validate_tasks

def task(id='T001', deps=None):
    return dict(id=id,title='实现规则',depends_on=deps or [],ac_ids=['AC-01'],design_refs=['design.md#一'],files=['app.py'],inputs=['spec'],outputs=['app.py'],done_when=['行为符合 AC'],verification_ids=['V001'],status='pending')

class ModelTests(unittest.TestCase):
    def test_valid(self): self.assertEqual(validate_tasks({'schema_version':1,'tasks':[task()]},{'AC-01'}),[])
    def test_duplicate_cycle_reference(self):
        for tasks in [[task(),task()],[task('T001',['T002']),task('T002',['T001'])],[task('T001',['T099'])]]:
            self.assertTrue(validate_tasks({'schema_version':1,'tasks':tasks},{'AC-01'}))
    def test_missing_fields_and_ac(self):
        self.assertTrue(validate_tasks({'schema_version':1,'tasks':[{'id':'T001'}]},{'AC-01'}))
        self.assertTrue(validate_tasks({'schema_version':1,'tasks':[task()]},{'AC-02'}))
