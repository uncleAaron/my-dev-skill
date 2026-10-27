"""Run declared commands and retain content-bound, redacted verification evidence."""
import hashlib
import json
import os
import re
import signal
import subprocess
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from storage import confined,resolve_feature,state_path,read_json,atomic_write_json,root_lock
from model import KINDS

REPORT_NAMES={'tasks.md','verification.md','delivery.md','test-cases.md','knowledge.md','knowledge.json'}

def utc():
    from datetime import datetime,timezone
    return datetime.now(timezone.utc).isoformat()

def redact(text):
    text=re.sub(r'(?i)((?:token|password|secret|api[_-]?key)\s*[=:]\s*)[^\s\"\',;]+',r'\1[REDACTED]',text)
    return re.sub(r'(?i)(Bearer\s+)[A-Za-z0-9._~+/=-]+',r'\1[REDACTED]',text)

def fingerprint(root):
    root=Path(root).resolve()
    result=subprocess.run(['git','-C',str(root),'ls-files','--cached','--others','--exclude-standard','-z'],capture_output=True,check=True)
    digest=hashlib.sha256()
    for name in sorted(set(result.stdout.decode('utf-8').split('\0'))- {''}):
        rel=Path(name)
        if any(x in {'.git','.workflow','__pycache__'} for x in rel.parts) or rel.suffix=='.pyc': continue
        if rel.parts[:2]==('docs','knowledge'): continue
        if rel.parts[:2]==('docs','features') and rel.name in REPORT_NAMES: continue
        p=confined(root,root/rel)
        digest.update(name.encode('utf-8')+b'\0')
        if not p.exists(): digest.update(b'<deleted>'); continue
        content=p.read_bytes()
        if rel.parts[:2]==('docs','features') and rel.name=='tasks.json':
            data=json.loads(content)
            for task in data.get('tasks',[]): task.pop('status',None)
            content=json.dumps(data,sort_keys=True,ensure_ascii=False).encode('utf-8')
        digest.update(content+b'\0')
    return digest.hexdigest()

def parse_test_result(adapter, artifacts, log=''):
    if adapter=='unittest':
        matches=re.findall(r'Ran (\d+) tests? in ',log)
        if not matches: return {'known':False}
        skips=re.findall(r'skipped=(\d+)',log)
        counts=dict(re.findall(r'(failures|errors|skipped)=(\d+)',log))
        return dict(known=True,tests=int(matches[-1]),failures=int(counts.get('failures',0)),errors=int(counts.get('errors',0)) if re.search(r'(?m)^(?:OK|FAILED)(?:\s|$)',log) else 1,skipped=int(counts.get('skipped',0)))
    if adapter=='junit':
        totals=dict(known=True,tests=0,failures=0,errors=0,skipped=0)
        if not artifacts: return {'known':False}
        try:
            for path in artifacts:
                tree=ET.parse(path).getroot()
                suites=[s for s in tree.iter('testsuite') if not s.findall('testsuite')]
                if not suites: return {'known':False}
                for suite in suites:
                    for k in ('tests','failures','errors','skipped'):
                        n=int(suite.get(k,'0'))
                        if n<0: return {'known':False}
                        totals[k]+=n
        except (OSError,ET.ParseError,ValueError): return {'known':False}
        return totals
    return {'known':False}

def definitions(root,fid):
    data=read_json(confined(root,resolve_feature(root,fid)/'verifications.json'))
    vs=data.get('verifications')
    if not isinstance(vs,list) or not vs: raise ValueError('No declared verifications')
    ids=[]
    for v in vs:
        if not isinstance(v,dict): raise ValueError('Verification must be object')
        vid=v.get('id')
        if not isinstance(vid,str) or not re.fullmatch(r'V\d{3,}',vid): raise ValueError('Invalid verification id')
        ids.append(vid)
        for k in ('task_ids','ac_ids','argv'):
            if not isinstance(v.get(k),list) or not v[k] or any(not isinstance(x,str) or not x for x in v[k]): raise ValueError('Invalid verification '+k)
        if v.get('kind') not in KINDS-{'manual'}: raise ValueError('Automated definition needs supported kind; manual evidence belongs in review')
        if v.get('downstream') not in {'none','real','mock'}: raise ValueError('Verification downstream must be none/real/mock')
        if type(v.get('required')) is not bool: raise ValueError('required must be boolean')
        if not isinstance(v.get('expected_artifacts'),list) or any(not isinstance(p,str) for p in v['expected_artifacts']): raise ValueError('Invalid expected_artifacts')
        confined(root,Path(root)/v.get('cwd','.'))
        for p in v['expected_artifacts']: confined(root,Path(root)/p)
    if len(set(ids))!=len(ids): raise ValueError('Duplicate verification ids')
    return {v['id']:v for v in vs}

def _terminate(process):
    if os.name=='nt':
        subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,timeout=15)
    else:
        try: os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError: pass

