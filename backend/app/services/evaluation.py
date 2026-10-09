"""Small reproducible diagnostic corpus; never claimed as broad ML accuracy."""
from app.domain.fingerprints import normalize

PAIRS=[
 ('File test.py:12 Error: refused','File test.py:98 Error: refused',True,'source line volatility'),
 ('Timeout after 20ms','Timeout after 90ms',True,'elapsed duration'),
 ('Error: expected 200 got 500','Error: expected 200 got 404',False,'HTTP codes retained'),
 ('AssertionError: expected 3 got 2','AssertionError: expected 3 got 1',False,'numeric assertions retained'),
 ('Error at 0xabcdef12','Error at 0x998877aa',True,'memory addresses'),
 ('Error: permission denied','Error: connection denied',False,'failure semantics'),
 ('2026-01-01T10:00:00Z Error: exit','2026-04-01T12:10:00Z Error: exit',True,'timestamps'),
 ('TypeError: missing argument','ValueError: missing argument',False,'exception classes'),
 ('[10:01:00] Error: timeout','[12:02:30] Error: timeout',True,'clock prefixes'),
 ('Error: database users missing','Error: database orders missing',False,'resource names'),
 ('Error: exit 1','Error: exit 2',False,'exit codes'),
 ('Error: test.ts:10:8 mismatch','Error: test.ts:20:4 mismatch',True,'TypeScript positions'),
]

def evaluate():
    rows=[{'left':a,'right':b,'expected_same':same,'actual_same':normalize(a)==normalize(b),'case':label} for a,b,same,label in PAIRS]
    return {'total':len(rows),'passed':sum(r['expected_same']==r['actual_same'] for r in rows),'cases':rows,
            'scope':'Handwritten normalization regression fixtures. No claim of general root-cause accuracy or calibrated flakiness prediction.'}

if __name__=='__main__':
    import json
    result=evaluate()
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if result['passed']==result['total'] else 1)
