"""Confined paths, atomic JSON and exclusive workspace mutations."""
import contextlib
import json
import os
import re
import socket
import tempfile
from pathlib import Path

class WorkflowConflict(RuntimeError): pass
class WorkflowBlocked(RuntimeError): pass

def confined(root, path):
    root=Path(root).resolve(); path=Path(path).resolve()
    if not path.is_relative_to(root): raise ValueError('Path escapes business root')
    return path

def resolve_feature(root, feature_id):
    if not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?', feature_id):
        raise ValueError('Feature id must be lowercase kebab-case, 1..64 characters')
    return confined(root, Path(root)/'docs/features'/feature_id)

def state_path(root, fid):
    resolve_feature(root,fid)
    return confined(root,Path(root)/'.workflow'/fid/'state.json')

def atomic_write_json(path, data):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.write-',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8',newline='\n') as f:
            json.dump(data,f,ensure_ascii=False,indent=2); f.write('\n'); f.flush(); os.fsync(f.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name): os.unlink(name)

def read_json(path):
    if Path(path).is_symlink(): raise ValueError('JSON file symlinks are unsupported')
    with Path(path).open(encoding='utf-8') as f: data=json.load(f)
    if not isinstance(data,dict) or data.get('schema_version')!=1: raise ValueError('Unsupported or missing schema_version; expected 1')
    return data

@contextlib.contextmanager
def root_lock(root):
    directory=confined(root,Path(root)/'.workflow'); directory.mkdir(exist_ok=True)
    path=confined(root,directory/'write.lock')
    try: fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError as e: raise WorkflowConflict('Workspace locked; inspect lock, use unlock only after owner exits') from e
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f: json.dump({'pid':os.getpid(),'host':socket.gethostname()},f)
        yield
    finally: path.unlink(missing_ok=True)

def unlock(root):
    p=confined(root,Path(root)/'.workflow/write.lock')
    data=json.loads(p.read_text(encoding='utf-8'))
    if data.get('host')!=socket.gethostname(): raise WorkflowConflict('Foreign host lock needs manual investigation')
    if pid_alive(int(data['pid'])): raise WorkflowConflict('Lock owner is still alive')
    p.unlink()

def _windows_pid_alive(pid):
    # A synchronize-only handle can be waited on without signaling or terminating it.
    import ctypes
    from ctypes import wintypes
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
    kernel.WaitForSingleObject.restype=wintypes.DWORD
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    kernel.CloseHandle.restype=wintypes.BOOL
    handle=kernel.OpenProcess(0x00100000,False,pid)
    if not handle:
        if ctypes.get_last_error()==87: return False
        raise WorkflowConflict('Cannot query Windows lock owner; keep lock')
    try:
        result=kernel.WaitForSingleObject(handle,0)
        if result==258: return True
        if result==0: return False
        raise WorkflowConflict('Windows process state unknown; keep lock')
    finally: kernel.CloseHandle(handle)

def pid_alive(pid,platform=None):
    if pid<=0: raise ValueError('Invalid lock PID')
    if (platform or os.name)=='nt': return _windows_pid_alive(pid)
    try: os.kill(pid,0)
    except ProcessLookupError: return False
    except OSError as e: raise WorkflowConflict('Cannot query lock owner; keep lock') from e
    return True