def run_verification(root,feature_id,verification_id,argv,kind,timeout,attempt_id=None):
    root=Path(root).resolve()
    if not isinstance(timeout,(int,float)) or timeout<=0: raise ValueError('Timeout must be positive')
    with root_lock(root):
        v=definitions(root,feature_id).get(verification_id)
        if not v or argv!=v['argv'] or kind!=v['kind']: raise ValueError('Command/kind differs from declared verification')
        cwd=confined(root,root/v.get('cwd','.'))
        if not cwd.is_dir(): raise ValueError('cwd is not a directory')
        if Path(argv[0]).suffix.lower() in {'.cmd','.bat'}: raise ValueError('Use explicit cmd.exe adapter; shell is never enabled implicitly')
        if attempt_id is not None:
            from engine import validate_attempt
            validate_attempt(root,feature_id,attempt_id,verification_id)
        sp=state_path(root,feature_id); state=read_json(sp)
        run_id='r-'+uuid.uuid4().hex
        directory=confined(root,root/'.workflow'/feature_id/'evidence'/run_id); directory.mkdir(parents=True)
        e=dict(schema_version=1,run_id=run_id,verification_id=verification_id,attempt_id=attempt_id,argv=[redact(s) for s in argv],cwd=str(cwd.relative_to(root)),kind=kind,downstream=v['downstream'],started=utc(),ended=None,timeout=timeout,revision=state['revision'],before=fingerprint(root),after=None,result='running',exit_code=None,log=str((directory/'output.log').relative_to(root)),artifacts=v['expected_artifacts'],redacted=True)
        head=subprocess.run(['git','-C',str(root),'rev-parse','HEAD'],capture_output=True,text=True)
        e['git_head']=head.stdout.strip() if head.returncode==0 else None
        e['artifact_before']={p:_artifact_stamp(confined(root,root/p)) for p in v['expected_artifacts']}
        atomic_write_json(directory/'meta.json',e)
        log=''; process=None
        try:
            process=subprocess.Popen(argv,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',start_new_session=os.name!='nt',creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name=='nt' else 0)
            try:
                log,_=process.communicate(timeout=timeout); e['exit_code']=process.returncode
                e['result']='passed' if process.returncode==0 else 'failed'
            except subprocess.TimeoutExpired:
                _terminate(process); log,_=process.communicate(timeout=15); e['result']='timed_out'; e['exit_code']=process.returncode
        except OSError as exc: log=str(exc); e['result']='error'
        except BaseException:
            if process is not None and process.poll() is None: _terminate(process); process.communicate(timeout=15)
            e['result']='interrupted'; raise
        finally:
            e['ended']=utc(); e['after']=fingerprint(root)
            safe_log=redact(log); (directory/'output.log').write_text(safe_log,encoding='utf-8')
            e['log_sha256']=hashlib.sha256(safe_log.encode('utf-8')).hexdigest()
            e['fresh_artifacts']=[p for p in v['expected_artifacts'] if _artifact_stamp(confined(root,root/p)) is not None and _artifact_stamp(confined(root,root/p))!=e['artifact_before'][p]]
            e['artifact_hashes']={p:hashlib.sha256(confined(root,root/p).read_bytes()).hexdigest() for p in v['expected_artifacts'] if confined(root,root/p).is_file()}
            e['test_result']=parse_test_result(v.get('adapter',''),[confined(root,root/p) for p in v['expected_artifacts']],safe_log)
            atomic_write_json(directory/'meta.json',e)
        return e

def validate_evidence(root,feature_id,evidence):
    root=Path(root).resolve(); e=evidence; errors=[]
    state=read_json(state_path(root,feature_id))
    if e.get('result')!='passed' or e.get('exit_code')!=0: errors.append('verification did not pass')
    if e.get('revision')!=state['revision']: errors.append('stale specification revision')
    if e.get('before')!=e.get('after') or e.get('after')!=fingerprint(root): errors.append('stale workspace fingerprint')
    v=definitions(root,feature_id).get(e.get('verification_id'))
    if not v: return errors+['unknown verification']
    if e.get('kind')!=v['kind'] or e.get('downstream')!=v['downstream']: errors.append('verification mode mismatch')
    p=confined(root,root/e.get('log','missing-log'))
    if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=e.get('log_sha256'): errors.append('log missing or changed')
    for name in v['expected_artifacts']:
        if name not in e.get('fresh_artifacts',[]): errors.append('artifact was not produced in this run: '+name)
        p=confined(root,root/name)
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=e.get('artifact_hashes',{}).get(name): errors.append('artifact missing or changed: '+name)
    if v['kind'] in {'unit','integration','contract','e2e'}:
        result=e.get('test_result',{})
        if not result.get('known') or result.get('tests',0)<=0 or any(result.get(k,0) for k in ('failures','errors','skipped')): errors.append('tests unknown, zero, failed or skipped')
    return errors

def evidence_records(root,fid):
    folder=confined(root,Path(root)/'.workflow'/fid/'evidence')
    return [read_json(p) for p in sorted(folder.glob('*/meta.json'))]


def _artifact_stamp(path):
    if not path.is_file(): return None
    stat=path.stat()
    return [stat.st_mtime_ns,stat.st_ctime_ns,stat.st_size,hashlib.sha256(path.read_bytes()).hexdigest()]
