"""Workflow orchestration. Public mutations hold the workspace lock."""
import json
import subprocess
from pathlib import Path
from storage import resolve_feature,state_path,atomic_write_json,read_json,root_lock,confined,WorkflowConflict

TEMPLATES=Path(__file__).resolve().parents[1]/'templates'

def initialize(root,feature_id):
    root=Path(root).resolve()
    if not (root/'.git').exists(): raise ValueError('Business root must be a Git repository/worktree')
    feature=resolve_feature(root,feature_id); sp=state_path(root,feature_id)
    with root_lock(root):
        if feature.exists() or sp.exists(): raise WorkflowConflict('Feature already exists; use resume')
        feature.mkdir(parents=True)
        for source in TEMPLATES.iterdir():
            if source.is_file(): (feature/source.name).write_text(source.read_text(encoding='utf-8'),encoding='utf-8')
        git=subprocess.run(['git','-C',str(root),'status','--porcelain'],capture_output=True,text=True,check=True)
        state=dict(schema_version=1,feature_id=feature_id,revision=1,stage='intake',status='active',root=str(root),baseline=git.stdout,attempts={},calls={},active_call_id=None,blockers=[],history=[])
        atomic_write_json(sp,state)
        return state

from model import STAGES,validate_tasks,validate_review,ac_ids,render_tasks,validate_traceability,validate_acceptance,validate_knowledge
from storage import WorkflowBlocked
from evidence import utc,fingerprint,definitions,evidence_records,validate_evidence
import uuid
import re

def _state(root,fid):
    state=read_json(state_path(root,fid))
    if state.get('feature_id')!=fid or state.get('stage') not in STAGES: raise ValueError('Invalid state identity/stage')
    return state

def _save(root,fid,state,event):
    state['history'].append(dict(time=utc(),event=event,stage=state['stage'],revision=state['revision']))
    atomic_write_json(state_path(root,fid),state)
    return state

def _tasks(root,fid): return read_json(confined(root,resolve_feature(root,fid)/'tasks.json'))

def _write_tasks(root,fid,data):
    folder=resolve_feature(root,fid)
    machine=confined(root,folder/'tasks.json'); rendered=confined(root,folder/'tasks.md')
    atomic_write_json(machine,data)
    rendered.write_text(render_tasks(data),encoding='utf-8')

def begin_call(root,feature_id,reason):
    if not reason.strip(): raise ValueError('A new user request summary is required')
    with root_lock(root):
        s=_state(root,feature_id)
        if any(a['status']=='running' for attempts in s['attempts'].values() for a in attempts): raise WorkflowConflict('An attempt is running; resume or finish it first')
        cid='c-'+uuid.uuid4().hex
        s['calls'][cid]=dict(reason=reason,started=utc(),consumed_attempts=0)
        s['active_call_id']=cid
        return _save(root,feature_id,s,'begin-call '+cid)

def validate_attempt(root,fid,attempt_id,verification_id):
    s=_state(root,fid)
    for tid,attempts in s['attempts'].items():
        for a in attempts:
            if a['id']==attempt_id and a['status']=='running' and a['call_id']==s['active_call_id']:
                t=next(t for t in _tasks(root,fid)['tasks'] if t['id']==tid)
                v=definitions(root,fid).get(verification_id)
                if t['status']=='running' and verification_id in t['verification_ids'] and v and tid in v['task_ids']: return a
    raise WorkflowConflict('No active task attempt matches this verification')

def _valid_runs(root,fid,vids,attempt_id=None):
    records=evidence_records(root,fid); found=[]
    for vid in vids:
        runs=[e for e in records if e.get('verification_id')==vid and (attempt_id is None or e.get('attempt_id')==attempt_id)]
        runs.sort(key=lambda e:e['started'])
        if not runs or validate_evidence(root,fid,runs[-1]): found.append('No current passing evidence: '+vid)
    return found

