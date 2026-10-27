import json, sys, collections
from where import cat, SC, ORDER
def load(aid):
    R=collections.OrderedDict(); ids={}
    cur=None
    for line in open(f"{SC}/tasks/{aid}.output"):
        o=json.loads(line); t=o.get('type'); msg=o.get('message') or {}
        if t=='assistant':
            r=o['requestId']; e=R.setdefault(r,{'ctx':None,'out':None,'own':0,'res':collections.Counter(),'reschars':0}); cur=e
            u=msg.get('usage')
            if u:
                e['ctx']=u.get('input_tokens',0)+u.get('cache_creation_input_tokens',0)+u.get('cache_read_input_tokens',0)
                if 'output_tokens_details' in u: e['out']=u['output_tokens']
            for c in msg.get('content') or []:
                if c.get('type')=='text': e['own']+=len(c['text'])
                if c.get('type')=='tool_use': e['own']+=len(json.dumps(c['input'])); ids[c['id']]=cat(c['name'],c.get('input') or {})
        if t=='user' and cur is not None:
            c=msg.get('content')
            if isinstance(c,list):
                for x in c:
                    if isinstance(x,dict) and x.get('type')=='tool_result':
                        b=x.get('content'); s=b if isinstance(b,str) else ''.join(y.get('text','') for y in (b or []) if isinstance(y,dict))
                        k=ids.get(x.get('tool_use_id'),'other'); cur['res'][k]+=len(s); cur['reschars']+=len(s)
    return list(R.values())
def split(aid):
    L=load(aid)
    # calibrate chars/token for tool results on requests with exact output
    num=den=0
    for i in range(len(L)-1):
        if L[i]['out'] is not None and L[i]['reschars']>2000:
            d=L[i+1]['ctx']-L[i]['ctx']; tr=d-L[i]['out']
            if tr>0: num+=L[i]['reschars']; den+=tr
    ratio=num/den if den else 3.0
    total=L[-1]['ctx']-L[0]['ctx']; own=sum(e['own'] for e in L)/4
    res=collections.Counter()
    for e in L[:-1]:
        for k,v in e['res'].items(): res[k]+=v/ratio
    think=total-sum(res.values())-own
    return dict(calls=len(L),ratio=ratio,total=total,res=res,own=own,think=think)
m=dict(l.split() for l in open(sys.argv[1]))
cats=['refs','docs','source','search','edit','diff','other']
print(f"{'sess':5} {'calls':>5} {'c/tok':>5} {'total':>6} | "+' '.join(f"{c:>6}" for c in cats)+f" | {'own~':>5} {'think':>6}")
out={}
for s in ORDER:
    a=split(m[s]); out[s]=a
    print(f"{s:5} {a['calls']:5} {a['ratio']:5.2f} {a['total']:6.0f} | "+' '.join(f"{a['res'][c]:6.0f}" for c in cats)+f" | {a['own']:5.0f} {a['think']:6.0f}")
json.dump({s:{k:(dict(v) if isinstance(v,collections.Counter) else v) for k,v in a.items()} for s,a in out.items()},open(sys.argv[1]+'.split.json','w'))
