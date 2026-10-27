import sys, tempfile, subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'skills/autonomous-dev/scripts'))

def repo():
    tmp=tempfile.TemporaryDirectory(prefix='工作流 test ')
    root=Path(tmp.name)
    subprocess.run(['git','init','-q',str(root)],check=True)
    return tmp,root
