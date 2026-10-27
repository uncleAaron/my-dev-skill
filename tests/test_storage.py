import unittest, json
from unittest.mock import patch
from common import repo
from storage import resolve_feature, atomic_write_json, root_lock, read_json

class StorageTests(unittest.TestCase):
    def setUp(self): self.tmp,self.root=repo(); self.addCleanup(self.tmp.cleanup)
    def test_identifier_and_spaces(self):
        self.assertTrue(str(resolve_feature(self.root,'f-001')).endswith('f-001'))
        for bad in ['../x','/x','a/b','A','x..y','x-','']:
            with self.assertRaises(ValueError): resolve_feature(self.root,bad)
    def test_symlink_escape(self):
        import tempfile
        with tempfile.TemporaryDirectory() as outside:
            (self.root/'docs').symlink_to(outside,target_is_directory=True)
            with self.assertRaises(ValueError): resolve_feature(self.root,'f1')
    def test_atomic_write_preserves_original(self):
        p=self.root/'state.json'; atomic_write_json(p,{'schema_version':1,'a':1})
        with patch('storage.os.replace',side_effect=OSError('write failed')):
            with self.assertRaises(OSError): atomic_write_json(p,{'a':2})
        self.assertEqual(read_json(p)['a'],1)
    def test_lock_conflict(self):
        with root_lock(self.root):
            with self.assertRaises(Exception):
                with root_lock(self.root): pass
    def test_unknown_or_corrupt_schema(self):
        p=self.root/'s.json'; p.write_text('{"schema_version":99}')
        with self.assertRaises(ValueError): read_json(p)
        p.write_text('broken')
        with self.assertRaises(ValueError): read_json(p)