def set_task_status(root,feature_id,task_id,status,call_id,repair=False):
    if status not in {'running','passed','blocked'}: raise ValueError('Use running/passed/blocked; pending is set by resume')
    with root_lock(root):
        s=_state(root,feature_id)
        if s['stage'] not in {'implement','verify'}: raise WorkflowConflict('Tasks execute only in implement/verify')
        if call_id!=s['active_call_id'] or call_id not in s['calls']: raise WorkflowConflict('Inactive call id')
        data=_tasks(root,feature_id); ts={t['id']:t for t in data['tasks']}
        if task_id not in ts: raise ValueError('Unknown task')
        t=ts[task_id]; attempts=s['attempts'].setdefault(task_id,[])
        if status=='running':
            if attempts and attempts[-1]['status']=='running' and attempts[-1]['call_id']==call_id:
                return {'attempt_id':attempts[-1]['id'],'state':s}
            if any(x['status']=='running' for history in s['attempts'].values() for x in history): raise WorkflowConflict('Finish active attempt before starting another')
            if any(ts[d]['status']!='passed' for d in t['depends_on']): raise WorkflowConflict('Dependencies not passed')
            if attempts and not repair: raise WorkflowConflict('Subsequent attempt requires --repair')
            if s['calls'][call_id]['consumed_attempts']>=30 or sum(x['repair'] for x in attempts)>=3:
                s['status']='blocked'
                if 'Execution budget exhausted' not in s['blockers']: s['blockers'].append('Execution budget exhausted')
                _save(root,feature_id,s,'budget-blocked')
                raise WorkflowBlocked('Execution budget exhausted; no automatic reset')
            a=dict(id='a-'+uuid.uuid4().hex,call_id=call_id,status='running',repair=bool(attempts),started=utc())
            attempts.append(a); s['calls'][call_id]['consumed_attempts']+=1
        else:
            if not attempts or attempts[-1]['status']!='running': raise WorkflowConflict('No running attempt')
            a=attempts[-1]
            if status=='passed':
                errors=_valid_runs(root,feature_id,t['verification_ids'],a['id'])
                if errors: raise WorkflowBlocked('; '.join(errors))
            a['status']=status; a['ended']=utc()
        t['status']=status
        s['status']='blocked' if s['blockers'] else 'active'
        # State is authoritative for attempt accounting. Resume repairs a partial multi-file mutation.
        _save(root,feature_id,s,'task '+task_id+' '+status)
        _write_tasks(root,feature_id,data)
        return {'attempt_id':a['id'],'state':s}

def _document(folder,name,headings=()):
    p=confined(folder,folder/name)
    if not p.is_file(): return ['Missing '+name]
    text=p.read_text(encoding='utf-8')
    if len(text.strip())<30 or re.search(r'\bTODO\b|\bTBD\b|待填写',text,re.I): return ['Incomplete '+name]
    return ['Missing heading '+h+' in '+name for h in headings if h not in text]

def check(root,feature_id):
    s=_state(root,feature_id); stage=s['stage']; f=resolve_feature(root,feature_id); errors=[]
    index=STAGES.index(stage)
    if index>=0: errors+=_document(f,'intake.md',('来源','范围','环境','基线','假设','关键问题'))
    if index>=1:
        errors+=_document(f,'feature.md',('范围','业务规则','异常','非功能','验收'))
        ids=ac_ids((f/'feature.md').read_text(encoding='utf-8'))
        if not ids: errors.append('No AC identifiers')
    if index>=2: errors+=_document(f,'design.md',('模块','接口','数据','事务','幂等','异常','权限','观测','兼容','迁移','验证'))
    if index>=3:
        try:
            tasks=_tasks(root,feature_id); errors+=validate_tasks(tasks,ids)
            vs=definitions(root,feature_id)
            errors+=validate_traceability((f/'feature.md').read_text(encoding='utf-8'),tasks,{'verifications':list(vs.values())})
            errors+=validate_acceptance(read_json(confined(root,f/'acceptance.json')),ids,vs)
            for t in tasks['tasks']:
                for vid in t.get('verification_ids',[]):
                    if vid not in vs or t['id'] not in vs[vid]['task_ids']: errors.append('Task verification reference mismatch')
            for v in vs.values():
                if not set(v['ac_ids'])<=ids or not set(v['task_ids'])<={t['id'] for t in tasks['tasks']}: errors.append('Dangling verification reference')
        except (ValueError,KeyError,TypeError,OSError) as e: errors.append(str(e))
    if index>=4 and not errors:
        if any(t['status']!='passed' for t in tasks['tasks']): errors.append('Unfinished tasks')
        errors+=_valid_runs(root,feature_id,list(vs))
    if index>=5:
        errors+=_document(f,'verification.md',('AC-','证据','语义','Mock'))
    if index>=6:
        for name in ('test-cases.md','delivery.md','knowledge.md'): errors+=_document(f,name)
        if s['blockers']: errors.append('Unresolved blockers')
        knowledge=read_json(confined(root,f/'knowledge.json'))
        if knowledge.get('entries'):
            for entry in knowledge['entries']: errors+=validate_knowledge(entry)
        elif not isinstance(knowledge.get('no_new_reason'),str) or len(knowledge['no_new_reason'].strip())<10: errors.append('Explain why no reusable knowledge was added')
        for cid in ids:
            for report in ('verification.md','test-cases.md'):
                if cid not in (f/report).read_text(encoding='utf-8'): errors.append(report+' missing '+cid)
    return errors

def advance(root,feature_id,review):
    with root_lock(root):
        s=_state(root,feature_id)
        if s['stage']=='complete': raise WorkflowConflict('Already complete')
        errors=check(root,feature_id)+(['Unresolved blockers'] if s['blockers'] else [])+validate_review(review,s['stage'],s['revision'])
        if errors: raise WorkflowBlocked('; '.join(errors))
        folder=confined(root,Path(root)/'.workflow'/feature_id/'reviews'); folder.mkdir(parents=True,exist_ok=True)
        record=dict(review,fingerprint=fingerprint(root)); atomic_write_json(folder/(s['stage']+'-'+uuid.uuid4().hex+'.json'),record)
        snapshot=_input_fingerprints(root,feature_id)
        if s['stage']=='specify': s['spec_fingerprint']=snapshot['spec']
        if s['stage']=='design': s['design_fingerprint']=snapshot['design']
        if s['stage']=='plan': s['plan_fingerprint']=snapshot['plan']
        s['stage']=STAGES[STAGES.index(s['stage'])+1]
        s['status']='complete' if s['stage']=='complete' else 'active'
        s['workspace_fingerprint']=fingerprint(root)
        return _save(root,feature_id,s,'advance')

