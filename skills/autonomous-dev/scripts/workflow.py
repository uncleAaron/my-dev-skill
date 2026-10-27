#!/usr/bin/env python3
"""Offline command-line interface. Run with --help for the stable contract."""
import argparse
import json
import subprocess
import sys
from pathlib import Path
import engine
from storage import WorkflowBlocked,WorkflowConflict,read_json,root_lock,unlock,resolve_feature,confined
from evidence import definitions,run_verification,validate_evidence
from model import render_tasks

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True,type=Path)
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ('init','status','check','resume','render','advance','begin-call','revise','block','reset-repairs','task','run','unblock','consolidate-knowledge'):
        p=sub.add_parser(name); p.add_argument('feature_id')
        if name in ('begin-call','revise','block','reset-repairs','unblock'): p.add_argument('--reason',required=True)
        if name=='advance': p.add_argument('--review',required=True,type=Path)
        if name in ('task','reset-repairs'): p.add_argument('task_id')
        if name=='unblock': p.add_argument('--index',required=True,type=int)
        if name=='task':
            p.add_argument('--status',choices=['running','passed','blocked'],required=True); p.add_argument('--call',required=True); p.add_argument('--repair',action='store_true')
        if name=='run':
            p.add_argument('--attempt',required=True); p.add_argument('--verification',required=True); p.add_argument('--timeout',type=float,default=600)
            p.add_argument('--kind',required=True)
    sub.add_parser('unlock')
    raw=list(sys.argv[1:] if argv is None else argv)
    command_argv=[]
    if '--' in raw:
        marker=raw.index('--'); command_argv=raw[marker+1:]; raw=raw[:marker]
    args=parser.parse_args(raw); root=args.root.resolve()
    if command_argv and args.command!='run': parser.error('Command argv supported only for run')
    try:
        cmd=args.command; fid=getattr(args,'feature_id',None); code=0
        if cmd=='init': result=engine.initialize(root,fid)
        elif cmd=='begin-call': result=engine.begin_call(root,fid,args.reason)
        elif cmd=='task': result=engine.set_task_status(root,fid,args.task_id,args.status,args.call,args.repair)
        elif cmd=='advance': result=engine.advance(root,fid,read_json(args.review))
        elif cmd=='resume': result=engine.resume(root,fid)
        elif cmd=='revise': result=engine.revise(root,fid,args.reason)
        elif cmd=='consolidate-knowledge':
            from knowledge import consolidate_knowledge
            result=consolidate_knowledge(root,fid)
        elif cmd=='block': result=engine.block(root,fid,args.reason)
        elif cmd=='unblock': result=engine.unblock(root,fid,args.index,args.reason)
        elif cmd=='reset-repairs': result=engine.reset_repairs(root,fid,args.task_id,args.reason)
        elif cmd=='check':
            result={'errors':engine.check(root,fid)}; code=2 if result['errors'] else 0
        elif cmd=='status':
            result=engine._state(root,fid); data=engine._tasks(root,fid); by_id={t['id']:t for t in data['tasks']}
            result=dict(result,ready_tasks=[t['id'] for t in data['tasks'] if t['status']=='pending' and all(by_id[d]['status']=='passed' for d in t['depends_on'])])
        elif cmd=='render':
            with root_lock(root):
                path=confined(root,resolve_feature(root,fid)/'tasks.md'); path.write_text(render_tasks(engine._tasks(root,fid)),encoding='utf-8'); result={'rendered':str(path)}
        elif cmd=='unlock': unlock(root); result={'unlocked':True}
        elif cmd=='run':
            declared=definitions(root,fid).get(args.verification)
            command=command_argv
            if not declared: raise ValueError('Unknown verification')
            command=command or declared['argv']
            result=run_verification(root,fid,args.verification,command,args.kind,args.timeout,args.attempt)
            errors=validate_evidence(root,fid,result); result['validation_errors']=errors
            code=4 if result['result']=='timed_out' else 3 if result['result']=='error' else 1 if errors else 0
        print(json.dumps(result,ensure_ascii=False,indent=2)); return code
    except WorkflowBlocked as e: print(json.dumps({'blocked':str(e)},ensure_ascii=False)); return 3
    except (ValueError,WorkflowConflict,KeyError,TypeError) as e: print(json.dumps({'error':str(e)},ensure_ascii=False)); return 2
    except (OSError,subprocess.SubprocessError) as e: print(json.dumps({'dependency_or_io_error':str(e)},ensure_ascii=False)); return 3

if __name__=='__main__': sys.exit(main())
