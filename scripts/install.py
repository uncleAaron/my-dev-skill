#!/usr/bin/env python3
"""Copy the self-contained Skill into a Git business repository, entirely offline."""
import argparse
import os
import shutil
import sys
import uuid
from pathlib import Path

SOURCE=Path(__file__).resolve().parents[1]/'skills/autonomous-dev'

def install(target,update=False,source=SOURCE):
    root=Path(target).resolve(); source=Path(source).resolve()
    if not (root/'.git').exists(): raise ValueError('Target must be an existing Git repository/worktree root')
    dest=(root/'.opencode/skills/autonomous-dev').resolve()
    if not dest.is_relative_to(root): raise ValueError('Install destination escapes target')
    if source==root or source.is_relative_to(dest) or dest.is_relative_to(source): raise ValueError('Source and destination overlap')
    if not (source/'SKILL.md').is_file(): raise ValueError('Source SKILL.md missing')
    if any(p.is_symlink() for p in source.rglob('*')): raise ValueError('Source symlinks are unsupported')
    if dest.exists() and not update: raise FileExistsError('Skill already installed; use --update to back it up first')
    dest.parent.mkdir(parents=True,exist_ok=True)
    backups=(root/'.opencode/autonomous-dev-backups').resolve()
    if not backups.is_relative_to(root): raise ValueError('Backup destination escapes target')
    backups.mkdir(parents=True,exist_ok=True)
    stage=backups/('.stage-'+uuid.uuid4().hex)
    backup=None
    try:
        shutil.copytree(source,stage,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        if dest.exists():
            backup=backups/('autonomous-dev.backup-'+uuid.uuid4().hex)
            os.replace(dest,backup)
        try: os.replace(stage,dest)
        except BaseException:
            if backup is not None: os.replace(backup,dest)
            raise
    finally:
        if stage.exists(): shutil.rmtree(stage)
    return dest

if __name__=='__main__':
    if sys.version_info<(3,10): raise SystemExit('Python 3.10+ required')
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--target',type=Path,required=True); p.add_argument('--update',action='store_true'); a=p.parse_args()
    try: print(install(a.target,a.update))
    except (ValueError,OSError) as e: p.exit(2,str(e)+'\n')
