import unittest,tempfile,importlib.util
from pathlib import Path
from unittest.mock import patch
from common import repo

class InstallTests(unittest.TestCase):
    def setUp(self):
        spec=importlib.util.spec_from_file_location('install',Path(__file__).resolve().parents[1]/'scripts/install.py')
        self.module=importlib.util.module_from_spec(spec); spec.loader.exec_module(self.module)
        self.tmp,self.root=repo(); self.addCleanup(self.tmp.cleanup)
    def test_install_repeat_update_backup(self):
        dest=self.module.install(self.root)
        self.assertTrue((dest/'SKILL.md').is_file())
        with self.assertRaises(FileExistsError): self.module.install(self.root)
        (dest/'SKILL.md').write_text('custom version')
        self.module.install(self.root,update=True)
        backups=list((self.root/'.opencode/autonomous-dev-backups').glob('autonomous-dev.backup-*'))
        self.assertEqual((backups[0]/'SKILL.md').read_text(),'custom version')
    def test_copy_failure_preserves_original(self):
        dest=self.module.install(self.root); (dest/'SKILL.md').write_text('original')
        with patch.object(self.module.shutil,'copytree',side_effect=OSError('copy interrupted')):
            with self.assertRaises(OSError): self.module.install(self.root,update=True)
        self.assertEqual((dest/'SKILL.md').read_text(),'original')
    def test_source_overlap_and_escape(self):
        with self.assertRaises(ValueError): self.module.install(self.root,source=self.root)
        with tempfile.TemporaryDirectory() as outside:
            (self.root/'.opencode').symlink_to(outside,target_is_directory=True)
            with self.assertRaises(ValueError): self.module.install(self.root)
