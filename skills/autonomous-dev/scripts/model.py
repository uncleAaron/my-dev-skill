"""Deterministic structural validation; semantic review stays with the agent."""
import re
STAGES=('intake','specify','design','plan','implement','verify','consolidate','complete')
STATUSES={'pending','running','passed','blocked'}
KINDS={'unit','integration','contract','e2e','static','manual'}

def validate_tasks(data, ac_ids):
    errors=[]
    if not isinstance(data,dict) or data.get('schema_version')!=1: return ['tasks schema_version must be 1']
    tasks=data.get('tasks')
    if not isinstance(tasks,list) or not tasks: return ['tasks must be a non-empty array']
    ids=[]; covered=set()
    list_fields=('depends_on','ac_ids','design_refs','files','inputs','outputs','done_when','verification_ids')
    for t in tasks:
        if not isinstance(t,dict): errors.append('task must be an object'); continue
        tid=t.get('id',''); ids.append(tid)
        if not isinstance(tid,str) or not re.fullmatch(r'T\d{3,}',tid): errors.append('invalid task id')
        if not isinstance(t.get('title'),str) or not t['title'].strip(): errors.append(f'{tid}: missing title')
        if t.get('status') not in STATUSES: errors.append(f'{tid}: invalid status')
        for k in list_fields:
            v=t.get(k)
            if not isinstance(v,list) or any(not isinstance(x,str) or not x.strip() for x in v) or (not v and k!='depends_on'):
                errors.append(f'{tid}: invalid {k}')
        ac=t.get('ac_ids',[])
        if isinstance(ac,list) and all(isinstance(x,str) for x in ac):
            covered.update(ac)
            if not set(ac)<=ac_ids: errors.append(f'{tid}: unknown AC')
    if len(ids)!=len(set(ids)): errors.append('duplicate task id')
    graph={t['id']:t.get('depends_on',[]) for t in tasks if isinstance(t,dict) and isinstance(t.get('id'),str) and isinstance(t.get('depends_on',[]),list)}
    visited=set(); active=set()
    def visit(n):
        if n in active: errors.append('task dependency cycle'); return
        if n in visited: return
        active.add(n)
        for d in graph.get(n,[]):
            if not isinstance(d,str) or d not in graph: errors.append(f'{n}: missing dependency')
            else: visit(d)
        active.remove(n); visited.add(n)
    for n in graph: visit(n)
    if not ac_ids<=covered: errors.append('uncovered AC: '+', '.join(sorted(ac_ids-covered)))
    return errors

def ac_ids(text): return set(re.findall(r'(?m)^\|\s*(AC-\d+)\s*\|',text))

def validate_review(review,stage,revision):
    if not isinstance(review,dict) or review.get('schema_version')!=1: return ['invalid review schema']
    errors=[]
    for k in ('scope','basis','reviewer'):
        if not isinstance(review.get(k),str) or not review[k].strip(): errors.append('review missing '+k)
    if review.get('stage')!=stage or review.get('revision')!=revision: errors.append('review stage/revision mismatch')
    if review.get('conclusion')!='passed': errors.append('semantic review did not pass')
    if not isinstance(review.get('findings'),list) or any(not isinstance(f,dict) or f.get('status')!='resolved' for f in review.get('findings',[])): errors.append('unresolved/invalid findings')
    return errors

def render_tasks(data):
    lines=['# 任务计划','', '| 任务 | 依赖 | 验收 | 完成条件 | 状态 |','|---|---|---|---|---|']
    for t in data['tasks']:
        cells=[t['id']+' '+t['title'],', '.join(t['depends_on']),', '.join(t['ac_ids']),'; '.join(t['done_when']),t['status']]
        lines.append('| '+' | '.join(x.replace('|','\\|').replace('\n',' ') for x in cells)+' |')
    return '\n'.join(lines)+'\n'

def validate_traceability(feature,tasks,verifications):
    ids=ac_ids(feature); errors=validate_tasks(tasks,ids)
    vs={v['id']:v for v in verifications.get('verifications',[])}
    ts={t['id']:t for t in tasks.get('tasks',[])}
    covered=set()
    for tid,t in ts.items():
        for vid in t.get('verification_ids',[]):
            v=vs.get(vid)
            if not v or tid not in v.get('task_ids',[]): errors.append('Task/verification linkage mismatch: '+tid); continue
            if not set(v.get('ac_ids',[]))<=set(t.get('ac_ids',[])): errors.append('Verification claims AC outside its task: '+vid)
    for vid,v in vs.items():
        if not set(v.get('task_ids',[]))<=set(ts) or not set(v.get('ac_ids',[]))<=ids: errors.append('Dangling verification: '+vid)
        if v.get('required'): covered.update(v.get('ac_ids',[]))
    if not ids<=covered: errors.append('AC lacks required verification: '+', '.join(sorted(ids-covered)))
    return errors

def validate_acceptance(data,ids,vs):
    errors=[]; rows=data.get('criteria',[])
    if not isinstance(rows,list) or not rows: return ['acceptance criteria must be nonempty']
    found=[]
    for c in rows:
        if not isinstance(c,dict): errors.append('invalid acceptance row'); continue
        cid=c.get('id'); found.append(cid)
        vids=c.get('verification_ids')
        if not isinstance(vids,list) or not vids or any(not isinstance(x,str) for x in vids): errors.append('Invalid acceptance verification_ids'); continue
        if c.get('downstream') not in {'none','real','mock'}: errors.append('Invalid acceptance downstream')
        for vid in vids:
            v=vs.get(vid)
            if not v or cid not in v['ac_ids'] or not v['required']: errors.append('Acceptance evidence reference mismatch')
            elif c['downstream']!=v['downstream']: errors.append('Acceptance downstream mismatch: '+str(cid))
    if any(not isinstance(x,str) for x in found) or len(found)!=len(set(found)) or set(found)!=ids: errors.append('Acceptance must list each AC exactly once')
    return errors

def validate_knowledge(entry):
    errors=[]
    for key in ('id','topic','trigger','scope','conclusion','review_when'):
        if not isinstance(entry.get(key),str) or not entry[key].strip(): errors.append('Knowledge missing '+key)
    if not isinstance(entry.get('evidence'),list) or not entry['evidence']: errors.append('Knowledge needs evidence')
    if entry.get('status') not in {'active','superseded','expired'}: errors.append('Invalid knowledge status')
    if entry.get('status')=='superseded' and not entry.get('replaced_by'): errors.append('Superseded entry needs replaced_by')
    return errors
