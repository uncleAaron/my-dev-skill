"""Persist reusable entries and a compact topic/trigger index without duplicate conclusions."""
import hashlib
import json
from pathlib import Path
from model import validate_knowledge
from storage import root_lock,resolve_feature,confined,read_json,atomic_write_json

def consolidate_knowledge(root,feature_id):
    with root_lock(root):
        source=read_json(confined(root,resolve_feature(root,feature_id)/'knowledge.json'))
        if not source.get('entries') and not source.get('no_new_reason','').strip(): raise ValueError('Explain no new knowledge')
        folder=confined(root,Path(root)/'docs/knowledge/entries'); folder.mkdir(parents=True,exist_ok=True)
        for entry in source.get('entries',[]):
            errors=validate_knowledge(entry)
            if errors: raise ValueError('; '.join(errors))
            key=hashlib.sha256(json.dumps([entry['topic'],entry['scope'],entry['conclusion']],ensure_ascii=False).encode()).hexdigest()[:20]
            p=confined(root,folder/(key+'.json'))
            data=dict(entry,schema_version=1,sources=[feature_id])
            if p.exists():
                old=read_json(p)
                data['sources']=sorted(set(old.get('sources',[])+[feature_id]))
                data['evidence']=sorted(set(old.get('evidence',[])+entry['evidence']))
            atomic_write_json(p,data)
        rows=['# 知识索引','', '按主题和触发条件检索，仅在命中时加载条目。','']
        for p in sorted(folder.glob('*.json')):
            e=read_json(p)
            if e['status']=='active': rows.append(f"- [{e['topic']}]({p.relative_to(folder.parent).as_posix()})：{e['trigger']}；范围：{e['scope']}")
        confined(root,folder.parent/'index.md').write_text('\n'.join(rows)+'\n',encoding='utf-8')
        return {'entries':len(list(folder.glob('*.json'))),'index':'docs/knowledge/index.md'}
