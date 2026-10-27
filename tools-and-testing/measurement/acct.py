import json, sys, collections
SC = '/private/tmp/claude-501/-home-author-work-keel/d6f81098-a555-43ee-ae26-4c2f6bf95a33'
ORDER = ['P-L','N-L','B-L','P-X','N-X','B-X','P-H','N-H','B-H']

def acct(agent_id):
    reqs = collections.OrderedDict(); own = 0
    for line in open(f"{SC}/tasks/{agent_id}.output"):
        o = json.loads(line); msg = o.get('message') or {}
        if o.get('type') != 'assistant': continue
        if msg.get('usage'): reqs[o.get('requestId')] = msg['usage']
        for c in msg.get('content') or []:
            if c.get('type') == 'text': own += len(c['text'])
            if c.get('type') == 'tool_use': own += len(json.dumps(c.get('input')))
    ctx = [u.get('input_tokens',0)+u.get('cache_creation_input_tokens',0)+u.get('cache_read_input_tokens',0) for u in reqs.values()]
    refs = ctx[1]-ctx[0]; work = ctx[-1]-ctx[1]
    return dict(calls=len(ctx), refs=refs, work=work, cum=sum(ctx), cumrefs=sum(ctx)-refs*(len(ctx)-1), own=own//4)

mapfile = sys.argv[1]
m = dict(l.split() for l in open(mapfile))
print(f"{'sess':5} {'calls':>5} {'refs':>7} {'work':>7} {'cum-refs':>9} {'own~':>6}")
for s in ORDER:
    if s not in m: continue
    try: a = acct(m[s])
    except Exception as e: print(s, 'ERR', e); continue
    print(f"{s:5} {a['calls']:5} {a['refs']:7} {a['work']:7} {a['cumrefs']:9} {a['own']:6}")
