import unittest
from common import repo
from engine import initialize

class InitTests(unittest.TestCase):
    def test_init_and_no_overwrite(self):
        tmp,root=repo(); self.addCleanup(tmp.cleanup)
        result=initialize(root,'f1')
        self.assertEqual(result['stage'],'intake')
        p=root/'docs/features/f1/feature.md'; p.write_text('user content')
        with self.assertRaises(Exception): initialize(root,'f1')
        self.assertEqual(p.read_text(),'user content')
