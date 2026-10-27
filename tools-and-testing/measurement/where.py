import json, sys, collections, re
SC='/private/tmp/claude-501/-home-author-work-keel/d6f81098-a555-43ee-ae26-4c2f6bf95a33'
ORDER=['P-L','N-L','B-L','P-X','N-X','B-X','P-H','N-H','B-H']
def cat(name, inp):
    s=json.dumps(inp)
    if name in ('Edit','Write','MultiEdit'): return 'edit'
    if name=='Read':
        p=inp.get('file_path','')
        if 'prompt.md' in p: return 'refs'
        if re.search(r'KEEL-GRAMMAR|KEEL-GUIDE|README|INDEX|REQUIREMENTS',p): return 'docs'
        if '/src/' in p: return 'source'
        return 'other'
    if name=='Bash':
        c=inp.get('command','')
        if 'git diff' in c or 'git status' in c: return 'diff'
        if re.search(r'\b(grep|rg|find|ls)\b',c): return 'search'
        if re.search(r'\b(cat|sed|head|tail)\b',c): return 'source'
        return 'other'
    if name in ('Grep','Glob','LS'): return 'search'
    return 'other'
def where(aid):
    ids={}; tot=collections.Counter(); n=collections.Counter()
    for line in open(f"{SC}/tasks/{aid}.output"):
        o=json.loads(line); msg=o.get('message') or {}
        for c in msg.get('content') or [] if isinstance(msg.get('content'),list) else []:
            if o.get('type')=='assistant' and c.get('type')=='tool_use':
                ids[c['id']]=cat(c['name'],c.get('input') or {})
            if o.get('type')=='user' and c.get('type')=='tool_result':
                k=ids.get(c.get('tool_use_id'),'other')
                body=c.get('content'); 
                if isinstance(body,list): body=''.join(x.get('text','') for x in body if isinstance(x,dict))
                tot[k]+=len(body or '')//4; n[k]+=1
    return tot,n
m=dict(l.split() for l in open(sys.argv[1]))
cats=['refs','docs','source','search','edit','diff','other']
print(f"{'sess':5} "+' '.join(f"{c:>8}" for c in cats)+"   (tokens~ from tool results, chars/4; count in parens)")
for s in ORDER:
    t,n=where(m[s])
    print(f"{s:5} "+' '.join(f"{t[c]:5}({n[c]:2})" for c in cats))