def resume(root,feature_id):
    with root_lock(root):
        s=_state(root,feature_id); data=_tasks(root,feature_id)
        snapshot=_input_fingerprints(root,feature_id)
        earliest=None
        if STAGES.index(s['stage'])>1 and s.get('spec_fingerprint') and s['spec_fingerprint']!=snapshot['spec']:
            earliest='specify'; s['revision']+=1
        elif STAGES.index(s['stage'])>2 and s.get('design_fingerprint') and s['design_fingerprint']!=snapshot['design']: earliest='design'
        elif STAGES.index(s['stage'])>3 and s.get('plan_fingerprint') and s['plan_fingerprint']!=snapshot['plan']: earliest='plan'
        if earliest:
            for t in data['tasks']: t['status']='pending'
            s['stage']=earliest; s['status']='blocked' if s['blockers'] else 'active'
            _write_tasks(root,feature_id,data)
        for attempts in s['attempts'].values():
            for a in attempts:
                if a['status']=='running': a['status']='interrupted'
        for e in evidence_records(root,feature_id):
            if e['result']=='running':
                e['result']='interrupted'; e['ended']=utc()
                atomic_write_json(confined(root,Path(root)/'.workflow'/feature_id/'evidence'/e['run_id']/'meta.json'),e)
        changed=False
        for t in data['tasks']:
            if t['status']=='running' or (t['status']=='passed' and _valid_runs(root,feature_id,t['verification_ids'])):
                t['status']='pending'; changed=True
        if changed or (STAGES.index(s['stage'])>=4 and (not data['tasks'] or any(t['status']!='passed' for t in data['tasks']))):
            s['stage']='implement' if STAGES.index(s['stage'])>=4 else s['stage']; s['status']='blocked' if s['blockers'] else 'active'
            _write_tasks(root,feature_id,data)
        # Completed runs also lose completion after code/spec changes, even if no task was passed.
        if s.get('workspace_fingerprint') and s['workspace_fingerprint']!=fingerprint(root):
            if s['stage']=='complete': s['stage']='verify'; s['status']='active'
        return _save(root,feature_id,s,'resume; inspect baseline and uncommitted changes')

def revise(root,feature_id,reason):
    if not reason.strip(): raise ValueError('Revision reason required')
    with root_lock(root):
        s=_state(root,feature_id); s['revision']+=1; s['stage']='specify'; s['status']='active'; s['blockers']=[]
        for attempts in s['attempts'].values():
            for a in attempts:
                if a['status']=='running': a['status']='interrupted'
        data=_tasks(root,feature_id)
        for t in data['tasks']: t['status']='pending'
        _write_tasks(root,feature_id,data)
        return _save(root,feature_id,s,'revise: '+reason)

def block(root,feature_id,reason):
    if not reason.strip(): raise ValueError('Blocker reason required')
    with root_lock(root):
        s=_state(root,feature_id); s['blockers'].append(reason); s['status']='blocked'
        return _save(root,feature_id,s,'block: '+reason)

def reset_repairs(root,feature_id,task_id,reason):
    if not reason.strip(): raise ValueError('Explicit user authorization summary required')
    with root_lock(root):
        s=_state(root,feature_id)
        for a in s['attempts'].get(task_id,[]): a['repair']=False
        return _save(root,feature_id,s,'user-authorized repair reset '+task_id+': '+reason)


def unblock(root,feature_id,index,reason):
    if not reason.strip(): raise ValueError('Resolution basis required')
    with root_lock(root):
        s=_state(root,feature_id)
        if index<0 or index>=len(s['blockers']): raise ValueError('Invalid blocker index')
        resolved=s['blockers'].pop(index)
        s['status']='blocked' if s['blockers'] else 'active'
        return _save(root,feature_id,s,'unblock: '+resolved+'; '+reason)


def _input_fingerprints(root,fid):
    import hashlib
    f=resolve_feature(root,fid)
    def digest(names):
        result=hashlib.sha256()
        for name in names:
            p=confined(root,f/name)
            value=p.read_bytes() if p.exists() else b'<missing>'
            if name=='tasks.json':
                data=json.loads(value)
                for t in data.get('tasks',[]): t.pop('status',None)
                value=json.dumps(data,ensure_ascii=False,sort_keys=True).encode('utf-8')
            result.update(name.encode()+b'\0'+value+b'\0')
        return result.hexdigest()
    return dict(spec=digest(['feature.md']),design=digest(['design.md']),plan=digest(['tasks.json','verifications.json','acceptance.json']))
